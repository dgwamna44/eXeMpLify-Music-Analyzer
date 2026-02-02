# analyzers/meter/analyzer.py
from __future__ import annotations

from copy import deepcopy

from music21 import converter

from analyzers.base import BaseAnalyzer
from analyzers.shared.score_extract import extract_meter_segments
from analyzers.rhythm.rules import load_rhythm_rules
from data_processing import derive_observed_grades


def apply_meter_change_penalty(base_total: float, meter_data, grade: float) -> float:
    """
    Returns penalized confidence for meter changes, and annotates comments when penalized.
    """
    if grade < 2 and len(meter_data) > 1:
        for m in meter_data:
            m.comments["meter_changes"] = "Meter changes not common for lower grades"
        return 0.6 * base_total

    if grade < 3 and len(meter_data) > 3:
        for m in meter_data:
            m.comments["meter_changes"] = "Frequent meter changes not common for mid grades"
        return 0.6 * base_total

    return base_total


def apply_meter_change_penalty(base_total: float, meter_data, grade: float) -> float:
    """
    Returns penalized confidence for meter changes, and annotates comments when penalized.
    """
    if grade < 2 and len(meter_data) > 1:
        for m in meter_data:
            m.comments["meter_changes"] = "Meter changes not common for lower grades"
        return 0.6 * base_total

    if grade < 3 and len(meter_data) > 3:
        for m in meter_data:
            m.comments["meter_changes"] = "Frequent meter changes not common for mid grades"
        return 0.6 * base_total

    return base_total


class MeterAnalyzer(BaseAnalyzer):
    def analyze_confidence(self, score, grade: float):
        rules_for_grade = self.rules[grade]
        meter_data = extract_meter_segments(score, grade=grade, rules_for_grade=rules_for_grade)

        base_total = sum((m.confidence or 0.0) * (m.exposure or 0.0) for m in meter_data)

        # IMPORTANT: apply SAME penalty logic here
        total_conf = apply_meter_change_penalty(base_total, meter_data, grade)
        return total_conf

    def analyze_target(self, score, target_grade: float):
        rules_for_grade = self.rules[target_grade]
        meter_data = extract_meter_segments(score, grade=target_grade, rules_for_grade=rules_for_grade)

        base_total = sum((m.confidence or 0.0) * (m.exposure or 0.0) for m in meter_data)
        total_conf = apply_meter_change_penalty(base_total, meter_data, target_grade)

        return meter_data, total_conf

def run_meter(
    score_path: str,
    target_grade: float,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    analysis_options=None,
):
    if score_factory is None:
        if score is not None:
            score_factory = lambda: deepcopy(score)
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    # shared rhythm rules drive both rhythm + meter
    rules = load_rhythm_rules()
    analyzer = MeterAnalyzer(rules)

    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        grades = analysis_options.observed_grades

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda score, g: analyzer.analyze_confidence(score, g),
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade, confidences = derive_observed_grades(**kwargs)
    else:
        observed_grade, confidences = None, {}

    if score is None:
        score = score_factory()
    meter_segments, overall_conf = analyzer.analyze_target(score, target_grade)

    return {
        "observed_grade": observed_grade,
        "confidences": confidences,
        "meter_segments": meter_segments,
        "overall_confidence": overall_conf,
    }
