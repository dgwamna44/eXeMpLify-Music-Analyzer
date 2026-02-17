# rules_key_range.py
from app_data import (
    GRADE_TO_KEY_TABLE,
    PUBLISHER_CATALOG_FREQUENCY,
    MAJOR_DIATONIC_MAP,
    MINOR_DIATONIC_MAP
)
from utilities import confidence_curve, format_grade, normalize_key_name
from music21 import pitch as m21pitch
import csv
from functools import lru_cache




# ------------------------------
# KEY CONFIDENCE
# ------------------------------

def publisher_key_support(key, grade):
    values = [
        v for v in GRADE_TO_KEY_TABLE.get(key, {}).values()
        if isinstance(v, (int, float))
    ]
    return sum(max_grade <= grade for max_grade in values)


def publisher_key_confidence(key, grade):
    values = [
        v for v in GRADE_TO_KEY_TABLE.get(key, {}).values()
        if isinstance(v, (int, float))
    ]
    total_sources = len(values)
    evidence = publisher_key_support(key, grade)
    if total_sources == 0:
        return 0.0
    if evidence == total_sources:
        return confidence_curve(evidence, normalize=total_sources, k=3.5, max_conf=1)
    return confidence_curve(evidence, normalize=total_sources, k=2.0, max_conf=0.80)


def catalog_key_confidence(key, grade):
    exposure = sum(
        count for g, count in PUBLISHER_CATALOG_FREQUENCY.get(key, {}).items() if g <= grade
    )
    total = sum(PUBLISHER_CATALOG_FREQUENCY.get(key, {}).values()) or 1
    return confidence_curve(exposure, normalize=total, k=1.2, max_conf=0.20)


def _relative_major_key(key: str) -> str:
    try:
        pitch = m21pitch.Pitch(normalize_key_name(key))
    except Exception:
        return key
    rel = pitch.transpose(3)
    return normalize_key_name(rel.name).capitalize()


def _key_in_tables(key: str) -> bool:
    return key in GRADE_TO_KEY_TABLE and key in PUBLISHER_CATALOG_FREQUENCY


def _min_publisher_grade(key: str) -> float | None:
    values = [
        v for v in GRADE_TO_KEY_TABLE.get(key, {}).values()
        if isinstance(v, (int, float))
    ]
    return min(values) if values else None


def total_key_confidence(key, grade, key_quality=None):
    eval_key = key
    if key_quality and str(key_quality).lower().startswith("min") and key != "None":
        eval_key = _relative_major_key(key)
    if not _key_in_tables(eval_key):
        eval_key = key
    min_grade = _min_publisher_grade(eval_key)
    if min_grade is not None and grade < min_grade:
        return 0.0
    return min(1.0, publisher_key_confidence(eval_key, grade) + catalog_key_confidence(eval_key, grade))


@lru_cache(maxsize=1)
def load_string_key_guidelines(path: str = "data/string_key_guidelines.csv") -> dict:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if row]

    if not rows:
        raise ValueError(f"{path} is empty")

    grades = [float(str(g).strip().lstrip("\ufeff")) for g in rows[0]]
    data_rows = rows[1:]
    if not data_rows:
        raise ValueError(f"{path} has no data rows")

    def parse_keys(cell: str | None):
        if cell is None:
            return None
        text = str(cell).strip()
        if not text or text.lower() == "any":
            return None
        return {normalize_key_name(k.strip()).capitalize() for k in text.split(",")}

    major_row = data_rows[0]
    minor_row = data_rows[1] if len(data_rows) > 1 else data_rows[0]

    guidelines: dict[float, dict[str, set[str] | None]] = {}
    for i, grade in enumerate(grades):
        major = parse_keys(major_row[i]) if i < len(major_row) else None
        minor = parse_keys(minor_row[i]) if i < len(minor_row) else None
        guidelines[float(grade)] = {"major": major, "minor": minor}

    return guidelines


def _select_grade(grade: float, available: list[float]) -> float:
    if grade in available:
        return grade
    lower = [g for g in available if g <= grade]
    return max(lower) if lower else min(available)


def string_key_confidence(key: str, grade: float, key_quality: str | None, guidelines: dict) -> float:
    grades = sorted(guidelines.keys())
    sel = _select_grade(float(grade), grades)
    quality = (key_quality or "major").lower()
    eval_key = key
    if quality.startswith("min"):
        eval_key = _relative_major_key(key)
        quality = "major"
    bucket = guidelines[sel].get(quality, guidelines[sel].get("major"))
    if bucket is None:
        return 1.0
    return 1.0 if eval_key in bucket else 0.0


# ------------------------------
# RANGE CONFIDENCE
# ------------------------------

def harmonic_tolerance_penalty(grade):
    if grade >= 5:
        return 0.0
    return 0.45 - ((grade - 1) * 0.1)


def compute_range_confidence(note, core, ext, total, target_grade, key_quality):
    """
    Computes per-note range confidence with harmonic penalties.
    """
    midi = note.sounding_midi_value
    rel = note.relative_key_index

    # -------------- Range position --------------
    if core and core[0] <= midi <= core[1]:
        conf = 1.0
    elif ext[0] <= midi <= ext[1]:
        conf = 0.6
        note.comments["range"] = (
            f"{note.written_pitch} in extended range for grade {format_grade(target_grade)}"
        )
    elif total[0] <= midi <= total[1]:
        conf = 0.25
        note.comments["range"] = (
            f"{note.written_pitch} out of range for grade {format_grade(target_grade)}"
        )
    else:
        conf = 0.0
        note.comments["range"] = f"{note.written_pitch} out of range altogether for {note.instrument}"

    # -------------- Harmonic Tolerance Penalty --------------
    penalty = harmonic_tolerance_penalty(target_grade)
    key_q = (key_quality or "").lower()
    if key_q not in ("", "none") and rel is not None:
        if key_q.startswith("maj"):
            if rel not in MAJOR_DIATONIC_MAP:
                conf = max(0.0, conf - penalty)
                note.comments["harmonic_tolerance"] = (
                    "Non-diatonic note "
                    f"{note.written_pitch} in major key for grade {format_grade(target_grade)}"
                )
        else:  # minor
            if (rel not in MINOR_DIATONIC_MAP) and rel != 11:
                conf = max(0.0, conf - penalty)
                note.comments["harmonic_tolerance"] = (
                    "Non-diatonic note "
                    f"{note.written_pitch} in minor key for grade {format_grade(target_grade)}"
                )

    if conf < 1.0 and not note.comments:
        note.comments["range"] = (
            f"{note.written_pitch} penalized for grade {format_grade(target_grade)}"
        )

    return max(0.0, conf)
