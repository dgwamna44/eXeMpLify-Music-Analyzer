from __future__ import annotations

from copy import deepcopy
import math
import re

from music21 import converter, interval, stream

from data_processing import build_instrument_data, derive_observed_grades
from utilities import parse_part_name, validate_part_for_availability, format_grade

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
    "bass_clarinet",
    "contra_bass_clarinet",
    "english_horn",
}

HIGH_BRASS = {
    "trumpet_bb",
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
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


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


def _compute_congruency(score) -> dict[str, float | None]:
    measure_map: dict[int, dict[str, dict[str, object]]] = {}

    for part in score.parts:
        part_name = _part_display_name(part)
        for meas in part.getElementsByClass(stream.Measure):
            num = getattr(meas, "measureNumber", None)
            if num is None:
                continue
            for el in meas.recurse().notes:
                offset = _norm_offset(getattr(el, "offset", None))
                if offset is None:
                    continue
                pitch = _pick_event_pitch(el)
                if pitch is None:
                    continue

                entry = measure_map.setdefault(num, {}).setdefault(
                    part_name,
                    {"offsets": set(), "pitches": {}},
                )
                entry["offsets"].add(offset)
                entry["pitches"][offset] = pitch

    total_onsets = 0
    shared_onsets = 0
    total_intervals = 0
    congruent_intervals = 0

    for part_map in measure_map.values():
        offset_counts: dict[float, int] = {}
        for data in part_map.values():
            offsets = data.get("offsets") or set()
            total_onsets += len(offsets)
            for offset in offsets:
                offset_counts[offset] = offset_counts.get(offset, 0) + 1

        for offset, count in offset_counts.items():
            if count < 2:
                continue
            shared_onsets += count
            pitches = [
                data.get("pitches", {}).get(offset)
                for data in part_map.values()
                if data.get("pitches", {}).get(offset) is not None
            ]
            if len(pitches) < 2:
                continue
            for i in range(len(pitches)):
                for j in range(i + 1, len(pitches)):
                    total_intervals += 1
                    if _is_congruent_interval(pitches[i], pitches[j]):
                        congruent_intervals += 1

    rhythmic = shared_onsets / total_onsets if total_onsets > 0 else None
    harmonic = (
        congruent_intervals / total_intervals if total_intervals > 0 else None
    )
    overall = None
    if harmonic is not None and rhythmic is not None:
        overall = (0.65 * harmonic) + (0.35 * rhythmic)
    elif harmonic is not None:
        overall = harmonic
    elif rhythmic is not None:
        overall = rhythmic

    return {
        "rhythmic": rhythmic,
        "harmonic": harmonic,
        "overall": overall,
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


def build_scoring_profile(score):
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
    congruency = _compute_congruency(score)
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

    if grade < 2:
        if split_instruments:
            issues.append("Multiple parts for the same instrument are uncommon below grade 2.")
            for base, part_names in split_parts.items():
                for name in part_names:
                    issues_by_part.setdefault(name, []).append(
                        "Split part (multiple parts for the same instrument) not common below grade 2."
                    )
        if solo_parts:
            issues.append("Solo passages are uncommon below grade 2.")
            for name in solo_parts:
                issues_by_part.setdefault(name, []).append(
                    "Solo passage detected (not common below grade 2)."
                )

    message = None
    if not issues:
        message = f"No particular scoring issues were detected for grade {format_grade(grade)}"

    summary = {
        "total_parts": total_parts,
        "families": family_counts,
        "groups": group_counts,
        "texture_density": density_ratio,
        "texture_label": profile.get("texture_label"),
        "rhythmic_congruency": profile.get("rhythmic_congruency"),
        "harmonic_congruency": profile.get("harmonic_congruency"),
        "overall_congruency": profile.get("overall_congruency"),
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
            score_factory = lambda: deepcopy(score)
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    if analysis_options is not None:
        run_observed = analysis_options.run_observed

    if score is None:
        score = score_factory()

    profile = build_scoring_profile(score)

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
