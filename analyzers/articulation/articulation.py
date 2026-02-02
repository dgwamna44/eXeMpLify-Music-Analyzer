from copy import deepcopy

import pandas as pd
from functools import lru_cache
from music21 import converter, stream

from data_processing import derive_observed_grades
from analyzers.articulation.articulation_confidence import get_articulation_confidence 

from models import BaseAnalyzer, PartialNoteData, ArticulationGradeRules
from utilities import iter_measure_events


# ----------------------------
# Analyzer class
# ----------------------------

class ArticulationAnalyzer(BaseAnalyzer):
    """
    Expects BaseAnalyzer to store self.rules (dict[grade -> rules_for_grade])
    """

    def analyze_confidence(self, score, grade: float):
        return analyze_articulation_confidence(score, self.rules, grade)

    def analyze_target(self, score, target_grade: float):
        return analyze_articulation_target(score, self.rules, target_grade)


# ----------------------------
# Rules loader
# ----------------------------

@lru_cache(maxsize=1)
def load_articulation_rules(path: str = r"data/articulation_guidelines.csv") -> dict[float, ArticulationGradeRules]:
    df = pd.read_csv(path)
    rules: dict[float, ArticulationGradeRules] = {}

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


# ----------------------------
# Public entry point
# ----------------------------

def run_articulation(
    score_path: str,
    target_grade: float,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    analysis_options=None,
):
    rules = load_articulation_rules()
    analyzer = ArticulationAnalyzer(rules)

    if score_factory is None:
        if score is not None:
            score_factory = lambda: deepcopy(score)
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    # 1) Observed grade + confidence curve (fresh parse per grade)
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

    # 2) Target-grade UI data (single parse)
    if score is None:
        score = score_factory()
    analysis_notes, overall_conf = analyzer.analyze_target(score, target_grade)

    return {
        "observed_grade": observed,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }


# ----------------------------
# Confidence-only pass
# ----------------------------

def analyze_articulation_confidence(score, rules: dict[float, ArticulationGradeRules], grade: float):
    """
    Returns a single confidence scalar for this grade, or None if no articulated notes exist.
    """
    total_weighted = 0.0
    total_dur = 0.0

    for part in score.parts:
        for m in part.getElementsByClass(stream.Measure):
            for n in iter_measure_events(m):
                if n.isRest or not n.articulations:
                    continue

                conf, _, _ = get_articulation_confidence(n, rules, grade)
                d = float(n.duration.quarterLength)
                total_weighted += float(conf) * d
                total_dur += d

    return (total_weighted / total_dur) if total_dur > 0 else None


# ----------------------------
# Target-grade detailed pass
# ----------------------------

def analyze_articulation_target(score, rules: dict[float, ArticulationGradeRules], target_grade: float):
    """
    Returns:
      analysis_notes: {part_name: {"articulation_data": [PartialNoteData...], "articulation_confidence": float|None}}
      overall_conf: float|None
    """
    analysis_notes: dict = {}
    overall_weighted = 0.0
    overall_total = 0.0

    for part in score.parts:
        part_name = part.partName or "Unknown Part"
        part_notes: list[PartialNoteData] = []

        part_weighted = 0.0
        part_total = 0.0

        for m in part.getElementsByClass(stream.Measure):
            for n in iter_measure_events(m):
                if n.isRest or not n.articulations:
                    continue

                written_pitch = None
                written_midi = None
                if getattr(n, "isChord", False) is False and hasattr(n, "pitch"):
                    written_pitch = n.pitch.nameWithOctave
                    written_midi = n.pitch.midi

                data = PartialNoteData(
                    measure=m.number,
                    offset=float(n.offset),
                    grade=target_grade,
                    instrument=part_name,
                    duration=float(n.duration.quarterLength),
                    written_pitch=written_pitch,
                    written_midi_value=written_midi,
                )

                conf, comment, ctype = get_articulation_confidence(n, rules, target_grade)
                data.articulation_confidence = float(conf)

                if conf == 0 and ctype:
                    data.comments[ctype] = comment

                part_notes.append(data)

                part_weighted += float(conf) * data.duration
                part_total += data.duration

        part_conf = (part_weighted / part_total) if part_total > 0 else None

        analysis_notes[part_name] = {
            "articulation_data": part_notes,
            "articulation_confidence": part_conf,
        }

        if part_total > 0:
            overall_weighted += part_weighted
            overall_total += part_total

    overall_conf = (overall_weighted / overall_total) if overall_total > 0 else None
    return analysis_notes, overall_conf
