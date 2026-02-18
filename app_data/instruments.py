NON_PERCUSSION_INSTRUMENTS = {
    "violin": r"violin(?:\s+\d+)?",
    "viola": r"viola(?:\s+\d+)?",
    "cello": r"(?:cello|violoncello)(?:\s+\d+)?",
    "piccolo": r"piccolo(?:\s+\d+)?",
    "flute": r"flute(?:\s+\d+)?",
    "oboe": r"oboe(?:\s+\d+)?",
    "english_horn": r"(?:english horn|cor anglais)(?:\s+\d+)?",
    "contra_bass_clarinet": r"contra bass clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "bass_clarinet": r"bass clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "clarinet_eb": r"(?:(?:e♭|eb)\s+clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?|clarinet(?:\s+\d+)?(?:\s+in\s+|in)\s*(?:e♭|eb))",
    "clarinet_bb": r"(?:b♭\s+|bb\s+)?clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "alto_clarinet": r"(?:e♭\s+|eb\s+)?alto clarinet(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?",
    "bassoon": r"bassoon(?:\s+\d+)?",
    "soprano_sax": r"(?:b♭\s+|bb\s+)?soprano sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "alto_sax": r"(?:e♭\s+|eb\s+)?alto sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?",
    "tenor_sax": r"(?:b♭\s+|bb\s+)?tenor sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "bari_sax": r"(?:e♭\s+|eb\s+)?baritone sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:e♭|eb)?",
    "bass_sax": r"(?:bb\s+)?bass sax(?:ophone)?(?:\s+\d+)?(?:\s+in\s+|in)?(?:bb)?",
    "trumpet_bb": r"(?:b♭\s+|bb\s+)?trumpet(?:\s+\d+)?(?:\s+in\s+|in)?(?:b♭|bb)?",
    "horn_f": r"(?:f\s+)?(?:french\s+)?horn(?:\s+\d+)?(?:\s+in\s+|in)?(?:f)?",
    "trombone": r"(?:trombone|tenor trombone)(?:\s+\d+)?",
    "euphonium": r"euphonium(?:\s+\d+)?",
    "baritone": r"baritone(?:\s+\d+)?",
    "tuba": r"tuba(?:\s+\d+)?",
    "bass": r"^(?:bass|double bass)(?:\s+\d+)?$",
    "piano": r".* piano(?:\s+\d+)?",
    "synthesizer": r"synthesizer(?:\s+\d+)?",
    "organ": r".* organ(?:\s+\d+)?",
    "celesta": r"celesta(?:\s+\d+)?",
    "harpsichord": r"harpsichord(?:\s+\d+)?",
}


PERCUSSION_INSTRUMENTS = {
    "snare_drum": r"snare drum(?:\s+\d+)?",
    "bass_drum": r"bass drum(?:\s+\d+)?",
    "timpani": r"timpani(?:\s+\d+)?",
    "drum_set": r"(?:drum set|drum kit)(?:\s+\d+)?",
    "bells": r"(?:bells|glockenspiel)(?:\s+\d+)?",
    "xylophone": r"xylophone(?:\s+\d+)?",
    "marimba": r"marimba(?:\s+\d+)?",
    "vibraphone": r"vibraphone(?:\s+\d+)?"
    }


FAMILY_MAP = {
    # strings
    "violin": "string",
    "viola": "string",
    "cello": "string",
    "bass": "string",

    # winds
    "piccolo": "wind",
    "flute": "wind",
    "oboe": "wind",
    "english_horn": "wind",
    "bassoon": "wind",
    "clarinet_eb": "wind",
    "clarinet_bb": "wind",
    "alto_clarinet": "wind",
    "bass_clarinet": "wind",
    "contra_bass_clarinet": "wind",
    "alto_sax": "wind",
    "tenor_sax": "wind",
    "bari_sax": "wind",
    "bass_sax": "wind",
    "soprano_sax": "wind",

    # brass
    "trumpet_bb": "brass",
    "horn_f": "brass",
    "trombone": "brass",
    "euphonium": "brass",
    "baritone": "brass",
    "tuba": "brass",

    #keyboard
    "piano": "keyboard",
    "synthesizer": "keyboard",
    "celesta": "keyboard",
    "harpsichord": "keyboard",
    "organ": "keyboard",
}


INST_TO_GRADE_NON_STRING = {
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
    "clarinet_eb":
    {
        "Marlatt": 5,
    },
    "clarinet_bb": {
        "ABC": 0.5, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "alto_clarinet":{
          "Marlatt": 1.5, "Kjos": .5
    },
    "soprano_sax":{
        "ABC": 5
    },
    "bass_clarinet": {
        "ABC": 2, "FJH": 0.5, "Belwin": 0.5, "Marlatt": 1
    },
    "contra_bass_clarinet": {
       "Marlatt": 5
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
    "bass_sax": {
        "ABC": 5, "FJH": 5, "Belwin": 5, "Marlatt": 5
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
        "FJH": 4, "Belwin": 4, "Marlatt": 5
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
        "Belwin": 2.5
    },
    "piano": {
        "Belwin": 2.5, "Marlatt": 4
    },
    "synthesizer": {
        "Belwin": 3
    },
    "electric_bass": {
        "Belwin": 3
    },
    "vibraphone": {
        "ABC": 2, "FJH": 2, "Belwin": 1, "Marlatt": 2
    },
    "marimba": {
        "ABC": 2, "FJH": 2, "Belwin": 1, "Marlatt": 2
    },
    "xylophone": {
        "ABC": 2, "FJH": 2, "Belwin": 1, "Marlatt": 2
    }
}
