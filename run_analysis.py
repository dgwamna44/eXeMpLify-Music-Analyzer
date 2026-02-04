from copy import deepcopy
from time import perf_counter
import argparse
import sys

from music21 import converter

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
    base_score = converter.parse(score_path)
    score_factory = lambda: deepcopy(base_score)

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
    target_only = args.target_only
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
    target_progress = target_progress_bar(len(analyzers))

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
            analysis_options=options,
        )
        collect_partial_notes(results[name], name, reconciler)
        if target_only:
            target_progress(step, name)

    results["reconciled_notes"] = reconciler._notes

    for name, fn, _ in other_analyzers:
        step += 1
        results[name] = fn(
            score_path,
            target_grade,
            score=score_factory(),
            score_factory=score_factory,
            progress_cb=None if target_only else progress_bar(name),
            analysis_options=options,
        )
        if target_only:
            target_progress(step, name)

    ava = results["availability"]
    dyn = results["dynamics"]
    kr = results["key_range"]
    temp = results["tempo_duration"]
    art = results["articulation"]
    rhy = results["rhythm"]
    met = results["meter"]
    
    confidences = {}
    notes = {}
    observed_grades = {}

    if target_only:
        observed_grades = None
    else:
        observed_grades['availability'] = ava.get('observed_grade')
        observed_grades['dynamics'] = dyn.get('observed_grade')
        observed_grades['key'] = kr.get('observed_grade_key')
        observed_grades['range'] = kr.get('observed_grade_range')
        observed_grades['tempo'] = temp.get('observed_grade_tempo')
        observed_grades['duration'] = temp.get('observed_grade_duration')
        observed_grades['articulation'] = art.get('observed_grade')
        observed_grades['rhythm'] = rhy.get('observed_grade')
        observed_grades['meter'] = met.get('observed_grade')


    confidences['availability'] = results['availability']['overall_confidence']
    confidences['dynamics'] = results['dynamics']['overall_confidence']
    confidences['key'] = results['key_range']['summary']['overall_key_confidence']
    confidences['range'] = results['key_range']['summary']['overall_range_confidence']
    confidences['tempo'] = results['tempo_duration']['summary']['overall_tempo_confidence']
    confidences['duration'] = results['tempo_duration']['summary']['overall_duration_confidence']
    confidences['articulation'] = results['articulation']['overall_confidence']
    confidences['rhythm'] = results['rhythm']['overall_confidence']
    confidences['meter'] = results['meter']['overall_confidence']

    notes['availability'] = results['availability'].get('analysis_notes', {})
    notes['dynamics'] = results['dynamics'].get('analysis_notes', {})
    notes['key'] = results['key_range'].get('analysis_notes', {}).get('key_data', {})
    notes['range'] = results['key_range'].get('analysis_notes', {}).get('range_data', {})
    notes['tempo'] = results['tempo_duration']["analysis_notes"].get('tempo_notes', {})
    notes['duration'] = results['tempo_duration']["analysis_notes"].get('duration_notes', {})
    notes['articulation'] = results['articulation'].get('analysis_notes', {})
    notes['rhythm'] = results['rhythm'].get('analysis_notes', {})
    notes['meter'] = results['meter'].get('analysis_notes', {})

    final_result = {
        "observed_grades": observed_grades,
        "confidences": confidences,
        "analysis_notes": notes,
    }