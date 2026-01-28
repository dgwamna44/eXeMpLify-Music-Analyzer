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

def validate_part_for_analysis(name):
    instrument_data = build_instrument_data()
    name = name.lower().replace("♭", "b").strip()

    for instrument in instrument_data:
        if re.search(instrument_data[instrument].regex, name):
            if instrument_data[instrument].range_analysis:
                return instrument

    return "unknown"

def get_rounded_grade(grade): # can only return discrete values for getting ranges
    return 1 if grade == .5 else math.floor(grade)