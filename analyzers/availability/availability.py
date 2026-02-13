from copy import deepcopy

from data_processing import build_instrument_data, derive_observed_grades
from models import BaseAnalyzer
from utilities import format_grade, validate_part_for_availability
from music21 import converter
from statistics import mean


def _apply_unavailable_penalty(base_conf: float | None, penalty_total: float) -> float | None:
    if base_conf is None:
        return None
    adjusted = base_conf - penalty_total
    return max(0.0, min(1.0, adjusted))


def _stepwise_penalty(delta: float) -> float:
    # delta = availability_grade - target_grade
    if delta <= 0.5:
        return 0.05
    if delta <= 1.0:
        return 0.10
    if delta <= 2.0:
        return 0.15
    return 0.20

class AvailabilityAnalyzer(BaseAnalyzer):
    def analyze(self, score, grade, *, run_target=False):
        return analyze_availability(score, self.rules, grade, run_target=run_target)
    
def run_availability(
    score_path: str,
    target_grade: float,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    analysis_options=None,
):
    data = build_instrument_data()
    rules = {i: data[i].availability for i in data}
    analyzer = AvailabilityAnalyzer(rules)

    if score_factory is None:
        if score is not None:
            score_factory = lambda: deepcopy(score)
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        grades = analysis_options.observed_grades

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda s, g: analyzer.analyze(s, g, run_target=False),
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed, confidences = derive_observed_grades(**kwargs)
    else:
        observed, confidences = None, {}

    if score is None:
        score = score_factory()
    overall_conf, analysis_notes = analyzer.analyze(score, target_grade, run_target=True)
    
    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }


def analyze_availability(score, rules: dict, grade, *, run_target: bool = False):
    conf_data = []
    penalty_total = 0.0
    analysis_notes = {} if run_target else None

    for part in score.parts:
        original_part_name = part.partName
        validated_part = validate_part_for_availability(part.partName)
        if run_target:
            analysis_notes[original_part_name] = {}

        if original_part_name and "percussion" in original_part_name.lower():
            if run_target:
                analysis_notes[original_part_name]["availability_confidence"] = 1
                analysis_notes[original_part_name]["availability"] = "Percussion part given a free pass"
            conf_data.append(1)
            continue

        if validated_part not in rules:
            if run_target:
                analysis_notes[original_part_name] = {
                    "no_instrument_found": f"Unable to find {original_part_name} in availability database",
                    "availability_confidence": None,
                }
            continue

        availability_grade = rules[validated_part]
        conf = 1 if availability_grade <= grade else 0
        conf_data.append(conf)
        if conf == 0:
            penalty_total += _stepwise_penalty(availability_grade - grade)
            if run_target:
                analysis_notes[original_part_name]["availability_confidence"] = 0
                analysis_notes[original_part_name]["availability"] = (
                    f"{original_part_name} typically not found in grade {format_grade(grade)}"
                )
        elif run_target:
            analysis_notes[original_part_name]["availability_confidence"] = 1

    base_conf = mean(conf_data) if conf_data else None
    overall_conf = _apply_unavailable_penalty(base_conf, penalty_total)
    if run_target:
        return overall_conf, analysis_notes
    return overall_conf
