from music21 import converter
import pandas as pd

from data_processing import derive_observed_grades
from models import DurationGradeBucket
from .tempo.analyzer import TempoAnalyzer
from .duration.analyzer import DurationAnalyzer, analyze_duration_target


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


def run_tempo_duration(score_path: str, target_grade: float):
    tempo_rules = load_tempo_rules()
    duration_rules = load_duration_rules()

    score = converter.parse(score_path)

    analyzer = TempoAnalyzer(tempo_rules)

    # observed grade based on tempo only (or you can build a combined curve)
    observed, confidences = derive_observed_grades(score_factory=lambda: converter.parse(score_path), 
                                                   analyze_confidence=analyzer.analyze_confidence)

    # target-grade UI data
    tempo_data, tempo_conf = analyzer.analyze_target(score, target_grade)
    duration_data, duration_conf = analyze_duration_target(score, duration_rules, target_grade, tempo_data=tempo_data)

    analysis_notes = {
        "tempo_data": tempo_data,
        "duration_data": duration_data
    }

    grade_summary = {
        "target_grade": target_grade,
        "composite_tempo_confidence": tempo_conf,
        "duration_confidence": duration_conf
    }

    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": None,  # optional composite if you want
        "grade_summary": grade_summary
    }
