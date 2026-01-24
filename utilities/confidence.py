import math

def traffic_light(c: float) -> str:
    if .6 < c <= 1:
        return "green"
    elif .4 < c <= .6:
        return "yellow"
    elif .2 < c <= .4:
        return "orange"
    return "red"

def confidence_curve(
    evidence: float,
    *,
    k: float = 0.75,
    max_conf: float = 1.0,
    normalize: float | None = None
) -> float:
    """
    Generic saturating confidence function.

    evidence   : raw evidence (count, weight, frequency)
    normalize  : value to divide evidence by (optional)
    k          : growth rate
    max_conf   : confidence ceiling
    """
    if normalize:
        evidence = evidence / normalize if normalize > 0 else 0.0

    return max_conf * (1 - math.exp(-k * evidence))