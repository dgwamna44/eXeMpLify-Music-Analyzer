from dataclasses import dataclass

@dataclass
class DurationData:
    duration: int
    length_string : str
    grade : float

    comments : str | None = None
    confidence : float | None = None

@dataclass
class DurationGradeBucket:
    grade: float
    core_max: float
    extended_max: float | None = None 
