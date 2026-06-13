"""보고서 재현가능성 (provenance) 메타데이터.

CRO 보고 기준: 모든 산출 수치는 *재현 가능*하고 *설명 가능* 해야 한다.
본 모듈은 보고서 빌드 시점에 다음을 수집해 표준화된 "Reproducibility" 카드를
생성한다.

- 입력 해시: request dict 의 키-스칼라 부분과 df shape/columns/dtype/체크섬
- 정책 버전: harness/*.json 의 (policy_version | matrix_version | taxonomy_version)
- git: 현재 브랜치, HEAD short rev, dirty 여부
- runtime: Python 버전, 핵심 라이브러리 (pandas/numpy) 버전
- 재실행 명령: --n / --seed / --stress 만으로 결과 결정성을 강제
- HITL 고지

본 카드는 모든 페이지에 동일 footer 로 삽입되어, 어느 페이지를 띄워도
검증자가 즉시 입력·정책·코드의 origin 을 확인할 수 있다.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_HARNESS = Path(__file__).resolve().parent.parent / "harness"

_POLICY_FILES = [
    "orchestration_matrix",
    "basel_risk_taxonomy",
    "capital_adequacy_thresholds",
    "icaap_thresholds",
    "alm_thresholds",
    "liquidity_risk_thresholds",
    "irrbb_thresholds",
    "market_risk_thresholds",
    "operational_risk_thresholds",
    "cva_thresholds",
    "ccr_thresholds",
    "concentration_thresholds",
    "scenario_floors",
    "report_glossary",
    "permission_matrix",
]


def _df_fingerprint(df: Any) -> dict[str, Any]:
    """pandas DataFrame 의 결정론적 지문 (shape/columns/dtype/SHA-256)."""
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        return {"type": type(df).__name__}
    h = hashlib.sha256()
    # column 순서/이름/dtype 도 지문에 반영 — 컬럼 추가/순서 변경 즉시 다른 해시
    h.update(",".join(f"{c}:{df[c].dtype}" for c in df.columns).encode("utf-8"))
    h.update(b"\n")
    # row 단위 raw bytes — to_csv 보다 빠르고 재현 가능
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return {
        "type": "DataFrame",
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "sha256": h.hexdigest(),
    }


def _scalar_fingerprint(value: Any) -> Any:
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_scalar_fingerprint(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _scalar_fingerprint(v) for k, v in sorted(value.items())}
    # pandas DataFrame 등은 별도
    return None


def request_fingerprint(request: Mapping[str, Any]) -> dict[str, Any]:
    """request dict 의 결정론적 지문 — df 는 별도 처리, 스칼라/dict 는 정렬 후 hash."""
    df_print: dict[str, Any] | None = None
    scalar_part: dict[str, Any] = {}
    for k, v in request.items():
        if k == "df":
            df_print = _df_fingerprint(v)
            continue
        coerced = _scalar_fingerprint(v)
        if coerced is not None or v is None:
            scalar_part[str(k)] = coerced
    canonical = json.dumps(scalar_part, ensure_ascii=False, sort_keys=True,
                           default=str)
    return {
        "df": df_print,
        "scalar_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "n_keys": len(request),
    }


def policy_versions(harness_dir: Path | None = None) -> dict[str, str]:
    """SSoT 정책 파일의 (matrix_|policy_|taxonomy_)version 모음."""
    base = harness_dir or _HARNESS
    out: dict[str, str] = {}
    for name in _POLICY_FILES:
        p = base / f"{name}.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            out[name] = "(unreadable)"
            continue
        v: str | None = None
        for key in ("policy_version", "matrix_version", "taxonomy_version",
                    "version"):
            if isinstance(data, dict) and key in data:
                v = str(data[key])
                break
        out[name] = v or "-"
    return out


def git_info() -> dict[str, str]:
    """현재 작업 트리의 git 정보 (실패 시 unknown)."""
    cwd = str(Path(__file__).resolve().parent.parent)
    def _run(*args: str) -> str:
        try:
            res = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                                 text=True, timeout=3, check=False)
            return res.stdout.strip()
        except Exception:
            return ""
    rev = _run("rev-parse", "--short", "HEAD") or "unknown"
    branch = _run("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    dirty = bool(_run("status", "--porcelain"))
    return {"branch": branch, "rev": rev, "dirty": "yes" if dirty else "no"}


def runtime_info() -> dict[str, str]:
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for mod in ("pandas", "numpy", "scipy", "statsmodels", "scikit-learn"):
        try:
            m = __import__(mod.replace("-", "_"))
            info[mod] = getattr(m, "__version__", "?")
        except Exception:
            info[mod] = "(not installed)"
    return info


def build_provenance(
    request: Mapping[str, Any],
    *,
    n: int,
    seed: int,
    stress: bool,
) -> dict[str, Any]:
    """보고서 빌드 시점의 전체 출처 메타데이터."""
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "n": n,
            "seed": seed,
            "stress": bool(stress),
            "fingerprint": request_fingerprint(request),
        },
        "policy_versions": policy_versions(),
        "git": git_info(),
        "runtime": runtime_info(),
        "reproduce": (
            f"python -m tools.report_pack --n {n} --seed {seed} "
            f"{'--stress ' if stress else ''}--out <dir>"
        ),
        "notes": [
            "재현 절차: 위 명령을 동일 git rev 에서 실행하면 동일 입력 해시·동일 "
            "수치를 산출한다 (합성 데이터 결정론).",
            "정책 버전이 변경되면 fingerprint 가 동일해도 판정 결과가 달라질 수 "
            "있다 — policy_versions 표를 함께 확인할 것.",
            "본 산출물은 검증 보조 자료 (DRAFT). 최종 판단은 인간 검증자.",
        ],
    }


__all__ = [
    "build_provenance",
    "request_fingerprint",
    "policy_versions",
    "git_info",
    "runtime_info",
]
