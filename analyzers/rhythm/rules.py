from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import pandas as pd

from app_data import GRADES
from models import RhythmGradeRules

TUPLET_CLASS_ORDER = {
    "none": 0,
    "simple": 1,
    "even": 2,
    "complex": 3,
}

# module cache (so we only read CSVs once per process)
_CACHED_RULES: dict[float, RhythmGradeRules] | None = None


def normalize_tuplet_class(value: str) -> str:
    if pd.isna(value):
        return "none"
    v = str(value).strip().lower()
    return v if v in TUPLET_CLASS_ORDER else "none"


def unpack_rhythm_data(filename: Path) -> dict[float, RhythmGradeRules]:
    df = pd.read_csv(filename)
    ruleset: dict[float, RhythmGradeRules] = {}

    for _, row in df.iterrows():
        grade = float(row["grade"])

        classes = [
            normalize_tuplet_class(v)
            for v in str(row["allowed_tuplet_classes"]).split(",")
            if str(v).strip() != ""
        ]

        ruleset[grade] = RhythmGradeRules(
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

    return ruleset


def reconcile_rhythm_rules(*rulesets: dict[float, RhythmGradeRules]) -> dict[float, RhythmGradeRules]:
    reconciled: dict[float, RhythmGradeRules] = {}

    for grade in GRADES:
        rows = [rs[grade] for rs in rulesets if grade in rs]
        if not rows:
            continue

        allowed_tuplet_classes = set().union(*(r.allowed_tuplet_classes for r in rows))

        # enforce "none only" for grade 0.5; otherwise remove "none"
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


@lru_cache(maxsize=2)
def load_rhythm_rules(data_dir: str = "data/rhythm") -> dict[float, RhythmGradeRules]:
    """
    Loads all rhythm CSVs and returns the reconciled grade->rules dict.
    Cached so repeated calls are cheap.
    """
    global _CACHED_RULES
    if _CACHED_RULES is not None:
        return _CACHED_RULES

    rulesets: list[dict[float, RhythmGradeRules]] = []
    for filename in Path(data_dir).iterdir():
        if filename.suffix.lower() != ".csv":
            continue
        rulesets.append(unpack_rhythm_data(filename))

    _CACHED_RULES = reconcile_rhythm_rules(*rulesets)
    return _CACHED_RULES
