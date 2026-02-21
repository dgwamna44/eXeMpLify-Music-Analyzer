from __future__ import annotations

import math
import re

from music21 import converter, stream

from data_processing import build_instrument_data, derive_observed_grades
from utilities import (
    parse_part_name,
    validate_part_for_availability,
    format_grade,
    get_closest_grade,
)
from analyzers.rhythm.rules import load_rhythm_rules
from app_data import RHYTHM_TOKEN_MAP

SOLO_RE = re.compile(r"\\bsolo(?:ist|i)?\\b", re.IGNORECASE)

HIGH_WOODWINDS = {
    "flute",
    "piccolo",
    "oboe",
}
MID_WOODWINDS = {
    "clarinet_bb",
    "clarinet_eb",
    "alto_clarinet",
    "alto_sax",
    "tenor_sax",
    "soprano_sax",
}
LOW_WOODWINDS = {
    "bassoon",
    "bari_sax",
    "bass_sax",
    "bass_clarinet",
    "contra_bass_clarinet",
    "english_horn",
}

HIGH_BRASS = {
    "trumpet_bb",
}
MID_BRASS = {
    "horn_f",
}
LOW_BRASS = {
    "euphonium",
    "baritone",
    "trombone",
    "tuba",
}

HIGH_STRINGS = {
    "violin",
    "viola",
}
LOW_STRINGS = {
    "cello",
    "bass",
}

GROUP_LABELS = {
    "high_woodwinds": "High woodwinds",
    "mid_woodwinds": "Mid woodwinds",
    "low_woodwinds": "Low woodwinds",
    "high_brass": "High brass",
    "mid_brass": "Mid brass",
    "low_brass": "Low brass",
    "high_strings": "High strings",
    "low_strings": "Low strings",
    "percussion": "Percussion",
    "keyboard": "Keyboard",
}

FAMILY_LABELS = {
    "wind": "Woodwinds",
    "brass": "Brass",
    "string": "Strings",
    "percussion": "Percussion",
    "keyboard": "Keyboard",
}


def _pretty_instrument_name(key: str) -> str:
    if not key:
        return "Unknown"
    base = key
    suffix = ""
    for tag, label in (("_bb", " Bb"), ("_eb", " Eb"), ("_f", " F")):
        if key.endswith(tag):
            base = key[: -len(tag)]
            suffix = label
            break
    text = base.replace("_", " ").strip().title()
    return f"{text}{suffix}"


def _part_display_name(part) -> str:
    name = part.partName or part.partAbbreviation
    if not name:
        inst = part.getInstrument(returnDefault=False)
        if inst is not None:
            name = inst.instrumentName or inst.bestName()
    return name or "Unknown Part"


def _instrument_key(name: str) -> str:
    if not name:
        return "unknown"
    trimmed = parse_part_name(name)
    key = validate_part_for_availability(trimmed)
    if key == "unknown":
        key = validate_part_for_availability(name)
    return key


def _classify_group(instrument_key: str, family: str | None) -> str | None:
    if instrument_key in HIGH_WOODWINDS:
        return "high_woodwinds"
    if instrument_key in MID_WOODWINDS:
        return "mid_woodwinds"
    if instrument_key in LOW_WOODWINDS:
        return "low_woodwinds"
    if instrument_key in HIGH_BRASS:
        return "high_brass"
    if instrument_key in MID_BRASS:
        return "mid_brass"
    if instrument_key in LOW_BRASS:
        return "low_brass"
    if instrument_key in HIGH_STRINGS:
        return "high_strings"
    if instrument_key in LOW_STRINGS:
        return "low_strings"
    if family == "percussion":
        return "percussion"
    if family == "keyboard":
        return "keyboard"
    return None


def _compute_texture_density(score) -> tuple[float, float, int]:
    parts = list(score.parts)
    if not parts:
        return 0.0, 0.0, 0

    active_counts: dict[int, int] = {}
    measure_numbers: set[int] = set()

    for part in parts:
        active_measures: set[int] = set()
        for meas in part.getElementsByClass(stream.Measure):
            num = getattr(meas, "measureNumber", None)
            if num is None:
                continue
            measure_numbers.add(num)
            if meas.notes:
                active_measures.add(num)
        for num in active_measures:
            active_counts[num] = active_counts.get(num, 0) + 1

    if not measure_numbers:
        return 0.0, 0.0, 0

    measures = sorted(measure_numbers)
    total_measures = len(measures)
    avg_active = sum(active_counts.get(m, 0) for m in measures) / total_measures
    ratio = avg_active / len(parts) if parts else 0.0
    return ratio, avg_active, total_measures


def _norm_offset(value) -> float | None:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _get_rhythm_step(grade: float) -> float:
    rules = load_rhythm_rules()
    rule_grade = get_closest_grade(grade, rules.keys())
    if rule_grade is None:
        return 0.25
    rule = rules[rule_grade]
    token_durations = {
        data["token"]: data["duration"] for data in RHYTHM_TOKEN_MAP.values()
    }
    token = str(rule.max_subdivision or "").strip().lower()
    if token in {"", "any"}:
        step = 0.25
    else:
        step = token_durations.get(token, 1.0)
    if rule.allow_syncopation:
        step = step / 2
    return max(0.03125, step)


def _quantize_offset(offset: float, step: float) -> float:
    if step <= 0:
        return offset
    pos = offset / step
    snapped = round(pos)
    if abs(pos - snapped) <= 1e-3:
        return round(snapped * step, 6)
    return round(offset, 6)


def _pitch_midi(pitch_obj):
    try:
        midi = float(pitch_obj.midi)
    except (AttributeError, TypeError, ValueError):
        return None
    if not math.isfinite(midi):
        return None
    return midi


def _pick_event_pitch(event):
    pitches = getattr(event, "pitches", None)
    candidates = []
    if pitches:
        for p in pitches:
            midi = _pitch_midi(p)
            if midi is None:
                continue
            candidates.append((midi, p))
    else:
        pitch = getattr(event, "pitch", None)
        midi = _pitch_midi(pitch) if pitch is not None else None
        if midi is not None:
            candidates.append((midi, pitch))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def _is_congruent_interval(pitch_a, pitch_b) -> bool:
    if pitch_a is None or pitch_b is None:
        return False
    try:
        a_num = pitch_a.diatonicNoteNum
        b_num = pitch_b.diatonicNoteNum
        a_midi = pitch_a.midi
        b_midi = pitch_b.midi
    except Exception:
        return False
    if a_num is None or b_num is None or a_midi is None or b_midi is None:
        return False
    generic = (abs(b_num - a_num) % 7) + 1
    semitone = int(round(abs(b_midi - a_midi))) % 12
    if generic == 1:
        return semitone == 0
    if generic == 3:
        return semitone in {3, 4}
    if generic == 4:
        return semitone == 5
    if generic == 5:
        return semitone == 7
    if generic == 6:
        return semitone in {8, 9}
    return False


def _pair_congruency(events_a: dict, events_b: dict) -> dict[str, float | None]:
    onsets_a = set(events_a.keys())
    onsets_b = set(events_b.keys())
    if not onsets_a or not onsets_b:
        return {"rhythmic": None, "harmonic": None, "overall": None}

    shared = onsets_a & onsets_b
    rhythmic = len(shared) / max(len(onsets_a), len(onsets_b))

    total_intervals = 0
    congruent_intervals = 0
    for onset in shared:
        pitch_a = events_a.get(onset)
        pitch_b = events_b.get(onset)
        if pitch_a is None or pitch_b is None:
            continue
        total_intervals += 1
        if _is_congruent_interval(pitch_a, pitch_b):
            congruent_intervals += 1

    harmonic = (
        congruent_intervals / total_intervals if total_intervals > 0 else None
    )
    if harmonic is not None:
        overall = (0.6 * harmonic) + (0.4 * rhythmic)
    else:
        overall = rhythmic
    return {"rhythmic": rhythmic, "harmonic": harmonic, "overall": overall}


def _compute_congruency(score, grade: float) -> dict[str, float | None]:
    instrument_data = build_instrument_data()
    step = _get_rhythm_step(grade)

    part_events: dict[str, dict[tuple[int, float], object | None]] = {}
    part_groups: dict[str, str | None] = {}
    part_families: dict[str, str] = {}

    for part in score.parts:
        part_name = _part_display_name(part)
        inst_key = _instrument_key(part_name)
        inst_info = instrument_data.get(inst_key)
        family = inst_info.type if inst_info is not None else "unknown"
        group = _classify_group(inst_key, family)
        part_groups[part_name] = group
        part_families[part_name] = family

        events: dict[tuple[int, float], object | None] = {}
        for meas in part.getElementsByClass(stream.Measure):
            num = getattr(meas, "measureNumber", None)
            if num is None:
                continue
            for el in meas.recurse().notes:
                offset = _norm_offset(getattr(el, "offset", None))
                if offset is None:
                    continue
                quantized = _quantize_offset(offset, step)
                pitch = _pick_event_pitch(el)
                if pitch is None and family != "percussion":
                    continue
                events[(num, quantized)] = pitch

        if events:
            part_events[part_name] = events

    groups: dict[str, list[str]] = {}
    percussion_parts = []
    for part_name, group in part_groups.items():
        if part_name not in part_events:
            continue
        family = part_families.get(part_name, "unknown")
        if family == "percussion":
            percussion_parts.append(part_name)
        if group:
            groups.setdefault(group, []).append(part_name)

    def _avg_metrics(metrics_list, key):
        vals = [m[key] for m in metrics_list if m[key] is not None]
        return sum(vals) / len(vals) if vals else None

    group_metrics = {}
    for group_name, group_parts in groups.items():
        if len(group_parts) < 2:
            continue
        pair_metrics = []
        for i in range(len(group_parts)):
            for j in range(i + 1, len(group_parts)):
                a = group_parts[i]
                b = group_parts[j]
                pair_metrics.append(_pair_congruency(part_events[a], part_events[b]))
        if pair_metrics:
            group_metrics[group_name] = {
                "rhythmic": _avg_metrics(pair_metrics, "rhythmic"),
                "harmonic": _avg_metrics(pair_metrics, "harmonic"),
                "overall": _avg_metrics(pair_metrics, "overall"),
                "parts": len(group_parts),
            }

    within_vals = []
    within_weights = []
    for data in group_metrics.values():
        if data.get("overall") is None:
            continue
        within_vals.append(data["overall"])
        within_weights.append(data.get("parts", 1))
    within_group = (
        sum(v * w for v, w in zip(within_vals, within_weights)) / sum(within_weights)
        if within_vals
        else None
    )

    pairing_defs = [
        ("high_woodwinds", "high_brass"),
        ("mid_woodwinds", "mid_brass"),
        ("low_woodwinds", "low_brass"),
        ("high_woodwinds", "mid_woodwinds"),
        ("mid_woodwinds", "low_woodwinds"),
        ("high_brass", "mid_brass"),
        ("mid_brass", "low_brass"),
        ("high_strings", "low_strings"),
    ]
    pairing_metrics = []
    for a_group, b_group in pairing_defs:
        a_parts = groups.get(a_group) or []
        b_parts = groups.get(b_group) or []
        if not a_parts or not b_parts:
            continue
        for a in a_parts:
            for b in b_parts:
                pairing_metrics.append(_pair_congruency(part_events[a], part_events[b]))

    cross_group = _avg_metrics(pairing_metrics, "overall")

    perc_metrics = []
    if percussion_parts:
        non_perc = [
            name for name in part_events.keys()
            if part_families.get(name) != "percussion"
        ]
        for perc in percussion_parts:
            for other in non_perc:
                perc_metrics.append(_pair_congruency(part_events[perc], part_events[other]))

    percussion_rhythm = _avg_metrics(perc_metrics, "rhythmic")

    base = None
    if within_group is not None and cross_group is not None:
        base = (0.7 * within_group) + (0.3 * cross_group)
    elif within_group is not None:
        base = within_group
    elif cross_group is not None:
        base = cross_group

    if base is not None and percussion_rhythm is not None:
        base = min(1.0, base + (0.1 * percussion_rhythm))

    harmonic = _avg_metrics(pairing_metrics, "harmonic")
    rhythmic = _avg_metrics(pairing_metrics, "rhythmic")
    if within_group is not None:
        harmonic_vals = [d["harmonic"] for d in group_metrics.values() if d.get("harmonic") is not None]
        rhythmic_vals = [d["rhythmic"] for d in group_metrics.values() if d.get("rhythmic") is not None]
        if harmonic_vals:
            harmonic = (
                (harmonic or 0.0) + (sum(harmonic_vals) / len(harmonic_vals))
            ) / (2 if harmonic is not None else 1)
        if rhythmic_vals:
            rhythmic = (
                (rhythmic or 0.0) + (sum(rhythmic_vals) / len(rhythmic_vals))
            ) / (2 if rhythmic is not None else 1)

    return {
        "rhythmic": rhythmic,
        "harmonic": harmonic,
        "overall": base,
        "within_group": within_group,
        "cross_group": cross_group,
        "percussion_rhythm": percussion_rhythm,
    }


def _estimate_scoring_grade(profile) -> float | None:
    if not profile or not profile.get("total_parts"):
        return None

    grade = 0.5
    family_count = len(profile.get("families_present") or [])
    if family_count > 1:
        grade += 0.4 * (family_count - 1)

    subgroup_count = len(profile.get("groups_present") or [])
    if subgroup_count > 1:
        grade += 0.15 * (subgroup_count - 1)

    split_instruments = len(profile.get("split_instruments") or {})
    grade += 0.3 * split_instruments

    solo_count = len(profile.get("solo_parts") or [])
    grade += 0.35 * solo_count

    density = profile.get("texture_density") or 0.0
    if density >= 0.75:
        grade += 0.5
    elif density >= 0.6:
        grade += 0.25
    elif density <= 0.3:
        grade -= 0.25

    congruency = profile.get("overall_congruency")
    if congruency is not None:
        grade += (0.5 - congruency) * 1.2

    grade = max(0.5, min(5.0, grade))
    return grade


def _scoring_confidence(profile, grade: float) -> float | None:
    estimate = profile.get("grade_estimate")
    if estimate is None:
        return None
    slope = 1.4
    try:
        delta = float(grade) - float(estimate)
    except (TypeError, ValueError):
        return None
    return 1.0 / (1.0 + math.exp(-delta * slope))


def build_scoring_profile(score, grade: float):
    instrument_data = build_instrument_data()
    parts = list(score.parts)
    part_entries = []
    base_counts: dict[str, int] = {}

    for part in parts:
        display_name = _part_display_name(part)
        instrument_key = _instrument_key(display_name)
        inst_info = instrument_data.get(instrument_key)
        family = inst_info.type if inst_info is not None else "unknown"
        group = _classify_group(instrument_key, family)
        is_solo = bool(SOLO_RE.search(display_name))

        part_entries.append(
            {
                "name": display_name,
                "instrument_key": instrument_key,
                "family": family,
                "group": group,
                "is_solo": is_solo,
            }
        )
        base_counts[instrument_key] = base_counts.get(instrument_key, 0) + 1

    family_counts: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    for entry in part_entries:
        family = entry["family"]
        if family and family != "unknown":
            family_counts[family] = family_counts.get(family, 0) + 1
        group = entry["group"]
        if group:
            group_counts[group] = group_counts.get(group, 0) + 1

    split_instruments = {
        key: count
        for key, count in base_counts.items()
        if count > 1 and key != "unknown"
    }
    split_parts = {
        key: [entry["name"] for entry in part_entries if entry["instrument_key"] == key]
        for key in split_instruments
    }

    solo_parts = [entry["name"] for entry in part_entries if entry["is_solo"]]

    density_ratio, avg_active, total_measures = _compute_texture_density(score)
    congruency = _compute_congruency(score, grade)
    if density_ratio >= 0.7:
        density_label = "Dense texture"
    elif density_ratio <= 0.35:
        density_label = "Sparse texture"
    else:
        density_label = "Moderate texture"

    profile = {
        "total_parts": len(parts),
        "part_entries": part_entries,
        "families": family_counts,
        "groups": group_counts,
        "families_present": [k for k, v in family_counts.items() if v > 0],
        "groups_present": [k for k, v in group_counts.items() if v > 0],
        "split_instruments": split_instruments,
        "split_parts": split_parts,
        "solo_parts": solo_parts,
        "texture_density": density_ratio,
        "avg_active_parts": avg_active,
        "total_measures": total_measures,
        "texture_label": density_label,
        "rhythmic_congruency": congruency.get("rhythmic"),
        "harmonic_congruency": congruency.get("harmonic"),
        "overall_congruency": congruency.get("overall"),
        "within_group_congruency": congruency.get("within_group"),
        "cross_group_congruency": congruency.get("cross_group"),
        "percussion_rhythm_congruency": congruency.get("percussion_rhythm"),
    }
    profile["grade_estimate"] = _estimate_scoring_grade(profile)
    return profile


def build_scoring_notes(profile, grade: float):
    issues: list[str] = []
    issues_by_part: dict[str, list[str]] = {}
    highlights: list[str] = []

    family_counts = profile.get("families") or {}
    group_counts = profile.get("groups") or {}
    split_instruments = profile.get("split_instruments") or {}
    split_parts = profile.get("split_parts") or {}
    solo_parts = profile.get("solo_parts") or []
    density_ratio = profile.get("texture_density") or 0.0
    summary_metrics = {
        "Texture density": density_ratio,
        "Rhythmic congruency": profile.get("rhythmic_congruency"),
        "Harmonic congruency": profile.get("harmonic_congruency"),
        "Overall congruency": profile.get("overall_congruency"),
        "Within-group congruency": profile.get("within_group_congruency"),
        "Cross-group congruency": profile.get("cross_group_congruency"),
        "Percussion rhythmic congruency": profile.get("percussion_rhythm_congruency"),
    }

    def _add_pct_issue(label: str, value: float | None, reason: str) -> None:
        if value is None:
            return
        try:
            pct = int(round(float(value) * 100))
        except (TypeError, ValueError):
            return
        if pct >= 100:
            return
        issues.append(f"{label} {pct}%: {reason}")

    if family_counts:
        family_text = ", ".join(
            f"{FAMILY_LABELS.get(name, name.title())} ({count})"
            for name, count in family_counts.items()
        )
        highlights.append(f"Families present: {family_text}")

    if group_counts:
        group_text = ", ".join(
            f"{GROUP_LABELS.get(name, name.replace('_', ' ').title())} ({count})"
            for name, count in group_counts.items()
        )
        highlights.append(f"Instrument subgroups: {group_text}")

    if split_instruments:
        split_text = ", ".join(
            f"{_pretty_instrument_name(name)} (x{count})"
            for name, count in split_instruments.items()
        )
        highlights.append(f"Split parts detected: {split_text}")

    if solo_parts:
        highlights.append("Solo parts detected: " + ", ".join(solo_parts))

    total_parts = profile.get("total_parts") or 0
    avg_active = profile.get("avg_active_parts") or 0.0
    density_pct = int(round(density_ratio * 100))
    if total_parts > 0:
        highlights.append(
            f"{profile.get('texture_label', 'Texture density')}: "
            f"{density_pct}% of parts active on average ({avg_active:.1f} of {total_parts})."
        )

    _add_pct_issue(
        "Texture density",
        summary_metrics["Texture density"],
        "many parts are resting at different times.",
    )
    _add_pct_issue(
        "Rhythmic congruency",
        summary_metrics["Rhythmic congruency"],
        "not all parts align on the same rhythmic onsets.",
    )
    _add_pct_issue(
        "Harmonic congruency",
        summary_metrics["Harmonic congruency"],
        "simultaneous notes often diverge from consonant parallels.",
    )
    _add_pct_issue(
        "Overall congruency",
        summary_metrics["Overall congruency"],
        "global texture remains heterogeneous.",
    )
    _add_pct_issue(
        "Within-group congruency",
        summary_metrics["Within-group congruency"],
        "parts within the same family/voice diverge.",
    )
    _add_pct_issue(
        "Cross-group congruency",
        summary_metrics["Cross-group congruency"],
        "families diverge in rhythm or harmony.",
    )
    _add_pct_issue(
        "Percussion rhythmic congruency",
        summary_metrics["Percussion rhythmic congruency"],
        "percussion patterns do not consistently align with other voices.",
    )

    if grade < 2:
        grade_str = format_grade(grade)
        if split_instruments:
            issues.append(
                f"Multiple parts for the same instrument are uncommon below grade {grade_str}."
            )
            for base, part_names in split_parts.items():
                for name in part_names:
                    issues_by_part.setdefault(name, []).append(
                        f"Split part (multiple parts for the same instrument) not common below grade {grade_str}."
                    )
        if solo_parts:
            issues.append(f"Solo passages are uncommon below grade {grade_str}.")
            for name in solo_parts:
                issues_by_part.setdefault(name, []).append(
                    f"Solo passage detected (not common below grade {grade_str})."
                )

    message = None
    if not issues:
        total_parts = profile.get("total_parts") or 0
        if total_parts <= 1:
            message = "Scoring analysis skipped for single part scores"
        else:
            message = (
                "No particular scoring issues were detected for grade "
                f"{format_grade(grade)}"
            )

    summary = {
        "total_parts": total_parts,
        "families": family_counts,
        "groups": group_counts,
        "texture_density": density_ratio,
        "texture_label": profile.get("texture_label"),
        "rhythmic_congruency": profile.get("rhythmic_congruency"),
        "harmonic_congruency": profile.get("harmonic_congruency"),
        "overall_congruency": profile.get("overall_congruency"),
        "within_group_congruency": profile.get("within_group_congruency"),
        "cross_group_congruency": profile.get("cross_group_congruency"),
        "percussion_rhythm_congruency": profile.get("percussion_rhythm_congruency"),
    }

    return {
        "summary": summary,
        "highlights": highlights,
        "issues": issues,
        "issues_by_part": issues_by_part,
        "message": message,
        "grade_estimate": profile.get("grade_estimate"),
    }


def run_scoring(
    score_path: str,
    target_grade: float,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    analysis_options=None,
):
    if score_factory is None:
        if score is not None:
            score_factory = lambda: score
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    if analysis_options is not None:
        run_observed = analysis_options.run_observed

    if score is None:
        score = score_factory()

    profile = build_scoring_profile(score, target_grade)

    grades = None
    if analysis_options is not None:
        grades = analysis_options.observed_grades

    if run_observed:
        def _confidence(_profile, g):
            return _scoring_confidence(profile, g)

        kwargs = {
            "score_factory": lambda: profile,
            "analyze_confidence": _confidence,
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade, confidences = derive_observed_grades(**kwargs)
    else:
        observed_grade, confidences = None, {}

    notes = build_scoring_notes(profile, target_grade)
    overall_conf = _scoring_confidence(profile, target_grade)

    return {
        "observed_grade": observed_grade,
        "confidences": confidences,
        "analysis_notes": notes,
        "overall_confidence": overall_conf,
    }
