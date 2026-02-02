from copy import deepcopy

from models import BaseAnalyzer
from utilities import get_rounded_grade
from music21 import converter
from statistics import mean

from data_processing import derive_observed_grades
from .helpers import load_dynamics_rules, derive_dynamics_data

class DynamicsAnalyzer(BaseAnalyzer):
    
    def analyze_confidence(self, score, grade: float):
        return analyze_dynamics_confidence(score, self.rules, grade)

    def analyze_target(self, score, target_grade: float):
        return analyze_dynamics_target(score, self.rules, target_grade)
    
def run_dynamics(
    score_path,
    target_grade,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    analysis_options=None,
):
    rules_table = load_dynamics_rules()
    analyzer = DynamicsAnalyzer(rules_table)

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
    analysis_notes, overall_conf = analyzer.analyze_target(score, target_grade)

    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }

def analyze_dynamics_confidence(score, rules_table, grade):
    rounded_grade = get_rounded_grade(grade)
    rules = rules_table.get(rounded_grade, {})
    part_confidences = []
    dynamics_data = derive_dynamics_data(score)
    for part in dynamics_data:
        part_valid = 0.0
        part_total = 0.0
        for dynamic in dynamics_data[part]:
            part_total += dynamic["exposure"]
            if rules.get(dynamic["dynamic"]) is True:
                part_valid += dynamic["exposure"]
        if part_total > 0:
            part_confidences.append(part_valid / part_total)
    return mean(part_confidences) if part_confidences else None

        
def analyze_dynamics_target(score, rules_table, target_grade):
    rounded_grade = get_rounded_grade(target_grade)
    rules = rules_table.get(rounded_grade, {})
    analysis_notes = {}
    dynamics_data = derive_dynamics_data(score)
    confidences = []
    for part_name, part_dyns in dynamics_data.items():
        part_valid = 0.0
        part_total = 0.0
        analysis_notes[part_name] = {"dynamics": []}
        for dynamic in part_dyns:
            dyn_name = dynamic["dynamic"]
            allowed = rules.get(dyn_name) is True
            analysis_notes[part_name]["dynamics"].append(
                {
                    "dynamic": dyn_name,
                    "measure": dynamic.get("measure"),
                    "exposure": dynamic.get("exposure"),
                    "allowed": allowed,
                }
            )
            part_total += dynamic["exposure"]
            if allowed:
                part_valid += dynamic["exposure"]
            else:
                analysis_notes[part_name][dyn_name] = (
                    f"{dyn_name} at measure {dynamic['measure']} not common for grade {target_grade}."
                )
        if part_total > 0:
            confidences.append(part_valid / part_total)
    overall_conf = mean(confidences) if confidences else None
    return analysis_notes, overall_conf
