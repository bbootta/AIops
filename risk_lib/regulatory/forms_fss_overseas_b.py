"""금감원 FINES 업무보고서 — 해외점포 수익성·자본적정성·현지화평가 23건.

근거는 은행업감독규정 제26조(자기자본비율)·제27조(자산건전성 분류)·제29조
(대손충당금)·제99조(업무보고서)와 Basel 기준(CRE40 자본의 정의 · LEV20·LEV30
레버리지 · CRE20 신용리스크 · OPE25 운영리스크)이다.

**해외점포 손익·인력·조달 원장이 없다.** 이 저장소는 익스포저의 소재국만 알 뿐
어느 점포가 어떤 이자를 받고 몇 명을 두고 어디서 조달했는지 모른다. 점포 마스터와
익스포저 귀속은 `forms_fss_overseas_data`(BF1xx~BF4xx와 공유), 손익 분해·전기
실적·인력·현지화 파생은 `forms_fss_overseas_b_data`가 **기준일 고정 시드**로
만든다. 같은 시드면 같은 값이다.

실측이라 파생하지 않는 것
  영업수익·판매관리비   `portfolio.revenue` · `operating_cost` 해외분 실측 합.
                      소재국으로 거른 합이므로 **배분이 아니다.**
  해외 신용 RWA        `rwa_result` 익스포저별 실측 합 (BF602·BF603).
  CCR RWA 비중         거래상대방 소재국이 원장에 있어 실측으로 가른다.
  손실위험도가중여신     건전성분류 실측 × **원장의** 제29조 최저적립률 (BF606).
                      그룹 서식 B2902와 같은 원천을 읽는다 — 서식이 가중치 사본을
                      들면 같은 지표가 두 값을 갖는다.
  해외자산·매출 비중     초국적화지수 세 축 중 둘은 실측이다 (BF705).

배분이라 파생인 것 — **본점 값을 그대로 쓰지 않는다**
  자기자본(BF601·BF601-1·BF602·BF602-1·BF605)은 본점 자기자본에 해외 익스포저
  실측 비중을 곱한 **배분자본**이다. BF201(대차대조표)이 쓰는 비율과 같은 비율을
  써야 두 서식이 어긋나지 않으므로 `overseas_share` 한 곳만 본다. 배분이라는
  사실은 해당 라인의 formula에 그대로 적는다.

BF605(단순기본자본비율)는 BR-07 레버리지비율의 해외분이며 정의가 같다 —
기본자본 ÷ 총익스포저(LEV30). 분자·분모를 같은 `ctx.result.leverage`에서
가져와 정의가 갈라지지 않게 한다.

BF701~BF706(현지화평가)은 전부 원장이 없다. 초국적화지수(BF705)는 자산·매출·
인력 비중의 산술평균이라는 정의를 지키며, 파생값끼리라도 그 정의 관계를
FormCheck로 검증한다. BF706은 정성평가라 점수 구간표를 데이터 모듈에 상수로
두고 지표 → 점수 환산 근거를 라인에 남긴다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from risk_lib.capital.crm import CCF_BUCKETS
from risk_lib.prudential.financials import CORPORATE_TAX_RATE
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_overseas_b_data import (
    GRADE_CUTS, NONINT_ITEMS, SEC_PNL_ITEMS, SCORE_SECTIONS, SECTION_POINTS,
    TOTAL_POINTS, allocated_balance, funding_book, grade_of, hq_staff,
    interest_prior, loss_weighted, loss_weighted_amount, noninterest_mix,
    overseas_income, overseas_rwa, pnl_book, prior_amount, score_of,
    security_pnl, staff_book, usage_book,
)
from risk_lib.regulatory.forms_fss_overseas_data import (
    AQ_ORDER, HOME_COUNTRY, NPL_CLASSES, _tol, branch_master, overseas_book,
    overseas_countries, overseas_securities, overseas_share,
)

_M_DER = "risk_lib.regulatory.forms_fss_overseas_b_data"
_M_DER_A = "risk_lib.regulatory.forms_fss_overseas_data"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_PRU = "risk_lib.prudential.financials"
_M_RDM = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_BIS = "risk_lib.capital.bis"
_M_BISD = "risk_lib.capital.bis_deep"
_M_LEV = "risk_lib.capital.leverage"
_M_RWA = "risk_lib.capital.rwa_sa · risk_lib.capital.rwa_irb"
_M_CCR = "risk_lib.ccr"
_M_MKT = "risk_lib.capital.market_risk"
_M_OPR = "risk_lib.capital.op_risk"

# 제26조 제1항 제1~3호가 보통주자본·기본자본·총자본 비율을, 제4호가
# 레버리지비율(단순기본자본비율)을 정한다. 호까지 적어야 같은 라인명이
# 다른 근거를 갖는 것이 설명된다 (독립검증 지적 F-C02).
_C26 = "은행업감독규정 제26조 제1항 제1~3호 자기자본비율"
_C27 = "은행업감독규정 제27조 자산건전성 5단계 분류"
_C29 = "은행업감독규정 제29조 제1항 최저적립률"
_C31 = "은행업감독규정 제31조 경영실태평가"
_C63 = "은행업감독규정 제63조 외화유동성"
_C99 = "은행업감독규정 제99조 업무보고서"
_CRE40 = "Basel III CRE40 자본의 정의"
_CRE20 = "Basel III CRE20 신용리스크 표준방법"
_LEV20 = "Basel III LEV20·LEV30 · 은행업감독규정 제26조 제1항 제4호"

# 아래 문구는 `regulatory.provenance`가 라인의 산출 근거를 판정하는 어휘와 맞춰야
# 한다. 어휘가 어긋나면 파생 라인이 조용히 '실측'으로 떨어지고(그게 provenance가
# 막으려는 것이다), 열린 라인이 어느 원장에도 걸리지 않아 이행 계획에 구멍이 난다.
#   · "파생이 아님"   → _NEGATIONS  (실측으로 확정)
#   · "파생값"·"파생 배분" → _DERIVED  (파생으로 확정)
#   · "해외점포"      → LED-12 해외점포 원장에 귀속
#   · "전기말"        → LED-06 전기말 잔액·변동 원장에 귀속
_DERIVED = "해외점포 원장 부재 — 기준일 고정 시드 파생값"
_DERIVED_ALLOC = ("해외점포 계정별 원장 부재 — 해외 익스포저 실측 비중으로 나눈 "
                  "파생 배분")
_MEASURED = "포트폴리오 country 실측 집계 — 파생이 아님"
_ALLOC_CAP = ("본점 자기자본 × 해외 익스포저 실측 비중 — 해외점포 자본계정 원장 "
              "부재로 배분한 파생값이며 본점 자본을 그대로 쓴 것이 아니다")


def _r(num: float, den: float) -> float:
    """분모 0을 0으로 돌린다 — `_ratio_check`가 쓰는 규칙과 같아야 대사가 맞는다."""
    return num / den if den else 0.0


# ---------------------------------------------------------------- BF501

def _bf501(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """수익과 비용 — 영업수익·판매관리비는 실측, 이자/비이자 구분은 파생이다."""
    df = pnl_book(ctx)
    inc = overseas_income(ctx)
    ni = float(df["net_interest"].sum())
    non = float(df["noninterest"].sum())
    L = [
        FormLine("1000", "영업수익", 0, "KRW", inc["영업수익"],
                 formula=f"portfolio.revenue 해외분 실측 합 · {len(df):,}건 · "
                         f"{_MEASURED}", citation=_C99, source_module=_M_PTF,
                 is_subtotal=True),
        FormLine("1010", "순이자이익", 1, "KRW", ni,
                 formula=f"영업수익 − 비이자이익 · 이자/비이자 구분은 {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1011", "이자수익", 2, "KRW",
                 float(df["interest_income"].sum()),
                 formula=f"순이자이익 − 이자비용 — 총액 분해는 {_DERIVED} "
                         f"(순액은 실측)", citation=_C99, source_module=_M_DER),
        FormLine("1012", "이자비용", 2, "KRW",
                 float(df["interest_expense"].sum()),
                 formula=f"−순이자이익 × 국가별 조달배수 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "비이자이익", 1, "KRW", non,
                 formula=f"영업수익 × 자산군별 비이자 비중 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "판매관리비", 0, "KRW", inc["영업비용"],
                 formula="portfolio.operating_cost 해외분 실측 합 (비용은 음수)",
                 citation=_C99, source_module=_M_PTF),
        FormLine("3000", "충당금 전입액", 0, "KRW", inc["충당금 전입액"],
                 formula="은행 전체 전입액 × 해외 ECL 비중 — 배분 기준은 실측",
                 citation="IFRS 9 5.5", source_module=_M_ECL),
        FormLine("4000", "운영손실", 0, "KRW", inc["운영손실"],
                 formula="은행 전체 운영손실 × 해외 영업수익 비중 — OPE25 "
                         "사업지표가 수익 기반이라 수익으로 배분한다",
                 citation="Basel III OPE25 신표준방법", source_module=_M_OPR),
        FormLine("5000", "법인세차감전순이익", 0, "KRW",
                 inc["법인세차감전순이익"],
                 formula="영업수익 + 판매관리비 + 충당금 전입액 + 운영손실",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("6000", "법인세비용", 0, "KRW", inc["법인세비용"],
                 formula=f"max(0, 세전이익) × {CORPORATE_TAX_RATE:.1%} — 실효세율은"
                         f" `financials.CORPORATE_TAX_RATE` 가정치",
                 citation=_C99, source_module=_M_PRU),
        FormLine("7000", "당기순이익", 0, "KRW", inc["당기순이익"],
                 formula="법인세차감전순이익 + 법인세비용", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
    ]
    rev_c, ni_c, non_c, opx_c = [], [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 8000 + i * 100
        s = df[df["country"] == country]
        rev_c.append(str(base))
        ni_c.append(str(base + 10))
        non_c.append(str(base + 20))
        opx_c.append(str(base + 30))
        L += [
            FormLine(str(base), f"소재국 · {country} 영업수익", 1, "KRW",
                     float(s["revenue"].sum()),
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_PTF, is_subtotal=True),
            FormLine(str(base + 10), "순이자이익", 2, "KRW",
                     float(s["net_interest"].sum()),
                     formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 20), "비이자이익", 2, "KRW",
                     float(s["noninterest"].sum()),
                     formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 30), "판매관리비", 2, "KRW",
                     -float(s["operating_cost"].sum()),
                     formula=f"operating_cost 실측 합 (음수) · {_MEASURED}",
                     citation=_C99, source_module=_M_PTF),
        ]
    t = _tol(inc["영업수익"])
    return L, [
        _sum_check("영업수익 = 순이자이익 + 비이자이익", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("순이자이익 = 이자수익 + 이자비용", L, "1010",
                   ("1011", "1012"), t),
        _sum_check("세전이익 = 수익 + 판관비 + 충당금 + 운영손실", L, "5000",
                   ("1000", "2000", "3000", "4000"), t),
        _sum_check("당기순이익 = 세전이익 + 법인세비용", L, "7000",
                   ("5000", "6000"), t),
        _sum_check("소재국별 영업수익 합 = 영업수익", L, "1000", tuple(rev_c), t),
        _sum_check("소재국별 순이자이익 합 = 순이자이익", L, "1010", tuple(ni_c), t),
        _sum_check("소재국별 비이자이익 합 = 비이자이익", L, "1020", tuple(non_c), t),
        _sum_check("소재국별 판매관리비 합 = 판매관리비", L, "2000", tuple(opx_c), t),
    ]


# ---------------------------------------------------------------- BF502

def _bf502(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """이자부분 손익증감 현황 — 전기는 국가×항목 단위 파생이라 위로 더해도 맞는다."""
    ip = interest_prior(ctx)
    cur_i, pri_i = float(ip["interest_income"].sum()), float(ip["prior_income"].sum())
    cur_e, pri_e = float(ip["interest_expense"].sum()), float(ip["prior_expense"].sum())
    src = f"전기말 실적 원장이 없어 항목별 증감률을 뽑아 역산 · {_DERIVED}"
    L = [
        FormLine("1000", "이자수익 (당기)", 0, "KRW", cur_i,
                 formula=f"순이자이익 − 이자비용 — 총액 분해는 {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "이자수익 (전기)", 1, "KRW", pri_i, formula=src,
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "이자수익 증감액", 1, "KRW", cur_i - pri_i,
                 formula="당기 − 전기", citation=_C99, source_module=_M_DER),
        FormLine("1030", "이자수익 증감률", 1, "ratio", _r(cur_i - pri_i, pri_i),
                 formula="증감액 ÷ 전기", citation=_C99, source_module=_M_DER),
        FormLine("2000", "이자비용 (당기)", 0, "KRW", cur_e,
                 formula=f"−순이자이익 × 국가별 조달배수 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "이자비용 (전기)", 1, "KRW", pri_e, formula=src,
                 citation=_C99, source_module=_M_DER),
        FormLine("2020", "이자비용 증감액", 1, "KRW", cur_e - pri_e,
                 formula="당기 − 전기", citation=_C99, source_module=_M_DER),
        FormLine("2030", "이자비용 증감률", 1, "ratio", _r(cur_e - pri_e, pri_e),
                 formula="증감액 ÷ 전기", citation=_C99, source_module=_M_DER),
        FormLine("3000", "순이자이익 (당기)", 0, "KRW", cur_i + cur_e,
                 formula="이자수익 + 이자비용 — **순액은 실측**",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("3010", "순이자이익 (전기)", 1, "KRW", pri_i + pri_e,
                 formula="전기 이자수익 + 전기 이자비용", citation=_C99,
                 source_module=_M_DER),
        FormLine("3020", "순이자이익 증감액", 1, "KRW",
                 (cur_i + cur_e) - (pri_i + pri_e), formula="당기 − 전기",
                 citation=_C99, source_module=_M_DER),
        FormLine("3030", "순이자이익 증감률", 1, "ratio",
                 _r((cur_i + cur_e) - (pri_i + pri_e), pri_i + pri_e),
                 formula="증감액 ÷ 전기", citation=_C99, source_module=_M_DER),
    ]
    ci, pi_, ce, pe, checks = [], [], [], [], []
    for i, (_, row) in enumerate(ip.iterrows(), start=1):
        base = 4000 + i * 100
        ci.append(str(base))
        pi_.append(str(base + 10))
        ce.append(str(base + 40))
        pe.append(str(base + 50))
        c = str(row["country"])
        L += [
            FormLine(str(base), f"소재국 · {c} 이자수익 (당기)", 1, "KRW",
                     float(row["interest_income"]),
                     formula=f"총액 분해는 {_DERIVED}", citation=_C99,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "이자수익 (전기)", 2, "KRW",
                     float(row["prior_income"]), formula=src, citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 20), "증감액", 2, "KRW",
                     float(row["interest_income"] - row["prior_income"]),
                     formula="당기 − 전기", citation=_C99, source_module=_M_DER),
            FormLine(str(base + 30), "증감률", 2, "ratio",
                     _r(float(row["interest_income"] - row["prior_income"]),
                        float(row["prior_income"])),
                     formula="증감액 ÷ 전기", citation=_C99, source_module=_M_DER),
            FormLine(str(base + 40), "이자비용 (당기)", 2, "KRW",
                     float(row["interest_expense"]),
                     formula=f"총액 분해는 {_DERIVED}", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 50), "이자비용 (전기)", 2, "KRW",
                     float(row["prior_expense"]), formula=src, citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 60), "순이자이익 (당기)", 2, "KRW",
                     float(row["net_interest"]),
                     formula="이자수익 + 이자비용 — 순액은 실측", citation=_C99,
                     source_module=_M_PTF),
            FormLine(str(base + 70), "순이자이익 (전기)", 2, "KRW",
                     float(row["prior_net"]),
                     formula="전기 이자수익 + 전기 이자비용", citation=_C99,
                     source_module=_M_DER),
        ]
        tc = _tol(max(abs(float(row["interest_income"])), 1.0))
        checks += [
            _sum_check(f"{c} 이자수익 당기 = 전기 + 증감액", L, str(base),
                       (str(base + 10), str(base + 20)), tc),
            _ratio_check(f"{c} 이자수익 증감률", L, str(base + 30),
                         str(base + 20), str(base + 10)),
            _sum_check(f"{c} 순이자이익 당기 = 이자수익 + 이자비용", L,
                       str(base + 60), (str(base), str(base + 40)), tc),
            _sum_check(f"{c} 순이자이익 전기 = 전기 이자수익 + 전기 이자비용", L,
                       str(base + 70), (str(base + 10), str(base + 50)), tc),
        ]
    t = _tol(cur_i)
    checks += [
        _sum_check("이자수익 당기 = 전기 + 증감액", L, "1000", ("1010", "1020"), t),
        _sum_check("이자비용 당기 = 전기 + 증감액", L, "2000", ("2010", "2020"), t),
        _sum_check("순이자이익 당기 = 전기 + 증감액", L, "3000", ("3010", "3020"), t),
        _sum_check("순이자이익 = 이자수익 + 이자비용", L, "3000", ("1000", "2000"), t),
        _sum_check("전기 순이자이익 = 전기 이자수익 + 전기 이자비용", L, "3010",
                   ("1010", "2010"), t),
        _sum_check("소재국별 당기 이자수익 합 = 합계", L, "1000", tuple(ci), t),
        _sum_check("소재국별 전기 이자수익 합 = 합계", L, "1010", tuple(pi_), t),
        _sum_check("소재국별 당기 이자비용 합 = 합계", L, "2000", tuple(ce), t),
        _sum_check("소재국별 전기 이자비용 합 = 합계", L, "2010", tuple(pe), t),
        _ratio_check("이자수익 증감률", L, "1030", "1020", "1010"),
        _ratio_check("이자비용 증감률", L, "2030", "2020", "2010"),
        _ratio_check("순이자이익 증감률", L, "3030", "3020", "3010"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF503

def _bf503(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """비이자부분 손익증감 현황 — 총액은 실측, 항목 구성과 전기는 파생이다."""
    mix = noninterest_mix(ctx)
    prior = {k: prior_amount(f"비이자:{k}", v) for k, v in mix.items()}
    cur = sum(mix.values())
    pri = sum(prior.values())
    L = [
        FormLine("1000", "비이자이익 (당기)", 0, "KRW", cur,
                 formula=f"영업수익 × 비이자 비중 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "비이자이익 (전기)", 1, "KRW", pri,
                 formula=f"전기말 실적 원장 부재 — 항목별 증감률 역산 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "증감액", 1, "KRW", cur - pri, formula="당기 − 전기",
                 citation=_C99, source_module=_M_DER),
        FormLine("1030", "증감률", 1, "ratio", _r(cur - pri, pri),
                 formula="증감액 ÷ 전기", citation=_C99, source_module=_M_DER),
    ]
    c_codes, p_codes, d_codes, checks = [], [], [], []
    for i, item in enumerate(NONINT_ITEMS, start=1):
        base = 2000 + i * 100
        c_codes.append(str(base))
        p_codes.append(str(base + 10))
        d_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"항목 · {item} (당기)", 1, "KRW", mix[item],
                     formula=f"비이자이익 × 항목 구성비 — 구성비만 {_DERIVED}",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "전기", 2, "KRW", prior[item],
                     formula=f"전기말 실적 원장 부재 — 증감률 역산 · {_DERIVED}", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 20), "증감액", 2, "KRW", mix[item] - prior[item],
                     formula="당기 − 전기", citation=_C99, source_module=_M_DER),
            FormLine(str(base + 30), "증감률", 2, "ratio",
                     _r(mix[item] - prior[item], prior[item]),
                     formula="증감액 ÷ 전기", citation=_C99, source_module=_M_DER),
        ]
        checks += [
            _sum_check(f"{item} 당기 = 전기 + 증감액", L, str(base),
                       (str(base + 10), str(base + 20)), _tol(max(cur, 1.0))),
            _ratio_check(f"{item} 증감률", L, str(base + 30), str(base + 20),
                         str(base + 10)),
        ]
    t = _tol(max(cur, 1.0))
    checks += [
        _sum_check("항목별 당기 합 = 비이자이익", L, "1000", tuple(c_codes), t),
        _sum_check("항목별 전기 합 = 전기 비이자이익", L, "1010", tuple(p_codes), t),
        _sum_check("항목별 증감액 합 = 증감액", L, "1020", tuple(d_codes), t),
        _sum_check("당기 = 전기 + 증감액", L, "1000", ("1010", "1020"), t),
        _ratio_check("비이자이익 증감률", L, "1030", "1020", "1010"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF504

def _bf504(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """유가증권 운용손익 — 총액·잔액은 실측, 이자/평가/처분 구분만 파생이다."""
    sec = overseas_securities(ctx).merge(
        ctx.portfolio[["exposure_id", "revenue"]], on="exposure_id")
    sp = security_pnl(ctx)
    total = float(sec["revenue"].sum())
    bal = float(sec["balance"].sum())
    L = [
        FormLine("1000", "유가증권 운용손익 합계", 0, "KRW", total,
                 formula=f"유가증권 프록시 {len(sec):,}종목 revenue 실측 합 · "
                         f"{_MEASURED}", citation=_C99, source_module=_M_PTF,
                 is_subtotal=True),
    ]
    item_codes = []
    for i, item in enumerate(SEC_PNL_ITEMS, start=1):
        code = str(1000 + i * 10)
        item_codes.append(code)
        L.append(FormLine(code, f"구분 · {item}", 1, "KRW", sp[item],
                          formula=f"합계 × 구분 구성비 — 구성비만 {_DERIVED}",
                          citation=_C99, source_module=_M_DER))
    type_codes, bal_codes, checks = [], [], []
    for i, (stype, sub) in enumerate(sec.groupby("security_type"), start=1):
        base = 2000 + i * 100
        type_codes.append(str(base))
        bal_codes.append(str(base + 10))
        pl = float(sub["revenue"].sum())
        sb = float(sub["balance"].sum())
        L += [
            FormLine(str(base), f"종류 · {stype} 운용손익", 1, "KRW", pl,
                     formula=f"{len(sub):,}종목 · {_MEASURED}", citation=_C99,
                     source_module=_M_PTF, is_subtotal=True),
            FormLine(str(base + 10), "잔액", 2, "KRW", sb, citation=_C63,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "운용수익률", 2, "ratio", _r(pl, sb),
                     formula="운용손익 ÷ 잔액", citation=_C99,
                     source_module=_M_PTF),
        ]
        checks.append(_ratio_check(f"{stype} 운용수익률", L, str(base + 20),
                                   str(base), str(base + 10)))
    ctry_codes = []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        code = str(3000 + i * 10)
        ctry_codes.append(code)
        s = sec[sec["country"] == country]
        L.append(FormLine(code, f"발행국 · {country} 운용손익", 1, "KRW",
                          float(s["revenue"].sum()),
                          formula=f"{len(s):,}종목 · {_MEASURED}", citation=_C99,
                          source_module=_M_PTF))
    L += [
        FormLine("4000", "유가증권 잔액 합계", 0, "KRW", bal,
                 formula=f"{len(sec):,}종목 · {_MEASURED}", citation=_C63,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("4010", "운용수익률", 0, "ratio", _r(total, bal),
                 formula="운용손익 합계 ÷ 잔액 합계", citation=_C99,
                 source_module=_M_PTF),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value=("유가증권 원장이 없어 국가·은행 익스포저를 국공채·"
                             "금융채 보유로 보는 프록시를 쓴다(BF204와 같은 "
                             "프록시다). 운용손익 총액과 잔액은 실측이며 "
                             "이자수익·평가손익·처분손익 구분만 파생이다."),
                 citation=_C99, source_module=_M_DER),
    ]
    t = _tol(max(abs(total), 1.0))
    checks += [
        _sum_check("구분별 합 = 운용손익 합계", L, "1000", tuple(item_codes), t),
        _sum_check("종류별 합 = 운용손익 합계", L, "1000", tuple(type_codes), t),
        _sum_check("발행국별 합 = 운용손익 합계", L, "1000", tuple(ctry_codes), t),
        _sum_check("종류별 잔액 합 = 잔액 합계", L, "4000", tuple(bal_codes),
                   _tol(bal)),
        _ratio_check("운용수익률 = 운용손익 ÷ 잔액", L, "4010", "1000", "4000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF505

def _bf505(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """총자산순이익률 — 분자(당기순이익)와 분모(총자산)를 함께 싣는다."""
    inc = overseas_income(ctx)
    ab = allocated_balance(ctx)
    w = overseas_share(ctx)
    assets = ab["자산총계"]
    ni = inc["당기순이익"]
    df = pnl_book(ctx)
    L = [
        FormLine("1000", "당기순이익 (분자)", 0, "KRW", ni,
                 formula="영업수익 + 판관비 + 충당금 + 운영손실 + 법인세비용",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "영업수익", 1, "KRW", inc["영업수익"],
                 formula=f"revenue 해외분 실측 합 · {_MEASURED}", citation=_C99,
                 source_module=_M_PTF),
        FormLine("1020", "판매관리비", 1, "KRW", inc["영업비용"],
                 formula="operating_cost 해외분 실측 합 (음수)", citation=_C99,
                 source_module=_M_PTF),
        FormLine("1030", "충당금 전입액", 1, "KRW", inc["충당금 전입액"],
                 formula="전체 전입액 × 해외 ECL 비중 — 배분", citation="IFRS 9 5.5",
                 source_module=_M_ECL),
        FormLine("1040", "운영손실", 1, "KRW", inc["운영손실"],
                 formula="전체 운영손실 × 해외 영업수익 비중 — 배분",
                 citation="Basel III OPE25", source_module=_M_OPR),
        FormLine("1050", "법인세비용", 1, "KRW", inc["법인세비용"],
                 formula=f"max(0, 세전이익) × {CORPORATE_TAX_RATE:.1%}",
                 citation=_C99, source_module=_M_PRU),
        FormLine("2000", "총자산 (분모)", 0, "KRW", assets,
                 formula=f"본지점 합산 자산총계 × {w:.6f} — {_DERIVED_ALLOC}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("2010", "해외 여신잔액 (참고·실측)", 1, "KRW",
                 float(df["balance"].sum()),
                 formula=f"익스포저 {len(df):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM),
        FormLine("3000", "총자산순이익률 (ROA)", 0, "ratio", _r(ni, assets),
                 formula="당기순이익 ÷ 총자산", citation=_C31,
                 source_module=_M_PRU),
        FormLine("3010", "총자산경상이익률 (세전)", 0, "ratio",
                 _r(inc["법인세차감전순이익"], assets),
                 formula="법인세차감전순이익 ÷ 총자산", citation=_C31,
                 source_module=_M_PRU),
        FormLine("3020", "법인세차감전순이익", 1, "KRW",
                 inc["법인세차감전순이익"], formula="당기순이익 − 법인세비용",
                 citation=_C99, source_module=_M_PRU),
    ]
    t = _tol(assets)
    return L, [
        _sum_check("당기순이익 = 손익 구성 합", L, "1000",
                   ("1010", "1020", "1030", "1040", "1050"), _tol(inc["영업수익"])),
        _sum_check("당기순이익 = 세전이익 + 법인세비용", L, "1000",
                   ("3020", "1050"), _tol(inc["영업수익"])),
        _ratio_check("ROA = 당기순이익 ÷ 총자산", L, "3000", "1000", "2000"),
        _ratio_check("세전 ROA = 세전이익 ÷ 총자산", L, "3010", "3020", "2000"),
        FormCheck("해외 여신잔액 ≤ 총자산", 0.0,
                  max(0.0, float(df["balance"].sum()) - assets), t),
    ]


# ---------------------------------------------------------------- BF506

def _bf506(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """총자산경비율 — 판매관리비 ÷ 총자산. 국가별 자산은 잔액 비중 배분이다."""
    df = pnl_book(ctx)
    ab = allocated_balance(ctx)
    assets = ab["자산총계"]
    opex = float(df["operating_cost"].sum())
    bal_all = float(df["balance"].sum())
    L = [
        FormLine("1000", "판매관리비 (분자)", 0, "KRW", opex,
                 formula=f"operating_cost 해외분 실측 합 (절대값) · {_MEASURED}",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("2000", "총자산 (분모)", 0, "KRW", assets,
                 formula=f"본지점 합산 자산총계 × {overseas_share(ctx):.6f} — "
                         f"{_DERIVED_ALLOC}", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("3000", "총자산경비율", 0, "ratio", _r(opex, assets),
                 formula="판매관리비 ÷ 총자산", citation=_C31,
                 source_module=_M_PRU),
    ]
    o_codes, a_codes, checks = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 4000 + i * 100
        s = df[df["country"] == country]
        o = float(s["operating_cost"].sum())
        a = assets * _r(float(s["balance"].sum()), bal_all)
        o_codes.append(str(base))
        a_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 판매관리비", 1, "KRW", o,
                     formula=f"{len(s):,}건 실측 합 · {_MEASURED}", citation=_C99,
                     source_module=_M_PTF, is_subtotal=True),
            FormLine(str(base + 10), "총자산", 2, "KRW", a,
                     formula="해외 총자산 × 국가별 여신잔액 비중 — 배분",
                     citation=_C99, source_module=_M_PRU),
            FormLine(str(base + 20), "총자산경비율", 2, "ratio", _r(o, a),
                     formula="판매관리비 ÷ 총자산", citation=_C31,
                     source_module=_M_PRU),
        ]
        checks.append(_ratio_check(f"{country} 총자산경비율", L, str(base + 20),
                                   str(base), str(base + 10)))
    checks += [
        _sum_check("소재국별 판매관리비 합 = 합계", L, "1000", tuple(o_codes),
                   _tol(opex)),
        _sum_check("소재국별 총자산 합 = 총자산", L, "2000", tuple(a_codes),
                   _tol(assets)),
        _ratio_check("총자산경비율 = 판관비 ÷ 총자산", L, "3000", "1000", "2000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF507

def _bf507(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """순이자마진율 — 분모는 이자수익자산(총자산 − 기타자산)이다."""
    df = pnl_book(ctx)
    ab = allocated_balance(ctx)
    ni = float(df["net_interest"].sum())
    ii = float(df["interest_income"].sum())
    ie = float(df["interest_expense"].sum())
    parts = ("현금 및 예치금", "유가증권 (Level 2A)", "유가증권 (Level 2B)",
             "대출채권 (총액)")
    earning = sum(ab[p] for p in parts)
    bal_all = float(df["balance"].sum())
    L = [
        FormLine("1000", "순이자이익 (분자)", 0, "KRW", ni,
                 formula=f"영업수익 − 비이자이익 · 구분은 {_DERIVED} (순액은 실측)",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "이자수익", 1, "KRW", ii,
                 formula=f"총액 분해는 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1020", "이자비용", 1, "KRW", ie,
                 formula=f"총액 분해는 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("2000", "이자수익자산 (분모)", 0, "KRW", earning,
                 formula="현금·예치금 + 유가증권 + 대출채권(총액) — 기타자산 제외",
                 citation=_C63, source_module=_M_PRU, is_subtotal=True),
    ]
    part_codes = []
    for i, p in enumerate(parts, start=1):
        code = str(2000 + i * 10)
        part_codes.append(code)
        note = (f"해외 EAD 실측 합과 같다 · {_MEASURED}" if p == "대출채권 (총액)"
                else _DERIVED_ALLOC)
        L.append(FormLine(code, p, 1, "KRW", ab[p], formula=note,
                          citation=_C99, source_module=_M_PRU))
    L += [
        FormLine("3000", "순이자마진율 (NIM)", 0, "ratio", _r(ni, earning),
                 formula="순이자이익 ÷ 이자수익자산", citation=_C31,
                 source_module=_M_DER),
        FormLine("3010", "자산운용수익률", 0, "ratio", _r(ii, earning),
                 formula="이자수익 ÷ 이자수익자산", citation=_C31,
                 source_module=_M_DER),
        FormLine("3020", "조달비용률", 0, "ratio", _r(ie, earning),
                 formula="이자비용 ÷ 이자수익자산 (음수 표시)", citation=_C31,
                 source_module=_M_DER),
    ]
    n_codes, e_codes, checks = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 4000 + i * 100
        s = df[df["country"] == country]
        n = float(s["net_interest"].sum())
        e = earning * _r(float(s["balance"].sum()), bal_all)
        n_codes.append(str(base))
        e_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 순이자이익", 1, "KRW", n,
                     formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "이자수익자산", 2, "KRW", e,
                     formula="해외 이자수익자산 × 국가별 여신잔액 비중 — 배분",
                     citation=_C63, source_module=_M_PRU),
            FormLine(str(base + 20), "순이자마진율", 2, "ratio", _r(n, e),
                     formula="순이자이익 ÷ 이자수익자산", citation=_C31,
                     source_module=_M_DER),
        ]
        checks.append(_ratio_check(f"{country} 순이자마진율", L, str(base + 20),
                                   str(base), str(base + 10)))
    t = _tol(earning)
    checks += [
        _sum_check("순이자이익 = 이자수익 + 이자비용", L, "1000",
                   ("1010", "1020"), _tol(max(abs(ii), 1.0))),
        _sum_check("이자수익자산 = 계정별 합", L, "2000", tuple(part_codes), t),
        _sum_check("소재국별 순이자이익 합 = 순이자이익", L, "1000", tuple(n_codes),
                   _tol(max(abs(ni), 1.0))),
        _sum_check("소재국별 이자수익자산 합 = 이자수익자산", L, "2000",
                   tuple(e_codes), t),
        _ratio_check("NIM = 순이자이익 ÷ 이자수익자산", L, "3000", "1000", "2000"),
        _ratio_check("자산운용수익률", L, "3010", "1010", "2000"),
        _ratio_check("조달비용률", L, "3020", "1020", "2000"),
        _sum_check("NIM = 자산운용수익률 + 조달비용률", L, "3000",
                   ("3010", "3020"), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- BF508

def _bf508(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """경비보상비율 — 비이자이익이 판매관리비를 얼마나 덮는지 본다."""
    df = pnl_book(ctx)
    non = float(df["noninterest"].sum())
    opex = float(df["operating_cost"].sum())
    L = [
        FormLine("1000", "비이자이익 (분자)", 0, "KRW", non,
                 formula=f"영업수익 × 비이자 비중 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "판매관리비 (분모)", 0, "KRW", opex,
                 formula=f"operating_cost 해외분 실측 합 (절대값) · {_MEASURED}",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("3000", "경비보상비율", 0, "ratio", _r(non, opex),
                 formula="비이자이익 ÷ 판매관리비", citation=_C31,
                 source_module=_M_DER),
    ]
    n_codes, o_codes, checks = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 4000 + i * 100
        s = df[df["country"] == country]
        n = float(s["noninterest"].sum())
        o = float(s["operating_cost"].sum())
        n_codes.append(str(base))
        o_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 비이자이익", 1, "KRW", n,
                     formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "판매관리비", 2, "KRW", o,
                     formula=f"{len(s):,}건 실측 합 · {_MEASURED}", citation=_C99,
                     source_module=_M_PTF),
            FormLine(str(base + 20), "경비보상비율", 2, "ratio", _r(n, o),
                     formula="비이자이익 ÷ 판매관리비", citation=_C31,
                     source_module=_M_DER),
        ]
        checks.append(_ratio_check(f"{country} 경비보상비율", L, str(base + 20),
                                   str(base), str(base + 10)))
    checks += [
        _sum_check("소재국별 비이자이익 합 = 합계", L, "1000", tuple(n_codes),
                   _tol(max(non, 1.0))),
        _sum_check("소재국별 판매관리비 합 = 합계", L, "2000", tuple(o_codes),
                   _tol(opex)),
        _ratio_check("경비보상비율 = 비이자이익 ÷ 판관비", L, "3000", "1000", "2000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF509

def _bf509(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """이익경비율 — 판매관리비 ÷ 총이익. 총이익이 영업수익 실측과 같아야 한다."""
    df = pnl_book(ctx)
    ni = float(df["net_interest"].sum())
    non = float(df["noninterest"].sum())
    opex = float(df["operating_cost"].sum())
    rev = float(df["revenue"].sum())
    L = [
        FormLine("1000", "총이익 (분모)", 0, "KRW", ni + non,
                 formula="순이자이익 + 비이자이익", citation=_C31,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "순이자이익", 1, "KRW", ni,
                 formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1020", "비이자이익", 1, "KRW", non,
                 formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1030", "영업수익 (실측·대사용)", 1, "KRW", rev,
                 formula=f"revenue 해외분 실측 합 · {_MEASURED}", citation=_C99,
                 source_module=_M_PTF),
        FormLine("2000", "판매관리비 (분자)", 0, "KRW", opex,
                 formula=f"operating_cost 해외분 실측 합 (절대값) · {_MEASURED}",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("3000", "이익경비율", 0, "ratio", _r(opex, ni + non),
                 formula="판매관리비 ÷ 총이익", citation=_C31,
                 source_module=_M_DER),
    ]
    g_codes, o_codes, checks = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 4000 + i * 100
        s = df[df["country"] == country]
        g = float(s["revenue"].sum())
        o = float(s["operating_cost"].sum())
        g_codes.append(str(base))
        o_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 총이익", 1, "KRW", g,
                     formula=f"{len(s):,}건 실측 합 · {_MEASURED}", citation=_C31,
                     source_module=_M_PTF, is_subtotal=True),
            FormLine(str(base + 10), "판매관리비", 2, "KRW", o,
                     formula=f"실측 합 · {_MEASURED}", citation=_C99,
                     source_module=_M_PTF),
            FormLine(str(base + 20), "이익경비율", 2, "ratio", _r(o, g),
                     formula="판매관리비 ÷ 총이익", citation=_C31,
                     source_module=_M_PTF),
        ]
        checks.append(_ratio_check(f"{country} 이익경비율", L, str(base + 20),
                                   str(base + 10), str(base)))
    t = _tol(rev)
    checks += [
        _sum_check("총이익 = 순이자이익 + 비이자이익", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("총이익 = 영업수익 실측", L, "1000", ("1030",), t),
        _sum_check("소재국별 총이익 합 = 총이익", L, "1000", tuple(g_codes), t),
        _sum_check("소재국별 판매관리비 합 = 판매관리비", L, "2000",
                   tuple(o_codes), _tol(opex)),
        _ratio_check("이익경비율 = 판관비 ÷ 총이익", L, "3000", "2000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF601

def _bf601(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자기자본 산출근거 — **배분자본이다. 본점 자기자본을 그대로 쓰지 않는다.**"""
    cap = ctx.result.meta["capital"]
    w = overseas_share(ctx)
    inc = overseas_income(ctx)
    ab = allocated_balance(ctx)
    L = [
        FormLine("1000", "본점 자기자본 (총자본)", 0, "KRW", float(cap.total),
                 formula="보통주자본 + 기타기본자본 + 보완자본", citation=_CRE40,
                 source_module=_M_BIS, is_subtotal=True),
        FormLine("1100", "보통주자본 (CET1)", 1, "KRW", float(cap.cet1),
                 citation="Basel III CRE40.1~40.26", source_module=_M_BIS),
        FormLine("1200", "기타기본자본 (AT1)", 1, "KRW",
                 float(cap.additional_t1),
                 citation="Basel III CRE40.27~40.41", source_module=_M_BIS),
        FormLine("1300", "보완자본 (Tier 2)", 1, "KRW", float(cap.tier2),
                 citation="Basel III CRE40.42~40.56", source_module=_M_BIS),
        FormLine("1400", "기본자본 (Tier 1)", 1, "KRW", float(cap.tier1),
                 formula="보통주자본 + 기타기본자본", citation=_CRE40,
                 source_module=_M_BIS, is_subtotal=True),
        FormLine("2000", "해외영업점 배분비율", 0, "ratio", w,
                 formula="해외 EAD ÷ 전체 EAD — BF201 대차대조표 배분과 같은 비율",
                 citation=_C99, source_module=_M_DER_A),
        FormLine("3000", "해외영업점 자기자본", 0, "KRW", float(cap.total) * w,
                 formula=_ALLOC_CAP, citation=_C26, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("3100", "배분 보통주자본 (CET1)", 1, "KRW", float(cap.cet1) * w,
                 formula=_ALLOC_CAP, citation="Basel III CRE40.1~40.26",
                 source_module=_M_DER),
        FormLine("3200", "배분 기타기본자본 (AT1)", 1, "KRW",
                 float(cap.additional_t1) * w, formula=_ALLOC_CAP,
                 citation="Basel III CRE40.27~40.41", source_module=_M_DER),
        FormLine("3300", "배분 보완자본 (Tier 2)", 1, "KRW", float(cap.tier2) * w,
                 formula=_ALLOC_CAP, citation="Basel III CRE40.42~40.56",
                 source_module=_M_DER),
        FormLine("3400", "배분 기본자본 (Tier 1)", 1, "KRW", float(cap.tier1) * w,
                 formula="배분 CET1 + 배분 AT1", citation=_CRE40,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("4000", "해외 당기순이익 (유보이익 원천·참고)", 0, "KRW",
                 inc["당기순이익"],
                 formula="해외 손익계산서 당기순이익 — 차기 배분자본의 증감 요인",
                 citation=_C99, source_module=_M_PRU),
        FormLine("5000", "BF201 배분 규제자본 합계 (대사용)", 0, "KRW",
                 ab["규제자본 합계 (참고)"],
                 formula=f"본지점 합산 규제자본 × {w:.6f} — 같은 비율이므로 "
                         f"해외영업점 자기자본과 일치해야 한다", citation=_C99,
                 source_module=_M_PRU),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value=("해외영업점 자본계정 원장이 없다. 본 서식의 자기자본은 "
                             "본점 자기자본을 해외 익스포저 실측 비중으로 배분한 "
                             "값이며, 대차대조표(BF201)가 쓰는 비율과 같은 비율을 "
                             "쓴다. 배분 결과는 파생값이고 비율은 실측이다."),
                 citation=_C99, source_module=_M_DER),
    ]
    t = _tol(float(cap.total))
    return L, [
        _sum_check("본점 자기자본 = CET1 + AT1 + T2", L, "1000",
                   ("1100", "1200", "1300"), t),
        _sum_check("본점 기본자본 = CET1 + AT1", L, "1400", ("1100", "1200"), t),
        _sum_check("배분 자기자본 = 배분 CET1 + AT1 + T2", L, "3000",
                   ("3100", "3200", "3300"), t),
        _sum_check("배분 기본자본 = 배분 CET1 + AT1", L, "3400",
                   ("3100", "3200"), t),
        FormCheck("배분 자기자본 = 본점 자기자본 × 배분비율",
                  float(cap.total) * w, _val(L, "3000"), t),
        _sum_check("배분 자기자본 = BF201 배분 규제자본", L, "3000", ("5000",), t),
    ]


# ---------------------------------------------------------------- BF601-1

def _capital_alloc_block(tbl: pd.DataFrame, base: int, title: str, w: float,
                         total: float) -> tuple[list[FormLine], tuple[str, ...]]:
    """자본 항목 명세 × 배분비율 — 항목별로 배분임을 남긴다.

    소계에만 '배분'을 적으면 서식이 flat table로 실체화될 때 하위 셀이 실측으로
    읽힌다.
    """
    L = [FormLine(str(base), title, 0, "KRW", total * w,
                  formula=_ALLOC_CAP, citation=_CRE40, source_module=_M_DER,
                  is_subtotal=True)]
    codes = []
    for i, (_, r) in enumerate(tbl.iterrows(), start=1):
        code = str(base + i)
        codes.append(code)
        L.append(FormLine(
            code, str(r["item"]), 1, "KRW", float(r["amount"]) * w,
            formula=f"본점 {float(r['amount']):,.0f}원 × {w:.6f} · "
                    f"{r['sign']} 부호 — 배분",
            citation=str(r["ref"]), source_module=_M_DER))
    return L, tuple(codes)


def _bf601_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자기자본 산출근거(해외영업점, 바젤Ⅲ) — 항목별 명세에 배분비율을 곱한다."""
    cap = ctx.result.meta["capital"]
    bd = ctx.result.bis_deep
    w = overseas_share(ctx)
    L = [
        FormLine("1000", "해외영업점 배분비율", 0, "ratio", w,
                 formula="해외 EAD ÷ 전체 EAD — BF201·BF601과 같은 비율",
                 citation=_C99, source_module=_M_DER_A),
    ]
    blocks = (
        (2000, "배분 보통주자본 (CET1) 명세", bd.cet1_table, float(cap.cet1)),
        (3000, "배분 기타기본자본 (AT1) 명세", bd.at1_table,
         float(cap.additional_t1)),
        (4000, "배분 보완자본 (Tier 2) 명세", bd.tier2_table, float(cap.tier2)),
    )
    checks = []
    for base, title, tbl, amount in blocks:
        lines, codes = _capital_alloc_block(tbl, base, title, w, amount)
        L += lines
        checks.append(_sum_check(f"{title} 항목 합 = 소계", L, str(base), codes,
                                 _tol(amount * w)))
    L += [
        FormLine("8000", "배분 기본자본 (Tier 1)", 0, "KRW", float(cap.tier1) * w,
                 formula="배분 CET1 + 배분 AT1", citation=_CRE40,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("8010", "배분 자기자본 (총자본)", 0, "KRW", float(cap.total) * w,
                 formula="배분 기본자본 + 배분 보완자본", citation=_CRE40,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value=("바젤Ⅲ 자본 항목 명세는 본점 기준으로만 산출된다. "
                             "해외영업점 몫은 전 항목에 같은 배분비율을 곱해 만든 "
                             "파생값이며, 같은 비율을 쓰므로 항목 합계와 소계의 "
                             "대사가 배분 후에도 성립한다."),
                 citation=_C99, source_module=_M_DER),
    ]
    t = _tol(float(cap.total) * w)
    checks += [
        _sum_check("배분 기본자본 = CET1 + AT1 소계", L, "8000",
                   ("2000", "3000"), t),
        _sum_check("배분 자기자본 = 기본자본 + 보완자본 소계", L, "8010",
                   ("8000", "4000"), t),
    ]
    return L, checks


# ---------------------------------------------------------------- BF602

def _rwa_block(ctx, base: int) -> tuple[list[FormLine], tuple[str, ...], dict]:
    """해외 위험가중자산 구성 — 신용은 실측, 나머지는 근거를 밝힌 비중 배분이다."""
    ov = overseas_rwa(ctx)
    rows = (
        ("신용리스크 (실측)", ov["credit"],
         f"rwa_result 해외 익스포저 실측 합 · {_MEASURED}", _CRE20, _M_RWA),
        ("거래상대방신용리스크 (SA-CCR + CVA)", ov["ccr"],
         f"본점 CCR RWA × 해외 거래상대방 비중 {ov['ccr_share']:.6f} — "
         f"거래상대방 소재국은 원장 실측", "Basel III CRE52 · MAR50", _M_CCR),
        ("시장리스크", ov["market"],
         f"본점 시장 RWA × {ov['market_share']:.6f} — 트레이딩계정에 소재국 "
         f"귀속이 없어 EAD 비중 배분", "Basel III MAR40", _M_MKT),
        ("운영리스크", ov["op"],
         f"본점 운영 RWA × 해외 영업수익 비중 {ov['op_share']:.6f} — OPE25 "
         f"사업지표가 수익 기반", "Basel III OPE25", _M_OPR),
        ("산출하한 조정분", ov["floor"],
         "본점 하한 조정분 × 해외 신용 RWA 비중 — 배분",
         "Basel III RBC20.11", "risk_lib.capital.output_floor"),
    )
    L, codes = [], []
    for i, (name, value, formula, cit, mod) in enumerate(rows, start=1):
        code = str(base + i * 10)
        codes.append(code)
        L.append(FormLine(code, name, 1, "KRW", value, formula=formula,
                          citation=cit, source_module=mod))
    return L, tuple(codes), ov


def _bf602(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """BIS기준 자기자본 비율 — 배분자본 ÷ 해외 귀속 위험가중자산."""
    from risk_lib.capital.bis import BIS_MINIMUMS

    cap = ctx.result.meta["capital"]
    w = overseas_share(ctx)
    rwa_lines, rwa_codes, ov = _rwa_block(ctx, 2000)
    total_rwa = ov["total"]
    own = float(cap.total) * w
    t1 = float(cap.tier1) * w
    min_total = float(BIS_MINIMUMS["total"])
    L = [
        FormLine("1000", "해외영업점 자기자본", 0, "KRW", own,
                 formula=_ALLOC_CAP, citation=_C26, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1010", "해외영업점 기본자본", 1, "KRW", t1,
                 formula=_ALLOC_CAP, citation=_CRE40, source_module=_M_DER),
        FormLine("2000", "해외 위험가중자산 합계", 0, "KRW", total_rwa,
                 formula="신용(실측) + CCR + 시장 + 운영 + 산출하한",
                 citation=_CRE20, source_module=_M_RWA, is_subtotal=True),
    ] + rwa_lines + [
        FormLine("3000", "자기자본비율 (총자본비율)", 0, "ratio",
                 _r(own, total_rwa), formula="해외영업점 자기자본 ÷ 해외 RWA",
                 citation=_C26, source_module=_M_DER),
        FormLine("3010", "기본자본비율", 0, "ratio", _r(t1, total_rwa),
                 formula="해외영업점 기본자본 ÷ 해외 RWA", citation=_C26,
                 source_module=_M_DER),
        FormLine("4000", "최저 총자본비율", 0, "ratio", min_total,
                 formula="risk_lib.capital.bis.BIS_MINIMUMS 참조",
                 citation="은행업감독규정 제26조 제1항", source_module=_M_BIS),
        FormLine("5000", "잉여(+)·부족(−)", 0, "ratio",
                 _r(own, total_rwa) - min_total, formula="실측 비율 − 최저기준",
                 citation=_C26, source_module=_M_DER),
        FormLine("6000", "본점 총자본비율 (참고)", 0, "ratio",
                 float(ctx.result.bis.total_ratio),
                 formula="본점 자기자본 ÷ 본점 RWA — 자본은 EAD 비중, RWA는 "
                         "위험도 기준이라 해외 비율과 다르다", citation=_C26,
                 source_module=_M_BIS),
        FormLine("6010", "해외 RWA 밀도", 0, "ratio",
                 _r(total_rwa, float(pnl_book(ctx)["ead"].sum())),
                 formula="해외 RWA ÷ 해외 EAD", citation=_CRE20,
                 source_module=_M_RWA),
        FormLine("9000", "배분 범위 비고", 0, "text", None,
                 text_value=(
                     f"본점 구조화 위험가중자산 "
                     f"{float(ctx.result.rwa.get('structured_total', 0.0)):,.0f}"
                     f"원(집합투자증권·유동화)은 해외에 배분하지 않았다. "
                     f"두 원장에 소재국 축이 없어 배분 근거가 없기 때문이며, "
                     f"0은 '해외 몫이 없다'가 아니라 '배분 근거가 없다'는 뜻이다."),
                 citation="CRE60 · CRE40", source_module=_M_RWA),
    ]
    t = _tol(total_rwa)
    return L, [
        _sum_check("해외 RWA = 구성요소 합", L, "2000", rwa_codes, t),
        _ratio_check("총자본비율 = 자기자본 ÷ RWA", L, "3000", "1000", "2000"),
        _ratio_check("기본자본비율 = 기본자본 ÷ RWA", L, "3010", "1010", "2000"),
        _sum_check("총자본비율 = 최저기준 + 잉여", L, "3000", ("4000", "5000"),
                   1e-12),
        FormCheck("해외 RWA ≤ 본점 RWA", 0.0,
                  max(0.0, total_rwa - ov["group_total"]), t),
    ]


# ---------------------------------------------------------------- BF602-1

def _bf602_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """BIS기준 총자본비율(해외영업점, 바젤Ⅲ) — 3개 비율과 완충자본까지 낸다."""
    from risk_lib.capital.bis import BIS_MINIMUMS

    cap = ctx.result.meta["capital"]
    bis = ctx.result.bis
    w = overseas_share(ctx)
    rwa_lines, rwa_codes, ov = _rwa_block(ctx, 1000)
    total_rwa = ov["total"]
    cet1, t1, tot = (float(cap.cet1) * w, float(cap.tier1) * w,
                     float(cap.total) * w)
    buffer_total = float(bis.required["total"]) - float(BIS_MINIMUMS["total"])
    L = [
        FormLine("1000", "해외 위험가중자산 합계", 0, "KRW", total_rwa,
                 formula="신용(실측) + CCR + 시장 + 운영 + 산출하한",
                 citation=_CRE20, source_module=_M_RWA, is_subtotal=True),
    ] + rwa_lines + [
        FormLine("2000", "배분 보통주자본 (CET1)", 0, "KRW", cet1,
                 formula=_ALLOC_CAP, citation="Basel III CRE40.1~40.26",
                 source_module=_M_DER),
        FormLine("2010", "배분 기본자본 (Tier 1)", 0, "KRW", t1,
                 formula=_ALLOC_CAP, citation=_CRE40, source_module=_M_DER),
        FormLine("2015", "배분 보완자본 (Tier 2)", 0, "KRW", float(cap.tier2) * w,
                 formula=_ALLOC_CAP, citation="Basel III CRE40.42~40.56",
                 source_module=_M_DER),
        FormLine("2020", "배분 자기자본 (총자본)", 0, "KRW", tot,
                 formula=_ALLOC_CAP, citation=_CRE40, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("3000", "보통주자본비율", 0, "ratio", _r(cet1, total_rwa),
                 formula="배분 CET1 ÷ 해외 RWA", citation=_C26,
                 source_module=_M_DER),
        FormLine("3010", "기본자본비율", 0, "ratio", _r(t1, total_rwa),
                 formula="배분 Tier 1 ÷ 해외 RWA", citation=_C26,
                 source_module=_M_DER),
        FormLine("3020", "총자본비율", 0, "ratio", _r(tot, total_rwa),
                 formula="배분 총자본 ÷ 해외 RWA", citation=_C26,
                 source_module=_M_DER),
        FormLine("4000", "최저 보통주자본비율", 1, "ratio",
                 float(BIS_MINIMUMS["cet1"]),
                 formula="risk_lib.capital.bis.BIS_MINIMUMS 참조",
                 citation="은행업감독규정 제26조 제1항", source_module=_M_BIS),
        FormLine("4010", "최저 기본자본비율", 1, "ratio",
                 float(BIS_MINIMUMS["tier1"]), citation="은행업감독규정 제26조 제1항",
                 source_module=_M_BIS),
        FormLine("4020", "최저 총자본비율", 1, "ratio",
                 float(BIS_MINIMUMS["total"]), citation="은행업감독규정 제26조 제1항",
                 source_module=_M_BIS),
        FormLine("4100", "완충자본 합계", 1, "ratio", buffer_total,
                 formula="요구 총자본비율 − 최저 총자본비율 (자본보전 + 경기대응 "
                         "+ 시스템적 중요 은행)",
                 citation="은행업감독규정 제26조의2~제26조의4", source_module=_M_BIS),
        FormLine("5000", "요구 총자본비율 (완충 포함)", 0, "ratio",
                 float(bis.required["total"]), formula="최저 총자본비율 + 완충자본",
                 citation=_C26, source_module=_M_BIS, is_subtotal=True),
        FormLine("6000", "총자본비율 잉여(+)·부족(−)", 0, "ratio",
                 _r(tot, total_rwa) - float(bis.required["total"]),
                 formula="총자본비율 − 요구 총자본비율", citation=_C26,
                 source_module=_M_DER),
    ]
    t = _tol(total_rwa)
    return L, [
        _sum_check("해외 RWA = 구성요소 합", L, "1000", rwa_codes, t),
        _ratio_check("보통주자본비율", L, "3000", "2000", "1000"),
        _ratio_check("기본자본비율", L, "3010", "2010", "1000"),
        _ratio_check("총자본비율", L, "3020", "2020", "1000"),
        _sum_check("요구 총자본비율 = 최저 + 완충", L, "5000",
                   ("4020", "4100"), 1e-12),
        _sum_check("총자본비율 = 요구비율 + 잉여", L, "3020", ("5000", "6000"),
                   1e-12),
        _sum_check("배분 총자본 = 배분 기본자본 + 배분 보완자본", L, "2020",
                   ("2010", "2015"), _tol(tot)),
    ]


# ---------------------------------------------------------------- BF603

def _bf603(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대차대조표 계정과목별 위험가중자산 — 대출채권만 신용 RWA 산출 대상이다."""
    ab = allocated_balance(ctx)
    w = overseas_share(ctx)
    ob = overseas_book(ctx)
    rr = ctx.tables["rwa_result"].merge(
        ctx.portfolio[["exposure_id", "asset_class", "country"]],
        on="exposure_id")
    ov = rr[rr["exposure_id"].isin(set(ob["exposure_id"]))]
    credit = float(ov["rwa"].sum())
    loans = ab["대출채권 (총액)"]
    no_rwa = ("본 산출 파이프라인은 이 계정에 신용 RWA를 산출하지 않는다 — 0으로 "
              "낸다. 익스포저의 계정 매핑 원장이 있어야 산출로 바뀐다")
    L = [
        FormLine("1000", "자산총계 (해외 배분)", 0, "KRW", ab["자산총계"],
                 formula=f"본지점 합산 × {w:.6f} — {_DERIVED_ALLOC}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "현금 및 예치금", 1, "KRW", ab["현금 및 예치금"],
                 formula=_DERIVED_ALLOC, citation=_C99, source_module=_M_PRU),
        FormLine("1020", "유가증권 (Level 2A)", 1, "KRW", ab["유가증권 (Level 2A)"],
                 formula=_DERIVED_ALLOC, citation=_C99, source_module=_M_PRU),
        FormLine("1030", "유가증권 (Level 2B)", 1, "KRW", ab["유가증권 (Level 2B)"],
                 formula=_DERIVED_ALLOC, citation=_C99, source_module=_M_PRU),
        FormLine("1040", "대출채권 (순액)", 1, "KRW", ab["대출채권 (순액)"],
                 formula="총액 + 대손충당금(차감)", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("1041", "대출채권 (총액)", 2, "KRW", loans,
                 formula=f"해외 EAD 실측 합과 같다 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM),
        FormLine("1042", "대손충당금 (차감)", 2, "KRW", ab["대손충당금 (차감)"],
                 formula=_DERIVED_ALLOC, citation="IFRS 9 5.5",
                 source_module=_M_ECL),
        FormLine("1050", "기타자산", 1, "KRW", ab["기타자산"],
                 formula=_DERIVED_ALLOC, citation=_C99, source_module=_M_PRU),
        FormLine("2000", "계정과목 대응 위험가중자산 합계", 0, "KRW", credit,
                 formula=f"rwa_result 해외 익스포저 실측 합 · {_MEASURED}",
                 citation=_CRE20, source_module=_M_RWA, is_subtotal=True),
        FormLine("2010", "현금 및 예치금", 1, "KRW", 0.0, formula=no_rwa,
                 citation=_CRE20, source_module=_M_RWA),
        FormLine("2020", "유가증권 (Level 2A)", 1, "KRW", 0.0, formula=no_rwa,
                 citation=_CRE20, source_module=_M_RWA),
        FormLine("2030", "유가증권 (Level 2B)", 1, "KRW", 0.0, formula=no_rwa,
                 citation=_CRE20, source_module=_M_RWA),
        FormLine("2040", "대출채권", 1, "KRW", credit,
                 formula=f"익스포저 {len(ov):,}건 위험가중자산 실측 합",
                 citation=_CRE20, source_module=_M_RWA),
        FormLine("2050", "기타자산", 1, "KRW", 0.0, formula=no_rwa,
                 citation=_CRE20, source_module=_M_RWA),
    ]
    ead_codes, rwa_codes, checks = [], [], []
    for i, (ac, sub) in enumerate(ov.groupby("asset_class"), start=1):
        base = 3000 + i * 100
        e = float(sub["ead_final"].sum())
        rw = float(sub["rwa"].sum())
        ead_codes.append(str(base))
        rwa_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"자산군 · {ac} 익스포저", 1, "KRW", e,
                     formula=f"{len(sub):,}건 · {_MEASURED}", citation=_CRE20,
                     source_module=_M_RWA, is_subtotal=True),
            FormLine(str(base + 10), "위험가중자산", 2, "KRW", rw,
                     citation=_CRE20, source_module=_M_RWA),
            FormLine(str(base + 20), "평균 위험가중치", 2, "ratio", _r(rw, e),
                     formula="위험가중자산 ÷ 익스포저", citation=_CRE20,
                     source_module=_M_RWA),
        ]
        checks.append(_ratio_check(f"{ac} 평균 위험가중치", L, str(base + 20),
                                   str(base + 10), str(base)))
    L += [
        FormLine("8000", "해외 익스포저 (EAD) 합계", 0, "KRW",
                 float(ov["ead_final"].sum()),
                 formula=f"{len(ov):,}건 · {_MEASURED}", citation=_CRE20,
                 source_module=_M_RWA, is_subtotal=True),
        FormLine("8010", "평균 위험가중치", 0, "ratio",
                 _r(credit, float(ov["ead_final"].sum())),
                 formula="위험가중자산 합계 ÷ 익스포저 합계", citation=_CRE20,
                 source_module=_M_RWA),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value=("계정과목별 해외 원장이 없어 잔액은 해외 익스포저 실측 "
                             "비중으로 배분한다. 위험가중자산은 배분이 아니라 "
                             "익스포저별 산출값의 실측 합이며, 파이프라인이 신용 "
                             "RWA를 산출하는 계정은 대출채권뿐이다. 부외·각주계정은 "
                             "BF604에 따로 싣는다."),
                 citation=_C99, source_module=_M_DER),
    ]
    t = _tol(ab["자산총계"])
    checks += [
        _sum_check("자산총계 = 계정과목 합", L, "1000",
                   ("1010", "1020", "1030", "1040", "1050"), t),
        _sum_check("대출채권 순액 = 총액 + 대손충당금", L, "1040",
                   ("1041", "1042"), t),
        _sum_check("계정과목별 RWA 합 = 위험가중자산 합계", L, "2000",
                   ("2010", "2020", "2030", "2040", "2050"), _tol(credit)),
        _sum_check("자산군별 익스포저 합 = EAD 합계", L, "8000", tuple(ead_codes),
                   _tol(float(ov["ead_final"].sum()))),
        _sum_check("자산군별 RWA 합 = 위험가중자산 합계", L, "2000",
                   tuple(rwa_codes), _tol(credit)),
        _sum_check("대출채권(총액) = 해외 EAD 합계", L, "1041", ("8000",), t),
        _ratio_check("평균 위험가중치 = RWA ÷ EAD", L, "8010", "2000", "8000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF604

def _bf604(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """위험가중자산내역(각주계정) — 부외거래는 준용 산출이며 그 사실을 명시한다."""
    ob = overseas_book(ctx)
    ov = overseas_rwa(ctx)
    ead = float(ob["ead"].sum())
    avg_rw = _r(ov["credit"], ead)
    ccf = (ob.assign(ccf_type=ob["ccf_type"].fillna("약정 없음"))
           .groupby("ccf_type", as_index=False)
           .agg(undrawn=("undrawn", "sum"), n=("exposure_id", "count"))
           .sort_values("ccf_type"))
    L, notional_codes, cea_codes, checks = [], [], [], []
    for i, (_, r) in enumerate(ccf.iterrows(), start=1):
        base = 1000 + i * 100
        rate = float(CCF_BUCKETS.get(str(r["ccf_type"]), 0.0))
        notional = float(r["undrawn"])
        notional_codes.append(str(base))
        cea_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"약정유형 · {r['ccf_type']}", 1, "KRW", notional,
                     formula=f"미사용 약정 {int(r['n']):,}건 · {_MEASURED}",
                     citation="Basel III CRE20.94 신용환산율",
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "신용환산율 (CCF)", 2, "ratio", rate,
                     formula="risk_lib.capital.crm.CCF_BUCKETS 참조",
                     citation="Basel III CRE20.94",
                     source_module="risk_lib.capital.crm"),
            FormLine(str(base + 20), "신용환산액", 2, "KRW", notional * rate,
                     formula="명목금액 × 신용환산율", citation="Basel III CRE20.94",
                     source_module="risk_lib.capital.crm"),
        ]
        if notional > 0:
            checks.append(_ratio_check(f"{r['ccf_type']} 신용환산율 대사", L,
                                       str(base + 10), str(base + 20), str(base)))
    cea = sum(_val(L, c) for c in cea_codes)
    drv = ctx.tables["mkt_trade"].merge(
        ctx.tables["rdm_obligor"][["obligor_id", "country"]],
        left_on="counterparty", right_on="obligor_id", how="left")
    # 본점 소재국은 `HOME_COUNTRY` 한 곳에서만 온다 — 문자열을 박으면 본점 소재국을
    # 바꿨을 때 해외 판정이 이 서식에서만 조용히 어긋난다.
    drv = drv[drv["country"].fillna(HOME_COUNTRY) != HOME_COUNTRY]
    gte = ctx.tables["rdm_guarantee"].merge(
        ctx.portfolio[["exposure_id", "country"]], on="exposure_id", how="left")
    gte = gte[gte["country"].fillna(HOME_COUNTRY) != HOME_COUNTRY]
    L += [
        FormLine("5000", "미사용 약정 명목금액 합계", 0, "KRW",
                 sum(_val(L, c) for c in notional_codes),
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}",
                 citation="Basel III CRE20.94", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("5010", "신용환산액 합계", 0, "KRW", cea,
                 formula="약정유형별 명목 × 신용환산율", citation="Basel III CRE20.94",
                 source_module="risk_lib.capital.crm", is_subtotal=True),
        FormLine("6000", "파생상품 명목금액", 0, "KRW",
                 float(drv["notional"].sum()),
                 formula=f"해외 거래상대방 {len(drv):,}거래 · {_MEASURED}",
                 citation="Basel III CRE52 SA-CCR", source_module=_M_CCR,
                 is_subtotal=True),
        FormLine("6010", "거래상대방신용리스크 위험가중자산", 1, "KRW", ov["ccr"],
                 formula=f"본점 CCR RWA × 해외 거래상대방 비중 "
                         f"{ov['ccr_share']:.6f} — 소재국은 원장 실측",
                 citation="Basel III CRE52 · MAR50", source_module=_M_CCR),
        FormLine("7000", "지급보증·신용파생 보장금액", 0, "KRW",
                 float(gte["guaranteed_amount"].sum()),
                 formula=f"보증 원장 {len(gte):,}건 · {_MEASURED}",
                 citation="Basel III CRE22 적격 보장", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("8000", "해외 평균 위험가중치", 0, "ratio", avg_rw,
                 formula="해외 신용 RWA ÷ 해외 EAD — 각주계정 준용 산출의 계수. 부외 "
                         "익스포저의 계정 귀속 원장이 있어야 준용을 벗어난다",
                 citation=_CRE20, source_module=_M_RWA),
        FormLine("8010", "미사용 약정 준용 위험가중자산", 0, "KRW", cea * avg_rw,
                 formula="신용환산액 × 해외 평균 위험가중치 — **준용 산출(참고치)**. "
                         "부외 익스포저의 계정 귀속 원장이 있어야 산출로 바뀐다",
                 citation="Basel III CRE20.94", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("8020", "각주계정 위험가중자산 합계 (준용)", 0, "KRW",
                 cea * avg_rw + ov["ccr"],
                 formula="미사용 약정 준용 RWA + CCR 위험가중자산 — 준용분을 포함하므로 "
                         "부외 익스포저의 계정 귀속 원장에 걸린다",
                 citation=_CRE20, source_module=_M_DER, is_subtotal=True),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value=("파이프라인의 EAD는 미사용 약정의 신용환산분을 포함하지 "
                             "않는다. 따라서 미사용 약정 위험가중자산은 산출값이 "
                             "아니라 해외 평균 위험가중치를 곱한 준용 참고치이며, "
                             "BF602의 해외 위험가중자산 합계에는 들어가지 않는다. "
                             "명목금액·신용환산율·보장금액은 실측이다."),
                 citation=_C99, source_module=_M_DER),
    ]
    t = _tol(max(float(ob["undrawn"].sum()), 1.0))
    checks += [
        _sum_check("약정유형별 명목 합 = 명목금액 합계", L, "5000",
                   tuple(notional_codes), t),
        _sum_check("약정유형별 신용환산액 합 = 신용환산액 합계", L, "5010",
                   tuple(cea_codes), t),
        _sum_check("각주계정 준용 RWA = 약정 준용 RWA + CCR RWA", L, "8020",
                   ("8010", "6010"), _tol(max(cea * avg_rw + ov["ccr"], 1.0))),
        _ratio_check("평균 위험가중치 대사", L, "8000", "8010", "5010"),
        FormCheck("신용환산액 ≤ 명목금액 합계", 0.0,
                  max(0.0, cea - float(ob["undrawn"].sum())), t),
    ]
    return L, checks


# ---------------------------------------------------------------- BF605

def _bf605(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """단순기본자본비율 — BR-07 레버리지비율의 해외분이며 정의가 같다.

    분자·분모를 BR-07과 같은 `ctx.result.leverage`에서 가져온다. 다른 원천을
    섞으면 같은 이름의 지표가 두 값을 갖게 된다.
    """
    lev = ctx.result.leverage
    w = overseas_share(ctx)
    ob = overseas_book(ctx)
    t1 = float(lev.tier1) * w
    em = float(lev.exposure_measure) * w
    L = [
        FormLine("1000", "본점 기본자본 (Tier 1)", 0, "KRW", float(lev.tier1),
                 formula="BR-07(B2314)과 같은 산출값", citation="Basel III LEV20.5",
                 source_module=_M_LEV),
        FormLine("1010", "해외영업점 배분비율", 0, "ratio", w,
                 formula="해외 EAD ÷ 전체 EAD — BF601과 같은 비율", citation=_C99,
                 source_module=_M_DER_A),
        FormLine("1020", "배분 기본자본", 0, "KRW", t1, formula=_ALLOC_CAP,
                 citation="Basel III LEV20.5", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("2000", "본점 총익스포저 (익스포저 측정치)", 0, "KRW",
                 float(lev.exposure_measure),
                 formula="온밸런스 + 파생 + SFT + 부외 환산", citation="Basel III LEV30",
                 source_module=_M_LEV),
        FormLine("2010", "배분 총익스포저", 0, "KRW", em,
                 formula=f"본점 총익스포저 × {w:.6f} — 해외점포 부외·파생상품 원장 "
                         f"부재로 배분한 파생값", citation="Basel III LEV30",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2020", "해외 온밸런스 익스포저 (참고·실측)", 1, "KRW",
                 float(ob["ead"].sum()),
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}",
                 citation="Basel III LEV30", source_module=_M_RDM),
        FormLine("3000", "단순기본자본비율", 0, "ratio", _r(t1, em),
                 formula="배분 기본자본 ÷ 배분 총익스포저 — BR-07 레버리지비율과 "
                         "같은 정의", citation="Basel III LEV20.1",
                 source_module=_M_DER),
        FormLine("4000", "최저 단순기본자본비율", 0, "ratio", float(lev.required),
                 citation=_LEV20, source_module=_M_LEV),
        FormLine("5000", "잉여(+)·부족(−)", 0, "ratio",
                 _r(t1, em) - float(lev.required), formula="실측 비율 − 최저기준",
                 citation=_LEV20, source_module=_M_DER),
        FormLine("6000", "본점 레버리지비율 (참고)", 0, "ratio",
                 float(lev.leverage_ratio),
                 formula="분자·분모에 같은 배분비율을 곱하므로 해외 비율과 같다",
                 citation="Basel III LEV20.1", source_module=_M_LEV),
    ]
    t = _tol(em)
    return L, [
        _ratio_check("단순기본자본비율 = 기본자본 ÷ 총익스포저", L, "3000",
                     "1020", "2010"),
        FormCheck("배분 기본자본 = 본점 × 배분비율", float(lev.tier1) * w,
                  _val(L, "1020"), _tol(float(lev.tier1))),
        FormCheck("배분 총익스포저 = 본점 × 배분비율",
                  float(lev.exposure_measure) * w, _val(L, "2010"), t),
        _sum_check("비율 = 최저기준 + 잉여", L, "3000", ("4000", "5000"), 1e-12),
        FormCheck("해외 비율 = 본점 비율 (동일 배분비율)",
                  float(lev.leverage_ratio), _r(t1, em), 1e-12),
        FormCheck("온밸런스 실측 ≤ 배분 총익스포저", 0.0,
                  max(0.0, float(ob["ead"].sum()) - em), t),
    ]


# ---------------------------------------------------------------- BF606

def _bf606(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """손실위험도가중여신비율 — 잔액도 가중치도 원장이다. 서식 상수가 없다.

    가중치는 은행업감독규정 제29조 제1항 최저적립률이며 익스포저 원장
    (`rdm_asset_quality.min_provision_rate`)에서 읽는다. 그룹 서식 B2902가 같은
    열을 읽으므로 해외분과 그룹분의 정의가 갈라지지 않는다. 기업여신·가계여신의
    적립률이 다르므로 분류 단위 단일 계수로 접지 않고 익스포저 단위로 곱한다.
    """
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    bal, wtd, note = loss_weighted(ctx)
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
    ]
    bal_codes, wtd_codes, checks = [], [], []
    for i, cls in enumerate(AQ_ORDER, start=1):
        base = 2000 + i * 100
        s = ob[ob["classification"] == cls]
        b, w = bal[cls], wtd[cls]
        bal_codes.append(str(base))
        wtd_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"분류 · {cls} 잔액", 1, "KRW", b,
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C27,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "손실위험도 가중치 (가중평균)", 2, "ratio",
                     _r(w, b),
                     formula=f"적용 최저적립률 {note[cls]} — 원장 "
                             f"min_provision_rate를 읽는다 (서식 상수 아님)",
                     citation=_C29, source_module=_M_RDM),
            FormLine(str(base + 20), "손실위험도가중여신", 2, "KRW", w,
                     formula="Σ(익스포저 잔액 × 제29조 최저적립률)", citation=_C29,
                     source_module=_M_RDM),
        ]
        if b > 0:
            checks.append(_ratio_check(f"{cls} 가중치 대사", L, str(base + 10),
                                       str(base + 20), str(base)))
    lw_total = sum(wtd.values())
    L += [
        FormLine("8000", "손실위험도가중여신 합계", 0, "KRW", lw_total,
                 formula="Σ(익스포저 잔액 × 제29조 최저적립률) — 원장 실측",
                 citation=_C29, source_module=_M_RDM, is_subtotal=True),
        FormLine("8010", "손실위험도가중여신비율", 0, "ratio",
                 _r(lw_total, total), formula="손실위험도가중여신 ÷ 해외 총여신",
                 citation=_C31, source_module=_M_RDM),
        FormLine("8020", "고정이하여신 (참고)", 0, "KRW",
                 float(ob[ob["classification"].isin(NPL_CLASSES)]["balance"].sum()),
                 formula="고정 + 회수의문 + 추정손실", citation=_C27,
                 source_module=_M_RDM),
    ]
    c_bal, c_wtd = [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 9000 + i * 100
        s = ob[ob["country"] == country]
        b = float(s["balance"].sum())
        lw = loss_weighted_amount(s)
        c_bal.append(str(base))
        c_wtd.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 총여신", 1, "KRW", b,
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C27,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "손실위험도가중여신", 2, "KRW", lw,
                     formula="Σ(익스포저 잔액 × 제29조 최저적립률)", citation=_C29,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "손실위험도가중여신비율", 2, "ratio",
                     _r(lw, b), formula="가중여신 ÷ 총여신", citation=_C31,
                     source_module=_M_RDM),
        ]
        checks.append(_ratio_check(f"{country} 손실위험도가중여신비율", L,
                                   str(base + 20), str(base + 10), str(base)))
    L.append(FormLine(
        "9000", "가중치 출처", 0, "text", None,
        text_value=("손실위험도 가중치는 은행업감독규정 제29조 제1항 최저적립률을 "
                    "익스포저 원장 min_provision_rate에서 읽는다 — 서식이 가중치 "
                    "사본을 들면 규정 개정 때 조용히 갈라진다. 그룹 서식 B2902가 "
                    "같은 열을 읽으므로 해외분과 그룹분의 정의가 일치한다. "
                    "기업여신·가계여신의 적립률이 다르므로(회수의문 50% vs 55%) "
                    "분류 단위 단일 계수로 접지 않고 익스포저 단위로 곱한다."),
        citation=_C29, source_module=_M_RDM))
    t = _tol(total)
    checks += [
        _sum_check("분류별 잔액 합 = 해외 총여신", L, "1000", tuple(bal_codes), t),
        _sum_check("분류별 가중여신 합 = 합계", L, "8000", tuple(wtd_codes), t),
        _sum_check("소재국별 총여신 합 = 해외 총여신", L, "1000", tuple(c_bal), t),
        _sum_check("소재국별 가중여신 합 = 합계", L, "8000", tuple(c_wtd), t),
        _ratio_check("손실위험도가중여신비율", L, "8010", "8000", "1000"),
        # 상한은 총여신이다. "≤ 고정이하여신"은 정상·요주의 가중치가 0일 때만
        # 성립하는 항등식이며, 제29조 최저적립률은 정상 0.85%·요주의 7%로 0이
        # 아니다 — 그 조건을 걸면 가중치가 틀렸을 때만 통과하는 검증이 된다.
        FormCheck("손실위험도가중여신 ≤ 해외 총여신", 0.0,
                  max(0.0, lw_total - total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- BF701

def _bf701(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """현지직원비율 — **인사 원장이 없어 직원수 전체가 파생값이다.**"""
    sb = staff_book(ctx)
    total = float(sb["staff_total"].sum())
    local = float(sb["staff_local"].sum())
    L = [
        FormLine("1000", "해외점포 총직원수", 0, "count", total,
                 formula=f"점포별 여신잔액 ÷ 인당 관리자산 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "현지채용 직원수", 1, "count", local,
                 formula=f"총직원수 × 점포형태별 현지채용비율 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "본점 파견 직원수", 1, "count",
                 float(sb["staff_expat"].sum()),
                 formula=f"총직원수 − 현지채용 직원수 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1030", "현지직원비율", 0, "ratio", _r(local, total),
                 formula="현지채용 직원수 ÷ 총직원수", citation=_C99,
                 source_module=_M_DER),
    ]
    b_tot, b_loc, checks = [], [], []
    for i, (_, b) in enumerate(sb.iterrows(), start=1):
        base = 2000 + i * 100
        b_tot.append(str(base))
        b_loc.append(str(base + 10))
        L += [
            FormLine(str(base), f"{b['branch_code']} {b['branch_name']}", 1,
                     "count", float(b["staff_total"]),
                     formula=f"{b['country']} · {b['kind']} · {_DERIVED}",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "현지채용", 2, "count",
                     float(b["staff_local"]), formula=_DERIVED, citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 20), "본점 파견", 2, "count",
                     float(b["staff_expat"]), formula=_DERIVED, citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 30), "현지직원비율", 2, "ratio",
                     _r(float(b["staff_local"]), float(b["staff_total"])),
                     formula="현지채용 ÷ 총직원수", citation=_C99,
                     source_module=_M_DER),
        ]
        checks += [
            _sum_check(f"{b['branch_code']} 총직원 = 현지 + 파견", L, str(base),
                       (str(base + 10), str(base + 20)), 1e-9),
            _ratio_check(f"{b['branch_code']} 현지직원비율", L, str(base + 30),
                         str(base + 10), str(base)),
        ]
    c_tot, c_loc = [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 5000 + i * 100
        s = sb[sb["country"] == country]
        c_tot.append(str(base))
        c_loc.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 총직원수", 1, "count",
                     float(s["staff_total"].sum()),
                     formula=f"점포 {len(s)}개 · {_DERIVED}", citation=_C99,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "현지채용", 2, "count",
                     float(s["staff_local"].sum()), formula=_DERIVED,
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), "현지직원비율", 2, "ratio",
                     _r(float(s["staff_local"].sum()),
                        float(s["staff_total"].sum())),
                     formula="현지채용 ÷ 총직원수", citation=_C99,
                     source_module=_M_DER),
        ]
        checks.append(_ratio_check(f"{country} 현지직원비율", L, str(base + 20),
                                   str(base + 10), str(base)))
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("인사 원장이 없어 점포별 직원수와 현지채용 비율을 "
                                  "기준일 고정 시드로 파생한다. 점포별 직원수는 "
                                  "여신잔액을 인당 관리자산으로 나눈 값이고, "
                                  "현지채용 비율은 점포형태(지점·현지법인·사무소)별 "
                                  "밴드에서 뽑는다. 같은 시드면 같은 값이다."),
                      citation=_C99, source_module=_M_DER))
    checks += [
        _sum_check("총직원 = 현지채용 + 본점 파견", L, "1000", ("1010", "1020"),
                   1e-9),
        _sum_check("점포별 총직원 합 = 해외 총직원", L, "1000", tuple(b_tot), 1e-9),
        _sum_check("점포별 현지채용 합 = 현지채용", L, "1010", tuple(b_loc), 1e-9),
        _sum_check("소재국별 총직원 합 = 해외 총직원", L, "1000", tuple(c_tot), 1e-9),
        _ratio_check("현지직원비율 = 현지채용 ÷ 총직원", L, "1030", "1010", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF702

def _bf702(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """현지차입금 및 예수금비율 — 총조달은 배분, 현지조달 구분은 파생이다."""
    fb = funding_book(ctx)
    total = float(fb["funding_total"].sum())
    local = float(fb["funding_local"].sum())
    L = [
        FormLine("1000", "해외점포 총조달", 0, "KRW", total,
                 formula=f"본지점 합산 부채총계 × {overseas_share(ctx):.6f}를 "
                         f"점포별 여신잔액 비중으로 나눈 값 — {_DERIVED_ALLOC}",
                 citation=_C63, source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "현지차입금 및 예수금", 1, "KRW", local,
                 formula=f"총조달 × 점포형태별 현지조달비중 · {_DERIVED}",
                 citation=_C63, source_module=_M_DER),
        FormLine("1020", "본지점 및 역외조달", 1, "KRW",
                 float(fb["funding_hq"].sum()),
                 formula=f"총조달 − 현지조달 · {_DERIVED}", citation=_C63,
                 source_module=_M_DER),
        FormLine("1030", "현지차입금 및 예수금비율", 0, "ratio", _r(local, total),
                 formula="현지조달 ÷ 총조달", citation=_C63, source_module=_M_DER),
    ]
    b_tot, b_loc, checks = [], [], []
    for i, (_, b) in enumerate(fb.iterrows(), start=1):
        base = 2000 + i * 100
        b_tot.append(str(base))
        b_loc.append(str(base + 10))
        L += [
            FormLine(str(base), f"{b['branch_code']} {b['branch_name']}", 1,
                     "KRW", float(b["funding_total"]),
                     formula=f"{b['country']} · {b['kind']} · 여신잔액 비중 배분",
                     citation=_C63, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "현지차입금 및 예수금", 2, "KRW",
                     float(b["funding_local"]), formula=_DERIVED, citation=_C63,
                     source_module=_M_DER),
            FormLine(str(base + 20), "본지점 및 역외조달", 2, "KRW",
                     float(b["funding_hq"]), formula=_DERIVED, citation=_C63,
                     source_module=_M_DER),
            FormLine(str(base + 30), "현지조달비율", 2, "ratio",
                     _r(float(b["funding_local"]), float(b["funding_total"])),
                     formula="현지조달 ÷ 총조달", citation=_C63,
                     source_module=_M_DER),
        ]
        checks += [
            _sum_check(f"{b['branch_code']} 총조달 = 현지 + 본지점", L, str(base),
                       (str(base + 10), str(base + 20)), _tol(total)),
            _ratio_check(f"{b['branch_code']} 현지조달비율", L, str(base + 30),
                         str(base + 10), str(base)),
        ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("자금 원장에 조달처 구분이 없다. 총조달은 배분 "
                                  "부채총계를 점포별 여신잔액 비중으로 나눈 값이고, "
                                  "현지조달 비중은 점포형태별 밴드에서 뽑은 파생값이다."),
                      citation=_C63, source_module=_M_DER))
    t = _tol(total)
    checks += [
        _sum_check("총조달 = 현지조달 + 본지점·역외조달", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("점포별 총조달 합 = 해외 총조달", L, "1000", tuple(b_tot), t),
        _sum_check("점포별 현지조달 합 = 현지조달", L, "1010", tuple(b_loc), t),
        _ratio_check("현지조달비율 = 현지조달 ÷ 총조달", L, "1030", "1010", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF703

def _bf703(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """현지자금운용비율 — 총운용은 여신잔액 실측, 현지운용 구분은 파생이다."""
    ub = usage_book(ctx)
    total = float(ub["usage_total"].sum())
    local = float(ub["usage_local"].sum())
    L = [
        FormLine("1000", "해외점포 총운용", 0, "KRW", total,
                 formula=f"점포별 여신잔액 합 · {_MEASURED} — 합계는 점포 귀속과 무관하다",
                 citation=_C63, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "현지자금운용", 1, "KRW", local,
                 formula=f"총운용 × 점포형태별 현지운용비중 · {_DERIVED}",
                 citation=_C63, source_module=_M_DER),
        FormLine("1020", "역외·본지점 운용", 1, "KRW",
                 float(ub["usage_offshore"].sum()),
                 formula=f"총운용 − 현지운용 · {_DERIVED}", citation=_C63,
                 source_module=_M_DER),
        FormLine("1030", "현지자금운용비율", 0, "ratio", _r(local, total),
                 formula="현지운용 ÷ 총운용", citation=_C63, source_module=_M_DER),
    ]
    b_tot, b_loc, checks = [], [], []
    for i, (_, b) in enumerate(ub.iterrows(), start=1):
        base = 2000 + i * 100
        b_tot.append(str(base))
        b_loc.append(str(base + 10))
        L += [
            FormLine(str(base), f"{b['branch_code']} {b['branch_name']}", 1,
                     "KRW", float(b["usage_total"]),
                     formula=f"{b['country']} · {b['kind']} · 여신잔액은 실측이고 점포 "
                             f"귀속은 해외점포 원장 부재로 뽑은 파생값", citation=_C63,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "현지자금운용", 2, "KRW",
                     float(b["usage_local"]), formula=_DERIVED, citation=_C63,
                     source_module=_M_DER),
            FormLine(str(base + 20), "역외·본지점 운용", 2, "KRW",
                     float(b["usage_offshore"]), formula=_DERIVED, citation=_C63,
                     source_module=_M_DER),
            FormLine(str(base + 30), "현지자금운용비율", 2, "ratio",
                     _r(float(b["usage_local"]), float(b["usage_total"])),
                     formula="현지운용 ÷ 총운용", citation=_C63,
                     source_module=_M_DER),
        ]
        checks += [
            _sum_check(f"{b['branch_code']} 총운용 = 현지 + 역외", L, str(base),
                       (str(base + 10), str(base + 20)), _tol(total)),
            _ratio_check(f"{b['branch_code']} 현지자금운용비율", L, str(base + 30),
                         str(base + 10), str(base)),
        ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("자금 원장에 운용처 구분이 없다. 총운용은 점포별 "
                                  "여신잔액 실측이고 현지운용 비중만 점포형태별 "
                                  "밴드에서 뽑은 파생값이다."),
                      citation=_C63, source_module=_M_DER))
    t = _tol(total)
    checks += [
        _sum_check("총운용 = 현지운용 + 역외운용", L, "1000", ("1010", "1020"), t),
        _sum_check("점포별 총운용 합 = 해외 총운용", L, "1000", tuple(b_tot), t),
        _sum_check("점포별 현지운용 합 = 현지운용", L, "1010", tuple(b_loc), t),
        _ratio_check("현지자금운용비율 = 현지운용 ÷ 총운용", L, "1030",
                     "1010", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF704

def _bf704(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """현지고객비율 — 금액은 실측, 현지고객 여부만 차주 단위 파생이다."""
    df = pnl_book(ctx)
    total = float(df["balance"].sum())
    loc = df[df["local_customer"]]
    local = float(loc["balance"].sum())
    obligors = df["obligor_id"].nunique()
    loc_ob = loc["obligor_id"].nunique()
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(df):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "현지고객 여신", 1, "KRW", local,
                 formula=f"금액은 실측 · 현지고객 판정은 차주 단위 {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "한국계 기업·교민 여신", 1, "KRW", total - local,
                 formula=f"총여신 − 현지고객 여신 · 판정은 {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("1030", "현지고객비율 (여신 기준)", 0, "ratio", _r(local, total),
                 formula="현지고객 여신 ÷ 해외 총여신", citation=_C99,
                 source_module=_M_DER),
        FormLine("1100", "총 차주수", 0, "count", float(obligors),
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1110", "현지고객 차주수", 1, "count", float(loc_ob),
                 formula=f"현지고객 판정은 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1120", "현지고객비율 (차주 기준)", 0, "ratio",
                 _r(float(loc_ob), float(obligors)),
                 formula="현지고객 차주수 ÷ 총 차주수", citation=_C99,
                 source_module=_M_DER),
    ]
    c_tot, c_loc, checks = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 2000 + i * 100
        s = df[df["country"] == country]
        b = float(s["balance"].sum())
        lb = float(s[s["local_customer"]]["balance"].sum())
        c_tot.append(str(base))
        c_loc.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 총여신", 1, "KRW", b,
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "현지고객 여신", 2, "KRW", lb,
                     formula=f"판정은 {_DERIVED}", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 20), "현지고객비율", 2, "ratio", _r(lb, b),
                     formula="현지고객 여신 ÷ 총여신", citation=_C99,
                     source_module=_M_DER),
        ]
        checks.append(_ratio_check(f"{country} 현지고객비율", L, str(base + 20),
                                   str(base + 10), str(base)))
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("차주 국적·진출기업 구분 원장이 없다. 현지고객 "
                                  "여부는 차주 단위로 기준일 고정 시드에서 판정하며 "
                                  "익스포저 단위가 아니다 — 같은 차주의 여신이 "
                                  "현지·한국계로 갈라지면 차주 기준 비율이 성립하지 "
                                  "않는다. 여신금액은 전부 실측이다."),
                      citation=_C99, source_module=_M_DER))
    t = _tol(total)
    checks += [
        _sum_check("총여신 = 현지고객 + 한국계", L, "1000", ("1010", "1020"), t),
        _sum_check("소재국별 총여신 합 = 해외 총여신", L, "1000", tuple(c_tot), t),
        _sum_check("소재국별 현지고객 여신 합 = 현지고객 여신", L, "1010",
                   tuple(c_loc), t),
        _ratio_check("현지고객비율 (여신 기준)", L, "1030", "1010", "1000"),
        _ratio_check("현지고객비율 (차주 기준)", L, "1120", "1110", "1100"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF705

def _tni(ctx) -> tuple[float, float, float, float]:
    """초국적화지수와 세 구성비중 — 정의는 자산·매출·인력 비중의 산술평균이다."""
    p = ctx.portfolio
    df = pnl_book(ctx)
    asset = _r(float(df["ead"].sum()), float(p["ead"].sum()))
    sales = _r(float(df["revenue"].sum()), float(p["revenue"].sum()))
    ov_staff = float(staff_book(ctx)["staff_total"].sum())
    staff = _r(ov_staff, ov_staff + hq_staff(ctx))
    return asset, sales, staff, (asset + sales + staff) / 3.0


def _bf705(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """초국적화지수 — 자산·매출 비중은 실측, 인력 비중만 파생이다."""
    p = ctx.portfolio
    df = pnl_book(ctx)
    sb = staff_book(ctx)
    asset, sales, staff, tni = _tni(ctx)
    ov_staff = float(sb["staff_total"].sum())
    hq = hq_staff(ctx)
    L = [
        FormLine("1000", "해외자산 (EAD)", 0, "KRW", float(df["ead"].sum()),
                 formula=f"익스포저 {len(df):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_PTF, is_subtotal=True),
        FormLine("1010", "총자산 (EAD)", 0, "KRW", float(p["ead"].sum()),
                 formula=f"익스포저 {len(p):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_PTF),
        FormLine("1020", "해외자산비중", 0, "ratio", asset,
                 formula="해외자산 ÷ 총자산 — 실측", citation=_C99,
                 source_module=_M_PTF),
        FormLine("2000", "해외매출 (영업수익)", 0, "KRW",
                 float(df["revenue"].sum()),
                 formula=f"revenue 해외분 실측 합 · {_MEASURED}", citation=_C99,
                 source_module=_M_PTF, is_subtotal=True),
        FormLine("2010", "총매출 (영업수익)", 0, "KRW", float(p["revenue"].sum()),
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_PTF),
        FormLine("2020", "해외매출비중", 0, "ratio", sales,
                 formula="해외매출 ÷ 총매출 — 실측", citation=_C99,
                 source_module=_M_PTF),
        FormLine("3000", "해외 직원수", 0, "count", ov_staff,
                 formula=f"점포별 직원수 합 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3010", "본점 직원수", 1, "count", hq,
                 formula=f"국내 여신잔액 ÷ 인당 관리자산 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("3020", "총 직원수", 0, "count", ov_staff + hq,
                 formula="해외 직원수 + 본점 직원수", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3030", "해외인력비중", 0, "ratio", staff,
                 formula=f"해외 직원수 ÷ 총 직원수 — 인사 원장이 없어 {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("4000", "세 비중 합계", 0, "ratio", asset + sales + staff,
                 formula="해외자산비중 + 해외매출비중 + 해외인력비중",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("4010", "구성비중 수", 0, "count", 3.0,
                 formula="초국적화지수 정의상 산술평균의 분모", citation=_C99,
                 source_module=_M_DER),
        FormLine("5000", "초국적화지수 (TNI)", 0, "ratio", tni,
                 formula="(해외자산비중 + 해외매출비중 + 해외인력비중) ÷ 3",
                 citation=_C99, source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value=("초국적화지수는 자산·매출·인력 비중의 산술평균이라는 "
                             "정의를 그대로 따른다. 세 축 중 자산·매출 비중은 실측 "
                             "집계이고 인력 비중만 파생이다 — 인사 원장이 없어 "
                             "해외·본점 직원수를 기준일 고정 시드로 만든다. "
                             "파생값이라도 정의상 관계(합 ÷ 3)는 대사한다."),
                 citation=_C99, source_module=_M_DER),
    ]
    return L, [
        _ratio_check("해외자산비중 = 해외자산 ÷ 총자산", L, "1020", "1000", "1010"),
        _ratio_check("해외매출비중 = 해외매출 ÷ 총매출", L, "2020", "2000", "2010"),
        _ratio_check("해외인력비중 = 해외 직원 ÷ 총 직원", L, "3030", "3000", "3020"),
        _sum_check("총 직원수 = 해외 + 본점", L, "3020", ("3000", "3010"), 1e-9),
        _sum_check("세 비중 합계 = 자산 + 매출 + 인력", L, "4000",
                   ("1020", "2020", "3030"), 1e-12),
        _ratio_check("TNI = 세 비중 합계 ÷ 3", L, "5000", "4000", "4010"),
    ]


# ---------------------------------------------------------------- BF706

def _bf706(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """글로벌업무역량 자체평가 — 정성평가라 점수 구간표와 환산근거를 남긴다.

    지표값은 전부 다른 서식의 산출값이다. 자체평가에서 임의성이 들어가는 곳은
    **구간표뿐**이므로 구간표를 데이터 모듈 상수로 두고 라인에 그대로 적는다.
    """
    bm = branch_master(ctx)
    ob = overseas_book(ctx)
    inc = overseas_income(ctx)
    ab = allocated_balance(ctx)
    cap = ctx.result.meta["capital"]
    w = overseas_share(ctx)
    ov = overseas_rwa(ctx)
    _, _, _, tni = _tni(ctx)
    bal = float(ob["balance"].sum())
    npl_ratio = _r(float(ob[ob["classification"].isin(NPL_CLASSES)]["balance"].sum()),
                   bal)
    values = {
        "해외 네트워크": float(len(bm)),
        "현지화 수준": tni,
        "자산건전성": npl_ratio,
        "자본적정성": _r(float(cap.total) * w, ov["total"]),
        "수익성": _r(inc["당기순이익"], ab["자산총계"]),
    }
    sources = {
        "해외 네트워크": ("BF101 점포 마스터", _M_DER_A),
        "현지화 수준": ("BF705 초국적화지수", _M_DER),
        "자산건전성": ("BF408 고정이하여신비율", _M_RDM),
        "자본적정성": ("BF602 해외영업점 총자본비율", _M_DER),
        "수익성": ("BF505 총자산순이익률", _M_PRU),
    }
    L, score_codes, checks = [], [], []
    total_score = 0.0
    for i, (name, label, unit, lower, cuts) in enumerate(SCORE_SECTIONS, start=1):
        base = 1000 + i * 100
        v = values[name]
        s = score_of(v, lower, cuts)
        total_score += s
        score_codes.append(str(base + 30))
        band = " · ".join(
            f"{'≤' if lower else '≥'}{b:,.3f} → {p:.0f}점" for b, p in cuts)
        ref, mod = sources[name]
        L += [
            FormLine(str(base), f"평가부문 · {name}", 0, "text", None,
                     text_value=f"평가지표 {label} · 근거 서식 {ref}",
                     citation=_C31, source_module=mod),
            FormLine(str(base + 10), f"{label} (지표값)", 1, unit, v,
                     formula=f"{ref}의 산출값을 그대로 쓴다", citation=_C31,
                     source_module=mod),
            FormLine(str(base + 20), "배점", 1, "count", SECTION_POINTS,
                     formula="부문별 배점 (5개 부문 × 20점 = 100점)",
                     citation=_C31, source_module=_M_DER),
            FormLine(str(base + 30), "획득점수", 1, "count", s,
                     formula=f"구간표 환산 — {band} · 그 외 4점",
                     citation=_C31, source_module=_M_DER),
        ]
        checks.append(FormCheck(f"{name} 획득점수 ≤ 배점", 0.0,
                                max(0.0, s - SECTION_POINTS), 1e-9))
    L += [
        FormLine("8000", "자체평가 총점", 0, "count", total_score,
                 formula="부문별 획득점수 합", citation=_C31, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("8010", "만점", 0, "count", TOTAL_POINTS,
                 formula=f"{len(SCORE_SECTIONS)}개 부문 × {SECTION_POINTS:.0f}점",
                 citation=_C31, source_module=_M_DER),
        FormLine("8020", "달성률", 0, "ratio", _r(total_score, TOTAL_POINTS),
                 formula="총점 ÷ 만점", citation=_C31, source_module=_M_DER),
        FormLine("8030", "자체평가 등급", 0, "text", None,
                 text_value=grade_of(total_score),
                 formula=" · ".join(f"{b:.0f}점 이상 {g}" for b, g in GRADE_CUTS)
                         + " · 그 외 5등급 (취약)",
                 citation=_C31, source_module=_M_DER),
        FormLine("9000", "평가기준 비고", 0, "text", None,
                 text_value=("글로벌업무역량은 정성평가이므로 평가위원 판단을 "
                             "지어내지 않는다. 본 서식은 5개 부문에 각 20점을 "
                             "배정하고 다른 서식의 산출 지표를 구간표로 환산해 "
                             "점수를 낸다. 구간 경계는 감독 최저기준(총자본비율 8%)과 "
                             "국내은행 해외점포 평균 수준을 기준으로 정했으며 "
                             "`forms_fss_overseas_b_data.SCORE_SECTIONS`에 한 곳으로 "
                             "모아 두었다. 최하 구간에도 4점을 주므로 총점 하한은 "
                             "20점이다. 지표값 자체가 파생에 걸리는 부문이 있다 — "
                             "현지화 수준(TNI)의 인력 축은 인사 원장이 없어 파생값이고, "
                             "자본적정성·수익성은 배분자본·배분 총자산을 쓴다. "
                             "자산건전성과 해외 네트워크만 실측 기반이다. "
                             "서술형 자체평가 의견은 별도 첨부로 제출한다."),
                 citation=_C31, source_module=_M_DER),
    ]
    checks += [
        _sum_check("부문별 획득점수 합 = 총점", L, "8000", tuple(score_codes), 1e-9),
        _ratio_check("달성률 = 총점 ÷ 만점", L, "8020", "8000", "8010"),
        FormCheck("총점 ≤ 만점", 0.0, max(0.0, total_score - TOTAL_POINTS), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "BF501": ("은행업감독규정 제99조 업무보고서 · 제31조 경영실태평가", "PRD-RDM",
              _bf501),
    "BF502": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _bf502),
    "BF503": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _bf503),
    "BF504": ("은행업감독규정 제63조 외화유동성 · 제99조 업무보고서", "PRD-RDM",
              _bf504),
    "BF505": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-RDM", _bf505),
    "BF506": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-RDM", _bf506),
    "BF507": ("은행업감독규정 제31조 · 제63조 외화유동성", "PRD-ALM", _bf507),
    "BF508": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-RDM", _bf508),
    "BF509": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-RDM", _bf509),
    "BF601": ("은행업감독규정 제26조 · Basel III CRE40 자본의 정의", "PRD-CAP",
              _bf601),
    "BF601-1": ("은행업감독규정 제26조 · Basel III CRE40 (바젤Ⅲ 편제)", "PRD-CAP",
                _bf601_1),
    "BF602": ("은행업감독규정 제26조 · Basel III CRE20·CRE52·MAR40·OPE25",
              "PRD-CAP", _bf602),
    "BF602-1": ("은행업감독규정 제26조·제26조의2~제26조의4 · Basel III CRE20",
                "PRD-CAP", _bf602_1),
    "BF603": ("Basel III CRE20 신용리스크 표준방법 · 은행업감독규정 제99조",
              "PRD-RWA", _bf603),
    "BF604": ("Basel III CRE20.94 신용환산율 · CRE52 SA-CCR · CRE22", "PRD-RWA",
              _bf604),
    "BF605": ("Basel III LEV20·LEV30 · 은행업감독규정 제26조 제1항 제4호",
              "PRD-CAP", _bf605),
    "BF606": ("은행업감독규정 제27조 자산건전성 분류 · 제31조 경영실태평가",
              "PRD-RDM", _bf606),
    "BF701": ("은행업감독규정 제99조 업무보고서 — 현지화평가", "PRD-RDM", _bf701),
    "BF702": ("은행업감독규정 제63조 외화유동성 — 현지화평가", "PRD-ALM", _bf702),
    "BF703": ("은행업감독규정 제63조 외화유동성 — 현지화평가", "PRD-ALM", _bf703),
    "BF704": ("은행업감독규정 제99조 업무보고서 — 현지화평가", "PRD-RDM", _bf704),
    "BF705": ("은행업감독규정 제99조 업무보고서 — 현지화평가", "PRD-RDM", _bf705),
    "BF706": ("은행업감독규정 제31조 경영실태평가 — 글로벌업무역량 자체평가",
              "PRD-VAL", _bf706),
}
