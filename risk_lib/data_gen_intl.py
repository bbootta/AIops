"""권역별 가상 기관 원장과 합성 포트폴리오 생성기 (INST-002).

이 저장소의 표본은 국내 은행 한 곳이었다. 권역이 다른 기관을 붙이는 목적은
화면에 깃발을 더 다는 것이 아니라, 기관 축이 실제로 서로 다른 산출을 담아내는지
파이프라인을 돌려 확인하는 것이다.

익명화의 뜻
------------
"대표적인 금융기관을 익명화한다"를 실존 기관의 수치에서 이름만 지우는 것으로
읽으면 안 된다. 이 저장소는 어떤 실존 기관의 재무수치도 가지고 있지 않으므로,
그것을 재현했다고 적으면 그 줄이 곧 지어낸 값이다.

여기서 쓰는 것은 **유형의 공개된 성격**뿐이다.

  대형 유니버설 뱅크   트레이딩 자산 비중이 크고 국가 분산이 넓다
  지역 은행            주택담보·소매 편중이 크고 트레이딩이 작다
  증권회사             신용 익스포저가 작고 시장·운영 비중이 크다

이 세 줄은 업권 유형의 성격이지 특정 기관의 수치가 아니다. 유형을 모수로 바꾼
자리가 `INST_PROFILE`·`INST_PORTFOLIO_MIX`·`INST_COUNTRY_MIX` 이며, 생성기는
그 원장을 인자로 받는다. 생성기 본문에는 계수가 없다.

모든 합성 행에는 `data_origin='합성'`·`evidence_status='내부기준(합성)'` 이
붙는다. 국내 표본(KR_BANK_01)의 익스포저도 여기 든다. 그 숫자는 여기서 다시
만들지 않고 기존 생성기(`data_gen.generate_portfolio`)의 산출을 그대로 쓰지만,
기존 생성기의 산출도 합성이다. 표기는 값을 만든 경로를 가리켜야 하므로 국내
표본이라고 해서 '수기등록'(사람이 등록한 실데이터)으로 적지 않는다.

프로파일·구성 원장의 국내 표본 행은 다르다. 그 행의 값은 기존 엔진이 쓰던
상수를 사람이 옮겨 적은 것이라 등록 경로가 '수기등록'·근거 상태가 '미확인'
이며, 그것이 그 원장 행의 사실이다.

금액 단위에 대하여
------------------
기관마다 보고통화가 다르지만 **환산은 하지 않는다.** 환율 근거가 이 저장소에
없기 때문이다. 금액의 규모감은 국내 표본 생성기의 것을 그대로 쓰고, 기관 간
차이는 `ead_scale` 배수로만 준다. 그러므로 기관 간 금액을 직접 비교하거나
합산하면 안 되며, `INST_PROFILE.note` 와 원장 컬럼 주석에 그 사실을 적어 둔다.
규제자본은 어차피 기관 단위 지표이므로 합산할 자리가 없다.

남는 한계: PD 모형 변별력
--------------------------
기관별 자체검증에서 `pd_gini_*` 와 `pd_backtest_zones` 는 일부 기관에서 FAIL 로
남는다. 원인은 기관 프로파일이 아니라 합성 생성기다. 기업 세그먼트의 부도율이
1% 미만이라 800건짜리 표본의 실현 부도가 한 자릿수이고, 표본외 Gini 추정치의
산포가 하한 0.2 를 덮는다. 기업 건수를 800·6,000·12,000·20,000 으로 올려
9개 기관 × 3개 세그먼트를 재보면 최소값이 -0.20 / -0.02 / 0.21 / 0.16 으로
움직이며 어느 크기에서도 27쌍 전부가 하한을 넘지는 않는다.

그래서 표본이 명백히 부족했던 두 자리(증권 주담대 250건, 소매 300건)만
잔액을 유지한 채 건수를 늘렸고, 그 밖에는 손대지 않았다. 검사를 통과시키려고
시드 오프셋이나 표본 크기를 고르면 그것은 검사에 데이터를 맞추는 일이다.

미등재 사유
-----------
여기 정의한 스펙 4장은 `catalog.ALL_TABLES` 에 넣지 않는다. `inst_master` 와
같은 이유다. 실체화·계보·문서 수량 검사가 ALL_TABLES 를 그대로 세는데 그쪽은
이 작업의 소유 범위 밖이다. 사유는 catalog 소스에 적어 두었다.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from risk_lib.capital.output_floor import FULLY_LOADED_FLOOR
from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey, TableSpec
from risk_lib import institutions as inst

__all__ = [
    "SYNTHETIC_ORIGIN", "SYNTHETIC_EVIDENCE", "LANGUAGES",
    "INST_MASTER_INTL", "INST_PROFILE", "INST_PORTFOLIO_MIX",
    "INST_COUNTRY_MIX", "INTL_LABEL_LEXICON",
    "build_inst_master_intl", "build_inst_profile", "build_portfolio_mix",
    "build_country_mix", "build_label_lexicon", "build_all",
    "institution_codes", "profile_row", "market_op_params", "buffers_for",
    "structured_scale_for", "pillar2_for",
    "capital_ledger_for", "CAPITAL_BASIS", "validate_ledgers",
    "generate_institution_portfolio",
]


# ---------------------------------------------------------------- 어휘

# 합성 표기. `institutions.DATA_ORIGINS`·`limits_master.EVIDENCE_STATUS` 에는
# 없는 값이다. 두 어휘는 실제 등록 경로와 규정 근거 상태를 위한 것이고, 합성
# 기관은 그 어느 쪽도 아니다. 기존 어휘에 억지로 맞추면 화면에서 국내 표본과
# 구분되지 않는다.
SYNTHETIC_ORIGIN = "합성"
SYNTHETIC_EVIDENCE = "내부기준(합성)"

LANGUAGES: tuple[str, ...] = ("ko", "en")

INSTITUTION_ARCHETYPES: tuple[str, ...] = (
    "국내표본", "대형유니버설뱅크", "지역은행", "증권회사")

SIZE_TIERS: tuple[str, ...] = ("대형", "중형", "소형")

# 국내 표본은 이 모듈이 다시 만들지 않는다. 기존 생성기의 산출을 그대로 쓰고
# 기관코드만 붙인다. 다시 만들면 (asof, seed) 재현이 그 자리에서 끊긴다.
BASE_INSTITUTION = inst.PRIMARY_INSTITUTION


def _widen(col: C, **kw) -> C:
    return dataclasses.replace(col, **kw)


def _master_spec() -> TableSpec:
    """`inst_master` 스펙에서 파생한 확장 스펙.

    원본 스펙의 `data_origin`·`evidence_status` 허용값에는 합성 표기가 없다.
    원본을 그 자리에서 고치면 기관 축 작업의 소유 파일을 건드리게 되므로
    파생본을 만든다. 나머지 컬럼·키·입도는 원본 그대로다.
    """
    cols = []
    for c in inst.INST_MASTER.columns:
        if c.name == "data_origin":
            c = _widen(c, allowed=inst.DATA_ORIGINS + (SYNTHETIC_ORIGIN,))
        elif c.name == "evidence_status":
            from risk_lib.limits_master import EVIDENCE_STATUS
            c = _widen(c, allowed=EVIDENCE_STATUS + (SYNTHETIC_EVIDENCE,))
        elif c.name == "size_tier":
            c = _widen(c, allowed=SIZE_TIERS)
        cols.append(c)
    return dataclasses.replace(
        inst.INST_MASTER, columns=tuple(cols),
        note=(inst.INST_MASTER.note + " 합성 기관을 담기 위해 등록 경로·근거 "
              "상태 허용값을 넓힌 파생 스펙이다."))


INST_MASTER_INTL = _master_spec()


# ---------------------------------------------------------------- 프로파일 스펙

_ORIGIN_COL = C("data_origin", "string", "등록 경로", nullable=False,
                allowed=(SYNTHETIC_ORIGIN,) + inst.DATA_ORIGINS)


def _evidence_col() -> C:
    from risk_lib.limits_master import EVIDENCE_STATUS
    return C("evidence_status", "string", "근거 상태", nullable=False,
             allowed=(SYNTHETIC_EVIDENCE,) + EVIDENCE_STATUS)


INST_PROFILE = TableSpec(
    name="inst_profile", korean="기관 프로파일 원장", product="PRD-RDM",
    grain="기관 1개당 1행",
    columns=(
        C("institution_code", "string", "기관코드", nullable=False),
        C("archetype", "string", "유형", nullable=False,
          allowed=INSTITUTION_ARCHETYPES,
          note="공개적으로 알려진 업권 유형의 성격이며 특정 기관이 아니다"),
        C("label_language", "string", "라벨 언어", nullable=False,
          allowed=LANGUAGES,
          note="차주명·부문명·상품명의 언어. 국내 기관만 ko 다"),
        C("hurdle_rate", "float", "요구수익률", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("output_floor", "float", "산출하한", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="CRE·RBC20 산출하한"),
        C("buffer_ccb", "float", "자본보전완충", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("buffer_ccyb", "float", "경기대응완충", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("buffer_dsib", "float", "systemic 완충", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("mkt_notional_base", "float", "시장·운영 기준 명목", nullable=False,
          unit="보고통화", min_value=0.0,
          note="신용 EAD 와 독립인 트레이딩·영업지표 규모감. 통화 환산은 하지 "
               "않았으므로 기관 간 금액 비교에 쓰지 않는다"),
        C("share_fx", "float", "외환 포지션 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("share_equity", "float", "주식 포지션 비중", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("share_ir", "float", "금리 포지션 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("share_bi_ildc", "float", "BI 이자·리스·배당 비중", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0, citation="OPE25 BI"),
        C("share_bi_sc", "float", "BI 수수료 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="OPE25 BI"),
        C("share_bi_fc", "float", "BI 금융 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="OPE25 BI"),
        C("op_loss_rate", "float", "10년 평균 운영손실률", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0, citation="OPE25 ILM"),
        # 구조화 익스포저(집합투자증권 CRE60 · 유동화 CRE40)의 금액 배수.
        # 이 두 갈래는 신용 포트폴리오와 모집단이 겹치지 않아 `ead_scale` 이
        # 닿지 않는다. 배수가 없으면 기관이 바뀌어도 국내 표본 규모의 구조화
        # 블록이 그대로 붙고, 그 블록이 최종 RWA 의 5분의 1을 넘는다.
        C("fund_scale", "float", "집합투자증권 규모 배수", nullable=False,
          unit="ratio", min_value=0.0, citation="CRE60",
          note="국내 표본 생성기 금액에 대한 배수다. 통화 환산이 아니다"),
        C("sec_scale", "float", "유동화 규모 배수", nullable=False,
          unit="ratio", min_value=0.0, citation="CRE40",
          note="국내 표본 생성기 금액에 대한 배수다. 통화 환산이 아니다"),
        # 감독당국의 개별 부과분(SREP)이다. 이 저장소에 근거가 없으므로 비운다.
        # 채우면 그 순간 없는 감독 결정이 있는 것처럼 보인다. 비어 있으면
        # 파이프라인이 0 으로 산출하고 자체검증이 그 사실을 매 회차 남긴다.
        C("p2r", "float", "Pillar 2 요구(P2R)", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation="SRP20"),
        C("p2g", "float", "Pillar 2 가이드(P2G)", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation="SRP20"),
        # 자본은 산출물이 아니라 입력이다(독립검증 지적 F-001·F-101). 금액을
        # 그대로 적으면 구성 원장을 고칠 때마다 낡은 값이 남으므로 총 익스포저에
        # 대한 비율로 둔다. 자기자본/총자산이 은행 대차대조표의 구조적 특성이라는
        # 것 말고 다른 근거는 없으며, 국내 표본은 비워 두어 기존 수익성 기반
        # 합성기를 그대로 쓴다.
        C("cet1_to_ead", "float", "보통주자본/총익스포저", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("at1_to_ead", "float", "기타기본자본/총익스포저", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("tier2_to_ead", "float", "보완자본/총익스포저", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        _ORIGIN_COL,
        _evidence_col(),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("institution_code",),
    foreign_keys=(ForeignKey(("institution_code",), inst.AXIS_MASTER,
                             ("institution_code",)),),
    note="기관별 산출 모수. 파이프라인 인자는 전부 이 원장에서 온다.",
)

INST_PORTFOLIO_MIX = TableSpec(
    name="inst_portfolio_mix", korean="기관 포트폴리오 구성 원장",
    product="PRD-RDM",
    grain="기관 × 자산군 1행",
    columns=(
        C("institution_code", "string", "기관코드", nullable=False),
        C("asset_class", "string", "자산군", nullable=False),
        C("n_exposures", "int", "익스포저 건수", nullable=False, min_value=0,
          unit="count"),
        C("ead_scale", "float", "익스포저 규모 배수", nullable=False,
          unit="ratio", min_value=0.0,
          note="국내 표본 생성기 금액에 대한 배수다. 통화 환산이 아니다"),
        _ORIGIN_COL,
        _evidence_col(),
    ),
    primary_key=("institution_code", "asset_class"),
    foreign_keys=(ForeignKey(("institution_code",), inst.AXIS_MASTER,
                             ("institution_code",)),),
    note="자산군별 건수와 규모 배수. 유형별 편중이 여기서 나온다.",
)

INST_COUNTRY_MIX = TableSpec(
    name="inst_country_mix", korean="기관 국가 구성 원장", product="PRD-RDM",
    grain="기관 × 소재국 1행",
    columns=(
        C("institution_code", "string", "기관코드", nullable=False),
        C("country", "string", "국가", nullable=False,
          citation="ISO 3166-1 alpha-2"),
        C("weight", "float", "구성비", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="기관별 합이 1이다. build_country_mix 가 확인한다"),
        _ORIGIN_COL,
        _evidence_col(),
    ),
    primary_key=("institution_code", "country"),
    foreign_keys=(ForeignKey(("institution_code",), inst.AXIS_MASTER,
                             ("institution_code",)),),
    note=("국가 배분. 국내 표본은 행이 없다. 기존 생성기의 국가 배정을 그대로 "
          "두어야 (asof, seed) 재현이 유지되기 때문이다."),
)

INTL_LABEL_LEXICON = TableSpec(
    name="intl_label_lexicon", korean="라벨 어휘집", product="PRD-RDM",
    grain="언어 × 라벨유형 × 코드 1행",
    columns=(
        C("language", "string", "언어", nullable=False, allowed=LANGUAGES),
        C("label_kind", "string", "라벨 유형", nullable=False,
          allowed=("sector", "product", "obligor_affix")),
        C("label_code", "string", "코드", nullable=False),
        C("label_text", "text", "표기", nullable=False),
    ),
    primary_key=("language", "label_kind", "label_code"),
    note=("기관코드를 넣지 않는다. 어휘는 언어에 딸린 것이지 기관에 딸린 것이 "
          "아니며, 기관마다 복제하면 같은 낱말이 기관 수만큼 갈라진다. "
          "기관은 inst_profile.label_language 로 언어를 고른다."),
)


# ---------------------------------------------------------------- 원장 빌더
#
# 아래 리터럴이 이 모듈에서 값을 적는 유일한 자리다. 생성기·실행부는 이 표를
# 인자로 받는다.

# (코드, 한글명, 영문명, 업권, 지역, 국가, 통화, 국내여부, 규제체계, 규모, 유형)
_INSTITUTIONS: tuple[tuple, ...] = (
    ("APAC_BANK_01", None, "Asia Pacific Universal Bank Alpha", "은행",
     "아시아태평양", "SG", "SGD", False, "Basel III (BCBS) 최종안", "대형",
     "대형유니버설뱅크"),
    ("APAC_SEC_01", None, "Asia Pacific Securities Alpha", "증권",
     "아시아태평양", "JP", "JPY", False, "Basel III (투자업 적용, 합성)", "중형",
     "증권회사"),
    ("NA_BANK_01", None, "North America Universal Bank Alpha", "은행",
     "북미", "US", "USD", False, "Basel III Endgame (미국)", "대형",
     "대형유니버설뱅크"),
    ("NA_SEC_01", None, "North America Securities Alpha", "증권",
     "북미", "US", "USD", False, "Basel III (투자업 적용, 합성)", "중형",
     "증권회사"),
    ("EU_BANK_01", None, "Europe Universal Bank Alpha", "은행",
     "유럽", "DE", "EUR", False, "CRR3/CRD6 (유럽연합)", "대형",
     "대형유니버설뱅크"),
    ("EU_SEC_01", None, "Europe Securities Alpha", "증권",
     "유럽", "FR", "EUR", False, "IFR/IFD (유럽연합 투자회사)", "중형",
     "증권회사"),
    ("MEA_BANK_01", None, "Middle East Africa Regional Bank Alpha", "은행",
     "중동아프리카", "AE", "AED", False, "Basel III (BCBS) 최종안", "중형",
     "지역은행"),
    ("LATAM_BANK_01", None, "Latin America Regional Bank Alpha", "은행",
     "중남미", "BR", "BRL", False, "Basel III (BCBS) 최종안", "중형",
     "지역은행"),
)

_SYNTHETIC_NOTE = (
    "합성 기관이다. 실존 기관의 수치가 아니며 업권 유형의 공개된 성격만 "
    "모수로 옮겼다. 금액 단위는 국내 표본 생성기의 규모감을 그대로 쓰며 "
    "환율 환산을 하지 않았으므로 기관 간 금액을 비교·합산하지 않는다.")

# 유형별 산출 모수. 국내표본 행은 기존 엔진이 쓰던 값과 같은 수이며, 그래야
# 기관 축을 붙인 뒤에도 (asof, seed) 산출이 그대로 재현된다.
_ARCHETYPE_PROFILE: dict[str, dict[str, float]] = {
    "국내표본": {
        "hurdle_rate": 0.10,
        "buffer_ccb": 0.025, "buffer_ccyb": 0.0, "buffer_dsib": 0.01,
        "mkt_notional_base": 1.0e13,
        "share_fx": 0.02, "share_equity": 0.01, "share_ir": 0.05,
        "share_bi_ildc": 0.02, "share_bi_sc": 0.01, "share_bi_fc": 0.005,
        "op_loss_rate": 0.001,
        # 배수 1.0 은 국내 표본이 기존 생성기 금액을 그대로 쓴다는 뜻이다.
        "fund_scale": 1.0, "sec_scale": 1.0,
        # 비워 둔다. 채우면 국내 표본의 자본이 바뀌고 기존 산출이 재현되지 않는다.
        "cet1_to_ead": None, "at1_to_ead": None, "tier2_to_ead": None,
        # 감독 부과분은 근거가 없다. 비운 상태가 사실이다.
        "p2r": None, "p2g": None,
    },
    # 트레이딩 자산 비중이 크고 완충자본 부과가 두텁다.
    "대형유니버설뱅크": {
        "hurdle_rate": 0.11,
        "buffer_ccb": 0.025, "buffer_ccyb": 0.010, "buffer_dsib": 0.015,
        "mkt_notional_base": 1.4e13,
        "share_fx": 0.035, "share_equity": 0.025, "share_ir": 0.075,
        "share_bi_ildc": 0.022, "share_bi_sc": 0.014, "share_bi_fc": 0.008,
        "op_loss_rate": 0.0012,
        # 트레이딩·투자은행 업무가 커서 펀드 수익증권과 유동화 보유가 크다.
        "fund_scale": 1.5, "sec_scale": 1.6,
        "cet1_to_ead": 0.120, "at1_to_ead": 0.014, "tier2_to_ead": 0.024,
        "p2r": None, "p2g": None,
    },
    # 트레이딩이 작고 예대 중심이다.
    "지역은행": {
        "hurdle_rate": 0.10,
        "buffer_ccb": 0.025, "buffer_ccyb": 0.0, "buffer_dsib": 0.005,
        "mkt_notional_base": 0.6e13,
        "share_fx": 0.012, "share_equity": 0.004, "share_ir": 0.030,
        "share_bi_ildc": 0.020, "share_bi_sc": 0.006, "share_bi_fc": 0.003,
        "op_loss_rate": 0.0009,
        # 예대 중심이라 구조화 보유가 얇다.
        "fund_scale": 0.45, "sec_scale": 0.40,
        "cet1_to_ead": 0.150, "at1_to_ead": 0.018, "tier2_to_ead": 0.030,
        "p2r": None, "p2g": None,
    },
    # 신용 익스포저가 작고 시장·운영 비중이 크다. 명목 자체는 은행보다 작다.
    # 큰 것은 자기 신용 익스포저 대비 **비중**이지 절대 규모가 아니다.
    "증권회사": {
        "hurdle_rate": 0.12,
        "buffer_ccb": 0.025, "buffer_ccyb": 0.0, "buffer_dsib": 0.0,
        "mkt_notional_base": 0.35e13,
        "share_fx": 0.060, "share_equity": 0.090, "share_ir": 0.110,
        "share_bi_ildc": 0.010, "share_bi_sc": 0.040, "share_bi_fc": 0.020,
        "op_loss_rate": 0.0025,
        # 신용 익스포저 대비 구조화·재고 보유 비중이 크지만 절대 규모는
        # 은행보다 작다. 배수도 그 순서를 따른다.
        "fund_scale": 0.55, "sec_scale": 0.50,
        "cet1_to_ead": 0.150, "at1_to_ead": 0.018, "tier2_to_ead": 0.030,
        "p2r": None, "p2g": None,
    },
}

# 유형별 자산군 구성. 값은 (건수, 규모 배수) 다.
# 국내표본은 `data_gen.generate_portfolio` 의 기본 인수와 같은 건수이며 배수는
# 1.0 이다. 그래야 같은 (asof, seed) 에서 기존 산출이 그대로 나온다.
_ARCHETYPE_MIX: dict[str, dict[str, tuple[int, float]]] = {
    "국내표본": {
        "corporate": (800, 1.0), "retail_other": (1500, 1.0),
        "residential_mortgage": (600, 1.0), "sovereign": (30, 1.0),
        "bank": (50, 1.0),
    },
    # 소매 건수·규모를 국내 표본보다 크게 잡는다. 국내 표본의 기타소매 잔액은
    # 총 익스포저의 0.6% 로 유니버설 뱅크의 예대 구조와 맞지 않고, 그 상태에서는
    # 자기자본(수익성 기반 합성)이 기업여신 한 갈래에만 기댄다.
    "대형유니버설뱅크": {
        "corporate": (900, 1.4), "retail_other": (3000, 5.0),
        "residential_mortgage": (700, 1.2), "sovereign": (60, 1.3),
        "bank": (90, 1.4),
    },
    "지역은행": {
        "corporate": (800, 0.7), "retail_other": (1000, 0.8),
        "residential_mortgage": (900, 1.1), "sovereign": (40, 0.5),
        "bank": (30, 0.4),
    },
    # 국공채·은행간 익스포저(재고·환매조건부) 비중이 높고 소매가 거의 없다.
    # 기업 건수를 800으로 두는 것은 편중과 무관하다. 그보다 적으면 PD 모형
    # 변별력(Gini) 하한을 못 넘고, 그것은 기관 특성이 아니라 표본 부족이다.
    # 소매·주담대 건수는 잔액을 그대로 두고 늘렸다(배수를 같은 비율로 낮췄다).
    # 250건짜리 주담대 표본으로는 PD 모형 변별력을 측정한다고 말할 수 없다.
    "증권회사": {
        "corporate": (800, 0.30), "retail_other": (800, 0.1125),
        "residential_mortgage": (600, 0.104), "sovereign": (120, 0.35),
        "bank": (180, 0.45),
    },
}

# 권역별 국가 배분. 권역이 겹치지 않게 국가군을 나눈다.
_REGION_COUNTRIES: dict[str, tuple[tuple[str, float], ...]] = {
    "아시아태평양": (("SG", 0.30), ("JP", 0.22), ("AU", 0.16), ("HK", 0.14),
                ("IN", 0.10), ("CN", 0.08)),
    "북미": (("US", 0.78), ("CA", 0.22)),
    "유럽": (("DE", 0.30), ("FR", 0.22), ("NL", 0.16), ("IT", 0.14),
           ("ES", 0.10), ("GB", 0.08)),
    "중동아프리카": (("AE", 0.36), ("SA", 0.24), ("ZA", 0.18), ("QA", 0.12),
                ("EG", 0.10)),
    "중남미": (("BR", 0.44), ("MX", 0.24), ("CL", 0.14), ("CO", 0.10),
             ("PE", 0.08)),
}

# 어휘집. `data_gen` 이 만드는 부문·자산군 코드 전량을 두 언어로 덮는다.
_LEXICON: dict[str, dict[str, tuple[str, str]]] = {
    # 코드 → (ko, en)
    "sector": {
        "manufacturing": ("제조업", "Manufacturing"),
        "construction": ("건설업", "Construction"),
        "shipping": ("해운업", "Shipping"),
        "tech": ("정보기술업", "Technology"),
        "real_estate": ("부동산업", "Real Estate"),
        "energy": ("에너지업", "Energy"),
        "retail_trade": ("도소매업", "Retail Trade"),
        "household": ("가계", "Household"),
        "government": ("정부", "Government"),
        "financial": ("금융업", "Financial"),
    },
    "product": {
        "corporate": ("기업대출", "Corporate Loan"),
        "retail_other": ("기타소매여신", "Other Retail Credit"),
        "residential_mortgage": ("주택담보대출", "Residential Mortgage"),
        "sovereign": ("국공채", "Sovereign Bond"),
        "bank": ("은행간여신", "Bank Exposure"),
    },
    "obligor_affix": {
        "corporate": ("법인", "Corporation"),
        "retail_other": ("차주", "Obligor"),
        "residential_mortgage": ("차주", "Obligor"),
        "sovereign": ("정부기관", "Sovereign Entity"),
        "bank": ("금융기관", "Bank Counterparty"),
    },
}


def build_inst_master_intl() -> pd.DataFrame:
    """국내 표본 1곳 + 권역별 합성 기관 8곳의 기관 원장.

    국내 표본 행은 `institutions.build_inst_master()` 가 만든 것을 그대로
    쓴다. 여기서 다시 쓰면 두 벌이 되고 두 벌은 갈라진다.
    """
    base = inst.build_inst_master()
    rows = []
    # 난수 오프셋은 등록 순서로 1부터 주되 간격은 `institutions.SEED_STRIDE` 다.
    # 간격이 모듈 오프셋 폭보다 좁으면 기관 A 의 어떤 모듈과 기관 B 의 다른
    # 모듈이 같은 난수열을 쓴다. 국내 표본이 0 이며 그 값을 유지해야 기존
    # 산출이 재현된다.
    for i, (code, ko, en, itype, region, country, ccy, domestic,
            regime, tier, _arch) in enumerate(_INSTITUTIONS, start=1):
        rows.append({
            "institution_code": code,
            "name_ko": ko,
            "name_en": en,
            "institution_type": itype,
            "region": region,
            "country": country,
            "currency": ccy,
            "is_domestic": domestic,
            "regulatory_regime": regime,
            "size_tier": tier,
            "seed_offset": i * inst.SEED_STRIDE,
            "data_origin": SYNTHETIC_ORIGIN,
            "evidence_status": SYNTHETIC_EVIDENCE,
            "note": _SYNTHETIC_NOTE,
        })
    add = pd.DataFrame(rows, columns=list(INST_MASTER_INTL.column_names))
    out = pd.concat([base, add], ignore_index=True)
    return out.astype({"seed_offset": "int64", "is_domestic": "bool"})


def _archetype_of(code: str) -> str:
    if code == BASE_INSTITUTION:
        return "국내표본"
    for row in _INSTITUTIONS:
        if row[0] == code:
            return row[-1]
    raise ValueError(f"기관 원장에 없는 기관코드: {code}")


def build_inst_profile() -> pd.DataFrame:
    """기관별 산출 모수. 파이프라인 인자가 전부 여기서 온다."""
    master = build_inst_master_intl()
    rows = []
    for r in master.itertuples():
        code = str(r.institution_code)
        arch = _archetype_of(code)
        p = dict(_ARCHETYPE_PROFILE[arch])
        base = code == BASE_INSTITUTION
        rows.append({
            "institution_code": code,
            "archetype": arch,
            "label_language": "ko" if bool(r.is_domestic) else "en",
            "output_floor": FULLY_LOADED_FLOOR,
            **p,
            "data_origin": "수기등록" if base else SYNTHETIC_ORIGIN,
            "evidence_status": "미확인" if base else SYNTHETIC_EVIDENCE,
            "note": ("기존 엔진이 쓰던 값과 같은 수다. 근거 문서가 없으므로 "
                     "근거 상태는 미확인이다." if base else _SYNTHETIC_NOTE),
        })
    df = pd.DataFrame(rows, columns=list(INST_PROFILE.column_names))
    # 전건이 비어 있는 float 칸은 pandas 가 object 로 만든다. 스펙 대조가
    # dtype 으로 걸리므로 여기서 float 로 못박는다. 값을 채우는 것이 아니라
    # 빈 칸의 자료형을 정하는 것이다.
    return df.astype({c.name: "float64" for c in INST_PROFILE.columns
                      if c.dtype == "float"})


def build_portfolio_mix() -> pd.DataFrame:
    """기관 × 자산군 구성 원장."""
    master = build_inst_master_intl()
    rows = []
    for r in master.itertuples():
        code = str(r.institution_code)
        base = code == BASE_INSTITUTION
        for asset_class, (n, scale) in _ARCHETYPE_MIX[_archetype_of(code)].items():
            rows.append({
                "institution_code": code,
                "asset_class": asset_class,
                "n_exposures": int(n),
                "ead_scale": float(scale),
                "data_origin": "수기등록" if base else SYNTHETIC_ORIGIN,
                "evidence_status": "미확인" if base else SYNTHETIC_EVIDENCE,
            })
    df = pd.DataFrame(rows, columns=list(INST_PORTFOLIO_MIX.column_names))
    return df.astype({"n_exposures": "int64"})


def build_country_mix() -> pd.DataFrame:
    """기관 × 국가 구성 원장. 국내 표본은 행이 없다.

    국내 표본에 행을 넣으면 국가 재배정이 일어나고 기존 (asof, seed) 산출이
    바뀐다. 재현을 깨면서까지 원장을 채울 이유가 없다.
    """
    rows = []
    for code, _ko, _en, _t, region, *_rest in _INSTITUTIONS:
        pairs = _REGION_COUNTRIES[region]
        total = sum(w for _c, w in pairs)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"{code}: 국가 구성비 합이 1이 아니다 ({total})")
        for country, w in pairs:
            rows.append({
                "institution_code": code, "country": country,
                "weight": float(w),
                "data_origin": SYNTHETIC_ORIGIN,
                "evidence_status": SYNTHETIC_EVIDENCE,
            })
    return pd.DataFrame(rows, columns=list(INST_COUNTRY_MIX.column_names))


def build_label_lexicon() -> pd.DataFrame:
    """언어별 라벨 어휘집."""
    rows = []
    for kind, table in _LEXICON.items():
        for code, (ko, en) in table.items():
            rows.append({"language": "ko", "label_kind": kind,
                         "label_code": code, "label_text": ko})
            rows.append({"language": "en", "label_kind": kind,
                         "label_code": code, "label_text": en})
    df = pd.DataFrame(rows, columns=list(INTL_LABEL_LEXICON.column_names))
    return df.sort_values(list(INTL_LABEL_LEXICON.primary_key)
                          ).reset_index(drop=True)


def build_all() -> dict[str, pd.DataFrame]:
    """네 원장 + 기관 원장을 한 번에. 이름은 스펙 이름과 같다."""
    return {
        inst.AXIS_MASTER: build_inst_master_intl(),
        INST_PROFILE.name: build_inst_profile(),
        INST_PORTFOLIO_MIX.name: build_portfolio_mix(),
        INST_COUNTRY_MIX.name: build_country_mix(),
        INTL_LABEL_LEXICON.name: build_label_lexicon(),
    }


# ---------------------------------------------------------------- 원장 조회

def institution_codes(master: pd.DataFrame | None = None) -> tuple[str, ...]:
    m = build_inst_master_intl() if master is None else master
    return tuple(str(c) for c in m["institution_code"])


def profile_row(code: str, profile: pd.DataFrame | None = None) -> pd.Series:
    p = build_inst_profile() if profile is None else profile
    hit = p[p["institution_code"] == code]
    if hit.empty:
        raise ValueError(f"프로파일 원장에 없는 기관코드: {code}")
    return hit.iloc[0]


_MARKET_OP_KEYS = ("mkt_notional_base", "share_fx", "share_equity", "share_ir",
                   "share_bi_ildc", "share_bi_sc", "share_bi_fc",
                   "op_loss_rate")


def market_op_params(code: str = BASE_INSTITUTION,
                     profile: pd.DataFrame | None = None) -> dict[str, float]:
    """시장·운영 산출 모수. 엔진은 이 dict 를 인자로 받고 본문에 수를 두지 않는다."""
    row = profile_row(code, profile)
    return {k: float(row[k]) for k in _MARKET_OP_KEYS}


_CAPITAL_KEYS = ("cet1_to_ead", "at1_to_ead", "tier2_to_ead")

# 이 원장의 자본이 무엇으로 만들어졌는지. 총익스포저 비율이므로 규모 비례분이
# 100% 이고, 그 사실은 자체검증이 매 회차 적어야 한다 (독립검증 F-201·F-202).
# 문자열은 `validation.consistency.RATIO_TO_EAD_BASIS` 와 같아야 한다.
CAPITAL_BASIS = "ratio_to_ead"


def capital_ledger_for(code: str, total_ead: float,
                       profile: pd.DataFrame | None = None):
    """기관의 자본 원장. 비율이 비어 있으면 None 을 돌려준다.

    None 이면 파이프라인이 수익성 기반 합성기를 쓰고 그 사실을 자체검증에
    `capital_source='synthetic'` 로 공시한다. 국내 표본이 그 경우다.

    값이 있을 때도 "실제 자본 원장" 은 아니다. `cet1_to_ead` 비율 × 총익스포저
    이므로 자본이 익스포저를 그대로 따라간다. 호출부는 `CAPITAL_BASIS` 를
    `run_pipeline(capital_basis=...)` 로 함께 넘겨 그 사실이 검증에 남게 한다.
    """
    from risk_lib.capital.bis import CapitalStack
    row = profile_row(code, profile)
    vals = [row[k] for k in _CAPITAL_KEYS]
    if any(pd.isna(v) for v in vals):
        return None
    cet1, at1, t2 = (float(v) * float(total_ead) for v in vals)
    return CapitalStack(cet1=cet1, additional_t1=at1, tier2=t2)


def buffers_for(code: str,
                profile: pd.DataFrame | None = None) -> dict[str, float]:
    """`run_pipeline(buffers=...)` 인자."""
    row = profile_row(code, profile)
    return {"capital_conservation": float(row["buffer_ccb"]),
            "countercyclical": float(row["buffer_ccyb"]),
            "dsib": float(row["buffer_dsib"])}


_STRUCTURED_KEYS = ("fund_scale", "sec_scale")


def structured_scale_for(code: str, profile: pd.DataFrame | None = None
                         ) -> dict[str, float]:
    """`run_pipeline(structured_scale=...)` 인자. 구조화 원장의 금액 배수다."""
    row = profile_row(code, profile)
    return {k: float(row[k]) for k in _STRUCTURED_KEYS}


def pillar2_for(code: str, profile: pd.DataFrame | None = None
                ) -> dict[str, float | None]:
    """`run_pipeline(pillar2=...)` 인자. 값이 없으면 None 을 그대로 돌려준다.

    없는 것을 0 으로 바꿔 돌려주면 "감독 부과분이 0" 과 "근거가 없다" 가
    구분되지 않는다. 구분은 호출부가 아니라 여기서 유지한다.
    """
    row = profile_row(code, profile)
    return {k: (None if pd.isna(row[k]) else float(row[k]))
            for k in ("p2r", "p2g")}


def _lexicon_map(language: str, kind: str,
                 lexicon: pd.DataFrame) -> dict[str, str]:
    sub = lexicon[(lexicon["language"] == language)
                  & (lexicon["label_kind"] == kind)]
    return dict(zip(sub["label_code"], sub["label_text"]))


# ---------------------------------------------------------------- 생성기

def generate_institution_portfolio(
    code: str, *,
    seed: int,
    master: pd.DataFrame | None = None,
    profile: pd.DataFrame | None = None,
    mix: pd.DataFrame | None = None,
    country_mix: pd.DataFrame | None = None,
    lexicon: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """기관 하나의 합성 포트폴리오.

    본문에 계수가 없다. 건수·규모 배수는 `inst_portfolio_mix`, 국가 배분은
    `inst_country_mix`, 표기는 `intl_label_lexicon` 에서 온다.

    국내 표본(KR_BANK_01)은 기존 생성기 산출을 **금액·위험요인 그대로** 쓴다.
    붙는 것은 라벨 컬럼과 기관코드뿐이며 숫자는 손대지 않는다. 그래야 기관
    축을 붙이기 전 산출이 그대로 재현된다.
    """
    master = build_inst_master_intl() if master is None else master
    profile = build_inst_profile() if profile is None else profile
    mix = build_portfolio_mix() if mix is None else mix
    country_mix = build_country_mix() if country_mix is None else country_mix
    lexicon = build_label_lexicon() if lexicon is None else lexicon

    if code not in set(master["institution_code"]):
        raise ValueError(f"기관 원장에 없는 기관코드: {code}")
    inst_seed = inst.institution_seed(seed, code, master)
    prow = profile_row(code, profile)
    my_mix = mix[mix["institution_code"] == code]
    if my_mix.empty:
        raise ValueError(f"구성 원장에 없는 기관코드: {code}")
    counts = dict(zip(my_mix["asset_class"], my_mix["n_exposures"]))
    scales = dict(zip(my_mix["asset_class"], my_mix["ead_scale"]))

    p = generate_portfolio(
        n_corporate=int(counts["corporate"]),
        n_retail=int(counts["retail_other"]),
        n_mortgage=int(counts["residential_mortgage"]),
        n_sovereign=int(counts["sovereign"]),
        n_bank=int(counts["bank"]),
        seed=inst_seed,
    )

    # 금액 배수. EAD 와 그 파생 금액을 같은 배수로 옮긴다. 하나만 옮기면
    # 수익성 기반 자본 합성기가 다른 규모의 은행을 설명하게 된다.
    money_cols = [c for c in ("ead", "balance", "revenue", "operating_cost")
                  if c in p.columns]
    factor = p["asset_class"].map(scales).astype(float)
    if factor.isna().any():
        missing = sorted(set(p.loc[factor.isna(), "asset_class"]))
        raise ValueError(f"{code}: 구성 원장에 없는 자산군 {missing}")
    for col in money_cols:
        p[col] = p[col].astype(float) * factor

    # 국가 재배정. 원장에 행이 있는 기관만 한다. 국내 표본은 행이 없어 그대로 둔다.
    my_countries = country_mix[country_mix["institution_code"] == code]
    if not my_countries.empty:
        rng = np.random.default_rng(inst_seed + 8200)
        w = my_countries["weight"].to_numpy(dtype=float)
        p["country"] = rng.choice(my_countries["country"].to_numpy(),
                                  size=len(p), p=w / w.sum())

    # 표기. 같은 컬럼에 한글과 영문이 섞이는 것은 정상이며 기관코드로 갈린다.
    lang = str(prow["label_language"])
    sector_label = _lexicon_map(lang, "sector", lexicon)
    product_label = _lexicon_map(lang, "product", lexicon)
    affix = _lexicon_map(lang, "obligor_affix", lexicon)
    unknown = sorted(set(p["sector"]) - set(sector_label))
    if unknown:
        raise ValueError(f"어휘집에 없는 부문 코드 {unknown} (언어 {lang})")
    p["sector_label"] = p["sector"].map(sector_label)
    p["product_label"] = p["asset_class"].map(product_label)
    seq = p.groupby("asset_class").cumcount() + 1
    p["obligor_name"] = [
        f"{s} {affix[a]} {i:05d}"
        for s, a, i in zip(p["sector_label"], p["asset_class"], seq)
    ]

    p.insert(0, inst.INSTITUTION_COLUMN, code)
    # 표기는 이 행을 만든 경로를 가리킨다. 프로파일 원장의 등록 경로를 그대로
    # 옮기면 국내 표본의 합성 익스포저 전건이 '수기등록'(사람이 등록한
    # 실데이터)으로 표시되고, `data_origin=='합성'` 으로 합성 행을 거르는 쪽은
    # 그 전건을 놓친다. 프로파일 행의 등록 경로는 그 원장 행의 사실이지 여기
    # 익스포저의 출처가 아니다.
    p["data_origin"] = SYNTHETIC_ORIGIN
    p["evidence_status"] = SYNTHETIC_EVIDENCE
    return p


def validate_ledgers(tables: Mapping[str, pd.DataFrame] | None = None
                     ) -> list:
    """다섯 원장을 스펙에 대조한다. 위반 목록을 돌려준다."""
    t = build_all() if tables is None else tables
    specs: Iterable[TableSpec] = (INST_MASTER_INTL, INST_PROFILE,
                                  INST_PORTFOLIO_MIX, INST_COUNTRY_MIX,
                                  INTL_LABEL_LEXICON)
    from risk_lib.datamodel.spec import validate as _validate
    out = []
    for spec in specs:
        out.extend(_validate(t[spec.name], spec))
    out.extend(inst.check_names(t[inst.AXIS_MASTER]))
    return out
