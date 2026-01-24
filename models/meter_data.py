from dataclasses import dataclass

@dataclass
class MeterData:
    measure: int
    time_signature: str
    grade: float

    duration: int | None = None
    exposure: int | None = None
    confidence: float | None = None
    comments: dict | None = None