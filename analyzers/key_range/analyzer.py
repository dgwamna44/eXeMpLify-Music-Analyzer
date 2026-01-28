from __future__ import annotations

from analyzers.base import BaseAnalyzer
from analyzers.key_range.extract import extract_key_segments, extract_note_data
from analyzers.key_range.rules import total_key_confidence, compute_range_confidence
from utilities import parse_part_name, validate_part_for_analysis, get_rounded_grade, traffic_light
from music21 import converter


class KeyRangeAnalyzer(BaseAnalyzer):
    """
    Handles BOTH key analysis and range analysis.
    BaseAnalyzer.rules = combined_ranges (instrument -> grade -> {core, extended} + total_range).
    """

    def __init__(self, combined_ranges: dict):
        super().__init__(combined_ranges)  # BaseAnalyzer stores this on self.rules

    # -------------------------------------------------------------
    # CONFIDENCE CURVE (for derive_observed_grades)
    # -------------------------------------------------------------

    def analyze_confidence(self, score, grade: float):
        """
        Returns ONE scalar: combined key + range confidence.
        """
        ranges = self.rules
        range_grade = float(get_rounded_grade(grade))

        # --- Key segments ---
        key_segments = extract_key_segments(score, grade)

        for k in key_segments:
            k.confidence = total_key_confidence(k.key, grade)

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
            canonical = validate_part_for_analysis(pname)

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

        return (0.75 * avg_range_conf) + (0.25 * combined_conf_key)

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
        key_segments = extract_key_segments(score, target_grade)

        for k in key_segments:
            k.confidence = total_key_confidence(k.key, target_grade)
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
            valid_part = validate_part_for_analysis(pname)

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


# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------

def run_key_range(score_path: str, target_grade: float):
    from data_processing import derive_observed_grades
    from analyzers.key_range.ranges import load_combined_ranges

    combined_ranges = load_combined_ranges("data/range") 
    analyzer = KeyRangeAnalyzer(combined_ranges)

    # Confidence curve across grades (fresh score each run)
    observed_grade, conf_curve = derive_observed_grades(
        score_factory=lambda: converter.parse(score_path),
        analyze_confidence=analyzer.analyze_confidence,
    )

    # UI data for target grade
    score = converter.parse(score_path)
    analysis_notes, summary = analyzer.analyze_target(score, target_grade)

    return {
        "observed_grade": observed_grade,
        "confidence": conf_curve,
        "analysis_notes": analysis_notes,
        "summary": summary,
    }
