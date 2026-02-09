# analyzers/key_range/confidence.py
from utilities import confidence_curve
from app_data import GRADE_TO_KEY_TABLE, PUBLISHER_CATALOG_FREQUENCY

def pub_cumulative_support(key, grade):
    values = [
        v for v in GRADE_TO_KEY_TABLE.get(key, {}).values()
        if isinstance(v, (int, float))
    ]
    return sum(max_grade <= grade for max_grade in values)

def pub_key_confidence(key, grade):
    values = [
        v for v in GRADE_TO_KEY_TABLE.get(key, {}).values()
        if isinstance(v, (int, float))
    ]
    if not values:
        return 0.0
    return confidence_curve(
        evidence=pub_cumulative_support(key, grade),
        normalize=len(values),
        k=2.0,
        max_conf=0.80
    )

def catalog_cumulative_exposure(key, grade):
    exposure = 0.0
    for g, count in PUBLISHER_CATALOG_FREQUENCY.get(key, {}).items():
        if g <= grade:
            exposure += count
    return exposure

def catalog_key_confidence(key, grade):
    exposure = catalog_cumulative_exposure(key, grade)
    total = sum(PUBLISHER_CATALOG_FREQUENCY.get(key, {}).values())

    if total == 0:
        return 0.0

    return confidence_curve(
        evidence=exposure,
        normalize=total,
        k=1.2,
        max_conf=0.20
    )

def total_key_confidence(key, grade):
    return (
        pub_key_confidence(key, grade)
        + catalog_key_confidence(key, grade)
    )

def harmonic_tolerance_penalty(grade):
    return .45 - ((grade-1) * .1)
