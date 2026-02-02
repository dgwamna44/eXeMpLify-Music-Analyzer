from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class AnalysisOptions:
    run_observed: bool = True
    string_only: bool = False
    observed_grades: Optional[Tuple[float, ...]] = (0.5, 1, 2, 3, 4, 5)
