"""Internal master rating scale (PD calibrated)."""

from __future__ import annotations

import bisect
from dataclasses import dataclass


@dataclass(frozen=True)
class RatingGrade:
    grade: str
    pd_lower: float   # inclusive
    pd_upper: float   # exclusive (last grade upper = 1.0 inclusive)
    pd_midpoint: float
    sa_bucket: str    # mapping to external SA bucket


# 17-grade master scale similar to Korean bank internal scales.
# pd_lower < pd <= pd_upper, midpoint used as calibration anchor.
DEFAULT_MASTER_SCALE: list[RatingGrade] = [
    RatingGrade("AAA",  0.0000, 0.0003, 0.00015, "AAA-AA"),
    RatingGrade("AA+",  0.0003, 0.0005, 0.00040, "AAA-AA"),
    RatingGrade("AA",   0.0005, 0.0008, 0.00065, "AAA-AA"),
    RatingGrade("AA-",  0.0008, 0.0012, 0.00100, "AAA-AA"),
    RatingGrade("A+",   0.0012, 0.0020, 0.00160, "A"),
    RatingGrade("A",    0.0020, 0.0035, 0.00270, "A"),
    RatingGrade("A-",   0.0035, 0.0060, 0.00470, "A"),
    RatingGrade("BBB+", 0.0060, 0.0100, 0.00800, "BBB"),
    RatingGrade("BBB",  0.0100, 0.0180, 0.01400, "BBB"),
    RatingGrade("BBB-", 0.0180, 0.0300, 0.02400, "BBB"),
    RatingGrade("BB+",  0.0300, 0.0500, 0.04000, "BB"),
    RatingGrade("BB",   0.0500, 0.0850, 0.06700, "BB"),
    RatingGrade("BB-",  0.0850, 0.1400, 0.11200, "BB"),
    RatingGrade("B+",   0.1400, 0.2200, 0.18000, "B"),
    RatingGrade("B",    0.2200, 0.3500, 0.28500, "B"),
    RatingGrade("B-",   0.3500, 0.5500, 0.45000, "B"),
    RatingGrade("CCC+", 0.5500, 1.0001, 0.75000, "CCC-"),
]


def pd_to_rating(
    pd_value: float,
    scale: list[RatingGrade] = DEFAULT_MASTER_SCALE,
) -> RatingGrade:
    """Map a PD to an internal grade."""
    if pd_value < 0 or pd_value > 1:
        raise ValueError(f"pd out of range: {pd_value}")
    uppers = [g.pd_upper for g in scale]
    idx = bisect.bisect_left(uppers, pd_value)
    if idx >= len(scale):
        idx = len(scale) - 1
    return scale[idx]


def rating_to_pd_midpoint(
    grade: str,
    scale: list[RatingGrade] = DEFAULT_MASTER_SCALE,
) -> float:
    """Recover calibrated PD from grade label."""
    for g in scale:
        if g.grade == grade:
            return g.pd_midpoint
    raise KeyError(f"unknown grade: {grade}")
