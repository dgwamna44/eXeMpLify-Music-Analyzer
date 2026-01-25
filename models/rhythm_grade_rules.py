from dataclasses import dataclass

@dataclass
class RhythmGradeRules:
    grade: float
    max_subdivision: str
    allow_dotted: bool
    allow_tuplet: bool
    allowed_tuplet_classes: list[str]
    allow_mixed_tuplet: bool
    allow_syncopation: bool
    allow_easy_compound: bool
    allow_mixed_compound: bool
    allow_compound: bool