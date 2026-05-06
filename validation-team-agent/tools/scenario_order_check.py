"""시나리오 서열 / PD multiplier floor 점검.

스트레스 테스트 / IFRS 9 ECL의 시나리오는 일반적으로
base <= adverse <= severe 의 서열을 가진다.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np


def check_scenario_order(base, adverse, severe) -> dict:
    """base, adverse, severe 각 값의 서열을 점검한다.

    스칼라 또는 동일 길이의 1차원 시퀀스를 허용한다.
    반환 dict 키: passed, violations (위반 인덱스 또는 'scalar')
    """
    arrays = [np.atleast_1d(np.asarray(v, dtype=float)) for v in (base, adverse, severe)]
    shapes = {a.shape for a in arrays}
    if len(shapes) != 1:
        raise ValueError(f"shape mismatch among scenarios: {[a.shape for a in arrays]}")
    b, a, s = arrays
    if np.isnan(b).any() or np.isnan(a).any() or np.isnan(s).any():
        raise ValueError("NaN not allowed in scenario inputs")

    passed_mask = (b <= a) & (a <= s)
    violations = np.where(~passed_mask)[0].tolist()
    return {
        "passed": bool(passed_mask.all()),
        "violations": violations if b.size > 1 else ("scalar" if not passed_mask.all() else []),
        "n": int(b.size),
    }


def check_pd_multiplier_floor(values: Iterable, scenario_type: str) -> dict:
    """시나리오 유형별 PD multiplier floor 충족 여부.

    참고용 default floor:
        base    >= 1.00
        adverse >= 1.20
        severe  >= 1.50
    실제 정책은 호출자가 floors 인자로 직접 지정할 수 있도록
    필요 시 본 함수를 확장하라. 현재 구현은 default floor만 사용한다.
    """
    floors = {"base": 1.00, "adverse": 1.20, "severe": 1.50}
    if scenario_type not in floors:
        raise ValueError(
            f"unknown scenario_type {scenario_type!r}; expected one of {sorted(floors)}"
        )
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("values must not be empty")
    if np.isnan(arr).any():
        raise ValueError("NaN not allowed in values")

    floor = floors[scenario_type]
    pass_mask = arr >= floor
    return {
        "scenario_type": scenario_type,
        "floor": floor,
        "n": int(arr.size),
        "n_pass": int(pass_mask.sum()),
        "n_violation": int((~pass_mask).sum()),
        "violation_indices": np.where(~pass_mask)[0].tolist(),
    }
