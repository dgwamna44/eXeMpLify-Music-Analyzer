from music21 import converter, pitch, stream, key, instrument
import pandas as pd
import re, math
from utilities import traffic_light, confidence_curve, parse_part_name, normalize_key_name, validate_for_range_analysis, get_rounded_grade
from data_processing.unpack_tables import unpack_source_grade_table
from app_data import GRADES, MAX_GRADE,GRADE_TO_KEY_TABLE,PUBLISHER_CATALOG_FREQUENCY, GRADE_TO_INSTRUMENTATION_TABLE, PITCH_TO_INDEX, MAJOR_DIATONIC_MAP, MINOR_DIATONIC_MAP
from models import KeyData, PartialNoteData
from pathlib import Path
from functools import reduce
from analyzers.instrument_rules import clarinet_break_allowed, crosses_break

MASTER_PUBLISHER_DF = {} # aggregated range data from all publishers
COMBINED_PUBLISHER_DF = {} # range data with core/extended values
KEY_SOURCES = {}
ANALYSIS_RESULTS = {}


def unpack_range_data(filename, index):
    range_data = pd.read_csv(filename)
    grade_columns = [c for c in range_data if c != "Instrument"]

    for _, row in range_data.iterrows():
        instrument = row["Instrument"]
        if instrument not in MASTER_PUBLISHER_DF:
            MASTER_PUBLISHER_DF[instrument] = {}   
        MASTER_PUBLISHER_DF[instrument][int(index)] = {}
        for grade in grade_columns:
            delimiter = "," if "," in row[grade] else "-" 
            MASTER_PUBLISHER_DF[instrument][int(index)][grade] = [pitch.Pitch(r).midi for r in row[grade].split(delimiter)]  # convert pitch range to midi ranges

def get_allowed_grades_for_key(min_grade):
    return {g for g in GRADES if g >= min_grade}

# unpack GRADE_TO_KEY_TABLE so that each key has a list of valid grades per source.
KEY_SOURCES = unpack_source_grade_table(GRADE_TO_KEY_TABLE, allowed_grades_fn=get_allowed_grades_for_key)
NUM_KEY_PUBLISHERS = len(next(iter(GRADE_TO_KEY_TABLE.values())))

def pub_cumulative_support(key, grade):
    return sum(
        max_grade <= grade
        for max_grade in GRADE_TO_KEY_TABLE[key].values()
    )

def pub_key_confidence(key, grade):
    return confidence_curve(
        evidence=pub_cumulative_support(key, grade),
        normalize=len(GRADE_TO_KEY_TABLE[key]),
        k=2.0,
        max_conf=0.80
    )

def catalog_cumulative_exposure(key, grade):
    exposure = 0.0
    for g, count in PUBLISHER_CATALOG_FREQUENCY[key].items():
        if g <= grade:
            exposure += count
    return exposure

def catalog_key_confidence(key, grade):
    exposure = catalog_cumulative_exposure(key, grade)
    total = sum(PUBLISHER_CATALOG_FREQUENCY[key].values())

    if total == 0:
        return 0.0

    return confidence_curve(
        evidence=exposure,
        normalize=total,
        k=1.2,
        max_conf=0.20
    )

def total_key_confidence(key, grade):
    return (
        pub_key_confidence(key, grade)
        + catalog_key_confidence(key, grade)
    )

def harmonic_tolerance_penalty(grade):
    return .45 - ((grade-1) * .1)

for index, filename in enumerate(Path(r"data\range").iterdir(), start=1):
    unpack_range_data(filename, index)
# ------ GET UNION AND INTERSECTION ACROSS ALL COLLECTIONS AS EXTENDED AND CORE RANGES RESPECTIVELY
for instrument, collections in MASTER_PUBLISHER_DF.items():
    is_range = True
    COMBINED_PUBLISHER_DF[instrument] = {}
    # Collect all grades across all collections
    all_grades = set()
    for c in collections.values():
        all_grades.update(c.keys())
    all_grades = sorted(all_grades)
    max_grade = float(all_grades[-1])
    
    for grade in all_grades:
        lows = []
        highs = []
        discrete_values = []
        core_discrete_values = set()
        extended_discrete_values = set()

        for collection in collections.values():
            if grade in collection:
                if len(collection[grade]) == 2:
                    is_range = True #Treat this as a range, not two discrete notes
                    low, high = collection[grade]
                    lows.append(low)
                    highs.append(high)
                else:
                    is_range = False
                    discrete_values.append(set(collection[grade]))
        
        grade = float(grade)    

        if not is_range: 
            core_discrete_values = reduce(set.union, discrete_values)
            extended_discrete_values = reduce(set.intersection, discrete_values)
            COMBINED_PUBLISHER_DF[instrument][grade] = {
                "core": sorted(list(core_discrete_values)),
                "extended": sorted(list(extended_discrete_values))
            }
        else:
            ext_low = min(lows)
            ext_high = max(highs)
            core_low = max(lows)
            core_high = min(highs)

            COMBINED_PUBLISHER_DF[instrument][grade] = {
                "core": None if core_low > core_high else [core_low, core_high],
                "extended": [ext_low, ext_high]
            }
    # store max range for each instrument as a property of the instrument itself
    max_low = COMBINED_PUBLISHER_DF[instrument][max_grade]['core'][0]
    max_high = COMBINED_PUBLISHER_DF[instrument][max_grade]['extended'][1]
    COMBINED_PUBLISHER_DF[instrument]['total_range'] = [max_low, max_high] 


for instrument in COMBINED_PUBLISHER_DF:
    if 'total_range' in COMBINED_PUBLISHER_DF[instrument]:
        del COMBINED_PUBLISHER_DF[instrument]['total_range']
    sorted_grades = sorted([g for g in COMBINED_PUBLISHER_DF[instrument] if isinstance(g, (int, float))])
    for i in range(1, len(sorted_grades)):
        curr_grade = sorted_grades[i]
        prev_grade = sorted_grades[i-1]
        curr_data = COMBINED_PUBLISHER_DF[instrument][curr_grade]
        prev_data = COMBINED_PUBLISHER_DF[instrument][prev_grade]
        
        # For ranges
        if curr_data['core'] and prev_data['core']:
            curr_data['core'][0] = min(curr_data['core'][0], prev_data['core'][0])
            curr_data['core'][1] = max(curr_data['core'][1], prev_data['core'][1])
        elif prev_data['core']:
            curr_data['core'] = prev_data['core'][:]
        
        curr_data['extended'][0] = min(curr_data['extended'][0], prev_data['extended'][0])
        curr_data['extended'][1] = max(curr_data['extended'][1], prev_data['extended'][1])
        
        # For discrete notes (if applicable)
        if isinstance(curr_data['core'], list) and not isinstance(curr_data['core'][0], int):  # assuming list of midi values
            curr_data['core'] = sorted(list(set(curr_data['core']) | set(prev_data['core'])))
            curr_data['extended'] = sorted(list(set(curr_data['extended']) & set(prev_data['extended'])))
    
    # Recalculate total_range after adjustments
    max_grade = max(sorted_grades)
    max_low = COMBINED_PUBLISHER_DF[instrument][max_grade]['core'][0] if COMBINED_PUBLISHER_DF[instrument][max_grade]['core'] else COMBINED_PUBLISHER_DF[instrument][max_grade]['extended'][0]
    max_high = COMBINED_PUBLISHER_DF[instrument][max_grade]['extended'][1]
    COMBINED_PUBLISHER_DF[instrument]['total_range'] = [max_low, max_high]

def run(
    score_path: str,
    target_grade: float
):
    
    """
    Analyze a score for a given target_grade.
    Returns:
        - analysis_results: detailed note-by-note analysis
        - grade_summary: overall confidence summary for this grade
    """
    from functools import reduce
    from music21 import converter, stream, pitch, key

    global_total_notes = 0
    global_total_confidence = 0.0

    ANALYSIS_RESULTS = {}  # per-call results
    KEY_DATA = []

    score = converter.parse(score_path)
    range_grade = get_rounded_grade(target_grade)

    # ----- Key Analysis -----
    score_sp = score.toSoundingPitch()
    keys = score_sp.parts[0].recurse().getElementsByClass('KeySignature')
    if not keys:
        keys = [key.KeySignature(sharps=None)]

    for ks in keys:
        measure = ks.getContextByClass(stream.Measure).number
        tonic = normalize_key_name(ks.tonicPitchNameWithCase)
        quality = ks.type
        KEY_DATA.append(
            KeyData(
                measure=measure,
                grade=target_grade,
                key=tonic,
                quality=quality,
                pitch_index = PITCH_TO_INDEX[tonic],
                confidence=total_key_confidence(tonic, target_grade)
            )
        )

    # Calculate durations and exposures
    if KEY_DATA:
        total_measures = score.parts[0].measure(-1).number
        KEY_DATA.sort(key=lambda k: k.measure)
        for i in range(len(KEY_DATA)):
            if i < len(KEY_DATA) - 1:
                duration = KEY_DATA[i+1].measure - KEY_DATA[i].measure
            else:
                duration = total_measures - KEY_DATA[i].measure + 1
            exposure = duration / total_measures
            KEY_DATA[i].duration = duration
            KEY_DATA[i].exposure = exposure

        # Apply degradation for key changes
        num_keys = len(KEY_DATA)
        degradation = 1.0
        if target_grade < 2 and num_keys > 1:
            degradation = 0.5
        elif target_grade < 3 and num_keys > 2:
            degradation = 0.5
        for key in KEY_DATA:
            key.confidence *= degradation

    ANALYSIS_RESULTS['Key Data'] = KEY_DATA

    # ----- Part & Note Analysis -----
    for part in score.parts:
        num_notes_in_core_range = 0
        num_notes_in_ext_range = 0
        num_notes_out_of_range_grade = 0
        num_notes_out_of_range = 0
        part_total_notes = 0
        original_part_name = part.partName
        part_name, optional_part = parse_part_name(part.partName)
        part_name = validate_for_range_analysis(part_name)

        ANALYSIS_RESULTS[original_part_name] = {}
        ANALYSIS_RESULTS[original_part_name]["Note Data"] = []

        is_range = len(COMBINED_PUBLISHER_DF[part_name][range_grade]['core']) == 2
        core_range = COMBINED_PUBLISHER_DF[part_name][range_grade]['core']
        ext_range = COMBINED_PUBLISHER_DF[part_name][range_grade]['extended']
        total_range = COMBINED_PUBLISHER_DF[part_name]['total_range']

        starting_index = len(KEY_DATA)-1
        local_key = None

        for measure in part.getElementsByClass(stream.Measure):
            for i in range(starting_index,-1,-1):
                if measure.number >= KEY_DATA[i].measure:
                    local_key = KEY_DATA[i]
                    break

            break_allowed = clarinet_break_allowed(target_grade, original_part_name)

            for n in measure.notesAndRests:
                if not n.isNote:
                    continue

                inst = n.getContextByClass("Instrument")
                interval = inst.transposition if inst else None
                written_pitch = normalize_key_name(n.pitch.nameWithOctave)
                written_midi_value = n.pitch.midi

                if interval:
                    sounding_pitch = normalize_key_name(n.pitch.transpose(interval).nameWithOctave)
                    sounding_midi_value = n.pitch.transpose(interval).midi
                else:
                    sounding_pitch = written_pitch
                    sounding_midi_value = written_midi_value

                note_data = PartialNoteData(
                    measure=n.measureNumber,
                    offset=n.offset,
                    grade=target_grade,
                    instrument=original_part_name,
                    duration=n.quarterLength,
                    written_midi_value=written_midi_value,
                    written_pitch=written_pitch,
                    sounding_midi_value=sounding_midi_value,
                    sounding_pitch=sounding_pitch
                )

                pitch_class = note_data.sounding_midi_value % 12
                note_data.relative_key_index = (pitch_class - local_key.pitch_index) % 12

                if part_name is "unknown" or part_name is None: # don't get range data if not available
                    continue
                # ----- Range Calculation -----
                break_penalty = 0
                if is_range:
                    if break_allowed is not None and crosses_break(note_data.written_pitch):
                        break_penalty = 0.1 if break_allowed else 0.5
                        if not break_allowed:
                            note_data.comments['Pedagogical Constraint'] = f"Crossing the break (written Bb, B in staff) is typically not feasible for {original_part_name} grade {target_grade}."

                    # range confidence
                    if core_range[0] <= note_data.sounding_midi_value <= core_range[1]:
                        num_notes_in_core_range += 1
                        note_data.range_confidence = 1.0
                    elif ext_range[0] <= note_data.sounding_midi_value <= ext_range[1]:
                        num_notes_in_ext_range += 1
                        note_data.range_confidence = 0.6
                    elif total_range[0] <= note_data.sounding_midi_value <= total_range[1]:
                        num_notes_out_of_range_grade += 1
                        note_data.range_confidence = 0.25
                    else:
                        num_notes_out_of_range += 1
                        note_data.range_confidence = 0

                    if break_penalty > 0:
                        note_data.range_confidence = max(0.0, note_data.range_confidence - break_penalty)
                    
                    # apply harmonic tolerance penalty (for accidentals in early music)
                    if local_key.quality == "major":
                        if note_data.relative_key_index not in MAJOR_DIATONIC_MAP:
                            note_data.range_confidence = max(0.0, note_data.range_confidence - harmonic_tolerance_penalty(grade))
                    else:
                        if (note_data.relative_key_index not in MINOR_DIATONIC_MAP) or note_data.relative_key_index != 11:
                            note_data.range_confidence = max(0.0, note_data.range_confidence - harmonic_tolerance_penalty(grade))

                ANALYSIS_RESULTS[original_part_name]['Note Data'].append(note_data)
                part_total_notes += 1
                global_total_notes += 1
                global_total_confidence += note_data.range_confidence

        # store summary percentages per part
        ANALYSIS_RESULTS[original_part_name]["Core Range %"] = round(100*num_notes_in_core_range/part_total_notes,2) if part_total_notes else 0
        ANALYSIS_RESULTS[original_part_name]["Extended Range %"] = round(100*num_notes_in_ext_range/part_total_notes,2) if part_total_notes else 0
        ANALYSIS_RESULTS[original_part_name]["Out of Range %"] = round(100*num_notes_out_of_range_grade/part_total_notes,2) if part_total_notes else 0

    # ----- Per-grade summary -----

    overall_confidence = ( 
    global_total_confidence / global_total_notes
    if global_total_notes else 0
)

    grade_summary = {
        "target_grade": target_grade,
        "total_notes": global_total_notes,
        "overall_range_confidence": overall_confidence
    }

    return ANALYSIS_RESULTS, grade_summary

def derive_observed_grades(score_path: str):
    """
    Run the analyzer across all grades and determine the observed range and key grades
    based on the largest improvement in overall composite confidence and key confidence.
    """

    TOP_CONFIDENCE_THRESHOLD = 0.97

    range_confidences = {}
    key_confidences = {}

    # Run analysis for all grades
    for grade in GRADES:
        analysis_results, summary = run(score_path=score_path, target_grade=grade)
        range_confidences[grade] = summary["overall_range_confidence"]
        key_data = analysis_results.get('Key Data', [])
        key_confidences[grade] = sum(k.confidence * k.exposure for k in key_data) if key_data else 0

    # Compute improvements between consecutive grades for range
    range_improvements = {}
    sorted_grades = sorted(GRADES)
    for i in range(1, len(sorted_grades)):
        prev_grade = sorted_grades[i-1]
        curr_grade = sorted_grades[i]
        range_improvements[curr_grade] = range_confidences[curr_grade] - range_confidences[prev_grade]

    # Compute improvements for key
    key_improvements = {}
    for i in range(1, len(sorted_grades)):
        prev_grade = sorted_grades[i-1]
        curr_grade = sorted_grades[i]
        key_improvements[curr_grade] = key_confidences[curr_grade] - key_confidences[prev_grade]

    # Determine observed range grade
    if min(range_confidences.values()) > TOP_CONFIDENCE_THRESHOLD:
        observed_range_grade = min(GRADES)
    else:
        observed_range_grade = max(range_improvements, key=range_improvements.get)

    # Determine observed key grade
    if min(key_confidences.values()) > TOP_CONFIDENCE_THRESHOLD:
        observed_key_grade = min(GRADES)
    else:
        observed_key_grade = max(key_improvements, key=key_improvements.get)

    return observed_range_grade, observed_key_grade, range_confidences, key_confidences
