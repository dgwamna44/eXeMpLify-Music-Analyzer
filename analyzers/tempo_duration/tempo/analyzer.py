from models import BaseAnalyzer
from .helpers import build_tempo_marks, build_tempo_segments, get_tempo_confidence, VALID_TEMPOS
from utilities import format_grade, get_rounded_grade


def analyze_tempo(score, rules, grade, *, run_target: bool = False):
    """
    rules[target_grade] should provide a tempo range, or you can pass in your tempo_grade_buckets mapping.
    Returns (tempo_data, composite_confidence)
    """
    tempo_marks = build_tempo_marks(score)
    segments = build_tempo_segments(score, tempo_marks)
    rounded_grade = get_rounded_grade(grade)

    # This assumes rules is a mapping grade -> "min-max" string or (min,max)
    tempo_rule = rules[rounded_grade]
    if isinstance(tempo_rule, str) and "-" in tempo_rule:
        tempo_min, tempo_max = map(int, tempo_rule.split("-"))
    else:
        tempo_min, tempo_max = tempo_rule  # e.g. (72, 120)

    for seg in segments:
        seg.grade = grade
        seg.confidence = get_tempo_confidence(seg.bpm, tempo_min, tempo_max, grade)
        if run_target and seg.confidence < 1:
            if seg.bpm < tempo_min or seg.bpm > tempo_max:
                seg.comments = (
                    f"Tempo {seg.bpm} ({seg.beat_unit}) "
                    f"outside grade {format_grade(grade)} range ({tempo_min}-{tempo_max})"
                )
            elif seg.bpm not in VALID_TEMPOS:
                seg.comments = f"Tempo {seg.bpm} BPM is not a standard metronome marking"

    composite = sum((s.confidence or 0.0) * (s.exposure or 0.0) for s in segments)
    composite = min(1.0, max(0.0, composite))
    if run_target:
        return segments, composite
    return composite




class TempoAnalyzer(BaseAnalyzer):
    def analyze(self, score, grade, *, run_target: bool = False):
        return analyze_tempo(score, self.rules, grade, run_target=run_target)
