from music21 import stream, tempo
from models import TempoData
from typing import List

VALID_TEMPOS = [
    40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60,
    63, 66, 69, 72, 76, 80, 84, 88, 92, 96,
    100, 104, 108, 112, 116, 120, 126, 132, 138,
    144, 152, 160, 168, 176, 184, 200, 208,
]

def _quarter_bpm(mark: tempo.MetronomeMark) -> int | None:
    if hasattr(mark, "getQuarterBPM") and mark.getQuarterBPM() is not None:
        return int(round(mark.getQuarterBPM()))
    if mark.number and mark.referent and mark.referent.quarterLength:
        return int(round(mark.number * mark.referent.quarterLength))
    if mark.number:
        return int(round(mark.number))
    return None


def _beat_unit(mark: tempo.MetronomeMark) -> str:
    if mark.referent and getattr(mark.referent, "fullName", None):
        return str(mark.referent.fullName)
    if mark.referent and getattr(mark.referent, "name", None):
        return str(mark.referent.name)
    return "quarter"


def build_tempo_marks(score) -> List[tuple[int, int, str, int]]:
    marks = []
    for m in score.parts[0].getElementsByClass(stream.Measure):
        for t in m.getElementsByClass(tempo.MetronomeMark):
            if t.number:
                qpm = _quarter_bpm(t)
                beat_unit = _beat_unit(t)
                if qpm is not None:
                    marks.append((m.number, int(t.number), beat_unit, qpm))
    return marks


def build_tempo_segments(score, tempo_marks: List[tuple[int, int, str, int]]) -> List[TempoData]:
    measures = score.parts[0].getElementsByClass(stream.Measure)
    total_measures = measures[-1].number

    if not tempo_marks:
        # default "unknown" tempo segment; you can choose 100 or whatever default
        return [
            TempoData(
                bpm=100,
                quarter_bpm=100,
                beat_unit="quarter",
                measure=1,
                exposure=1.0,
                grade=0.0,
                qtr_len=total_measures * 4,
                confidence=0.0,
                comments="No tempo markings found; using default 100 BPM"
            )
        ]

    tempo_marks = sorted(tempo_marks, key=lambda x: x[0])
    segments: List[TempoData] = []

    for i, (start, bpm, beat_unit, quarter_bpm) in enumerate(tempo_marks):
        end_measure = tempo_marks[i + 1][0] if i + 1 < len(tempo_marks) else total_measures + 1
        length = max(0, end_measure - start)
        exposure = length / total_measures if total_measures else 0

        segments.append(
            TempoData(
                bpm=bpm,
                quarter_bpm=quarter_bpm,
                beat_unit=beat_unit,
                measure=start,
                exposure=exposure,
                grade=0.0,
                qtr_len=length * 4,
                confidence=0.0
            )
        )

    return segments


def get_tempo_score(bpm: int, low: int, high: int) -> float:
    return 1.0 if low <= bpm <= high else 0.0


def _penalty_per_step(grade: float) -> float:
    if grade >= 5:
        return 0.0
    steps = max(0, round((grade - 0.5) / 0.5))
    penalty = 0.20 - (0.03 * steps)
    return max(0.0, penalty)


def _step_distance_from_range(bpm: int, low: int, high: int) -> int:
    if low <= bpm <= high:
        return 0
    if bpm < low:
        below = [t for t in VALID_TEMPOS if t <= bpm]
        low_idx = VALID_TEMPOS.index(low) if low in VALID_TEMPOS else 0
        bpm_idx = VALID_TEMPOS.index(below[-1]) if below else 0
        return max(1, low_idx - bpm_idx)
    above = [t for t in VALID_TEMPOS if t >= bpm]
    high_idx = VALID_TEMPOS.index(high) if high in VALID_TEMPOS else len(VALID_TEMPOS) - 1
    bpm_idx = VALID_TEMPOS.index(above[0]) if above else len(VALID_TEMPOS) - 1
    return max(1, bpm_idx - high_idx)


def _step_distance_to_mark(bpm: int) -> int:
    if bpm in VALID_TEMPOS:
        return 0
    lower = [t for t in VALID_TEMPOS if t <= bpm]
    upper = [t for t in VALID_TEMPOS if t >= bpm]
    if not lower:
        return max(1, VALID_TEMPOS.index(upper[0]))
    if not upper:
        return max(1, len(VALID_TEMPOS) - 1 - VALID_TEMPOS.index(lower[-1]))
    lower_idx = VALID_TEMPOS.index(lower[-1])
    upper_idx = VALID_TEMPOS.index(upper[0])
    return max(1, min(upper_idx - lower_idx, lower_idx - upper_idx) or 1)


def get_tempo_confidence(bpm: int, low: int, high: int, grade: float) -> float:
    if grade >= 5:
        return 1.0
    penalty = _penalty_per_step(grade)
    if penalty <= 0:
        return 1.0

    if low <= bpm <= high:
        steps = _step_distance_to_mark(bpm)
    else:
        steps = _step_distance_from_range(bpm, low, high)
    if steps <= 0:
        return 1.0
    confidence = 1.0 - (penalty * steps)
    return max(0.0, min(1.0, confidence))
