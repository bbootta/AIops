"""Basel III output floor (CRE / finalisation).

Aggregate RWA computed with internal models must be at least `floor` times the
RWA computed under the full standardised approaches.

  RWA_final = max(RWA_internal, floor * RWA_standardised)

Phase-in: 50% (2023) → 72.5% (2028, fully loaded).  Default = 0.725.
"""

from __future__ import annotations

from dataclasses import dataclass


FULLY_LOADED_FLOOR = 0.725

PHASE_IN = {
    2023: 0.50,
    2024: 0.55,
    2025: 0.60,
    2026: 0.65,
    2027: 0.70,
    2028: 0.725,
}


@dataclass
class OutputFloorResult:
    rwa_internal: float
    rwa_standardised: float
    floor: float
    floor_amount: float       # floor * standardised
    rwa_final: float
    add_on: float             # rwa_final - rwa_internal
    is_binding: bool


def apply_output_floor(
    rwa_internal: float,
    rwa_standardised: float,
    floor: float = FULLY_LOADED_FLOOR,
) -> OutputFloorResult:
    if rwa_internal < 0 or rwa_standardised < 0:
        raise ValueError("RWA inputs must be non-negative")
    if not 0 < floor <= 1:
        raise ValueError("floor must be in (0, 1]")
    floor_amount = floor * rwa_standardised
    rwa_final = max(rwa_internal, floor_amount)
    return OutputFloorResult(
        rwa_internal=rwa_internal,
        rwa_standardised=rwa_standardised,
        floor=floor,
        floor_amount=floor_amount,
        rwa_final=rwa_final,
        add_on=rwa_final - rwa_internal,
        is_binding=floor_amount > rwa_internal,
    )
