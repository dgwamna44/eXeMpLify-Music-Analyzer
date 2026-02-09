# extract_key_range.py
from music21 import stream, key, pitch
from models import KeyData, PartialNoteData
from utilities import normalize_key_name, get_rounded_grade, iter_measure_events
from app_data import PITCH_TO_INDEX
from utilities import parse_part_name, validate_part_for_range_analysis


def extract_key_segments(score, target_grade, *, sounding_score=None):
    """
    Extracts key signature changes and computes exposures.
    Returns a list of KeyData objects.
    """
    src = sounding_score if sounding_score is not None else score.toSoundingPitch()
    keys = src.parts[0].recurse().getElementsByClass('KeySignature')
    if not keys:
        keys = [key.KeySignature(sharps=None)]

    key_segments = []
    for ks in keys:
        measure = ks.getContextByClass(stream.Measure).number
        if getattr(ks, "sharps", None) is None:
            tonic = "None"
            quality = "none"
            pitch_index = None
        else:
            tonic = normalize_key_name(ks.tonicPitchNameWithCase).capitalize()
            quality = ks.type
            pitch_index = PITCH_TO_INDEX[tonic]

        key_segments.append(
            KeyData(
                measure=measure,
                grade=target_grade,
                key=tonic,
                quality=quality,
                pitch_index=pitch_index
            )
        )

    # Compute durations + exposure
    if key_segments:
        total_measures = score.parts[0].measure(-1).number
        key_segments.sort(key=lambda k: k.measure)

        for i in range(len(key_segments)):
            if i < len(key_segments) - 1:
                duration = key_segments[i+1].measure - key_segments[i].measure
            else:
                duration = total_measures - key_segments[i].measure + 1

            key_segments[i].duration = duration
            key_segments[i].exposure = duration / total_measures

    return key_segments


def extract_note_data(score, target_grade, combined_ranges, key_segments):
    analysis_results = {}
    range_grade = get_rounded_grade(target_grade)

    for part in score.parts:
        original_name = part.partName or "Unknown Part"
        analysis_results[original_name] = {"Note Data": []}

        parsed = parse_part_name(original_name)
        valid_part = validate_part_for_range_analysis(parsed)

        has_range_rules = (
            valid_part
            and valid_part != "unknown"
            and valid_part in combined_ranges
            and range_grade in combined_ranges[valid_part]
        )

        if has_range_rules:
            core_range  = combined_ranges[valid_part][range_grade]["core"]
            ext_range   = combined_ranges[valid_part][range_grade]["extended"]
            total_range = combined_ranges[valid_part]["total_range"]
        else:
            core_range = ext_range = total_range = None

        for measure in part.getElementsByClass(stream.Measure):
            local_key = None
            for ks in reversed(key_segments):
                if measure.number >= ks.measure:
                    local_key = ks
                    break

            for n in iter_measure_events(measure):
                if not n.isNote:
                    continue

                inst = n.getContextByClass("Instrument")
                interval = inst.transposition if inst else None

                written_pitch = normalize_key_name(n.pitch.nameWithOctave)
                written_midi = n.pitch.midi

                if interval:
                    sounding_pitch = normalize_key_name(n.pitch.transpose(interval).nameWithOctave)
                    sounding_midi = n.pitch.transpose(interval).midi
                else:
                    sounding_pitch = written_pitch
                    sounding_midi = written_midi

                data = PartialNoteData(
                    measure=n.measureNumber,
                    offset=n.offset,
                    grade=target_grade,
                    instrument=original_name,
                    duration=n.quarterLength,
                    written_pitch=written_pitch,
                    written_midi_value=written_midi,
                    sounding_pitch=sounding_pitch,
                    sounding_midi_value=sounding_midi,
                )

                if local_key is not None and local_key.key != "None" and local_key.pitch_index is not None:
                    pitch_class = sounding_midi % 12
                    data.relative_key_index = (pitch_class - local_key.pitch_index) % 12

                # Range application is optional
                if has_range_rules:
                    # TODO: apply your range confidence buckets here
                    pass
                else:
                    data.range_confidence = None
                    data.comments["Range"] = f"No range dataset for '{original_name}' (normalized: '{valid_part}')"

                analysis_results[original_name]["Note Data"].append(data)

    return analysis_results
