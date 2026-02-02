from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from functools import reduce
import pandas as pd
from music21 import pitch



def unpack_range_data(file_path: Path, publisher_id: int) -> dict:
    """
    Returns: dict[instrument_name][grade(float)] -> list[midi...]
    """
    df = pd.read_csv(file_path)
    if "Instrument" not in df.columns:
        raise ValueError(f"{file_path.name} missing 'Instrument' column. Columns: {list(df.columns)}")

    grade_cols = [c for c in df.columns if c != "Instrument"]
    out: dict[str, dict[float, list[int]]] = {}

    for _, row in df.iterrows():
        instrument = str(row["Instrument"]).strip()
        if not instrument:
            continue

        out.setdefault(instrument, {})

        for grade_col in grade_cols:
            cell = row.get(grade_col)
            if pd.isna(cell):
                continue

            s = str(cell).strip()
            if not s:
                continue

            delim = "," if "," in s else "-"
            midi_vals = [pitch.Pitch(x.strip()).midi for x in s.split(delim)]
            out[instrument][float(grade_col)] = midi_vals

    return out


def reconcile_ranges(master: dict) -> dict:
    """
    master: dict[instrument][publisher_id][grade] -> list[midi...]

    Returns:
      combined[instrument][grade] = {"core": ..., "extended": ...}
      combined[instrument]["total_range"] = [low, high]
    """
    combined: dict = {}

    for instrument, publishers in master.items():
        combined[instrument] = {}

        # collect all grades
        all_grades = sorted({g for pub in publishers.values() for g in pub.keys()})
        if not all_grades:
            continue

        max_grade = float(all_grades[-1])

        for g in all_grades:
            lows, highs = [], []
            discrete_sets = []

            is_range = None

            for pub in publishers.values():
                if g not in pub:
                    continue

                vals = pub[g]
                if len(vals) == 2:
                    is_range = True
                    low, high = vals
                    lows.append(low)
                    highs.append(high)
                else:
                    is_range = False
                    discrete_sets.append(set(vals))

            grade = float(g)

            if is_range is False:
                core = sorted(list(reduce(set.union, discrete_sets))) if discrete_sets else []
                extended = sorted(list(reduce(set.intersection, discrete_sets))) if discrete_sets else []
                combined[instrument][grade] = {"core": core, "extended": extended}
            else:
                ext_low = min(lows)
                ext_high = max(highs)
                core_low = max(lows)
                core_high = min(highs)

                core = None if core_low > core_high else [core_low, core_high]
                combined[instrument][grade] = {"core": core, "extended": [ext_low, ext_high]}

        # total_range from max grade after reconciliation
        max_entry = combined[instrument][max_grade]
        if max_entry["core"] is not None:
            max_low = max_entry["core"][0]
        else:
            max_low = max_entry["extended"][0]
        max_high = max_entry["extended"][1]
        combined[instrument]["total_range"] = [max_low, max_high]

    return combined


@lru_cache(maxsize=4)
def load_combined_ranges(range_dir: str | Path = "data/range", *, file_glob: str = "*.csv") -> dict:

    range_dir = Path(range_dir)
    files = sorted(range_dir.glob(file_glob))
    if not files:
        raise FileNotFoundError(f"No range csv files found in {range_dir.resolve()}")

    master: dict = {}  # instrument -> publisher_id -> grade -> list[midi...]

    for publisher_id, fp in enumerate(files, start=1):
        per_file = unpack_range_data(fp, publisher_id)
        for inst, grades in per_file.items():
            master.setdefault(inst, {})
            master[inst][publisher_id] = grades

    combined = reconcile_ranges(master)

    if not combined:
        raise RuntimeError(
            f"Loaded {len(files)} range files from {range_dir.resolve()} but combined_ranges is empty. "
            "Check CSV schema/cell formatting."
        )

    return combined


@lru_cache(maxsize=2)
def load_string_ranges(range_dir: str | Path = "data/range") -> dict:
    return load_combined_ranges(range_dir, file_glob="string_range*.csv")
