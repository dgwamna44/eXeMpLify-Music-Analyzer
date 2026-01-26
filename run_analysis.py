from analyzers.articulation_analysis import run_articulation

if __name__ == "__main__":
    FILE = r"input_files\test.musicxml"
    FILE_2 = r"input_files\multiple_meter_madness.musicxml"
    FILE_3 = r"input_files\duration_test.musicxml"
    FILE_4 = r"input_files\multiple_instrument_test.musicxml"
    FILE_5 = r"input_files\articulation_test.musicxml"

    art = run_articulation(FILE_5, 1)


