# shared/score_extract.py
from __future__ import annotations

from music21 import meter as m21meter, stream
from models import MeterData, RhythmGradeRules
from analyzers.meter.helpers import meter_segment_confidence
from utilities import format_grade, iter_measure_events


def extract_meter_segments(score, *, grade: float, rules_for_grade: RhythmGradeRules) -> list[MeterData]:
    part0 = score.parts[0]
    measures = list(part0.getElementsByClass(stream.Measure))

    if not measures:
        return []

    total_measures = len(measures)  # IMPORTANT: use count of measures in score order

    # Build list of (measure_index, measure_number, ts_ratio) ONLY when TS changes
    change_points: list[tuple[int, int, str]] = []

    prev_ratio = None
    for idx, meas in enumerate(measures):
        ts = meas.getContextByClass(m21meter.TimeSignature)
        ratio = ts.ratioString if ts else "4/4"

        if ratio != prev_ratio:
            change_points.append((idx, meas.number, ratio))
            prev_ratio = ratio

    segments: list[MeterData] = []

    for i, (start_idx, start_num, ratio) in enumerate(change_points):
        end_idx = change_points[i + 1][0] if i + 1 < len(change_points) else total_measures
        duration_measures = end_idx - start_idx
        exposure = duration_measures / total_measures if total_measures else 0.0

        seg = MeterData(
            measure=start_num,
            time_signature=ratio,
            grade=grade,
        )
        seg.duration = duration_measures
        seg.exposure = exposure
        seg.type = classify_meter(ratio)          # helper below (avoids needing ts object)
        seg.confidence = meter_segment_confidence(seg, rules_for_grade)

        if seg.confidence == 0:
            seg.comments["Time Signature"] = (
                f"{seg.time_signature} not common for grade {format_grade(grade)}"
            )

        segments.append(seg)

    return segments


def classify_meter(ratio: str) -> str:
    num, denom = map(int, ratio.split("/"))
    if num in (2, 3, 4) and denom == 4:
        return "simple"
    if num in (6, 9, 12) and denom == 8:
        return "compound"
    if denom == 8 and num % 3 != 0:
        return "odd"
    return "mixed"


def max_chord_size_in_part(part) -> int:
    #returns max chord size in given part
    return max(
        (
            len(n.pitches)
            for m in part.getElementsByClass(stream.Measure)
            for n in iter_measure_events(m)
            if n.isChord
        ),
        default=1,
    )
