from data_processing import build_instrument_data, derive_observed_grades
from models import BaseAnalyzer
from utilities import validate_part_for_analysis
from music21 import converter
from statistics import mean

class AvailabilityAnalyzer(BaseAnalyzer):
    def analyze_confidence(self, score, grade):
        return analyze_availability_confidence(score, self.rules, grade)
    def analyze_target(self, score, target_grade):
        return analyze_availablity_target(score, self.rules, target_grade)
    
def run_availability(score_path: str, target_grade : float):
    data = build_instrument_data()
    rules = {i: data[i].availability for i in data}
    analyzer = AvailabilityAnalyzer(rules)

    observed, confidences = derive_observed_grades(
        score_factory=lambda: converter.parse(score_path),
        analyze_confidence=analyzer.analyze_confidence,
    )

    score = converter.parse(score_path)
    overall_conf, analysis_notes = analyze_availablity_target(score, rules, target_grade)
    
    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }


def analyze_availability_confidence(score, rules: dict, grade):
    conf_data = []
    for part in score.parts:
        vaildated_part = validate_part_for_analysis(part.partName)
        if vaildated_part not in rules:
            continue
        else:
            conf = 1 if rules[vaildated_part] <= grade else 0
            conf_data.append(conf)
    return mean(conf_data) if len(conf_data) > 0 else None
            

def analyze_availablity_target(score, rules: dict, target_grade):
    analysis_notes = {}
    for part in score.parts:
        original_part_name, vaildated_part = part.partName, validate_part_for_analysis(part.partName)
        analysis_notes[original_part_name] = {}
        if vaildated_part not in rules:
            analysis_notes[original_part_name] = {"no_instrument_found": f"Unable to find {original_part_name} in availability database"}
        else:
            if rules[vaildated_part] <= target_grade:
                analysis_notes[original_part_name]["availability_confidence"] = 1
            else:
                analysis_notes[original_part_name]["availability_confidence"] = 0
                analysis_notes[original_part_name] = {"availability": f"{original_part_name} typically not found in grade {target_grade}"}

    overall_conf = mean([i['availability_confidence'] for i in analysis_notes.values()])
    return overall_conf, analysis_notes
