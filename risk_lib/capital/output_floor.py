"""Basel III output floor (RBC30).

Aggregate RWA from internal models cannot fall below `floor` × RWA the bank
would have under the full standardised approaches for everything currently
using an internal model.

  RWA_final = max(RWA_internal, floor × RWA_standardised)            (RBC30.1)

Phase-in schedule per RBC30.5: 50% (2023) → 72.5% (2028, fully loaded).
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_lib.references import (
    OUTPUT_FLOOR_FULLY_LOADED, OUTPUT_FLOOR_PHASE_IN,
)


FULLY_LOADED_FLOOR = OUTPUT_FLOOR_FULLY_LOADED
PHASE_IN = dict(OUTPUT_FLOOR_PHASE_IN)


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
