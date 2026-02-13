from __future__ import annotations

from copy import deepcopy

from analyzers.base import BaseAnalyzer
from analyzers.key_range.extract import extract_key_segments, extract_note_data
from analyzers.key_range.rules import total_key_confidence, compute_range_confidence
from data_processing import build_instrument_data
import math
from utilities import (
    format_grade,
    get_rounded_grade,
    parse_part_name,
    traffic_light,
    validate_part_for_range_analysis,
)
from music21 import converter


class KeyRangeAnalyzer(BaseAnalyzer):
    """
    Handles BOTH key analysis and range analysis.
    BaseAnalyzer.rules = combined_ranges (instrument -> grade -> {core, extended} + total_range).
    """

    def __init__(self, combined_ranges: dict, *, key_segments_base=None, key_confidence_fn=total_key_confidence):
        super().__init__(combined_ranges)  # BaseAnalyzer stores this on self.rules
        self._key_segments_base = key_segments_base
        self._key_confidence_fn = key_confidence_fn

    def _get_key_segments(self, score, grade: float):
        if self._key_segments_base is None:
            return extract_key_segments(score, grade)
        key_segments = deepcopy(self._key_segments_base)
        for k in key_segments:
            k.grade = grade
        return key_segments

    @staticmethod
    def _get_brass_partial(sounding_midi: int | None, partials: dict | None) -> int | None:
        if sounding_midi is None or not partials:
            return None
        closest = min(partials.items(), key=lambda kv: abs(kv[1] - sounding_midi))
        return int(closest[0]) + 1  # store partial number (1-based)

    @staticmethod
    def _partial_jump_penalty(grade: float) -> float:
        if grade is None:
            return 0.0
        capped = min(float(grade), 3.0)
        steps = int(math.floor((capped - 0.5) / 0.5 + 1e-6))
        return max(0.0, 0.3 - 0.05 * steps)

    # -------------------------------------------------------------
    # CORE ANALYSIS (confidence-only or target)
    # -------------------------------------------------------------

    def analyze(self, score, grade: float, *, run_target: bool = False):
        ranges = self.rules
        range_grade = float(get_rounded_grade(grade))
        instrument_data = build_instrument_data()

        # --- Key segments ---
        key_segments = self._get_key_segments(score, grade)
        key_changes = len(key_segments) - 1

        for k in key_segments:
            k.confidence = self._key_confidence_fn(k.key, grade, k.quality)
            if run_target:
                color = traffic_light(k.confidence)
                if color == "yellow":
                    k.comments = (
                        f"{k.key} {k.quality} is somewhat common in grade {format_grade(grade)}"
                    )
                elif color == "orange":
                    k.comments = f"{k.key} {k.quality} is uncommon in grade {format_grade(grade)}"
                elif color == "red":
                    k.comments = (
                        f"{k.key} {k.quality} is typically not found in grade {format_grade(grade)}"
                    )

        
        # apply key change penalty, if applicable. Max penalty scaled to grade, from .5 to .3.
        MAX_PEN = .5 - (.1 * (grade - .5)) if grade < 3 else None
        key_change_penalty = min(MAX_PEN, MAX_PEN/5 * key_changes) if MAX_PEN else None
        combined_conf_key = (
            sum((k.confidence or 0.0) * (k.exposure or 0.0) for k in key_segments)
            if key_segments else 0.0
        )
        if key_change_penalty:
            combined_conf_key = max(0.0, combined_conf_key - key_change_penalty)

        # --- Note extraction ---
        note_map = extract_note_data(score, grade, key_segments)

        total_exposure = 0.0
        total_conf = 0.0

        for original_part_name, pdata in note_map.items():
            pname = parse_part_name(original_part_name)
            canonical = validate_part_for_range_analysis(pname)

            # If we can’t map the part to an instrument bucket, skip range scoring for it
            if not canonical or canonical not in ranges:
                continue

            if range_grade not in ranges[canonical]:
                continue

            core = ranges[canonical][range_grade]["core"]
            ext = ranges[canonical][range_grade]["extended"]
            total = ranges[canonical]["total_range"]

            # Use the last key segment quality as a fallback
            key_quality = key_segments[-1].quality if key_segments else "major"
            inst_meta = instrument_data.get(canonical)
            brass_partials = inst_meta.partials if inst_meta and inst_meta.type == "brass" else None
            prev_partial = None
            prev_note_name = None

            for note in pdata.get("Note Data", []):
                conf = compute_range_confidence(
                    note,
                    core=core,
                    ext=ext,
                    total=total,
                    target_grade=grade,
                    key_quality=key_quality,
                )
                if conf < 1.0 and not note.comments:
                    label = note.written_pitch or note.sounding_pitch or "note"
                    note.comments["range"] = f"{label} flagged for grade {format_grade(grade)}"
                note.brass_partial = self._get_brass_partial(
                    note.sounding_midi_value, brass_partials
                )
                if prev_partial is not None and note.brass_partial is not None:
                    if (
                        note.brass_partial > prev_partial
                        and prev_partial <= 3
                        and note.brass_partial > 3
                        and (note.brass_partial - prev_partial) > 1
                    ):
                        penalty = self._partial_jump_penalty(grade)
                        conf = max(0.0, conf - penalty)
                        prev_label = prev_note_name or "previous note"
                        curr_label = note.written_pitch or note.sounding_pitch or "current note"
                        note.comments["partial_change"] = (
                            f"partial jump detected from {prev_label} to {curr_label}"
                        )

                if note.brass_partial is not None:
                    prev_partial = note.brass_partial
                    prev_note_name = note.written_pitch or note.sounding_pitch
                exposure = float(note.duration or 0.0)
                note.range_exposure = exposure
                if run_target:
                    note.range_confidence = conf
                total_exposure += exposure
                total_conf += conf * exposure

        avg_range_conf = (total_conf / total_exposure) if total_exposure else 0.0

        if not run_target:
            return (avg_range_conf, combined_conf_key)

        analysis_notes = {"key_data": {"segments": key_segments}, "range_data": note_map}
        if key_change_penalty:
            analysis_notes["key_data"]["key_changes"] = f"Multiple key changes found, {key_changes}."
        summary = {
            "target_grade": grade,
            "overall_range_confidence": avg_range_conf,
            "overall_key_confidence": combined_conf_key,
        }
        return (avg_range_conf, combined_conf_key, analysis_notes, summary)

# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------

def run_key_range(
    score_path: str,
    target_grade: float,
    *,
    score=None,
    score_factory=None,
    progress_cb=None,
    run_observed=True,
    string_only=False,
    analysis_options=None,
):
    from data_processing import derive_observed_grades
    from analyzers.key_range.ranges import load_combined_ranges
    from analyzers.key_range.rules import load_string_key_guidelines, string_key_confidence

    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        string_only = analysis_options.string_only
        grades = analysis_options.observed_grades

    combined_ranges = load_combined_ranges("data/range")
    key_confidence_fn = total_key_confidence
    if string_only:
        string_guidelines = load_string_key_guidelines()
        key_confidence_fn = lambda key, grade, quality: string_key_confidence(
            key, grade, quality, string_guidelines
        )

    if score_factory is None:
        if score is not None:
            score_factory = lambda: deepcopy(score)
        elif score_path is not None:
            score_factory = lambda: converter.parse(score_path)
        else:
            raise ValueError("score_path or score_factory is required")

    base_score = score if score is not None else score_factory()
    sounding_score = base_score.toSoundingPitch()
    key_segments_base = extract_key_segments(base_score, target_grade, sounding_score=sounding_score)
    analyzer = KeyRangeAnalyzer(
        combined_ranges,
        key_segments_base=key_segments_base,
        key_confidence_fn=key_confidence_fn,
    )

    # Confidence curve across grades (fresh score each run)
    def _progress_range(grade, idx, total):
        if progress_cb is not None:
            progress_cb(grade, idx, total, "range")

    def _progress_key(grade, idx, total):
        if progress_cb is not None:
            progress_cb(grade, idx, total, "key")

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda s, g: analyzer.analyze(s, g, run_target=False)[0],
            "progress_cb": _progress_range if progress_cb is not None else None,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade_range, conf_curve_range = derive_observed_grades(**kwargs)
    else:
        observed_grade_range, conf_curve_range = None, {}

    if run_observed:
        kwargs = {
            "score_factory": score_factory,
            "analyze_confidence": lambda s, g: analyzer.analyze(s, g, run_target=False)[1],
            "progress_cb": _progress_key if progress_cb is not None else None,
        }
        if grades is not None:
            kwargs["grades"] = grades
        observed_grade_key, conf_curve_key = derive_observed_grades(**kwargs)
    else:
        observed_grade_key, conf_curve_key = None, {}


    # UI data for target grade
    if score is None:
        score = base_score

    _, _, analysis_notes, summary = analyzer.analyze(score, target_grade, run_target=True)

    return {
        "observed_grade_range": observed_grade_range,
        "confidence_range": conf_curve_range,
        "observed_grade_key": observed_grade_key,
        "confidence_key": conf_curve_key, 
        "analysis_notes": analysis_notes,
        "summary": summary,
    }
