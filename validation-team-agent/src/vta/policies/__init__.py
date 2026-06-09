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


def list_policies() -> list[tuple[str, Path]]:
    """SSoT JSON 정책 파일을 (name, path) 쌍으로 반환한다.

    schema 파일은 제외 — 정책 자체의 인덱스만 노출.
    """
    out: list[tuple[str, Path]] = []
    for p in sorted(_HARNESS.glob("*.json")):
        if p.name.endswith(".schema.json"):
            continue
        if p.name == "change_manifest.json":
            # 매니페스트는 별도 도구 (tools.manifest) 로 다룬다.
            continue
        out.append((p.stem, p))
    return out


def list_schemas() -> list[tuple[str, Path]]:
    """JSON schema 파일 인덱스."""
    out: list[tuple[str, Path]] = []
    for p in sorted(_HARNESS.glob("*.schema.json")):
        out.append((p.name.replace(".schema.json", ""), p))
    return out


__all__ = ["load", "harness_path", "list_policies", "list_schemas"]
