from dataclasses import dataclass

@dataclass
class TempoData:
    bpm: int
    start: int
    qtr_len: int
    grade: float
    exposure : float

    confidence: float | None = None
    comments : str | None = None