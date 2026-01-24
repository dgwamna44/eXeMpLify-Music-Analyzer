from music21 import converter, tempo, note, chord
from collections import defaultdict
score = converter.parse(r"C:\Users\dgwam\XMLScan\input_files\test.musicxml")
tempos = list(score.flat.getElementsByClass(tempo.MetronomeMark))
if len(tempos) == 1:
    ratio = 60/tempos[0].number
    duration = divmod(ratio * score.duration.quarterLength, 60)
    minutes = str(int(duration[0])) + '\'' if duration[0] != 0 else ""
    seconds = str(int(duration[1])) + '"'
    print("Duration:", f"{minutes}{seconds}")
trumpet_notes = []
highest_note = 0
lowest_note_name = highest_note_name = ""
for p in score.parts:
    if p.partName == "Trumpet in Bb":
        for n in p.recurse().notes:
            trumpet_notes.append((n.pitch.nameWithOctave, n.pitch.midi, n.duration.quarterLength))

lowest_note_midi, lowest_note_name = min(trumpet_notes, key=lambda x: x[1])[1], min(trumpet_notes, key=lambda x: x[1])[0] 
highest_note_midi, highest_note_name = max(trumpet_notes, key=lambda x: x[1])[1], max(trumpet_notes, key=lambda x: x[1])[0]
trumpet_notes_grouped = defaultdict(float)
for key, _, value in trumpet_notes:
    trumpet_notes_grouped[key] += value
print(lowest_note_name, highest_note_name)

