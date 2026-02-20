# analyzers/meter/analyzer.py
from __future__ import annotations

from music21 import converter

from analyzers.base import BaseAnalyzer
from analyzers.shared.score_extract import extract_meter_segments
from analyzers.rhythm.rules import load_rhythm_rules
from data_processing import derive_observed_grades
from utilities import get_closest_grade


def apply_meter_change_penalty(base_total: float, meter_data, grade: float):
    """
    Returns (penalized_confidence, comment|None) for meter changes.
    """
    meter_changes = max(0, len(meter_data) - 1)
    if meter_changes == 0:
        return base_total, None

    penalty = 0.0
    comment = None

    if grade < 2:
        penalty = 0.4
        comment = "Meter changes not common for lower grades"
    elif grade < 2.5:
        penalty = min(0.03 * meter_changes, 0.3)
        comment = "Meter changes penalized at 0.03 per change (cap 0.3)"
    elif grade < 3:
        penalty = min(0.025 * meter_changes, 0.25)
        comment = "Meter changes penalized at 0.025 per change (cap 0.25)"

    if penalty <= 0:
        return base_total, None

    return max(0.0, base_total - penalty), comment


class MeterAnalyzer(BaseAnalyzer):
    def analyze(self, score, grade: float, *, run_target: bool = False):
        rule_grade = get_closest_grade(grade, self.rules.keys())
        if rule_grade is None:
            return ([], None) if run_target else None
        rules_for_grade = self.rules[rule_grade]
        meter_data = extract_meter_segments(score, grade=grade, rules_for_grade=rules_for_grade)

        base_total = sum((m.confidence or 0.0) * (m.exposure or 0.0) for m in meter_data)
        total_conf, meter_comment = apply_meter_change_penalty(base_total, meter_data, grade)

        if run_target:
            if meter_comment and meter_data:
                meter_data[0].comments["meter_changes"] = meter_comment
            return meter_data, total_conf
        return total_conf

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
            score_factory = lambda: score
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
            "analyze_confidence": lambda score, g: analyzer.analyze(score, g, run_target=False),
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade, confidences = derive_observed_grades(**kwargs)
    else:
        observed_grade, confidences = None, {}

    if score is None:
        score = score_factory()
    meter_segments, overall_conf = analyzer.analyze(score, target_grade, run_target=True)

    return {
        "observed_grade": observed_grade,
        "confidences": confidences,
        "meter_segments": meter_segments,
        "analysis_notes": {
            "meter_data": meter_segments,
        },
        "overall_confidence": overall_conf,
    }
