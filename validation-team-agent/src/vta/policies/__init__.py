"""vta.policies — SSoT JSON 로더 (v1 호환).

Phase 5 에서 `harness/` 디렉터리의 정책 파일이 `src/vta/policies/` 하위로
이전될 예정. 현재는 v1 의 `harness/` 경로를 그대로 사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path

# v1 경로 그대로 사용 (Phase 5 에서 이전).
_HARNESS = Path(__file__).resolve().parent.parent.parent.parent / "harness"


def load(name: str) -> dict:
    """정책 SSoT JSON 을 로드한다.

    name 예: 'orchestration_matrix', 'permission_matrix',
    'market_risk_thresholds', 'capital_adequacy_thresholds', ...
    """
    path = _HARNESS / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"policy file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def harness_path() -> Path:
    """v1 harness 디렉터리 경로."""
    return _HARNESS


__all__ = ["load", "harness_path"]
