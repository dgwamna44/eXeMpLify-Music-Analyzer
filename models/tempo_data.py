from dataclasses import dataclass

@dataclass
class TempoData:
    bpm: int
    duration: int
    grade: float
    exposure : float

    confidence: float | None = None
    comments : str | None = None