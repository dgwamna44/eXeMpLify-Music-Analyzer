from music21 import stream, tempo
from models import TempoData
from typing import List

VALID_TEMPOS = [
    40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60,
    63, 66, 69, 72, 76, 80, 84, 88, 92, 96, 100,
    104, 108, 112, 116, 120, 126, 132, 138, 144,
    152, 160, 168, 176, 184, 200, 208,
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


def _nearest_valid_index(bpm: int) -> int:
    return min(range(len(VALID_TEMPOS)), key=lambda i: abs(VALID_TEMPOS[i] - bpm))


def _bound_index(low: int, high: int, *, upper: bool) -> int:
    if upper:
        candidates = [i for i, v in enumerate(VALID_TEMPOS) if v <= high]
        return max(candidates) if candidates else 0
    candidates = [i for i, v in enumerate(VALID_TEMPOS) if v >= low]
    return min(candidates) if candidates else len(VALID_TEMPOS) - 1


def _steps_above(high: int, bpm: int) -> int:
    bound_idx = _bound_index(0, high, upper=True)
    target_idx = None
    for i, v in enumerate(VALID_TEMPOS):
        if v >= bpm:
            target_idx = i
            break
    if target_idx is None:
        target_idx = len(VALID_TEMPOS) - 1
    steps = target_idx - bound_idx
    return max(1, steps)


def _steps_below(low: int, bpm: int) -> int:
    bound_idx = _bound_index(low, 0, upper=False)
    target_idx = None
    for i in range(len(VALID_TEMPOS) - 1, -1, -1):
        if VALID_TEMPOS[i] <= bpm:
            target_idx = i
            break
    if target_idx is None:
        target_idx = 0
    steps = bound_idx - target_idx
    return max(1, steps)


def get_tempo_confidence(bpm: int, low: int, high: int, grade: float) -> float:
    if grade >= 5:
        return 1.0

    step_penalty = max(0.02, 0.09 - 0.01 * float(grade))

    if low <= bpm <= high:
        if bpm in VALID_TEMPOS:
            return 1.0
        steps = 1
    else:
        steps = _steps_below(low, bpm) if bpm < low else _steps_above(high, bpm)

    confidence = 1.0 - steps * step_penalty
    return max(0.0, min(1.0, confidence))
