"""상업성 계산 — 순구축대가·ARR·TCO·Lifecycle·ROI (COM-001~008).

리스크 산출물이 아니라 **사업성 산출물**이다. 그래서 세 가지를 분리한다.

1. 여기 숫자는 규제 보고에 실리지 않는다 — 제출 지문·독립검증 재계산
   대상에 넣지 않는다.
2. 모든 값은 **가정 원장**(ASSUMPTIONS)에서 계산으로만 나온다. 가정 없이
   등장하는 금액이 하나라도 있으면 그 표는 견적이 아니라 소설이다 (COM-006).
3. ROI 편익은 항목별로 **한 번만** 계산한다 — 같은 절감을 인력·오류·속도에
   세 번 계상하는 것이 ROI 부풀리기의 전형이다 (COM-007). 편익 항목마다
   출처 가정이 하나씩 붙고, 검증이 중복 참조를 잡는다.

전부 합성 가정(SYNTHETIC)이다 — 실제 고객 견적은 계약 가정으로 교체된다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# ---------------------------------------------------------------- 가정 원장

# (가정 ID, 설명, 값, 단위) — COM-001 고객·계약 가정. 값을 바꾸려면 여기를
# 바꾼다 — 계산식 안에 숫자를 심지 않는다.
ASSUMPTIONS = (
    ("A-RATE", "투입 단가 (블렌디드, 인일)", 1_200_000.0, "KRW/인일"),
    ("A-BANK-PD", "은행 패키지 구축 인일", 420.0, "인일"),
    ("A-SEC-PD", "증권 패키지 구축 인일", 300.0, "인일"),
    ("A-FULL-PD", "통합 패키지 구축 인일", 640.0, "인일"),
    ("A-LIFE", "Lifecycle 연 요율 (구축대가 대비)", 0.22, "비율"),
    ("A-INFRA", "연 인프라·운영 원가", 180_000_000.0, "KRW/년"),
    ("A-DISC", "다년 계약 할인율 (3년 선약정)", 0.10, "비율"),
    ("A-FTE", "수작업 보고 인력 절감", 3.0, "FTE"),
    ("A-FTE-COST", "FTE 연 총원가", 110_000_000.0, "KRW/FTE·년"),
    ("A-ERR", "오류 시정·재제출 회피 (연)", 60_000_000.0, "KRW/년"),
    ("A-AUDIT", "감사 대응 단축 (연)", 40_000_000.0, "KRW/년"),
)

_A = {a[0]: a[2] for a in ASSUMPTIONS}

# 패키지 Preset (COM-004) — (코드, 이름, 구축 인일 가정 ID, 포함 범위)
PRESETS = (
    ("PKG-BANK", "은행 리스크 패키지", "A-BANK-PD",
     "RWA·BIS·ECL·스트레스·업무보고서 290서식"),
    ("PKG-SEC", "증권 NCR 패키지", "A-SEC-PD",
     "NCR·시장·CCR/XVA·IPV·백테스팅"),
    ("PKG-FULL", "통합 RiskOps 패키지", "A-FULL-PD",
     "은행+증권 전 부문 + 에이전틱 UI + 독립검증 루프"),
)

# ROI 편익 항목 (COM-007) — 항목마다 출처 가정이 **하나**다. 같은 가정을 두
# 항목이 참조하면 이중계상이며, 검증이 잡는다.
ROI_BENEFITS = (
    ("B-FTE", "수작업 보고 인력 절감", "A-FTE"),
    ("B-ERR", "오류 시정·재제출 회피", "A-ERR"),
    ("B-AUDIT", "감사 대응 단축", "A-AUDIT"),
)


@dataclass(frozen=True)
class PackageQuote:
    """패키지 1종의 견적 — 전 항목이 가정에서 파생된다."""
    code: str
    name: str
    scope: str
    build_cost: float          # 순구축대가 (COM-002)
    lifecycle_annual: float    # Lifecycle 연 요율 (COM-005)
    arr: float                 # ARR (COM-003)
    year1_total: float         # 1년차 (구축 + Lifecycle)
    tco_3y: float              # 3년 TCO (할인 반영)


def quote(preset_code: str) -> PackageQuote:
    p = {x[0]: x for x in PRESETS}[preset_code]
    build = _A[p[2]] * _A["A-RATE"]                       # 인일 × 단가
    life = build * _A["A-LIFE"] + _A["A-INFRA"]           # 요율 + 인프라
    year1 = build + life
    tco3 = (build + 3 * life) * (1 - _A["A-DISC"])        # 3년 선약정 할인
    return PackageQuote(code=p[0], name=p[1], scope=p[3], build_cost=build,
                        lifecycle_annual=life, arr=life, year1_total=year1,
                        tco_3y=tco3)


def roi_annual_benefit() -> float:
    """연 편익 합 — 항목별 1회 계상."""
    total = 0.0
    for _, _, aid in ROI_BENEFITS:
        v = _A[aid]
        total += v * _A["A-FTE-COST"] if aid == "A-FTE" else v
    return total


def check_no_double_counting() -> list[str]:
    """COM-007 — 같은 가정을 두 편익 항목이 쓰면 이중계상이다."""
    seen: dict[str, str] = {}
    dup = []
    for bid, _, aid in ROI_BENEFITS:
        if aid in seen:
            dup.append(f"{bid}와 {seen[aid]}가 같은 가정 {aid}를 계상")
        seen[aid] = bid
    return dup


# ---------------------------------------------------------------- 프레임

def assumption_frame() -> pd.DataFrame:
    return pd.DataFrame(ASSUMPTIONS,
                        columns=["assumption_id", "description", "value", "unit"])


def quote_frame() -> pd.DataFrame:
    rows = []
    for code, _, _, _ in PRESETS:
        q = quote(code)
        payback = (q.build_cost / max(roi_annual_benefit(), 1.0))
        rows.append({
            "package": q.code, "name": q.name, "scope": q.scope,
            "build_cost": q.build_cost, "lifecycle_annual": q.lifecycle_annual,
            "arr": q.arr, "year1_total": q.year1_total, "tco_3y": q.tco_3y,
            "payback_years": round(payback, 2),
        })
    return pd.DataFrame(rows)


def roi_frame() -> pd.DataFrame:
    rows = []
    for bid, desc, aid in ROI_BENEFITS:
        v = _A[aid] * _A["A-FTE-COST"] if aid == "A-FTE" else _A[aid]
        rows.append({"benefit_id": bid, "description": desc,
                     "assumption_ref": aid, "annual_value": v})
    return pd.DataFrame(rows)


# GTM Funnel (COM-008) — 단계 정의 원장. 실제 파이프라인 데이터는 CRM에서
# 온다 — 여기는 단계·전환 기준의 정본이다.
FUNNEL_STAGES = (
    ("F1", "인지 — 규제 대응 페인 확인", "리스크·IT 임원 미팅"),
    ("F2", "평가 — PoC (합성 데이터)", "PoC 산출물 재현 성공"),
    ("F3", "검증 — 고객 데이터 파일럿", "2선·3선 게이트 통과"),
    ("F4", "계약 — 패키지·요율 확정", "가정 원장 서명"),
    ("F5", "확장 — 부문·계열사 추가", "Lifecycle 갱신"),
)


def funnel_frame() -> pd.DataFrame:
    return pd.DataFrame(FUNNEL_STAGES,
                        columns=["stage_id", "stage", "exit_criteria"])
