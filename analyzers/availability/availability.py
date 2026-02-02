from copy import deepcopy

from data_processing import build_instrument_data, derive_observed_grades
from models import BaseAnalyzer
from utilities import validate_part_for_availability
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
    def analyze_confidence(self, score, grade):
        return analyze_availability_confidence(score, self.rules, grade)
    def analyze_target(self, score, target_grade):
        return analyze_availablity_target(score, self.rules, target_grade)
    
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
            "analyze_confidence": analyzer.analyze_confidence,
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed, confidences = derive_observed_grades(**kwargs)
    else:
        observed, confidences = None, {}

    if score is None:
        score = score_factory()
    overall_conf, analysis_notes = analyze_availablity_target(score, rules, target_grade)
    
    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }


def analyze_availability_confidence(score, rules: dict, grade):
    conf_data = []
    penalty_total = 0.0
    for part in score.parts:
        if part.partName and "percussion" in part.partName.lower():
            conf_data.append(1)
            continue
        vaildated_part = validate_part_for_availability(part.partName)
        if vaildated_part not in rules:
            continue
        else:
            availability_grade = rules[vaildated_part]
            conf = 1 if availability_grade <= grade else 0
            conf_data.append(conf)
            if conf == 0:
                penalty_total += _stepwise_penalty(availability_grade - grade)
    base_conf = mean(conf_data) if len(conf_data) > 0 else None
    return _apply_unavailable_penalty(base_conf, penalty_total)
            

def analyze_availablity_target(score, rules: dict, target_grade):
    analysis_notes = {}
    penalty_total = 0.0
    for part in score.parts:
        original_part_name, vaildated_part = part.partName, validate_part_for_availability(part.partName)
        analysis_notes[original_part_name] = {}
        if original_part_name and "percussion" in original_part_name.lower():
            analysis_notes[original_part_name]["availability_confidence"] = 1
            analysis_notes[original_part_name]["availability"] = "Percussion part given a free pass"
            continue
        if vaildated_part not in rules:
            analysis_notes[original_part_name] = {
                "no_instrument_found": f"Unable to find {original_part_name} in availability database",
                "availability_confidence": None,
            }
        else:
            availability_grade = rules[vaildated_part]
            if availability_grade <= target_grade:
                analysis_notes[original_part_name]["availability_confidence"] = 1
            else:
                analysis_notes[original_part_name]["availability_confidence"] = 0
                analysis_notes[original_part_name]["availability"] = (
                    f"{original_part_name} typically not found in grade {target_grade}"
                )
                penalty_total += _stepwise_penalty(availability_grade - target_grade)

    confidences = [
        i["availability_confidence"]
        for i in analysis_notes.values()
        if i.get("availability_confidence") is not None
    ]
    base_conf = mean(confidences) if confidences else None
    overall_conf = _apply_unavailable_penalty(base_conf, penalty_total)
    return overall_conf, analysis_notes
