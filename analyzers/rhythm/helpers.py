from app_data import RHYTHM_TOKEN_MAP
import math
from models import PartialNoteData

def get_rhythm_token(n):
    base = RHYTHM_TOKEN_MAP[n.duration.type]["token"]
    return base + ("d" * n.duration.dots)

def get_quarter_length(token):
    if not token or 'r' in token:
        return None
    base_token = token.rstrip('d')
    dots = token.count('d')
    if base_token not in RHYTHM_TOKEN_MAP:
        return None
    base_duration = RHYTHM_TOKEN_MAP[base_token]["duration"]
    total = base_duration
    add = base_duration / 2
    for _ in range(dots):
        total += add
        add /= 2
    return total


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


# =========================
# Tuplet annotation
# =========================

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
    return (offset % dur, offset % dur != 0)


def get_tuplet_class(actual, normal) -> str:
    if actual == 3 and normal == 2:
        return "simple"
    elif actual % 2 == 0:
        return "even"
    else:
        return "complex"
