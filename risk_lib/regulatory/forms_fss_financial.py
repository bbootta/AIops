"""금감원 FINES 업무보고서 — 재무제표 21건 (B21xx).

근거는 은행업감독규정 제99조(업무보고서)·제26조(자기자본비율)와 K-IFRS
제1109호(금융상품)·제1110호(연결재무제표)다.

**총괄분은 이미 있다.** BR-15(B2101 대차대조표)·BR-16(B2110 손익계산서)가
`pru_balance_sheet` · `pru_income_statement`를 그대로 낸다. 이 모듈은 그 두 장의
계정별(은행·신탁·종금)·지역별·범주별·연결 변형이므로 **같은 두 테이블에만 앵커**한다.
같은 재무제표가 서식마다 다른 값을 갖지 않도록 국내+해외 = 총괄분, 범주별 합 =
계정 잔액, 연결 = 단독을 전부 FormCheck로 건다.

**원장이 없어 파생·배분한 것** (자세한 근거는 `forms_fss_financial_data` docstring)
  국내·해외 계정별 금액   계정별 소재지 원장이 없다. 전 계정에 같은 실측 EAD 비중
                          (`overseas_share`)을 곱한다 — BF201이 쓰는 바로 그 비율이다.
                          한 비율을 전 계정에 곱하므로 대차 항등식이 배분 후에도 성립한다.
  손익 국내·해외          수익·비용은 country별 실측 합이고, 충당금은 실측 ECL 비중,
                          운영손실·법인세만 배분이다.
  IFRS 9 범주             범주 열이 없다. FVTPL은 트레이딩 포지션 산출값에 앵커한다.
  국내 지역               가계는 `forms_fss_retail_data.household`의 지역을 재사용하고
                          비가계만 시드 고정으로 뽑는다(가중치 `NONRETAIL_REGION_W`는
                          관찰 근거 없는 가정치다). 수신은 원장이 아예 없어
                          예수금 총액을 그 지역분포로 가른다.

**미영위로 0을 적은 것** — 신탁계정(B2104·B2105·B2113·B2114)과 종금계정(B2106·
B2107·B2115·B2116). 이 저장소의 원천 데이터에 해당 계정과목이 존재하지 않는다.
0을 조용히 적으면 "없다"와 "안 봤다"가 구분되지 않으므로 **모든 라인의 formula와
9000 비고 라인에 사유를 남긴다.**

**연결은 단독과 같다** — B2109·B2118·B2125·B2126. 연결 대상 자회사 원장(지분율·
연결범위·소수주주지분)이 없다. forms_fss_capital의 B2311·B2312와 같은 처리이며
문구를 맞췄다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

from risk_lib.prudential.financials import CORPORATE_TAX_RATE
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_card_data import (
    COST_ITEMS, REVENUE_ITEMS, card_book, cost_mix, credit_cost, revenue_mix,
)
from risk_lib.regulatory.forms_fss_financial_data import (
    ASSET_CATEGORIES, BS_SKIP, BS_TOTALS, CORP_DEPOSITS, LIAB_CATEGORIES,
    RETAIL_DEPOSITS, asset_categories, bs_amounts, deposit_regions,
    derivative_values, domestic_share, income_split, liability_categories,
    region_book, tol, trading_position,
)
from risk_lib.regulatory.forms_fss_overseas_data import HOME_COUNTRY
from risk_lib.regulatory.forms_fss_retail_data import REGIONS

_M_PRU = "risk_lib.prudential.financials"
_M_DER = "risk_lib.regulatory.forms_fss_financial_data"
_M_RDM = "risk_lib.datamodel.materialize_detail"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_MKT = "risk_lib.capital.market_risk"
_M_CARD = "risk_lib.regulatory.forms_fss_card_data"
# 미영위 계정에는 산출 모듈이 없다. 빈 문자열을 두면 "못 채웠다"로 읽히므로
# 산출값이 아니라 계정 부존재라는 사실을 그대로 적는다.
_M_NONE = "해당 계정 미영위 — 산출 모듈 없음"

_C99 = "은행업감독규정 제99조 업무보고서"
_C26 = "은행업감독규정 제26조 자기자본비율"
_C1109 = "K-IFRS 제1109호 금융상품 — 금융자산·금융부채의 분류"
_C1110 = "K-IFRS 제1110호 연결재무제표"
_C_TRUST = ("은행법 제28조 겸영업무 · 자본시장과 금융투자업에 관한 법률 "
            "제103조 신탁재산의 제한")
# 종합금융회사는 「종합금융회사에 관한 법률」 폐지 후 자본시장법 제336조로 옮겼다.
# 부칙이 아니라 본칙 조문이 정본이다.
_C_MERCH = ("은행법 제28조 겸영업무 · 자본시장과 금융투자업에 관한 법률 "
            "제336조 종합금융회사의 업무")
_C_CARD = "여신전문금융업법 제2조 신용카드업 · 은행법 제28조 겸영업무"
# 대손충당금 적립기준은 여신전문금융업감독규정 제11조다. forms_fss_card의 _R11과
# 같은 조문을 써야 B2119와 B2817이 같은 근거 위에 선다.
_C_CARD_ALW = "여신전문금융업감독규정 제11조 대손충당금 등 적립기준"
# 재무제표 관련 은행법 조문은 제41조(재무제표의 공고 등)다. 제33조의2는 조건부
# 자본증권 발행절차이므로 재무제표 근거가 될 수 없다.
_C_BANK_FS = "은행법 제41조 재무제표의 공고 등"
# 예대율은 은행업감독규정 제26조 제1항의 경영지도비율이다 —
# risk_lib.prudential.liquidity·forms_fss_keyfin과 같은 조문을 쓴다.
_C_LDR = "은행업감독규정 제26조 제1항 원화예대율"

_ALLOC = "계정별 소재지 원장 없음 — 실측 EAD 비중으로 배분"
_CONSOL = "연결 자회사 원장 없음 → 연결 = 단독"
_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"

# 신탁업·종합금융업 미영위 사유. B2311의 문구와 같은 형식으로 적는다 —
# "0"이 미조회가 아니라 계정 부존재라는 것을 서식 자체가 말해야 한다.
_TRUST_REASON = "신탁계정 미영위 — 원천 데이터에 신탁 계정과목 없음"
_MERCH_REASON = "종금계정 미영위 — 원천 데이터에 종합금융 계정과목 없음"


# ---------------------------------------------------------------- 공용 블록

def _bs_lines(ctx, w: float, *, suffix: str, note: str
              ) -> tuple[list[FormLine], dict[str, str], dict[str, list[str]]]:
    """대차대조표 계정 라인 한 벌. `w`를 전 계정에 곱하므로 대차 항등식이 유지된다.

    계정별로 다른 비율을 쓰면 자산 = 부채 + 자본이 깨지고 그 차액을 메울 근거가 없다.

    `note`는 **라인마다** 붙는다. 배분·연결 사유를 소계나 비고에만 적으면 서식이
    flat table로 실체화될 때 하위 셀이 실측으로 읽힌다. 배분이 없는 경우(w = 1)
    에도 사유는 남긴다 — "곱하지 않았다"와 "자회사를 안 봤다"는 다른 말이다.
    """
    t = ctx.tables["pru_balance_sheet"]
    L: list[FormLine] = []
    code_of: dict[str, str] = {}
    comp: dict[str, list[str]] = {"자산": [], "부채": [], "자본": []}
    for si, section in enumerate(("자산", "부채", "자본"), start=1):
        sub = t[t["section"] == section]
        base = si * 1000
        L.append(FormLine(str(base), f"{section} 구분", 0, "text", None,
                          text_value=f"{len(sub)}개 계정 · {suffix}",
                          citation=_C99, source_module=_M_PRU))
        for j, (_, r) in enumerate(sub.iterrows(), start=1):
            code = str(base + j * 10)
            item = str(r["item"])
            code_of[item] = code
            gross = float(r["amount"])
            L.append(FormLine(
                code, item, 1, "KRW", gross * w,
                formula=(f"총괄분 {gross:,.0f}원 × {w:.6f} — {note}"
                         if note and w != 1.0 else
                         f"총괄분 {gross:,.0f}원 — {note}" if note
                         else f"총괄분 {gross:,.0f}원"),
                citation=_C99, source_module=_M_PRU,
                is_subtotal=item in BS_TOTALS))
            if item not in BS_TOTALS and item not in BS_SKIP:
                comp[section].append(code)
    return L, code_of, comp


def _bs_checks(L: list[FormLine], code_of: dict[str, str],
               comp: dict[str, list[str]]) -> list[FormCheck]:
    """대차대조표가 스스로 대사해야 하는 항등식 — 구성계정 합·대차 일치·순액."""
    t = tol(_val(L, code_of["자산총계"]))
    return [
        _sum_check("자산 구성계정 합 = 자산총계", L, code_of["자산총계"],
                   tuple(comp["자산"]), t),
        _sum_check("부채 구성계정 합 = 부채총계", L, code_of["부채총계"],
                   tuple(comp["부채"]), t),
        _sum_check("자본 구성계정 합 = 자본총계 (회계)", L, code_of["자본총계 (회계)"],
                   tuple(comp["자본"]), t),
        _sum_check("자산총계 = 부채총계 + 자본총계", L, code_of["자산총계"],
                   (code_of["부채총계"], code_of["자본총계 (회계)"]), t),
        _sum_check("대출채권 순액 = 총액 + 대손충당금(차감)", L,
                   code_of["대출채권 (순액)"],
                   (code_of["대출채권 (총액)"], code_of["대손충당금 (차감)"]), t),
    ]


def _income_lines(rows: list[tuple[str, float, str]], *, base: int = 1000,
                  note: str = "") -> tuple[list[FormLine], dict[str, str]]:
    """손익계산서 7행. 비용은 음수로 적어 총괄분(BR-16)과 부호 규약을 맞춘다.

    `note`는 라인마다 붙는다 — 연결 서식의 계정 라인이 "포트폴리오 수익 합계"만
    달고 나가면 자회사를 반영한 연결 수치로 읽힌다.
    """
    L, code_of = [], {}
    for i, (item, amount, formula) in enumerate(rows, start=1):
        code = str(base + i * 10)
        code_of[item] = code
        if note:
            formula = f"{formula} — {note}"
        L.append(FormLine(code, item, 0, "KRW", amount, formula=formula,
                          citation=_C99, source_module=_M_PRU,
                          is_subtotal=item in ("법인세차감전순이익", "당기순이익")))
    return L, code_of


def _income_checks(L: list[FormLine], code_of: dict[str, str]) -> list[FormCheck]:
    t = tol(_val(L, code_of["영업수익"]))
    return [
        _sum_check("세전이익 = 수익 + 비용 + 충당금 + 운영손실", L,
                   code_of["법인세차감전순이익"],
                   (code_of["영업수익"], code_of["영업비용"],
                    code_of["충당금 전입액"], code_of["운영손실"]), t),
        _sum_check("당기순이익 = 세전이익 + 법인세비용", L, code_of["당기순이익"],
                   (code_of["법인세차감전순이익"], code_of["법인세비용"]), t),
    ]


def _nil_lines(groups: tuple[tuple[str, tuple[str, ...]], ...], reason: str,
               citation: str) -> tuple[list[FormLine], list[FormCheck]]:
    """미영위 계정 서식의 라인 한 벌 — 0과 사유를 **라인마다** 함께 남긴다.

    소계에만 사유를 적으면 서식이 flat table로 실체화될 때 하위 셀의 0이
    "산출했더니 0"으로 읽힌다.
    """
    L: list[FormLine] = []
    checks: list[FormCheck] = []
    for gi, (title, items) in enumerate(groups, start=1):
        base = gi * 1000
        codes = []
        L.append(FormLine(str(base), title, 0, "KRW", 0.0, formula=reason,
                          citation=citation, source_module=_M_NONE,
                          is_subtotal=True))
        for i, item in enumerate(items, start=1):
            code = str(base + i * 10)
            codes.append(code)
            L.append(FormLine(code, item, 1, "KRW", 0.0, formula=reason,
                              citation=citation, source_module=_M_NONE))
        checks.append(_sum_check(f"{title} = 세부항목 합", L, str(base),
                                 tuple(codes), 1e-9))
    return L, checks


def _remark(text: str, citation: str) -> FormLine:
    return FormLine("9000", "비고", 0, "text", None, text_value=text,
                    citation=citation)


# ---------------------------------------------------------------- B2102 / B2103

def _b2102(ctx):
    """대차대조표(은행계정, 국내분) — 국내분 + 해외분 = 총괄분(B2101)을 건다."""
    w = domestic_share(ctx)
    L, code_of, comp = _bs_lines(ctx, w, suffix="국내분", note=_ALLOC)
    amt = bs_amounts(ctx)
    p = ctx.portfolio
    dom_loan = float(p.loc[p["country"] == HOME_COUNTRY, "ead"].sum())
    L = [FormLine("100", "국내분 배분비율", 0, "ratio", w,
                  formula="1 − 해외 EAD 비중 — 비율은 실측, 계정별 배분은 파생",
                  citation=_C99, source_module=_M_DER)] + L
    L += [
        FormLine("4000", "국내 여신잔액 (원장 실측)", 0, "KRW", dom_loan,
                 formula=f"country={HOME_COUNTRY} 익스포저 EAD 실측 합 · "
                         f"{int((p['country'] == HOME_COUNTRY).sum()):,}건",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("4010", "총괄분 자산총계 (B2101)", 0, "KRW", amt["자산총계"],
                 formula="pru_balance_sheet 자산총계 — 국내분+해외분의 앵커",
                 citation=_C99, source_module=_M_PRU),
        _remark("계정별 국내·해외 소재지 원장이 없어 전 계정에 같은 실측 EAD 비중을 "
                "곱해 배분했다. 배분비율은 forms_fss_overseas_data.overseas_share의 "
                "여집합이며 BF201(해외점포 자산·부채)과 같은 비율이다. 비율 자체는 "
                "실측이고 계정별 배분 결과는 파생값이다.", _C99),
    ]
    checks = _bs_checks(L, code_of, comp)
    checks += [
        # 배분비율의 모수가 EAD이므로 대출채권(총액) 국내분은 국내 EAD와 같아야
        # 한다 — 어긋나면 배분비율의 모수가 대차대조표와 다른 것이다.
        FormCheck("배분 대출채권(총액) = 국내 여신잔액 실측", dom_loan,
                  _val(L, code_of["대출채권 (총액)"]), tol(dom_loan)),
        FormCheck("국내분 자산총계 = 총괄분 × 배분비율", amt["자산총계"] * w,
                  _val(L, code_of["자산총계"]), tol(amt["자산총계"])),
    ]
    return L, checks


def _b2103(ctx):
    """대차대조표(은행계정, 해외분) — BF201과 같은 비율을 쓴다. 갈리면 안 된다."""
    w = 1.0 - domestic_share(ctx)
    L, code_of, comp = _bs_lines(ctx, w, suffix="해외분", note=_ALLOC)
    amt = bs_amounts(ctx)
    p = ctx.portfolio
    ov = p["country"] != HOME_COUNTRY
    ov_loan = float(p.loc[ov, "ead"].sum())
    L = [FormLine("100", "해외분 배분비율", 0, "ratio", w,
                  formula="해외 EAD ÷ 전체 EAD — 비율은 실측, 계정별 배분은 파생",
                  citation=_C99, source_module=_M_DER)] + L
    L += [
        FormLine("4000", "해외 여신잔액 (원장 실측)", 0, "KRW", ov_loan,
                 formula=f"country≠{HOME_COUNTRY} 익스포저 EAD 실측 합 · "
                         f"{int(ov.sum()):,}건 · "
                         f"{int(p.loc[ov, 'country'].nunique())}개국",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("4010", "총괄분 자산총계 (B2101)", 0, "KRW", amt["자산총계"],
                 formula="pru_balance_sheet 자산총계 — 국내분+해외분의 앵커",
                 citation=_C99, source_module=_M_PRU),
        FormLine("4020", "국내분 자산총계 (B2102)", 0, "KRW",
                 amt["자산총계"] * domestic_share(ctx),
                 formula="총괄분 × 국내분 배분비율 — B2102와 같은 값",
                 citation=_C99, source_module=_M_DER),
        _remark("B2102와 같은 배분비율의 여집합이다. 해외점포 서식 BF201도 이 비율을 "
                "쓰므로 해외분 대차대조표가 두 값을 갖지 않는다. 계정별 배분 결과는 "
                "파생값이며 비율 자체는 실측 EAD 비중이다.", _C99),
    ]
    checks = _bs_checks(L, code_of, comp)
    checks += [
        FormCheck("배분 대출채권(총액) = 해외 여신잔액 실측", ov_loan,
                  _val(L, code_of["대출채권 (총액)"]), tol(ov_loan)),
        # 이 한 줄이 B2101 = B2102 + B2103을 보증한다.
        FormCheck("국내분 + 해외분 자산총계 = 총괄분", amt["자산총계"],
                  _val(L, "4020") + _val(L, code_of["자산총계"]),
                  tol(amt["자산총계"])),
    ]
    return L, checks


# ---------------------------------------------------------------- B2104 / B2105

_TRUST_ASSETS = ("현금 및 예치금", "유가증권", "대출금", "부동산", "기타 신탁자산")
_TRUST_LIAB = ("원본", "신탁이익", "특별유보금", "기타 신탁부채")
# 자본시장법 제103조의 신탁재산 구분(금전신탁·재산신탁)을 따른 상품 어휘다.
_TRUST_PRODUCTS = ("특정금전신탁", "불특정금전신탁", "연금신탁", "퇴직연금신탁",
                   "금전채권신탁", "부동산신탁", "유가증권신탁", "동산신탁")


def _b2104(ctx):
    """대차대조표(신탁계정, 총계기준) — 신탁업 미영위. 0과 사유를 함께 적는다."""
    L, checks = _nil_lines((("신탁자산 총계", _TRUST_ASSETS),
                            ("신탁부채 총계", _TRUST_LIAB)),
                           _TRUST_REASON, _C_TRUST)
    L.append(_remark(
        "이 저장소의 원천 데이터(rdm_* · pru_*)에 신탁 계정과목이 존재하지 않는다. "
        "신탁업 미영위로 보아 전 계정을 0으로 적었으며, 0은 '미조회'가 아니라 "
        "'해당 계정 없음'이다. 신탁업을 영위하면 신탁 원장을 먼저 확보해야 하고 "
        "여기 0을 그대로 제출해서는 안 된다.", _C_TRUST))
    checks.append(FormCheck("신탁자산 총계 = 신탁부채 총계",
                            _val(L, "1000"), _val(L, "2000"), 1e-9))
    return L, checks


def _b2105(ctx):
    """대차대조표(신탁계정, 상품별) — 상품 칸은 두되 전부 0이다."""
    L, checks = _nil_lines((("신탁 수탁고 합계", _TRUST_PRODUCTS),),
                           _TRUST_REASON, _C_TRUST)
    L.append(_remark(
        "상품별 칸을 비우지 않고 0으로 채운 것은 감독당국 집계와 행 수를 맞추기 "
        "위해서다. 신탁계정 미영위이므로 어느 상품도 잔고가 없다 — B2104와 같은 "
        "사유이며 두 서식의 합계는 모두 0으로 일치한다.", _C_TRUST))
    return L, checks


# ---------------------------------------------------------------- B2106 / B2107

_MERCH_ASSETS = ("현금 및 예치금", "유가증권", "어음할인·매출채권", "리스자산",
                 "기타 종금자산")
_MERCH_LIAB = ("발행어음", "어음관리계좌(CMA)", "차입금", "기타 종금부채")
_MERCH_EQUITY = ("종금계정 자본",)


def _b2106(ctx):
    """대차대조표(종금계정, 총괄분) — 종합금융업 미영위."""
    L, checks = _nil_lines((("종금자산 총계", _MERCH_ASSETS),
                            ("종금부채 총계", _MERCH_LIAB),
                            ("종금자본 총계", _MERCH_EQUITY)),
                           _MERCH_REASON, _C_MERCH)
    L.append(_remark(
        "이 저장소의 원천 데이터에 종합금융 계정과목(발행어음·어음관리계좌·"
        "팩토링·리스)이 존재하지 않는다. 종금계정 미영위로 보아 전 계정을 0으로 "
        "적었으며, 0은 '미조회'가 아니라 '해당 계정 없음'이다.", _C_MERCH))
    checks.append(FormCheck("종금자산 총계 = 종금부채 + 종금자본",
                            _val(L, "1000"),
                            _val(L, "2000") + _val(L, "3000"), 1e-9))
    return L, checks


def _b2107(ctx):
    """대차대조표(종금계정, 국내분·해외분) — 미영위이므로 두 분할 모두 0이다."""
    L, checks = _nil_lines((("종금자산 국내분", _MERCH_ASSETS),
                            ("종금자산 해외분", _MERCH_ASSETS)),
                           _MERCH_REASON, _C_MERCH)
    L.append(FormLine("4000", "종금자산 총계 (국내분 + 해외분)", 0, "KRW", 0.0,
                      formula=_MERCH_REASON, citation=_C_MERCH,
                      source_module=_M_NONE, is_subtotal=True))
    L.append(_remark(
        "종금계정 미영위(B2106과 같은 사유)이므로 국내분·해외분 배분 자체가 "
        "성립하지 않는다. 은행계정의 국내·해외 배분비율(B2102·B2103)을 여기에 "
        "적용하지 않았다 — 없는 계정에 비율을 곱하면 0이 아니라 근거 없는 0이 된다.",
        _C_MERCH))
    checks.append(_sum_check("종금자산 총계 = 국내분 + 해외분", L, "4000",
                             ("1000", "2000"), 1e-9))
    return L, checks


# ---------------------------------------------------------------- B2109

def _b2109(ctx):
    """연결대차대조표 — 연결 대상 자회사 원장이 없어 연결 = 단독이다."""
    L, code_of, comp = _bs_lines(ctx, 1.0, suffix="연결", note=_CONSOL)
    amt = bs_amounts(ctx)
    L = [FormLine("100", "연결 대상 자회사 수", 0, "count", 0.0,
                  formula="자회사 지분·연결범위 원장 미보유 → 연결 대상 없음",
                  citation=_C1110, source_module=_M_PRU, is_subtotal=True)] + L
    L += [
        FormLine("4000", "비지배지분 (소수주주지분)", 0, "KRW", 0.0,
                 formula=_CONSOL + " → 비지배지분 없음", citation=_C1110,
                 source_module=_M_PRU),
        FormLine("4010", "단독 자산총계 (B2101)", 0, "KRW", amt["자산총계"],
                 formula="pru_balance_sheet 자산총계", citation=_C99,
                 source_module=_M_PRU),
        _remark("연결 자회사 원장(지분율·연결범위·비지배지분)이 원천 데이터에 없다. "
                "자회사 수를 0으로 두고 연결 = 단독으로 표시했으며, 자회사 수치를 "
                "지어내지 않았다. 실제 제출 시 연결 대상 목록을 반드시 확인해야 한다. "
                "B2311(연결 자회사 내역)·B2312와 같은 처리다.", _C1110),
    ]
    checks = _bs_checks(L, code_of, comp)
    checks += [
        FormCheck("연결 자산총계 = 단독 자산총계", amt["자산총계"],
                  _val(L, code_of["자산총계"]), tol(amt["자산총계"])),
        FormCheck("연결 자본총계 = 단독 자본총계 + 비지배지분",
                  amt["자본총계 (회계)"] + _val(L, "4000"),
                  _val(L, code_of["자본총계 (회계)"]), tol(amt["자산총계"])),
    ]
    return L, checks


# ---------------------------------------------------------------- B2111 / B2112

def _income_form(ctx, col: str, other: str, label: str
                 ) -> tuple[list[FormLine], list[FormCheck]]:
    """손익계산서 국내분·해외분 공용 — 두 서식이 같은 배분표를 본다."""
    sp = income_split(ctx)
    rows = [(str(r["item"]), float(r[col]), str(r["basis"]))
            for _, r in sp.iterrows()]
    L, code_of = _income_lines(rows)
    m = {str(r["item"]): r for _, r in sp.iterrows()}
    L = [FormLine("100", f"{label} 구분", 0, "text", None,
                  text_value=f"{label} 손익 — 수익·비용은 country 실측 합, "
                             f"운영손실·법인세는 배분",
                  citation=_C99, source_module=_M_DER)] + L
    L += [
        FormLine("2000", "총괄분 영업수익 (B2110)", 0, "KRW",
                 float(m["영업수익"]["total"]),
                 formula="pru_income_statement 영업수익 — 국내분+해외분의 앵커",
                 citation=_C99, source_module=_M_PRU),
        FormLine("2010", f"{'해외' if col == 'domestic' else '국내'}분 영업수익",
                 0, "KRW", float(m["영업수익"][other]),
                 formula="총괄분 − 당 서식 영업수익", citation=_C99,
                 source_module=_M_DER),
        FormLine("2020", "총괄분 당기순이익 (B2110)", 0, "KRW",
                 float(m["당기순이익"]["total"]),
                 formula="pru_income_statement 당기순이익", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2030", f"{'해외' if col == 'domestic' else '국내'}분 당기순이익",
                 0, "KRW", float(m["당기순이익"][other]),
                 formula="총괄분 − 당 서식 당기순이익", citation=_C99,
                 source_module=_M_DER),
        FormLine("3000", f"{label} 영업수익 비중", 0, "ratio",
                 (float(m["영업수익"][col]) / float(m["영업수익"]["total"])
                  if float(m["영업수익"]["total"]) else 0.0),
                 formula=f"{label} 영업수익 ÷ 총괄분 영업수익",
                 citation=_C99, source_module=_M_DER),
        _remark("영업수익·영업비용은 익스포저 country로 가른 실측 합이고 배분이 "
                "아니다. 충당금 전입액은 실측 ECL 비중, 운영손실은 영업수익 비중, "
                "법인세비용은 세전이익 비중으로 배분했다 — 운영손실 원장에 국가 열이 "
                "없고, 부문별 실효세율을 다시 계산하면 국내+해외가 총괄분(B2110)과 "
                "어긋나기 때문이다.", _C99),
    ]
    checks = _income_checks(L, code_of)
    t = tol(float(m["영업수익"]["total"]))
    checks += [
        _sum_check("국내분 + 해외분 영업수익 = 총괄분", L, "2000",
                   (code_of["영업수익"], "2010"), t),
        _sum_check("국내분 + 해외분 당기순이익 = 총괄분", L, "2020",
                   (code_of["당기순이익"], "2030"), t),
        _ratio_check("영업수익 비중", L, "3000", code_of["영업수익"], "2000"),
    ]
    return L, checks


def _b2111(ctx):
    """손익계산서(은행계정, 국내분)."""
    return _income_form(ctx, "domestic", "overseas", "국내분")


def _b2112(ctx):
    """손익계산서(은행계정, 해외분)."""
    return _income_form(ctx, "overseas", "domestic", "해외분")


# ---------------------------------------------------------------- B2113 ~ B2116

_TRUST_INCOME = ("신탁보수", "신탁관련 수수료수익", "신탁재산 운용손익",
                 "신탁관련 판매관리비", "신탁계정 당기순이익")
_MERCH_INCOME = ("영업수익", "영업비용", "충당금 전입액",
                 "법인세차감전순이익", "종금계정 당기순이익")


def _b2113(ctx):
    """손익계산서(신탁계정, 총계기준) — 신탁업 미영위."""
    L, checks = _nil_lines((("신탁계정 손익 합계", _TRUST_INCOME),),
                           _TRUST_REASON, _C_TRUST)
    L.append(_remark(
        "신탁계정 미영위(B2104와 같은 사유)이므로 신탁보수·신탁관련비용이 모두 "
        "없다. 은행계정 손익계산서(B2110)에는 신탁 관련 손익이 섞여 있지 않다.",
        _C_TRUST))
    return L, checks


def _b2114(ctx):
    """손익계산서(신탁계정, 상품별) — 상품 칸은 두되 전부 0이다."""
    L, checks = _nil_lines((("상품별 신탁보수 합계", _TRUST_PRODUCTS),),
                           _TRUST_REASON, _C_TRUST)
    L.append(_remark(
        "B2105(상품별 수탁고)와 같은 상품 어휘를 쓴다. 수탁고가 0이므로 상품별 "
        "신탁보수도 0이며, 두 서식이 같은 상품 목록을 쓰지 않으면 감독당국 집계에서 "
        "행이 어긋난다.", _C_TRUST))
    return L, checks


def _b2115(ctx):
    """손익계산서(종금계정, 총괄분) — 종합금융업 미영위."""
    L, checks = _nil_lines((("종금계정 손익 합계", _MERCH_INCOME),),
                           _MERCH_REASON, _C_MERCH)
    L.append(_remark(
        "종금계정 미영위(B2106과 같은 사유). 은행계정 손익계산서(B2110)에 종금 "
        "관련 손익이 섞여 있지 않다.", _C_MERCH))
    return L, checks


def _b2116(ctx):
    """손익계산서(종금계정, 국내분·해외분) — 미영위이므로 두 분할 모두 0이다."""
    L, checks = _nil_lines((("종금계정 손익 국내분", _MERCH_INCOME),
                            ("종금계정 손익 해외분", _MERCH_INCOME)),
                           _MERCH_REASON, _C_MERCH)
    # 1000·2000은 국내분·해외분 손익 **합계** 라인이다. 대사 대상이 합계인데
    # 라인·검증 이름만 "당기순이익"으로 두면 서식이 스스로를 잘못 설명한다.
    L.append(FormLine("4000", "종금계정 손익 합계 (국내분 + 해외분)", 0, "KRW",
                      0.0, formula=_MERCH_REASON, citation=_C_MERCH,
                      source_module=_M_NONE, is_subtotal=True))
    L.append(_remark(
        "종금계정 미영위이므로 국내·해외 배분이 성립하지 않는다. 은행계정의 손익 "
        "배분비율(B2111·B2112)을 여기에 적용하지 않았다.", _C_MERCH))
    checks.append(_sum_check("종금계정 손익 합계 = 국내분 + 해외분", L, "4000",
                             ("1000", "2000"), 1e-9))
    return L, checks


# ---------------------------------------------------------------- B2118

def _b2118(ctx):
    """연결손익계산서 — 연결 대상 자회사 원장이 없어 연결 = 단독이다."""
    inc = ctx.tables["pru_income_statement"].sort_values("seq")
    rows = [(str(r["item"]), float(r["amount"]), str(r["formula"]))
            for _, r in inc.iterrows()]
    L, code_of = _income_lines(rows, note=_CONSOL)
    net = float(inc.loc[inc["item"] == "당기순이익", "amount"].iloc[0])
    L = [FormLine("100", "연결 대상 자회사 수", 0, "count", 0.0,
                  formula="자회사 지분·연결범위 원장 미보유 → 연결 대상 없음",
                  citation=_C1110, source_module=_M_PRU, is_subtotal=True)] + L
    L += [
        FormLine("2000", "지배기업 소유주 귀속 당기순이익", 0, "KRW", net,
                 formula=_CONSOL + " → 당기순이익 전액이 지배기업 귀속",
                 citation=_C1110, source_module=_M_PRU, is_subtotal=True),
        FormLine("2010", "비지배지분 귀속 당기순이익", 0, "KRW", 0.0,
                 formula=_CONSOL + " → 비지배지분 없음", citation=_C1110,
                 source_module=_M_PRU),
        FormLine("2020", "단독 당기순이익 (B2110)", 0, "KRW", net,
                 formula="pru_income_statement 당기순이익", citation=_C99,
                 source_module=_M_PRU),
        _remark("연결 자회사 원장(지분율·연결범위·비지배지분)이 원천 데이터에 없다. "
                "자회사 수를 0으로 두고 연결 = 단독으로 표시했으며, 자회사 손익을 "
                "지어내지 않았다. B2109·B2311과 같은 처리다.", _C1110),
    ]
    checks = _income_checks(L, code_of)
    checks += [
        _sum_check("당기순이익 = 지배기업 귀속 + 비지배지분 귀속", L,
                   code_of["당기순이익"], ("2000", "2010"), tol(net)),
        FormCheck("연결 당기순이익 = 단독 당기순이익", net,
                  _val(L, code_of["당기순이익"]), tol(net)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2119

def _b2119(ctx):
    """신용카드부문손익계산서 — 카드 서식(B2816·B2817)과 같은 배분표를 본다.

    카드부문 수익·판관비의 **합계는 실측**(portfolio.revenue·operating_cost)이고
    항목 구성비만 파생이다. 대손비용은 은행 전체 충당금 전입액의 카드 ECL 비중
    배분이다 — B2817과 같은 값이어야 두 서식이 대사된다.
    """
    cb = card_book(ctx)
    rm, cm = revenue_mix(ctx), cost_mix(ctx)
    inc = ctx.tables["pru_income_statement"]
    op_rev = float(inc.loc[inc["item"] == "영업수익", "amount"].iloc[0])
    rev = float(cb["revenue"].sum())
    sga = float(cb["operating_cost"].sum())
    cc = credit_cost(ctx)
    pre = rev - sga - cc
    tax = max(pre, 0.0) * CORPORATE_TAX_RATE
    L = [
        FormLine("1000", "카드부문 영업수익", 0, "KRW", rev,
                 formula=f"portfolio.revenue 실측 합 · 카드 익스포저 {len(cb):,}건",
                 citation=_C_CARD, source_module=_M_PTF, is_subtotal=True),
    ]
    rev_codes = []
    for i, item in enumerate(REVENUE_ITEMS, start=1):
        code = str(1000 + i * 10)
        rev_codes.append(code)
        L.append(FormLine(code, item, 1, "KRW", float(rm[item].sum()),
                          formula="합계는 실측 · 항목 구성비만 파생",
                          citation=_C_CARD, source_module=_M_CARD))
    L.append(FormLine("2000", "카드부문 영업비용", 0, "KRW", -sga,
                      formula="portfolio.operating_cost 실측 합 (음수 표시)",
                      citation=_C_CARD, source_module=_M_PTF, is_subtotal=True))
    cost_codes = []
    for i, item in enumerate(COST_ITEMS, start=1):
        code = str(2000 + i * 10)
        cost_codes.append(code)
        L.append(FormLine(code, item, 1, "KRW", -cm[item],
                          formula="합계는 실측 · 항목 구성비만 파생",
                          citation=_C_CARD, source_module=_M_CARD))
    L += [
        FormLine("3000", "카드부문 대손비용", 0, "KRW", -cc,
                 formula="은행 전체 충당금 전입액 × 카드 ECL 비중 — 비중은 실측, "
                         "배분은 파생. B2817 대손비용과 같은 금액이며 이 서식은 "
                         "손익계산서 부호 규약을 따라 음수로 적는다",
                 citation=_C_CARD_ALW, source_module=_M_CARD),
        FormLine("4000", "법인세차감전순이익", 0, "KRW", pre,
                 formula="영업수익 + 영업비용 + 대손비용", citation=_C_CARD,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("4010", "법인세비용", 0, "KRW", -tax,
                 formula=f"max(0, 세전이익) × {CORPORATE_TAX_RATE:.1%} — 은행 "
                         f"손익계산서와 같은 실효세율 가정",
                 citation=_C_CARD, source_module=_M_PRU),
        FormLine("4020", "카드부문 당기순이익", 0, "KRW", pre - tax,
                 formula="법인세차감전순이익 + 법인세비용", citation=_C_CARD,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("5000", "은행 영업수익 (B2110)", 0, "KRW", op_rev,
                 formula="pru_income_statement 영업수익", citation=_C99,
                 source_module=_M_PRU),
        FormLine("5010", "카드부문 수익 비중", 0, "ratio",
                 rev / op_rev if op_rev else 0.0,
                 formula="카드부문 영업수익 ÷ 은행 영업수익", citation=_C99,
                 source_module=_M_PRU),
        _remark("카드 원장이 없다. 카드채권 배정은 forms_fss_card_data가 기준일 "
                "고정 시드로 만든 파생값이고, 배정된 익스포저의 수익·비용 합계는 "
                "실측이다. 수익·비용의 항목 구성비만 파생이므로 합계는 B2816·B2817과 "
                "어긋나지 않는다.", _C_CARD),
    ]
    t = tol(rev)
    checks = [
        _sum_check("항목별 수익 합 = 카드부문 영업수익", L, "1000",
                   tuple(rev_codes), t),
        _sum_check("항목별 비용 합 = 카드부문 영업비용", L, "2000",
                   tuple(cost_codes), t),
        _sum_check("세전이익 = 영업수익 + 영업비용 + 대손비용", L, "4000",
                   ("1000", "2000", "3000"), t),
        _sum_check("당기순이익 = 세전이익 + 법인세비용", L, "4020",
                   ("4000", "4010"), t),
        _ratio_check("카드부문 수익 비중", L, "5010", "1000", "5000"),
        FormCheck("카드부문 영업수익 ≤ 은행 영업수익", 0.0,
                  max(0.0, rev - op_rev), tol(op_rev)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2121 / B2125

def _asset_category_form(ctx, *, consolidated: bool):
    """금융자산 범주별 분류 — 범주별 합이 대차대조표 계정 잔액과 같아야 한다."""
    cat = asset_categories(ctx)
    amt = bs_amounts(ctx)
    items = list(cat["item"])
    fin_total = float(cat["balance"].sum())
    other = amt["자산총계"] - fin_total
    pos = trading_position(ctx)
    drv_a, _ = derivative_values(ctx)
    scope = "연결" if consolidated else "은행계정 및 종금계정 총괄분"
    # 연결 사유는 라인마다 붙인다 — "적용 범위" 한 줄에만 적으면 flat table로
    # 실체화될 때 계정 셀이 자회사를 반영한 연결 수치로 읽힌다.
    tail = f" · {_CONSOL}" if consolidated else ""
    L = [
        FormLine("100", "적용 범위", 0, "text", None,
                 text_value=(f"{scope} · 말잔 기준"
                             + (f" · {_CONSOL}" if consolidated else
                                " · 종금계정 미영위이므로 은행계정과 같다")),
                 citation=_C1109, source_module=_M_PRU),
        FormLine("1000", "금융자산 합계", 0, "KRW", fin_total,
                 formula="현금 및 예치금 + 유가증권 + 대출채권(순액)" + tail,
                 citation=_C1109, source_module=_M_PRU, is_subtotal=True),
    ]
    cat_codes, item_codes = [], {it: [] for it in items}
    for ci, category in enumerate(ASSET_CATEGORIES, start=1):
        base = 1000 + ci * 100
        cat_codes.append(str(base))
        L.append(FormLine(str(base), category, 1, "KRW",
                          float(cat[category].sum()),
                          formula="범주 열이 원장에 없어 사업모형에서 배분" + tail,
                          citation=_C1109, source_module=_M_DER,
                          is_subtotal=True))
        for ii, item in enumerate(items, start=1):
            code = str(base + ii * 10)
            item_codes[item].append(code)
            v = float(cat.loc[cat["item"] == item, category].iloc[0])
            is_sec = "유가증권" in item
            L.append(FormLine(
                code, f"{category} · {item}", 2, "KRW", v,
                formula=("트레이딩 포지션(시장리스크 산출값)에 앵커 — 난수 아님"
                         if is_sec and category.startswith("당기손익") else
                         "트레이딩 포지션을 뺀 잔여 유가증권"
                         if is_sec and category.startswith("기타포괄") else
                         "원리금 수취 사업모형 — 전액 상각후원가"
                         if not is_sec and category.startswith("상각후") else
                         "해당 사업모형 없음") + tail,
                citation=_C1109, source_module=_M_DER))
    L += [
        FormLine("2000", "트레이딩 포지션 (참고)", 0, "KRW", pos,
                 formula="rwa_market_component.position 합 — FVTPL의 앵커",
                 citation="Basel III MAR10 트레이딩계정", source_module=_M_MKT),
        FormLine("2010", "파생상품 평가액 — 자산 (참고)", 0, "KRW", drv_a,
                 formula="mkt_trade.fo_value 양(+) 실측 합 — 대차대조표에 파생상품 "
                         "계정이 없어 기타자산에 섞여 있다. 본문에 넣으면 금융자산 "
                         "합계가 자산총계를 넘는다",
                 citation=_C1109, source_module=_M_MKT),
        FormLine("3000", "비금융자산 (기타자산)", 0, "KRW", other,
                 formula="자산총계 − 금융자산 합계 — 세부 원장이 없어 가르지 않았다"
                         + tail,
                 citation=_C99, source_module=_M_PRU),
        FormLine("3010", "자산총계", 0, "KRW", amt["자산총계"],
                 formula="pru_balance_sheet 자산총계", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        _remark(
            ("연결 자회사 원장이 없어 연결 = 단독이다(B2109·B2311과 같은 처리). "
             if consolidated else
             "종금계정 미영위(B2106)이므로 은행계정 금융자산과 같다. ")
            + "IFRS 9 범주 열이 원장에 없다. 현금성자산·대출채권은 원리금 수취 "
              "사업모형으로 보아 전액 상각후원가로, 유가증권은 트레이딩 포지션 "
              "산출값만큼을 당기손익-공정가치로, 나머지를 기타포괄손익-공정가치로 "
              "배분했다. 상수 비율을 박지 않았고 FVTPL은 산출값에 앵커된다.",
            _C1109),
    ]
    t = tol(amt["자산총계"])
    checks = [_sum_check("금융자산 합계 = 범주별 합", L, "1000",
                         tuple(cat_codes), t)]
    for ci, category in enumerate(ASSET_CATEGORIES, start=1):
        base = 1000 + ci * 100
        checks.append(_sum_check(f"{category} 소계 = 계정별 합", L, str(base),
                                 tuple(str(base + ii * 10)
                                       for ii in range(1, len(items) + 1)), t))
    # 계정별 가로합 — 범주 배분이 계정 잔액을 넘거나 모자라면 여기서 잡힌다.
    for item in items:
        checks.append(FormCheck(
            f"{item} 범주별 합 = 대차대조표 잔액", amt[item],
            sum(_val(L, c) for c in item_codes[item]), t))
    fvtpl_code = str(1000 + (ASSET_CATEGORIES.index("당기손익-공정가치 (FVTPL)")
                             + 1) * 100)
    checks += [
        _sum_check("금융자산 + 비금융자산 = 자산총계", L, "3010",
                   ("1000", "3000"), t),
        # 위 한 줄은 비금융자산을 잔차로 정의했으므로 항상 참이다 — 실제로
        # 대사해야 하는 것은 그 잔차가 대차대조표의 기타자산과 같은가다.
        # 금융자산 범위(FIN_ASSET_ITEMS)가 편제와 어긋나면 여기서만 잡힌다.
        FormCheck("비금융자산 = 대차대조표 기타자산", amt["기타자산"],
                  _val(L, "3000"), t),
        FormCheck("FVTPL ≤ 트레이딩 포지션", 0.0,
                  max(0.0, _val(L, fvtpl_code) - pos), t),
    ]
    return L, checks


def _b2121(ctx):
    """금융자산 범주별 분류정보(은행계정 및 종금계정, 총괄분, 말잔)."""
    return _asset_category_form(ctx, consolidated=False)


def _b2125(ctx):
    """금융자산 범주별 분류정보(연결, 일반목적 말잔)."""
    return _asset_category_form(ctx, consolidated=True)


# ---------------------------------------------------------------- B2122 / B2126

def _liab_category_form(ctx, *, consolidated: bool):
    """금융부채 범주별 분류 — 예수금·차입금·사채는 전부 상각후원가다."""
    cat = liability_categories(ctx)
    amt = bs_amounts(ctx)
    items = list(cat["item"])
    total = float(cat["balance"].sum())
    _, drv_l = derivative_values(ctx)
    scope = "연결" if consolidated else "은행계정 및 종금계정 총괄분"
    tail = f" · {_CONSOL}" if consolidated else ""
    L = [
        FormLine("100", "적용 범위", 0, "text", None,
                 text_value=(f"{scope} · 말잔 기준"
                             + (f" · {_CONSOL}" if consolidated else
                                " · 종금계정 미영위이므로 은행계정과 같다")),
                 citation=_C1109, source_module=_M_PRU),
        FormLine("1000", "금융부채 합계", 0, "KRW", total,
                 formula="예수금 + 차입금 + 사채 — 부채총계와 같다" + tail,
                 citation=_C1109, source_module=_M_PRU, is_subtotal=True),
    ]
    cat_codes, item_codes = [], {it: [] for it in items}
    for ci, category in enumerate(LIAB_CATEGORIES, start=1):
        base = 1000 + ci * 100
        cat_codes.append(str(base))
        L.append(FormLine(str(base), category, 1, "KRW",
                          float(cat[category].sum()),
                          formula="범주 열이 원장에 없어 상품 성격에서 배분" + tail,
                          citation=_C1109, source_module=_M_DER,
                          is_subtotal=True))
        for ii, item in enumerate(items, start=1):
            code = str(base + ii * 10)
            item_codes[item].append(code)
            L.append(FormLine(
                code, f"{category} · {item}", 2, "KRW",
                float(cat.loc[cat["item"] == item, category].iloc[0]),
                formula=("계약상 현금흐름 수취 목적 — 전액 상각후원가"
                         if category.startswith("상각후") else
                         "공정가치 지정 부채·파생상품부채 계정 없음") + tail,
                citation=_C1109, source_module=_M_DER))
    L += [
        FormLine("2000", "파생상품 평가액 — 부채 (참고)", 0, "KRW", drv_l,
                 formula="mkt_trade.fo_value 음(−) 실측 합의 절대값 — 대차대조표에 "
                         "파생상품 계정이 없어 본문에 넣지 않았다",
                 citation=_C1109, source_module=_M_MKT),
        FormLine("3000", "부채총계", 0, "KRW", amt["부채총계"],
                 formula="pru_balance_sheet 부채총계", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        _remark(
            ("연결 자회사 원장이 없어 연결 = 단독이다(B2109·B2311과 같은 처리). "
             if consolidated else
             "종금계정 미영위(B2106)이므로 은행계정 금융부채와 같다. ")
            + "조달 계정이 예수금·차입금·사채뿐이고 공정가치 지정 부채나 파생상품 "
              "부채 계정이 대차대조표에 없다. 따라서 금융부채 전액이 상각후원가이며 "
              "당기손익-공정가치는 0이다 — 미조회가 아니라 해당 계정 부존재다.",
            _C1109),
    ]
    t = tol(total)
    checks = [_sum_check("금융부채 합계 = 범주별 합", L, "1000",
                         tuple(cat_codes), t)]
    for ci, category in enumerate(LIAB_CATEGORIES, start=1):
        base = 1000 + ci * 100
        checks.append(_sum_check(f"{category} 소계 = 계정별 합", L, str(base),
                                 tuple(str(base + ii * 10)
                                       for ii in range(1, len(items) + 1)), t))
    for item in items:
        checks.append(FormCheck(
            f"{item} 범주별 합 = 대차대조표 잔액", amt[item],
            sum(_val(L, c) for c in item_codes[item]), t))
    checks.append(FormCheck("금융부채 합계 = 부채총계", amt["부채총계"],
                            _val(L, "1000"), t))
    return L, checks


def _b2122(ctx):
    """금융부채 범주별 분류정보(은행계정 및 종금계정, 총괄분, 말잔)."""
    return _liab_category_form(ctx, consolidated=False)


def _b2126(ctx):
    """금융부채 범주별 분류정보(연결, 일반목적 말잔)."""
    return _liab_category_form(ctx, consolidated=True)


# ---------------------------------------------------------------- B2127 / B2128

def _b2127(ctx):
    """국내 지역별 여신현황 — 잔액·건전성은 실측, 지역만 파생이다.

    가계 지역은 `forms_fss_retail_data.household`가 이미 만든 값을 그대로 쓴다.
    같은 개념을 여기서 다시 뽑으면 가계여신 서식과 지역분포가 갈린다.
    """
    rb = region_book(ctx)
    total = float(rb["balance"].sum())
    L = [
        FormLine("1000", "국내 여신잔액 합계", 0, "KRW", total,
                 formula=f"country={HOME_COUNTRY} 익스포저 {len(rb):,}건 실측 합 "
                         f"— 지역만 파생",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "국내 차주 수", 0, "count",
                 float(rb["obligor_id"].nunique()),
                 formula="국내 익스포저의 고유 차주 수 (실측)", citation=_C99,
                 source_module=_M_RDM),
    ]
    bal_codes, hh_codes, co_codes, npl_codes, ob_codes = [], [], [], [], []
    for ri, region in enumerate(REGIONS, start=1):
        base = 2000 + ri * 100
        sub = rb[rb["region"] == region]
        hh = float(sub.loc[sub["is_household"], "balance"].sum())
        co = float(sub.loc[~sub["is_household"], "balance"].sum())
        bal_codes.append(str(base))
        hh_codes.append(str(base + 10))
        co_codes.append(str(base + 20))
        npl_codes.append(str(base + 40))
        ob_codes.append(str(base + 30))
        L += [
            FormLine(str(base), f"{region} · 여신잔액", 1, "KRW", hh + co,
                     formula=f"{len(sub):,}건 — 잔액은 실측, 지역 귀속은 "
                             f"가계 재사용·비가계 {_DERIVED}",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), f"{region} · 가계여신", 2, "KRW", hh,
                     formula="지역은 forms_fss_retail_data.household 재사용",
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), f"{region} · 기업 등 여신", 2, "KRW", co,
                     formula=f"지역은 규모(log_assets) 가중 {_DERIVED}",
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 30), f"{region} · 차주 수", 2, "count",
                     float(sub["obligor_id"].nunique()),
                     formula="지역 내 고유 차주 수", citation=_C99,
                     source_module=_M_DER),
            FormLine(str(base + 40), f"{region} · 고정이하여신", 2, "KRW",
                     float(sub.loc[sub["npl"], "balance"].sum()),
                     formula="은행업감독규정 제27조 고정·회수의문·추정손실 실측 합",
                     citation="은행업감독규정 제27조 자산건전성 5단계 분류",
                     source_module=_M_RDM),
            FormLine(str(base + 50), f"{region} · 고정이하여신비율", 2, "ratio",
                     (float(sub.loc[sub["npl"], "balance"].sum()) / (hh + co)
                      if hh + co else 0.0),
                     formula="고정이하여신 ÷ 지역 여신잔액", citation=_C99,
                     source_module=_M_DER),
        ]
    npl_total = float(rb.loc[rb["npl"], "balance"].sum())
    L += [
        FormLine("3000", "가계여신 합계", 0, "KRW",
                 float(rb.loc[rb["is_household"], "balance"].sum()),
                 formula="지역 배분 전 실측 합", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "기업 등 여신 합계", 0, "KRW",
                 float(rb.loc[~rb["is_household"], "balance"].sum()),
                 formula="지역 배분 전 실측 합", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3020", "고정이하여신 합계", 0, "KRW", npl_total,
                 formula="지역 배분 전 실측 합",
                 citation="은행업감독규정 제27조 자산건전성 5단계 분류",
                 source_module=_M_RDM, is_subtotal=True),
        _remark("여신잔액·차주·건전성분류는 전부 실측이고 **지역 귀속만 파생**이다. "
                "가계 지역은 forms_fss_retail_data.household의 값을 그대로 재사용해 "
                "가계여신 서식과 지역분포가 갈리지 않게 했고, 기업·은행·국가 "
                "익스포저만 기준일 고정 시드로 뽑았다(규모가 클수록 수도권 가중). "
                "지역별 합계는 국내 여신잔액 실측과 정확히 일치한다.", _C99),
    ]
    t = tol(total)
    checks = [
        _sum_check("지역별 여신잔액 합 = 국내 여신잔액 합계", L, "1000",
                   tuple(bal_codes), t),
        _sum_check("지역별 가계여신 합 = 가계여신 합계", L, "3000",
                   tuple(hh_codes), t),
        _sum_check("지역별 기업 등 여신 합 = 기업 등 여신 합계", L, "3010",
                   tuple(co_codes), t),
        _sum_check("지역별 고정이하여신 합 = 고정이하여신 합계", L, "3020",
                   tuple(npl_codes), t),
        _sum_check("가계 + 기업 등 = 국내 여신잔액 합계", L, "1000",
                   ("3000", "3010"), t),
        # 지역 귀속은 익스포저 단위다. 한 차주가 두 지역에 걸치면 지역별 차주
        # 수가 중복계상되고 합이 국내 차주 수를 넘는다 — 금액만 대사하면 그
        # 중복이 서식에 남아도 아무도 못 본다.
        _sum_check("지역별 차주 수 합 = 국내 차주 수", L, "1010",
                   tuple(ob_codes), 1e-9),
    ]
    for ri, region in enumerate(REGIONS, start=1):
        base = 2000 + ri * 100
        checks.append(_sum_check(f"{region} 여신잔액 = 가계 + 기업 등", L,
                                 str(base), (str(base + 10), str(base + 20)), t))
        checks.append(_ratio_check(f"{region} 고정이하여신비율", L, str(base + 50),
                                   str(base + 40), str(base)))
    return L, checks


def _b2128(ctx):
    """국내 지역별 수신현황 — **수신 원장이 아예 없다.**

    예수금 계정별 총액(실측)에 국내분 배분비율을 곱하고, 개인은 가계 차주 수,
    법인은 기업여신 잔액의 지역분포로 가른다. 지역분포는 B2127과 같은 값을 쓴다.
    """
    dr = deposit_regions(ctx)
    amt = bs_amounts(ctx)
    w = domestic_share(ctx)
    # 예대율 분자는 B2127과 같은 지역별 여신잔액이어야 한다 — 여기서 다시
    # 파생하면 두 서식의 지역 개념이 갈린다.
    loan_by_region = region_book(ctx).groupby("region")["balance"].sum()
    retail_total = sum(amt[i] for i in RETAIL_DEPOSITS) * w
    corp_total = sum(amt[i] for i in CORP_DEPOSITS) * w
    total = retail_total + corp_total
    L = [
        FormLine("100", "국내분 배분비율", 0, "ratio", w,
                 formula="1 − 해외 EAD 비중 — B2102와 같은 비율",
                 citation=_C99, source_module=_M_DER),
        FormLine("1000", "국내 수신잔액 합계", 0, "KRW", total,
                 formula="예수금 4계정 총액(실측) × 국내분 배분비율",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "개인 예수금", 1, "KRW", retail_total,
                 formula=" + ".join(RETAIL_DEPOSITS) + " (실측) × 배분비율",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("1020", "법인 예수금", 1, "KRW", corp_total,
                 formula=" + ".join(CORP_DEPOSITS) + " (실측) × 배분비율",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
    ]
    sub_codes, retail_codes, corp_codes = [], [], []
    for ri, region in enumerate(REGIONS, start=1):
        base = 2000 + ri * 100
        r = dr[dr["region"] == region].iloc[0]
        rv, cv = float(r["retail"]), float(r["corporate"])
        sub_codes.append(str(base))
        retail_codes.append(str(base + 10))
        corp_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"{region} · 수신잔액", 1, "KRW", rv + cv,
                     formula="개인 + 법인 — 수신 원장 부재, 여신 지역분포로 배분",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), f"{region} · 개인 예수금", 2, "KRW", rv,
                     formula="개인 예수금 총액 × 지역별 가계 차주 수 비중 "
                             "— 총액은 실측, 지역 배분은 파생",
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), f"{region} · 법인 예수금", 2, "KRW", cv,
                     formula="법인 예수금 총액 × 지역별 기업여신 잔액 비중 "
                             "— 총액은 실측, 지역 배분은 파생",
                     citation=_C99, source_module=_M_DER),
            # 예대율 분자를 라인으로 세우지 않으면 비율에 FormCheck를 걸 수 없다
            # — 대사 없는 비율은 틀려도 서식 안에서 드러나지 않는다.
            FormLine(str(base + 30), f"{region} · 지역 여신잔액 (B2127)", 2,
                     "KRW", float(loan_by_region.get(region, 0.0)),
                     formula="B2127 지역별 여신잔액 — 같은 region_book을 쓴다",
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 40), f"{region} · 예대율", 2, "ratio",
                     (float(loan_by_region.get(region, 0.0)) / (rv + cv)
                      if rv + cv else 0.0),
                     formula="지역 여신잔액(B2127) ÷ 지역 수신잔액",
                     citation=_C_LDR, source_module=_M_DER),
        ]
    krw_ldr = ctx.tables["pru_liquidity_ratio"]
    ldr_row = krw_ldr[krw_ldr["metric"] == "원화예대율"]
    L += [
        FormLine("3000", "예수금 총액 (총괄분, B2101)", 0, "KRW",
                 sum(amt[i] for i in RETAIL_DEPOSITS + CORP_DEPOSITS),
                 formula="pru_balance_sheet 예수금 4계정 합 — 국내분의 앵커",
                 citation=_C99, source_module=_M_PRU),
        FormLine("3010", "국내 여신잔액 합계 (B2127)", 0, "KRW",
                 float(loan_by_region.sum()),
                 formula="B2127 국내 여신잔액 합계 — 예대율의 분자",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("3020", "국내 예대율", 0, "ratio",
                 float(loan_by_region.sum()) / total if total else 0.0,
                 formula="국내 여신잔액 ÷ 국내 수신잔액 — BR-24 원화예대율과 "
                         "같은 값이어야 한다(여·수신에 같은 배분비율을 곱하므로 "
                         "비율은 배분에 불변)",
                 citation=_C_LDR, source_module=_M_DER),
        _remark("수신(예수금) 원장이 이 저장소에 아예 없다 — 차주별 예금계좌·지역·"
                "상품 어느 것도 원천 데이터에 없다. 그래서 대차대조표의 예수금 "
                "4계정 총액(실측)에 국내분 배분비율(B2102와 같은 값)을 곱한 뒤, "
                "개인은 가계 차주 수, 법인은 기업여신 잔액의 지역분포로 갈랐다. "
                "지역분포는 B2127과 같은 region_book에서 나오므로 여신과 수신이 "
                "서로 다른 지역 개념을 쓰지 않는다. 차입금·사채는 지역 귀속 근거가 "
                "없어 수신 범위에서 제외했다. 예대율은 여·수신에 같은 배분비율을 "
                "곱하므로 배분에 불변이며, 국내 예대율이 BR-24 원화예대율과 같은 "
                "값인지 서식 안에서 대사한다.", _C99),
    ]
    t = tol(total)
    checks = [
        _sum_check("지역별 수신잔액 합 = 국내 수신잔액 합계", L, "1000",
                   tuple(sub_codes), t),
        _sum_check("지역별 개인 예수금 합 = 개인 예수금", L, "1010",
                   tuple(retail_codes), t),
        _sum_check("지역별 법인 예수금 합 = 법인 예수금", L, "1020",
                   tuple(corp_codes), t),
        _sum_check("개인 + 법인 = 국내 수신잔액 합계", L, "1000",
                   ("1010", "1020"), t),
        FormCheck("국내 수신잔액 = 예수금 총액 × 배분비율",
                  _val(L, "3000") * w, _val(L, "1000"), t),
        _ratio_check("국내 예대율", L, "3020", "3010", "1000"),
    ]
    if len(ldr_row):
        # 예대율이라는 같은 개념이 BR-24(원화예대율)와 이 서식에서 다른 값을
        # 가지면 안 된다. 여신·수신에 같은 국내분 배분비율을 곱하므로 비율은
        # 배분에 불변이고, 어긋난다면 두 곳의 예수금 정의가 갈린 것이다.
        checks.append(FormCheck("국내 예대율 = 원화예대율 (BR-24)",
                                float(ldr_row["value"].iloc[0]),
                                _val(L, "3020"), 1e-6))
    for ri, region in enumerate(REGIONS, start=1):
        base = 2000 + ri * 100
        checks.append(_sum_check(f"{region} 수신잔액 = 개인 + 법인", L, str(base),
                                 (str(base + 10), str(base + 20)), t))
        checks.append(_ratio_check(f"{region} 예대율", L, str(base + 40),
                                   str(base + 30), str(base)))
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2102": (_C99 + " · " + _C_BANK_FS, "PRD-RDM", _b2102),
    "B2103": (_C99 + " · " + _C_BANK_FS, "PRD-RDM", _b2103),
    "B2104": (_C_TRUST, "PRD-RDM", _b2104),
    "B2105": (_C_TRUST, "PRD-RDM", _b2105),
    "B2106": (_C_MERCH, "PRD-RDM", _b2106),
    "B2107": (_C_MERCH, "PRD-RDM", _b2107),
    "B2109": (_C1110 + " · " + _C26, "PRD-RDM", _b2109),
    "B2111": (_C99 + " · K-IFRS 제1001호 재무제표 표시", "PRD-RDM", _b2111),
    "B2112": (_C99 + " · K-IFRS 제1001호 재무제표 표시", "PRD-RDM", _b2112),
    "B2113": (_C_TRUST, "PRD-RDM", _b2113),
    "B2114": (_C_TRUST, "PRD-RDM", _b2114),
    "B2115": (_C_MERCH, "PRD-RDM", _b2115),
    "B2116": (_C_MERCH, "PRD-RDM", _b2116),
    "B2118": (_C1110 + " · " + _C99, "PRD-RDM", _b2118),
    "B2119": (_C_CARD + " · " + _C_CARD_ALW, "PRD-RDM", _b2119),
    "B2121": (_C1109, "PRD-RDM", _b2121),
    "B2122": (_C1109, "PRD-RDM", _b2122),
    "B2125": (_C1109 + " · " + _C1110, "PRD-RDM", _b2125),
    "B2126": (_C1109 + " · " + _C1110, "PRD-RDM", _b2126),
    "B2127": (_C99 + " · 은행업감독규정 제27조 자산건전성 분류", "PRD-RDM", _b2127),
    "B2128": (_C99 + " · " + _C_LDR, "PRD-RDM", _b2128),
}
