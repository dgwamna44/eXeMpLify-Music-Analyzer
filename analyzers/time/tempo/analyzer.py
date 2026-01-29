from models import BaseAnalyzer
from .helpers import build_tempo_marks, build_tempo_segments, get_tempo_score
from utilities import get_rounded_grade


def analyze_tempo_target(score, rules, target_grade):
    """
    rules[target_grade] should provide a tempo range, or you can pass in your tempo_grade_buckets mapping.
    Returns (tempo_data, composite_confidence)
    """
    tempo_marks = build_tempo_marks(score)
    segments = build_tempo_segments(score, tempo_marks)
    rounded_grade = get_rounded_grade(target_grade)

    # This assumes rules is a mapping grade -> "min-max" string or (min,max)
    tempo_min, tempo_max = rules[rounded_grade]  # e.g. (72, 120)

    for seg in segments:
        seg.grade = target_grade
        seg.confidence = get_tempo_score(seg.bpm, tempo_min, tempo_max)
        if seg.confidence == 0:
            seg.comments = f"Tempo {seg.bpm} BPM outside grade {target_grade} range ({tempo_min}-{tempo_max})"

    composite = sum(s.confidence * s.exposure for s in segments)
    return segments, composite


def analyze_tempo_confidence(score, rules, grade):
    _, composite = analyze_tempo_target(score, rules, grade)
    return composite


class TempoAnalyzer(BaseAnalyzer):
    def analyze_confidence(self, score, grade):
        return analyze_tempo_confidence(score, self.rules, grade)

    def analyze_target(self, score, target_grade):
        return analyze_tempo_target(score, self.rules, target_grade)
