"""시나리오 서열 / PD multiplier floor 점검.

스트레스 테스트 / IFRS 9 ECL의 시나리오는 일반적으로
base <= adverse <= severe 의 서열을 가진다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

_DEFAULT_FLOORS = {"base": 1.00, "adverse": 1.20, "severe": 1.50}
_FLOORS_PATH = Path(__file__).resolve().parent.parent / "harness" / "scenario_floors.json"


def load_floors(path: str | Path | None = None) -> dict:
    """harness/scenario_floors.json 에서 floor 정책을 로드한다.

    파일이 없거나 키가 부족하면 default를 채워서 반환한다.
    """
    p = Path(path) if path else _FLOORS_PATH
    if not p.exists():
        return dict(_DEFAULT_FLOORS)
    with p.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    floors = dict(_DEFAULT_FLOORS)
    floors.update(cfg.get("floors", {}))
    return floors


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


def check_pd_multiplier_floor(
    values: Iterable,
    scenario_type: str,
    floors: Mapping[str, float] | None = None,
) -> dict:
    """시나리오 유형별 PD multiplier floor 충족 여부.

    floors 인자가 None 이면 ``harness/scenario_floors.json`` 의 정책을 사용한다.
    호출자가 정책을 명시하려면 ``floors={"base":1.0,"adverse":1.25,"severe":1.6}``
    형태로 전달한다. 정책 변경 시 ``harness/change_manifest.json`` 에 기록한다.
    """
    floors_map = dict(load_floors() if floors is None else floors)
    if scenario_type not in floors_map:
        raise ValueError(
            f"unknown scenario_type {scenario_type!r}; expected one of {sorted(floors_map)}"
        )
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("values must not be empty")
    if np.isnan(arr).any():
        raise ValueError("NaN not allowed in values")

    floor = float(floors_map[scenario_type])
    pass_mask = arr >= floor
    return {
        "scenario_type": scenario_type,
        "floor": floor,
        "n": int(arr.size),
        "n_pass": int(pass_mask.sum()),
        "n_violation": int((~pass_mask).sum()),
        "violation_indices": np.where(~pass_mask)[0].tolist(),
        "floors_source": "argument" if floors is not None else "policy_file",
    }
