"""수동조정 원장 (DAT-006) — 사람이 덮어쓴 수치의 통제된 기록.

모형·엔진이 산출한 값을 사람이 조정하는 일은 실무에서 불가피하다(데이터 지연,
일회성 사건, 모형 한계 보정 등). 문제는 **기록되지 않은 조정**이다 — 조정
한 건이 문서 없이 들어가면 그 순간부터 보고서 전체가 재현 불가가 되고,
감사에서 가장 먼저 지적되는 항목이 된다.

본 원장이 강제하는 통제:

  직무분리(SoD)   요청자 ≠ 승인자. 위반 시 적용 불가.
  중요성 임계     기준 초과 조정은 상위 승인(CRO/위원회) 필요.
  유효기간        만료된 조정은 자동 무효 — 임시 조정이 영구화되는 것을 막는다.
  근거 필수       사유와 증빙 참조가 없으면 등록 자체가 거부된다.
  재현성          원장 지문(SHA-256)이 manifest에 실려, 조정 포함 산출과
                  미포함 산출이 digest 수준에서 구분된다.

조정은 **적용(applied)** 되어야만 수치에 반영된다. 등록만 된 조정(pending)은
보고서에 "미승인 조정"으로 노출되며 수치에는 들어가지 않는다.

참조: RYNTA BRD DAT-006(수동조정 원장) · RDM-007(데이터 예외·조치 workflow),
BCBS 239 원칙 3(정확성·무결성), AIMS_POLICY.md §2-1(인적 감독).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

import pandas as pd

# 중요성 임계 — 초과 시 상위 승인 필요. 기관 승인값으로 교체 대상.
MATERIALITY_ABS = 10_000_000_000.0        # 100억원
MATERIALITY_REL = 0.01                    # 기준값 대비 1%

VALID_STATUS = ("pending", "applied", "rejected", "expired")
SENIOR_APPROVERS = ("CRO", "리스크관리위원회", "이사회")


class AdjustmentError(ValueError):
    """조정 등록·적용이 통제를 위반했을 때."""


@dataclass
class ManualAdjustment:
    """수동조정 1건 — 어떤 수치를, 얼마나, 왜, 누가, 언제까지."""
    adjustment_id: str
    figure_id: str                # 조정 대상 (audit ledger의 figure_id와 동일 체계)
    label: str
    base_value: float             # 조정 전 엔진 산출값
    adjusted_value: float         # 조정 후 값
    reason: str                   # 사유 — 필수
    evidence_ref: str             # 증빙 참조 (문서번호·티켓 등) — 필수
    requester: str
    approver: str
    approval_date: str            # ISO date
    expires_on: str               # ISO date — 이후 자동 무효
    status: str = "pending"
    senior_approval: str = ""     # 중요성 초과 시 상위 승인자
    schema_version: str = "1.0"

    # ---- 파생 ----
    @property
    def delta(self) -> float:
        return self.adjusted_value - self.base_value

    @property
    def rel_delta(self) -> float:
        return abs(self.delta) / abs(self.base_value) if self.base_value else float("inf")

    def is_material(self) -> bool:
        """절대·상대 임계 중 하나라도 초과하면 중요 조정."""
        return abs(self.delta) >= MATERIALITY_ABS or self.rel_delta >= MATERIALITY_REL

    def is_expired(self, asof: str | date) -> bool:
        """ISO date로 파싱해 비교한다 — 문자열 사전순 비교는 비ISO 형식이나
        자릿수 미보정 날짜에서 통제를 영구히 무력화한다."""
        a = date.fromisoformat(asof if isinstance(asof, str) else asof.isoformat())
        try:
            exp = date.fromisoformat(self.expires_on)
        except (ValueError, TypeError):
            return True          # 파싱 불가 = 유효기간 없음 = 사용 불가
        return exp < a

    # ---- 통제 ----
    def control_violations(self, asof: str | date) -> list[str]:
        """적용을 막는 통제 위반 목록 — 비어 있어야 적용 가능."""
        v = []
        if not self.reason.strip():
            v.append("사유 미기재")
        if not self.evidence_ref.strip():
            v.append("증빙 참조 미기재")
        if not self.requester.strip() or not self.approver.strip():
            v.append("요청자·승인자 미기재")
        elif self.requester.strip() == self.approver.strip():
            v.append(f"직무분리 위반 (요청자=승인자: {self.requester})")
        if self.is_expired(asof):
            v.append(f"유효기간 만료 ({self.expires_on})")
        if self.is_material() and not self.senior_approval.strip():
            v.append(f"중요성 임계 초과 — 상위 승인 필요 "
                     f"(Δ {self.delta:,.0f}, {self.rel_delta:.2%})")
        if self.senior_approval and self.senior_approval not in SENIOR_APPROVERS:
            v.append(f"상위 승인자 자격 미달: {self.senior_approval}")
        if self.status not in VALID_STATUS:
            v.append(f"알 수 없는 상태: {self.status}")
        try:
            date.fromisoformat(self.expires_on)
        except (ValueError, TypeError):
            v.append(f"유효기간 형식 오류 (ISO date 아님): {self.expires_on!r}")
        return v

    def can_apply(self, asof: str | date) -> bool:
        return not self.control_violations(asof)


@dataclass
class AdjustmentLedger:
    """수동조정 원장 — append-only. 적용 여부는 통제 통과 시에만."""
    adjustments: list[ManualAdjustment] = field(default_factory=list)

    def add(self, adj: ManualAdjustment) -> None:
        if any(a.adjustment_id == adj.adjustment_id for a in self.adjustments):
            raise AdjustmentError(f"조정 ID 중복: {adj.adjustment_id}")
        if not adj.reason.strip() or not adj.evidence_ref.strip():
            raise AdjustmentError(
                f"{adj.adjustment_id}: 사유·증빙 없는 조정은 등록할 수 없다")
        self.adjustments.append(adj)

    def cumulative_violations(self, asof: str | date) -> dict[str, str]:
        """figure_id별 **누적** 중요성 검사 — 쪼개기(splitting) 우회 차단.

        건별로는 임계 미만이어도 같은 수치에 대한 조정 합이 임계를 넘으면
        상위 승인이 필요하다. 상위 승인이 하나도 없으면 그 수치의 조정을
        모두 차단한다 — 큰 조정을 잘게 나누면 통제가 무력화되기 때문이다.
        """
        out: dict[str, str] = {}
        by_fig: dict[str, list[ManualAdjustment]] = {}
        for a in self.adjustments:
            if a.status == "rejected":
                continue
            if a.control_violations(asof):
                continue                       # 개별 위반은 별도로 차단됨
            by_fig.setdefault(a.figure_id, []).append(a)

        for fig, items in by_fig.items():
            total = sum(x.delta for x in items)
            base = items[0].base_value
            rel = abs(total) / abs(base) if base else float("inf")
            if len(items) < 2:
                continue                       # 단건은 개별 임계로 이미 판정
            if abs(total) >= MATERIALITY_ABS or rel >= MATERIALITY_REL:
                if not any(x.senior_approval.strip() for x in items):
                    out[fig] = (
                        f"누적 중요성 초과 — {len(items)}건 합 Δ {total:,.0f} "
                        f"({rel:.2%}), 상위 승인 없음 (쪼개기 우회 차단)")
        return out

    def apply_all(self, asof: str | date) -> list[str]:
        """통제를 통과한 조정만 applied로, 만료분은 expired로 전이.

        반환값은 적용되지 못한 조정의 사유 목록 — 조용히 넘어가지 않는다.
        개별 통제를 통과해도 figure_id별 누적 중요성에 걸리면 차단된다.
        """
        blocked = []
        for a in self.adjustments:
            if a.status == "rejected":
                continue
            violations = a.control_violations(asof)
            if violations:
                a.status = "expired" if a.is_expired(asof) else "pending"
                blocked.append(f"{a.adjustment_id} ({a.figure_id}): "
                               + " · ".join(violations))
            else:
                a.status = "applied"

        # 누적 임계는 개별 판정이 끝난 뒤 적용한다.
        for fig, reason in self.cumulative_violations(asof).items():
            for a in self.adjustments:
                if a.figure_id == fig and a.status == "applied":
                    a.status = "pending"
                    blocked.append(f"{a.adjustment_id} ({fig}): {reason}")
        return blocked

    # ---- 조회 ----
    def applied(self) -> list[ManualAdjustment]:
        return [a for a in self.adjustments if a.status == "applied"]

    def net_effect(self, figure_id: str | None = None) -> float:
        """적용된 조정의 순효과. figure_id를 주면 해당 수치만."""
        return sum(a.delta for a in self.applied()
                   if figure_id is None or a.figure_id == figure_id)

    def adjusted(self, figure_id: str, base_value: float) -> float:
        """엔진 산출값에 적용된 조정을 반영한 최종값."""
        return base_value + self.net_effect(figure_id)

    def to_frame(self) -> pd.DataFrame:
        if not self.adjustments:
            return pd.DataFrame(columns=[
                "adjustment_id", "figure_id", "label", "base_value",
                "adjusted_value", "delta", "rel_delta", "material",
                "status", "requester", "approver", "senior_approval",
                "approval_date", "expires_on", "reason", "evidence_ref"])
        rows = []
        for a in self.adjustments:
            d = asdict(a)
            d.update({"delta": a.delta, "rel_delta": a.rel_delta,
                      "material": a.is_material()})
            rows.append(d)
        return pd.DataFrame(rows)

    # ---- 재현성 ----
    def fingerprint(self) -> str:
        """원장 지문 — 조정 내용이 바뀌면 digest가 바뀐다.

        manifest에 실어 '조정 포함 산출'과 '미포함 산출'을 구분한다.
        상태(status)까지 포함하므로 승인 전후도 구분된다.
        """
        payload = [
            {k: v for k, v in asdict(a).items() if k != "schema_version"}
            for a in sorted(self.adjustments, key=lambda x: x.adjustment_id)
        ]
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def export_json(self, path) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"fingerprint": self.fingerprint(),
             "adjustments": [asdict(a) for a in self.adjustments]},
            indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return str(p.resolve())

    @classmethod
    def load(cls, path) -> "AdjustmentLedger":
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(adjustments=[ManualAdjustment(**d)
                                for d in data.get("adjustments", [])])


# ---------------------------------------------------------------- 대사

def reconcile(ledger: AdjustmentLedger, engine_values: dict[str, float],
              reported_values: dict[str, float] | None = None,
              *, tolerance: float = 1.0) -> pd.DataFrame:
    """엔진 산출값 ↔ 조정 후 보고값 대사 (RDM-005 원천–산출–보고 대사).

    `reported_values`(외부 보고서·공시에 실제로 실린 값)를 주면
    `보고값 − (엔진값 + 적용 조정)` 의 잔차를 계산한다. 잔차가 0이 아니면
    **원장에 기록되지 않은 조정**이 어딘가에서 들어간 것이므로 즉시 조사 대상이다.

    reported_values를 주지 않으면 기대 보고값만 산출하고 잔차는 NaN으로 둔다 —
    대사하지 않은 것을 "대사 통과"로 표기하지 않기 위함이다.
    """
    import numpy as np
    rows = []
    for fid, base in engine_values.items():
        net = ledger.net_effect(fid)
        expected = base + net
        actual = (reported_values or {}).get(fid)
        residual = np.nan if actual is None else actual - expected
        rows.append({
            "figure_id": fid, "engine_value": base, "adjustment": net,
            "expected_reported": expected,
            "actual_reported": np.nan if actual is None else actual,
            "residual": residual,
            "n_applied": sum(1 for a in ledger.applied() if a.figure_id == fid),
            "n_blocked": sum(1 for a in ledger.adjustments
                             if a.figure_id == fid
                             and a.status in ("pending", "expired")),
            # 미대사는 True도 False도 아니다 — pd.NA로 남겨 구분한다.
            "reconciles": pd.NA if actual is None else bool(abs(residual) <= tolerance),
        })
    return pd.DataFrame(rows)


def unrecorded_adjustments(recon: pd.DataFrame) -> pd.DataFrame:
    """대사 잔차가 남은 수치 — 원장에 없는 조정이 개입한 흔적."""
    return recon[recon["reconciles"] == False]      # noqa: E712 — pd.NA 제외 의도


# ---------------------------------------------------------------- 데모 원장

def demo_ledger(result, *, asof: str | None = None) -> AdjustmentLedger:
    """통제 시연용 조정 4건 — 통과 2 · 차단 2 (**예시**).

    실무 원장이 아니라 통제가 실제로 작동함을 보이기 위한 합성 사례다.
    """
    asof = asof or result.meta.get("asof", date.today().isoformat())
    y = int(asof[:4])
    led = AdjustmentLedger()

    # 1) 정상 — 소액, SoD 충족, 유효
    led.add(ManualAdjustment(
        adjustment_id="ADJ-001", figure_id="ecl.ttc_total",
        label="일회성 대손 회수 반영",
        base_value=float(result.ecl["total"]),
        adjusted_value=float(result.ecl["total"]) * 0.995,
        reason="결산 후 확정된 담보 처분대금 반영 (모형 산출 시점 미반영)",
        evidence_ref="RISK-2026-0431 / 담보처분 확인서",
        requester="신용리스크부 김OO", approver="리스크관리부장 이OO",
        approval_date=asof, expires_on=f"{y + 1}-12-31", status="pending"))

    # 2) 정상 — 중요 조정이나 상위 승인 확보
    led.add(ManualAdjustment(
        adjustment_id="ADJ-002", figure_id="rwa.final_total",
        label="분류오류 정정 (중복배분 해소)",
        base_value=float(result.rwa["final_total"]),
        adjusted_value=float(result.rwa["final_total"]) * 0.985,
        reason="동일 익스포저가 SA·IRB에 중복 계상된 건 정정",
        evidence_ref="RISK-2026-0455 / 독립검증 재계산 결과",
        requester="RWA산출팀 박OO", approver="자본관리부장 최OO",
        approval_date=asof, expires_on=f"{y + 1}-06-30",
        senior_approval="CRO", status="pending"))

    # 3) 차단 — 직무분리 위반
    led.add(ManualAdjustment(
        adjustment_id="ADJ-003", figure_id="alm.lcr",
        label="예금 이탈률 가정 완화",
        base_value=float(result.alm["lcr"].lcr),
        adjusted_value=float(result.alm["lcr"].lcr) * 1.03,
        reason="자체 관측 이탈률이 규정 가정보다 낮음",
        evidence_ref="ALM-2026-0112",
        requester="자금부 정OO", approver="자금부 정OO",     # 동일인 — SoD 위반
        approval_date=asof, expires_on=f"{y + 1}-12-31", status="pending"))

    # 4) 차단 — 중요성 초과인데 상위 승인 없음
    led.add(ManualAdjustment(
        adjustment_id="ADJ-004", figure_id="rwa.final_total",
        label="시장리스크 RWA 재산정",
        base_value=float(result.rwa["final_total"]),
        adjusted_value=float(result.rwa["final_total"]) * 0.96,
        reason="포지션 매핑 오류 추정",
        evidence_ref="MKT-2026-0087 (검토 중)",
        requester="시장리스크팀 한OO", approver="시장리스크부장 오OO",
        approval_date=asof, expires_on=f"{y + 1}-12-31", status="pending"))

    led.apply_all(asof)
    return led
