from collections import defaultdict
import math
from pathlib import Path
import pandas as pd

from app_data import RHYTHM_TOKEN_MAP, GRADES
from models import PartialNoteData, MeterData, RhythmGradeRules

# =========================
# Globals
# =========================

ANALYSIS_NOTES = {}
MASTER_RHYTHM_DF = {}
ABS_TOLERANCE = 1e-06 # set tolerance to compare flating point number accuracy using math.isclose()

TUPLET_CLASS_ORDER = {
    "none": 0,
    "simple": 1,
    "even": 2,
    "complex": 3
}

# =========================
# Normalization helpers
# =========================

def normalize_tuplet_class(value: str) -> str:
    if pd.isna(value):
        return "none"
    v = str(value).strip().lower()
    return v if v in TUPLET_CLASS_ORDER else "none"

def get_tuplet_class(actual, normal) -> str:
    if actual == 3 and normal == 2:
        return "simple"
    elif actual % 2 == 0:
        return "even"
    else:
        return "complex"
    

# =========================
# Rhythm CSV ingest
# =========================

def unpack_rhythm_data(filename: Path, index: int):
    df = pd.read_csv(filename)
    MASTER_RHYTHM_DF[index] = {}

    for _, row in df.iterrows():
        grade = float(row["grade"])

        classes = [
            normalize_tuplet_class(v)
            for v in str(row["allowed_tuplet_classes"]).split(",")
        ]

        MASTER_RHYTHM_DF[index][grade] = RhythmGradeRules(
            grade=grade,
            max_subdivision=row["max_subdivision"],
            allow_dotted=bool(row["allow_dotted"]),
            allow_tuplet=bool(row["allow_tuplet"]),
            allowed_tuplet_classes=set(classes),
            allow_mixed_tuplet=bool(row["allow_mixed_tuplet"]),
            allow_syncopation=bool(row["allow_syncopation"]),
            allow_easy_compound=bool(row["allow_easy_compound"]),
            allow_mixed_compound=bool(row["allow_mixed_compound"]),
            allow_compound=bool(row["allow_compound"]),
        )


# =========================
# Load all rhythm datasets
# =========================

for index, filename in enumerate(Path(r"data\rhythm").iterdir(), start=1):
    unpack_rhythm_data(filename, index)

# =========================
# Ruleset reconciliation
# =========================

def reconcile_rhythm_rules(*rulesets):
    reconciled = {}

    for grade in GRADES:
        rows = [r[grade] for r in rulesets if grade in r]
        if not rows:
            continue

        allowed_tuplet_classes = set().union(*[r.allowed_tuplet_classes for r in rows])

        if grade == 0.5:
            allowed_tuplet_classes = {"none"}
        else:
            allowed_tuplet_classes.discard("none")

        reconciled[grade] = RhythmGradeRules(
            grade=grade,
            max_subdivision=max(r.max_subdivision for r in rows),
            allow_dotted=any(r.allow_dotted for r in rows),
            allow_tuplet=any(r.allow_tuplet for r in rows),
            allowed_tuplet_classes=allowed_tuplet_classes,
            allow_mixed_tuplet=any(r.allow_mixed_tuplet for r in rows),
            allow_syncopation=any(r.allow_syncopation for r in rows),
            allow_easy_compound=any(r.allow_easy_compound for r in rows),
            allow_mixed_compound=any(r.allow_mixed_compound for r in rows),
            allow_compound=any(r.allow_compound for r in rows),
        )

    return reconciled

combined_rhythm_rules = reconcile_rhythm_rules(*MASTER_RHYTHM_DF.values())


# =========================
# Rhythm helpers
# =========================

def get_rhythm_token(n):
    base = RHYTHM_TOKEN_MAP[n.duration.type]["token"]
    return base + ("d" * n.duration.dots)


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

# =====================
# meter confidence 
# =====================

def meter_segment_confidence(segment, rules: RhythmGradeRules):
    c = segment.type
    if c == "compound":
        return 1 if rules.allow_compound else 0
    if c == "mixed":
        return 1 if rules.allow_mixed_compound else 0
    if c == "odd":
        return 1 if rules.allow_easy_compound else 0
    return 1  # simple meter always allowed

# =========================
# Rhythm confidence parsers
# =========================

def rule_dotted(note, rules):
    if "d" not in note.rhythm_token:
        return (1, None)
    if rules.allow_dotted:
        return (1, None)
    return (0, "dotted rhythms not common for given grade", "Dotted Rhythm")

def check_syncopation(dur, offset):
    # return remainder, if any, and if syncopation exists for given note length and offset
    return (offset % dur, offset % dur != 0)

def rule_syncopation(note, rules):
    _, is_sync = check_syncopation(
        note.duration,
        note.offset
    )
    if not is_sync:
        return (1, None)
    return (1, None) if rules.allow_syncopation else (0, "syncopation not common for given grade", "Syncopation")

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

def rule_subdivision(note, rules):
    note_duration = get_quarter_length(note.rhythm_token)
    if note_duration is None:
        return (1, None, None)
    max_allowed = RHYTHM_TOKEN_MAP.get(rules.max_subdivision, {}).get("duration", 0)
    if note_duration <= max_allowed:
        return (1, None, None)
    else:
        return (0, f"subdivisions smaller than {rules.max_subdivision} not common for given grade", "Subdivision")

def rule_tuplet(note, rules):
    if note.tuplet_id is None:
        return (1, None, None)
    if not rules.allow_tuplet:
        return (0, "Triplets not common for given grade", "Tuplets")
    if tuplet_class := normalize_tuplet_class(note.tuplet_class):
        if tuplet_class in rules.allowed_tuplet_classes:
            return (1, None, None)
        else:
            return (0, f"{tuplet_class} tuplets not common for given grade", "Tuplets")
    
def rhythm_note_confidence(note, rules):
    return [
        rule_dotted(note, rules),
        rule_syncopation(note, rules),
        rule_subdivision(note, rules),
        rule_tuplet(note, rules),
        ]


# =========================
# Beat grouping (VIEW layer)
# =========================

def group_notes_by_beat(notes: list[PartialNoteData]):
    groups = defaultdict(list)
    for n in notes:
        if n.rhythm_token is None:
            continue
        groups[(n.measure, n.beat_index)].append(n)
    return groups


# =========================
# Analyzer entry point
# =========================

def run(score_path: str, target_grade: float):
    from music21 import converter, stream, meter
    score = converter.parse(score_path)

    rhythm_grade_rules = combined_rhythm_rules[target_grade]

    # -------------------------
    # Meter data
    # -------------------------
    meter_data = []
    meters = score.parts[0].recurse().getElementsByClass(meter.TimeSignature)
    total_measures = score.parts[0].measure(-1).number

    if not meters:
        meters = [meter.TimeSignature("4/4")]

    for index, ts in enumerate(meters):
        data = MeterData(
                measure=ts.getContextByClass(stream.Measure).number,
                time_signature=ts.ratioString,
                grade=target_grade
            )
        if index < len(meters) - 1:
            next_measure = meters[index+1].getContextByClass(stream.Measure).number
            data.duration = next_measure - data.measure
        else:
            data.duration = total_measures - data.measure + 1
        data.exposure = data.duration / total_measures
        
        # classify meter

        num, denom = map(int,data.time_signature.split("/"))

        if num in (2, 3, 4) and denom == 4:
            data.type = "simple"
        elif num in (6, 9, 12) and denom == 8:
            data.type = "compound"
        elif denom == 8 and num % 3 != 0:
            data.type = "odd"
        else:
            data.type = "mixed"

        meter_data.append(data)

    # -------------------------
    # Note extraction
    # -------------------------
    for part in score.parts:
        part_name = part.partName
        current_ts = None

        ANALYSIS_NOTES[part_name] = {}
        ANALYSIS_NOTES[part_name]["Note Data"] = []

        partial_notes = []
        music21_notes = []

        for m in part.getElementsByClass(stream.Measure):
            ts = m.getContextByClass(meter.TimeSignature)
            if ts is not None:
                current_ts = ts
            if current_ts is None:
                continue

            beat_length = current_ts.beatDuration.quarterLength

            # IMPLICIT EMPTY MEASURE
            if is_implicit_empty_measure(m, current_ts):
                partial_notes.append(
                    PartialNoteData(
                        measure=m.number,
                        offset=0.0,
                        grade=target_grade,
                        instrument=part_name,
                        duration=current_ts.barDuration.quarterLength,
                        rhythm_token=None,
                        beat_index=None,
                        beat_offset=None,
                        beat_unit=beat_length
                    )
                )
                continue

            for n in m.notesAndRests:
                beat_index = int(n.offset // beat_length)
                beat_offset = n.offset % beat_length

                p = PartialNoteData(
                    measure=m.number,
                    offset=n.offset,
                    grade=target_grade,
                    instrument=part_name,
                    duration=n.duration.quarterLength,
                    rhythm_token=get_rhythm_token(n) + ("r" if n.isRest else ""),
                    beat_index=beat_index,
                    beat_offset=beat_offset,
                    beat_unit=beat_length
                )

                partial_notes.append(p)
                music21_notes.append(n)

        annotate_tuplets(partial_notes, music21_notes)
        ANALYSIS_NOTES[part_name]["Note Data"] = partial_notes

    #---------------------
    # Meter Analysis
    #---------------------

    for m in meter_data:
        m.confidence = meter_segment_confidence(m, rhythm_grade_rules)
        m.comments = f"{m.timeSignature} not common for grade {m.grade}" if m.confidence == 0 else None 

    #-----------------------
    # Rhythm Analysis 
    #-----------------------

    # check for the following for each note: if it's dotted, if syncopation is allowed, if subdivisions are allowed, if tuplets ar permitted, and if so, simple, even or complex

    for part in ANALYSIS_NOTES.values():
        for note in part["Note Data"]:
            if note.rhythm_token is not None:
                res = rhythm_note_confidence(note, rhythm_grade_rules)
                note.confidence = min(r[0] for r in res)    
                note.comments = [r[1] for r in res if r[1] is not None] 

    return ANALYSIS_NOTES
