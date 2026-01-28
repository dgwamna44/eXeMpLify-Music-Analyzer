from analyzers.articulation import run_articulation
from analyzers.rhythm import run_rhythm
from analyzers.meter import run_meter
from analyzers.key_range import run_key_range
from analyzers.availability import run_availability

if __name__ == "__main__":

    test_files = [r"input_files\test.musicxml",
                  r"input_files\multiple_meter_madness.musicxml",
                  r"input_files\duration_test.musicxml",
                  r"input_files\multiple_instrument_test.musicxml",
                  r"input_files\articulation_test.musicxml",
                  r"input_files\chord_test.musicxml"]

    art = run_articulation(test_files[3], 1)
    rhy = run_rhythm(test_files[3], 1)
    met = run_meter(test_files[3], .5)
    kr = run_key_range(test_files[3], 2)
    ava = run_availability(test_files[3],2)





