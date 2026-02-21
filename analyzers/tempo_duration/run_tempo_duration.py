
from music21 import converter
from functools import lru_cache
import pandas as pd

from data_processing import derive_observed_grades
from models import DurationGradeBucket
from .tempo.analyzer import TempoAnalyzer
from .duration.analyzer import analyze_duration


def _parse_tempo_range(value: str):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return int(value[0]), int(value[1])
    text = str(value).strip()
    if not text:
        return None
    parts = text.replace("–", "-").split("-")
    if len(parts) != 2:
        return None
    return int(parts[0]), int(parts[1])


@lru_cache(maxsize=4)
def load_tempo_rules(path: str = r"data/tempo_guidelines.csv", column: str = "combined"):
    df = pd.read_csv(path)
    rules = {}
    for _, row in df.iterrows():
        grade = float(row["grade"])
        tempo_range = _parse_tempo_range(row.get(column))
        if tempo_range is not None:
            rules[grade] = tempo_range
    return rules


def _parse_duration_value(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() == "any":
        return "Any"
    return float(text) * 60.0


@lru_cache(maxsize=1)
def load_duration_rules(path: str = r"data/duration_guidelines.csv"):
    df = pd.read_csv(path)
    rules = {}
    for _, row in df.iterrows():
        grade = float(row["Grade"])
        core = _parse_duration_value(row.get("Core"))
        extended = _parse_duration_value(row.get("Extended"))
        rules[grade] = DurationGradeBucket(
            grade=grade,
            core_max=core,
            extended_max=extended,
        )
    return rules


def run_tempo_duration(
    score_path: str,
    target_grade: float,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    analysis_options=None,
):
    tempo_rules = load_tempo_rules()
    duration_rules = load_duration_rules()

    analyzer = TempoAnalyzer(tempo_rules)

    if score_factory is None:
        if score is not None:
            score_factory = lambda: score
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    # observed grade based on tempo only (or you can build a combined curve)
    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        grades = analysis_options.observed_grades

    def _progress_tempo(grade, idx, total):
        if progress_cb is not None:
            progress_cb(grade, idx, total, "tempo")

    def _progress_duration(grade, idx, total):
        if progress_cb is not None:
            progress_cb(grade, idx, total, "duration")

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda s, g: analyzer.analyze(s, g, run_target=False),
            "progress_cb": _progress_tempo if progress_cb is not None else None,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed, confidences = derive_observed_grades(**kwargs)
    else:
        observed, confidences = None, {}

    # target-grade UI data
    if score is None:
        score = score_factory()
    tempo_data, tempo_conf = analyzer.analyze(score, target_grade, run_target=True)
    duration_data, duration_conf = analyze_duration(
        score,
        duration_rules,
        target_grade,
        run_target=True,
        tempo_data=tempo_data,
    )
    tempo_conf = min(1.0, max(0.0, tempo_conf))
    duration_conf = min(1.0, max(0.0, duration_conf))

    # observed grade based on duration (uses tempo-derived duration)
    if run_observed:
        def _duration_confidence(s, g):
            return analyze_duration(s, duration_rules, g, run_target=False, tempo_data=tempo_data)

        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": _duration_confidence,
            "progress_cb": _progress_duration if progress_cb is not None else None,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_duration, confidences_duration = derive_observed_grades(**kwargs)
    else:
        observed_duration, confidences_duration = None, {}

    analysis_notes = {
        "tempo_data": tempo_data,
        "duration_data": duration_data
    }

    grade_summary = {
        "target_grade": target_grade,
        "composite_tempo_confidence": tempo_conf,
        "duration_confidence": duration_conf,
        "overall_tempo_confidence": tempo_conf,
        "overall_duration_confidence": duration_conf,
    }

    return {
        "observed_grade": observed,
        "confidences": confidences,
        "observed_grade_tempo": observed,
        "confidence_tempo": confidences,
        "observed_grade_duration": observed_duration,
        "confidence_duration": confidences_duration,
        "analysis_notes": analysis_notes,
        "grade_summary": grade_summary,
        "summary": grade_summary,
    }
