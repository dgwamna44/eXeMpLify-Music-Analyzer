from app_data import RHYTHM_TOKEN_MAP
from utilities import format_grade
from .helpers import check_syncopation, get_quarter_length, get_token_duration
from .rules import normalize_tuplet_class, TUPLET_CLASS_ORDER

TOKEN_TO_NAME = {data["token"]: name for name, data in RHYTHM_TOKEN_MAP.items()}


def _token_label(token: str | None) -> str:
    if not token:
        return "unknown"
    base = str(token).rstrip("d").lower()
    name = TOKEN_TO_NAME.get(base, token)
    dots = str(token).count("d")
    if dots > 0 and name != token:
        return f"dotted {name}"
    return name


def _rule_token_label(token: str | None) -> str:
    if token is None:
        return "any"
    val = str(token).strip().lower()
    if val in {"any", ""}:
        return "any"
    return _token_label(val)


def _ratio_penalty(ratio: float, *, exponent: float, floor: float) -> float:
    if ratio is None:
        return 1.0
    ratio = max(0.0, min(1.0, ratio))
    return max(floor, ratio ** exponent)

def _max_allowed_duration(rules):
    token = str(rules.max_subdivision).strip().lower()
    if token in {"any", ""}:
        return None
    return get_token_duration(token)

def rule_dotted(note, rules, target_grade):
    if "d" not in note.rhythm_token:
        return (1, None, None)
    if rules.allow_dotted:
        return (1, None, None)
    note_duration = note.duration or get_quarter_length(note.rhythm_token)
    max_allowed = _max_allowed_duration(rules)
    ratio = None
    if note_duration is not None and max_allowed:
        ratio = note_duration / max_allowed
    conf = 0.7 * _ratio_penalty(ratio, exponent=1.2, floor=0.05)
    return (
        conf,
        f"dotted rhythms not common for grade {format_grade(target_grade)}",
        "Dotted Rhythm",
    )

def rule_syncopation(note, rules, target_grade):
    _, is_sync = check_syncopation(note.duration, note.offset)
    if not is_sync:
        return (1, None, None)
    if rules.allow_syncopation:
        return (1, None, None)
    ratio = None
    if note.duration is not None and note.beat_unit is not None:
        ratio = note.duration / note.beat_unit
    conf = 0.85 * _ratio_penalty(ratio, exponent=0.6, floor=0.2)
    return (
        conf,
        f"syncopation not common for grade {format_grade(target_grade)}",
        "Syncopation",
    )


def rule_subdivision(note, rules, target_grade):
    note_duration = note.duration if note.duration is not None else get_quarter_length(note.rhythm_token)
    if note_duration is None:
        return (0.7, f"unknown rhythm value {_token_label(note.rhythm_token)}", "Subdivision")
    if float(target_grade) < 5 and note_duration <= 0.0625:
        return (
            0.0,
            f"64th notes or smaller not common for grade {format_grade(target_grade)}",
            "Subdivision",
        )
    if float(target_grade) == 0.5 and getattr(note, "eighth_pair_ok", False):
        return (1, None, None)
    if float(target_grade) == 0.5 and getattr(note, "eighth_pair_overflow", False):
        return (
            0.0,
            f"consecutive eighth notes not common for grade {format_grade(target_grade)}",
            "Subdivision",
        )
    max_allowed = _max_allowed_duration(rules)
    if max_allowed is None:
        return (1, None, None)
    if note_duration >= max_allowed:
        return (1, None, None)
    max_label = _rule_token_label(rules.max_subdivision)
    ratio = note_duration / max_allowed
    if float(target_grade) < 4 and ratio <= 0.5:
        return (
            0.0,
            f"subdivisions smaller than a {max_label} note not common for grade {format_grade(target_grade)}",
            "Subdivision",
        )
    exponent = max(2.0, 6.0 - float(target_grade))
    conf = _ratio_penalty(ratio, exponent=exponent, floor=0.02)
    return (
        conf,
        f"subdivisions smaller than a {max_label} note not common for grade {format_grade(target_grade)}",
        "Subdivision",
    )

def rule_tuplet(note, rules, target_grade):
    if note.tuplet_id is None:
        return (1, None, None)
    if not rules.allow_tuplet:
        tuplet_class = normalize_tuplet_class(note.tuplet_class)
        order = TUPLET_CLASS_ORDER.get(tuplet_class, 1)
        conf = max(0.05, 0.5 / (order + 1))
        return (conf, "Tuplets not common for given grade", "Tuplets")
    if tuplet_class := normalize_tuplet_class(note.tuplet_class):
        if tuplet_class in rules.allowed_tuplet_classes:
            return (1, None, None)
        allowed_order = 0
        if rules.allowed_tuplet_classes:
            allowed_order = max(TUPLET_CLASS_ORDER.get(c, 0) for c in rules.allowed_tuplet_classes)
        order = TUPLET_CLASS_ORDER.get(tuplet_class, allowed_order + 1)
        ratio = (allowed_order + 1) / (order + 1) if order >= 0 else 0
        conf = max(0.1, 0.8 * ratio)
        return (
            conf,
            f"{tuplet_class} tuplets not common for grade {format_grade(target_grade)}",
            "Tuplets",
        )
        
