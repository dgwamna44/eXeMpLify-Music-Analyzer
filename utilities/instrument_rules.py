HARMONIC_SERIES = [48, 60, 67, 72, 76, 79, 82, 84, 86, 88, 90, 91]

def get_brass_partials(instrument: str) :
    semitones = 0
    if instrument == "trumpet_bb":
        semitones = -2
    elif instrument == "horn_f":
        semitones = -7
    elif instrument in ["euphonium", "trombone", "baritone"]:
        semitones = -14
    elif instrument == "tuba":
        semitones = -26
    return {i: (partial - semitones) for i, partial in enumerate(HARMONIC_SERIES)}


def clarinet_break_allowed(grade, part_name):
    if "Clarinet" in part_name:
        if grade < 2.0:
            return False
        if 2.0 <= grade < 3.0:
            return "Clarinet 1" in part_name
    return None

def crosses_break(written_note):
    return written_note in {"Bb4", "B4"}