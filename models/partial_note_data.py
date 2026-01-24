from dataclasses import dataclass, field

@dataclass
class PartialNoteData:
    # required
    measure: int
    offset: float
    grade: float
    instrument: str

    comments: dict = field(default_factory=dict)

    duration: float | None = None
    written_midi_value: int | None = None
    written_pitch: str | None = None
    sounding_midi_value: int | None = None
    sounding_pitch: str | None = None

    # rhythm context
    beat_index: int | None = None
    beat_offset: float | None = None
    time_signature: str | None = None
    beat_unit: float | None = None

    # tuplets
    tuplet_id: int | None = None
    tuplet_actual: int | None = None
    tuplet_normal: int | None = None
    tuplet_index: int | None = None

    # derived
    rhythm_token: str | None = None
    rhythm_level: float | None = None

    # analyzer outputs
    relative_key_index: int | None = None
    range_confidence: float | None = None
    rhythm_confidence: float | None = None
    articulation_confidence: float | None = None
