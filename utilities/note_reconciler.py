from dataclasses import fields
from models import PartialNoteData

class NoteReconciler:
    def __init__(self):
        self._notes = {}

    def _key(self, n: PartialNoteData):
        return (
            n.instrument,
            n.measure,
            round(n.offset, 5),
            n.written_midi_value
        )

    def add(self, n: PartialNoteData):
        key = self._key(n)
        if key not in self._notes:
            self._notes[key] = n
        else:
            self.merge(self._notes[key], n)

    def merge(self, base: PartialNoteData, incoming: PartialNoteData):
        for f in base.__dataclass_fields__:
            val = getattr(incoming, f)
            if val is not None:
                setattr(base, f, val)
        base.comments.update(incoming.comments)