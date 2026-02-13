from dataclasses import fields
from models import PartialNoteData

class NoteReconciler:
    def __init__(self):
        self._notes = {}

    def _key(self, n: PartialNoteData):
        chord_token = None
        if n.is_chord and n.chord_size:
            chord_token = (n.chord_size, n.chord_index)
        return (
            n.instrument,
            n.measure,
            round(n.offset, 5),
            n.written_midi_value,
            chord_token,
        )

    def add(self, n: PartialNoteData):
        key = self._key(n)
        if key not in self._notes:
            self._notes[key] = n
        else:
            self.merge(self._notes[key], n)

    def merge(self, base: PartialNoteData, incoming: PartialNoteData):
        for f in base.__dataclass_fields__:
            if f == "comments":
                continue
            val = getattr(incoming, f)
            if val is not None:
                setattr(base, f, val)
        if incoming.comments:
            base.comments.update(incoming.comments)
