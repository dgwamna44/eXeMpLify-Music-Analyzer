def clarinet_break_allowed(grade, part_name):
    if "Clarinet" in part_name:
        if grade < 2.0:
            return False
        if 2.0 <= grade < 3.0:
            return "Clarinet 1" in part_name
    return None

def crosses_break(written_note):
    return written_note in {"Bb4", "B4"}