from copy import deepcopy
import math
import threading
from time import perf_counter
import argparse
import sys

from music21 import converter, stream

from analyzers.articulation.articulation import run_articulation
from analyzers.rhythm import run_rhythm
from analyzers.meter import run_meter
from analyzers.key_range import run_key_range
from analyzers.availability.availability import run_availability
from analyzers.tempo_duration import run_tempo_duration
from analyzers.dynamics import run_dynamics
from models import AnalysisOptions
from utilities.note_reconciler import NoteReconciler
from utilities import format_grade
from app_data import FULL_GRADES

_OBSERVED_CACHE: dict[tuple, dict] = {}
_CACHE_LOCK = threading.Lock()

_OBSERVED_KEYS = {
    "availability": ["observed_grade", "confidences"],
    "dynamics": ["observed_grade", "confidences"],
    "key_range": ["observed_grade_range", "confidence_range", "observed_grade_key", "confidence_key"],
    "tempo_duration": [
        "observed_grade",
        "confidences",
        "observed_grade_tempo",
        "confidence_tempo",
        "observed_grade_duration",
        "confidence_duration",
    ],
    "articulation": ["observed_grade", "confidences"],
    "rhythm": ["observed_grade", "confidences"],
    "meter": ["observed_grade", "confidences"],
}


def _cache_key(score_path: str, analysis_options: AnalysisOptions) -> tuple:
    return (score_path, bool(analysis_options.string_only))


def _get_cached_observed(cache_key: tuple, analyzer_name: str):
    with _CACHE_LOCK:
        return _OBSERVED_CACHE.get(cache_key, {}).get(analyzer_name)


def _set_cached_observed(cache_key: tuple, analyzer_name: str, grades, result: dict):
    observed_fields = _OBSERVED_KEYS.get(analyzer_name)
    if not observed_fields:
        return
    entry = {
        "grades": tuple(float(g) for g in grades) if grades else (),
        "data": {k: result.get(k) for k in observed_fields},
    }
    with _CACHE_LOCK:
        bucket = _OBSERVED_CACHE.setdefault(cache_key, {})
        bucket[analyzer_name] = entry


def _should_use_cached(entry, requested_grades):
    if not entry:
        return False
    cached_grades = set(entry.get("grades") or ())
    requested = set(float(g) for g in (requested_grades or ()))
    if not requested:
        return False
    return requested.issubset(cached_grades)


def run_analysis_engine(
    score_path: str,
    target_grade: float,
    *,
    analysis_options: AnalysisOptions,
    progress_cb=None,
):
    target_only = not analysis_options.run_observed
    cache_key = _cache_key(score_path, analysis_options)
    requested_grades = analysis_options.observed_grades if analysis_options.run_observed else None
    base_score = converter.parse(score_path)
    total_measures = len(list(base_score.parts[0].getElementsByClass(stream.Measure)))
    score_factory = lambda: deepcopy(base_score)

    analyzers = [
        ("dynamics", run_dynamics, False),
        ("availability", run_availability, False),
        ("key_range", run_key_range, True),
        ("tempo_duration", run_tempo_duration, False),
        ("articulation", run_articulation, True),
        ("rhythm", run_rhythm, True),
        ("meter", run_meter, False),
    ]
    note_analyzers = [a for a in analyzers if a[2]]
    other_analyzers = [a for a in analyzers if not a[2]]

    def emit(event):
        if progress_cb is not None:
            progress_cb(event)

    def progress_bar(name):
        def _cb(grade, idx, total, label=None):
            emit(
                {
                    "type": "observed",
                    "analyzer": name,
                    "label": label,
                    "grade": grade,
                    "idx": idx,
                    "total": total,
                }
            )

        return _cb

    def analyzer_progress(step, name):
        emit(
            {
                "type": "analyzer",
                "analyzer": name,
                "idx": step,
                "total": len(analyzers),
            }
        )

    def collect_partial_notes(result, name, reconciler: NoteReconciler):
        analysis = result.get("analysis_notes") if result else None
        if not analysis:
            return
        if name == "articulation":
            for pdata in analysis.values():
                for note in pdata.get("articulation_data", []):
                    reconciler.add(note)
        elif name == "rhythm":
            for pdata in analysis.values():
                for note in pdata.get("note_data", []):
                    reconciler.add(note)
        elif name == "key_range":
            range_data = analysis.get("range_data", {})
            for pdata in range_data.values():
                for note in pdata.get("Note Data", []):
                    reconciler.add(note)

    results = {}
    reconciler = NoteReconciler()
    step = 0

    for name, fn, _ in note_analyzers:
        cache_entry = _get_cached_observed(cache_key, name) if not target_only else None
        use_cache = (not target_only) and _should_use_cached(cache_entry, requested_grades)
        options_for_analyzer = AnalysisOptions(
            run_observed=analysis_options.run_observed and not use_cache,
            string_only=analysis_options.string_only,
            observed_grades=analysis_options.observed_grades,
        )
        step += 1
        results[name] = fn(
            score_path,
            target_grade,
            score=score_factory(),
            score_factory=score_factory,
            progress_cb=None if target_only or use_cache else progress_bar(name),
            analysis_options=options_for_analyzer,
        )
        if use_cache and cache_entry:
            results[name].update(cache_entry.get("data") or {})
        elif not target_only and options_for_analyzer.run_observed:
            _set_cached_observed(cache_key, name, requested_grades, results[name])
        collect_partial_notes(results[name], name, reconciler)
        analyzer_progress(step, name)

    results["reconciled_notes"] = reconciler._notes

    for name, fn, _ in other_analyzers:
        cache_entry = _get_cached_observed(cache_key, name) if not target_only else None
        use_cache = (not target_only) and _should_use_cached(cache_entry, requested_grades)
        options_for_analyzer = AnalysisOptions(
            run_observed=analysis_options.run_observed and not use_cache,
            string_only=analysis_options.string_only,
            observed_grades=analysis_options.observed_grades,
        )
        step += 1
        results[name] = fn(
            score_path,
            target_grade,
            score=score_factory(),
            score_factory=score_factory,
            progress_cb=None if target_only or use_cache else progress_bar(name),
            analysis_options=options_for_analyzer,
        )
        if use_cache and cache_entry:
            results[name].update(cache_entry.get("data") or {})
        elif not target_only and options_for_analyzer.run_observed:
            _set_cached_observed(cache_key, name, requested_grades, results[name])
        analyzer_progress(step, name)

    emit({"type": "done"})
    return build_final_result(results, target_only, total_measures, target_grade)


def build_final_result(
    results,
    target_only: bool,
    total_measures: int | None = None,
    target_grade: float | None = None,
):
    def clamp_conf(value):
        if value is None:
            return None
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return None

    observed_grades = None
    observed_grade_overall = None
    observed_grade_overall_range = None
    if not target_only:
        observed_grades = {
            "availability": results.get("availability", {}).get("observed_grade"),
            "dynamics": results.get("dynamics", {}).get("observed_grade"),
            "key": results.get("key_range", {}).get("observed_grade_key"),
            "range": results.get("key_range", {}).get("observed_grade_range"),
            "tempo": results.get("tempo_duration", {}).get("observed_grade_tempo"),
            "duration": results.get("tempo_duration", {}).get("observed_grade_duration"),
            "articulation": results.get("articulation", {}).get("observed_grade"),
            "rhythm": results.get("rhythm", {}).get("observed_grade"),
            "meter": results.get("meter", {}).get("observed_grade"),
        }
        weights = {
            "rhythm": 0.25,
            "range": 0.25,
            "meter": 0.10,
            "key": 0.10,
            "tempo": 0.10,
            "duration": 0.05,
            "availability": 0.05,
            "articulation": 0.05,
            "dynamics": 0.05,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for name, weight in weights.items():
            val = observed_grades.get(name)
            if val is None:
                continue
            try:
                num = float(val)
            except (TypeError, ValueError):
                continue
            weighted_sum += num * weight
            total_weight += weight
        if total_weight > 0:
            overall = weighted_sum / total_weight
            observed_grade_overall = (int(overall * 2 + 0.5)) / 2
            observed_grade_overall_range = (
                math.floor(overall * 2) / 2,
                math.ceil(overall * 2) / 2,
            )

    confidences = {
        "availability": clamp_conf(results.get("availability", {}).get("overall_confidence")),
        "dynamics": clamp_conf(results.get("dynamics", {}).get("overall_confidence")),
        "key": clamp_conf(results.get("key_range", {}).get("summary", {}).get("overall_key_confidence")),
        "range": clamp_conf(results.get("key_range", {}).get("summary", {}).get("overall_range_confidence")),
        "tempo": clamp_conf(results.get("tempo_duration", {}).get("summary", {}).get("overall_tempo_confidence")),
        "duration": clamp_conf(results.get("tempo_duration", {}).get("summary", {}).get("overall_duration_confidence")),
        "articulation": clamp_conf(results.get("articulation", {}).get("overall_confidence")),
        "rhythm": clamp_conf(results.get("rhythm", {}).get("overall_confidence")),
        "meter": clamp_conf(results.get("meter", {}).get("overall_confidence")),
    }

    full_notes = {
        "availability": results.get("availability", {}).get("analysis_notes", {}),
        "dynamics": results.get("dynamics", {}).get("analysis_notes", {}),
        "key": results.get("key_range", {}).get("analysis_notes", {}).get("key_data", {}),
        "range": results.get("key_range", {}).get("analysis_notes", {}).get("range_data", {}),
        "tempo": results.get("tempo_duration", {}).get("analysis_notes", {}).get("tempo_data", {}),
        "duration": results.get("tempo_duration", {}).get("analysis_notes", {}).get("duration_data", {}),
        "articulation": results.get("articulation", {}).get("analysis_notes", {}),
        "rhythm": results.get("rhythm", {}).get("analysis_notes", {}),
        "meter": results.get("meter", {}).get("analysis_notes", {}),
    }
    if confidences.get("availability") is None:
        availability_notes = full_notes.get("availability") or {}
        availability_values = [
            data.get("availability_confidence")
            for data in availability_notes.values()
            if isinstance(data, dict) and data.get("availability_confidence") is not None
        ]
        if availability_values:
            confidences["availability"] = clamp_conf(
                sum(availability_values) / len(availability_values)
            )

    def _filter_note_list(notes_list, attr):
        return [
            n for n in (notes_list or [])
            if (val := getattr(n, attr, None)) is not None and val < 1
        ]

    filtered_notes = {}

    availability = full_notes.get("availability") or {}
    filtered_notes["availability"] = {
        part: data
        for part, data in availability.items()
        if data.get("availability_confidence") is not None
        and data.get("availability_confidence") < 1
    }

    dynamics = full_notes.get("dynamics") or {}
    filtered_dynamics = {}
    for part, data in dynamics.items():
        filtered = [d for d in data.get("dynamics", []) if not d.get("allowed", True)]
        comments = {
            k: v
            for k, v in data.items()
            if k != "dynamics" and isinstance(v, str)
        }
        if filtered or comments:
            filtered_dynamics[part] = {
                "dynamics": filtered,
                "comments": comments,
            }
    filtered_notes["dynamics"] = filtered_dynamics

    key_payload = full_notes.get("key") or {}
    key_segments = key_payload.get("segments", []) if isinstance(key_payload, dict) else []
    filtered_keys = [k for k in key_segments if getattr(k, "comments", None)]
    key_filtered = {"segments": filtered_keys}
    if isinstance(key_payload, dict) and key_payload.get("key_changes"):
        key_filtered["key_changes"] = key_payload["key_changes"]
    filtered_notes["key"] = key_filtered

    range_data = full_notes.get("range") or {}
    filtered_range = {}
    for part, data in range_data.items():
        filtered = _filter_note_list(data.get("Note Data", []), "range_confidence")
        if filtered:
            filtered_range[part] = {"Note Data": filtered}
    filtered_notes["range"] = filtered_range

    tempo_data = full_notes.get("tempo")
    filtered_notes["tempo"] = [
        t for t in (tempo_data or [])
        if (conf := getattr(t, "confidence", None)) is not None and conf < 1
    ]

    duration_data = full_notes.get("duration")
    if duration_data and getattr(duration_data, "confidence", None) is not None:
        filtered_notes["duration"] = duration_data if duration_data.confidence < 1 else None
    else:
        filtered_notes["duration"] = None

    articulation = full_notes.get("articulation") or {}
    filtered_articulation = {}
    for part, data in articulation.items():
        filtered = _filter_note_list(data.get("articulation_data", []), "articulation_confidence")
        if filtered:
            filtered_articulation[part] = {
                "articulation_data": filtered,
                "articulation_confidence": data.get("articulation_confidence"),
            }
    filtered_notes["articulation"] = filtered_articulation

    rhythm = full_notes.get("rhythm") or {}
    filtered_rhythm = {}
    for part, data in rhythm.items():
        filtered = _filter_note_list(data.get("note_data", []), "rhythm_confidence")
        extremes = data.get("extreme_measures", [])
        if filtered or extremes:
            filtered_rhythm[part] = {
                "note_data": filtered,
                "extreme_measures": extremes,
                "rhythm_confidence": data.get("rhythm_confidence"),
            }
    filtered_notes["rhythm"] = filtered_rhythm

    meter_payload = full_notes.get("meter") or {}
    meter_data = meter_payload.get("meter_data", []) if isinstance(meter_payload, dict) else []
    filtered_meter = [
        m for m in meter_data
        if (conf := getattr(m, "confidence", None)) is not None and conf < 1
    ]
    filtered_notes["meter"] = filtered_meter

    if target_grade is not None:
        def _empty_payload(value):
            if value is None:
                return True
            if isinstance(value, str):
                return False
            if isinstance(value, list):
                return len(value) == 0
            if isinstance(value, dict):
                return len(value) == 0
            return False

        no_issue_msg = "No particular {name} issues were detected for grade {grade}"
        grade_str = format_grade(target_grade)

        for name in ("articulation", "dynamics", "range", "rhythm", "tempo"):
            if _empty_payload(filtered_notes.get(name)):
                filtered_notes[name] = no_issue_msg.format(name=name, grade=grade_str)

        key_payload = filtered_notes.get("key")
        key_segments = key_payload.get("segments") if isinstance(key_payload, dict) else None
        has_key_changes = isinstance(key_payload, dict) and bool(key_payload.get("key_changes"))
        if (not key_segments or len(key_segments) == 0) and not has_key_changes:
            filtered_notes["key"] = no_issue_msg.format(name="key", grade=grade_str)

        meter_payload = filtered_notes.get("meter")
        if isinstance(meter_payload, list):
            meter_segments = meter_payload
        elif isinstance(meter_payload, dict):
            meter_segments = meter_payload.get("meter_data")
        else:
            meter_segments = None
        if not meter_segments:
            filtered_notes["meter"] = no_issue_msg.format(name="meter", grade=grade_str)

        if _empty_payload(filtered_notes.get("availability")):
            filtered_notes["availability"] = (
                f"All instruments are valid for grade {grade_str}"
            )

        duration_payload = filtered_notes.get("duration")
        if duration_payload is None:
            filtered_notes["duration"] = (
                f"Duration of piece within acceptable limits for grade {grade_str}"
            )

    duration_data = full_notes.get("duration")
    if isinstance(duration_data, dict):
        duration_str = duration_data.get("length_string")
    else:
        duration_str = getattr(duration_data, "length_string", None)

    return {
        "observed_grades": observed_grades,
        "observed_grade_overall": observed_grade_overall,
        "observed_grade_overall_range": observed_grade_overall_range,
        "confidences": confidences,
        "analysis_notes": full_notes,
        "analysis_notes_filtered": filtered_notes,
        "total_measures": total_measures,
        "duration": duration_str,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-only",
        "--target_only",
        action="store_true",
        help="Skip observed-grade analysis and run target-grade analysis only.",
    )
    parser.add_argument(
        "--strings-only",
        "--strings_only",
        action="store_true",
        help="Use string-preferred key spellings for key analysis.",
    )
    parser.add_argument(
        "--observed-grades",
        default="",
        help="Comma-separated list of grades to evaluate for observed-grade analysis.",
    )
    parser.add_argument(
        "--full-grade-search",
        action="store_true",
        help="Include fractional grades (0.5 steps) in observed-grade analysis.",
    )
    args = parser.parse_args()

    target_grade = 2

    test_files = [r"input_files\test.musicxml",
                  r"input_files\multiple_meter_madness.musicxml",
                  r"input_files\duration_test.musicxml",
                  r"input_files\multiple_instrument_test.musicxml",
                  r"input_files\articulation_test.musicxml",
                  r"input_files\chord_test.musicxml",
                  r"input_files\dynamics_test.musicxml",
                  r"input_files\ijo.musicxml"]
    
    score_path = test_files[-1]

    def progress_bar(name):
        bar_width = 50
        started = perf_counter()
        label_started = {}

        def _cb(grade, idx, total, label=None):
            if label not in label_started:
                label_started[label] = perf_counter()
            elapsed = perf_counter() - label_started[label]
            filled = int((idx / total) * bar_width) if total else 0
            bar = "[" + ("#" * filled) + ("-" * (bar_width - filled)) + "]"
            suffix = f" {label}" if label else ""
            sys.stdout.write(
                f"\r{name}{suffix} {bar} {idx}/{total} (grade {format_grade(grade)}) {elapsed:.1f}s"
            )
            sys.stdout.flush()
            if idx >= total:
                sys.stdout.write("\n")
                sys.stdout.flush()

        return _cb

    def target_progress_bar(total):
        bar_width = 50
        started = perf_counter()

        def _cb(idx, name):
            elapsed = perf_counter() - started
            filled = int((idx / total) * bar_width) if total else 0
            bar = "[" + ("#" * filled) + ("-" * (bar_width - filled)) + "]"
            sys.stdout.write(f"\rtarget_only {bar} {idx}/{total} ({name}) {elapsed:.1f}s")
            sys.stdout.flush()
            if idx >= total:
                sys.stdout.write("\n")
                sys.stdout.flush()

        return _cb

    observed_grades = None
    if args.observed_grades:
        observed_grades = tuple(float(x.strip()) for x in args.observed_grades.split(",") if x.strip())
    elif args.full_grade_search:
        observed_grades = tuple(FULL_GRADES)

    options = AnalysisOptions(
        run_observed=not args.target_only,
        string_only=args.strings_only,
        observed_grades=observed_grades,
    )
    def cli_progress(event):
        if event.get("type") == "observed":
            progress_bar(event["analyzer"])(event["grade"], event["idx"], event["total"], event.get("label"))
        elif event.get("type") == "analyzer":
            target_progress_bar(7)(event["idx"], event["analyzer"])

    final_result = run_analysis_engine(
        score_path,
        target_grade,
        analysis_options=options,
        progress_cb=cli_progress,
    )
    _ = final_result
