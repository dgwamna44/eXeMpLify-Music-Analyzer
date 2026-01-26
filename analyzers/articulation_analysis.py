import pandas as pd
from data_processing import derive_observed_grades
from analyzers import get_articulation_confidence

from models import BaseAnalyzer, PartialNoteData, ArticulationGradeRules
from music21 import converter, stream

class ArticulationAnalyzer(BaseAnalyzer):

    def analyze_confidence(self, score, grade):
        return analyze_articulation_confidence(score, self.rules, grade)

    def analyze_target(self, score, target_grade):
        return analyze_articulation_target(score, self.rules, target_grade)

def load_articulation_rules():
    df = pd.read_csv(r"data/articulation_guidelines.csv")
    rules = {}

    for _, row in df.iterrows():
        grade = float(row["grade"])
        rules[grade] = ArticulationGradeRules(
            grade=grade,
            staccato=bool(row["staccato"]),
            tenuto=bool(row["tenuto"]),
            accent=bool(row["accent"]),
            marcato=bool(row["marcato"]),
            multiple_articulations=bool(row["mult_articulation"]),
            slur=bool(row["slur"]),
        )

    return rules

def run_articulation(score_path, target_grade):
    score = converter.parse(score_path)
    rules = load_articulation_rules()
    analyzer = ArticulationAnalyzer(rules)

    # confidence curve
    observed, confidences = derive_observed_grades(
        score,
        analyzer.analyze_confidence
    )

    # target-grade UI data
    analysis_notes, overall_conf = analyzer.analyze_target(score, target_grade)

    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf
    }


def analyze_articulation_confidence(score, rules, grade):
    total = 0
    dur = 0

    for part in score.parts:
        for m in part.getElementsByClass(stream.Measure):
            for n in m.notesAndRests:
                if n.isRest or not n.articulations:
                    continue

                conf, _, _ = get_articulation_confidence(n, rules, grade)
                d = n.duration.quarterLength
                total += conf * d
                dur += d

    return total / dur if dur > 0 else None

def analyze_articulation_target(score, rules, target_grade):
    analysis_notes = {}
    overall_total = 0
    overall_weighted = 0

    for part in score.parts:
        part_name = part.partName
        analysis_notes[part_name] = {"articulation_data": []}

        for m in part.getElementsByClass(stream.Measure):
            for n in m.notesAndRests:
                if n.isRest or not n.articulations:
                    continue

                data = PartialNoteData(
                    measure=m.number,
                    offset=n.offset,
                    grade=target_grade,
                    instrument=part_name,
                    duration=n.duration.quarterLength
                )

                conf, comment, ctype = get_articulation_confidence(n, rules, target_grade)
                data.articulation_confidence = conf

                if conf == 0:
                    data.comments[ctype] = comment

                analysis_notes[part_name]["articulation_data"].append(data)
                overall_total += n.duration.quarterLength
                overall_weighted += conf * n.duration.quarterLength

    overall_conf = overall_weighted / overall_total if overall_total else None
    return analysis_notes, overall_conf