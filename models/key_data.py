from dataclasses import dataclass

@dataclass
class KeyData:
    measure: int
    grade: float
    key: str
    quality: str
    pitch_index: int
    duration: int | None = None
    exposure: float | None = None
    confidence: float | None = None
