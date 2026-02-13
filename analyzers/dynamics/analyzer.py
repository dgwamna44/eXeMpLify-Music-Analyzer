from copy import deepcopy

from models import BaseAnalyzer
from utilities import format_grade, get_rounded_grade
from music21 import converter
from statistics import mean

from data_processing import derive_observed_grades
from .helpers import load_dynamics_rules, derive_dynamics_data

class DynamicsAnalyzer(BaseAnalyzer):
    
    def analyze(self, score, grade: float, *, run_target=False):
        return analyze_dynamics(score, self.rules, grade, run_target=run_target)
    
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
    analysis_notes, overall_conf = analyzer.analyze(score, target_grade, run_target=True)

    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }

def analyze_dynamics(score, rules_table, grade, *, run_target: bool = False):
    rounded_grade = get_rounded_grade(grade)
    rules = rules_table.get(rounded_grade, {})
    dynamics_data = derive_dynamics_data(score)
    part_confidences = []
    analysis_notes = {} if run_target else None

    for part_name, part_dyns in dynamics_data.items():
        part_valid = 0.0
        part_total = 0.0
        if run_target:
            analysis_notes[part_name] = {"dynamics": []}
        for dynamic in part_dyns:
            dyn_name = dynamic["dynamic"]
            exposure = dynamic["exposure"]
            allowed = rules.get(dyn_name) is True
            part_total += exposure
            if allowed:
                part_valid += exposure
            if run_target:
                analysis_notes[part_name]["dynamics"].append(
                    {
                        "dynamic": dyn_name,
                        "measure": dynamic.get("measure"),
                        "exposure": exposure,
                        "allowed": allowed,
                    }
                )
                if not allowed:
                    analysis_notes[part_name][dyn_name] = (
                        f"{dyn_name} at measure {dynamic['measure']} not common for grade {format_grade(grade)}."
                    )
        if part_total > 0:
            part_confidences.append(part_valid / part_total)

    overall_conf = mean(part_confidences) if part_confidences else None
    if run_target:
        return analysis_notes, overall_conf
    return overall_conf
