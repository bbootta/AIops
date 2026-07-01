"""Time-series ledger — accumulate manifests across periods for trend reporting.

A Top-IB risk function does not look at a single snapshot; it tracks every
headline metric through time and flags trends, QoQ/YoY drift, and consecutive-
period breaches. This module:

  - `TimeSeriesLedger`: append-only store of period snapshots (each keyed by a
    period label like "2025Q3" and carrying the manifest headline dict).
  - persistence: JSON on disk so quarterly runs accumulate.
  - `to_frame()`: tidy time-indexed frame of every headline metric.
  - `qoq_yoy()`: quarter-over-quarter and year-over-year deltas per metric.
  - `trend_flags()`: per-metric direction (개선/악화/보합) + consecutive-breach
    counter against a regulatory floor.
  - `build_timeseries_report(...)`: HTML trend deep-dive page.

Reproducibility: each period stores its manifest `headline_digest`, so a trend
line is auditable back to the run that produced each point.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# metric_id -> (label, regulatory floor or None, direction "min"/"max", fmt)
HEADLINE_SPEC: dict[str, tuple[str, float | None, str, str]] = {
    "bis.cet1":               ("CET1 비율",         0.08,  "min", "pct"),
    "bis.tier1":              ("Tier1 비율",        0.095, "min", "pct"),
    "bis.total":              ("총자본 비율",       0.115, "min", "pct"),
    "leverage":               ("레버리지 비율",     0.03,  "min", "pct"),
    "lcr":                    ("LCR",              1.00,  "min", "pct"),
    "nsfr":                   ("NSFR",             1.00,  "min", "pct"),
    "irrbb.worst_pct_tier1":  ("IRRBB ΔEVE/Tier1", 0.15,  "max", "pct"),
    "icaap.utilisation":      ("ICAAP 사용률",      1.00,  "max", "pct"),
    "rwa.final_total":        ("최종 RWA",          None,  "n",   "won"),
    "ecl.ttc_total":          ("TTC ECL",           None,  "n",   "won"),
    "ecl.pit_weighted":       ("PIT 가중 ECL",       None,  "n",   "won"),
    "reverse_stress.severity":("역스 임계 심도",     None,  "n",   "num"),
}


@dataclass
class PeriodSnapshot:
    period: str                       # "2025Q3"
    asof: str                         # ISO date
    headline: dict[str, Any]          # metric_id -> value
    headline_digest: str = ""
    seed: int = 0
    validation_summary: dict[str, int] = field(default_factory=dict)


@dataclass
class TimeSeriesLedger:
    snapshots: list[PeriodSnapshot] = field(default_factory=list)

    # ---- mutation ----
    def add(self, snap: PeriodSnapshot) -> None:
        # replace if same period exists (idempotent quarterly re-run)
        self.snapshots = [s for s in self.snapshots if s.period != snap.period]
        self.snapshots.append(snap)
        self.snapshots.sort(key=lambda s: s.period)

    def add_from_manifest(self, period: str, manifest) -> None:
        self.add(PeriodSnapshot(
            period=period,
            asof=manifest.timing.get("end_utc", "")[:10],
            headline=dict(manifest.headline),
            headline_digest=manifest.headline_digest,
            seed=int(manifest.parameters.get("seed", 0)),
            validation_summary=dict(manifest.validation),
        ))

    # ---- persistence ----
    def to_json(self) -> str:
        return json.dumps([asdict(s) for s in self.snapshots],
                          indent=2, ensure_ascii=False, default=str)

    def save(self, path) -> str:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return str(p.resolve())

    @classmethod
    def load(cls, path) -> "TimeSeriesLedger":
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(snapshots=[PeriodSnapshot(**d) for d in data])

    # ---- analytics ----
    def to_frame(self) -> pd.DataFrame:
        rows = []
        for s in self.snapshots:
            row = {"period": s.period, "asof": s.asof,
                   "digest": s.headline_digest[:12]}
            for mid in HEADLINE_SPEC:
                row[mid] = s.headline.get(mid, np.nan)
            rows.append(row)
        return pd.DataFrame(rows)

    def qoq_yoy(self, metric_id: str) -> pd.DataFrame:
        df = self.to_frame()[["period", metric_id]].copy()
        df["qoq"] = df[metric_id].diff()
        df["yoy"] = df[metric_id].diff(4)
        return df

    def trend_flags(self) -> pd.DataFrame:
        """Per-metric latest value, QoQ direction, and consecutive breach count."""
        df = self.to_frame()
        rows = []
        for mid, (label, floor, direction, fmt) in HEADLINE_SPEC.items():
            series = df[mid].dropna()
            if series.empty:
                continue
            latest = float(series.iloc[-1])
            qoq = float(series.diff().iloc[-1]) if len(series) > 1 else 0.0
            # trend label (direction-aware)
            if abs(qoq) < 1e-9:
                trend = "보합"
            elif direction == "min":
                trend = "개선" if qoq > 0 else "악화"
            elif direction == "max":
                trend = "개선" if qoq < 0 else "악화"
            else:
                trend = "증가" if qoq > 0 else "감소"
            # consecutive breach counter
            breaches = 0
            if floor is not None:
                for v in reversed(series.tolist()):
                    breach = (v < floor) if direction == "min" else (v > floor)
                    if breach:
                        breaches += 1
                    else:
                        break
            rows.append({
                "metric": mid, "label": label, "latest": latest,
                "qoq": qoq, "floor": floor, "direction": direction,
                "fmt": fmt, "trend": trend,
                "consecutive_breaches": breaches,
            })
        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# HTML trend report
# ---------------------------------------------------------------------------

def build_timeseries_report(ledger: "TimeSeriesLedger", out_path,
                            *, title: str = "리스크 지표 시계열 추이") -> str:
    """Standalone HTML trend deep-dive across accumulated periods."""
    from risk_lib import viz
    from risk_lib.html_report import CSS, _won, _pct, _esc, _table
    from risk_lib.abbreviations import abbr_dict_card_html
    from pathlib import Path

    df = ledger.to_frame()
    flags = ledger.trend_flags()
    periods = df["period"].tolist()

    def _fmt(v, fmt):
        if fmt == "pct":  return f"{v*100:.2f}%"
        if fmt == "won":  return _won(v)
        return f"{v:.3f}"

    # Capital ratios trend (CET1/Tier1/Total)
    cap_series = {
        "CET1": [float(x) for x in df["bis.cet1"]],
        "Tier1": [float(x) for x in df["bis.tier1"]],
        "Total": [float(x) for x in df["bis.total"]],
    }
    cap_chart = viz.line_chart(periods, cap_series, value_fmt=_pct,
                               title="자본비율 추이", reference_value=0.08,
                               reference_label="CET1 최저 8%")

    # Liquidity trend
    liq_series = {
        "LCR": [float(x) for x in df["lcr"]],
        "NSFR": [float(x) for x in df["nsfr"]],
    }
    liq_chart = viz.line_chart(periods, liq_series, value_fmt=_pct,
                               title="유동성비율 추이", reference_value=1.0,
                               reference_label="기준 100%")

    # RWA / ECL trend
    rwa_series = {"최종 RWA": [float(x) for x in df["rwa.final_total"]]}
    rwa_chart = viz.line_chart(periods, rwa_series, value_fmt=_won,
                               title="최종 RWA 추이")
    ecl_series = {
        "TTC ECL": [float(x) for x in df["ecl.ttc_total"]],
        "PIT 가중": [float(x) for x in df["ecl.pit_weighted"]],
    }
    ecl_chart = viz.line_chart(periods, ecl_series, value_fmt=_won,
                               title="ECL 충당금 추이")

    # trend flags table
    flag_rows = []
    for _, r in flags.iterrows():
        badge_tone = ("bad" if r["consecutive_breaches"] > 0
                      else "warn" if r["trend"] == "악화" else "good")
        flag_rows.append([
            r["label"], _fmt(r["latest"], r["fmt"]),
            (f"{r['qoq']*100:+.2f}%p" if r["fmt"] == "pct"
             else _won(r["qoq"]) if r["fmt"] == "won"
             else f"{r['qoq']:+.3f}"),
            r["trend"],
            str(int(r["consecutive_breaches"])) if r["floor"] is not None else "—",
        ])

    # QoQ/YoY table for capital
    qoq_cet1 = ledger.qoq_yoy("bis.cet1")
    qoq_rows = [[r["period"],
                 f"{r['bis.cet1']*100:.2f}%" if pd.notna(r["bis.cet1"]) else "—",
                 f"{r['qoq']*100:+.2f}%p" if pd.notna(r["qoq"]) else "—",
                 f"{r['yoy']*100:+.2f}%p" if pd.notna(r["yoy"]) else "—"]
                for _, r in qoq_cet1.iterrows()]

    body = f"""
<h1 class="title">{_esc(title)}</h1>
<p class="section-lead">누적 {len(periods)}개 기간 ({', '.join(periods)}) 시계열 추이.
각 데이터 포인트는 해당 기간 manifest digest로 추적 가능. QoQ/YoY 변동 + 연속 침범 카운터 포함.</p>

<div class="row2">
<div class="card"><h2>1-1. 자본비율 추이</h2><div class="chart">{cap_chart}</div></div>
<div class="card"><h2>1-2. 유동성비율 추이</h2><div class="chart">{liq_chart}</div></div>
</div>
<div class="row2">
<div class="card"><h2>1-3. 최종 RWA 추이</h2><div class="chart">{rwa_chart}</div></div>
<div class="card"><h2>1-4. ECL 충당금 추이</h2><div class="chart">{ecl_chart}</div></div>
</div>

<div class="card"><h2>2. 지표별 trend flag + 연속 침범</h2>
{_table(["지표","최근값","QoQ","추이","연속 침범"], flag_rows, right_cols=[1,2,4])}
<p class="section-lead">연속 침범 ≥ 2분기이면 감독상 escalation 대상. 추이는 방향 보정
(규제상 높을수록 좋은 지표는 상승=개선).</p>
</div>

<div class="card"><h2>3. CET1 QoQ / YoY 분기 변동</h2>
{_table(["기간","CET1","QoQ","YoY"], qoq_rows, right_cols=[1,2,3])}
</div>

{abbr_dict_card_html()}
"""
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>{_esc(title)}</title><style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap"><h1>{_esc(title)}</h1>
<div class="meta">누적 {len(periods)}개 기간 · risk_lib v0.23</div></div></header>
<div class="container">{body}</div>
<footer>risk_lib v0.23 · timeseries_ledger</footer>
</body></html>"""
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return str(p.resolve())
