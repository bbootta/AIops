"""내부등급법 추정 모수 원장 (IRB-P001).

이 패키지의 추정 엔진은 규제 수치를 한 개도 갖지 않는다. 하한·관측기간·
적용범위·할인율은 전부 이 모듈의 빌더가 적재하고 엔진은 원장을 인자로 받는다.
엔진 본문이나 기본값에 숫자가 있으면 화면에 나오지 않고, 화면에 없으면 검증도
결재도 그 값을 보지 못한다.

원장 네 장

  ``crm_input_floor``        리스크 추정치 하한 (PD·LGD·CCF)
  ``crm_irb_scope``          자산군별 허용 산출방법 (표준방법·FIRB·AIRB)
  ``crm_estimation_param``   관측기간 최소요건과 내부기준 모수
  ``crm_lgd_discount_rate``  회수 할인율 (세그먼트별)

**하한값의 근거 등급이 서로 다르다.** 개정 전 [별표 3] 2018.6.30본은 원문을
직접 읽었고(``개정전판본원문``), 바젤Ⅲ 최종안 하한은 2019.4.26 개정 사전예고
신구대비표와 금융감독원 워크숍 자료에서 얻었다(``사전예고안원문``·``2차자료``).
**확정 시행세칙 [별표 3] 최종안 반영본은 아직 확보하지 못했다.** 확정본을
얻으면 ``framework_version='바젤3최종안'`` 행의 근거등급만 올리면 된다.

**값이 비어 있는 것도 산출물이다.** 자료가 칸을 비워 둔 항목
(주거용주택담보 무담보 LGD 하한)과 자료끼리 어긋나는 항목(대기업 AIRB 제외
매출 기준액 6천억 대 7천억)은 값을 채우지 않는다. ``floor_status``·
``evidence_status``가 그 사실을 들고 있고, 엔진은 NULL을 만나면 조용히 하한
없이 가지 않고 경고를 남긴다.
"""

from __future__ import annotations

import warnings

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

__all__ = [
    "IRB_EVIDENCE_STATUS", "INPUT_SOURCES", "FRAMEWORK_VERSIONS",
    "IRB_EXPOSURE_CLASSES", "FLOOR_COLLATERAL_TYPES", "FLOOR_PARAMETERS",
    "FLOOR_STATUS", "IRB_METHODS", "PARAM_CODES", "DISCOUNT_BASES",
    "INPUT_FLOOR", "IRB_SCOPE", "ESTIMATION_PARAM", "LGD_DISCOUNT_RATE",
    "PARAM_TABLES",
    "ParamWarning",
    "build_crm_input_floor", "build_crm_irb_scope",
    "build_crm_estimation_param", "build_crm_lgd_discount_rate",
    "build_estimation_param_ledgers",
    "floor_value", "param_value", "param_text", "discount_rate_for",
    "approve_estimation_param", "approve_discount_rate",
    "unapproved_internal_params", "assign_irb_method",
]


class ParamWarning(UserWarning):
    """모수 원장에 값이 없어 조정을 건너뛴다는 경고.

    조용히 기본값을 쓰면 화면에는 숫자가 보이는데 그 숫자의 출처가 없다.
    경고를 남기고 건너뛰어야 산출물에 '적용하지 않았다'가 남는다.
    """


# ---------------------------------------------------------------- 어휘

# alm.params.EVIDENCE_STATUS를 잇되 내부등급법 자료 사정에 맞는 두 값을 더한다.
# '개정전판본원문'은 2018.6.30본 원문을 직접 읽었으나 최종안 반영본이 아니라는
# 뜻이고, '사전예고안원문'은 감독당국이 낸 개정안 원문이지만 확정본과의 문언
# 일치를 확인하지 못했다는 뜻이다. 둘을 '원문확인'으로 뭉치면 확정본을 본 값과
# 구분이 사라진다.
# '내부추정(합성관측)'은 규정도 실측도 아닌 값이다. 관측 계열 자체가 합성이라
# 그것으로 낸 추정치는 실측 관측으로 낸 값과 같은 칸에 둘 수 없다. 회수 할인율의
# CAPM 추정이 이 상태로 들어온다.
IRB_EVIDENCE_STATUS: tuple[str, ...] = (
    "원문확인", "개정전판본원문", "사전예고안원문", "2차자료",
    "내부추정(합성관측)", "업계관행", "추론", "재량·미규정", "미확인")
# 값의 효력 근거. '규정'은 법령·감독규정이 정한 것, '내부기준'은 내규가 정하며
# 승인기구 의결이 효력 요건, '업계참고'는 타행 실측으로 승인 판단의 참고자료다.
INPUT_SOURCES: tuple[str, ...] = ("규정", "내부기준", "업계참고")
FRAMEWORK_VERSIONS: tuple[str, ...] = ("별표3_2018-06-30", "바젤3최종안")
# 자산군 어휘. catalog.ASSET_CLASSES에 적격회전거래 세분과 주식·전체를 더한다.
# 최종안 116의7.라가 적격회전거래를 transactor/revolver로 나누면서 PD 하한이
# 갈라졌으므로(0.05% 대 0.1%) 한 칸으로는 표현할 수 없다.
IRB_EXPOSURE_CLASSES: tuple[str, ...] = (
    "sovereign", "bank", "corporate", "retail_other", "residential_mortgage",
    "qrre_transactor", "qrre_revolver", "equity", "hvcre", "all")
FLOOR_COLLATERAL_TYPES: tuple[str, ...] = (
    "해당없음", "financial", "receivables", "real_estate", "other_physical")
FLOOR_PARAMETERS: tuple[str, ...] = (
    "pd_floor", "lgd_floor_unsecured", "lgd_floor_secured",
    "ccf_floor_multiplier")
# 하한 행의 상태. NULL 값 하나로는 '자료를 못 봤다'와 '규정이 적용을 면제했다'가
# 구분되지 않는다. 정부 익스포저의 CCF 하한 면제가 그 사례다.
FLOOR_STATUS: tuple[str, ...] = ("확정", "미확인", "적용제외")
IRB_METHODS: tuple[str, ...] = ("표준방법", "FIRB", "AIRB")
DISCOUNT_BASES: tuple[str, ...] = (
    "무위험이자율", "약정금리", "가중평균자본비용", "자기자본비용", "미정")

PARAM_CODES: tuple[str, ...] = (
    "obs_years_min_pd_corporate", "obs_years_min_pd_retail",
    "obs_years_min_lgd_corporate", "obs_years_min_lgd_retail",
    "obs_years_min_ccf_corporate", "obs_years_min_ccf_retail",
    "review_interval_months",
    "airb_exclusion_revenue_krw",
    "downturn_year_quantile", "moc_confidence_level",
    "moc_data_quality_addon", "moc_model_quality_addon",
    "moc_representativeness_addon", "moc_aggregation",
    "lgd_censoring_treatment", "pd_seasoning_addon_retail",
    "backtest_ci_level", "backtest_significance_level",
    "psi_threshold_warn", "psi_threshold_fail",
    "capm_market_return",
)

# 원문 파일 위치를 문자열에 남긴다. 인용만 있고 파일이 없으면 재현이 안 된다.
_SEC18 = ("은행업감독업무시행세칙 [별표 3] 신용·운영리스크 위험가중자산에 대한 "
          "자기자본비율 산출기준 (개정 2018.6.30). "
          "docs/primary_sources/별표3_내부등급법_추정검증_발췌.txt")
_PRE19 = ("은행업감독업무시행세칙 개정 사전예고 [별표 3] 신구대비표 "
          "(금융감독원, 2019.4.26, 바젤Ⅲ 규제개혁 마무리과제). "
          "확정 시행세칙과의 문언 일치는 미확인")
_WS18 = ("금융감독원 「바젤Ⅲ 규제개정 주요내용 및 감독계획 · 신용리스크」 "
         "은행 리스크관리 발전 워크숍 자료 (2018.4.12) p.19 리스크 요소 하한. "
         "자료 첫 장에 '원문이 우선됨' 표기")
_JB23 = ("JB금융지주 바젤Ⅲ 최종안 신용리스크 요건정의서 (2023.11.21). "
         "사내 요건정의서이며 2차자료")
_UNCONFIRMED = ("확정 시행세칙 [별표 3] 최종안 반영본을 확보하지 못했다. "
                "확정본을 얻으면 근거등급만 올린다")


# ---------------------------------------------------------------- 하한 원장

INPUT_FLOOR = TableSpec(
    name="crm_input_floor", korean="리스크 추정치 하한", product="PRD-RWA",
    grain="규제판본 × 모수 × 자산군 × 담보유형 1건당 1행",
    columns=(
        C("framework_version", "string", "규제판본", nullable=False,
          allowed=FRAMEWORK_VERSIONS),
        C("parameter", "string", "모수", nullable=False,
          allowed=FLOOR_PARAMETERS),
        C("exposure_class", "string", "자산군", nullable=False,
          allowed=IRB_EXPOSURE_CLASSES),
        C("collateral_type", "string", "담보유형", nullable=False,
          allowed=FLOOR_COLLATERAL_TYPES,
          note="담보와 무관한 하한은 '해당없음'. PK 컬럼이라 NULL을 둘 수 없다"),
        C("floor_value", "float", "하한값", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="NULL은 floor_status가 설명한다. 미확인이면 엔진은 경고를 "
               "남기고 하한을 적용하지 않으며 그 사실을 산출 결과에 싣는다"),
        C("floor_status", "string", "하한 상태", nullable=False,
          allowed=FLOOR_STATUS),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("framework_version", "parameter", "exposure_class",
                 "collateral_type"),
    note="추정 엔진에는 하한 상수가 한 개도 없다. 전부 이 원장에서 읽는다.",
)


def build_crm_input_floor() -> pd.DataFrame:
    """하한 원장을 적재한다. 이 함수가 곧 규제표 등재 프로세스다."""
    rows: list[dict] = []

    def add(fw, param, cls, coll, value, status, cite, ev, note=None):
        rows.append({"framework_version": fw, "parameter": param,
                     "exposure_class": cls, "collateral_type": coll,
                     "floor_value": value, "floor_status": status,
                     "citation": cite, "evidence_status": ev, "note": note})

    # ---- 개정 전 판본 (2018.6.30) ----
    for cls in ("sovereign", "bank", "corporate", "retail_other",
                "residential_mortgage"):
        add("별표3_2018-06-30", "pd_floor", cls, "해당없음", 0.0003, "확정",
            f"{_SEC18} 123.·131. PD 하한 0.03%", "개정전판본원문")
    add("별표3_2018-06-30", "pd_floor", "all", "해당없음", 1.0, "확정",
        f"{_SEC18} 123. 부도자산 PD 100%", "개정전판본원문",
        note="부도자산은 자산군과 무관하게 100%")
    add("별표3_2018-06-30", "lgd_floor_secured", "residential_mortgage",
        "real_estate", 0.10, "확정",
        f"{_SEC18} 185.가(1) 단서. 주거용주택담보는 장기평균 LGD 또는 10% 중 "
        "높은 값을 하한으로 한다", "개정전판본원문")

    # ---- 바젤Ⅲ 최종안 ----
    # PD 하한. 사전예고안 123.(기업·정부)·131.(소매·적격회전거래) 문언과
    # 워크숍 자료 하한표가 일치한다.
    _pd_final = (
        ("sovereign", 0.0003, "123. 정부 익스포져 PD 하한 0.03%"),
        ("corporate", 0.0005, "123. 기업 등 익스포져 PD 하한 0.05%"),
        ("bank", 0.0005, "123. 기업 등 익스포져 PD 하한 0.05%"),
        ("retail_other", 0.0005, "131. 소매 익스포져 PD 하한 0.05%"),
        ("residential_mortgage", 0.0005, "131. 소매 익스포져 PD 하한 0.05%"),
        ("qrre_transactor", 0.0005,
         "131. 소매 PD 하한 0.05%. 116의7.라의 transactor(표준방법 39.나 "
         "요건 충족 거래)"),
        ("qrre_revolver", 0.0010,
         "131. 단서. 적격회전거래 중 리볼빙(revolver) PD 하한 0.1%"),
    )
    for cls, val, clause in _pd_final:
        add("바젤3최종안", "pd_floor", cls, "해당없음", val, "확정",
            f"{_PRE19} {clause}. 교차확인: {_WS18}", "사전예고안원문",
            note=_UNCONFIRMED)
    add("바젤3최종안", "pd_floor", "all", "해당없음", 1.0, "확정",
        f"{_PRE19} 123. 부도자산 100%", "사전예고안원문", note=_UNCONFIRMED)

    # LGD 하한(무담보). 워크숍 자료 하한표. JB 검증매뉴얼이 주거용 하한의
    # 조문 위치를 132.가로 적어 교차확인된다.
    _lgd_unsec = (
        ("corporate", 0.25, "기업 무담보 LGD 하한 25%"),
        ("retail_other", 0.30, "기타소매 무담보 LGD 하한 30%"),
        ("qrre_transactor", 0.50, "적격회전거래(일반) 무담보 LGD 하한 50%"),
        ("qrre_revolver", 0.50, "적격회전거래(리볼빙) 무담보 LGD 하한 50%"),
    )
    for cls, val, clause in _lgd_unsec:
        add("바젤3최종안", "lgd_floor_unsecured", cls, "해당없음", val, "확정",
            f"{_WS18} {clause}. 교차확인: {_JB23}", "2차자료",
            note=_UNCONFIRMED)
    add("바젤3최종안", "lgd_floor_unsecured", "residential_mortgage",
        "해당없음", None, "미확인",
        f"{_WS18} 하한표의 소매 주담대 무담보 칸이 '-'로 비어 있다",
        "미확인",
        note="무담보 주거용주택담보라는 조합에 어떤 하한이 걸리는지 원문 "
             "미확인이다. 값을 지어내지 않는다")

    # LGD 하한(담보). 워크숍 자료 p.19 및 부분담보 가중평균 산식(p.22).
    add("바젤3최종안", "lgd_floor_secured", "residential_mortgage",
        "real_estate", 0.05, "확정",
        f"{_WS18} 소매 주담대 담보 LGD 하한 10%→5%. 조문 위치는 132.가"
        f" ({_JB23} 검증매뉴얼 교차확인)", "2차자료", note=_UNCONFIRMED)
    for cls in ("corporate", "retail_other"):
        for coll, val, clause in (
                ("financial", 0.00, "금융담보 0%"),
                ("receivables", 0.10, "매출채권 10%"),
                ("real_estate", 0.10, "상업용·주거용 부동산 10%"),
                ("other_physical", 0.15, "기타 물적담보 15%")):
            add("바젤3최종안", "lgd_floor_secured", cls, coll, val, "확정",
                f"{_WS18} 기업 및 기타소매 담보 LGD 하한 · {clause}",
                "2차자료", note=_UNCONFIRMED)

    # CCF 하한. 상수가 아니라 표준방법 CCF에 곱하는 배수다. 20%는 40% 버킷의
    # 인스턴스값이고, 취소가능(10%) 버킷에 20%를 걸면 4배 과대한 하한이 된다.
    add("바젤3최종안", "ccf_floor_multiplier", "all", "해당없음", 0.50, "확정",
        f"{_PRE19} 자체추정 신용환산율은 표준방법 적용 신용환산율의 50%를 "
        f"하한으로 한다. 교차확인: {_JB23}", "사전예고안원문",
        note="하한 = 표준방법 CCF × 0.5. 40% 버킷에서 20%가 나오는 것이고 "
             "20%는 상수가 아니다")
    add("바젤3최종안", "ccf_floor_multiplier", "sovereign", "해당없음", None,
        "적용제외",
        f"{_JB23} 정부 익스포저는 자체추정 CCF 하한 적용 대상에서 제외",
        "2차자료",
        note="값이 NULL인 이유가 '미확인'이 아니라 '적용제외'다. "
             "floor_status가 두 사건을 가른다")

    return _cast_floor(pd.DataFrame(rows))


def _cast_floor(df: pd.DataFrame) -> pd.DataFrame:
    df["floor_value"] = pd.to_numeric(df["floor_value"],
                                      errors="coerce").astype("float64")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 적용범위

IRB_SCOPE = TableSpec(
    name="crm_irb_scope", korean="내부등급법 적용범위", product="PRD-RWA",
    grain="규제판본 × 자산군 1건당 1행",
    columns=(
        C("framework_version", "string", "규제판본", nullable=False,
          allowed=FRAMEWORK_VERSIONS),
        C("exposure_class", "string", "자산군", nullable=False,
          allowed=IRB_EXPOSURE_CLASSES),
        C("sa_allowed", "bool", "표준방법 가능", nullable=False),
        C("firb_allowed", "bool", "기본내부등급법 가능", nullable=False),
        C("airb_allowed", "bool", "고급내부등급법 가능", nullable=True,
          note="NULL은 조건부다. 조건은 condition 컬럼이 들고 있고 판정은 "
               "차주 단위 모수(매출액 등)를 봐야 난다"),
        C("condition", "text", "조건", nullable=True),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "exposure_class"),
    note="주식 IRB 금지와 대기업·금융기관 AIRB 금지를 원장이 강제한다. "
         "판정 로직이 소스에 있으면 규제판본이 바뀔 때 코드를 고쳐야 한다.",
)


def build_crm_irb_scope() -> pd.DataFrame:
    """적용범위 원장을 적재한다."""
    rows: list[dict] = []

    def add(fw, cls, sa, firb, airb, cond, cite, ev):
        rows.append({"framework_version": fw, "exposure_class": cls,
                     "sa_allowed": sa, "firb_allowed": firb,
                     "airb_allowed": airb, "condition": cond,
                     "citation": cite, "evidence_status": ev})

    # 개정 전에는 주식도 내부모형법이 있었고 대기업 AIRB 제한이 없었다.
    for cls in ("sovereign", "bank", "corporate"):
        add("별표3_2018-06-30", cls, True, True, True, None,
            f"{_SEC18} 177. 고급내부등급법은 기업 등 익스포져의 LGD·EAD도 "
            "은행이 추정한다", "개정전판본원문")
    for cls in ("retail_other", "residential_mortgage"):
        add("별표3_2018-06-30", cls, True, False, True,
            "소매는 자산군별 PD·LGD·EAD를 모두 은행이 추정한다(FIRB 구분 없음)",
            f"{_SEC18} 177.", "개정전판본원문")
    add("별표3_2018-06-30", "equity", True, True, True,
        "제7관 주식 등 익스포져 내부모형법", f"{_SEC18} 제5관 제7목",
        "개정전판본원문")

    # 최종안
    add("바젤3최종안", "equity", True, False, False,
        "주식 익스포져는 내부등급법 적용 불가. 표준방법만 적용",
        f"{_PRE19} 115.라 및 제7관(주식 등 익스포져 내부모형법 최소요건) 삭제. "
        f"교차확인: {_WS18} p.18", "사전예고안원문")
    add("바젤3최종안", "bank", True, True, False,
        "은행·증권회사·기타 금융기관(보험 포함)은 고급내부등급법 적용 불가",
        f"{_PRE19} 115.마. 교차확인: {_WS18} p.18", "사전예고안원문")
    add("바젤3최종안", "corporate", True, True, None,
        "최근 3년 평균 연간 매출액이 기준액을 초과하는 기업(동 기업집단 소속 "
        "포함)은 고급내부등급법 적용 불가. 기준액은 crm_estimation_param의 "
        "airb_exclusion_revenue_krw이며 자료가 어긋나 미확인이다",
        f"{_PRE19} 115.마. 교차확인: {_WS18} p.18", "사전예고안원문")
    add("바젤3최종안", "hvcre", True, True, None,
        "특수금융 중 HVCRE는 국가재량. 최소요건 충족 시 허용하되 별도 상관계수",
        f"{_WS18} p.18. 국내 재량 행사 여부 미확인", "2차자료")
    for cls in ("retail_other", "residential_mortgage", "qrre_transactor",
                "qrre_revolver"):
        add("바젤3최종안", cls, True, False, True,
            "소매는 자산군별 PD·LGD·EAD를 모두 은행이 추정한다",
            f"{_PRE19} 131. 소매 익스포져. 최종안이 소매의 자체추정 구조를 "
            "바꿨다는 문언은 확인되지 않는다", "사전예고안원문")
    add("바젤3최종안", "sovereign", True, True, True,
        "감독당국이 제시한 AIRB 제외 목록(주식·대기업·은행·금융기관)에 정부가 "
        "없다는 사실에서 세운 추론이다. 조문에서 직접 확인하지 못했다",
        f"{_WS18} p.18 적용범위 제한 목록", "추론")

    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 추정 모수

ESTIMATION_PARAM = TableSpec(
    name="crm_estimation_param", korean="추정 모수", product="PRD-RWA",
    grain="모수 코드 1건당 1행",
    columns=(
        C("param_code", "string", "모수 코드", nullable=False,
          allowed=PARAM_CODES),
        C("param_value", "float", "값", nullable=True,
          unit="param_unit 컬럼 참조",
          note="NULL은 '규정이 정하지 않았고 내부기준도 승인 전'이다. "
               "엔진은 NULL을 만나면 그 조정을 건너뛰고 경고를 남긴다"),
        C("param_text", "string", "값(문자)", nullable=True,
          note="산식이 아니라 방식을 고르는 모수. 집계방식·관측중단 처리 등"),
        C("param_unit", "string", "단위", nullable=False,
          allowed=("years", "months", "ratio", "KRW", "code")),
        C("input_source", "string", "값의 근거", nullable=False,
          allowed=INPUT_SOURCES),
        C("scope", "text", "적용 범위", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("framework_version", "string", "규제판본", nullable=False,
          allowed=FRAMEWORK_VERSIONS),
        C("reference_value", "float", "참고치", nullable=True,
          unit="param_unit 컬럼 참조",
          note="타행 실측·문헌값. 승인 판단의 참고자료이며 엔진은 읽지 않는다"),
        C("reference_citation", "text", "참고치 근거", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approval_date", "date", "승인일", nullable=True),
        C("approval_body", "string", "승인기구", nullable=True),
    ),
    primary_key=("param_code",),
    note="내부기준 행은 param_value가 비어 있고 승인자·승인일도 비어 있다. "
         "비어 있음이 화면에 드러나는 것이 산출물이다.",
)

_INTERNAL = ("규정이 수치를 주지 않는다. 내규가 정하는 내부기준이며 "
             "승인기구 의결이 효력 요건이다")


def build_crm_estimation_param() -> pd.DataFrame:
    """추정 모수 원장을 적재한다.

    관측기간 최소요건은 개정 전 판본의 값(5년·7년)이다. 최종안이 183·187·193을
    개정했으나 관측기간 연수 자체가 바뀌었다는 문언은 어느 자료에서도 확인되지
    않았다. 그래서 값을 그대로 두고 ``framework_version='별표3_2018-06-30'``,
    ``evidence_status='개정전판본원문'``으로 표시한다. 최종안 반영본을 얻으면
    이 행만 갈아끼운다.
    """
    rows: list[dict] = []

    def reg(code, value, unit, scope, cite):
        rows.append({
            "param_code": code, "param_value": value, "param_text": None,
            "param_unit": unit, "input_source": "규정", "scope": scope,
            "citation": cite, "evidence_status": "개정전판본원문",
            "framework_version": "별표3_2018-06-30",
            "reference_value": None, "reference_citation": None,
            "approved_by": None, "approval_date": None,
            "approval_body": None})

    def internal(code, unit, scope, cite, ref=None, ref_cite=None,
                 framework="바젤3최종안"):
        rows.append({
            "param_code": code, "param_value": None, "param_text": None,
            "param_unit": unit, "input_source": "내부기준", "scope": scope,
            "citation": cite, "evidence_status": "재량·미규정",
            "framework_version": framework,
            "reference_value": ref, "reference_citation": ref_cite,
            "approved_by": None, "approval_date": None,
            "approval_body": None})

    reg("obs_years_min_pd_corporate", 5.0, "years",
        "기업 등 익스포져 PD 추정의 최소 관측기간",
        f"{_SEC18} 182.라·마. 사전예고 신구대비표에서도 '현행과 같음'")
    reg("obs_years_min_pd_retail", 5.0, "years",
        "소매 익스포져 장기평균 PD 추정의 최소 관측기간",
        f"{_SEC18} 183.나. 사전예고 신구대비표에서도 유지")
    reg("obs_years_min_lgd_corporate", 7.0, "years",
        "기업 등 익스포져 LGD 추정의 최소 관측기간(AIRB)", f"{_SEC18} 186.")
    reg("obs_years_min_lgd_retail", 5.0, "years",
        "소매 익스포져 LGD 추정의 최소 관측기간", f"{_SEC18} 187.가")
    reg("obs_years_min_ccf_corporate", 7.0, "years",
        "기업 등 익스포져 EAD·CCF 추정의 최소 관측기간(AIRB)", f"{_SEC18} 195.")
    reg("obs_years_min_ccf_retail", 5.0, "years",
        "소매 익스포져 EAD·CCF 추정의 최소 관측기간", f"{_SEC18} 196.")
    reg("review_interval_months", 12.0, "months",
        "추정치 적정성 점검과 사후검증의 최대 주기",
        f"{_SEC18} 179.나 · 193.마 · 203.가 '연 1회 이상'")

    # 자료가 어긋나는 항목. 두 후보를 근거와 함께 남기고 값은 비운다.
    rows.append({
        "param_code": "airb_exclusion_revenue_krw", "param_value": None,
        "param_text": None, "param_unit": "KRW", "input_source": "규정",
        "scope": "고급내부등급법 적용 금지 대기업 판정의 연간 매출액 기준액",
        "citation": (
            f"자료가 어긋난다. ① {_WS18} p.18은 '연결기준 연간 매출액 5억 유로"
            "(6천억원) 이상'. ② {jb} §I는 '연간 매출액 7천억원 초과'. "
            "금액도 부등호도 다르다. 확정 시행세칙 원문 미확보"
        ).format(jb=_JB23),
        "evidence_status": "미확인", "framework_version": "바젤3최종안",
        "reference_value": None,
        "reference_citation": "후보 ① 600,000,000,000원(이상) ② 700,000,000,000원(초과)",
        "approved_by": None, "approval_date": None, "approval_body": None})

    internal("downturn_year_quantile", "ratio",
             "경기침체 연도 식별 기준. 연도별 포트폴리오 부도율이 이 분위 이상인 "
             "해를 침체기로 본다",
             f"{_SEC18} 185.가·나는 '평균보다 상당히 높은 손실발생기간'이라고만 "
             f"적고 기간의 정의를 주지 않는다. {_INTERNAL}")
    internal("moc_confidence_level", "ratio",
             "통계적 불확실성 MoC의 신뢰수준. 추정 표본이 작을수록 구간이 넓어져 "
             "MoC가 커진다",
             f"{_SEC18} 181.은 '보수적으로 조정' '조정폭 확대'만 정하고 크기를 "
             f"주지 않는다. {_INTERNAL}")
    internal("moc_data_quality_addon", "ratio",
             "데이터 품질 결함에 대한 MoC 가산율(상대)",
             f"{_SEC18} 181. {_INTERNAL}")
    internal("moc_model_quality_addon", "ratio",
             "모형 품질 결함에 대한 MoC 가산율(상대)",
             f"{_SEC18} 181. {_INTERNAL}")
    internal("moc_representativeness_addon", "ratio",
             "표본 대표성 결함에 대한 MoC 가산율(상대). 180. 대표성 판정 결과와 "
             "연동한다",
             f"{_SEC18} 180.·181. {_INTERNAL}")
    rows.append({
        "param_code": "moc_aggregation", "param_value": None,
        "param_text": None, "param_unit": "code", "input_source": "내부기준",
        "scope": "세 원천(데이터품질·모형품질·대표성) MoC의 합산 방식. "
                 "'단순합' 또는 '제곱합'",
        "citation": f"{_SEC18} 181.은 합산 방식을 정하지 않는다. {_INTERNAL}",
        "evidence_status": "재량·미규정", "framework_version": "바젤3최종안",
        "reference_value": None, "reference_citation": None,
        "approved_by": None, "approval_date": None, "approval_body": None})
    rows.append({
        "param_code": "lgd_censoring_treatment", "param_value": None,
        "param_text": None, "param_unit": "code", "input_source": "내부기준",
        "scope": "회수 미종료 부도건(관측중단)의 처리. '제외' 또는 '보수적포함'",
        "citation": (
            f"{_SEC18} 184.·185.는 관측중단 처리를 정하지 않는다. 완료된 "
            "워크아웃만 쓰면 LGD가 과소 추정된다는 업계 판정이 있으나 규정이 "
            f"아니다. {_INTERNAL}"),
        "evidence_status": "재량·미규정", "framework_version": "바젤3최종안",
        "reference_value": None,
        "reference_citation": "우리금융지주 LGD 적합성 검증 서식(업계관행)은 "
                              "미완료 워크아웃을 포함한다",
        "approved_by": None, "approval_date": None, "approval_body": None})
    internal("pd_seasoning_addon_retail", "ratio",
             "기간경과효과가 있는 장기 소매 자산군의 PD 보수적 마진",
             f"{_SEC18} 183.라는 '적절한 보수적 마진을 추가'라고만 적고 크기를 "
             f"주지 않는다. {_INTERNAL}")
    internal("backtest_ci_level", "ratio",
             "사후검증 예상 부도율 범위(신뢰구간)의 신뢰수준",
             f"{_SEC18} 203.가는 '예상 부도율 범위 내'를 요구하나 범위의 정의와 "
             f"신뢰수준을 주지 않는다. {_INTERNAL}")
    internal("backtest_significance_level", "ratio",
             "등급별 이항검정의 유의수준",
             f"{_SEC18} 203. {_INTERNAL}")
    internal("psi_threshold_warn", "ratio",
             "대표성 판정의 PSI 경고 임계",
             f"{_SEC18} 180.은 대표성 입증을 요구하나 지표와 임계를 주지 "
             f"않는다. {_INTERNAL}")
    internal("psi_threshold_fail", "ratio",
             "대표성 판정의 PSI 불합격 임계",
             f"{_SEC18} 180. {_INTERNAL}")
    # 회수 할인율을 CAPM으로 추정할 때 관측으로 대체할 수 없는 유일한 입력이다.
    # R_f는 국고채 3년 관측 평균, 베타는 초과수익률 회귀로 나오지만 R_M은
    # 지표 원장의 KOSPI가 표류항 없는 평균회귀 계열이라 실현 평균이 0 부근이고
    # R_M − R_f 가 구조적으로 음수가 된다. 값을 지어내지 않고 비워 둔다.
    internal("capm_market_return", "ratio",
             "CAPM 시장수익률 R_M (연율). 회수 할인율 k_e = R_f + beta·(R_M − R_f)"
             "의 입력이며 승인 전에는 '전체' 회수유형 할인율이 비고 그 세그먼트 "
             "LGD가 산출불가로 남는다",
             f"{_SEC18} 184.(1)은 '회수기간에 따른 할인효과'만 정하고 할인율의 "
             f"산식·수준을 주지 않는다. {_INTERNAL}",
             ref_cite=(
                 "우리금융지주 적합성 검증 서식은 KOSPI 일별 로그수익률의 연도별 "
                 "평균을 R_M으로 쓰고 2003~2014 산술평균으로 자기자본비용 "
                 "11.22%를 냈다. 베타를 공시하지 않아 그 서식에서 R_M을 역산할 "
                 "수 없으므로 참고치 칸을 비운다"))

    df = pd.DataFrame(rows)
    df["param_value"] = pd.to_numeric(df["param_value"],
                                      errors="coerce").astype("float64")
    df["reference_value"] = pd.to_numeric(df["reference_value"],
                                          errors="coerce").astype("float64")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 할인율

LGD_DISCOUNT_RATE = TableSpec(
    name="crm_lgd_discount_rate", korean="회수 할인율", product="PRD-RWA",
    grain="기준일 × 세그먼트 × 회수유형 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("recovery_scope", "string", "회수유형", nullable=False,
          allowed=("전체", "무위험회수"),
          note="예적금 상계처럼 회수 불확실성이 없는 회수와 나머지를 나눈다. "
               "하나의 할인율로 묶으면 회수 타이밍이 다른 세그먼트 간 LGD "
               "서열이 왜곡된다"),
        C("discount_rate", "float", "할인율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="NULL이면 엔진은 그 세그먼트 LGD 산출을 건너뛰고 경고를 "
               "남긴다. 조용히 기본값을 쓰지 않는다"),
        C("basis", "string", "산출 근거", nullable=False,
          allowed=DISCOUNT_BASES),
        C("rf_source", "text", "무위험이자율 출처", nullable=True),
        C("beta_source", "text", "베타 출처", nullable=True),
        C("estimation_period", "text", "산출대상기간", nullable=True),
        C("input_source", "string", "값의 근거", nullable=False,
          allowed=INPUT_SOURCES),
        C("reference_value", "float", "참고치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("reference_citation", "text", "참고치 근거", nullable=True),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("approved_by", "string", "승인자", nullable=True),
        C("approval_date", "date", "승인일", nullable=True),
    ),
    primary_key=("asof", "segment", "recovery_scope"),
    note="[별표 3] 184.는 '할인효과를 고려할 것'까지만 정하고 값·산식·세그먼트 "
         "구분을 주지 않는다. 전건 값이 비어 있고 승인자도 비어 있다.",
)

_DISC_CITE = (
    f"{_SEC18} 184.(1)은 '회수기간에 따른 할인효과'를 고려하라고만 정하고 "
    "할인율의 수준·산식·세그먼트 구분을 주지 않는다. 전부 내부기준이며 "
    "승인기구 의결이 효력 요건이다")
# 타행 실측이다. 우리 은행의 내부기준이 아니므로 discount_rate가 아니라
# reference_value 칸에 넣는다. 엔진은 참고치를 읽지 않는다.
_DISC_REF = (
    "우리금융지주 「V. 리스크 측정요소의 계량화 2. LGD」 적합성 검증 서식. "
    "자기자본비용(CAPM) 방식, R_f는 국고채 3년 만기, R_M은 KOSPI 일별 "
    "로그수익률 연도별 평균, 베타는 Bloomberg 제공. 산출대상기간 2003~2014의 "
    "산술평균으로 예적금담보 4.01%, 예적금 外 11.22%. 타행 실측이며 "
    "본 은행의 내부기준이 아니다")


def build_crm_lgd_discount_rate(
    asof: str,
    segments: tuple[str, ...] = ("corporate", "retail_other",
                                 "residential_mortgage"),
    *,
    rf_source: str | None = None,
    beta_source: str | None = None,
    estimation_period: str | None = None,
) -> pd.DataFrame:
    """할인율 원장을 적재한다. 값은 비어 있다.

    승인된 내부기준이 생기면 :func:`approve_discount_rate`로 값과 승인자를
    채운다. 그 전까지 LGD 추정은 세그먼트별로 '산출불가'로 남는다. 값이 없는데
    0.05를 조용히 쓰면 LGD가 근거 없는 숫자가 되고, 그 숫자가 RWA로 흘러간다.

    ``rf_source``·``beta_source``·``estimation_period``는 추정 절차가 자기 출처를
    미리 적어 두는 칸이다(``discount_capm.build_capm_discount_ledgers``가
    채운다). **넣어도 ``discount_rate``는 그대로 NULL이고 근거 상태도
    '재량·미규정'이다.** 출처를 적는 것과 값을 넣는 것은 다른 사건이고, 값과
    근거 상태는 승인을 거쳐야 바뀐다.
    """
    rows = []
    for seg in segments:
        rows.append({
            "asof": asof, "segment": seg, "recovery_scope": "전체",
            "discount_rate": None, "basis": "미정",
            "rf_source": rf_source, "beta_source": beta_source,
            "estimation_period": estimation_period, "input_source": "내부기준",
            "reference_value": 0.1122, "reference_citation": _DISC_REF,
            "citation": _DISC_CITE, "evidence_status": "재량·미규정",
            "approved_by": None, "approval_date": None})
        rows.append({
            "asof": asof, "segment": seg, "recovery_scope": "무위험회수",
            "discount_rate": None, "basis": "미정",
            "rf_source": rf_source, "beta_source": beta_source,
            "estimation_period": estimation_period, "input_source": "내부기준",
            "reference_value": 0.0401, "reference_citation": _DISC_REF,
            "citation": _DISC_CITE, "evidence_status": "재량·미규정",
            "approved_by": None, "approval_date": None})
    df = pd.DataFrame(rows)
    for col in ("discount_rate", "reference_value"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 조회·승인

def floor_value(floors: pd.DataFrame, *, parameter: str, exposure_class: str,
                framework_version: str = "바젤3최종안",
                collateral_type: str = "해당없음") -> tuple[float | None, str]:
    """하한 조회. ``(값, 상태)``를 돌려준다.

    행 자체가 없으면 원장 결함이므로 ``KeyError``로 멈춘다. 행은 있고 값이
    NULL이면 상태가 이유를 말한다. 두 사건을 같은 방식으로 처리하면 원장 누락이
    조용히 '하한 없음'으로 둔갑한다.
    """
    hit = floors[(floors["framework_version"] == framework_version)
                 & (floors["parameter"] == parameter)
                 & (floors["exposure_class"] == exposure_class)
                 & (floors["collateral_type"] == collateral_type)]
    if hit.empty:
        raise KeyError(
            f"crm_input_floor에 행이 없다: {framework_version}/{parameter}/"
            f"{exposure_class}/{collateral_type}")
    row = hit.iloc[0]
    v = row["floor_value"]
    return (None if pd.isna(v) else float(v)), str(row["floor_status"])


def param_value(param: pd.DataFrame, code: str) -> float | None:
    """수치 모수 조회. 행이 없으면 ``KeyError``, 값이 NULL이면 ``None``."""
    hit = param.loc[param["param_code"] == code, "param_value"]
    if hit.empty:
        raise KeyError(f"crm_estimation_param에 {code!r} 행이 없다")
    v = hit.iloc[0]
    return None if pd.isna(v) else float(v)


def param_text(param: pd.DataFrame, code: str) -> str | None:
    """방식 모수 조회. 행이 없으면 ``KeyError``, 값이 NULL이면 ``None``."""
    hit = param.loc[param["param_code"] == code, "param_text"]
    if hit.empty:
        raise KeyError(f"crm_estimation_param에 {code!r} 행이 없다")
    v = hit.iloc[0]
    return None if (v is None or pd.isna(v)) else str(v)


def discount_rate_for(rates: pd.DataFrame, *, asof: str, segment: str,
                      recovery_scope: str = "전체") -> float | None:
    """할인율 조회. 행이 없으면 ``KeyError``, 값이 NULL이면 ``None``."""
    hit = rates[(rates["asof"] == asof) & (rates["segment"] == segment)
                & (rates["recovery_scope"] == recovery_scope)]
    if hit.empty:
        raise KeyError(
            f"crm_lgd_discount_rate에 행이 없다: {asof}/{segment}/{recovery_scope}")
    v = hit.iloc[0]["discount_rate"]
    return None if pd.isna(v) else float(v)


def approve_estimation_param(param: pd.DataFrame, *, code: str,
                             value: float | None = None,
                             text: str | None = None,
                             approved_by: str, approval_date: str,
                             approval_body: str) -> pd.DataFrame:
    """내부기준 모수에 값과 승인 기록을 넣은 사본을 돌려준다.

    승인은 수기 프로세스다. 이 함수는 그 프로세스가 원장에 남기는 형태를 고정할
    뿐 승인 자체를 만들지 않는다. 승인 기록이 있어야 엔진이 그 모수를 쓴다.
    """
    if code not in set(param["param_code"]):
        raise KeyError(f"crm_estimation_param에 {code!r} 행이 없다")
    if value is None and text is None:
        raise ValueError("value 또는 text 중 하나는 있어야 한다")
    out = param.copy()
    m = out["param_code"] == code
    if out.loc[m, "input_source"].iloc[0] != "내부기준":
        raise ValueError(f"{code}는 내부기준 모수가 아니다. 규정 값은 승인 대상이 "
                         "아니라 원문 확인 대상이다")
    if value is not None:
        out.loc[m, "param_value"] = float(value)
    if text is not None:
        out.loc[m, "param_text"] = str(text)
    out.loc[m, "approved_by"] = approved_by
    out.loc[m, "approval_date"] = approval_date
    out.loc[m, "approval_body"] = approval_body
    return out


def approve_discount_rate(rates: pd.DataFrame, *, asof: str, segment: str,
                          recovery_scope: str, rate: float, basis: str,
                          approved_by: str, approval_date: str,
                          rf_source: str | None = None,
                          beta_source: str | None = None,
                          estimation_period: str | None = None,
                          evidence_status: str | None = None
                          ) -> pd.DataFrame:
    """할인율 행에 값과 승인 기록을 넣은 사본을 돌려준다.

    **할인율 값이 원장에 들어가는 경로는 이 함수 하나다.** 값과 승인자·승인일을
    한 번에 적으므로 승인 없이 값만 들어간 행이 생기지 않는다.
    ``evidence_status``는 그 값이 원문·실측·내부추정 중 무엇인지를 적는 칸이며,
    합성 관측으로 낸 추정치는 '내부추정(합성관측)'으로 들어온다.
    """
    if basis not in DISCOUNT_BASES:
        raise ValueError(f"basis는 {DISCOUNT_BASES} 중 하나여야 한다")
    if evidence_status is not None and evidence_status not in IRB_EVIDENCE_STATUS:
        raise ValueError(f"evidence_status는 {IRB_EVIDENCE_STATUS} 중 하나여야 한다")
    out = rates.copy()
    m = ((out["asof"] == asof) & (out["segment"] == segment)
         & (out["recovery_scope"] == recovery_scope))
    if not m.any():
        raise KeyError(
            f"crm_lgd_discount_rate에 행이 없다: {asof}/{segment}/{recovery_scope}")
    out.loc[m, "discount_rate"] = float(rate)
    out.loc[m, "basis"] = basis
    out.loc[m, "approved_by"] = approved_by
    out.loc[m, "approval_date"] = approval_date
    if rf_source is not None:
        out.loc[m, "rf_source"] = rf_source
    if beta_source is not None:
        out.loc[m, "beta_source"] = beta_source
    if estimation_period is not None:
        out.loc[m, "estimation_period"] = estimation_period
    if evidence_status is not None:
        out.loc[m, "evidence_status"] = evidence_status
    return out


def unapproved_internal_params(param: pd.DataFrame) -> pd.DataFrame:
    """값 또는 승인자가 빈 내부기준 행.

    빈 채로 두는 것이 목적이므로 이 함수는 경고가 아니라 목록을 돌려준다.
    화면과 결재 문서가 '무엇이 아직 승인되지 않았나'를 이 목록으로 적는다.
    """
    internal = param[param["input_source"] == "내부기준"]
    blank = (internal["param_value"].isna() & internal["param_text"].isna())
    return internal[blank | internal["approved_by"].isna()].reset_index(drop=True)


def assign_irb_method(obligors: pd.DataFrame, scope: pd.DataFrame,
                      param: pd.DataFrame, *,
                      framework_version: str = "바젤3최종안") -> pd.DataFrame:
    """차주별 허용 산출방법을 판정한다.

    ``obligors``는 ``obligor_id``·``exposure_class``를 가져야 하고, 매출액
    기준 판정을 하려면 ``annual_revenue``(원, 최근 3년 평균)가 있어야 한다.

    **판정불가를 허용으로 바꾸지 않는다.** 대기업 AIRB 제외 기준액이 미확인이면
    ``airb_allowed``를 NULL로 두고 ``scope_status='기준액미확인'``을 적는다.
    보수적 처리를 원하는 호출자를 위해 ``airb_allowed_conservative``를 함께
    돌려주며 이 컬럼은 판정불가를 False로 본다.
    """
    need = {"obligor_id", "exposure_class"}
    missing = need - set(obligors.columns)
    if missing:
        raise ValueError(f"obligors에 없는 컬럼: {sorted(missing)}")
    sc = scope[scope["framework_version"] == framework_version]
    if sc.empty:
        raise KeyError(f"crm_irb_scope에 {framework_version} 행이 없다")
    threshold = param_value(param, "airb_exclusion_revenue_krw")
    if threshold is None:
        warnings.warn(
            "airb_exclusion_revenue_krw가 비어 있다. 대기업 고급내부등급법 제외 "
            "판정을 하지 않고 판정불가로 남긴다. 자료 두 종의 기준액이 어긋난다",
            ParamWarning, stacklevel=2)

    m = sc.set_index("exposure_class")
    out = obligors[["obligor_id", "exposure_class"]].copy()
    known = out["exposure_class"].isin(m.index)
    if not known.all():
        raise KeyError("crm_irb_scope에 없는 자산군: "
                       f"{sorted(set(out.loc[~known, 'exposure_class']))}")
    out["sa_allowed"] = out["exposure_class"].map(m["sa_allowed"]).astype(bool)
    out["firb_allowed"] = out["exposure_class"].map(m["firb_allowed"]).astype(bool)
    base = out["exposure_class"].map(m["airb_allowed"])
    status = pd.Series("판정완료", index=out.index, dtype=object)
    airb = base.copy()

    cond_idx = base.index[base.isna()]
    if len(cond_idx):
        if threshold is None:
            status.loc[cond_idx] = "기준액미확인"
        elif "annual_revenue" not in obligors.columns:
            status.loc[cond_idx] = "매출액없음"
        else:
            rev = pd.to_numeric(obligors.loc[cond_idx, "annual_revenue"],
                                errors="coerce")
            # 기준액 부등호(이상/초과)도 자료가 어긋난다. 기준액이 승인되면
            # 그 승인 문서가 부등호를 함께 정한다. 여기서는 초과로 둔다.
            judged = rev.notna()
            airb.loc[rev.index[judged]] = ~(rev[judged] > threshold)
            status.loc[rev.index[judged]] = "판정완료"
            status.loc[rev.index[~judged]] = "매출액없음"
    out["airb_allowed"] = airb
    out["scope_status"] = status
    out["airb_allowed_conservative"] = airb.fillna(False).astype(bool)
    out["framework_version"] = framework_version
    out["revenue_threshold"] = threshold
    return out.reset_index(drop=True)


PARAM_TABLES: dict[str, TableSpec] = {
    INPUT_FLOOR.name: INPUT_FLOOR,
    IRB_SCOPE.name: IRB_SCOPE,
    ESTIMATION_PARAM.name: ESTIMATION_PARAM,
    LGD_DISCOUNT_RATE.name: LGD_DISCOUNT_RATE,
}


def build_estimation_param_ledgers(asof: str) -> dict[str, pd.DataFrame]:
    """모수 원장 네 장을 한 번에 만든다."""
    return {
        "crm_input_floor": build_crm_input_floor(),
        "crm_irb_scope": build_crm_irb_scope(),
        "crm_estimation_param": build_crm_estimation_param(),
        "crm_lgd_discount_rate": build_crm_lgd_discount_rate(asof),
    }
