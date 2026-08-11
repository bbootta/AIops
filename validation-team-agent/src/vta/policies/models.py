"""vta.policies.models — Pydantic 정책 로더 (Phase 2, Q3=a).

``load_validated(name)`` 은 SSoT JSON 을 로드하고, 같은 이름의
``<name>.schema.json`` 이 있으면 jsonschema 검증을 수행한 뒤
``Policy`` envelope 으로 반환한다. 정책 JSON 의 의미는 바꾸지 않는다
(v2 비목표: SSoT 의미 변경 금지).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from vta.policies import harness_path, load


class Policy(BaseModel):
    """정책 SSoT envelope. data 는 원본 JSON 그대로."""

    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    schema_path: Path | None = None
    schema_validated: bool = False
    data: dict[str, Any]

    @property
    def version(self) -> str | None:
        """'version' 또는 '*_version' 키 (matrix_version, taxonomy_version 등)."""
        for key in sorted(self.data):
            if key == "version" or key.endswith("_version"):
                return str(self.data[key])
        return None


def load_validated(name: str) -> Policy:
    """정책을 로드하고 schema 가 있으면 검증한다.

    schema 위반 시 jsonschema.ValidationError 를 그대로 올린다 —
    검증 기준 완화 금지 원칙에 따라 비정상 정책은 침묵 통과시키지 않는다.
    """
    data = load(name)
    path = harness_path() / f"{name}.json"
    schema_path = harness_path() / f"{name}.schema.json"
    validated = False
    if schema_path.exists():
        import json

        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(data, schema)
        validated = True
    return Policy(
        name=name,
        path=path,
        schema_path=schema_path if schema_path.exists() else None,
        schema_validated=validated,
        data=data,
    )


__all__ = ["Policy", "load_validated"]
