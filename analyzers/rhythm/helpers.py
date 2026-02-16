from app_data import RHYTHM_TOKEN_MAP
import math
from models import PartialNoteData
from .rules import normalize_tuplet_class, TUPLET_CLASS_ORDER

TOKEN_DURATION_MAP = {data["token"]: data["duration"] for data in RHYTHM_TOKEN_MAP.values()}
EXTREME_LABELS = {"Dotted Rhythm", "Syncopation", "Subdivision", "Tuplets"}

def is_extreme_hit(note, rule_results, target_grade: float) -> bool:
    g = float(target_grade)
    if g >= 5.0:
        return False

    # 1) If anything already got hard-zeroed, treat as extreme.
    if any((label in EXTREME_LABELS and conf == 0.0) for conf, _, label in rule_results):
        return True

    # 2) Subdivision: anything smaller than 32nd is extreme (<0.125 quarterLength)
    dur = note.duration
    if dur is not None and dur < 0.125:
        return True

    # 3) Dots > 2 in your token scheme (only if you encode dots as 'd')
    if note.rhythm_token and note.rhythm_token.count("d") > 2:
        return True

    # 4) Tuplets: treat high-order tuplets as extreme below grade 5
    if note.tuplet_id is not None:
        tuplet_class = normalize_tuplet_class(note.tuplet_class)
        order = TUPLET_CLASS_ORDER.get(tuplet_class, 1)
        if order >= 3:  # tune threshold
            return True

    # 5) Syncopation: if rule says it's "bad" AND it's rhythmically dense

    sync_rule = next(((c, m) for (c, m, lbl) in rule_results if lbl == "Syncopation"), None)
    if sync_rule is not None:
        conf, _msg = sync_rule
        if conf < 1.0 and note.beat_unit is not None and dur is not None:
            if dur <= (note.beat_unit / 4.0):
                return True

    return False

def get_rhythm_token(n):
    base = RHYTHM_TOKEN_MAP[n.duration.type]["token"]
    return base + ("d" * n.duration.dots)

def get_token_duration(token):
    if token in RHYTHM_TOKEN_MAP:
        return RHYTHM_TOKEN_MAP[token]["duration"]
    return TOKEN_DURATION_MAP.get(token)

def get_quarter_length(token):
    if not token or 'r' in token:
        return None
    base_token = token.rstrip('d')
    dots = token.count('d')
    base_duration = get_token_duration(base_token)
    if base_duration is None:
        return None
    total = base_duration
    add = base_duration / 2
    for _ in range(dots):
        total += add
        add /= 2
    return total


def _is_plain_eighth(note: PartialNoteData) -> bool:
    token = str(note.rhythm_token or "").lower()
    if not token or "r" in token:
        return False
    if "d" in token:
        return False
    base = token.rstrip("d")
    if base != "e":
        return False
    dur = note.duration
    if dur is None:
        return False
    return math.isclose(dur, 0.5, abs_tol=1e-3)


def mark_eighth_pairs(notes: list[PartialNoteData], *, grade: float) -> None:
    if float(grade) != 0.5:
        return

    for note in notes:
        note.eighth_pair_ok = False
        note.eighth_pair_overflow = False

    groups: dict[tuple[int | None, int | None], list[PartialNoteData]] = {}
    for note in notes:
        if not _is_plain_eighth(note):
            continue
        key = (note.measure, note.voice_index)
        groups.setdefault(key, []).append(note)

    for group in groups.values():
        group.sort(key=lambda n: n.offset or 0.0)
        run: list[PartialNoteData] = []
        for note in group:
            if not run:
                run.append(note)
                continue
            prev = run[-1]
            if prev.duration is None or note.duration is None:
                run = [note]
                continue
            if prev.offset is None or note.offset is None:
                run = [note]
                continue
            if math.isclose(prev.offset + prev.duration, note.offset, abs_tol=1e-3):
                run.append(note)
            else:
                if len(run) == 2:
                    for n in run:
                        n.eighth_pair_ok = True
                elif len(run) > 2:
                    for n in run:
                        n.eighth_pair_overflow = True
                run = [note]
        if run:
            if len(run) == 2:
                for n in run:
                    n.eighth_pair_ok = True
            elif len(run) > 2:
                for n in run:
                    n.eighth_pair_overflow = True


def is_implicit_empty_measure(measure, ts):
    events = list(measure.notesAndRests)
    if len(events) != 1:
        return False

    n = events[0]
    return (
        n.isRest
        and n.offset == 0
        and math.isclose(n.duration.quarterLength, ts.barDuration.quarterLength)
    )

def annotate_tuplets(notes: list[PartialNoteData], music21_notes):
    current_tuplet_id = 0
    active_signature = None
    tuplet_index = 0

    for pd, n in zip(notes, music21_notes):

        if not n.duration.tuplets:
            continue

        t = n.duration.tuplets[0]

        signature = (
            pd.measure,
            pd.beat_index,
            pd.voice_index,
            t.numberNotesActual,
            t.numberNotesNormal
        )

        if signature != active_signature:
            current_tuplet_id += 1
            active_signature = signature
            tuplet_index = 0

        pd.tuplet_id = current_tuplet_id
        pd.tuplet_index = tuplet_index
        pd.tuplet_actual = t.numberNotesActual
        pd.tuplet_normal = t.numberNotesNormal
        pd.tuplet_class = get_tuplet_class(t.numberNotesActual, t.numberNotesNormal)

        tuplet_index += 1

def check_syncopation(dur, offset):
    # return remainder, if any, and if syncopation exists for given note length and offset
    if dur in (None, 0) or offset is None:
        return (0, False)
    return (offset % dur, offset % dur != 0)


def get_tuplet_class(actual, normal) -> str:
    if actual == 3 and normal == 2:
        return "simple"
    elif actual % 2 == 0:
        return "even"
    else:
        return "complex"
