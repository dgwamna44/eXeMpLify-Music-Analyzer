from __future__ import annotations

from copy import deepcopy
from music21 import meter, stream, converter

from models import PartialNoteData
from analyzers.rhythm.helpers import (
    get_rhythm_token,
    annotate_tuplets,
    is_implicit_empty_measure,
    is_extreme_hit,   # expects: is_extreme_hit(note, rule_results, grade)->bool
    mark_eighth_pairs,
)
from analyzers.rhythm.note_rules import rule_dotted, rule_subdivision, rule_syncopation, rule_tuplet
from analyzers.rhythm.rules import load_rhythm_rules
from data_processing import derive_observed_grades
from utilities import get_closest_grade, iter_measure_lines


def rhythm_note_confidence(note, rules_for_grade, target_grade):
    return [
        rule_dotted(note, rules_for_grade, target_grade),
        rule_syncopation(note, rules_for_grade, target_grade),
        rule_subdivision(note, rules_for_grade, target_grade),
        rule_tuplet(note, rules_for_grade, target_grade),
    ]


def compute_note_confidence(note, rules_for_grade, target_grade):
    res = rhythm_note_confidence(note, rules_for_grade, target_grade)
    return min(r[0] for r in res), res


def _severe_measure_multiplier(measure_mins, grade, *, severe_threshold=0.2):
    if not measure_mins:
        return 1.0
    severe_count = sum(1 for m in measure_mins if m <= severe_threshold)
    total = len(measure_mins)
    if total == 0:
        return 1.0

    ratio = severe_count / total
    allowed = 0.02 + 0.06 * (grade / 5.0)

    if ratio <= allowed:
        return 1.0

    drop_limit = 1.5 * allowed
    if ratio >= drop_limit:
        return 0.0

    return max(0.0, 1.0 - (ratio - allowed) / (drop_limit - allowed))


def _apply_pg13_gate(part_conf: float, extreme_measure_count: int, grade: float, *, allowed=1, cap_if_one=0.65) -> float:
    """Quota-based gate for extreme measures (below grade 5)."""
    if float(grade) >= 5.0:
        return part_conf

    if extreme_measure_count > allowed:
        return 0.0
    if extreme_measure_count == allowed and allowed == 1:
        return min(part_conf, cap_if_one)

    return part_conf


# ----------------------------
# 1) Confidence-only pass (no UI note data)
# ----------------------------

def analyze_rhythm_confidence(score, rules, grade: float) -> float | None:
    rule_grade = get_closest_grade(grade, rules.keys())
    rules_for_grade = rules.get(rule_grade) if rule_grade is not None else None
    if rules_for_grade is None:
        return None

    part_confs: list[float] = []

    for part in score.parts:
        current_ts = None
        total_conf = 0.0
        total_dur = 0.0
        measure_mins: list[float] = []

        hard_subdivision_hit = False
        extreme_measure_count = 0  # <-- per part

        for m in part.getElementsByClass(stream.Measure):
            ts = m.getContextByClass(meter.TimeSignature)
            if ts is None:
                local_ts = list(m.getElementsByClass(meter.TimeSignature))
                ts = local_ts[0] if local_ts else None
            if ts is not None:
                current_ts = ts
            if current_ts is None:
                continue

            beat_length = current_ts.beatDuration.quarterLength

            if is_implicit_empty_measure(m, current_ts):
                continue

            partial_notes: list[PartialNoteData] = []
            music21_notes = []

            for line_index, events in iter_measure_lines(m):
                for event_index, n in enumerate(events):
                    written_pitch = None
                    written_midi = None
                    if not n.isRest and getattr(n, "isChord", False) is False and hasattr(n, "pitch"):
                        written_pitch = n.pitch.nameWithOctave
                        written_midi = n.pitch.midi

                    p = PartialNoteData(
                        measure=m.number,
                        offset=n.offset,
                        grade=grade,
                        instrument=(part.partName or ""),
                        duration=n.duration.quarterLength,
                        written_pitch=written_pitch,
                        written_midi_value=written_midi,
                        rhythm_token=get_rhythm_token(n) + ("r" if n.isRest else ""),
                        beat_index=int(n.offset // beat_length),
                        beat_offset=(n.offset % beat_length),
                        beat_unit=beat_length,
                        voice_index=line_index,
                        chord_index=event_index,
                        is_chord=bool(getattr(n, "isChord", False)),
                        chord_size=len(n.pitches) if getattr(n, "isChord", False) else None,
                    )
                    partial_notes.append(p)
                    music21_notes.append(n)

            annotate_tuplets(partial_notes, music21_notes)
            mark_eighth_pairs(partial_notes, grade=grade)

            measure_conf_sum = 0.0
            measure_dur = 0.0
            measure_min = 1.0
            measure_has_extreme = False

            for note in partial_notes:
                if note.rhythm_token is None:
                    continue

                note_conf, res = compute_note_confidence(note, rules_for_grade, grade)

                # measure-level extreme flag
                if is_extreme_hit(note, res, grade):
                    measure_has_extreme = True

                # keep your hard-subdivision shortcut
                if any((label == "Subdivision" and conf == 0.0) for conf, _, label in res):
                    hard_subdivision_hit = True

                measure_min = min(measure_min, note_conf)
                d = (note.duration or 0.0)
                measure_conf_sum += note_conf * d
                measure_dur += d

            if measure_dur <= 0:
                continue

            # base measure scoring
            measure_avg = measure_conf_sum / measure_dur
            measure_conf = measure_avg * measure_min

            # If ANY extreme occurs in the measure and grade < 5, the whole measure is "cursed"
            if measure_has_extreme and float(grade) < 5.0:
                measure_conf = 0.0
                measure_min = 0.0  # so it also registers as severe
                extreme_measure_count += 1

            total_conf += measure_conf * measure_dur
            total_dur += measure_dur
            measure_mins.append(measure_min)

        if total_dur <= 0:
            continue

        part_conf = total_conf / total_dur
        part_conf *= _severe_measure_multiplier(measure_mins, grade)

        # your original "hard subdivision" kill switch, updated to < 5 per your spec
        if hard_subdivision_hit and float(grade) < 5.0:
            part_conf = 0.0

        # PG-13 / quota gate by EXTREME MEASURES
        part_conf = _apply_pg13_gate(part_conf, extreme_measure_count, grade, allowed=1, cap_if_one=0.65)

        part_confs.append(part_conf)

    if not part_confs:
        return None

    return sum(part_confs) / len(part_confs)


# ----------------------------
# 2) Target-grade pass (build UI note data)
# ----------------------------

def analyze_rhythm_target(score, rules, target_grade: float):
    analysis_notes = {}
    rule_grade = get_closest_grade(target_grade, rules.keys())
    rules_for_grade = rules.get(rule_grade) if rule_grade is not None else None
    if rules_for_grade is None:
        return {}, None

    # Build note data
    for part in score.parts:
        part_name = part.partName or "Unknown"
        current_ts = None

        analysis_notes[part_name] = {"note_data": [], "extreme_measures": []}
        partial_notes: list[PartialNoteData] = []
        music21_notes = []

        for m in part.getElementsByClass(stream.Measure):
            ts = m.getContextByClass(meter.TimeSignature)
            if ts is None:
                local_ts = list(m.getElementsByClass(meter.TimeSignature))
                ts = local_ts[0] if local_ts else None
            if ts is not None:
                current_ts = ts
            if current_ts is None:
                continue

            beat_length = current_ts.beatDuration.quarterLength

            if is_implicit_empty_measure(m, current_ts):
                partial_notes.append(
                    PartialNoteData(
                        measure=m.number,
                        offset=0.0,
                        grade=target_grade,
                        instrument=part_name,
                        duration=current_ts.barDuration.quarterLength,
                        rhythm_token=None,
                        beat_index=None,
                        beat_offset=None,
                        beat_unit=beat_length,
                    )
                )
                continue

            for line_index, events in iter_measure_lines(m):
                for event_index, n in enumerate(events):
                    beat_index = int(n.offset // beat_length)
                    beat_offset = n.offset % beat_length

                    written_pitch = None
                    written_midi = None
                    if not n.isRest and getattr(n, "isChord", False) is False and hasattr(n, "pitch"):
                        written_pitch = n.pitch.nameWithOctave
                        written_midi = n.pitch.midi

                    p = PartialNoteData(
                        measure=m.number,
                        offset=n.offset,
                        grade=target_grade,
                        instrument=part_name,
                        duration=n.duration.quarterLength,
                        written_pitch=written_pitch,
                        written_midi_value=written_midi,
                        rhythm_token=get_rhythm_token(n) + ("r" if n.isRest else ""),
                        beat_index=beat_index,
                        beat_offset=beat_offset,
                        beat_unit=beat_length,
                        chord_index=event_index,
                        voice_index=line_index,
                        is_chord=bool(getattr(n, "isChord", False)),
                        chord_size=len(n.pitches) if getattr(n, "isChord", False) else None,
                    )
                    partial_notes.append(p)
                    music21_notes.append(n)

        annotate_tuplets(partial_notes, music21_notes)
        mark_eighth_pairs(partial_notes, grade=target_grade)
        analysis_notes[part_name]["note_data"] = partial_notes

    # Score per part + attach comments
    part_confs: list[float] = []

    for part_name, part in analysis_notes.items():
        notes: list[PartialNoteData] = part.get("note_data", [])

        total_conf = 0.0
        total_dur = 0.0
        measure_acc: dict[int, dict[str, float | bool]] = {}
        hard_subdivision_hit = False

        for note in notes:
            if note.rhythm_token is None:
                continue

            note_conf, res = compute_note_confidence(note, rules_for_grade, target_grade)
            note.rhythm_confidence = note_conf

            if any((label == "Subdivision" and conf == 0.0) for conf, _, label in res):
                hard_subdivision_hit = True

            # Attach note-level comments
            for conf, msg, label in res:
                if label is not None and conf < 1 and msg:
                    note.comments[label] = msg

            measure = note.measure if note.measure is not None else -1
            acc = measure_acc.setdefault(measure, {"sum": 0.0, "dur": 0.0, "min": 1.0, "extreme": False})

            d = (note.duration or 0.0)
            acc["sum"] = float(acc["sum"]) + (note_conf * d)
            acc["dur"] = float(acc["dur"]) + d
            acc["min"] = min(float(acc["min"]), note_conf)

            # Measure-level extreme detection
            if is_extreme_hit(note, res, target_grade):
                acc["extreme"] = True

        # Compute measure confidences
        extreme_measure_count = 0
        for measure_num, acc in measure_acc.items():
            dur = float(acc["dur"])
            if dur <= 0:
                continue

            measure_avg = float(acc["sum"]) / dur
            measure_min = float(acc["min"])
            measure_conf = measure_avg * measure_min

            if bool(acc["extreme"]) and float(target_grade) < 5.0:
                measure_conf = 0.0
                extreme_measure_count += 1
                part["extreme_measures"].append(measure_num)

            total_conf += measure_conf * dur
            total_dur += dur

        if total_dur > 0:
            measure_mins = [
                (0.0 if bool(acc["extreme"]) and float(target_grade) < 5.0 else float(acc["min"]))
                for acc in measure_acc.values()
                if float(acc["dur"]) > 0
            ]

            part_conf = (total_conf / total_dur) * _severe_measure_multiplier(measure_mins, target_grade)

            if hard_subdivision_hit and float(target_grade) < 5.0:
                part_conf = 0.0

            part_conf = _apply_pg13_gate(part_conf, extreme_measure_count, target_grade, allowed=1, cap_if_one=0.65)

            part["rhythm_confidence"] = part_conf
            part_confs.append(part_conf)
        else:
            part["rhythm_confidence"] = None

    overall_conf = (sum(part_confs) / len(part_confs)) if part_confs else None
    return analysis_notes, overall_conf

def analyze_rhythm(score, rules, grade: float, *, run_target: bool = False):
    if run_target:
        return analyze_rhythm_target(score, rules, grade)
    return analyze_rhythm_confidence(score, rules, grade)

# ----------------------------
# ENTRY POINT
# ----------------------------

def run_rhythm(
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

    rules = load_rhythm_rules()

    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        grades = analysis_options.observed_grades

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda sc, g: analyze_rhythm(sc, rules, g, run_target=False),
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade, confidences = derive_observed_grades(**kwargs)
    else:
        observed_grade, confidences = None, {}

    if score is None:
        score = score_factory()

    analysis_notes, overall_conf = analyze_rhythm(score, rules, target_grade, run_target=True)

    return {
        "observed_grade": observed_grade,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }
