"""분기 거버넌스 KPI 시계열.

``tools.governance_kpi.build_report`` 는 단일 시점의 KPI 만 산출한다. 본 모듈은
분기별 KPI panel 을 합성 또는 누적으로 구성해 거버넌스 trend 를 시각화한다.

분기별 KPI:
- manifest validated_ratio (검증된 CHG 비율)
- audit fail_ratio (실행 로그의 fail 비율)
- feedback agreement_rate (분류기 동의율)
- policy_lint OK / conflict 카운트

본 모듈은 결정론적 합성 panel 을 제공하고 (운영 panel 부재 시 fallback),
다회 실행된 ``logs/run.jsonl`` 이 있을 경우 실제 audit_kpi 를 계산해 분기에
귀속시킨다.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def synthetic_governance_panel(*, n_quarters: int = 4) -> list[dict]:
    """분기별 거버넌스 KPI 합성 panel (결정론적, seed 불필요).

    실 panel 이 없을 때 보고서 trend 시각화용. 점진 개선 trend.
    """
    base_validated = 0.40
    base_fail = 0.18
    base_agree = 0.65
    base_conflicts = 4
    out = []
    for i in range(n_quarters):
        q = f"2026Q{i + 1}" if i < 4 else f"2027Q{i - 3}"
        out.append({
            "quarter": q,
            "validated_ratio": round(min(base_validated + 0.05 * i, 0.85), 4),
            "applied_or_validated_ratio": round(
                min(base_validated + 0.08 * i, 0.95), 4),
            "manifest_total": 80 + i * 12,
            "audit_fail_ratio": round(max(base_fail - 0.02 * i, 0.05), 4),
            "feedback_agreement_rate": round(
                min(base_agree + 0.04 * i, 0.90), 4),
            "policy_lint_conflicts": max(0, base_conflicts - i),
            "rf_total": 7 + i,
        })
    return out


def quarter_of(ts: str) -> str | None:
    """timestamp 문자열을 'YYYYQn' 으로 변환."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(ts, fmt)
            return f"{dt.year}Q{(dt.month - 1) // 3 + 1}"
        except (ValueError, TypeError):
            continue
    return None


def audit_panel_from_log(log_path: str | Path) -> list[dict]:
    """``logs/run.jsonl`` 의 step 이벤트를 분기로 묶어 분기별 fail_ratio 산출."""
    p = Path(log_path)
    if not p.exists():
        return []
    quarters: dict[str, dict[str, int]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") != "step":
            continue
        q = quarter_of(rec.get("timestamp", ""))
        if q is None:
            continue
        bucket = quarters.setdefault(q, {"total": 0, "fail": 0})
        bucket["total"] += 1
        if rec.get("workflow_status") == "fail":
            bucket["fail"] += 1
    out = []
    for q in sorted(quarters):
        b = quarters[q]
        out.append({
            "quarter": q,
            "audit_total_steps": b["total"],
            "audit_fail_steps": b["fail"],
            "audit_fail_ratio": (b["fail"] / b["total"]) if b["total"] else 0.0,
        })
    return out


def build_panel(log_path: str | Path | None = None) -> list[dict]:
    """audit panel + 합성 governance panel 을 분기 키로 merge.

    실 audit 데이터가 있는 분기는 audit_fail_ratio 를 실측으로 대체.
    """
    synth = synthetic_governance_panel(n_quarters=4)
    audit = audit_panel_from_log(log_path) if log_path else []
    audit_by_q = {a["quarter"]: a for a in audit}
    for row in synth:
        if row["quarter"] in audit_by_q:
            row["audit_fail_ratio"] = audit_by_q[row["quarter"]]["audit_fail_ratio"]
            row["audit_total_steps"] = audit_by_q[row["quarter"]]["audit_total_steps"]
            row["audit_source"] = "live"
        else:
            row["audit_source"] = "synthetic"
    return synth


__all__ = [
    "synthetic_governance_panel",
    "audit_panel_from_log",
    "build_panel",
    "quarter_of",
]
