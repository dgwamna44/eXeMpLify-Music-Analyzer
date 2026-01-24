from music21 import converter, stream, meter
from collections import defaultdict
from app_data.rhythms import RHYTHM_TOKEN_MAP
from models import PartialNoteData, MeterData

ANALYSIS_NOTES = {}
partial_notes = []
music21_notes = []
# =========================
# Rhythm helpers
# =========================

def get_rhythm_token(n):
    base = RHYTHM_TOKEN_MAP[n.duration.type]["token"]
    return base + ("d" * n.duration.dots)

def annotate_tuplets(notes: list[PartialNoteData], music21_notes):
    """
    Mutates PartialNoteData objects to add tuplet info.
    Assumes notes and music21_notes are aligned 1:1
    """
    current_tuplet_id = 0
    active_tuplet = None
    tuplet_index = 0

    for pd, n in zip(notes, music21_notes):

        if not n.duration.tuplets:
            active_tuplet = None
            tuplet_index = 0
            continue

        t = n.duration.tuplets[0]

        # Start new tuplet group
        if active_tuplet is None or t is not active_tuplet:
            current_tuplet_id += 1
            active_tuplet = t
            tuplet_index = 0

        pd.tuplet_id = current_tuplet_id
        pd.tuplet_index = tuplet_index
        pd.tuplet_actual = t.numberNotesActual
        pd.tuplet_normal = t.numberNotesNormal

        tuplet_index += 1



# =========================
# Beat grouping (VIEW layer)
# =========================

def group_notes_by_beat(notes: list[PartialNoteData]):
    groups = defaultdict(list)
    for n in notes:
        groups[(n.measure, n.beat_index)].append(n)
    return groups


# =========================
# Analyzer entry point
# =========================

def run(score_path: str, target_grade: float):
    score = converter.parse(score_path)

    # -------------------------
    # Meter data
    # -------------------------
    meter_data: list[MeterData] = []
    meters = score.parts[0].recurse().getElementsByClass(meter.TimeSignature)

    if not meters:
        meters = [meter.TimeSignature("4/4")]

    for ts in meters:
        meter_data.append(
            MeterData(
                measure=ts.getContextByClass(stream.Measure).number,
                time_signature=ts.ratioString,
                grade=target_grade
            )
        )

    # -------------------------
    # Note extraction
    # -------------------------
    all_notes: list[PartialNoteData] = []

    for part in score.parts:
        part_name = part.partName
        current_ts = None
        ANALYSIS_NOTES[part_name] = {}
        ANALYSIS_NOTES[part_name]['Note Data'] = []

        for m in part.getElementsByClass(stream.Measure):
            ts = m.getContextByClass(meter.TimeSignature)
            if ts is not None:
                current_ts = ts
            if current_ts is None: # this will handle any pickup measures that won't have a time signature
                continue

            beat_length = current_ts.beatDuration.quarterLength

            for n in m.notesAndRests:
                beat_index = int(n.offset // beat_length)
                beat_offset = n.offset % beat_length

                p = PartialNoteData(
                    measure=m.number,
                    offset=n.offset,
                    grade=target_grade,
                    instrument=part_name,
                    duration=n.duration.quarterLength,
                    written_midi_value=None,
                    written_pitch=None,
                    sounding_midi_value=None,
                    sounding_pitch=None,
                    rhythm_token=get_rhythm_token(n) + ("r" if n.isRest else ""),
                    beat_index= beat_index,
                    beat_offset= beat_offset,
                    beat_unit= beat_length
                )

                partial_notes.append(p)
                music21_notes.append(n)

                annotate_tuplets(partial_notes, music21_notes)
                all_notes.extend(partial_notes)

        ANALYSIS_NOTES[part_name]['Note Data'] = all_notes
    return ANALYSIS_NOTES