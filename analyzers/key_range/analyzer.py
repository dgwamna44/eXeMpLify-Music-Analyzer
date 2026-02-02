from __future__ import annotations

from copy import deepcopy

from analyzers.base import BaseAnalyzer
from analyzers.key_range.extract import extract_key_segments, extract_note_data
from analyzers.key_range.rules import total_key_confidence, compute_range_confidence
from utilities import parse_part_name, validate_part_for_range_analysis, get_rounded_grade, traffic_light
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

    # -------------------------------------------------------------
    # CONFIDENCE CURVE (for derive_observed_grades)
    # -------------------------------------------------------------

    def analyze_confidence(self, score, grade: float):

        ranges = self.rules
        range_grade = float(get_rounded_grade(grade))

        # --- Key segments ---
        key_segments = self._get_key_segments(score, grade)

        for k in key_segments:
            k.confidence = self._key_confidence_fn(k.key, grade, k.quality)

        combined_conf_key = (
            sum((k.confidence or 0.0) * (k.exposure or 0.0) for k in key_segments)
            if key_segments else 0.0
        )

        # --- Note extraction (no confidence yet) ---
        note_map = extract_note_data(score, grade, ranges, key_segments)

        total_notes = 0
        total_conf = 0.0

        # Compute range confidence per note
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

            for note in pdata.get("Note Data", []):
                conf = compute_range_confidence(
                    note,
                    core=core,
                    ext=ext,
                    total=total,
                    target_grade=grade,
                    key_quality=key_quality,
                )
                total_notes += 1
                total_conf += conf

        avg_range_conf = (total_conf / total_notes) if total_notes else 0.0

        return (avg_range_conf, combined_conf_key)

    def analyze_confidence_range(self, score, grade: float) -> float:
        return self.analyze_confidence(score, grade)[0]

    def analyze_confidence_key(self, score, grade: float) -> float:
        return self.analyze_confidence(score, grade)[1]

    # -------------------------------------------------------------
    # TARGET-GRADE ANALYSIS (UI layer)
    # -------------------------------------------------------------

    def analyze_target(self, score, target_grade: float):
        """
        Returns (analysis_results, summary) suitable for UI.
        """
        ranges = self.rules
        range_grade = float(get_rounded_grade(target_grade))

        # --- Key segments ---
        key_segments = self._get_key_segments(score, target_grade)

        for k in key_segments:
            k.confidence = self._key_confidence_fn(k.key, target_grade, k.quality)
            color = traffic_light(k.confidence)
            if color == "yellow":
                k.comments = f"{k.key} {k.quality} is somewhat common in grade {target_grade}"
            elif color == "orange":
                k.comments = f"{k.key} {k.quality} is uncommon in grade {target_grade}"
            elif color == "red":
                k.comments = f"{k.key} {k.quality} is typically not found in grade {target_grade}"


        # --- Note extraction ---
        note_map = extract_note_data(score, target_grade, ranges, key_segments)

        global_total_conf = 0.0
        global_total_notes = 0

        for original_part_name, pdata in note_map.items():
            pname = parse_part_name(original_part_name)
            valid_part = validate_part_for_range_analysis(pname)

            if not valid_part or valid_part not in ranges:
                continue
            if range_grade not in ranges[valid_part]:
                continue

            core = ranges[valid_part][range_grade]["core"]
            ext = ranges[valid_part][range_grade]["extended"]
            total = ranges[valid_part]["total_range"]
            key_quality = key_segments[-1].quality if key_segments else "major"

            for note in pdata.get("Note Data", []):
                conf = compute_range_confidence(
                    note,
                    core=core,
                    ext=ext,
                    total=total,
                    target_grade=target_grade,
                    key_quality=key_quality,
                )
                note.range_confidence = conf
                global_total_conf += conf
                global_total_notes += 1

        overall_range_conf = (global_total_conf / global_total_notes) if global_total_notes else 0.0
        overall_key_conf = (
            sum((k.confidence or 0.0) * (k.exposure or 0.0) for k in key_segments)
            if key_segments else 0.0
        )

        analysis_notes = {"key_data" : key_segments, "range_data" : note_map}
        summary = {
            "target_grade": target_grade,
            "overall_range_confidence": overall_range_conf,
            "overall_key_confidence": overall_key_conf
        }

        return analysis_notes, summary


def analyze_confidence_range(analyzer: KeyRangeAnalyzer, score, grade: float) -> float:
    return analyzer.analyze_confidence_range(score, grade)


def analyze_confidence_key(analyzer: KeyRangeAnalyzer, score, grade: float) -> float:
    return analyzer.analyze_confidence_key(score, grade)


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
    from analyzers.key_range.ranges import load_combined_ranges, load_string_ranges
    from analyzers.key_range.rules import load_string_key_guidelines, string_key_confidence

    grades = None
    if analysis_options is not None:
        run_observed = analysis_options.run_observed
        string_only = analysis_options.string_only
        grades = analysis_options.observed_grades

    combined_ranges = load_string_ranges("data/range") if string_only else load_combined_ranges("data/range")
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
            "analyze_confidence": analyzer.analyze_confidence_range,
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
            "analyze_confidence": analyzer.analyze_confidence_key,
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

    analysis_notes, summary = analyzer.analyze_target(score, target_grade)

    return {
        "observed_grade_range": observed_grade_range,
        "confidence_range": conf_curve_range,
        "observed_grade_key": observed_grade_key,
        "confidence_key": conf_curve_key, 
        "analysis_notes": analysis_notes,
        "summary": summary,
    }
