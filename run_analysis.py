from copy import deepcopy
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
from app_data import FULL_GRADES


def run_analysis_engine(
    score_path: str,
    target_grade: float,
    *,
    analysis_options: AnalysisOptions,
    progress_cb=None,
):
    target_only = not analysis_options.run_observed
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
        step += 1
        results[name] = fn(
            score_path,
            target_grade,
            score=score_factory(),
            score_factory=score_factory,
            progress_cb=None if target_only else progress_bar(name),
            analysis_options=analysis_options,
        )
        collect_partial_notes(results[name], name, reconciler)
        analyzer_progress(step, name)

    results["reconciled_notes"] = reconciler._notes

    for name, fn, _ in other_analyzers:
        step += 1
        results[name] = fn(
            score_path,
            target_grade,
            score=score_factory(),
            score_factory=score_factory,
            progress_cb=None if target_only else progress_bar(name),
            analysis_options=analysis_options,
        )
        analyzer_progress(step, name)

    emit({"type": "done"})
    return build_final_result(results, target_only, total_measures)


def build_final_result(results, target_only: bool, total_measures: int | None = None):
    def clamp_conf(value):
        if value is None:
            return None
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return None

    observed_grades = None
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

    notes = {
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

    duration_data = notes.get("duration")
    if isinstance(duration_data, dict):
        duration_str = duration_data.get("length_string")
    else:
        duration_str = getattr(duration_data, "length_string", None)

    return {
        "observed_grades": observed_grades,
        "confidences": confidences,
        "analysis_notes": notes,
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
        help="Use string-only key/range guidelines.",
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
                f"\r{name}{suffix} {bar} {idx}/{total} (grade {grade}) {elapsed:.1f}s"
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
