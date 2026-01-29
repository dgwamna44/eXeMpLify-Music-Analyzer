import math
from models import BaseAnalyzer, DurationData, DurationGradeBucket

def compute_total_seconds_from_tempo_data(tempo_data) -> float:
    return sum((60.0 / t.bpm) * t.qtr_len for t in tempo_data)


def analyze_duration_target(score, rules: dict[float, DurationGradeBucket], target_grade, tempo_data=None):
    """
    If tempo_data is provided, duration is computed using tempo segments.
    If not, we fall back to assuming 100 BPM across whole piece.
    """
    measures = score.parts[0].getElementsByClass("Measure")
    total_measures = measures[-1].number if measures else 0
    total_quarters = total_measures * 4

    if tempo_data is None:
        # fallback default
        total_seconds = (60.0 / 100.0) * total_quarters
    else:
        total_seconds = compute_total_seconds_from_tempo_data(tempo_data)

    minutes, seconds = divmod(total_seconds, 60)

    duration_data = DurationData(
        duration=int(total_seconds),
        length_string=f"{int(minutes)}'{int(math.ceil(seconds))}\"",
        grade=target_grade,
    )

    bucket = rules[target_grade]

    if bucket.core_max == "Any" or duration_data.duration <= bucket.core_max:
        duration_data.confidence = 1.0
    elif bucket.extended_max and duration_data.duration <= bucket.extended_max:
        duration_data.confidence = 0.5
        duration_data.comments = "Duration slightly long for grade"
    else:
        duration_data.confidence = 0.0
        duration_data.comments = "Duration too long for grade"

    return duration_data, duration_data.confidence


def analyze_duration_confidence(score, rules, grade, tempo_data=None):
    _, conf = analyze_duration_target(score, rules, grade, tempo_data=tempo_data)
    return conf


class DurationAnalyzer(BaseAnalyzer):
    def analyze_confidence(self, score, grade):
        # For observed-grade curves, you probably *do* want tempo_data;
        # but if you're running these independently, fallback is fine.
        return analyze_duration_confidence(score, self.rules, grade, tempo_data=None)

    def analyze_target(self, score, target_grade):
        return analyze_duration_target(score, self.rules, target_grade, tempo_data=None)
