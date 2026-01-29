from analyzers.articulation.articulation import run_articulation
from analyzers.rhythm import run_rhythm
from analyzers.meter import run_meter
from analyzers.key_range import run_key_range
from analyzers.availability.availability import run_availability
from analyzers.time import run_tempo_duration

if __name__ == "__main__":

    target_grade = 3

    test_files = [r"input_files\test.musicxml",
                  r"input_files\multiple_meter_madness.musicxml",
                  r"input_files\duration_test.musicxml",
                  r"input_files\multiple_instrument_test.musicxml",
                  r"input_files\articulation_test.musicxml",
                  r"input_files\chord_test.musicxml"]
    
    score = test_files[3]

    temp = run_tempo_duration(score,target_grade)
    art = run_articulation(score, target_grade)
    rhy = run_rhythm(score, target_grade)
    met = run_meter(score, target_grade)
    kr = run_key_range(score, target_grade)
    ava = run_availability(score,target_grade)






