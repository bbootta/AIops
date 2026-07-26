"""자산운용 한도 — 대주주 신용공여 · 유가증권 투자 · 자회사 출자 · 부동산 소유.

은행법이 자기자본 대비로 묶는 한도들이다. 자본비율만 보고하면 이 한도들은
화면 밖에 남고, 한 건이라도 초과하면 그 자체가 시정조치 사유가 된다.

  대주주 신용공여      자기자본 25% 이내 (은행법 제35조의2 제1항)
  대주주 발행주식 취득  자기자본 1% 이내 (은행법 제35조의3 제1항)
  자회사 출자          자기자본 20% 이내 (은행법 제37조 제2항)
  유가증권 투자        자기자본 100% 이내 (은행법 제38조 제1호)
  업무용부동산 소유    자기자본 60% 이내 (은행법 제38조 제3호)

한도 자체는 규정값이고, 사용액은 대차대조표·포트폴리오에서 유도한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# 자기자본 대비 한도 (은행법)
LIMIT_MAJOR_SHAREHOLDER_CREDIT = 0.25
LIMIT_MAJOR_SHAREHOLDER_EQUITY = 0.01
LIMIT_SUBSIDIARY_INVESTMENT = 0.20
LIMIT_SECURITIES = 1.00
LIMIT_BUSINESS_PROPERTY = 0.60

# 사용액 유도 비율 — 합성 대차대조표에 계정 구분이 없어 자산 구성에서 배분한다.
# 실제 제출 시 계정계 원장으로 대체된다.
_SHARE_OF_OTHER_ASSETS = {
    "subsidiary": 0.18,          # 자회사 출자금
    "business_property": 0.34,   # 업무용 부동산
}
# 대주주 지정 원장이 원천 데이터에 **없다**. 아무 그룹이나 대주주로 지정하면
# 있지도 않은 한도 초과를 보고하게 되므로 사용액을 0으로 두고 "미식별" 상태를
# 남긴다 — 제출 전에 반드시 채워야 하는 칸임이 드러나야 한다.
_MAJOR_SHAREHOLDER_IDENTIFIED = False


@dataclass(frozen=True)
class OwnershipLimits:
    asof: str
    own_capital: float
    detail: pd.DataFrame     # item, used, limit_pct, limit_amount, utilisation, passes, citation

    def passes(self) -> bool:
        return bool(self.detail["passes"].all())

    @property
    def n_breaches(self) -> int:
        return int((~self.detail["passes"]).sum())


def compute_ownership_limits(result, portfolio: pd.DataFrame) -> OwnershipLimits:
    asof = result.meta.get("asof", "1970-01-01")
    cap = result.meta["capital"]
    own = float(cap.total)
    bs = result.alm["balance_sheet"]

    ms_credit = 0.0 if not _MAJOR_SHAREHOLDER_IDENTIFIED else float("nan")

    # 유가증권 투자한도의 모집단은 국채·통화안정증권 등을 **제외한** 유가증권이다.
    # Level 1 HQLA는 대부분 국채이므로 한도 대상에서 뺀다. 전액을 넣으면 실제로는
    # 존재하지 않는 한도 초과가 만들어진다.
    securities = float(bs.hqla["level_2a"] + bs.hqla["level_2b"])
    other = float(bs.other_assets)
    subsidiary = other * _SHARE_OF_OTHER_ASSETS["subsidiary"]
    property_ = other * _SHARE_OF_OTHER_ASSETS["business_property"]
    ms_equity = other * 0.004

    _UNIDENTIFIED = "대주주 지정 원장 미보유 — 제출 전 반드시 확인 필요"
    rows = [
        ("대주주 신용공여", ms_credit, LIMIT_MAJOR_SHAREHOLDER_CREDIT,
         "은행법 제35조의2 제1항 — 자기자본 25% 이내", _UNIDENTIFIED),
        ("대주주 발행주식 취득", ms_equity, LIMIT_MAJOR_SHAREHOLDER_EQUITY,
         "은행법 제35조의3 제1항 — 자기자본 1% 이내",
         "기타자산 중 지분증권 배분치"),
        ("자회사 출자", subsidiary, LIMIT_SUBSIDIARY_INVESTMENT,
         "은행법 제37조 제2항 — 자기자본 20% 이내", "기타자산 중 출자금 배분치"),
        ("유가증권 투자", securities, LIMIT_SECURITIES,
         "은행법 제38조 제1호 — 자기자본 100% 이내 (국채·통안증권 제외)",
         "HQLA Level 2A·2B 합계"),
        ("업무용부동산 소유", property_, LIMIT_BUSINESS_PROPERTY,
         "은행법 제38조 제3호 — 자기자본 60% 이내", "기타자산 중 부동산 배분치"),
    ]
    detail = pd.DataFrame([{
        "item": name, "used": used, "limit_pct": pct,
        "limit_amount": own * pct,
        "utilisation": (used / (own * pct)) if own * pct > 0 else 0.0,
        "passes": used <= own * pct + 1e-6,
        "citation": cite, "basis": basis,
    } for name, used, pct, cite, basis in rows])
    return OwnershipLimits(asof=asof, own_capital=own, detail=detail)
