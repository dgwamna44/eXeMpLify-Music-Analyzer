from app_data import NON_PERCUSSION_INSTRUMENTS, PERCUSSION_INSTRUMENTS, FAMILY_MAP, INST_TO_GRADE_NON_STRING
from models import InstrumentData
from statistics import median

def build_instrument_data():
    data = {}
    for instrument, pattern in NON_PERCUSSION_INSTRUMENTS.items():        
        data[instrument] = InstrumentData(
            instrument=instrument,
            regex=pattern,
            availability=apply_availability(instrument),
            type=FAMILY_MAP.get(instrument, "unknown"),
        )
    for instrument, pattern in PERCUSSION_INSTRUMENTS.items():        
        data[instrument] = InstrumentData(
            instrument=instrument,
            regex=pattern,
            range_analysis=False,
            availability=apply_availability(instrument),
            type="percussion",
        )
    return data

def apply_availability(instrument):
    if instrument in ["violin", "viola", "cello", "bass", "double bass"]:
        return .5
    elif instrument not in INST_TO_GRADE_NON_STRING.keys():
        return None
    else:
        pub_grades = INST_TO_GRADE_NON_STRING[instrument]
        return round(median([pub_grades[i] for i in pub_grades if pub_grades[i] is not None])*2)/2


