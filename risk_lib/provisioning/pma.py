"""모형 후 조정과 총계정원장 대사 (BNK-CRE-006).

ECL 엔진이 낸 값과 재무제표에 실리는 충당금은 같지 않다. 그 사이에 모형이
담지 못한 요인을 사람이 얹는데(PMA), 이 조정이 원장 없이 들어가면 충당금
전체가 재현 불가가 된다. 반대로 조정을 금지하면 알려진 모형 한계를 그대로
재무제표에 싣게 된다.

원장 두 장이다.

  ecl_pma                세그먼트별 모형 후 조정과 그 통제
  ecl_gl_reconciliation  모형 + 조정 값과 총계정원장 잔액의 대사

통제는 수동조정 원장(risk_lib.adjustments)과 같은 원칙을 쓴다. 요청자와
승인자가 달라야 하고, 사유와 증빙 참조가 있어야 하며, 유효기간이 지난 조정은
자동으로 무효다. 통제를 통과하지 못한 조정은 '미적용'으로 남고 대사에도
들어가지 않는다.

**총계정원장 잔액은 이 저장소 밖의 값이다.** 회계 시스템 연계가 없으므로
대사 입력을 인자로 받으며, 주지 않으면 대사 결과를 '미대사'로 남긴다.
대사하지 않은 것을 '대사 통과'로 적지 않는다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD BNK-CRE-006(PMA·IRB-ECL·GL) · DAT-006(수동조정 원장),
IFRS 9 5.5(손실충당금), IFRS 7 B5(가정 공시).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

PMA_CATEGORIES = ("모형 한계", "데이터 결함", "신규 리스크", "거시가정 보정",
                  "일회성 사건")
PMA_STATUSES = ("적용", "미적용")
RECON_STATUSES = ("일치", "차이", "미대사")


ECL_PMA = TableSpec(
    name="ecl_pma", korean="모형 후 조정", product="PRD-ECL",
    grain="세그먼트 x 조정사유 1건당 1행",
    columns=(
        C("pma_id", "string", "조정 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("category", "string", "조정 사유 구분", nullable=False,
          allowed=PMA_CATEGORIES),
        C("model_ecl", "float", "모형 ECL", nullable=False, unit="KRW",
          min_value=0.0),
        C("pma_amount", "float", "조정액", nullable=False, unit="KRW"),
        C("pma_ratio", "float", "모형 대비 조정 비율", nullable=False, unit="ratio"),
        C("rationale", "text", "사유", nullable=False),
        C("evidence_ref", "text", "증빙 참조", nullable=False),
        C("requester", "text", "요청자", nullable=False),
        C("approver", "text", "승인자", nullable=False),
        C("approval_date", "date", "승인일", nullable=False),
        C("expires_on", "date", "유효 종료일", nullable=False),
        C("status", "string", "적용 상태", nullable=False, allowed=PMA_STATUSES),
        C("control_note", "text", "통제 판정", nullable=False),
    ),
    primary_key=("pma_id",),
    note="조정 비율을 컬럼으로 둔다. 금액만 보면 세그먼트 규모에 묻혀 과도한 조정이 보이지 않는다.",
)

GL_RECONCILIATION = TableSpec(
    name="ecl_gl_reconciliation", korean="충당금 총계정원장 대사", product="PRD-ECL",
    grain="세그먼트 1개당 1행",
    columns=(
        C("recon_id", "string", "대사 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("model_ecl", "float", "모형 ECL", nullable=False, unit="KRW",
          min_value=0.0),
        C("pma_applied", "float", "적용 조정액", nullable=False, unit="KRW"),
        C("reported_ecl", "float", "보고 충당금", nullable=False, unit="KRW",
          min_value=0.0),
        C("gl_balance", "float", "총계정원장 잔액", nullable=True, unit="KRW",
          min_value=0.0, note="회계 시스템 연계가 없으면 NULL이다"),
        C("gap", "float", "차이", nullable=True, unit="KRW"),
        C("gap_ratio", "float", "차이 비율", nullable=True, unit="ratio"),
        C("tolerance", "float", "허용 오차", nullable=False, unit="KRW",
          min_value=0.0),
        C("status", "string", "대사 판정", nullable=False, allowed=RECON_STATUSES),
        C("reason", "text", "사유", nullable=False),
    ),
    primary_key=("recon_id",),
    note="세그먼트 축은 호출부가 정한다. 이 원장이 축을 정하면 다른 보고서와 갈라진다.",
)

SPECS: tuple[TableSpec, ...] = (ECL_PMA, GL_RECONCILIATION)


# ---------------------------------------------------------------- 적재 표
#
# PMA 후보. 조정 비율은 세그먼트 모형 ECL 대비 비율로 적용한다. 마지막 두 건은
# 통제에 걸리도록 둔다. 통제가 실제로 발동하는 것을 원장에서 보여야 한다.
#
# (조정ID, 세그먼트키워드, 구분, 비율, 사유, 증빙, 요청자, 승인자, 유효월수)
_PMA_CANDIDATES = (
    ("PMA-001", "corporate", "모형 한계", 0.04,
     "업종 편중이 모형 설명변수에 반영되지 않아 부동산업 익스포저의 PD가 과소추정된다",
     "CRE-2026-0112 / 업종 백테스트 보고서", "신용리스크부 담당", "리스크관리부장", 12),
    ("PMA-002", "retail_other", "데이터 결함", 0.02,
     "연체일수 원천의 갱신 지연으로 일부 계좌의 Stage 전이가 늦게 잡힌다",
     "DQ-2026-0087 / 데이터품질 예외", "리스크데이터관리자", "리스크관리부장", 6),
    ("PMA-003", "residential_mortgage", "거시가정 보정", -0.03,
     "주택가격 시나리오가 직전 분기 실적을 반영하지 않아 LGD가 과대추정된다",
     "MAC-2026-0041 / 거시 시나리오 검토", "신용리스크부 담당", "최고리스크책임자", 6),
    # 통제 위반 1. 요청자와 승인자가 같다.
    ("PMA-004", "bank", "신규 리스크", 0.05,
     "해외 거래상대 신용도 악화 우려",
     "MEMO-2026-0210", "시장리스크부 담당", "시장리스크부 담당", 12),
    # 통제 위반 2. 증빙 참조가 비어 있다.
    ("PMA-005", "sovereign", "일회성 사건", 0.01,
     "국가 신용등급 전망 변경 반영", "", "신용리스크부 담당", "리스크관리부장", 12),
)

# 대사 허용 오차. 세그먼트 보고 충당금 대비 비율로 정한다. 회계 정책상
# 반올림 단위가 있어 완전 일치를 요구하지 않는다.
_TOLERANCE_RATIO = 0.0001


def _months_later(day: str, months: int) -> str:
    d = date.fromisoformat(day)
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, min(d.day, 28)).isoformat()


def control_violations(row: dict, *, asof: str) -> list[str]:
    """적용을 막는 통제 위반 목록. 비어 있어야 적용된다."""
    v = []
    if not str(row["rationale"]).strip():
        v.append("사유 미기재")
    if not str(row["evidence_ref"]).strip():
        v.append("증빙 참조 미기재")
    if str(row["requester"]).strip() == str(row["approver"]).strip():
        v.append(f"직무분리 위반 (요청자=승인자: {row['requester']})")
    try:
        if date.fromisoformat(str(row["expires_on"])) < date.fromisoformat(asof):
            v.append(f"유효기간 만료 ({row['expires_on']})")
    except ValueError:
        v.append(f"유효기간 형식 오류 ({row['expires_on']!r})")
    return v


def build_pma(segment_ecl: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """세그먼트별 모형 ECL에 조정 후보를 붙이고 통제를 판정한다.

    segment_ecl은 segment·ecl 두 컬럼을 가진 표다. 세그먼트가 없으면 그 조정은
    만들지 않는다. 없는 세그먼트에 조정을 얹으면 대사에서 정체 불명 금액이 된다.
    """
    base = dict(zip(segment_ecl["segment"].astype(str),
                    segment_ecl["ecl"].astype(float)))
    rows = []
    for (pid, segment, category, ratio, rationale, evidence, requester,
         approver, months) in _PMA_CANDIDATES:
        if segment not in base:
            continue
        model_ecl = float(base[segment])
        row = {
            "pma_id": pid, "segment": segment, "category": category,
            "model_ecl": round(model_ecl, 2),
            "pma_amount": round(model_ecl * ratio, 2),
            "pma_ratio": float(ratio), "rationale": rationale,
            "evidence_ref": evidence, "requester": requester,
            "approver": approver, "approval_date": asof,
            "expires_on": _months_later(asof, months),
        }
        violations = control_violations(row, asof=asof)
        row["status"] = "미적용" if violations else "적용"
        row["control_note"] = " · ".join(violations) if violations else "통제 통과"
        rows.append(row)
    return pd.DataFrame(rows, columns=[c.name for c in ECL_PMA.columns])


def reconcile_gl(segment_ecl: pd.DataFrame, pma: pd.DataFrame, *,
                 gl_balances: dict[str, float] | None = None
                 ) -> tuple[pd.DataFrame, list[str]]:
    """모형 + 적용 조정과 총계정원장 잔액을 대사한다.

    gl_balances를 주지 않으면 대사하지 않고 '미대사'로 남긴다.
    (대사 원장, 차이 목록)을 돌려준다.
    """
    applied = (pma[pma["status"] == "적용"].groupby("segment")["pma_amount"].sum()
               if len(pma) else pd.Series(dtype="float64"))
    problems: list[str] = []
    rows = []
    for _, s in segment_ecl.iterrows():
        seg = str(s["segment"])
        model = float(s["ecl"])
        adj = float(applied.get(seg, 0.0))
        reported = model + adj
        tol = abs(reported) * _TOLERANCE_RATIO
        gl = None if gl_balances is None else float(gl_balances.get(seg, np.nan))
        if gl is None or (isinstance(gl, float) and np.isnan(gl)):
            gap = gap_ratio = None
            status = "미대사"
            reason = "총계정원장 잔액 미제공. 회계 시스템 연계가 없다"
        else:
            gap = gl - reported
            gap_ratio = gap / reported if reported else 0.0
            if abs(gap) <= tol:
                status, reason = "일치", f"차이 {gap:,.0f}이 허용 오차 {tol:,.0f} 이내"
            else:
                status = "차이"
                reason = (f"차이 {gap:,.0f} ({gap_ratio:.4%})가 허용 오차 "
                          f"{tol:,.0f}을 넘는다. 원장에 없는 조정을 확인해야 한다")
                problems.append(f"{seg}: {reason}")
        rows.append({
            "recon_id": f"GLR-{seg}", "segment": seg,
            "model_ecl": round(model, 2), "pma_applied": round(adj, 2),
            "reported_ecl": round(reported, 2),
            "gl_balance": None if gl is None else round(float(gl), 2),
            "gap": None if gap is None else round(float(gap), 2),
            "gap_ratio": None if gap_ratio is None else round(float(gap_ratio), 6),
            "tolerance": round(tol, 2), "status": status, "reason": reason,
        })
    frame = pd.DataFrame(rows, columns=[c.name for c in GL_RECONCILIATION.columns]
                         ).astype({"gl_balance": "float64", "gap": "float64",
                                   "gap_ratio": "float64"})
    if gl_balances is None:
        problems.append("총계정원장 대사를 수행하지 않았다. 연계 원장이 없다")
    return frame, problems


def segment_ecl_from_result(ecl_frame: pd.DataFrame, *,
                            segment_column: str = "asset_class"
                            ) -> pd.DataFrame:
    """ECL 산출 결과를 세그먼트 단위로 집계한다.

    세그먼트 축을 인자로 받는다. 축을 이 모듈이 정하면 다른 보고서와 세그먼트
    정의가 갈라진다.
    """
    if segment_column not in ecl_frame.columns:
        raise KeyError(f"ECL 원장에 세그먼트 컬럼 {segment_column}이 없다")
    agg = (ecl_frame.groupby(segment_column)["ecl"].sum().reset_index()
           .rename(columns={segment_column: "segment"}))
    return agg.sort_values("segment").reset_index(drop=True)


def build_pma_and_recon(segment_ecl: pd.DataFrame, *, asof: str,
                        gl_balances: dict[str, float] | None = None
                        ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """PMA 원장과 대사 원장을 만든다. (원장, 문제 목록)을 돌려준다."""
    pma = build_pma(segment_ecl, asof=asof)
    recon, problems = reconcile_gl(segment_ecl, pma, gl_balances=gl_balances)
    blocked = [f"{r['pma_id']}: {r['control_note']}"
               for _, r in pma.iterrows() if r["status"] == "미적용"]
    return ({"ecl_pma": pma, "ecl_gl_reconciliation": recon}, blocked + problems)
