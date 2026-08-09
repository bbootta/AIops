"""상품 명세와 평가모형 매핑 (SEC-PRC-002).

이 저장소는 커브·변동성면을 만들고(market_data) 가격을 검증하지만(ipv),
**어떤 상품을 어떤 모형으로 평가하는가**를 원장으로 두지 않았다. 그 매핑이
없으면 새 상품이 들어왔을 때 승인된 모형 없이 평가되는 것을 막을 수 없다.

원장 세 장이다.

  mkt_product            상품 명세(자산군·수익구조·기초자산·결제)
  mkt_pricing_model      평가모형(방법론·입력 리스크팩터·검증 상태)
  mkt_product_model_map  상품 x 모형 x 용도 매핑과 승인 여부

판정 하나를 붙인다. 공식평가 용도로 승인된 모형이 없는 상품은 '평가불가'다.
평가불가 상품이 남아 있는데 손익이 산출되면 그 손익은 근거 없는 값이다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD SEC-PRC-002(상품명세·Pricing Model) · SEC-PRC-005(IPV),
SR 11-7(모형위험관리), Basel III MAR30(내부모형 승인).
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

ASSET_CLASSES = ("금리", "외환", "주식", "신용", "상품")
PAYOFF_TYPES = ("선형", "옵션", "구조화")
SETTLEMENTS = ("현금결제", "실물인수도")
METHODOLOGIES = ("할인현금흐름", "해석해", "격자", "몬테카를로", "시장가")
VALIDATION_STATUSES = ("검증완료", "검증중", "미검증")
MODEL_USES = ("공식평가", "독립검증", "한도산출")
PRICING_DECISIONS = ("평가가능", "평가불가")


PRODUCT = TableSpec(
    name="mkt_product", korean="상품 명세", product="PRD-MKT",
    grain="상품 유형 1개당 1행",
    columns=(
        C("product_id", "string", "상품 식별자", nullable=False),
        C("product_name", "text", "상품명", nullable=False),
        C("asset_class", "string", "자산군", nullable=False, allowed=ASSET_CLASSES),
        C("payoff_type", "string", "수익구조", nullable=False, allowed=PAYOFF_TYPES),
        C("underlying", "text", "기초자산", nullable=False),
        C("currency", "string", "표시통화", nullable=False),
        C("settlement", "string", "결제 방식", nullable=False, allowed=SETTLEMENTS),
        C("is_listed", "bool", "장내 여부", nullable=False),
        C("complexity_tier", "int", "복잡도 등급", nullable=False, unit="count",
          min_value=1, max_value=3,
          note="1은 시장가 관측, 3은 모형 의존이 큰 상품이다"),
    ),
    primary_key=("product_id",),
)

PRICING_MODEL = TableSpec(
    name="mkt_pricing_model", korean="평가모형", product="PRD-MKT",
    grain="평가모형 1개당 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("model_name", "text", "모형명", nullable=False),
        C("methodology", "string", "방법론", nullable=False,
          allowed=METHODOLOGIES),
        C("input_factors", "text", "입력 리스크팩터", nullable=False),
        C("validation_status", "string", "검증 상태", nullable=False,
          allowed=VALIDATION_STATUSES),
        C("owner_role", "text", "모형 소유", nullable=False),
        C("last_validation", "date", "직전 검증일", nullable=True),
        C("known_limitation", "text", "알려진 한계", nullable=False),
    ),
    primary_key=("model_id",),
    note="한계를 필수 컬럼으로 둔다. 한계를 적지 않은 모형은 검증받지 않은 모형이다.",
)

PRODUCT_MODEL_MAP = TableSpec(
    name="mkt_product_model_map", korean="상품 평가모형 매핑", product="PRD-MKT",
    grain="상품 x 모형 x 용도 1건당 1행",
    columns=(
        C("product_id", "string", "상품 식별자", nullable=False),
        C("model_id", "string", "모형 식별자", nullable=False),
        C("model_use", "string", "용도", nullable=False, allowed=MODEL_USES),
        C("is_approved", "bool", "승인 여부", nullable=False),
        C("approved_by", "text", "승인 주체", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("product_id", "model_id", "model_use"),
    foreign_keys=(FK(("product_id",), "mkt_product", ("product_id",)),
                  FK(("model_id",), "mkt_pricing_model", ("model_id",))),
)

SPECS: tuple[TableSpec, ...] = (PRODUCT, PRICING_MODEL, PRODUCT_MODEL_MAP)


# ---------------------------------------------------------------- 적재 표
#
# (상품ID, 상품명, 자산군, 수익구조, 기초자산, 통화, 결제, 장내, 복잡도)
_PRODUCTS = (
    ("PRD-IRS", "이자율스왑", "금리", "선형", "CD 91일", "KRW", "현금결제", False, 1),
    ("PRD-KTB", "국고채", "금리", "선형", "국고채 지표물", "KRW", "실물인수도", True, 1),
    ("PRD-BF", "국채선물", "금리", "선형", "국채선물 3년", "KRW", "현금결제", True, 1),
    ("PRD-SWO", "스왑션", "금리", "옵션", "이자율스왑", "KRW", "현금결제", False, 3),
    ("PRD-FXF", "선물환", "외환", "선형", "USD/KRW", "USD", "실물인수도", False, 1),
    ("PRD-FXO", "통화옵션", "외환", "옵션", "USD/KRW", "USD", "현금결제", False, 2),
    ("PRD-EQF", "주가지수선물", "주식", "선형", "KOSPI200", "KRW", "현금결제", True, 1),
    ("PRD-ELS", "주가연계증권", "주식", "구조화", "KOSPI200·S&P500", "KRW",
     "현금결제", False, 3),
    ("PRD-CDS", "신용부도스왑", "신용", "옵션", "회사채 준거자산", "USD",
     "현금결제", False, 2),
    ("PRD-CB", "전환사채", "신용", "구조화", "발행사 주식", "KRW",
     "실물인수도", False, 3),
)

# (모형ID, 모형명, 방법론, 입력 팩터, 검증상태, 소유, 한계)
_MODELS = (
    ("PM-DCF", "무이표커브 할인", "할인현금흐름", "무이표커브", "검증완료",
     "시장리스크관리자", "커브 보간 구간 밖에서는 외삽 가정에 의존한다"),
    ("PM-MTM", "장내 종가", "시장가", "거래소 종가", "검증완료",
     "미들오피스", "거래 부진 종목은 종가가 체결가를 대표하지 못한다"),
    ("PM-BLK", "블랙 모형", "해석해", "무이표커브·내재변동성", "검증완료",
     "시장리스크관리자", "변동성 스마일을 단일 변동성으로 압축한다"),
    ("PM-GK", "가먼-콜하겐", "해석해", "양 통화 커브·내재변동성", "검증완료",
     "시장리스크관리자", "선도환율 고정 가정을 쓴다"),
    ("PM-HW", "헐-화이트 1요인", "격자", "무이표커브·스왑션 변동성", "검증중",
     "시장리스크관리자", "단일 요인이라 곡선 비평행 변형을 담지 못한다"),
    ("PM-MC", "몬테카를로 경로", "몬테카를로", "무이표커브·변동성면·상관계수",
     "검증중", "시장리스크관리자", "경로 수에 따른 수치오차가 남는다"),
    ("PM-HZD", "위험강도 모형", "해석해", "신용스프레드커브·회수율", "검증완료",
     "신용리스크관리자", "회수율을 상수로 둔다"),
)

# (상품ID, 모형ID, 용도, 승인여부, 승인주체)
_MAPPINGS = (
    ("PRD-IRS", "PM-DCF", "공식평가", True, "리스크관리위원회"),
    ("PRD-KTB", "PM-MTM", "공식평가", True, "리스크관리위원회"),
    ("PRD-KTB", "PM-DCF", "독립검증", True, "적합성검증담당"),
    ("PRD-BF", "PM-MTM", "공식평가", True, "리스크관리위원회"),
    ("PRD-SWO", "PM-HW", "공식평가", False, None),
    ("PRD-SWO", "PM-BLK", "독립검증", True, "적합성검증담당"),
    ("PRD-FXF", "PM-DCF", "공식평가", True, "리스크관리위원회"),
    ("PRD-FXO", "PM-GK", "공식평가", True, "리스크관리위원회"),
    ("PRD-EQF", "PM-MTM", "공식평가", True, "리스크관리위원회"),
    ("PRD-ELS", "PM-MC", "공식평가", False, None),
    ("PRD-CDS", "PM-HZD", "공식평가", True, "리스크관리위원회"),
    ("PRD-CB", "PM-MC", "독립검증", True, "적합성검증담당"),
)


def build_products() -> pd.DataFrame:
    return pd.DataFrame([{
        "product_id": p[0], "product_name": p[1], "asset_class": p[2],
        "payoff_type": p[3], "underlying": p[4], "currency": p[5],
        "settlement": p[6], "is_listed": bool(p[7]), "complexity_tier": p[8],
    } for p in _PRODUCTS])


def build_pricing_models(*, asof: str) -> pd.DataFrame:
    """검증일은 검증완료 모형에만 붙인다. 검증중·미검증 모형은 NULL이다."""
    rows = []
    for mid, name, method, factors, status, owner, limitation in _MODELS:
        rows.append({
            "model_id": mid, "model_name": name, "methodology": method,
            "input_factors": factors, "validation_status": status,
            "owner_role": owner,
            "last_validation": asof if status == "검증완료" else None,
            "known_limitation": limitation,
        })
    return pd.DataFrame(rows, columns=[c.name for c in PRICING_MODEL.columns])


def build_mappings() -> pd.DataFrame:
    return pd.DataFrame([{
        "product_id": m[0], "model_id": m[1], "model_use": m[2],
        "is_approved": bool(m[3]), "approved_by": m[4],
        "evidence_status": "재량·미규정",
    } for m in _MAPPINGS], columns=[c.name for c in PRODUCT_MODEL_MAP.columns])


def judge_pricing(products: pd.DataFrame, models: pd.DataFrame,
                  mappings: pd.DataFrame) -> pd.DataFrame:
    """상품별 평가 가능 여부.

    공식평가 용도로 승인된 매핑이 있고 그 모형의 검증이 끝났어야 평가가능이다.
    승인만 있고 검증이 끝나지 않은 모형은 평가 근거가 되지 못한다.
    """
    mdl = models.set_index("model_id")
    rows = []
    for _, p in products.iterrows():
        pid = str(p["product_id"])
        official = mappings[(mappings["product_id"] == pid)
                            & (mappings["model_use"] == "공식평가")]
        approved = official[official["is_approved"] == True]     # noqa: E712
        if approved.empty:
            decision, reason, model_id = "평가불가", "승인된 공식평가 모형이 없다", None
        else:
            mid = str(approved.iloc[0]["model_id"])
            status = str(mdl.loc[mid, "validation_status"]) if mid in mdl.index else "미검증"
            if status != "검증완료":
                decision, reason = "평가불가", f"공식평가 모형 {mid}의 검증 상태가 {status}다"
            else:
                decision, reason = "평가가능", f"공식평가 모형 {mid} 검증완료"
            model_id = mid
        rows.append({
            "product_id": pid, "product_name": str(p["product_name"]),
            "complexity_tier": int(p["complexity_tier"]),
            "official_model": model_id, "decision": decision, "reason": reason,
        })
    return pd.DataFrame(rows, columns=["product_id", "product_name",
                                       "complexity_tier", "official_model",
                                       "decision", "reason"])


def build_product_master(*, asof: str
                         ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """상품·모형 원장 3장을 만든다. (원장, 평가불가 상품 목록)을 돌려준다."""
    products = build_products()
    models = build_pricing_models(asof=asof)
    mappings = build_mappings()
    judged = judge_pricing(products, models, mappings)
    unpriced = [f"{r['product_id']} {r['product_name']}: {r['reason']}"
                for _, r in judged.iterrows() if r["decision"] == "평가불가"]
    return ({"mkt_product": products,
             "mkt_pricing_model": models,
             "mkt_product_model_map": mappings}, unpriced)
