"""Reproducibility manifest — every CRO-bound number must be traceable.

A `RunManifest` captures everything needed to reproduce a PipelineResult bit
for bit:
  - portfolio fingerprint: SHA-256 over a canonical row order + numeric cast
  - parameter snapshot: seed, hurdle, output_floor, buffers, years_ahead
  - regulatory constants snapshot: every public number from risk_lib.references
  - code provenance: risk_lib.__version__ + git commit (if available) + python
  - environment: os, python, numpy, pandas, scipy versions
  - timing: start/end UTC ISO timestamps + wall-clock seconds
  - result digest: SHA-256 over the canonical (key, value) representation of
    the headline aggregates and validation summary

Two runs with the same manifest input → identical headline_digest. A new
diff function explains which field changed first when two manifests disagree.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- hashing

def _stable_bytes(obj: Any) -> bytes:
    """Deterministic JSON encoding for hashing."""
    return json.dumps(obj, sort_keys=True, default=str,
                      ensure_ascii=False).encode("utf-8")


def sha256_str(obj: Any) -> str:
    return hashlib.sha256(_stable_bytes(obj)).hexdigest()


def portfolio_fingerprint(portfolio: pd.DataFrame) -> dict[str, Any]:
    """Stable SHA-256 over the portfolio + key shape stats.

    Sorts by exposure_id, casts floats to a fixed string format so that NaN/
    dtype quirks don't flip the hash, and includes ``n_rows`` + column list +
    EAD total as a sanity readout.
    """
    df = portfolio.copy()
    if "exposure_id" in df.columns:
        df = df.sort_values("exposure_id", kind="stable")
    # canonical numeric format: 17 sig digits, NaN → "nan"
    canon_rows = []
    for tup in df.itertuples(index=False):
        canon_rows.append("|".join(
            f"{v:.17g}" if isinstance(v, (float, np.floating)) else str(v)
            for v in tup))
    body = "\n".join(canon_rows).encode("utf-8")
    h = hashlib.sha256()
    h.update(b"COLS=" + ",".join(df.columns).encode("utf-8") + b"\n")
    h.update(body)
    return {
        "sha256": h.hexdigest(),
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "columns": list(df.columns),
        "ead_total": float(df["ead"].sum()) if "ead" in df.columns else None,
    }


def _git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL, timeout=2)
        return out.decode().strip()
    except Exception:
        return None


def _env() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


def _regulatory_snapshot() -> dict[str, Any]:
    """Snapshot of every public scalar/dict in risk_lib.references."""
    import risk_lib.references as r
    snap = {}
    for name in dir(r):
        if name.startswith("_"): continue
        v = getattr(r, name)
        if isinstance(v, (int, float, str, bool)):
            snap[name] = v
        elif isinstance(v, dict):
            try:
                snap[name] = dict(v)
            except Exception:
                pass
        elif isinstance(v, tuple) and all(isinstance(x, (int, float)) for x in v):
            snap[name] = list(v)
    return snap


# ---------------------------------------------------------------- manifest

@dataclass
class RunManifest:
    """All inputs + outputs needed to reproduce a run."""
    portfolio: dict[str, Any]                # fingerprint
    parameters: dict[str, Any]               # seed, buffers, hurdle, etc.
    regulatory_constants: dict[str, Any]
    code: dict[str, str | None]              # version, git_commit
    environment: dict[str, str]
    timing: dict[str, str | float]
    headline: dict[str, Any] = field(default_factory=dict)
    headline_digest: str = ""
    validation: dict[str, int] = field(default_factory=dict)
    notes: str = ""

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent,
                          ensure_ascii=False, default=str)

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    @classmethod
    def read(cls, path: str | Path) -> "RunManifest":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def build_manifest(
    *,
    portfolio: pd.DataFrame,
    parameters: dict[str, Any],
    result: Any,
    start_utc: datetime,
    end_utc: datetime,
    notes: str = "",
    adjustment_ledger: Any = None,
) -> RunManifest:
    """Construct a RunManifest from a portfolio, parameters, and the PipelineResult."""
    import risk_lib
    fp = portfolio_fingerprint(portfolio)

    # The effective reference date drives the forecast quarter axis, so a
    # manifest without it cannot reproduce the run — record it always
    # (ISO/IEC 42001 A.7.2 provenance; callers may still override).
    parameters = dict(parameters)
    meta = getattr(result, "meta", None) or {}
    parameters.setdefault("asof", meta.get("asof"))
    # 수동조정 원장 지문 — 조정 포함 산출과 미포함 산출을 digest 수준에서
    # 구분한다. 원장이 없으면 "none"으로 기록해 '조정 없음'과 '미기록'을
    # 구분한다 (DAT-006, AIMS_POLICY §2-2).
    if adjustment_ledger is not None:
        # setdefault를 쓰면 parameters에 이미 키가 있을 때 넘긴 원장이 조용히
        # 무시된다 — 명시적으로 전달된 원장이 항상 이긴다.
        parameters["adjustment_fingerprint"] = adjustment_ledger.fingerprint()
        parameters["adjustments_applied"] = len(adjustment_ledger.applied())
    else:
        parameters.setdefault("adjustment_fingerprint", "none")

    # Headline = every CRO-relevant aggregate, in a fixed key order.
    head = {
        "rwa.sa": float(result.rwa["sa"]),
        "rwa.irb": float(result.rwa["irb"]),
        "rwa.market": float(result.rwa["market"]),
        "rwa.op": float(result.rwa["op"]),
        "rwa.final_total": float(result.rwa["final_total"]),
        "bis.cet1": float(result.bis.cet1_ratio),
        "bis.tier1": float(result.bis.tier1_ratio),
        "bis.total": float(result.bis.total_ratio),
        "leverage": float(result.leverage.leverage_ratio),
        "ecl.ttc_total": float(result.ecl["total"]),
        "ecl.pit_weighted": float(result.macro_ecl.weighted_total),
        "reverse_stress.severity": float(result.reverse_stress.critical_severity),
        "lcr": float(result.alm["lcr"].lcr),
        "nsfr": float(result.alm["nsfr"].nsfr),
        "irrbb.worst_pct_tier1": float(result.alm["irrbb"].worst_pct_tier1),
        "icaap.utilisation": float(result.icaap.utilisation),
        "icaap.grade": result.icaap.grade,
    }
    return RunManifest(
        portfolio=fp,
        parameters=parameters,
        regulatory_constants=_regulatory_snapshot(),
        code={"risk_lib_version": risk_lib.__version__,
              "git_commit": _git_commit()},
        environment=_env(),
        timing={
            "start_utc": start_utc.isoformat(),
            "end_utc": end_utc.isoformat(),
            "elapsed_seconds": (end_utc - start_utc).total_seconds(),
        },
        headline=head,
        headline_digest=sha256_str(head),
        validation=result.validation.summary(),
        notes=notes,
    )


def diff_manifests(a: RunManifest, b: RunManifest) -> dict[str, Any]:
    """Compare two manifests and return only the differing top-level fields.

    Useful as an audit answer to "why does this run not reproduce?": the
    first non-empty key in the returned dict identifies the divergence.
    """
    out = {}
    for k in ("portfolio", "parameters", "regulatory_constants", "code",
              "environment", "headline", "validation"):
        va, vb = getattr(a, k), getattr(b, k)
        if va != vb:
            if isinstance(va, dict) and isinstance(vb, dict):
                keys = sorted(set(va) | set(vb))
                fld = {k2: (va.get(k2), vb.get(k2)) for k2 in keys
                       if va.get(k2) != vb.get(k2)}
                if fld: out[k] = fld
            else:
                out[k] = (va, vb)
    if a.headline_digest != b.headline_digest:
        out["headline_digest"] = (a.headline_digest, b.headline_digest)
    return out


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
