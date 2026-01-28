from dataclasses import dataclass

@dataclass
class InstrumentData:
    instrument: str
    regex: str
    type: str
    range_analysis: bool = True
    availability: float | None = None
