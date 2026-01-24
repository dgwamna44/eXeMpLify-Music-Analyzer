from dataclasses import dataclass
from music21 import converter, tempo, stream, meter
import math
import pandas as pd
import numpy as np
from typing import List
from models import TempoData, DurationData, DurationGradeBucket
from utilities import confidence_curve, get_rounded_grade
from app_data import GRADES

ANALYSIS_RESULTS = {}
MASTER_TEMPO_DF = pd.read_csv(r"data\tempo_guidelines.csv")
MASTER_DURATION_DF = pd.read_csv(r"data\duration_guidelines.csv")

# ----------------------------
# helpers
# ----------------------------

@dataclass
class TempoSegment:
    bpm: int
    start_measure: int
    length_measures: int
    exposure: float

def get_tempo_score(tempo, low, high):
    if  tempo > high:
        return "high"
    elif tempo < low:
        return "low"
    return "in range"

def build_tempo_segments(score, tempo_marks):
    measures = score.parts[0].getElementsByClass(stream.Measure)
    total_measures = measures[-1].number + 1

    markers = [t.measureNumber for t in tempo_marks]
    markers.append(total_measures)

    segments = []

    for i in range(len(tempo_marks)):
        start = markers[i]
        end = markers[i + 1]
        length = end - start
        exposure = length / total_measures

        segments.append(
            TempoSegment(
                bpm=tempo_marks[i].number,
                start_measure=start,
                length_measures=length,
                exposure=exposure
            )
        )

    return segments


# ----------------------------
# main analyzer
# ----------------------------

def run(
    score_path: str,
    target_grade: float 
):


    score = converter.parse(score_path)

    duration_grade_buckets = {g:[] for g in GRADES}
    for core,ext,grade in zip(MASTER_DURATION_DF["Core"], MASTER_DURATION_DF["Extended"], GRADES):
        if str(core).isdigit():
            core_max = float(core)
        else:
            core_max = core
        if str(ext).isdigit():
            ext_max = float(ext)
        else:
            ext_max = None
        duration_grade_buckets[grade].append(DurationGradeBucket(
                grade=grade,
                core_max=core_max,
                extended_max = ext_max
            )
        )

    tempo_grade_buckets = {grade: x.split("-") for x in MASTER_TEMPO_DF["combined"] 
                           for grade in GRADES if grade.is_integer()}

    tempo_marks = list(score.flat.getElementsByClass(tempo.MetronomeMark))
    total_measures = score.parts[0].getElementsByClass(stream.Measure)[-1].number

    if not tempo_marks:
        tempo_marks = [tempo.MetronomeMark(number=120, measureNumber=1)]

    segments = build_tempo_segments(score, tempo_marks)

    tempo_data: List[TempoData] = []

    rounded_tempo_grade = int(get_rounded_grade(target_grade))
    tempo_min, tempo_max = map(int, tempo_grade_buckets[rounded_tempo_grade])

    # --------------------------------
    # build TempoData
    # --------------------------------

    for seg in segments:
        result = get_tempo_score(seg.bpm, tempo_min, tempo_max)
        data = TempoData(
                bpm=seg.bpm,
                duration=seg.length_measures * 4,
                grade=target_grade,
                exposure=seg.length_measures / total_measures,
                confidence=0.0 if result in ["high", "low"] else 1.0
            )
        data.comments = f"Tempo is {result} for grade {target_grade}" if result in ["high", "low"] else None
        tempo_data.append(data)

    # --------------------------------
    # build DurationData
    # --------------------------------

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
    
    core_max, ext_max = duration_grade_buckets[target_grade]
    if duration_data.duration <= core_max or core_max == "Any":
        duration_data.confidence = 1.0
    elif ext_max is not None:
        if duration_data.duration <= ext_max:
            duration_data.confidence = math.exp(-.9 * (duration_data - core_max))
            duration_data.comments = f"Approx. time of {duration_data.length_string} on the longer side for grade {target_grade}"
        else:
            duration_data.confidence = 0.0
            duration_data.comments = f"{duration_data.length_string} is too long for grade {target_grade}"

    ANALYSIS_RESULTS["Tempo Data"] = tempo_data
    # sum each tempo block's confidence and exposure to get composite 
    ANALYSIS_RESULTS["Composite Tempo Confidence"] = sum([t.confidence*t.exposure for t in tempo_data])
    ANALYSIS_RESULTS["Duration Data"] = duration_data
