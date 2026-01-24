from analyzers.key_range_analysis import derive_observed_grades, run as run_range
from analyzers.rhythm_meter_analysis import run as run_rhythm
from analyzers.tempo_duration_analysis import run as run_tempo

if __name__ == "__main__":
    FILE = "input_files\multiple_instrument_test.musicxml"
    FILE_2 = "input_files\multiple_meter_madness.musicxml"
    FILE_3 = "input_files\duration_test.musicxml"

    T_DATA = run_tempo(FILE_3, 1)
    DATA = run_range(FILE, .5)
    DATA_2 = run_rhythm(FILE, .5)
    observed_range_grade, observed_key_grade, range_confidences, key_confidences, range_improvements, key_improvements = derive_observed_grades(FILE)
    print(f"Observed Range Grade: {observed_range_grade}")
    print(f"Observed Key Grade: {observed_key_grade}")
    print("Range Confidences:", range_confidences)
    print("Key Confidences:", key_confidences)
    print("Range Improvements:", range_improvements)
    print("Key Improvements:", key_improvements)
