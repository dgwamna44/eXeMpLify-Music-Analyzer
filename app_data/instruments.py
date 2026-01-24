CANONICAL_INSTRUMENTS = {
    "violin": r"violin(?:\s+\d+)?",
    "viola": r"viola(?:\s+\d+)?",
    "cello": r"(?:cello|violoncello)(?:\s+\d+)?",
    "piccolo": r"piccolo(?:\s+\d+)?",
    "flute": r"flute(?:\s+\d+)?",
    "oboe": r"oboe(?:\s+\d+)?",
    "contra_bass_clarinet": r"contra bass clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "bass_clarinet": r"bass clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "clarinet_bb": r"(?:b♭\s+|bb\s+)?clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "alto_clarinet": r"(?:e♭\s+|eb\s+)?alto clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?",
    "bassoon": r"bassoon(?:\s+\d+)?",
    "alto_sax": r"(?:e♭\s+|eb\s+)?alto sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?",
    "tenor_sax": r"(?:b♭\s+|bb\s+)?tenor sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "bari_sax": r"(?:e♭\s+|eb\s+)?baritone sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?",
    "trumpet_bb": r"(?:b♭\s+|bb\s+)?trumpet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "horn_f": r"(?:f\s+)?(?:french\s+)?horn(?:\s+\d+)?(?:\s+in\s+|in)?(?:f)?",
    "trombone": r"(?:trombone|tenor trombone)(?:\s+\d+)?",
    "euphonium": r"euphonium(?:\s+\d+)?",
    "baritone": r"baritone(?:\s+\d+)?",
    "tuba": r"tuba(?:\s+\d+)?",
    "bass": r"^(?:bass|double bass)(?:\s+\d+)?$"
}


GRADE_TO_INSTRUMENTATION_TABLE = {
    "piccolo": {
        "ABC": 3, "FJH": 3, "Belwin": 4, "Marlatt": 4
    },
    "alto_flute": {
        "ABC": 4, "FJH": 4, "Belwin": 4, "Marlatt": 5
    },
    "bass_flute": {
        "ABC": 4, "FJH": 4, "Belwin": 4, "Marlatt": 5
    },
        "flute": {
        "ABC": 0.5, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "oboe": {
        "ABC": 2, "FJH": 1.5, "Belwin": 0.5, "Marlatt": 1
    },
    "english_horn": {
        "ABC": 4, "FJH": 4, "Belwin": 4, "Marlatt": 5
    },
    "clarinet_bb": {
        "ABC": 0.5, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "bass_clarinet": {
        "ABC": 2, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "alto_sax": {
        "ABC": 0.5, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "tenor_sax": {
        "ABC": 2, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "bari_sax": {
        "ABC": 2, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "bassoon": {
        "ABC": 2, "FJH": 1, "Belwin": 1.5, "Marlatt": 1
    },
    "horn_f": {
        "ABC": 2, "FJH": 1, "Belwin": 0.5, "Marlatt": 1
    },
    "trumpet_bb": {
        "ABC": 0.5, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "trombone": {
        "ABC": 0.5, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "bass_trombone": {
        "ABC": None, "FJH": 4, "Belwin": 4, "Marlatt": 5
    },
    "euphonium": {
        "ABC": 2, "FJH": 1, "Belwin": 0.5, "Marlatt": 1
    },
    "baritone": {
        "ABC": 2, "FJH": 1, "Belwin": 0.5, "Marlatt": 1
    },
    "snare_drum": {
        "ABC": 1, "FJH": 1, "Belwin": 0.5, "Marlatt": 1
    },
    "tuba": {
        "ABC": 1, "FJH": 1, "Belwin": 0.5, "Marlatt": 1
    },
    "timpani": {
        "ABC": 3, "FJH": 1.5, "Belwin": 0.5, "Marlatt": 1
    },
    "bass_drum": {
        "ABC": 1, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "bells": {
        "ABC": 1, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "drum_set": {
        "ABC": None, "FJH": None, "Belwin": 2.5, "Marlatt": None
    },
    "piano": {
        "ABC": None, "FJH": None, "Belwin": 2.5, "Marlatt": 4
    },
    "synthesizer": {
        "ABC": None, "FJH": None, "Belwin": 3, "Marlatt": None
    },
    "electric_bass": {
        "ABC": None, "FJH": None, "Belwin": 3, "Marlatt": None
    },
    "vibraphone": {
        "ABC": 2, "FJH": 2, "Belwin": 1, "Marlatt": 2
    },
    "marimba": {
        "ABC": 2, "FJH": 2, "Belwin": 1, "Marlatt": 2
    },
    "xylophone": {
        "ABC": 2, "FJH": 2, "Belwin": 1, "Marlatt": 2
    },
}