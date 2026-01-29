from dataclasses import dataclass, field
from music21 import converter, tempo, stream
import math
import pandas as pd
from typing import List
from models import DurationData, DurationGradeBucket
from utilities import get_rounded_grade
from app_data import GRADES, ROUNDED_GRADES
from data_processing import derive_observed_grades

# ----------------------------
# globals
# ----------------------------

ANALYSIS_RESULTS = {}

MASTER_TEMPO_DF = pd.read_csv(r"data\tempo_guidelines.csv")
MASTER_DURATION_DF = pd.read_csv(r"data\duration_guidelines.csv")

# ----------------------------
# dataclasses
# ----------------------------

@dataclass
class TempoData:
    bpm: int
    start_measure: int
    length_measures: int
    exposure: float
    grade: float
    duration: float
    confidence: float
    comments: str | None = None

# ----------------------------
# helpers
# ----------------------------

def get_tempo_score(bpm, low, high) -> int:
    """Binary bucket: 1 = acceptable, 0 = not acceptable"""
    return 1 if low <= bpm <= high else 0


def build_tempo_segments(score, tempo_marks: List[tuple]):
    """
    tempo_marks: List[(measure_number, bpm)]
    Always returns at least one TempoData segment
    """

    measures = score.parts[0].getElementsByClass(stream.Measure)
    total_measures = measures[-1].number

    # --- DEFAULT TEMPO ---
    if not tempo_marks:

        return [
            TempoData(
                bpm=100,
                start_measure=1,
                length_measures=total_measures,
                exposure=1.0,
                grade=0,
                duration=total_measures * 4,
                confidence=0
            )
        ]

    tempo_marks = sorted(tempo_marks, key=lambda x: x[0])
    segments = []

    for i, (start_measure, bpm) in enumerate(tempo_marks):
        end_measure = (
            tempo_marks[i + 1][0]
            if i + 1 < len(tempo_marks)
            else total_measures + 1
        )

        length = max(0, end_measure - start_measure)
        exposure = length / total_measures

        segments.append(
            TempoData(
                bpm=int(bpm),
                start_measure=start_measure,
                length_measures=length,
                exposure=exposure,
                grade=0,
                duration=length * 4,
                confidence=0
            )
        )

    return segments


# ----------------------------
# grade buckets
# ----------------------------

duration_grade_buckets = {}
for core, ext, grade in zip(
    MASTER_DURATION_DF["Core"],
    MASTER_DURATION_DF["Extended"],
    GRADES
):
    duration_grade_buckets[grade] = DurationGradeBucket(
        grade=grade,
        core_max=float(core)*60 if not str(core).isalpha() else core,
        extended_max=float(ext)*60 if not str(ext).isalpha() else None
    )

tempo_grade_buckets = {
    grade: MASTER_TEMPO_DF.iloc[i]["combined"]
    for i, grade in enumerate(ROUNDED_GRADES)
}

# ----------------------------
# main analyzer
# ----------------------------

def run(score_path: str, target_grade: float):

    score = converter.parse(score_path)

    # extract tempo marks explicitly
    tempo_marks = []
    for m in score.parts[0].getElementsByClass(stream.Measure):
        for t in m.getElementsByClass(tempo.MetronomeMark):
            if t.number:
                tempo_marks.append((m.number, int(t.number)))

    total_measures = score.parts[0].getElementsByClass(stream.Measure)[-1].number

    segments = build_tempo_segments(score, tempo_marks)

    rounded = get_rounded_grade(target_grade)
    tempo_min, tempo_max = map(int, tempo_grade_buckets[rounded].split("-"))

    # ----------------------------
    # build TempoData
    # ----------------------------

    tempo_data: List[TempoData] = []

    for seg in segments:
        conf = get_tempo_score(seg.bpm, tempo_min, tempo_max)

        seg.grade = target_grade
        seg.confidence = conf
        seg.comments = (
            f"Tempo {seg.bpm} BPM outside grade {target_grade} range"
            if conf == 0 else None
        )

        tempo_data.append(seg)

    ANALYSIS_RESULTS["tempo_data"] = tempo_data

    # ----------------------------
    # build DurationData
    # ----------------------------

    total_seconds = sum(
        (60 / t.bpm) * t.duration
        for t in tempo_data
    )

    minutes, seconds = divmod(total_seconds, 60)

    duration_data = DurationData(
        duration=int(total_seconds),
        length_string=f"{int(minutes)}'{int(math.ceil(seconds))}\"",
        grade=target_grade,
    )

    bucket = duration_grade_buckets[target_grade]

    if bucket.core_max == "Any" or duration_data.duration <= bucket.core_max:
        duration_data.confidence = 1.0
    elif bucket.extended_max and duration_data.duration <= bucket.extended_max:
        duration_data.confidence = 0.5
        duration_data.comments = "Duration slightly long for grade"
    else:
        duration_data.confidence = 0.0
        duration_data.comments = "Duration too long for grade"

    ANALYSIS_RESULTS["duration_data"] = duration_data

    grade_summary = {
        "target_grade": target_grade,
        "composite_tempo_confidence": sum(
            t.confidence * t.exposure for t in tempo_data
        ),
        "duration_confidence": duration_data.confidence
    }



    return ANALYSIS_RESULTS, grade_summary


    





