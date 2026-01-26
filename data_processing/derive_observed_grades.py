from app_data import GRADES

def derive_observed_grades(score, analyze_func):
    confidences = {}

    for grade in GRADES:
        confidences[grade] = analyze_func(score, grade)

    observed = _derive_observed_grade(confidences)
    return observed, confidences

def _derive_observed_grade(confidences: dict):
    """
    If all confidences are extremely high and flat, choose lowest grade.
    Otherwise choose grade with max confidence.
    """
    # drop None
    filtered = {g: c for g, c in confidences.items() if c is not None}
    if not filtered:
        return None

    grades = sorted(filtered.keys())
    values = [filtered[g] for g in grades]

    # compute deltas
    deltas = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    # too easy detector
    if deltas and min(deltas) > 0.97:
        return grades[0]

    return grades[values.index(max(values))]