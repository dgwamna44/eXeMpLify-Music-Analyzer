from __future__ import annotations

from copy import deepcopy

from music21 import meter, stream, converter

from models import PartialNoteData
from analyzers.rhythm.helpers import get_rhythm_token, annotate_tuplets, is_implicit_empty_measure
from analyzers.rhythm.note_rules import rule_dotted, rule_subdivision, rule_syncopation, rule_tuplet
from analyzers.rhythm.rules import load_rhythm_rules
from data_processing import derive_observed_grades
from app_data import GRADES
from utilities import iter_measure_lines


def rhythm_note_confidence(note, rules_for_grade, target_grade):
    return [
        rule_dotted(note, rules_for_grade, target_grade),
        rule_syncopation(note, rules_for_grade, target_grade),
        rule_subdivision(note, rules_for_grade, target_grade),
        rule_tuplet(note, rules_for_grade, target_grade),
    ]


# ----------------------------
# 1) Confidence-only pass (no UI note data)
# ----------------------------

def analyze_rhythm_confidence(score, rules, grade: float) -> float | None:
    rules_for_grade = rules.get(grade)
    if rules_for_grade is None:
        return None

    part_confs: list[float] = []

    for part in score.parts:
        current_ts = None
        total_conf = 0.0
        total_dur = 0.0

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

            # implicit empty measure: ignore from confidence curve (your choice)
            # If you want empty measures to count as "acceptable" but not boost:
            if is_implicit_empty_measure(m, current_ts):
                continue

            # build aligned lists just for tuplet detection
            partial_notes = []
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

            for note in partial_notes:
                # ignore None tokens (won't occur here) and optionally ignore rests:
                if note.rhythm_token is None:
                    continue

                res = rhythm_note_confidence(note, rules_for_grade, grade)
                note_conf = min(r[0] for r in res)
                total_conf += note_conf * (note.duration or 0.0)
                total_dur += (note.duration or 0.0)

        if total_dur > 0:
            part_confs.append(total_conf / total_dur)

    if not part_confs:
        return None

    return sum(part_confs) / len(part_confs)


# ----------------------------
# 2) Target-grade pass (build UI note data)
# ----------------------------

def analyze_rhythm_target(score, rules, target_grade: float):
    analysis_notes = {}
    rules_for_grade = rules.get(target_grade)
    if rules_for_grade is None:
        return {}, None

    for part in score.parts:
        part_name = part.partName or "Unknown"
        current_ts = None

        analysis_notes[part_name] = {"note_data": []}
        partial_notes = []
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

            # implicit empty measure -> add a None-token "placeholder" note
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
        analysis_notes[part_name]["note_data"] = partial_notes

    # compute per-part rhythm confidence + attach comments
    part_confs: list[float] = []

    for part_name, part in analysis_notes.items():
        notes = part.get("note_data", [])
        total_conf = 0.0
        total_dur = 0.0

        for note in notes:
            if note.rhythm_token is None:
                # Empty measure placeholders: excluded from confidence (your current preference)
                continue

            res = rhythm_note_confidence(note, rules_for_grade, target_grade)
            note.rhythm_confidence = min(r[0] for r in res)

            for conf, msg, label in res:
                if label is not None and conf == 0 and msg:
                    note.comments[label] = msg

            total_conf += (note.rhythm_confidence or 0.0) * (note.duration or 0.0)
            total_dur += (note.duration or 0.0)

        part["rhythm_confidence"] = (total_conf / total_dur) if total_dur > 0 else None
        if part["rhythm_confidence"] is not None:
            part_confs.append(part["rhythm_confidence"])

    overall_conf = (sum(part_confs) / len(part_confs)) if part_confs else None
    return analysis_notes, overall_conf


# ----------------------------
# ENTRY POINT (this is where derive_observed_grades goes)
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

    # 1) observed grade + confidence curve (across all grades)
    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        grades = analysis_options.observed_grades

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda score, g: analyze_rhythm_confidence(score, rules, g),
            "progress_cb": progress_cb,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade, confidences = derive_observed_grades(**kwargs)
    else:
        observed_grade, confidences = None, {}

    # 2) target grade (UI note data)
    if score is None:
        score = score_factory()
    analysis_notes, overall_conf = analyze_rhythm_target(score, rules, target_grade)

    return {
        "observed_grade": observed_grade,
        "confidences": confidences,
        "analysis_notes": analysis_notes,
        "overall_confidence": overall_conf,
    }
