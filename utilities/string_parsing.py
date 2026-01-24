from app_data import CANONICAL_INSTRUMENTS
import re, math

def parse_part_name(name):
    if not name:
        return {}
    main = name
    optional = None

    m = re.search(r"\((.*?)\)", name)
    if m:
        optional = m.group(1)
        main = name[:m.start()].strip()
    return main, optional

def normalize_key_name(name):
    return name.replace("-", "b")

def validate_for_range_analysis(name):
    name = name.lower().replace("♭", "b").strip()

    for canonical, pattern in CANONICAL_INSTRUMENTS.items():
        if re.search(pattern, name):
            return canonical

    return "unknown"

def get_rounded_grade(grade): # can only return discrete values for getting ranges
    return 1 if grade == .5 else math.floor(grade)