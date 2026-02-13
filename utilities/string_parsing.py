from data_processing import build_instrument_data
import re, math


def parse_part_name(name):
    if not name:
        return {}
    main = name

    m = re.search(r"\((.*?)\)", name)
    if m:
        main = name[:m.start()].strip()
    return main


def normalize_key_name(name):
    return name.replace("-", "b")


def _normalize_part_name(name: str) -> str:
    # Normalize common symbols before stripping to keep regex matching stable
    normalized = (
        name.replace("♭", "b")
        .replace("â™­", "b")
        .replace("–", "-")
        .replace("â€“", "-")
    )
    ascii_name = normalized.encode("ascii", "ignore").decode()
    return ascii_name.lower().strip()


def validate_part_for_range_analysis(name):
    instrument_data = build_instrument_data()
    name = _normalize_part_name(name)

    for instrument in instrument_data:
        if re.search(instrument_data[instrument].regex, name):
            if instrument_data[instrument].range_analysis:
                return instrument

    return "unknown"


def validate_part_for_availability(name):
    instrument_data = build_instrument_data()
    name = _normalize_part_name(name)

    for instrument in instrument_data:
        if re.search(instrument_data[instrument].regex, name):
            return instrument

    return "unknown"


def get_rounded_grade(grade):  # can only return discrete values for getting ranges
    return 1 if grade == .5 else math.floor(grade)

def format_grade(grade) -> str:
    if grade is None:
        return ""
    try:
        val = float(grade)
    except (TypeError, ValueError):
        return str(grade)
    if not math.isfinite(val):
        return str(grade)
    if val.is_integer():
        return str(int(val))
    return f"{val:g}"


def get_closest_grade(grade, available_grades):
    if grade is None:
        return None
    grades = sorted(float(g) for g in available_grades)
    if not grades:
        return None
    if grade in grades:
        return grade
    return min(grades, key=lambda g: (abs(g - grade), -g))
