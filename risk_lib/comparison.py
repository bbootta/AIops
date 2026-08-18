"""Multi-snapshot comparison — quarter-over-quarter / year-over-year analysis.

Two consumer patterns:
  - quick:   pass two PipelineResults, get the bridge + delta table
  - history: pass N manifests OR results, get a tidy time-indexed frame and
             charts (line + heatmap) of every headline KPI through time

Used by:
  - risk_lib.cli compare
  - new ops page 26_comparison.html

NOTE: 다기간 축적/추세 기능(원장 persistence, QoQ/YoY, trend flags)은
`risk_lib.timeseries_ledger`가 담당한다 — 신규 시계열 기능은 그쪽에 추가하고,
이 모듈은 2-스냅샷 bridge와 ops 페이지 26 전용으로 유지한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from risk_lib.attribution import capital_bridge, rwa_bridge, ecl_bridge, lcr_bridge


# ---------------------------------------------------------------- two-snapshot

@dataclass
class SnapshotDiff:
    a_label: str
    b_label: str
    bis_change_pp: float
    rwa_change_krw: float
    ecl_change_krw: float
    lcr_change_pp: float
    nsfr_change_pp: float
    capital_bridge: Any
    rwa_bridge: Any
    ecl_bridge: Any
    lcr_bridge: Any


def compare_results(a, b, *, a_label: str = "이전", b_label: str = "현재") -> SnapshotDiff:
    return SnapshotDiff(
        a_label=a_label, b_label=b_label,
        bis_change_pp=(b.bis.cet1_ratio - a.bis.cet1_ratio) * 100,
        rwa_change_krw=b.rwa["final_total"] - a.rwa["final_total"],
        ecl_change_krw=float(b.ecl["total"]) - float(a.ecl["total"]),
        lcr_change_pp=(b.alm["lcr"].lcr - a.alm["lcr"].lcr) * 100,
        nsfr_change_pp=(b.alm["nsfr"].nsfr - a.alm["nsfr"].nsfr) * 100,
        capital_bridge=capital_bridge(a, b),
        rwa_bridge=rwa_bridge(a, b),
        ecl_bridge=ecl_bridge(a, b),
        lcr_bridge=lcr_bridge(a, b),
    )


# ---------------------------------------------------------------- N-snapshot history

@dataclass
class HistoryRow:
    label: str
    asof: str
    cet1: float
    tier1: float
    total: float
    leverage: float
    rwa_final: float
    ecl_ttc: float
    ecl_pit_weighted: float
    lcr: float
    nsfr: float
    irrbb_pct_tier1: float
    icaap_util: float
    raf_worst: str
    validation_summary: dict[str, int]
    manifest_digest: str


def history_from_manifests(paths: list[Path | str]) -> pd.DataFrame:
    """Load N manifest.json files and stack their headline numbers."""
    rows = []
    for p in paths:
        p = Path(p)
        m = json.loads(p.read_text(encoding="utf-8"))
        h = m["headline"]
        rows.append({
            "label": p.parent.name or p.stem,
            "asof": m["timing"]["end_utc"][:10],
            "cet1": h.get("bis.cet1"),
            "tier1": h.get("bis.tier1"),
            "total": h.get("bis.total"),
            "leverage": h.get("leverage"),
            "rwa_final": h.get("rwa.final_total"),
            "ecl_ttc": h.get("ecl.ttc_total"),
            "ecl_pit_weighted": h.get("ecl.pit_weighted"),
            "lcr": h.get("lcr"),
            "nsfr": h.get("nsfr"),
            "irrbb_pct_tier1": h.get("irrbb.worst_pct_tier1"),
            "icaap_util": h.get("icaap.utilisation"),
            "icaap_grade": h.get("icaap.grade"),
            "manifest_digest": m["headline_digest"],
            "validation": m["validation"],
        })
    return pd.DataFrame(rows).sort_values("asof").reset_index(drop=True)


def history_from_results(results: list[tuple[str, Any]]) -> pd.DataFrame:
    """Build history from labelled (label, result) tuples."""
    rows = []
    for label, r in results:
        rows.append({
            "label": label,
            "asof": r.meta.get("asof", ""),
            "cet1": r.bis.cet1_ratio,
            "tier1": r.bis.tier1_ratio,
            "total": r.bis.total_ratio,
            "leverage": r.leverage.leverage_ratio,
            "rwa_final": r.rwa["final_total"],
            "ecl_ttc": float(r.ecl["total"]),
            "ecl_pit_weighted": r.macro_ecl.weighted_total,
            "lcr": r.alm["lcr"].lcr,
            "nsfr": r.alm["nsfr"].nsfr,
            "irrbb_pct_tier1": r.alm["irrbb"].worst_pct_tier1,
            "icaap_util": r.icaap.utilisation,
            "icaap_grade": r.icaap.grade,
            "raf_worst": r.raf.worst() if r.raf else "",
            "validation": r.validation.summary(),
        })
    return pd.DataFrame(rows).sort_values("asof").reset_index(drop=True)


def qoq_yoy_change(history: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Compute QoQ and YoY change for one metric column."""
    df = history.copy()
    df["qoq"] = df[metric].diff()
    df["yoy"] = df[metric].diff(4)
    return df[["label", "asof", metric, "qoq", "yoy"]]
