"""금감원 FINES 업무보고서 — 수익성 18건 (B25xx).

근거는 은행업감독규정 제99조(업무보고서)·제31조(경영실태평가)·제29조(대손충당금)와
은행법 제37조(자회사 출자)·제38조(유가증권 투자한도), 상법 제458조(이익준비금)다.

**손익계산서가 정본이다.** BR-16(B2110)이 `pru_income_statement`를 그대로 내므로
이 모듈의 모든 손익 라인은 같은 테이블에 앵커하고, 서식마다 "손익계산서 대사"
FormCheck를 건다. 같은 이익이 서식마다 다른 값을 가지면 어느 쪽이 맞는지 제출 뒤에는
가릴 수 없다. 마찬가지로 —

  충당금(B2506~B2508)  `rdm_asset_quality` · `ecl_provision_bridge` · `mkt_ipv`.
                       자산건전성 서식 B2402·B2403과 **같은 원천**이며 새로 계산하지
                       않는다. 대차대조표의 대손충당금(차감)과도 대사한다.
  금리(B2510~B2512-2)  `alm_repricing_gap`(= `alm.balance_sheet.REPRICING_BUCKETS`)과
                       `alm["irrbb"].base_rate`. BR-13(B2909 IRRBB)과 같은 사다리·같은
                       기준금리를 쓴다. 서식이 자기 사다리를 들면 두 화면이 갈라진다.
  여신종별             `forms_fss_asset_data.loan_book` 재사용 — B2403과 같은 구분이다.
  자회사(B2516)        `forms_fss_compliance_data.subsidiary_book`, 총액은
                       `pru_ownership_limit` 산출 사용액.
  이익잉여금(B2518)    `risk_lib.capital.bis`의 `PAID_IN_CAPITAL`·`RETAINED_YEARS`를
                       import해 "CET1 − 발행자본 = 연간이익 × 4년"을 대사한다.

**원장이 없어 파생한 것** (자세한 근거는 `forms_fss_profit_data` docstring)
  이자/비이자 구분     `revenue = ead × 스프레드`라 원천에 구분이 없다. 자산군별 비중
                       밴드는 BF503·BF507이 쓰는 `_NONINT_BAND`를 그대로 쓴다.
  이자수익·이자비용     순이자이익만 실측이다. 총액은 조달비용률로 열고 순액은 불변이다.
  기중평잔             일별 잔액 원장이 없다. 기중 성장률을 뽑아 (기초 + 기말) ÷ 2.
  대출금리·가산금리     금리 원장이 없다. `기준금리 + 실측 스프레드 + PD × LGD`로
                       재구성한다 — 난수는 없지만 원장도 아니다.
  월중 신규취급액       취급일자 원장이 없다. `잔액 ÷ (만기 × 12)`.
  기준금리 유형·구성    자산군별·계정별 고정 가중치. 잔액은 실측이다.
  유가증권 종류        HQLA 등급(2A·2B)까지 실측, 그 안의 종류 구성만 파생.
  수수료 항목 구성      총액은 비이자이익, 항목 구성비만 파생.
  월중 수수료 조정      **앵커할 산출값이 없는 완전 파생.**
  배당성향             배당 결의 원장이 없다. 미처분이익잉여금은 실측이다.

**미영위로 0을 적은 것** — B2517 신탁계정 수지. 원천 데이터에 신탁 계정과목이
없다. 0을 조용히 적으면 "없다"와 "안 봤다"가 구분되지 않으므로 라인마다 사유를 남긴다
(B2104·B2113과 같은 처리이며 문구를 맞췄다).

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

from risk_lib.capital.bis import PAID_IN_CAPITAL, RETAINED_YEARS
from risk_lib.prudential.financials import CORPORATE_TAX_RATE
from risk_lib.datamodel.materialize_detail import reserve_net_gap, reserve_requirement
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_asset_data import (
    AQ_ORDER, NPL_CLASSES, loan_book,
)
from risk_lib.regulatory.forms_fss_compliance_data import subsidiary_book
from risk_lib.regulatory.forms_fss_financial import _TRUST_REASON
from risk_lib.regulatory.forms_fss_profit_data import (
    EARNING_ASSET_ITEMS, FEE_ACTIONS, FEE_ITEMS, GRADE_ORDER,
    INTEREST_LIAB_ITEMS, LEGAL_RESERVE_RATE, NONINT_ITEMS, RATE_BAND_LABELS,
    SECURITY_ITEMS, SECURITY_KINDS_2A, TRUST_EXPENSE_ITEMS, TRUST_REVENUE_ITEMS,
    appropriation, avg_balance, balance, benchmark_mix, fee_changes, fee_mix,
    floating_share, guarantee_book, income, interest_flow, loan_rates,
    noninterest_mix, pnl_split, ratio, securities_book, tol,
    valuation_adjustment, weighted,
)

_M_PRU = "risk_lib.prudential.financials"
_M_DER = "risk_lib.regulatory.forms_fss_profit_data"
_M_DER_A = "risk_lib.regulatory.forms_fss_asset_data"
_M_DER_C = "risk_lib.regulatory.forms_fss_compliance_data"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_RDM = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_ALM = "risk_lib.alm.balance_sheet · risk_lib.alm.irrbb"
# mkt_ipv를 만드는 것은 risk_lib.ipv(run_ipv)이고 materialize가 실체화한다.
# market_data·frtb는 평가 입력이지 독립가격검증 산출 모듈이 아니다.
_M_IPV = "risk_lib.ipv · risk_lib.datamodel.materialize"
_M_BIS = "risk_lib.capital.bis"
_M_LIM = "risk_lib.prudential.limits"
# 미영위 계정에는 산출 모듈이 없다. 빈 문자열은 "못 채웠다"로 읽히므로 계정
# 부존재라는 사실을 그대로 적는다.
_M_NONE = "해당 계정 미영위 — 산출 모듈 없음"

_C99 = "은행업감독규정 제99조 업무보고서"
_C31 = "은행업감독규정 제31조 경영실태평가"
_C27 = "은행업감독규정 제27조 자산건전성 5단계 분류"
_C29 = "은행업감독규정 제29조 제1항 대손충당금 최저적립률"
_C_IFRS9 = "K-IFRS 제1109호 5.5 기대신용손실"
# 은행업감독규정 제30조는 **대손상각**이다(forms_fss_asset·forms_fss_retail이
# 그 뜻으로 쓴다). 금리리스크 근거는 제30조의2이며 BR-13(B2909 금리리스크지표)과
# 같은 조문을 쓴다 — 같은 사다리를 쓰면서 다른 조문을 달면 안 된다.
_C_SRP31 = ("Basel III SRP31.94 표준 재설정 구간 · "
            "은행업감독규정 제30조의2 금리리스크")
_C_B37 = "은행법 제37조 제2항 — 자회사 출자 자기자본 20% 이내"
_C_B38 = "은행법 제38조 제1호 — 유가증권 투자 자기자본 100% 이내"
_C_B458 = "상법 제458조 이익준비금"
_C_TRUST = "은행법 제28조 겸영업무 · 자본시장과 금융투자업에 관한 법률 제103조"
# 독립가격검증은 바젤 통합편제에서 **CAP50 신중한 평가**에 있다. MAR30은
# 내부모형 일반규정이라 IPV 근거가 아니다.
_C_MAR = "Basel III CAP50 신중한 평가(Prudent valuation) — 독립가격검증(IPV)"

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
# 빈 구간의 가중평균은 0이 된다. 0%를 그대로 두면 "금리 0%로 취급했다"로 읽힌다.
_RATE_NA = "해당 등급 여신을 취급하지 않아 0 — 금리 0%가 아니라 해당사항 없음"
# 이자제한법·대부업법 최고이자율(연 20%). 재구성 금리를 여기서 자르지는 않는다 —
# 자르면 재구성이 결정론적 함수가 아니게 된다. 대신 초과분을 서식에 드러낸다.
_USURY_CAP = 0.20
_RECON = "원장 부재 — 산출값의 결정론적 재구성 (난수 없음)"
# provenance._NEGATIONS에 등록된 표현은 "파생이 아님"이다. "파생 아님"으로 적으면
# 분류는 실측으로 떨어지지만 provenance.unclassified()에 오탐으로 쌓여 "파생이
# 감춰진 라인" 리포트를 못 쓰게 만든다.
_MEASURED = "산출값 실측 — 파생이 아님"


def _remark(text: str, citation: str = _C99) -> FormLine:
    return FormLine("9900", "비고", 0, "text", None, text_value=text,
                    citation=citation)


def _income_recon(ctx, codes: dict[str, str]) -> list[FormCheck]:
    """손익계산서 대사 — 서식 라인이 BR-16(B2110)과 같은 값인지 본다.

    수익성 서식은 전부 손익계산서의 변형이다. 어느 한 장이라도 총계가 어긋나면
    같은 이익이 두 값을 갖는데, 제출 뒤에는 어느 쪽이 맞는지 가릴 수 없다.
    """
    inc = income(ctx)
    return [FormCheck(f"손익계산서 대사 · {item}", inc[item], _val(codes["L"], code),
                      tol(inc[item]))
            for item, code in codes.items() if item != "L"]


# ---------------------------------------------------------------- B2501

def _b2501(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """손익현황 — 손익계산서를 이자·비이자로 편 장이다. 총계는 B2110과 같다."""
    inc = income(ctx)
    fl = interest_flow(ctx)
    mix = noninterest_mix(ctx)
    ps = pnl_split(ctx)
    L = [
        FormLine("1000", "영업수익", 0, "KRW", inc["영업수익"],
                 formula=f"portfolio.revenue 실측 합 · {_MEASURED}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1100", "이자이익 (순)", 1, "KRW", fl["net_interest"],
                 formula=f"영업수익 − 비이자이익 · 이자/비이자 구분은 {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1110", "이자수익", 2, "KRW", fl["interest_income"],
                 formula=f"이자이익 − 이자비용 · 총액 분해는 {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("1120", "이자비용", 2, "KRW", fl["interest_expense"],
                 formula=f"이자부부채 {fl['interest_liability']:,.0f}원 × "
                         f"조달비용률 {fl['funding_rate']:.4%} — {_DERIVED} (음수)",
                 citation=_C99, source_module=_M_DER),
        FormLine("1200", "비이자이익", 1, "KRW", fl["noninterest"],
                 formula=f"자산군별 비이자 비중 밴드(BF503과 동일) 적용 — {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
    ]
    for i, item in enumerate(NONINT_ITEMS, start=1):
        L.append(FormLine(f"{1200 + i * 10}", item, 2, "KRW", mix[item],
                          formula=f"비이자이익 항목 구성비는 {_DERIVED}",
                          citation=_C99, source_module=_M_DER))
    L += [
        FormLine("2000", "판매관리비", 0, "KRW", inc["영업비용"],
                 formula=f"portfolio.operating_cost 실측 합 (음수) · {_MEASURED}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("3000", "충당금 전입액", 0, "KRW", inc["충당금 전입액"],
                 formula="IFRS 9 ECL 기말 − 기초 (음수) — B2506과 같은 값",
                 citation=_C_IFRS9, source_module=_M_ECL, is_subtotal=True),
        FormLine("4000", "운영손실", 0, "KRW", inc["운영손실"],
                 formula="운영손실 사건 순손실 연간 합계 (음수)",
                 citation="Basel III OPE25", source_module=_M_PRU,
                 is_subtotal=True),
        FormLine("5000", "법인세차감전순이익", 0, "KRW", inc["법인세차감전순이익"],
                 formula="영업수익 + 판매관리비 + 충당금 전입액 + 운영손실",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("6000", "법인세비용", 0, "KRW", inc["법인세비용"],
                 formula=f"max(0, 세전이익) × {CORPORATE_TAX_RATE:.1%} (음수)",
                 citation=_C99, source_module=_M_PRU),
        FormLine("7000", "당기순이익", 0, "KRW", inc["당기순이익"],
                 formula="법인세차감전순이익 + 법인세비용", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
    ]
    ac_codes = []
    for i, (ac, sub) in enumerate(ps.groupby("asset_class"), start=1):
        code = f"{8000 + i * 10}"
        ac_codes.append(code)
        L.append(FormLine(code, f"자산군별 영업수익 · {ac}", 1, "KRW",
                          float(sub["revenue"].sum()),
                          formula=f"{len(sub):,}건 실측 합 · {_MEASURED}",
                          citation=_C99, source_module=_M_PTF))
    L.append(FormLine("8000", "자산군별 영업수익 합계", 0, "KRW",
                      float(ps["revenue"].sum()),
                      formula="영업수익과 같아야 한다 — 분해 누락 검출용",
                      citation=_C99, source_module=_M_PTF, is_subtotal=True))
    L.append(_remark(
        "이자·비이자 구분과 이자수익·이자비용 총액은 파생값이다. 원천의 revenue는 "
        "`ead × 자산군별 스프레드`라 구분이 존재하지 않는다. 순이자이익 + 비이자이익 = "
        "영업수익(실측)은 항상 성립하며, 이 서식이 손익계산서(B2110)와 어긋나지 않도록 "
        "7개 항목 전부에 대사를 걸었다."))
    t = tol(inc["영업수익"])
    checks = [
        _sum_check("영업수익 = 이자이익 + 비이자이익", L, "1000", ("1100", "1200"), t),
        _sum_check("이자이익 = 이자수익 + 이자비용", L, "1100", ("1110", "1120"), t),
        _sum_check("비이자이익 = 항목별 합", L, "1200",
                   tuple(f"{1200 + i * 10}" for i in range(1, len(NONINT_ITEMS) + 1)),
                   t),
        _sum_check("세전이익 = 영업수익 + 판관비 + 충당금 + 운영손실", L, "5000",
                   ("1000", "2000", "3000", "4000"), t),
        _sum_check("당기순이익 = 세전이익 + 법인세비용", L, "7000",
                   ("5000", "6000"), t),
        _sum_check("자산군별 영업수익 합 = 합계", L, "8000", tuple(ac_codes), t),
        FormCheck("자산군별 합계 = 영업수익", _val(L, "1000"), _val(L, "8000"), t),
    ]
    checks += _income_recon(ctx, {
        "L": L, "영업수익": "1000", "영업비용": "2000", "충당금 전입액": "3000",
        "운영손실": "4000", "법인세차감전순이익": "5000", "법인세비용": "6000",
        "당기순이익": "7000"})
    return L, checks


# ---------------------------------------------------------------- B2505

def _b2505(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """충당금적립전이익 — 충당금 전입 전 이익체력. 세전이익까지 손익계산서와 잇는다."""
    inc = income(ctx)
    pre = inc["영업수익"] + inc["영업비용"] + inc["운영손실"]
    ab = avg_balance(ctx, ("자산총계",))
    assets = float(ab["average"].iloc[0])
    L = [
        FormLine("1000", "영업수익", 0, "KRW", inc["영업수익"],
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_PRU),
        FormLine("2000", "판매관리비", 0, "KRW", inc["영업비용"],
                 formula=f"{_MEASURED} (음수)", citation=_C99,
                 source_module=_M_PRU),
        FormLine("3000", "운영손실", 0, "KRW", inc["운영손실"],
                 formula="운영손실 사건 순손실 연간 합계 (음수)",
                 citation="Basel III OPE25", source_module=_M_PRU),
        FormLine("4000", "충당금적립전이익", 0, "KRW", pre,
                 formula="영업수익 + 판매관리비 + 운영손실", citation=_C31,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("5000", "충당금 전입액", 0, "KRW", inc["충당금 전입액"],
                 formula="IFRS 9 ECL 기말 − 기초 (음수) — B2506과 같은 값",
                 citation=_C_IFRS9, source_module=_M_ECL),
        FormLine("6000", "법인세차감전순이익", 0, "KRW", inc["법인세차감전순이익"],
                 formula="충당금적립전이익 + 충당금 전입액", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("7000", "법인세비용", 0, "KRW", inc["법인세비용"],
                 formula=f"max(0, 세전이익) × {CORPORATE_TAX_RATE:.1%} (음수)",
                 citation=_C99, source_module=_M_PRU),
        FormLine("8000", "당기순이익", 0, "KRW", inc["당기순이익"],
                 formula="법인세차감전순이익 + 법인세비용", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("4100", "총자산 기중평잔", 1, "KRW", assets,
                 formula=f"(기초 + 기말) ÷ 2 — 일별 잔액 원장 없음 · {_DERIVED}",
                 citation=_C31, source_module=_M_DER),
        FormLine("4110", "충당금적립전이익률", 1, "ratio", ratio(pre, assets),
                 formula="충당금적립전이익 ÷ 총자산 기중평잔", citation=_C31,
                 source_module=_M_DER),
        # 배수는 비율이 아니다. unit="ratio"로 담으면 엑셀이 934%로 표시하고
        # 감독당국은 이를 백분율로 읽는다 — 단위를 배수로 둔다.
        FormLine("4120", "충당금 전입 흡수배수 (배)", 1, "count",
                 ratio(pre, -inc["충당금 전입액"]),
                 formula="충당금적립전이익 ÷ 충당금 전입액 (절대값) — 비율이 아니라 배수",
                 citation=_C31, source_module=_M_ECL),
    ]
    L.append(_remark(
        "충당금적립전이익은 손익계산서(B2110)에 없는 소계다. 새로 계산하지 않고 "
        "손익계산서 항목의 합으로만 만들어 세전이익과의 항등식을 FormCheck로 닫았다. "
        "총자산 기중평잔은 일별 잔액 원장이 없어 파생값이다."))
    t = tol(inc["영업수익"])
    checks = [
        _sum_check("충당금적립전이익 = 영업수익 + 판관비 + 운영손실", L, "4000",
                   ("1000", "2000", "3000"), t),
        _sum_check("세전이익 = 충당금적립전이익 + 충당금 전입액", L, "6000",
                   ("4000", "5000"), t),
        _sum_check("당기순이익 = 세전이익 + 법인세비용", L, "8000",
                   ("6000", "7000"), t),
        _ratio_check("충당금적립전이익률 = 이익 ÷ 총자산 평잔", L, "4110",
                     "4000", "4100"),
        # 흡수배수는 대사가 없으면 틀려도 드러나지 않는다.
        FormCheck("흡수배수 × 충당금 전입액 = 충당금적립전이익",
                  _val(L, "4120") * -_val(L, "5000"), _val(L, "4000"),
                  tol(pre)),
        FormCheck("총자산 평잔 = (기초 + 기말) ÷ 2",
                  (float(ab["opening"].iloc[0]) + float(ab["closing"].iloc[0])) / 2.0,
                  assets, tol(assets)),
    ]
    checks += _income_recon(ctx, {
        "L": L, "영업수익": "1000", "영업비용": "2000", "운영손실": "3000",
        "충당금 전입액": "5000", "법인세차감전순이익": "6000",
        "법인세비용": "7000", "당기순이익": "8000"})
    return L, checks


# ---------------------------------------------------------------- B2506

def _b2506(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대손충당금 적립현황 — B2402와 **같은 원천**이다. 새로 계산하지 않는다."""
    aq = ctx.tables["rdm_asset_quality"]
    br = ctx.tables["ecl_provision_bridge"].sort_values("seq")
    inc = income(ctx)
    bal = balance(ctx)
    total = float(aq["balance"].sum())
    ifrs = float(aq["ifrs9_provision"].sum())
    minp = float(aq["min_provision"].sum())
    npl = float(aq[aq["classification"].isin(NPL_CLASSES)]["balance"].sum())
    opening = float(br[br["step"] == "opening"]["amount"].iloc[0])
    closing = float(br[br["step"] == "closing"]["cumulative"].iloc[0])
    L = [
        FormLine("1000", "총 여신 잔액", 0, "KRW", total,
                 formula=f"rdm_asset_quality 실측 합 · {_MEASURED}",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("2000", "대손충당금 (IFRS 9 ECL)", 0, "KRW", ifrs,
                 formula="익스포저별 ECL 실측 합 — B2402와 같은 값",
                 citation=_C_IFRS9, source_module=_M_ECL, is_subtotal=True),
        FormLine("3000", "감독규정 최저적립액", 0, "KRW", minp,
                 formula="Σ 잔액 × 분류별 최저적립률", citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
    ]
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = aq[aq["classification"] == cls]
        L += [
            FormLine(f"{1000 + j * 10}", f"{cls} — 잔액", 1, "KRW",
                     float(s["balance"].sum()), formula=f"{len(s):,}건",
                     citation=_C27, source_module=_M_RDM),
            FormLine(f"{2000 + j * 10}", f"{cls} — 대손충당금", 1, "KRW",
                     float(s["ifrs9_provision"].sum()), citation=_C_IFRS9,
                     source_module=_M_ECL),
            FormLine(f"{3000 + j * 10}", f"{cls} — 최저적립액", 1, "KRW",
                     float(s["min_provision"].sum()), citation=_C29,
                     source_module=_M_RDM),
        ]
    L += [
        FormLine("4000", "대손준비금 소요액", 0, "KRW",
                 reserve_requirement(aq)["required"],
                 formula="max(0, 최저적립액 합계 − 충당금 합계) — 합계 기준 (은행업감독규정 제29조 제2항)",
                 citation="은행업감독규정 제29조 제2항", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("5000", "기초 대손충당금", 0, "KRW", opening,
                 citation=_C_IFRS9, source_module=_M_ECL, is_subtotal=True),
    ]
    steps = ("pd_effect", "lgd_effect", "ead_effect", "migration_effect")
    for i, st in enumerate(steps, start=1):
        L.append(FormLine(f"{5000 + i * 10}", f"당기 변동 · {st}", 1, "KRW",
                          float(br[br["step"] == st]["amount"].iloc[0]),
                          formula="요인별 분해 (경로 의존 — 순서 고정)",
                          citation=_C_IFRS9, source_module=_M_ECL))
    L += [
        FormLine("5900", "기말 대손충당금", 0, "KRW", closing,
                 formula="기초 + 당기 변동 합", citation=_C_IFRS9,
                 source_module=_M_ECL, is_subtotal=True),
        FormLine("6000", "고정이하여신", 0, "KRW", npl, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("6100", "충당금 적립률", 0, "ratio", ratio(ifrs, total),
                 formula="대손충당금 ÷ 총 여신", citation=_C31,
                 source_module=_M_ECL),
        FormLine("6200", "고정이하여신 대비 커버리지", 0, "ratio", ratio(ifrs, npl),
                 formula="대손충당금 ÷ 고정이하여신", citation=_C31,
                 source_module=_M_ECL),
        FormLine("7000", "대차대조표 대손충당금(차감) 절대값", 0, "KRW",
                 -bal["대손충당금 (차감)"],
                 formula="B2101 대차대조표 차감계정 — 대사용",
                 citation=_C99, source_module=_M_PRU),
        FormLine("7010", "손익계산서 충당금 전입액", 0, "KRW", inc["충당금 전입액"],
                 formula="B2110 손익계산서 (음수) — 대사용", citation=_C99,
                 source_module=_M_PRU),
    ]
    L.append(_remark(
        "이 서식은 새 충당금을 계산하지 않는다. 자산건전성 서식(B2402·B2403)과 같은 "
        "rdm_asset_quality·ecl_provision_bridge에서 가져오고, 대차대조표의 "
        "대손충당금(차감)·손익계산서의 충당금 전입액과 3중으로 대사한다. 감독 최저적립액"
        "(제29조)과 회계 충당금(IFRS 9)은 별개 체계라 나란히 싣는다.", _C29))
    t = tol(total)
    checks = [
        _sum_check("총 여신 = 분류별 합", L, "1000",
                   tuple(f"{1000 + j * 10}" for j in range(1, 6)), t),
        _sum_check("대손충당금 = 분류별 합", L, "2000",
                   tuple(f"{2000 + j * 10}" for j in range(1, 6)), tol(ifrs)),
        _sum_check("최저적립액 = 분류별 합", L, "3000",
                   tuple(f"{3000 + j * 10}" for j in range(1, 6)), tol(minp)),
        _sum_check("기말 충당금 = 기초 + 당기 변동", L, "5900",
                   ("5000",) + tuple(f"{5000 + i * 10}" for i in range(1, 5)),
                   tol(ifrs)),
        FormCheck("기말 충당금(브리지) = 대손충당금 합계(원장)", ifrs, closing,
                  tol(ifrs)),
        FormCheck("대손충당금 = 대차대조표 차감계정", _val(L, "2000"),
                  _val(L, "7000"), tol(ifrs)),
        FormCheck("손익 충당금 전입액 = −(기말 − 기초)", -(closing - opening),
                  inc["충당금 전입액"], tol(ifrs)),
        _ratio_check("충당금 적립률 = 충당금 ÷ 총여신", L, "6100", "2000", "1000"),
        _ratio_check("커버리지 = 충당금 ÷ 고정이하", L, "6200", "2000", "6000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2507

def _b2507(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """지급보증충당금 적립현황 — 잔액은 실측, 충당금은 실측 커버리지 환산이다."""
    g = guarantee_book(ctx)
    book = loan_book(ctx)
    total = float(g["guarantee"].sum())
    prov = float(g["provision"].sum())
    all_undrawn = float(book["undrawn"].sum())
    L = [
        FormLine("1000", "지급보증 잔액", 0, "KRW", total,
                 formula=f"지급보증 성격 부외약정 미사용액 실측 합 · {len(g):,}건 · "
                         f"{_MEASURED}", citation=_C27, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("2000", "지급보증충당금", 0, "KRW", prov,
                 formula="Σ 미사용액 × 해당 익스포저 실측 커버리지율 — 부외약정에 "
                         "ECL이 산출되지 않아 환산한 값이다(원장 아님)",
                 citation=_C_IFRS9, source_module=_M_DER, is_subtotal=True),
    ]
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = g[g["classification"] == cls]
        L += [
            FormLine(f"{1000 + j * 10}", f"{cls} — 지급보증 잔액", 1, "KRW",
                     float(s["guarantee"].sum()), formula=f"{len(s):,}건",
                     citation=_C27, source_module=_M_RDM),
            FormLine(f"{2000 + j * 10}", f"{cls} — 지급보증충당금", 1, "KRW",
                     float(s["provision"].sum()),
                     formula="실측 커버리지율 환산", citation=_C_IFRS9,
                     source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "지급보증충당금 적립률", 0, "ratio", ratio(prov, total),
                 formula="지급보증충당금 ÷ 지급보증 잔액", citation=_C29,
                 source_module=_M_DER),
        FormLine("4000", "총 부외약정 미사용액 (참고)", 0, "KRW", all_undrawn,
                 formula=f"전체 미사용약정 실측 합 · {_MEASURED} — 지급보증은 "
                         f"이 중 direct_credit_substitute · transaction_related 뿐이다",
                 citation="Basel III CRE20.94 신용환산율", source_module=_M_RDM),
        FormLine("4010", "지급보증 비중", 0, "ratio", ratio(total, all_undrawn),
                 formula="지급보증 잔액 ÷ 총 부외약정 미사용액",
                 citation="Basel III CRE20.94 신용환산율", source_module=_M_RDM),
    ]
    L.append(_remark(
        "지급보증 잔액과 건전성분류는 실측이다. 충당금은 부외약정에 ECL이 산출되지 "
        "않아(EAD가 인출액 기준) 같은 익스포저의 실측 커버리지율을 미사용액에 곱한 "
        "환산값이며, 난수는 쓰지 않았다. 대지급금 발생 현황은 자산건전성 서식이 "
        "다루므로 여기서 다시 파생하지 않는다.", _C29))
    checks = [
        _sum_check("지급보증 잔액 = 분류별 합", L, "1000",
                   tuple(f"{1000 + j * 10}" for j in range(1, 6)), tol(total)),
        _sum_check("지급보증충당금 = 분류별 합", L, "2000",
                   tuple(f"{2000 + j * 10}" for j in range(1, 6)), tol(prov)),
        _ratio_check("적립률 = 충당금 ÷ 지급보증 잔액", L, "3000", "2000", "1000"),
        _ratio_check("지급보증 비중 = 지급보증 ÷ 총 미사용액", L, "4010",
                     "1000", "4000"),
        FormCheck("지급보증 잔액 ≤ 총 부외약정 미사용액", 0.0,
                  max(0.0, total - all_undrawn), tol(all_undrawn)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2508

def _b2508(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """채권평가충당금 및 특별유보금 — 평가조정은 IPV 실측, 특별유보금은 계정 부존재."""
    va = valuation_adjustment(ctx)
    ipv = ctx.tables["mkt_ipv"]
    bal = balance(ctx)
    sec = sum(bal[i] for i in SECURITY_ITEMS)
    L = [
        FormLine("1000", "채권평가충당금", 0, "KRW", va["down"],
                 formula="독립가격검증 하향조정 필요액 합계 (mkt_ipv.diff < 0) · "
                         f"{_MEASURED}", citation=_C_MAR, source_module=_M_IPV,
                 is_subtotal=True),
    ]
    src_codes = []
    for i, (src, sub) in enumerate(ipv.groupby("source"), start=1):
        d = sub["diff"].astype(float)
        code = f"{1000 + i * 10}"
        src_codes.append(code)
        L.append(FormLine(code, f"검증원천 · {src}", 1, "KRW",
                          float(-d[d < 0].sum()),
                          formula=f"{len(sub):,}건 중 하향 {int((d < 0).sum()):,}건",
                          citation=_C_MAR, source_module=_M_IPV))
    L += [
        FormLine("2000", "평가이익 (상향조정분·참고)", 0, "KRW", va["up"],
                 formula="mkt_ipv.diff > 0 합계 — 보수적 평가에서 충당금 상계 불가",
                 citation=_C_MAR, source_module=_M_IPV),
        FormLine("3000", "순 평가손익", 0, "KRW", va["net"],
                 formula="평가이익 − 채권평가충당금", citation=_C_MAR,
                 source_module=_M_IPV, is_subtotal=True),
        FormLine("4000", "검증대상 포지션 건수", 0, "count", va["n"],
                 citation=_C_MAR, source_module=_M_IPV, is_subtotal=True),
        FormLine("4010", "하향조정 건수", 1, "count", va["n_down"],
                 citation=_C_MAR, source_module=_M_IPV),
        FormLine("4020", "검증한도 초과 건수", 1, "count", va["n_break"],
                 formula="|차이| > 한도 — IPV break", citation=_C_MAR,
                 source_module=_M_IPV),
        FormLine("5000", "특별유보금", 0, "KRW", 0.0,
                 formula="자본 원장(risk_lib.capital.bis.synthesise_capital)에 "
                         "특별유보금 계정이 없다 — 적립액을 산출할 원천이 없어 0이며, "
                         "미적립 확인이 아니라 미보유 사실이다",
                 citation="은행업감독규정 제99조 업무보고서", source_module=_M_NONE,
                 is_subtotal=True),
        FormLine("6000", "유가증권 잔액 (분모)", 0, "KRW", sec,
                 formula="대차대조표 Level 2A + 2B 실측", citation=_C99,
                 source_module=_M_PRU),
        FormLine("6100", "채권평가충당금 적립률", 0, "ratio", ratio(va["down"], sec),
                 formula="채권평가충당금 ÷ 유가증권 잔액", citation=_C31,
                 source_module=_M_IPV),
    ]
    L.append(_remark(
        "채권평가충당금은 독립가격검증(IPV) 결과 프런트오피스 평가액이 벤치마크보다 "
        "높은 포지션의 차이 합계다 — 실측이며 파생이 아니다. 상향조정분을 상계하면 "
        "충당금이 아니라 순평가손익이 되어 성격이 달라지므로 따로 싣는다. 특별유보금은 "
        "자본 원장에 계정 자체가 없어 0이다.", _C_MAR))
    checks = [
        _sum_check("채권평가충당금 = 검증원천별 합", L, "1000", tuple(src_codes),
                   tol(va["down"])),
        FormCheck("순 평가손익 = 평가이익 − 평가충당금", va["up"] - va["down"],
                  _val(L, "3000"), tol(max(abs(va["net"]), 1.0))),
        FormCheck("하향조정 건수 ≤ 검증대상 건수", 0.0,
                  max(0.0, va["n_down"] - va["n"]), 1e-9),
        _ratio_check("적립률 = 평가충당금 ÷ 유가증권 잔액", L, "6100",
                     "1000", "6000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2510

def _b2510(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """순이자마진(기중평잔기준) — 분자·분모를 함께 싣고 평잔 산식까지 대사한다."""
    fl = interest_flow(ctx)
    inc = income(ctx)
    ab = avg_balance(ctx, EARNING_ASSET_ITEMS)
    lb = avg_balance(ctx, INTEREST_LIAB_ITEMS)
    earning = float(ab["average"].sum())
    funding = float(lb["average"].sum())
    lr = loan_rates(ctx)
    loan_rate = weighted(lr, "rate", "balance")
    L = [
        FormLine("1000", "순이자이익 (분자)", 0, "KRW", fl["net_interest"],
                 formula=f"영업수익 − 비이자이익 · 구분은 {_DERIVED} (순액은 실측)",
                 citation=_C31, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "이자수익", 1, "KRW", fl["interest_income"],
                 formula=f"총액 분해는 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1020", "이자비용", 1, "KRW", fl["interest_expense"],
                 formula=f"이자부부채 × 조달비용률 {fl['funding_rate']:.4%} — "
                         f"{_DERIVED} (음수)", citation=_C99, source_module=_M_DER),
        FormLine("1030", "비이자이익 (참고)", 1, "KRW", fl["noninterest"],
                 formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1040", "영업수익 (실측·대사용)", 1, "KRW", inc["영업수익"],
                 formula=f"{_MEASURED} — 순이자이익 + 비이자이익과 같아야 한다",
                 citation=_C99, source_module=_M_PRU),
        FormLine("2000", "이자수익자산 기중평잔 (분모)", 0, "KRW", earning,
                 formula="현금·예치금 + 유가증권 + 대출채권(총액) 평잔 — 기타자산 제외",
                 citation=_C31, source_module=_M_DER, is_subtotal=True),
    ]
    a_codes = []
    for i, (_, r) in enumerate(ab.iterrows(), start=1):
        code = f"{2000 + i * 10}"
        a_codes.append(code)
        L.append(FormLine(code, f"{r['item']} — 기중평잔", 1, "KRW",
                          float(r["average"]),
                          formula=f"(기초 {float(r['opening']):,.0f} + 기말 "
                                  f"{float(r['closing']):,.0f}) ÷ 2 — 일별 잔액 "
                                  f"원장 없음 · {_DERIVED}",
                          citation=_C31, source_module=_M_DER))
    L += [
        FormLine("2100", "이자수익자산 기말잔액 (참고)", 1, "KRW",
                 float(ab["closing"].sum()),
                 formula=f"대차대조표 실측 · {_MEASURED}", citation=_C99,
                 source_module=_M_PRU),
        FormLine("3000", "이자부부채 기중평잔", 0, "KRW", funding,
                 formula=f"예수금 + 차입금 + 사채 평잔 — 일별 잔액 원장 없음 · {_DERIVED}",
                 citation=_C31, source_module=_M_DER, is_subtotal=True),
        FormLine("4000", "순이자마진 (NIM)", 0, "ratio",
                 ratio(fl["net_interest"], earning),
                 formula="순이자이익 ÷ 이자수익자산 기중평잔", citation=_C31,
                 source_module=_M_DER),
        FormLine("4010", "자산운용수익률", 0, "ratio",
                 ratio(fl["interest_income"], earning),
                 formula="이자수익 ÷ 이자수익자산 기중평잔", citation=_C31,
                 source_module=_M_DER),
        FormLine("4020", "조달비용률 (운용자산 대비)", 0, "ratio",
                 ratio(fl["interest_expense"], earning),
                 formula="이자비용 ÷ 이자수익자산 기중평잔 (음수)", citation=_C31,
                 source_module=_M_DER),
        FormLine("5000", "대출 가중평균금리", 0, "ratio", loan_rate,
                 formula=f"잔액 가중 — 금리는 {_RECON}", citation=_C31,
                 source_module=_M_DER),
        FormLine("5010", "조달 평균금리", 0, "ratio", fl["funding_rate"],
                 formula=f"|이자비용| ÷ 이자부부채 **기말**잔액 — 이 서식의 다른 "
                         f"분모(기중평잔)와 기준이 다르다 · {_DERIVED}",
                 citation=_C31, source_module=_M_DER),
        FormLine("5020", "예대금리차", 0, "ratio", loan_rate - fl["funding_rate"],
                 formula="대출 가중평균금리 − 조달 평균금리", citation=_C31,
                 source_module=_M_DER),
    ]
    L.append(_remark(
        "기중평잔은 일별·월별 잔액 원장이 없어 파생값이다 — 계정별 기중 성장률을 "
        "기준일 고정 시드로 뽑아 기초를 역산하고 (기초 + 기말) ÷ 2로 본다. 분자인 "
        "순이자이익은 실측 영업수익에서 갈라낸 값이라 비이자이익과의 합이 항상 "
        "영업수익(B2110)과 같다. 이자수익자산 정의는 BF507(해외 NIM)과 같은 계정 "
        "묶음을 쓴다.", _C31))
    checks = [
        _sum_check("순이자이익 = 이자수익 + 이자비용", L, "1000",
                   ("1010", "1020"), tol(fl["interest_income"])),
        _sum_check("영업수익 = 순이자이익 + 비이자이익", L, "1040",
                   ("1000", "1030"), tol(inc["영업수익"])),
        _sum_check("이자수익자산 평잔 = 계정별 평잔 합", L, "2000", tuple(a_codes),
                   tol(earning)),
        _ratio_check("NIM = 순이자이익 ÷ 이자수익자산 평잔", L, "4000",
                     "1000", "2000"),
        _ratio_check("자산운용수익률 = 이자수익 ÷ 평잔", L, "4010", "1010", "2000"),
        _ratio_check("조달비용률 = 이자비용 ÷ 평잔", L, "4020", "1020", "2000"),
        _sum_check("NIM = 자산운용수익률 + 조달비용률", L, "4000",
                   ("4010", "4020"), 1e-12),
        FormCheck("예대금리차 = 대출금리 − 조달금리",
                  _val(L, "5000") - _val(L, "5010"), _val(L, "5020"), 1e-12),
        FormCheck("이자수익자산 평잔 = (기초 + 기말) ÷ 2",
                  float((ab["opening"].sum() + ab["closing"].sum()) / 2.0),
                  earning, tol(earning)),
        FormCheck("이자부부채 평잔 = (기초 + 기말) ÷ 2",
                  float((lb["opening"].sum() + lb["closing"].sum()) / 2.0),
                  funding, tol(funding)),
        FormCheck("손익계산서 대사 · 영업수익", inc["영업수익"], _val(L, "1040"),
                  tol(inc["영업수익"])),
    ]
    return L, checks


# ---------------------------------------------------------------- B2511

def _b2511(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """금리감응 자산·부채현황 — 사다리는 alm_repricing_gap 그대로다."""
    t = ctx.tables["alm_repricing_gap"].sort_values("seq")
    bal = balance(ctx)
    asset = float(t["asset"].sum())
    liab = float(t["liability"].sum())
    L = [
        FormLine("100", "금리감응자산 합계", 0, "KRW", asset,
                 formula=f"재설정 사다리 실측 합 · {_MEASURED}",
                 citation=_C_SRP31, source_module=_M_ALM, is_subtotal=True),
        FormLine("110", "금리감응부채 합계", 0, "KRW", liab,
                 citation=_C_SRP31, source_module=_M_ALM, is_subtotal=True),
        FormLine("120", "금리감응갭 합계", 0, "KRW", asset - liab,
                 formula="금리감응자산 − 금리감응부채", citation=_C_SRP31,
                 source_module=_M_ALM, is_subtotal=True),
        FormLine("130", "갭 비율 (총자산 대비)", 0, "ratio",
                 ratio(asset - liab, bal["자산총계"]),
                 formula="금리감응갭 ÷ 자산총계", citation=_C31,
                 source_module=_M_ALM),
        FormLine("140", "자산총계 (대차대조표)", 0, "KRW", bal["자산총계"],
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_PRU),
        FormLine("150", "만기구간 미배분 자산", 0, "KRW",
                 bal["자산총계"] - asset,
                 formula="자산총계 − 금리감응자산 — 사다리는 금리민감 자산만 담는다",
                 citation=_C_SRP31, source_module=_M_ALM),
        FormLine("160", "부채총계 (대차대조표)", 0, "KRW", bal["부채총계"],
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_PRU),
        FormLine("170", "만기구간 미배분 부채", 0, "KRW", bal["부채총계"] - liab,
                 formula="부채총계 − 금리감응부채 (비금리민감 조달)",
                 citation=_C_SRP31, source_module=_M_ALM),
    ]
    a_codes, l_codes, checks = [], [], []
    cum = 0.0
    for i, (_, r) in enumerate(t.iterrows(), start=1):
        base = i * 1000
        a_codes.append(str(base + 10))
        l_codes.append(str(base + 20))
        cum += float(r["gap"])
        L += [
            FormLine(str(base), f"재설정 구간 · {r['bucket']}", 1, "KRW",
                     float(r["gap"]), formula="자산 − 부채", citation=_C_SRP31,
                     source_module=_M_ALM, is_subtotal=True),
            FormLine(str(base + 10), "금리감응자산", 2, "KRW", float(r["asset"]),
                     citation=_C_SRP31, source_module=_M_ALM),
            FormLine(str(base + 20), "금리감응부채", 2, "KRW",
                     float(r["liability"]), citation=_C_SRP31,
                     source_module=_M_ALM),
            FormLine(str(base + 30), "누적갭", 2, "KRW",
                     float(r["cumulative_gap"]),
                     formula="당해 구간까지의 갭 누적", citation=_C_SRP31,
                     source_module=_M_ALM),
        ]
        checks += [
            FormCheck(f"{r['bucket']} 갭 = 자산 − 부채",
                      float(r["asset"] - r["liability"]), float(r["gap"]),
                      tol(asset)),
            FormCheck(f"{r['bucket']} 누적갭 = 갭 누적합", cum,
                      float(r["cumulative_gap"]), tol(asset)),
        ]
    L.append(_remark(
        "만기 구간은 alm.balance_sheet.REPRICING_BUCKETS(SRP31.94)를 그대로 쓴다 — "
        "BR-13(B2909 IRRBB)과 같은 사다리여야 두 화면이 같은 만기 분포를 보고한다. "
        "사다리는 금리민감 자산·부채만 담으므로 대차대조표 총액과 차이가 나며, 그 차를 "
        "'만기구간 미배분' 라인으로 드러낸다. 비만기성 예금은 행태만기로 슬로팅되어 "
        "있어 계약상 만기와 완전히 같지 않다.", _C_SRP31))
    checks += [
        _sum_check("금리감응자산 = 구간별 합", L, "100", tuple(a_codes), tol(asset)),
        _sum_check("금리감응부채 = 구간별 합", L, "110", tuple(l_codes), tol(liab)),
        FormCheck("금리감응갭 = 자산 − 부채", asset - liab, _val(L, "120"),
                  tol(asset)),
        FormCheck("최종 누적갭 = 갭 합계", _val(L, "120"),
                  float(t["cumulative_gap"].iloc[-1]), tol(asset)),
        _sum_check("자산총계 = 금리감응자산 + 미배분", L, "140", ("100", "150"),
                   tol(bal["자산총계"])),
        _sum_check("부채총계 = 금리감응부채 + 미배분", L, "160", ("110", "170"),
                   tol(bal["부채총계"])),
        _ratio_check("갭 비율 = 갭 ÷ 자산총계", L, "130", "120", "140"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2511-1

def _b2511_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """기준금리 유형별 여수신 잔액현황 — 잔액은 실측, 유형 구성비는 고정 가중치다."""
    m = benchmark_mix(ctx)
    book = loan_book(ctx)
    bal = balance(ctx)
    loan_total = float(book["balance"].sum())
    dep_total = sum(bal[i] for i in INTEREST_LIAB_ITEMS)
    f_loan, f_dep = floating_share(ctx)
    L = [
        FormLine("1000", "여신 잔액 합계", 0, "KRW", loan_total,
                 formula=f"rdm_asset_quality 실측 합 · {_MEASURED}",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("2000", "수신·조달 잔액 합계", 0, "KRW", dep_total,
                 formula=f"예수금 + 차입금 + 사채 실측 합 · {_MEASURED}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
    ]
    l_codes, d_codes = [], []
    for i, (_, r) in enumerate(m.iterrows(), start=1):
        lc, dc = f"{1000 + i * 10}", f"{2000 + i * 10}"
        l_codes.append(lc)
        d_codes.append(dc)
        L += [
            FormLine(lc, f"여신 · {r['type']}", 1, "KRW", float(r["loan"]),
                     formula="자산군별 고정 가중치 배분 — 잔액은 실측, 유형 구성은 "
                             "원장 부재로 가정",
                     citation=_C99, source_module=_M_DER),
            FormLine(dc, f"수신·조달 · {r['type']}", 1, "KRW", float(r["deposit"]),
                     formula="계정별 고정 가중치 배분 — 잔액은 실측, 유형 구성은 "
                             "원장 부재로 가정",
                     citation=_C99, source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "여신 변동금리 비중", 0, "ratio", f_loan,
                 formula="1 − 고정금리 여신 ÷ 여신 합계", citation=_C31,
                 source_module=_M_DER),
        FormLine("3010", "수신·조달 변동금리 비중", 0, "ratio", f_dep,
                 formula="1 − 고정금리 수신 ÷ 수신 합계", citation=_C31,
                 source_module=_M_DER),
        FormLine("3020", "변동금리 비중 갭", 0, "ratio", f_loan - f_dep,
                 formula="여신 변동비중 − 수신 변동비중 — B2512 금리구조갭의 방향",
                 citation=_C31, source_module=_M_DER),
    ]
    L.append(_remark(
        "기준금리 유형 원장이 없다. 유형 구성비는 난수가 아니라 자산군별·계정별 고정 "
        "가중치이고 잔액은 실측이므로, 유형별 합계는 여신원장·대차대조표와 정확히 "
        "일치한다. 여기서 나온 고정·변동 구분을 B2512(금리구조갭)가 그대로 쓴다 — "
        "두 서식이 다른 구분을 쓰면 갈라진다."))
    checks = [
        _sum_check("여신 합계 = 유형별 합", L, "1000", tuple(l_codes),
                   tol(loan_total)),
        _sum_check("수신·조달 합계 = 유형별 합", L, "2000", tuple(d_codes),
                   tol(dep_total)),
        FormCheck("여신 변동비중 = 1 − 고정 ÷ 합계",
                  1.0 - ratio(_val(L, "1010"), _val(L, "1000")), f_loan, 1e-12),
        FormCheck("수신 변동비중 = 1 − 고정 ÷ 합계",
                  1.0 - ratio(_val(L, "2010"), _val(L, "2000")), f_dep, 1e-12),
        FormCheck("비중 갭 = 여신 − 수신", f_loan - f_dep, _val(L, "3020"), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2512

def _b2512(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자금조달·운용의 금리구조갭현황 — 고정·변동 구분은 B2511-1과 같은 것을 쓴다."""
    t = ctx.tables["alm_repricing_gap"].sort_values("seq")
    bal = balance(ctx)
    asset = float(t["asset"].sum())
    liab = float(t["liability"].sum())
    f_loan, f_dep = floating_share(ctx)
    fa, fl_ = asset * f_loan, liab * f_dep
    L = [
        FormLine("1000", "자금운용 (금리감응자산)", 0, "KRW", asset,
                 formula=f"재설정 사다리 실측 합 · {_MEASURED}",
                 citation=_C_SRP31, source_module=_M_ALM, is_subtotal=True),
        FormLine("1010", "변동금리부", 1, "KRW", fa,
                 formula=f"운용 합계 × 여신 변동비중 {f_loan:.6f} — 비중은 B2511-1과 "
                         f"같은 고정 가중치이고 배분 결과는 파생값이다",
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "고정금리부", 1, "KRW", asset - fa,
                 formula="운용 합계 − 변동금리부", citation=_C99,
                 source_module=_M_DER),
        FormLine("2000", "자금조달 (금리감응부채)", 0, "KRW", liab,
                 citation=_C_SRP31, source_module=_M_ALM, is_subtotal=True),
        FormLine("2010", "변동금리부", 1, "KRW", fl_,
                 formula=f"조달 합계 × 수신 변동비중 {f_dep:.6f} — 배분 결과는 파생값",
                 citation=_C99, source_module=_M_DER),
        FormLine("2020", "고정금리부", 1, "KRW", liab - fl_,
                 formula="조달 합계 − 변동금리부", citation=_C99,
                 source_module=_M_DER),
        FormLine("3000", "변동금리 구조갭", 0, "KRW", fa - fl_,
                 formula="변동금리 운용 − 변동금리 조달", citation=_C31,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3010", "고정금리 구조갭", 0, "KRW", (asset - fa) - (liab - fl_),
                 formula="고정금리 운용 − 고정금리 조달", citation=_C31,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3020", "총 금리구조갭", 0, "KRW", asset - liab,
                 formula="운용 − 조달 — B2511 금리감응갭과 같은 값", citation=_C31,
                 source_module=_M_ALM, is_subtotal=True),
        FormLine("3030", "변동금리 구조갭 ÷ 자산총계", 0, "ratio",
                 ratio(fa - fl_, bal["자산총계"]),
                 formula="변동금리 구조갭 ÷ 자산총계", citation=_C31,
                 source_module=_M_DER),
        FormLine("3040", "자산총계 (대차대조표)", 1, "KRW", bal["자산총계"],
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_PRU),
    ]
    a_codes, l_codes = [], []
    for i, (_, r) in enumerate(t.iterrows(), start=1):
        base = 4000 + i * 100
        a_codes.append(str(base + 10))
        l_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"재설정 구간 · {r['bucket']} 갭", 1, "KRW",
                     float(r["gap"]), citation=_C_SRP31, source_module=_M_ALM,
                     is_subtotal=True),
            FormLine(str(base + 10), "운용", 2, "KRW", float(r["asset"]),
                     citation=_C_SRP31, source_module=_M_ALM),
            FormLine(str(base + 20), "조달", 2, "KRW", float(r["liability"]),
                     citation=_C_SRP31, source_module=_M_ALM),
        ]
    L.append(_remark(
        "금리구조갭의 만기 축은 B2511과 같은 재설정 사다리이고, 고정·변동 축은 "
        "B2511-1과 같은 기준금리 유형 구성비다. 두 축 모두 이 서식이 자기 사본을 "
        "만들지 않는다. 고정·변동 배분 결과는 파생값이며 총액은 실측이다.", _C_SRP31))
    checks = [
        _sum_check("운용 = 변동 + 고정", L, "1000", ("1010", "1020"), tol(asset)),
        _sum_check("조달 = 변동 + 고정", L, "2000", ("2010", "2020"), tol(liab)),
        FormCheck("변동 구조갭 = 변동운용 − 변동조달", fa - fl_, _val(L, "3000"),
                  tol(asset)),
        _sum_check("총 구조갭 = 변동갭 + 고정갭", L, "3020", ("3000", "3010"),
                   tol(asset)),
        FormCheck("총 구조갭 = 운용 − 조달", asset - liab, _val(L, "3020"),
                  tol(asset)),
        _sum_check("운용 = 구간별 합", L, "1000", tuple(a_codes), tol(asset)),
        _sum_check("조달 = 구간별 합", L, "2000", tuple(l_codes), tol(liab)),
        _ratio_check("변동갭 비율 = 변동갭 ÷ 자산총계", L, "3030", "3000", "3040"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2512-1

def _b2512_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """여신종별 금리구간별 대출잔액 현황 — 금리는 재구성값이지 원장이 아니다."""
    df = loan_rates(ctx)
    total = float(df["balance"].sum())
    base_rate = float(df["base_rate"].iloc[0])
    products = tuple(sorted(df["product"].unique()))
    L = [
        FormLine("100", "대출잔액 합계", 0, "KRW", total,
                 formula=f"rdm_asset_quality 실측 합 · {len(df):,}건 · {_MEASURED}",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
    ]
    band_codes = []
    for j, lab in enumerate(RATE_BAND_LABELS, start=1):
        code = f"{100 + j * 10}"
        band_codes.append(code)
        L.append(FormLine(code, f"금리구간 · {lab}", 1, "KRW",
                          float(df[df["rate_band"] == lab]["balance"].sum()),
                          formula=f"대출금리는 {_RECON}", citation=_C31,
                          source_module=_M_DER))
    L += [
        FormLine("180", "가중평균 대출금리", 0, "ratio",
                 weighted(df, "rate", "balance"),
                 formula=f"Σ(잔액 × 금리) ÷ Σ잔액 — 금리는 {_RECON}",
                 citation=_C31, source_module=_M_DER),
        FormLine("190", "기준금리", 0, "ratio", base_rate,
                 formula="alm['irrbb'].base_rate 산출값 — 재구성의 출발점",
                 citation=_C_SRP31, source_module=_M_ALM),
        # 재구성 금리에는 법정 최고금리 상한이 없다. 얼마가 그 위로 튀는지
        # 서식이 스스로 드러내지 않으면 감독당국이 잔액표만 보고는 알 수 없다.
        FormLine("195", f"참고 · 재구성 금리 연 {_USURY_CAP:.0%} 초과 대출잔액",
                 0, "KRW",
                 float(df[df["rate"] > _USURY_CAP]["balance"].sum()),
                 formula=f"재구성 금리에 이자제한법 최고금리 상한을 두지 않았다 — "
                         f"신용원가(PD × LGD)가 큰 차주에서 계약 불가능한 금리가 "
                         f"나온다 · {_RECON}",
                 citation="이자제한법 제2조 · 대부업법 제8조 최고이자율",
                 source_module=_M_DER),
    ]
    p_codes, checks = [], []
    for i, prod in enumerate(products, start=1):
        base = (i + 1) * 1000
        s = df[df["product"] == prod]
        bal_p = float(s["balance"].sum())
        p_codes.append(str(base))
        cell_codes = []
        L.append(FormLine(str(base), f"여신종별 · {prod}", 1, "KRW", bal_p,
                          formula=f"{len(s):,}건 · 여신종별 구분은 {_DERIVED} (B2403과 같은 배분)",
                          citation=_C27, source_module=_M_DER_A, is_subtotal=True))
        for j, lab in enumerate(RATE_BAND_LABELS, start=1):
            code = str(base + j * 10)
            cell_codes.append(code)
            L.append(FormLine(code, f"{lab}", 2, "KRW",
                              float(s[s["rate_band"] == lab]["balance"].sum()),
                              citation=_C31, source_module=_M_DER))
        L.append(FormLine(str(base + 90), "가중평균 대출금리", 2, "ratio",
                          weighted(s, "rate", "balance"),
                          formula="Σ(잔액 × 금리) ÷ Σ잔액", citation=_C31,
                          source_module=_M_DER))
        checks.append(_sum_check(f"{prod} 잔액 = 금리구간별 합", L, str(base),
                                 tuple(cell_codes), tol(bal_p)))
        checks.append(FormCheck(f"{prod} 가중평균금리 재계산",
                                weighted(s, "rate", "balance"),
                                _val(L, str(base + 90)), 1e-12))
    for j, lab in enumerate(RATE_BAND_LABELS, start=1):
        checks.append(_sum_check(f"금리구간 {lab} = 여신종별 합", L,
                                 f"{100 + j * 10}",
                                 tuple(str((i + 1) * 1000 + j * 10)
                                       for i in range(1, len(products) + 1)),
                                 tol(total)))
    L.append(_remark(
        "대출금리 원장이 없다. 계약금리를 `기준금리 + 실측 스프레드(revenue ÷ ead) + "
        "신용원가(PD × LGD)`로 재구성했다 — 세 항이 모두 산출값이라 난수는 없지만 "
        "원장도 아니다. 합성 포트폴리오의 revenue는 자산군별 단일 스프레드(기업 2.5% · "
        "가계일반 5.5% · 주택 1.8% · 기타 0.8%)라 그것만으로는 금리 분산이 생기지 않아 "
        "차주별 신용원가를 더했다. 국가·은행 익스포저는 표준방법 대상이라 PD·LGD가 "
        "없어 신용원가가 0이다. 금리구간 경계도 감독 실무 구간이 아니라 이 분포를 "
        "가르기 위한 가정이다. 잔액은 전부 실측이다. **재구성 금리에는 이자제한법 "
        "최고이자율(연 20%) 상한이 걸려 있지 않다** — 신용원가가 큰 차주에서 계약이 "
        "불가능한 금리가 나오고, 그 결과 고PD 여신종별(가계일반)의 가중평균 금리가 "
        "20%를 넘는다. 초과 잔액은 라인 195에 별도로 실었다. 실제 제출 시 금리 원장으로 "
        "대체되면 사라지는 현상이며, 상한으로 자르면 재구성이 결정론적 함수가 아니게 "
        "되므로 자르지 않고 드러낸다.", _C31))
    checks += [
        _sum_check("대출잔액 합계 = 여신종별 합", L, "100", tuple(p_codes),
                   tol(total)),
        _sum_check("대출잔액 합계 = 금리구간별 합", L, "100", tuple(band_codes),
                   tol(total)),
        FormCheck("가중평균 대출금리 재계산", weighted(df, "rate", "balance"),
                  _val(L, "180"), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2512-2

def _b2512_2(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """여신종별 신용등급별 월중 신규취급 대출금리·가산금리 — 신규취급액도 재구성이다."""
    df = loan_rates(ctx)
    base_rate = float(df["base_rate"].iloc[0])
    total = float(df["new_amount"].sum())
    products = tuple(sorted(df["product"].unique()))
    L = [
        FormLine("100", "월중 신규취급액 합계", 0, "KRW", total,
                 formula=f"Σ 잔액 ÷ (만기 × 12) — 취급일자 원장 없음 · {_RECON}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("110", "가중평균 대출금리", 0, "ratio",
                 weighted(df, "rate", "new_amount"),
                 formula="Σ(신규취급액 × 금리) ÷ Σ신규취급액", citation=_C31,
                 source_module=_M_DER),
        FormLine("120", "가중평균 가산금리", 0, "ratio",
                 weighted(df, "add_on", "new_amount"),
                 formula="대출금리 − 기준금리 = 실측 스프레드 + 신용원가",
                 citation=_C31, source_module=_M_DER),
        FormLine("130", "기준금리", 0, "ratio", base_rate,
                 formula="alm['irrbb'].base_rate 산출값", citation=_C_SRP31,
                 source_module=_M_ALM),
    ]
    p_codes, checks = [], []
    for i, prod in enumerate(products, start=1):
        base = (i + 1) * 1000
        s = df[df["product"] == prod]
        amt = float(s["new_amount"].sum())
        p_codes.append(str(base))
        L += [
            FormLine(str(base), f"여신종별 · {prod} 신규취급액", 1, "KRW", amt,
                     formula=f"{len(s):,}건 · 여신종별 구분은 {_DERIVED} (B2403과 같은 배분)",
                     citation=_C27, source_module=_M_DER_A, is_subtotal=True),
            FormLine(str(base + 10), "가중평균 대출금리", 2, "ratio",
                     weighted(s, "rate", "new_amount"), citation=_C31,
                     source_module=_M_DER),
            FormLine(str(base + 20), "가중평균 가산금리", 2, "ratio",
                     weighted(s, "add_on", "new_amount"), citation=_C31,
                     source_module=_M_DER),
        ]
        g_codes = []
        for j, grade in enumerate(GRADE_ORDER, start=1):
            gsub = s[s["grade"] == grade]
            gb = base + j * 100
            g_codes.append(str(gb))
            # 해당 등급 취급이 없으면 가중평균이 0이 된다. 0%는 "금리가 0"이 아니라
            # "해당 없음"이므로 라인에 그 사실을 적는다 — 적지 않으면 서식에서
            # 0% 대출금리를 보고한 것으로 읽힌다(B2517의 0 처리와 같은 원칙).
            empty = _RATE_NA if gsub.empty else None
            L += [
                # 취급액 0원은 "0건"이라는 실측이다. 해당사항 없음을 적어야 하는
                # 것은 분모가 없어 0이 되는 금리 라인 쪽이다.
                FormLine(str(gb), f"신용등급 · {grade} 신규취급액", 2, "KRW",
                         float(gsub["new_amount"].sum()),
                         formula=f"{len(gsub):,}건 · 등급은 crm_rating SA 버킷 실측",
                         citation="Basel III CRE20.4 ECRA", source_module=_M_RDM),
                FormLine(str(gb + 10), "가중평균 대출금리", 3, "ratio",
                         weighted(gsub, "rate", "new_amount"), formula=empty,
                         citation=_C31, source_module=_M_DER),
                FormLine(str(gb + 20), "가중평균 가산금리", 3, "ratio",
                         weighted(gsub, "add_on", "new_amount"), formula=empty,
                         citation=_C31, source_module=_M_DER),
            ]
        checks += [
            _sum_check(f"{prod} 신규취급액 = 등급별 합", L, str(base),
                       tuple(g_codes), tol(max(amt, 1.0))),
            FormCheck(f"{prod} 가산금리 = 대출금리 − 기준금리",
                      _val(L, str(base + 10)) - base_rate,
                      _val(L, str(base + 20)), 1e-12),
            # 등급별 금리를 신규취급액으로 다시 가중하면 상품 평균으로 돌아와야 한다.
            FormCheck(f"{prod} 등급별 금리 가중합 = 상품 평균금리",
                      _val(L, str(base + 10)) * amt,
                      sum(_val(L, str(base + j * 100))
                          * _val(L, str(base + j * 100 + 10))
                          for j in range(1, len(GRADE_ORDER) + 1)),
                      tol(max(amt, 1.0))),
        ]
    L.append(_remark(
        "월중 신규취급 원장이 없다. 만기까지 균등 재취급을 가정해 `잔액 ÷ (만기 × 12)`를 "
        "월 신규취급액으로 본다(0.5%~10% 구간으로 자름). 대출금리·가산금리는 B2512-1과 "
        "같은 재구성이며, 가산금리는 정의상 `대출금리 − 기준금리`이므로 상품별로 항등식을 "
        "걸었다. 신용등급은 crm_rating의 SA 버킷 실측이고 은행·국가는 원장 등급이다. "
        "해당 등급 취급이 없는 칸은 가중평균이 0으로 계산되므로 '금리 0%'가 아니라 "
        "'해당사항 없음'임을 라인마다 적었다. 재구성 금리에 이자제한법 최고이자율 "
        "(연 20%) 상한이 없다는 점은 B2512-1 비고와 같다.", _C31))
    checks += [
        _sum_check("신규취급액 합계 = 여신종별 합", L, "100", tuple(p_codes),
                   tol(total)),
        FormCheck("가중평균 가산금리 = 대출금리 − 기준금리",
                  _val(L, "110") - base_rate, _val(L, "120"), 1e-12),
        FormCheck("신규취급액 ≤ 대출잔액", 0.0,
                  max(0.0, total - float(df["balance"].sum())),
                  tol(float(df["balance"].sum()))),
    ]
    return L, checks


# ---------------------------------------------------------------- B2513

def _b2513(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """유가증권 운용현황 — 잔액·평가손익은 실측, 종류 구성만 파생이다."""
    sb = securities_book(ctx)
    va = valuation_adjustment(ctx)
    bal = balance(ctx)
    mix = noninterest_mix(ctx)
    own = ctx.tables["pru_ownership_limit"]
    row = own[own["item"] == "유가증권 투자"].iloc[0]
    total = sum(bal[i] for i in SECURITY_ITEMS)
    L = [
        FormLine("1000", "유가증권 잔액 합계", 0, "KRW", total,
                 formula=f"대차대조표 Level 2A + 2B 실측 · {_MEASURED}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "Level 2A (국공채성)", 1, "KRW",
                 bal["유가증권 (Level 2A)"],
                 formula=f"LCR 적격 HQLA 등급 실측 · {_MEASURED}",
                 citation="Basel III LCR30 HQLA", source_module=_M_PRU),
        FormLine("1020", "Level 2B (회사채·주식성)", 1, "KRW",
                 bal["유가증권 (Level 2B)"],
                 formula=f"LCR 적격 HQLA 등급 실측 · {_MEASURED}",
                 citation="Basel III LCR30 HQLA", source_module=_M_PRU),
    ]
    kind_codes, a_codes, b_codes = [], [], []
    for i, (_, r) in enumerate(sb.iterrows(), start=1):
        code = f"{2000 + i * 10}"
        kind_codes.append(code)
        (a_codes if r["kind"] in SECURITY_KINDS_2A else b_codes).append(code)
        L.append(FormLine(code, f"종류 · {r['kind']}", 1, "KRW",
                          float(r["balance"]),
                          formula=f"{r['level']} 잔액(실측) 안의 종류 구성은 {_DERIVED}",
                          citation=_C99, source_module=_M_DER))
    L += [
        FormLine("3000", "순 평가손익", 0, "KRW", va["net"],
                 formula=f"독립가격검증 차이 합계 · {_MEASURED}", citation=_C_MAR,
                 source_module=_M_IPV, is_subtotal=True),
        FormLine("3010", "평가이익", 1, "KRW", va["up"], citation=_C_MAR,
                 source_module=_M_IPV),
        FormLine("3020", "평가손실 (채권평가충당금 — B2508)", 1, "KRW", -va["down"],
                 formula="하향조정 필요액 (음수) — B2508 1000과 같은 값",
                 citation=_C_MAR, source_module=_M_IPV),
        FormLine("4000", "유가증권관련이익 (손익)", 0, "KRW",
                 mix["유가증권관련이익"],
                 formula=f"비이자이익 항목 — 구성비는 {_DERIVED}, 총액은 실측 "
                         f"영업수익에서 갈라낸 값이다",
                 citation=_C99, source_module=_M_DER),
        FormLine("4010", "유가증권 운용수익률", 0, "ratio",
                 ratio(mix["유가증권관련이익"], total),
                 formula="유가증권관련이익 ÷ 유가증권 잔액", citation=_C31,
                 source_module=_M_DER),
        FormLine("5000", "은행법 제38조 한도 (자기자본 100%)", 0, "KRW",
                 float(row["limit_amount"]), citation=_C_B38,
                 source_module=_M_LIM),
        FormLine("5010", "한도 사용액 (산출)", 0, "KRW", float(row["used"]),
                 formula=f"pru_ownership_limit 산출값 — 유가증권 잔액과 같아야 한다 · "
                         f"{_MEASURED}", citation=_C_B38, source_module=_M_LIM),
        FormLine("5020", "한도 소진율", 0, "ratio", float(row["utilisation"]),
                 formula="사용액 ÷ 한도금액", citation=_C_B38,
                 source_module=_M_LIM),
    ]
    L.append(_remark(
        "HQLA 등급(Level 2A·2B)까지는 실측 분류이고 그 안의 종류 구성만 파생이다 — "
        "종류별 원장이 없다. 평가손익은 독립가격검증(mkt_ipv) 실측이며 B2508의 "
        "채권평가충당금과 같은 값이다. 한도 사용액은 pru_ownership_limit 산출값이고 "
        "유가증권 잔액과 일치해야 한다. 다만 은행법 제38조 제1호의 투자한도는 국채·"
        "통화안정증권을 제외하고 산정하는데, 산출값(pru_ownership_limit)은 HQLA "
        "Level 2A·2B 합계를 그대로 사용액으로 잡는다 — 이 서식이 국채·통화안정증권을 "
        "종류로 분해해 보여주므로 그 금액이 한도 사용액에 포함돼 있다는 사실이 드러난다. "
        "한도 소진율은 그만큼 보수적(과다)이며, 제외 처리는 산출 모듈에서 바로잡을 "
        "사항이지 서식이 자기 사본으로 고칠 사항이 아니다.", _C_B38))
    checks = [
        _sum_check("유가증권 잔액 = 등급별 합", L, "1000", ("1010", "1020"),
                   tol(total)),
        _sum_check("유가증권 잔액 = 종류별 합", L, "1000", tuple(kind_codes),
                   tol(total)),
        _sum_check("Level 2A = 국공채성 종류 합", L, "1010", tuple(a_codes),
                   tol(total)),
        _sum_check("Level 2B = 회사채·주식성 종류 합", L, "1020", tuple(b_codes),
                   tol(total)),
        _sum_check("순 평가손익 = 평가이익 + 평가손실", L, "3000",
                   ("3010", "3020"), tol(max(abs(va["net"]), 1.0))),
        FormCheck("한도 사용액 = 유가증권 잔액", total, _val(L, "5010"),
                  tol(total)),
        _ratio_check("한도 소진율 = 사용액 ÷ 한도", L, "5020", "5010", "5000"),
        _ratio_check("운용수익률 = 관련이익 ÷ 잔액", L, "4010", "4000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2516

def _b2516(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자회사출자현황 — 출자 총액은 산출값이고 자회사별 배분·지분율이 파생이다."""
    own = ctx.tables["pru_ownership_limit"]
    row = own[own["item"] == "자회사 출자"].iloc[0]
    total = float(row["used"])
    equity = float(ctx.result.meta["capital"].total)
    sub = subsidiary_book(total)
    credit_total = float(sub["credit"].sum())
    L = [
        FormLine("1000", "자회사 출자총액", 0, "KRW", total,
                 formula=f"pru_ownership_limit 산출 사용액 · {_MEASURED}",
                 citation=_C_B37, source_module=_M_LIM, is_subtotal=True),
        FormLine("1010", "자기자본 (총자본)", 0, "KRW", equity,
                 citation="은행업감독규정 제26조 자기자본비율", source_module=_M_BIS),
        FormLine("1020", "출자한도 (자기자본 20%)", 0, "KRW",
                 float(row["limit_amount"]), citation=_C_B37,
                 source_module=_M_LIM),
        FormLine("1030", "한도 소진율", 0, "ratio", float(row["utilisation"]),
                 formula="출자총액 ÷ 출자한도", citation=_C_B37,
                 source_module=_M_LIM),
    ]
    inv_codes, cr_codes = [], []
    for i, (_, r) in enumerate(sub.iterrows(), start=1):
        base = 2000 + i * 100
        inv_codes.append(str(base))
        cr_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"자회사 · {r['name']} 출자금액", 1, "KRW",
                     float(r["investment"]),
                     formula=f"총액은 산출값, 자회사별 배분은 {_DERIVED}",
                     citation=_C_B37, source_module=_M_DER_C, is_subtotal=True),
            FormLine(str(base + 10), "지분율", 2, "ratio", float(r["stake"]),
                     formula=f"{_DERIVED} — 자회사 요건(의결권 15% 초과) 위",
                     citation=_C_B37, source_module=_M_DER_C),
            FormLine(str(base + 20), "신용공여액", 2, "KRW", float(r["credit"]),
                     formula=f"출자금액 비례 {_DERIVED}",
                     citation="은행법 제37조 제3항 자회사 신용공여 한도",
                     source_module=_M_DER_C),
        ]
    L += [
        FormLine("3000", "자회사 신용공여 합계", 0, "KRW", credit_total,
                 citation="은행법 제37조 제3항", source_module=_M_DER_C,
                 is_subtotal=True),
        FormLine("3010", "합계 한도 (자기자본 20%)", 0, "KRW", equity * 0.20,
                 citation="은행법 제37조 제3항", source_module=_M_BIS),
        FormLine("3020", "합계 한도 소진율", 0, "ratio",
                 ratio(credit_total, equity * 0.20),
                 formula="신용공여 합계 ÷ 합계 한도", citation="은행법 제37조 제3항",
                 source_module=_M_DER_C),
        FormLine("3030", "개별 한도 (자기자본 10%)", 0, "KRW", equity * 0.10,
                 citation="은행법 제37조 제3항", source_module=_M_BIS),
        FormLine("3040", "최대 개별 신용공여액", 0, "KRW",
                 float(sub["credit"].max()), citation="은행법 제37조 제3항",
                 source_module=_M_DER_C),
    ]
    L.append(_remark(
        "출자 총액은 pru_ownership_limit의 산출 사용액이고 자회사 명칭·업종·개별 "
        "출자금액·지분율·신용공여는 자회사 마스터가 없어 파생값이다 "
        "(forms_fss_compliance_data.subsidiary_book — 준수 서식과 같은 파생을 "
        "재사용한다). 명세 합계 = 산출 총액 대사는 파생 난수끼리의 자기충족이 아니라 "
        "산출값과의 대사다.", _C_B37))
    checks = [
        _sum_check("출자총액 = 자회사별 합", L, "1000", tuple(inv_codes),
                   tol(total)),
        _sum_check("신용공여 합계 = 자회사별 합", L, "3000", tuple(cr_codes),
                   tol(credit_total)),
        _ratio_check("한도 소진율 = 출자총액 ÷ 한도", L, "1030", "1000", "1020"),
        _ratio_check("신용공여 소진율 = 합계 ÷ 한도", L, "3020", "3000", "3010"),
        FormCheck("최대 개별 신용공여 ≤ 자기자본 10%", 0.0,
                  max(0.0, float(sub["credit"].max()) - equity * 0.10),
                  tol(equity)),
        FormCheck("자회사 신용공여 합계 ≤ 자기자본 20%", 0.0,
                  max(0.0, credit_total - equity * 0.20), tol(equity)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2517

def _b2517(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """신탁계정 수지상황 — 신탁업 미영위. 0과 사유를 라인마다 함께 남긴다."""
    L: list[FormLine] = []
    checks: list[FormCheck] = []
    for gi, (title, items) in enumerate(
            (("신탁계정 수입 합계", TRUST_REVENUE_ITEMS),
             ("신탁계정 지출 합계", TRUST_EXPENSE_ITEMS)), start=1):
        base = gi * 1000
        codes = []
        L.append(FormLine(str(base), title, 0, "KRW", 0.0, formula=_TRUST_REASON,
                          citation=_C_TRUST, source_module=_M_NONE,
                          is_subtotal=True))
        for i, item in enumerate(items, start=1):
            code = str(base + i * 10)
            codes.append(code)
            L.append(FormLine(code, item, 1, "KRW", 0.0, formula=_TRUST_REASON,
                              citation=_C_TRUST, source_module=_M_NONE))
        checks.append(_sum_check(f"{title} = 세부항목 합", L, str(base),
                                 tuple(codes), 1e-9))
    L += [
        FormLine("3000", "신탁계정 수지차 (당기순이익)", 0, "KRW", 0.0,
                 formula=f"수입 합계 − 지출 합계 · {_TRUST_REASON}",
                 citation=_C_TRUST, source_module=_M_NONE, is_subtotal=True),
        FormLine("4000", "수탁고 잔액", 0, "KRW", 0.0, formula=_TRUST_REASON,
                 citation=_C_TRUST, source_module=_M_NONE, is_subtotal=True),
    ]
    L.append(_remark(
        "신탁계정 미영위(B2104·B2113과 같은 사유)이므로 신탁보수·신탁관련비용이 모두 "
        "없다. 은행계정 손익계산서(B2110)에 신탁 관련 손익이 섞여 있지 않으며, 이 "
        "서식의 0은 '산출했더니 0'이 아니라 '계정 자체가 없다'는 뜻이다.", _C_TRUST))
    checks.append(FormCheck("수지차 = 수입 − 지출",
                            _val(L, "1000") - _val(L, "2000"), _val(L, "3000"),
                            1e-9))
    return L, checks


# ---------------------------------------------------------------- B2518

def _b2518(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """이익잉여금 처분안 — 합성 자본의 이익잉여금 가정(연간이익 × 4년)과 대사한다."""
    ap = appropriation(ctx)
    p = ctx.portfolio
    cap = ctx.result.meta["capital"]
    annual = float(p["revenue"].sum() - p["operating_cost"].sum())
    L = [
        FormLine("1000", "미처분이익잉여금", 0, "KRW", ap["unappropriated"],
                 formula=f"대차대조표 이익잉여금 실측 · {_MEASURED}",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "전기이월 미처분이익잉여금", 1, "KRW", ap["carried_in"],
                 formula="미처분이익잉여금 − 당기순이익으로 역산 — 전기 원장 없음",
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "당기순이익", 1, "KRW", ap["net_income"],
                 formula=f"손익계산서(B2110) 당기순이익 · {_MEASURED}",
                 citation=_C99, source_module=_M_PRU),
        FormLine("2000", "이익잉여금 처분액", 0, "KRW",
                 ap["dividend"] + ap["legal_reserve"],
                 formula="이익준비금 적립액 + 배당금", citation=_C_B458,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "이익준비금 적립액", 1, "KRW", ap["legal_reserve"],
                 formula=f"현금배당액 × {LEGAL_RESERVE_RATE:.0%} (상법 최저기준)",
                 citation=_C_B458, source_module=_M_DER),
        FormLine("2020", "배당금", 1, "KRW", ap["dividend"],
                 formula=f"당기순이익 × 배당성향 {ap['payout']:.4%} — 배당 결의 "
                         f"원장 없음 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER),
        FormLine("3000", "차기이월 미처분이익잉여금", 0, "KRW", ap["carried_out"],
                 formula="미처분이익잉여금 − 처분액", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("4000", "배당성향", 0, "ratio", ap["payout"],
                 formula="배당금 ÷ 당기순이익", citation=_C31,
                 source_module=_M_DER),
        FormLine("5000", "보통주자본 (CET1)", 0, "KRW", float(cap.cet1),
                 formula="자본 원장 — 규제자본 기준", citation="Basel III CRE40",
                 source_module=_M_BIS, is_subtotal=True),
        FormLine("5010", "고정 발행자본 (자본금 + 자본잉여금)", 1, "KRW",
                 PAID_IN_CAPITAL,
                 formula="risk_lib.capital.bis.PAID_IN_CAPITAL — 증자는 이산 사건이라 "
                         "자산 규모에 비례시키지 않는다",
                 citation="Basel III CRE40", source_module=_M_BIS),
        FormLine("5020", "규제자본 이익잉여금", 1, "KRW",
                 float(cap.cet1) - PAID_IN_CAPITAL,
                 formula=f"연간 영업이익 × 누적 유보 연수 {RETAINED_YEARS:g}년",
                 citation="Basel III CRE40", source_module=_M_BIS),
        FormLine("5030", "연간 영업이익 (수익 − 비용)", 1, "KRW", annual,
                 formula=f"portfolio.revenue − operating_cost 실측 합 · {_MEASURED}",
                 citation=_C99, source_module=_M_PTF),
        FormLine("5040", "누적 유보 연수", 1, "count", RETAINED_YEARS,
                 formula="risk_lib.capital.bis.RETAINED_YEARS 가정",
                 citation="Basel III CRE40", source_module=_M_BIS),
    ]
    L.append(_remark(
        "미처분이익잉여금은 대차대조표 이익잉여금(회계) 실측이고, 전기이월액은 그것에서 "
        "당기순이익을 뺀 역산이라 처분안 합계가 대차대조표와 어긋날 수 없다. 배당성향만 "
        "파생이다(배당 결의 원장 없음). 회계 이익잉여금과 별개로 규제자본의 이익잉여금은 "
        "합성 자본 원장의 가정 '연간 영업이익 × 4년'을 따르므로, 그 항등식을 이 서식에서 "
        "직접 대사한다 — 두 이익잉여금이 다른 개념임을 서식이 스스로 드러내야 한다.",
        _C_B458))
    t = tol(ap["unappropriated"])
    checks = [
        _sum_check("미처분이익잉여금 = 전기이월 + 당기순이익", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("처분액 = 이익준비금 + 배당금", L, "2000", ("2010", "2020"), t),
        _sum_check("미처분이익잉여금 = 처분액 + 차기이월", L, "1000",
                   ("2000", "3000"), t),
        FormCheck("이익준비금 = 배당금 × 10%",
                  _val(L, "2020") * LEGAL_RESERVE_RATE, _val(L, "2010"),
                  tol(ap["dividend"])),
        _ratio_check("배당성향 = 배당금 ÷ 당기순이익", L, "4000", "2020", "1020"),
        FormCheck("규제자본 이익잉여금 = 연간 영업이익 × 유보 연수",
                  annual * RETAINED_YEARS, _val(L, "5020"), tol(float(cap.cet1))),
        _sum_check("CET1 = 발행자본 + 규제자본 이익잉여금", L, "5000",
                   ("5010", "5020"), tol(float(cap.cet1))),
        FormCheck("손익계산서 대사 · 당기순이익", income(ctx)["당기순이익"],
                  _val(L, "1020"), tol(ap["net_income"])),
    ]
    return L, checks


# ---------------------------------------------------------------- B2520

def _b2520(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """주요 손익비율 — 비율마다 분자·분모 라인을 함께 싣고 전부 대사한다."""
    inc = income(ctx)
    fl = interest_flow(ctx)
    ab = avg_balance(ctx, ("자산총계", "자본총계 (회계)"))
    ea = avg_balance(ctx, EARNING_ASSET_ITEMS)
    assets = float(ab.loc[ab["item"] == "자산총계", "average"].iloc[0])
    equity = float(ab.loc[ab["item"] == "자본총계 (회계)", "average"].iloc[0])
    earning = float(ea["average"].sum())
    loans = float(ctx.tables["rdm_asset_quality"]["balance"].sum())
    pre_prov = inc["영업수익"] + inc["영업비용"] + inc["운영손실"]
    opex = -inc["영업비용"]
    prov = -inc["충당금 전입액"]
    tax = -inc["법인세비용"]
    gross = fl["net_interest"] + fl["noninterest"]
    L = [
        FormLine("1000", "당기순이익", 0, "KRW", inc["당기순이익"],
                 formula=f"손익계산서(B2110) · {_MEASURED}", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "법인세차감전순이익", 0, "KRW", inc["법인세차감전순이익"],
                 citation=_C99, source_module=_M_PRU),
        FormLine("1020", "충당금적립전이익", 0, "KRW", pre_prov,
                 formula="영업수익 + 판관비 + 운영손실 — B2505 4000과 같은 값",
                 citation=_C31, source_module=_M_PRU),
        FormLine("1030", "순이자이익", 0, "KRW", fl["net_interest"],
                 formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1040", "비이자이익", 0, "KRW", fl["noninterest"],
                 formula=f"이자/비이자 구분은 {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1050", "판매관리비 (절대값)", 0, "KRW", opex,
                 formula=f"{_MEASURED}", citation=_C99, source_module=_M_PRU),
        FormLine("1060", "충당금 전입액 (절대값)", 0, "KRW", prov,
                 citation=_C_IFRS9, source_module=_M_ECL),
        FormLine("1070", "법인세비용 (절대값)", 0, "KRW", tax, citation=_C99,
                 source_module=_M_PRU),
        FormLine("1080", "총이익 (순이자 + 비이자)", 0, "KRW", gross,
                 formula="영업수익(실측)과 같아야 한다 — 합계는 파생이 아님, "
                         "이자/비이자 구분만 파생값이다", citation=_C31,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "총자산 기중평잔", 0, "KRW", assets,
                 formula=f"(기초 + 기말) ÷ 2 — 일별 잔액 원장 없음 · {_DERIVED}", citation=_C31,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "자기자본(회계) 기중평잔", 0, "KRW", equity,
                 formula=f"(기초 + 기말) ÷ 2 — 일별 잔액 원장 없음 · {_DERIVED}", citation=_C31,
                 source_module=_M_DER),
        FormLine("2020", "이자수익자산 기중평잔", 0, "KRW", earning,
                 formula="B2510 분모와 같은 값", citation=_C31,
                 source_module=_M_DER),
        FormLine("2030", "총 여신 잔액", 0, "KRW", loans,
                 formula=f"rdm_asset_quality 실측 합 · {_MEASURED}",
                 citation=_C27, source_module=_M_RDM),
        FormLine("3000", "총자산순이익률 (ROA)", 0, "ratio", ratio(inc["당기순이익"],
                                                              assets),
                 formula="당기순이익 ÷ 총자산 기중평잔", citation=_C31,
                 source_module=_M_DER),
        FormLine("3010", "자기자본순이익률 (ROE)", 0, "ratio",
                 ratio(inc["당기순이익"], equity),
                 formula="당기순이익 ÷ 자기자본 기중평잔", citation=_C31,
                 source_module=_M_DER),
        FormLine("3020", "총자산경상이익률 (세전)", 0, "ratio",
                 ratio(inc["법인세차감전순이익"], assets),
                 formula="법인세차감전순이익 ÷ 총자산 기중평잔", citation=_C31,
                 source_module=_M_DER),
        FormLine("3030", "충당금적립전이익률", 0, "ratio", ratio(pre_prov, assets),
                 formula="충당금적립전이익 ÷ 총자산 기중평잔 — B2505와 같은 정의",
                 citation=_C31, source_module=_M_DER),
        FormLine("3040", "순이자마진 (NIM)", 0, "ratio",
                 ratio(fl["net_interest"], earning),
                 formula="순이자이익 ÷ 이자수익자산 기중평잔 — B2510과 같은 값",
                 citation=_C31, source_module=_M_DER),
        FormLine("3050", "총자산경비율", 0, "ratio", ratio(opex, assets),
                 formula="판매관리비 ÷ 총자산 기중평잔", citation=_C31,
                 source_module=_M_DER),
        FormLine("3060", "영업경비율 (효율성)", 0, "ratio", ratio(opex, gross),
                 formula="판매관리비 ÷ 총이익", citation=_C31, source_module=_M_DER),
        FormLine("3070", "대손비용률", 0, "ratio", ratio(prov, loans),
                 formula="충당금 전입액 ÷ 총 여신 잔액", citation=_C31,
                 source_module=_M_ECL),
        FormLine("3080", "유효법인세율", 0, "ratio",
                 ratio(tax, inc["법인세차감전순이익"]),
                 formula=f"법인세비용 ÷ 세전이익 (가정 실효세율 "
                         f"{CORPORATE_TAX_RATE:.1%})", citation=_C99,
                 source_module=_M_PRU),
    ]
    L.append(_remark(
        "비율마다 분자·분모 라인을 함께 실었다 — 비율만 실으면 감독당국이 재계산할 수 "
        "없고 서식도 스스로 대사하지 못한다. 분모의 기중평잔은 일별 잔액 원장이 없어 "
        "파생값이며, 계정별 성장률 키가 같아 B2505·B2510과 같은 평잔을 쓴다. NIM은 "
        "B2510과, 충당금적립전이익은 B2505와, 분자 손익은 전부 B2110과 대사한다.",
        _C31))
    t = tol(inc["영업수익"])
    checks = [
        _sum_check("총이익 = 순이자이익 + 비이자이익", L, "1080",
                   ("1030", "1040"), t),
        FormCheck("총이익 = 영업수익 (손익계산서)", inc["영업수익"],
                  _val(L, "1080"), t),
        FormCheck("충당금적립전이익 = 세전이익 + 충당금 전입액",
                  inc["법인세차감전순이익"] + prov, _val(L, "1020"), t),
        _ratio_check("ROA = 당기순이익 ÷ 총자산 평잔", L, "3000", "1000", "2000"),
        _ratio_check("ROE = 당기순이익 ÷ 자기자본 평잔", L, "3010", "1000", "2010"),
        _ratio_check("세전 ROA = 세전이익 ÷ 총자산 평잔", L, "3020", "1010", "2000"),
        _ratio_check("충당금적립전이익률", L, "3030", "1020", "2000"),
        _ratio_check("NIM = 순이자이익 ÷ 이자수익자산 평잔", L, "3040",
                     "1030", "2020"),
        _ratio_check("총자산경비율 = 판관비 ÷ 총자산 평잔", L, "3050",
                     "1050", "2000"),
        _ratio_check("영업경비율 = 판관비 ÷ 총이익", L, "3060", "1050", "1080"),
        _ratio_check("대손비용률 = 충당금 ÷ 총여신", L, "3070", "1060", "2030"),
        _ratio_check("유효법인세율 = 법인세 ÷ 세전이익", L, "3080", "1070", "1010"),
        FormCheck("손익계산서 대사 · 당기순이익", inc["당기순이익"],
                  _val(L, "1000"), t),
        FormCheck("손익계산서 대사 · 법인세차감전순이익",
                  inc["법인세차감전순이익"], _val(L, "1010"), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2521

def _b2521(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """월중 수수료 신설 및 조정현황 — 수수료 원장이 없어 전부 파생이다."""
    ch = fee_changes(ctx)
    L = [
        FormLine("1000", "수수료 신설·조정 건수", 0, "count", float(len(ch)),
                 formula=f"수수료 요율 원장 없음 — 건수·요율 모두 {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
    ]
    act_codes = []
    for i, act in enumerate(FEE_ACTIONS, start=1):
        code = f"{1000 + i * 10}"
        act_codes.append(code)
        L.append(FormLine(code, f"구분 · {act}", 1, "count",
                          float(int((ch["action"] == act).sum())),
                          citation=_C99, source_module=_M_DER))
    checks = []
    for i, (_, r) in enumerate(ch.iterrows(), start=1):
        base = 2000 + i * 100
        L += [
            FormLine(str(base), f"{r['item']} · {r['action']} — 종전요율", 1,
                     "ratio", float(r["rate_before"]),
                     formula=f"{_DERIVED} (신설은 0)", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 10), "변경요율", 2, "ratio",
                     float(r["rate_after"]),
                     formula=f"{_DERIVED} (폐지는 0)", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 20), "변동폭", 2, "ratio", float(r["delta"]),
                     formula="변경요율 − 종전요율", citation=_C99,
                     source_module=_M_DER),
        ]
        checks.append(FormCheck(f"{i}행 변동폭 = 변경 − 종전",
                                float(r["rate_after"] - r["rate_before"]),
                                _val(L, str(base + 20)), 1e-12))
    L.append(_remark(
        "이 서식은 앵커할 산출값이 없는 완전 파생이다 — 수수료 요율·조정 이력 원장이 "
        "이 저장소에 아예 없다. 기준일 고정 시드로 만들어 같은 시드면 같은 값이 나오며, "
        "요율 변경은 당월 이후 수입에 반영되므로 B2522(수수료수입)와 금액으로 연결되지 "
        "않는다. 실제 제출 시 수수료 마스터로 대체된다."))
    checks.append(_sum_check("건수 = 구분별 합", L, "1000", tuple(act_codes), 1e-9))
    return L, checks


# ---------------------------------------------------------------- B2522

def _b2522(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """주요 수수료수입 현황 — 총액은 비이자이익에서 오고 항목 구성만 파생이다."""
    inc = income(ctx)
    fl = interest_flow(ctx)
    mix = noninterest_mix(ctx)
    fee = fee_mix(ctx)
    total = mix["수수료이익"]
    L = [
        FormLine("1000", "수수료수입 합계", 0, "KRW", total,
                 formula="비이자이익의 수수료이익 — B2501 1210과 같은 값",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
    ]
    item_codes = []
    for i, item in enumerate(FEE_ITEMS, start=1):
        code = f"{1000 + i * 10}"
        item_codes.append(code)
        L.append(FormLine(code, item, 1, "KRW", fee[item],
                          formula=f"항목 구성비는 {_DERIVED} — 수수료 원장 없음",
                          citation=_C99, source_module=_M_DER))
    non_codes = []
    for i, item in enumerate(NONINT_ITEMS, start=1):
        code = f"{2000 + i * 10}"
        non_codes.append(code)
        L.append(FormLine(code, f"비이자이익 · {item}", 1, "KRW", mix[item],
                          formula=f"구성비는 {_DERIVED}", citation=_C99,
                          source_module=_M_DER))
    L += [
        FormLine("2000", "비이자이익 합계", 0, "KRW", fl["noninterest"],
                 formula="B2501 1200과 같은 값", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3000", "영업수익 (실측·분모)", 0, "KRW", inc["영업수익"],
                 formula=f"손익계산서(B2110) · {_MEASURED}", citation=_C99,
                 source_module=_M_PRU),
        FormLine("3010", "수수료수입 비중 (영업수익 대비)", 0, "ratio",
                 ratio(total, inc["영업수익"]),
                 formula="수수료수입 합계 ÷ 영업수익", citation=_C31,
                 source_module=_M_DER),
        FormLine("3020", "수수료수입 비중 (비이자이익 대비)", 0, "ratio",
                 ratio(total, fl["noninterest"]),
                 formula="수수료수입 합계 ÷ 비이자이익", citation=_C31,
                 source_module=_M_DER),
    ]
    L.append(_remark(
        "수수료수입 총액은 비이자이익의 수수료이익 그 자체이고 항목 구성비만 파생이다 — "
        "수수료 원장이 없다. 비이자이익 자체가 영업수익(실측)에서 갈라낸 파생 구분이므로, "
        "이 서식이 손익계산서를 넘어서지 않도록 '수수료 ≤ 비이자이익 ≤ 영업수익'을 "
        "대사한다. B2521(요율 조정)과는 금액으로 연결되지 않는다."))
    checks = [
        _sum_check("수수료수입 합계 = 항목별 합", L, "1000", tuple(item_codes),
                   tol(total)),
        _sum_check("비이자이익 = 항목별 합", L, "2000", tuple(non_codes),
                   tol(fl["noninterest"])),
        FormCheck("수수료수입 ≤ 비이자이익", 0.0,
                  max(0.0, total - fl["noninterest"]), tol(fl["noninterest"])),
        FormCheck("비이자이익 ≤ 영업수익", 0.0,
                  max(0.0, fl["noninterest"] - inc["영업수익"]),
                  tol(inc["영업수익"])),
        _ratio_check("수수료 비중 = 수수료 ÷ 영업수익", L, "3010", "1000", "3000"),
        _ratio_check("수수료 비중 = 수수료 ÷ 비이자이익", L, "3020",
                     "1000", "2000"),
        FormCheck("손익계산서 대사 · 영업수익", inc["영업수익"], _val(L, "3000"),
                  tol(inc["영업수익"])),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2501": ("은행업감독규정 제99조 업무보고서 · 제31조 경영실태평가", "PRD-RDM",
              _b2501),
    "B2505": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-RDM", _b2505),
    "B2506": ("은행업감독규정 제29조 대손충당금 · K-IFRS 제1109호 5.5", "PRD-ECL",
              _b2506),
    "B2507": ("은행업감독규정 제29조 대손충당금 · Basel III CRE20.94", "PRD-ECL",
              _b2507),
    "B2508": ("Basel III CAP50 신중한 평가(독립가격검증) · 은행업감독규정 제99조", "PRD-MKT",
              _b2508),
    "B2510": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-ALM", _b2510),
    "B2511": ("Basel III SRP31.94 재설정 구간 · 은행업감독규정 제30조의2 금리리스크", "PRD-ALM",
              _b2511),
    "B2511-1": ("은행업감독규정 제99조 업무보고서 · 제30조의2 금리리스크", "PRD-ALM",
                _b2511_1),
    "B2512": ("Basel III SRP31.94 재설정 구간 · 은행업감독규정 제30조의2 금리리스크", "PRD-ALM",
              _b2512),
    "B2512-1": ("은행업감독규정 제99조 업무보고서 · 제31조 경영실태평가", "PRD-ALM",
                _b2512_1),
    "B2512-2": ("은행업감독규정 제99조 업무보고서 · 제31조 경영실태평가", "PRD-ALM",
                _b2512_2),
    "B2513": ("은행법 제38조 제1호 유가증권 투자한도 · Basel III CAP50 신중한 평가", "PRD-MKT",
              _b2513),
    "B2516": ("은행법 제37조 제2항·제3항 자회사 출자 및 신용공여", "PRD-RDM",
              _b2516),
    "B2517": ("은행법 제28조 겸영업무 · 자본시장법 제103조 신탁업", "PRD-RDM",
              _b2517),
    "B2518": ("상법 제458조 이익준비금 · Basel III CRE40 자본의 정의", "PRD-CAP",
              _b2518),
    "B2520": ("은행업감독규정 제31조 경영실태평가 계량지표", "PRD-RDM", _b2520),
    "B2521": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _b2521),
    "B2522": ("은행업감독규정 제99조 업무보고서 · 제31조 경영실태평가", "PRD-RDM",
              _b2522),
}
