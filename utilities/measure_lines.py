from __future__ import annotations

from music21 import stream


class _ChordNoteProxy:
    def __init__(self, chord, pitch):
        self._chord = chord
        self.pitch = pitch
        self.duration = chord.duration
        self.quarterLength = chord.quarterLength
        self.offset = chord.offset
        self.measureNumber = getattr(chord, "measureNumber", None)
        if self.measureNumber is None:
            measure = chord.getContextByClass(stream.Measure)
            self.measureNumber = measure.number if measure is not None else None
        self.isRest = False
        self.isChord = False
        self.isNote = True
        self.articulations = list(getattr(chord, "articulations", []))

    def getContextByClass(self, cls):
        return self._chord.getContextByClass(cls)


def _collect_events(s, include_rests: bool):
    if include_rests:
        return list(s.notesAndRests)
    return list(s.notes)


def extract_measure_lines(measure: stream.Measure, *, include_rests: bool = True):
    """
    Returns (texture, lines).
    texture: "polyphonic" | "chordal" | "monophonic" | "empty"
    lines: list[list[music21.note.Note | music21.chord.Chord | music21.note.Rest]]
    """
    voices = list(measure.getElementsByClass(stream.Voice))

    if voices:
        lines = []
        for v in voices:
            events = _collect_events(v, include_rests)
            if events:
                lines.append(events)
        return "polyphonic", lines

    events = _collect_events(measure, include_rests)
    if not events:
        events = (
            list(measure.recurse().notesAndRests)
            if include_rests
            else list(measure.recurse().notes)
        )

    if not events:
        return "empty", []

    texture = "chordal" if any(getattr(e, "isChord", False) for e in events) else "monophonic"
    return texture, [events]


def iter_measure_events(
    measure: stream.Measure,
    *,
    include_rests: bool = True,
    expand_chords: bool = False,
):
    _, lines = extract_measure_lines(measure, include_rests=include_rests)
    for events in lines:
        for event in events:
            if expand_chords and getattr(event, "isChord", False):
                for pitch in getattr(event, "pitches", []):
                    yield _ChordNoteProxy(event, pitch)
                continue
            yield event


def iter_measure_lines(measure: stream.Measure, *, include_rests: bool = True):
    _, lines = extract_measure_lines(measure, include_rests=include_rests)
    for index, events in enumerate(lines):
        yield index, events
