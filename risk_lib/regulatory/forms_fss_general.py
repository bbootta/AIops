"""금감원 FINES 업무보고서 — 일반현황·집합투자증권 판매·휴면금융재산 등 30건.

편제가 넓어 근거 법령이 서식마다 다르다. 은행업감독규정 조문을 아무 데나 달지
않는 것이 이 그룹의 핵심이다 — 전자금융(B1110~B1112)은 전자금융거래법, 집합투자증권
판매(B81xx)와 투자자문업(B111xx·B12101)은 자본시장법, 휴면금융재산(B91xx)은
서민의 금융생활 지원에 관한 법률, 금리인하요구권(B10101)은 은행법 제30조의2다.
조문 번호가 확실하지 않은 곳(업무위수탁·정보처리위탁)은 **법령 단위로 낮춰**
달았다. 틀린 조문은 조문이 없는 것보다 나쁘다.

**이 그룹은 파생 비중이 가장 높다.** 인사·점포·기기·전자금융·펀드판매·휴면예금
원장이 이 저장소에 없기 때문이다. 파생을 숨기지 않기 위해 파생 함수는 전부
`forms_fss_general_data`에 모았고 무엇을 어떻게 파생했는지는 그 모듈 docstring에
열거했다. 파생값이 들어간 라인은 **그 라인 자체의** formula에 그 사실을 남긴다 —
상위 소계에만 적어 두면 서식이 flat table로 실체화될 때 하위 셀이 실측으로 읽힌다.

**앵커** — 파생이라고 총계까지 지어내지는 않는다.
  휴면예금·미거래예금   개인 예수금(`pru_balance_sheet` 실측) × 파생 휴면율.
  휴면 자기앞수표       법인 결제성 예수금(실측) × 파생 발행·휴면율.
  집합투자증권 판매잔액  예수금 총액(실측) × 파생 판매비중. 수익자 구분의
                       개인·법인 비중은 개인·법인 예수금 **실측** 비중이다.
  전자금융 개인 고객수   개인 예수금(실측) ÷ 파생 1인당 예금. 법인 고객수는
                       `rdm_obligor` 실측 차주 수다.
  비대면 대출(B1112)    **금액·건수가 전부 실측**이다. 익스포저마다 취급채널
                       라벨만 파생이라 채널별 합계가 자동으로 실측 총액이 된다.
  금리인하요구권(B10101) 대상 여신이 실제 포트폴리오다. 신청·수용 여부와 인하폭만
                       파생이므로 "대상 ≥ 신청 ≥ 수용"이 서식 안에서 성립한다.

**다른 그룹과 같은 값을 쓴다.** 임직원 수는 `forms_fss_keyfin_data.headcount`,
국내 점포 수는 같은 모듈의 `domestic_branches`, 해외 점포는
`forms_fss_overseas_data.branch_master`를 그대로 읽는다. B1101이 B2701(생산성)과
다른 임직원 수를 쓰면 제출본이 성립하지 않는다. B1107의 권역 비중은
`forms_fss_retail_data.household`의 지역분포이므로 B2426 계열과 갈리지 않는다.

**미영위로 0을 적은 것 — 투자자문업(B11101~B11107·B12101) 8건.**
`forms_fss_general_data.ADVISORY_LICENSED = False`이며 판단 근거는 그 상수 주석에
있다. 없는 영업을 파생으로 만들어 내는 것이 가장 나쁘므로 0으로 두고 사유를
라인마다 남긴다. 0은 "미조회"가 아니라 "해당 영업 없음"이다. 집합투자증권
판매(B81xx)는 미영위가 아니다 — 판매 **원장**이 없을 뿐이다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_general_data import (
    ADVISORY_LICENSED, ADVISORY_REASON, ATM_KINDS, EBANK_LOAN_CHANNELS, RANKS,
    REGION_SIDO, ancillary_business, atm, cashier_checks, corporate_deposits,
    domestic_branches, dormant_deposits, ebank_loan_book, ebank_registered,
    ebank_subscribers, ebank_transactions, fund_investors, fund_sales,
    inactive_deposits, it_outsourcing, org_units, outsourcing,
    rate_cut_requests, region_branches, retail_customers, retail_deposits,
    staff,
)
from risk_lib.regulatory.forms_fss_financial_data import bs_amounts, tol
from risk_lib.regulatory.forms_fss_retail_data import REGIONS

_M_DER = "risk_lib.regulatory.forms_fss_general_data"
_M_KEY = "risk_lib.regulatory.forms_fss_keyfin_data"
_M_OVS = "risk_lib.regulatory.forms_fss_overseas_data"
_M_PRU = "risk_lib.prudential.financials"
_M_RDM = "risk_lib.datamodel.materialize_detail"
# 미영위 항목에는 산출 모듈이 없다. 빈 문자열은 "못 채웠다"로 읽힌다.
_M_NONE = "해당 영업 미영위 — 산출 모듈 없음"

_C99 = "은행업감독규정 제99조 업무보고서"
_C_BR = "은행법 제13조 — 지점의 신설 등"
_C_ANC = "은행법 제27조의2 — 부수업무"
_C_CON = "은행법 제28조 — 겸영업무"
# 전자금융은 전자금융거래법 소관이다. 은행업감독규정 조문을 달면 안 된다.
_C_EFT = "전자금융거래법 제2조 — 전자금융거래·전자적 장치"
# 업무위탁 보고의 조문 번호를 확신할 수 없어 고시 단위로 낮춰 단다.
_C_OUT = "금융기관의 업무위탁 등에 관한 규정(금융위원회 고시) — 업무위탁 보고"
_C_ITO = ("전자금융감독규정 — 정보처리 업무위탁 · "
          "금융기관의 업무위탁 등에 관한 규정(금융위원회 고시)")
_C_FUND = ("자본시장과 금융투자업에 관한 법률 — 집합투자증권의 판매(투자중개업) · "
           "은행법 제28조 겸영업무")
_C_ADV = "자본시장과 금융투자업에 관한 법률 — 투자자문업 등록 및 영업행위 규제"
_C_ROBO = ("자본시장과 금융투자업에 관한 법률 — 전자적 투자조언장치 "
           "(투자자문업 영위를 전제로 한다)")
_C_DORM = ("서민의 금융생활 지원에 관한 법률 — 휴면예금 관리·지급 · "
           "상법 제64조 상사소멸시효")
_C_RATE = "은행법 제30조의2 — 금리인하 요구"

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
_ANCHOR = "합계는 재무상태표 예수금(실측) 앵커 · 배분만 파생"
_NA = "해당 영업 미영위 — 파생하지 않고 0으로 적는다"


def _remark(text: str, citation: str) -> FormLine:
    return FormLine("9000", "비고", 0, "text", None, text_value=text,
                    citation=citation)


def _not_operating(items: tuple[tuple[str, str, int, str], ...],
                   citation: str, note: str
                   ) -> tuple[list[FormLine], list[FormCheck]]:
    """투자자문업 미영위 서식의 공통 몸통 — 항목을 0으로 적고 사유를 남긴다.

    여덟 서식이 같은 판단 하나(`ADVISORY_LICENSED`)를 보므로 몸통도 한 곳에 둔다.
    상수가 뒤집히면 서식을 다시 저작해야 하니 조용히 0을 적지 않고 멈춘다.
    """
    if ADVISORY_LICENSED:
        raise NotImplementedError(
            "투자자문업을 영위하면 B11101~B11107·B12101을 다시 저작해야 한다")
    L = [FormLine(code, name, level, unit, 0.0, formula=_NA,
                  citation=citation, source_module=_M_NONE)
         for code, name, level, unit in items]
    L.append(_remark(note, citation))
    return L, [FormCheck("미영위 — 전 항목 0", 0.0,
                         sum(float(x.value or 0.0) for x in L), 1e-9)]


def _band_range_check(name: str, bands) -> FormCheck:
    """구간 평균잔액이 자기 금액구간 안에 있는가 — 이탈 구간 수가 0이어야 한다.

    `_amount_bands`는 계좌수를 먼저 배분하고 금액을 구간 대표금액으로 만들어
    "어느 구간도 자기 금액구간을 벗어나지 않는다"를 **설계로** 보장한다. 그런데
    그 주장을 라인 formula에 적어 두기만 하고 대사하지 않으면, 배분 방식이나
    대표금액 어휘가 바뀌어 "1만원 이하 구간의 평균잔액이 8만원"이 되어도 서식은
    아무 말도 하지 않는다. 계좌수가 0인 구간은 평균이 정의되지 않아 건너뛴다.
    """
    bad = 0
    for _, r in bands.iterrows():
        n = float(r["n_account"])
        if not n:
            continue
        avg = float(r["amount"]) / n
        if not float(r["lower"]) < avg <= float(r["upper"]):
            bad += 1
    return FormCheck(name, 0.0, float(bad), 1e-9)


# ---------------------------------------------------------------- B1101

def _b1101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """인원현황 — 총원은 B2701(생산성)과 **같은** headcount이고 구성만 파생이다."""
    s = staff(ctx)
    assets = bs_amounts(ctx)["자산총계"]
    L = [
        FormLine("1000", "임직원 수 계", 0, "count", s["total"],
                 formula=f"총자산 ÷ 1인당 총자산 · {_DERIVED} — B2701과 같은 값",
                 citation=_C99, source_module=_M_KEY, is_subtotal=True),
        FormLine("1010", "임원", 1, "count", s["officer"], formula=_DERIVED,
                 citation=_C99, source_module=_M_KEY),
        FormLine("1020", "정규직 직원", 1, "count", s["regular"],
                 formula=f"임직원 수 − 임원 − 기간제 · {_DERIVED}",
                 citation=_C99, source_module=_M_KEY),
        FormLine("1030", "기간제·단시간 직원", 1, "count", s["temporary"],
                 formula=_DERIVED, citation=_C99, source_module=_M_KEY),
        FormLine("1100", "남자", 1, "count", s["male"],
                 formula=f"임직원 수 − 여자 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("1110", "여자", 1, "count", s["female"],
                 formula=f"임직원 수 × 파생 여성비중 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("2000", "직급별 계 (임원 제외)", 0, "count",
                 s["total"] - s["officer"], formula="임직원 수 − 임원",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
    ]
    rank_codes = []
    for i, r in enumerate(RANKS, start=1):
        code = f"20{i:02d}"
        rank_codes.append(code)
        L.append(FormLine(code, r, 1, "count", float(s["ranks"][r]),
                          formula=f"직급 구성비 파생 후 잔여 배분 · {_DERIVED}",
                          citation=_C99, source_module=_M_DER))
    L += [
        FormLine("3000", "분기 중 신규채용", 0, "count", s["hired"],
                 formula=f"임직원 수 × 파생 채용률 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("3010", "분기 중 퇴직", 0, "count", s["left"],
                 formula=f"임직원 수 × 파생 퇴직률 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("4000", "평균 근속연수", 0, "count", s["tenure_years"],
                 formula=f"인사 원장 부재 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("4010", "평균 연령", 0, "count", s["avg_age"],
                 formula=f"인사 원장 부재 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("5000", "1인당 총자산", 0, "KRW", assets / s["total"],
                 formula="자산총계 ÷ 임직원 수 — B2701과 같은 값", citation=_C99,
                 source_module=_M_KEY),
        FormLine("5010", "자산총계 (참고)", 1, "KRW", assets,
                 formula="재무상태표 실측", citation=_C99, source_module=_M_PRU),
        _remark("인사 원장이 없어 임직원 수를 총자산에서 역산했다. 총원은 "
                "forms_fss_keyfin_data.headcount 그대로이므로 B2701(생산성)·"
                "B5103(자지점)과 같은 값이다. 성별·직급·채용·퇴직·근속·연령은 "
                "구성만 파생이며 합계가 언제나 총원이 되도록 잔여로 맞췄다.", _C99),
    ]
    checks = [
        _sum_check("임직원 수 = 임원 + 정규직 + 기간제", L, "1000",
                   ("1010", "1020", "1030"), 1e-9),
        _sum_check("임직원 수 = 남자 + 여자", L, "1000", ("1100", "1110"), 1e-9),
        _sum_check("직급별 계 = 직급 구성 합", L, "2000", tuple(rank_codes), 1e-9),
        FormCheck("임직원 수 = 임원 + 직급별 계", s["total"],
                  _val(L, "1010") + _val(L, "2000"), 1e-9),
        _ratio_check("1인당 총자산 = 자산총계 ÷ 임직원 수", L, "5000", "5010",
                     "1000", 1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B1104

def _b1104(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """기구현황 — 국내 점포는 B5103과 같은 파생, 해외는 BF101과 같은 마스터다."""
    o = org_units(ctx)
    L = [
        FormLine("1000", "국내 점포 계", 0, "count", o["domestic_total"],
                 formula=f"임직원 수 ÷ 점포당 임직원 · {_DERIVED} — B5103과 같은 값",
                 citation=_C_BR, source_module=_M_KEY, is_subtotal=True),
        FormLine("1010", "본점", 1, "count", o["head_office"],
                 formula="본점은 언제나 1개다", citation=_C_BR,
                 source_module=_M_KEY),
        FormLine("1020", "지점", 1, "count", o["branch"],
                 formula=f"국내 점포 계 − 본점 · {_DERIVED}", citation=_C_BR,
                 source_module=_M_KEY),
        FormLine("1030", "출장소 (참고 — 점포 계에 포함하지 않음)", 1, "count",
                 o["sub_office"],
                 formula=f"국내 점포 수 × 파생비율 · {_DERIVED} — B5103과 같은 값",
                 citation=_C_BR, source_module=_M_KEY),
        FormLine("2000", "본점 내부기구 계", 0, "count",
                 o["hq_group"] + o["hq_dept"], formula="사업그룹 + 부서",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "사업그룹(본부)", 1, "count", o["hq_group"],
                 formula=f"본점 기구 원장 부재 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("2020", "부서", 1, "count", o["hq_dept"],
                 formula=f"본점 기구 원장 부재 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER),
        FormLine("3000", "해외 점포 계", 0, "count", o["ov_total"],
                 formula="해외점포 마스터 행 수 — BF101·B5103과 같은 마스터",
                 citation="은행법 제13조 제2항 — 국외 지점 설치",
                 source_module=_M_OVS, is_subtotal=True),
        FormLine("3010", "해외 지점", 1, "count", o["ov_branch"],
                 formula="해외점포 마스터에서 형태='지점' 행 수 — BF101과 같은 값",
                 citation=_C_BR, source_module=_M_OVS),
        FormLine("3020", "해외 현지법인", 1, "count", o["ov_subsidiary"],
                 formula="해외점포 마스터에서 형태='현지법인' 행 수 — BF101과 같은 값",
                 citation=_C_BR, source_module=_M_OVS),
        FormLine("3030", "해외 사무소", 1, "count", o["ov_rep"],
                 formula="해외점포 마스터에서 형태='사무소' 행 수 — BF101과 같은 값",
                 citation=_C_BR, source_module=_M_OVS),
        FormLine("4000", "총 점포 계 (국내 + 해외)", 0, "count",
                 o["domestic_total"] + o["ov_total"],
                 formula="국내 점포 계 + 해외 점포 계", citation=_C_BR,
                 source_module=_M_DER, is_subtotal=True),
        _remark("점포 원장이 없어 국내 점포 수를 임직원 수에서 역산했다 — "
                "forms_fss_keyfin_data.domestic_branches 그대로이므로 B5103·B2701과 "
                "같은 값이다. 본점 사업그룹·부서 수만 이 서식에서 새로 파생했다. "
                "해외 점포는 파생하지 않고 forms_fss_overseas_data.branch_master를 "
                "읽으므로 BF101 계열과 갈리지 않는다.", _C_BR),
    ]
    checks = [
        _sum_check("국내 점포 계 = 본점 + 지점", L, "1000", ("1010", "1020"), 1e-9),
        _sum_check("본점 내부기구 계 = 사업그룹 + 부서", L, "2000",
                   ("2010", "2020"), 1e-9),
        _sum_check("해외 점포 계 = 지점 + 현지법인 + 사무소", L, "3000",
                   ("3010", "3020", "3030"), 1e-9),
        _sum_check("총 점포 계 = 국내 + 해외", L, "4000", ("1000", "3000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B1105

def _b1105(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """무인자동화기기 설치현황 — 기기 원장이 없어 점포 수에서 파생한다."""
    a = atm(ctx)
    branches = domestic_branches(ctx)["total"]
    L = [
        FormLine("1000", "설치대수 계", 0, "count", a["total"],
                 formula=f"국내 점포 수 × 점포당 기기 수 · {_DERIVED}",
                 citation=_C_EFT, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "점내 설치", 1, "count", a["inside"],
                 formula=f"설치대수 계 − 점외 · {_DERIVED}", citation=_C_EFT,
                 source_module=_M_DER),
        FormLine("1020", "점외 설치", 1, "count", a["outside"],
                 formula=f"설치대수 계 × 파생 점외비중 · {_DERIVED}",
                 citation=_C_EFT, source_module=_M_DER),
        FormLine("2000", "기기유형별 계", 0, "count", a["total"],
                 formula="유형 배분 합 — 설치대수 계와 같아야 한다",
                 citation=_C_EFT, source_module=_M_DER, is_subtotal=True),
    ]
    kind_codes = []
    for i, k in enumerate(ATM_KINDS, start=1):
        code = f"20{i:02d}"
        kind_codes.append(code)
        L.append(FormLine(code, k, 1, "count", float(a["kinds"][k]),
                          formula=f"유형 구성비 파생 후 최대잔여법 배분 · {_DERIVED}",
                          citation=_C_EFT, source_module=_M_DER))
    L += [
        FormLine("3000", "국내 점포 수 (참고)", 0, "count", branches,
                 formula=f"{_DERIVED} — B5103과 같은 값", citation=_C_BR,
                 source_module=_M_KEY),
        FormLine("3010", "점포당 설치대수", 0, "count", a["total"] / branches,
                 formula="설치대수 계 ÷ 국내 점포 수", citation=_C99,
                 source_module=_M_DER),
        FormLine("4000", "공동망 제휴기기 (자행 설치분 아님 — 계에서 제외)", 0,
                 "count", a["shared_network"],
                 formula=f"설치대수 계 × 파생비율 · {_DERIVED}", citation=_C_EFT,
                 source_module=_M_DER),
        _remark("기기 원장이 없어 점포 수에서 파생했다. 공동망 제휴기기는 자행 "
                "설치분이 아니므로 설치대수 계에 넣지 않는다 — 넣으면 점포당 "
                "설치대수가 자행 설치 수준을 과대표시한다.", _C_EFT),
    ]
    checks = [
        _sum_check("설치대수 계 = 점내 + 점외", L, "1000", ("1010", "1020"), 1e-9),
        _sum_check("기기유형별 계 = 유형 합", L, "2000", tuple(kind_codes), 1e-9),
        FormCheck("기기유형별 계 = 설치대수 계", _val(L, "1000"), _val(L, "2000"),
                  1e-9),
        _ratio_check("점포당 설치대수 = 설치대수 ÷ 점포 수", L, "3010", "1000",
                     "3000", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B1107

def _b1107(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """국내지역별 점포 — 권역 비중은 가계 차주 실측 분포, 시·도 배분만 파생이다."""
    rb = region_branches(ctx)
    total = domestic_branches(ctx)["total"]
    L = [
        FormLine("1000", "국내 점포 계", 0, "count", total,
                 formula=f"{_DERIVED} — B1104·B5103과 같은 값", citation=_C_BR,
                 source_module=_M_KEY, is_subtotal=True),
    ]
    region_codes = []
    for i, region in enumerate(REGIONS, start=1):
        sub = rb[rb["region"] == region]
        base = 2000 + i * 100
        region_codes.append(str(base))
        L.append(FormLine(
            str(base), f"권역 · {region}", 1, "count",
            float(sub["n_branch"].sum()),
            formula=("가계 차주 지역분포(B2426 계열과 같은 분포) 비중 "
                     f"{float(sub['region_share'].iloc[0]):.1%} × 국내 점포 수"),
            citation=_C_BR, source_module=_M_DER, is_subtotal=True))
        sido_codes = []
        for j, (_, r) in enumerate(sub.iterrows(), start=1):
            code = str(base + j)
            sido_codes.append(code)
            L.append(FormLine(code, str(r["sido"]), 2, "count",
                              float(r["n_branch"]),
                              formula=f"권역 내 시·도 배분 · {_DERIVED}",
                              citation=_C_BR, source_module=_M_DER))
        L.append(FormLine(f"{base + 90}", f"{region} 점포 비중", 2, "ratio",
                          float(sub["n_branch"].sum()) / total,
                          formula="권역 점포 수 ÷ 국내 점포 수", citation=_C99,
                          source_module=_M_DER))
    L.append(_remark(
        "권역(수도권·광역시·기타 지방) 비중은 새로 뽑지 않고 "
        "forms_fss_retail_data.household의 가계 차주 지역분포를 쓴다 — B2127·B2426 "
        "계열과 같은 분포다. 권역 안의 시·도 배분만 파생이며 최대잔여법 정수 배분이라 "
        "시·도 합이 반드시 국내 점포 수가 된다.", _C_BR))
    checks = [_sum_check("권역별 합 = 국내 점포 계", L, "1000",
                         tuple(region_codes), 1e-9)]
    for i, region in enumerate(REGIONS, start=1):
        base = 2000 + i * 100
        n_sido = len(REGION_SIDO[region])
        checks.append(_sum_check(
            f"{region} = 시·도 합", L, str(base),
            tuple(str(base + j) for j in range(1, n_sido + 1)), 1e-9))
        checks.append(_ratio_check(f"{region} 점포 비중", L, str(base + 90),
                                   str(base), "1000", 1e-12))
    return L, checks


# ---------------------------------------------------------------- B1108

def _b1108(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """부수업무 및 겸영업무 현황 — 영위 여부를 원장·산출의 흔적으로 판정한다."""
    ab = ancillary_business(ctx)
    anc = ab[ab["kind"] == "부수업무"]
    con = ab[ab["kind"] == "겸영업무"]
    L = [
        FormLine("1000", "영위 업무 수 계", 0, "count",
                 float(int(ab["operating"].sum())),
                 formula="부수업무 + 겸영업무 영위 건수",
                 citation=f"{_C_ANC} · {_C_CON}", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1100", "부수업무 영위 수", 1, "count",
                 float(int(anc["operating"].sum())),
                 formula=f"부수업무 {len(anc)}개 중 영위 판정 건수",
                 citation=_C_ANC, source_module=_M_DER, is_subtotal=True),
        FormLine("1200", "겸영업무 영위 수", 1, "count",
                 float(int(con["operating"].sum())),
                 formula=f"겸영업무 {len(con)}개 중 영위 판정 건수",
                 citation=_C_CON, source_module=_M_DER, is_subtotal=True),
    ]
    anc_codes, con_codes = [], []
    for i, (_, r) in enumerate(ab.iterrows(), start=1):
        base = 2000 if r["kind"] == "부수업무" else 3000
        code = str(base + i * 10)
        (anc_codes if r["kind"] == "부수업무" else con_codes).append(code)
        L.append(FormLine(
            code, f"{r['kind']} · {r['item']}", 1, "count",
            1.0 if r["operating"] else 0.0,
            formula=("영위 = 1 · 미영위 = 0 — 판정근거: " + str(r["basis"])),
            citation=_C_ANC if r["kind"] == "부수업무" else _C_CON,
            source_module=_M_DER if r["operating"] else _M_NONE))
    L.append(_remark(
        "영위 여부는 이 산출체계의 원장·산출에 그 업무의 흔적이 있는지로 판정했다 "
        "(예: 신탁 계정과목 없음 → 신탁업 미영위, 부외 익스포저에 직접적 신용대체 "
        "있음 → 지급보증 영위). 판정근거는 **[원장]·[편제]·[파생]으로 층위를 "
        "구분**했다 — [원장]만 실제 원장을 대조한 판정이고, [편제]는 이 저장소가 "
        "그 서식을 제출대상으로 편제했다는 사실, [파생]은 판정 대상 수치 자체가 "
        "파생이라 원장 대조가 아니라는 뜻이다. 업무 마스터가 없어 흔적이 없는 "
        "업무는 미영위로 적었으므로, 실제 제출 시에는 업무 마스터로 대체해야 한다. "
        "취급규모는 별도 원장이 없어 이 서식에서는 영위 여부만 보고하며 "
        "집합투자증권 판매 규모는 B8101이 적는다.",
        f"{_C_ANC} · {_C_CON}"))
    checks = [
        _sum_check("영위 업무 수 = 부수 + 겸영", L, "1000", ("1100", "1200"), 1e-9),
        _sum_check("부수업무 영위 수 = 부수업무 항목 합", L, "1100",
                   tuple(anc_codes), 1e-9),
        _sum_check("겸영업무 영위 수 = 겸영업무 항목 합", L, "1200",
                   tuple(con_codes), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B1110

def _b1110(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """전자금융서비스 가입자수 — 개인 고객 수는 개인 예수금(실측)에서 역산한다."""
    sub = ebank_subscribers(ctx)
    reg = ebank_registered(ctx)
    cust = retail_customers(ctx)
    L = [
        FormLine("1000", "전자금융 등록고객 수 (중복 제외)", 0, "count",
                 reg["total"],
                 formula=f"채널 최댓값 × 파생 여유배수 · {_DERIVED}",
                 citation=_C_EFT, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "개인", 1, "count", reg["individual"],
                 formula=_DERIVED, citation=_C_EFT, source_module=_M_DER),
        FormLine("1020", "법인", 1, "count", reg["corporate"],
                 formula=_DERIVED, citation=_C_EFT, source_module=_M_DER),
    ]
    ch_codes = []
    for i, (_, r) in enumerate(sub.iterrows(), start=1):
        base = 2000 + i * 100
        ch_codes.append(str(base))
        L += [
            FormLine(str(base), f"채널 · {r['channel']} 가입자 수", 1, "count",
                     float(r["total"]),
                     formula=f"고객 수 × 파생 침투율 · {_DERIVED} (채널 간 중복 포함)",
                     citation=_C_EFT, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "개인", 2, "count", float(r["individual"]),
                     formula=_DERIVED, citation=_C_EFT, source_module=_M_DER),
            FormLine(str(base + 20), "법인", 2, "count", float(r["corporate"]),
                     formula=_DERIVED, citation=_C_EFT, source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "개인 고객 수 (모수)", 0, "count", cust["individual"],
                 formula=f"개인 예수금(실측) ÷ 파생 1인당 예금 · {_ANCHOR}",
                 citation=_C99, source_module=_M_DER),
        FormLine("3010", "법인 고객 수 (모수)", 0, "count", cust["corporate"],
                 formula="rdm_obligor 기업·은행·국가 차주 수 — 실측",
                 citation=_C99, source_module=_M_RDM),
        FormLine("4000", "개인 고객 전자금융 이용률", 0, "ratio",
                 reg["individual"] / cust["individual"],
                 formula="개인 등록고객 ÷ 개인 고객 수", citation=_C_EFT,
                 source_module=_M_DER),
        _remark("전자금융 가입자 원장이 없다. 개인 고객 수는 개인 예수금(실측)을 "
                "파생 1인당 예금잔액으로 나눠 역산했고 법인 고객 수는 rdm_obligor "
                "차주 수 실측이다. 채널 가입은 중복되므로 채널 합계는 고객 수를 넘을 "
                "수 있으며, 중복을 제외한 등록고객 수를 따로 두어 어느 채널도 "
                "등록고객을 넘지 않게 했다.", _C_EFT),
    ]
    checks = [
        _sum_check("등록고객 수 = 개인 + 법인", L, "1000", ("1010", "1020"), 1e-9),
        _ratio_check("개인 이용률 = 개인 등록고객 ÷ 개인 고객 수", L, "4000",
                     "1010", "3000", 1e-12),
        FormCheck("등록고객 수 ≤ 고객 수 (개인)", 0.0,
                  max(0.0, reg["individual"] - cust["individual"]), 1e-9),
        FormCheck("채널 최대 가입자 ≤ 등록고객 수", 0.0,
                  max(0.0, float(sub["total"].max()) - reg["total"]), 1e-9),
    ]
    for i, (_, r) in enumerate(sub.iterrows(), start=1):
        base = 2000 + i * 100
        checks.append(_sum_check(f"{r['channel']} = 개인 + 법인", L, str(base),
                                 (str(base + 10), str(base + 20)), 1e-9))
    return L, checks


# ---------------------------------------------------------------- B1111

def _b1111(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """전자금융경로를 이용한 거래 — 거래 원장이 없어 가입자에서 파생한다."""
    tx = ebank_transactions(ctx)
    n_total = float(tx["n_txn"].sum())
    amt_total = float(tx["amount"].sum())
    L = [
        FormLine("1000", "거래건수 계", 0, "count", n_total,
                 formula=f"채널 가입자 × 파생 1인당 거래횟수 · {_DERIVED}",
                 citation=_C_EFT, source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "거래금액 계", 0, "KRW", amt_total,
                 formula=f"거래건수 × 파생 건당 금액 · {_DERIVED}",
                 citation=_C_EFT, source_module=_M_DER, is_subtotal=True),
    ]
    n_codes, a_codes = [], []
    for i, (_, r) in enumerate(tx.iterrows(), start=1):
        nc, ac = f"10{i:02d}", f"20{i:02d}"
        n_codes.append(nc)
        a_codes.append(ac)
        L.append(FormLine(nc, f"거래건수 · {r['channel']}", 1, "count",
                          float(r["n_txn"]),
                          formula=(f"가입자 × 분기 {float(r['per_user']):.1f}회 · "
                                   f"{_DERIVED}"),
                          citation=_C_EFT, source_module=_M_DER))
        L.append(FormLine(ac, f"거래금액 · {r['channel']}", 1, "KRW",
                          float(r["amount"]),
                          formula=(f"건수 × 건당 {float(r['per_txn']):,.0f}원 · "
                                   f"{_DERIVED}"),
                          citation=_C_EFT, source_module=_M_DER))
    L += [
        FormLine("3000", "건당 평균 거래금액", 0, "KRW", amt_total / n_total,
                 formula="거래금액 계 ÷ 거래건수 계", citation=_C_EFT,
                 source_module=_M_DER),
        _remark("거래 원장이 없다. 채널별 가입자 수(파생)에 1인당 분기 거래횟수와 "
                "건당 금액을 곱해 만들었으므로 이 서식은 전부 파생이다. 조회거래는 "
                "건당 금액이 정의되지 않아 제외하고 자금이동 거래만 센다.", _C_EFT),
    ]
    checks = [
        _sum_check("거래건수 계 = 채널별 합", L, "1000", tuple(n_codes), 1e-9),
        _sum_check("거래금액 계 = 채널별 합", L, "2000", tuple(a_codes),
                   tol(amt_total)),
        _ratio_check("건당 평균 = 거래금액 ÷ 거래건수", L, "3000", "2000", "1000",
                     1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B1112

def _b1112(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """전자금융경로를 통한 대출 — **금액·건수는 실측이고 채널 라벨만 파생이다.**"""
    lb = ebank_loan_book(ctx)
    total = float(lb["balance"].sum())
    nonface = lb[lb["channel"] != "영업점 창구"]
    L = [
        FormLine("1000", "가계여신 잔액 계", 0, "KRW", total,
                 formula=f"rdm_asset_quality 잔액 실측 · {len(lb):,}건",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        # 건수도 소계 라인으로 세운다. 채널별 건수만 적어 두면 합계가 실측 건수와
        # 맞는지 서식 안에서 대사할 수 없다.
        FormLine("1010", "가계여신 건수 계", 0, "count", float(len(lb)),
                 formula="rdm_asset_quality 익스포저 건수 실측",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
    ]
    ch_codes = []
    for i, ch in enumerate(EBANK_LOAN_CHANNELS, start=1):
        s = lb[lb["channel"] == ch]
        base = 1000 + i * 100
        ch_codes.append(str(base))
        L += [
            FormLine(str(base), f"취급채널 · {ch}", 1, "KRW",
                     float(s["balance"].sum()),
                     formula=("채널 라벨은 파생, 금액은 실측 — 익스포저별 채널 "
                              f"배정 · {_DERIVED}"),
                     citation=_C_EFT if i > 1 else _C99, source_module=_M_DER,
                     is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     formula="채널 배정 건수 — 잔액과 같은 배정",
                     citation=_C99, source_module=_M_DER),
        ]
    L += [
        FormLine("2000", "비대면 취급 잔액", 0, "KRW",
                 float(nonface["balance"].sum()),
                 formula="인터넷뱅킹 + 모바일뱅킹", citation=_C_EFT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "비대면 취급 건수", 0, "count", float(len(nonface)),
                 formula="인터넷뱅킹 건수 + 모바일뱅킹 건수 — 건수는 실측",
                 citation=_C_EFT, source_module=_M_DER),
        FormLine("3000", "비대면 취급 비중", 0, "ratio",
                 float(nonface["balance"].sum()) / total,
                 formula="비대면 취급 잔액 ÷ 가계여신 잔액 계", citation=_C_EFT,
                 source_module=_M_DER),
        FormLine("4010", "상품별 · 주택담보대출 (비대면)", 1, "KRW",
                 float(nonface[nonface["is_mortgage"]]["balance"].sum()),
                 formula="담보 실행 절차 때문에 창구 비중이 높다 — 금액은 실측",
                 citation=_C_EFT, source_module=_M_DER),
        FormLine("4020", "상품별 · 기타가계대출 (비대면)", 1, "KRW",
                 float(nonface[~nonface["is_mortgage"]]["balance"].sum()),
                 formula="금액은 실측 · 채널 라벨만 파생", citation=_C_EFT,
                 source_module=_M_DER),
        _remark("취급채널 원장이 없어 익스포저마다 채널을 배정했다. **금액·건수는 "
                "전부 실측**이고 파생은 채널 라벨 하나뿐이므로 채널별 합계가 자동으로 "
                "가계여신 실측 총액이 된다. 비대면 비중을 잔액에 곱해 만들었다면 그 "
                "항등식을 따로 지켜야 했다.", _C_EFT),
    ]
    t = tol(total)
    checks = [
        _sum_check("가계여신 잔액 계 = 채널별 합", L, "1000", tuple(ch_codes), t),
        _sum_check("가계여신 건수 계 = 채널별 건수 합", L, "1010",
                   tuple(str(int(c) + 10) for c in ch_codes), 1e-9),
        _sum_check("비대면 취급 잔액 = 인터넷 + 모바일", L, "2000",
                   ("1200", "1300"), t),
        _sum_check("비대면 취급 건수 = 인터넷 + 모바일 건수", L, "2010",
                   ("1210", "1310"), 1e-9),
        _sum_check("비대면 잔액 = 주담대 + 기타가계", L, "2000",
                   ("4010", "4020"), t),
        _ratio_check("비대면 비중 = 비대면 ÷ 가계여신 계", L, "3000", "2000",
                     "1000", 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B1115

def _b1115(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """업무위수탁 현황 — 목록은 고정 어휘이고 수탁사 수·재위탁만 파생이다."""
    ob = outsourcing(ctx)
    L = [
        FormLine("1000", "위탁업무 건수", 0, "count", float(len(ob)),
                 formula="위탁업무 목록 행 수", citation=_C_OUT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "수탁사 수 계", 0, "count", float(ob["n_vendor"].sum()),
                 formula="업무별 수탁사 수 합", citation=_C_OUT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "재위탁이 있는 업무 수", 0, "count",
                 float(int(ob["resale"].sum())),
                 formula=f"재위탁 여부 · {_DERIVED}", citation=_C_OUT,
                 source_module=_M_DER),
        FormLine("1030", "계열회사 위탁 업무 수", 0, "count",
                 float(int((ob["party_type"] == "계열회사").sum())),
                 formula="수탁자 유형이 계열회사인 업무 수", citation=_C_OUT,
                 source_module=_M_DER),
    ]
    codes = []
    for i, (_, r) in enumerate(ob.iterrows(), start=1):
        code = str(2000 + i * 10)
        codes.append(code)
        L.append(FormLine(
            code, f"위탁업무 · {r['item']}", 1, "count", float(r["n_vendor"]),
            formula=(f"수탁자 {r['party_type']} · 재위탁 "
                     f"{'있음' if r['resale'] else '없음'} · "
                     + ("대출모집 위탁사 수는 B3114와 같은 값"
                        if r["from_ledger"] else _DERIVED)),
            citation=_C_OUT, source_module=_M_DER))
    L.append(_remark(
        "위탁업무 목록은 난수가 아니라 편제용 고정 어휘이고 수탁사 수·재위탁 여부만 "
        "파생이다. 대출모집만 forms_fss_compliance_data.loan_agent_book을 읽어 "
        "B3114와 같은 위탁사 수를 쓴다. 보고 근거 조문 번호를 확신할 수 없어 고시 "
        "단위로 낮춰 달았다 — 틀린 조문은 조문이 없는 것보다 나쁘다.", _C_OUT))
    checks = [
        _sum_check("수탁사 수 계 = 업무별 합", L, "1010", tuple(codes), 1e-9),
        FormCheck("위탁업무 건수 = 명세 행 수", float(len(ob)), _val(L, "1000"),
                  1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B1116

def _b1116(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """정보처리 업무위탁 현황 — 국외 소재·고유식별정보 처리 여부를 함께 적는다."""
    it = it_outsourcing()
    L = [
        FormLine("1000", "정보처리 위탁업무 건수", 0, "count", float(len(it)),
                 formula="위탁업무 목록 행 수", citation=_C_ITO,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "수탁사 수 계", 0, "count", float(it["n_vendor"].sum()),
                 formula="업무별 수탁사 수 합", citation=_C_ITO,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "국외 소재 수탁 업무 수", 0, "count",
                 float(int((it["location"] == "국외").sum())),
                 formula="수탁자 소재가 국외인 업무 수 — 국외이전 점검 대상",
                 citation=_C_ITO, source_module=_M_DER),
        FormLine("1030", "고유식별정보 처리 위탁 업무 수", 0, "count",
                 float(int(it["pii"].sum())),
                 formula="고유식별정보를 처리하는 위탁업무 수 — 업무 성격에서 정한 "
                         "고정 어휘이며 난수가 아니다",
                 citation=_C_ITO, source_module=_M_DER),
        FormLine("1040", "클라우드 이용 업무 수", 0, "count",
                 float(int(it["item"].str.contains("클라우드").sum())),
                 formula="위탁업무명에 '클라우드'가 들어간 업무 수 — 고정 어휘",
                 citation=_C_ITO, source_module=_M_DER),
    ]
    codes = []
    for i, (_, r) in enumerate(it.iterrows(), start=1):
        code = str(2000 + i * 10)
        codes.append(code)
        L.append(FormLine(
            code, f"정보처리 위탁 · {r['item']}", 1, "count",
            float(r["n_vendor"]),
            formula=(f"수탁자 소재 {r['location']} · 고유식별정보 처리 "
                     f"{'있음' if r['pii'] else '없음'} · {_DERIVED}"),
            citation=_C_ITO, source_module=_M_DER))
    L.append(_remark(
        "정보처리 위탁 목록은 편제용 고정 어휘이고 수탁사 수만 파생이다. 소재지·"
        "고유식별정보 처리 여부는 업무 성격에서 정한 값이며 난수가 아니다. 보고 근거 "
        "조문 번호를 확신할 수 없어 규정·고시 단위로 낮춰 달았다.", _C_ITO))
    checks = [
        _sum_check("수탁사 수 계 = 업무별 합", L, "1010", tuple(codes), 1e-9),
        FormCheck("위탁업무 건수 = 명세 행 수", float(len(it)), _val(L, "1000"),
                  1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B8101

def _b8101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """집합투자증권 판매현황 — 판매잔액 총액만 예수금(실측)에 앵커한다."""
    fs = fund_sales(ctx)
    total = float(fs["balance"].sum())
    base_dep = float(fs["deposit_base"].iloc[0])
    new_total = float(fs["new_sales"].sum())
    L = [
        FormLine("1000", "판매잔액 계", 0, "KRW", total,
                 formula=f"예수금 총액(실측) × 파생 판매비중 · {_ANCHOR}",
                 citation=_C_FUND, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "예수금 총액 (참고 — 앵커)", 1, "KRW", base_dep,
                 formula="개인 + 법인 예수금 실측", citation=_C99,
                 source_module=_M_PRU),
        FormLine("1020", "예수금 대비 판매잔액 비중", 1, "ratio",
                 total / base_dep, formula="판매잔액 계 ÷ 예수금 총액",
                 citation=_C99, source_module=_M_DER),
    ]
    # 잔액 블록과 신규판매 블록을 나눠 담는다 — 라인 순서가 곧 시트 행 순서라
    # 두 축을 번갈아 적으면 서식이 읽히지 않는다.
    bal_codes, new_codes, new_lines = [], [], []
    for i, (_, r) in enumerate(fs.iterrows(), start=1):
        bal_codes.append(str(2000 + i * 10))
        new_codes.append(str(3000 + i * 10))
        L.append(FormLine(str(2000 + i * 10), f"펀드유형 · {r['fund_type']}", 1,
                          "KRW", float(r["balance"]),
                          formula=f"유형 구성비 파생 · {_DERIVED}",
                          citation=_C_FUND, source_module=_M_DER))
        new_lines.append(FormLine(
            str(3000 + i * 10), f"신규판매 · {r['fund_type']}", 1, "KRW",
            float(r["new_sales"]),
            formula=f"잔액 × 월 회전율 {float(r['turnover']):.1%} · {_DERIVED}",
            citation=_C_FUND, source_module=_M_DER))
    L.append(FormLine("3000", "당월 신규판매액 계", 0, "KRW", new_total,
                      formula=f"유형별 잔액 × 파생 월 회전율 · {_DERIVED}",
                      citation=_C_FUND, source_module=_M_DER, is_subtotal=True))
    L += new_lines
    L.append(_remark(
        "판매 원장이 없다. 판매잔액 총액만 예수금 총액(실측)에 파생 비중을 곱해 "
        "앵커했고 유형 배분·회전율은 파생이다. 이 은행은 집합투자증권 판매를 "
        "미영위하는 것이 아니라 판매 원장이 없을 뿐이다 — 미영위 처리한 투자자문업"
        "(B111xx)과는 다르다.", _C_FUND))
    t = tol(total)
    checks = [
        _sum_check("판매잔액 계 = 유형별 합", L, "1000", tuple(bal_codes), t),
        _sum_check("당월 신규판매액 계 = 유형별 합", L, "3000", tuple(new_codes), t),
        _ratio_check("예수금 대비 비중 = 판매잔액 ÷ 예수금", L, "1020", "1000",
                     "1010", 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B8102

def _b8102(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """수익자별 판매현황 — 개인·법인 비중은 **예수금 실측 비중**을 그대로 쓴다."""
    fi = fund_investors(ctx)
    total = float(fi["balance"].sum())
    L = [
        FormLine("1000", "판매잔액 계", 0, "KRW", total,
                 formula="B8101 판매잔액 계와 같은 값", citation=_C_FUND,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "계좌수 계", 0, "count", float(fi["n_account"].sum()),
                 formula="B8104 총 계좌수와 같은 값", citation=_C_FUND,
                 source_module=_M_DER, is_subtotal=True),
    ]
    bal_codes, acc_codes = [], []
    for i, (_, r) in enumerate(fi.iterrows(), start=1):
        base = 2000 + i * 100
        bal_codes.append(str(base))
        acc_codes.append(str(base + 10))
        share = r["deposit_share"]
        note = ("개인·법인 예수금 실측 비중 "
                f"{float(share):.1%} 적용" if share == share
                else f"기관 몫만 파생 · {_DERIVED}")
        L += [
            FormLine(str(base), f"수익자 · {r['investor']}", 1, "KRW",
                     float(r["balance"]), formula=note, citation=_C_FUND,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "계좌수", 2, "count", float(r["n_account"]),
                     formula=f"계좌당 평잔 배수 파생 후 최대잔여법 배분 · {_DERIVED}",
                     citation=_C_FUND, source_module=_M_DER),
            FormLine(str(base + 20), "계좌당 평균 판매잔액", 2, "KRW",
                     float(r["balance"]) / float(r["n_account"]),
                     formula="수익자별 잔액 ÷ 계좌수", citation=_C_FUND,
                     source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "개인 예수금 비중 (참고 — 배분 근거)", 0, "ratio",
                 retail_deposits(ctx)
                 / (retail_deposits(ctx) + corporate_deposits(ctx)),
                 formula="개인 예수금 ÷ (개인 + 법인 예수금) — 실측",
                 citation=_C99, source_module=_M_PRU),
        _remark("수익자 구분 원장이 없다. 기관투자자 몫만 파생으로 떼어내고 나머지 "
                "개인·법인 배분은 **개인·법인 예수금 실측 비중**을 그대로 쓴다 — "
                "수익자 구성을 새로 뽑으면 같은 은행의 고객 구성이 수신 서식과 펀드 "
                "서식에서 갈린다.", _C_FUND),
    ]
    t = tol(total)
    checks = [
        _sum_check("판매잔액 계 = 수익자별 합", L, "1000", tuple(bal_codes), t),
        _sum_check("계좌수 계 = 수익자별 합", L, "1010", tuple(acc_codes), 1e-9),
        FormCheck("판매잔액 계 = B8101 판매잔액 계",
                  float(fund_sales(ctx)["balance"].sum()), total, t),
    ]
    return L, checks


# ---------------------------------------------------------------- B8103

def _b8103(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """집합투자증권 판매수익현황 — 판매보수는 잔액 × 파생 보수율이다."""
    fs = fund_sales(ctx)
    fee = float(fs["fee_income"].sum())
    front = float(fs["front_income"].sum())
    balance = float(fs["balance"].sum())
    L = [
        FormLine("1000", "판매수익 계 (당월)", 0, "KRW", fee + front,
                 formula="판매보수 + 선취판매수수료", citation=_C_FUND,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "판매보수 (잔액 기준)", 1, "KRW", fee,
                 formula=f"유형별 잔액 × 파생 연 보수율 ÷ 12 · {_DERIVED}",
                 citation=_C_FUND, source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "선취판매수수료", 1, "KRW", front,
                 formula=f"당월 신규판매액 × 파생 선취율 · {_DERIVED}",
                 citation=_C_FUND, source_module=_M_DER),
    ]
    fee_codes = []
    for i, (_, r) in enumerate(fs.iterrows(), start=1):
        code = str(2000 + i * 10)
        fee_codes.append(code)
        L.append(FormLine(code, f"판매보수 · {r['fund_type']}", 1, "KRW",
                          float(r["fee_income"]),
                          formula=(f"잔액 × 연 {float(r['fee_rate']):.2%} ÷ 12 · "
                                   f"{_DERIVED}"),
                          citation=_C_FUND, source_module=_M_DER))
    L += [
        FormLine("3000", "평균 판매보수율 (연율)", 0, "ratio",
                 fee * 12.0 / balance,
                 formula="연환산 판매보수 ÷ 판매잔액", citation=_C_FUND,
                 source_module=_M_DER),
        FormLine("3010", "연환산 판매보수 (참고)", 1, "KRW", fee * 12.0,
                 formula="당월 판매보수 × 12", citation=_C_FUND,
                 source_module=_M_DER),
        FormLine("3020", "판매잔액 (참고)", 1, "KRW", balance,
                 formula="B8101 판매잔액 계", citation=_C_FUND,
                 source_module=_M_DER),
        _remark("판매수수료 원장이 없다. 판매보수율·선취수수료율이 파생이고 잔액은 "
                "B8101과 같은 앵커다. 손익계산서에는 수수료수익 계정이 따로 없으므로 "
                "이 수익은 pru_income_statement의 영업수익과 대사되지 않는다 — "
                "대사할 수 있는 척하지 않는다.", _C_FUND),
    ]
    t = tol(max(fee + front, 1.0))
    checks = [
        _sum_check("판매수익 계 = 판매보수 + 선취수수료", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("판매보수 = 유형별 합", L, "1010", tuple(fee_codes), t),
        _ratio_check("평균 보수율 = 연환산 보수 ÷ 판매잔액", L, "3000", "3010",
                     "3020", 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B8104

def _b8104(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """계좌수 현황 — 계좌수는 잔액 ÷ 계좌당 평잔(파생)으로 만든다."""
    fs = fund_sales(ctx)
    fi = fund_investors(ctx)
    total_acc = float(fs["n_account"].sum())
    balance = float(fs["balance"].sum())
    L = [
        FormLine("1000", "총 계좌수", 0, "count", total_acc,
                 formula=f"유형별 잔액 ÷ 파생 계좌당 평잔 · {_DERIVED}",
                 citation=_C_FUND, source_module=_M_DER, is_subtotal=True),
    ]
    type_codes = []
    for i, (_, r) in enumerate(fs.iterrows(), start=1):
        code = str(1000 + i * 10)
        type_codes.append(code)
        L.append(FormLine(code, f"펀드유형 · {r['fund_type']}", 1, "count",
                          float(r["n_account"]),
                          formula=(f"잔액 ÷ 계좌당 평잔 "
                                   f"{float(r['per_account']):,.0f}원 · {_DERIVED}"),
                          citation=_C_FUND, source_module=_M_DER))
    L.append(FormLine("2000", "수익자별 계좌수 계", 0, "count",
                      float(fi["n_account"].sum()),
                      formula="B8102 계좌수 계와 같은 값", citation=_C_FUND,
                      source_module=_M_DER, is_subtotal=True))
    inv_codes = []
    for i, (_, r) in enumerate(fi.iterrows(), start=1):
        code = str(2000 + i * 10)
        inv_codes.append(code)
        L.append(FormLine(code, f"수익자 · {r['investor']}", 1, "count",
                          float(r["n_account"]),
                          formula=f"수익자별 계좌당 평잔 배수 파생 · {_DERIVED}",
                          citation=_C_FUND, source_module=_M_DER))
    L += [
        FormLine("3000", "계좌당 평균 판매잔액", 0, "KRW", balance / total_acc,
                 formula="판매잔액 계 ÷ 총 계좌수", citation=_C_FUND,
                 source_module=_M_DER),
        FormLine("3010", "판매잔액 계 (참고)", 1, "KRW", balance,
                 formula="B8101 판매잔액 계", citation=_C_FUND,
                 source_module=_M_DER),
        _remark("계좌 원장이 없다. 계좌수를 따로 뽑지 않고 잔액 ÷ 계좌당 평잔으로 "
                "만들어 서식 안에서 셋이 서로 대사되게 했다. 유형별 계좌수와 "
                "수익자별 계좌수는 같은 총 계좌수를 서로 다른 축으로 가른 것이다.",
                _C_FUND),
    ]
    checks = [
        _sum_check("총 계좌수 = 유형별 합", L, "1000", tuple(type_codes), 1e-9),
        _sum_check("수익자별 계좌수 계 = 수익자별 합", L, "2000", tuple(inv_codes),
                   1e-9),
        FormCheck("유형별 축과 수익자 축의 계좌수 총계 일치", _val(L, "1000"),
                  _val(L, "2000"), 1e-9),
        _ratio_check("계좌당 평잔 = 판매잔액 ÷ 계좌수", L, "3000", "3010", "1000",
                     1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B9101

def _b9101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """휴면예금 현황(종류별) — 합계는 개인 예수금(실측) × 파생 휴면율이다."""
    dd = dormant_deposits(ctx)
    total = dd["closing"]
    L = [
        FormLine("1000", "휴면예금 잔액 계", 0, "KRW", total,
                 formula=f"개인 예수금(실측) × 파생 휴면율 · {_ANCHOR}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "개인 예수금 (참고 — 앵커)", 1, "KRW",
                 dd["deposit_base"], formula="예수금 개인 안정 + 준안정 실측",
                 citation=_C99, source_module=_M_PRU),
        FormLine("1020", "개인 예수금 대비 휴면예금 비율", 1, "ratio",
                 total / dd["deposit_base"],
                 formula="휴면예금 잔액 ÷ 개인 예수금", citation=_C_DORM,
                 source_module=_M_DER),
    ]
    codes = []
    for i, (_, r) in enumerate(dd["kinds"].iterrows(), start=1):
        code = str(2000 + i * 10)
        codes.append(code)
        L.append(FormLine(code, f"예금종류 · {r['kind']}", 1, "KRW",
                          float(r["amount"]),
                          formula=f"종류 구성비 파생 · {_DERIVED}",
                          citation=_C_DORM, source_module=_M_DER))
    L.append(_remark(
        "휴면예금 원장이 없다. 잔액 **총계는 개인 예수금(실측)에 앵커**하고 종류 "
        "배분만 파생이다. 휴면 판정 기준(최종거래일로부터 상법 제64조 상사소멸시효 "
        "경과)은 원장이 있어야 적용할 수 있으므로 이 서식은 그 판정을 재현하지 "
        "않는다 — 재현한 척하지 않는다.", _C_DORM))
    checks = [
        _sum_check("휴면예금 잔액 계 = 종류별 합", L, "1000", tuple(codes),
                   tol(total)),
        _ratio_check("개인 예수금 대비 비율", L, "1020", "1000", "1010", 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B9102

def _b9102(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """휴면예금 현황(금액별) — 계좌수를 먼저 배분하고 금액은 대표금액으로 만든다."""
    dd = dormant_deposits(ctx)
    bands = dd["bands"]
    total = dd["closing"]
    n_total = float(bands["n_account"].sum())
    L = [
        FormLine("1000", "휴면예금 잔액 계", 0, "KRW", total,
                 formula="B9101 잔액 계와 같은 값", citation=_C_DORM,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "계좌수 계", 0, "count", n_total,
                 formula=f"총액 ÷ 구간 대표금액 가중평균 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
    ]
    amt_codes, acc_codes = [], []
    for i, (_, r) in enumerate(bands.iterrows(), start=1):
        base = 2000 + i * 100
        amt_codes.append(str(base))
        acc_codes.append(str(base + 10))
        n = float(r["n_account"])
        L += [
            FormLine(str(base), f"금액구간 · {r['band']}", 1, "KRW",
                     float(r["amount"]),
                     formula=f"구간 계좌수 × 구간 대표금액 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "계좌수", 2, "count", n,
                     formula=f"구간 구성비 파생 후 최대잔여법 배분 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER),
            FormLine(str(base + 20), "계좌당 평균잔액", 2, "KRW",
                     float(r["amount"]) / n if n else 0.0,
                     formula="구간 잔액 ÷ 구간 계좌수 — 구간 대표금액과 같아야 한다",
                     citation=_C_DORM, source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "계좌당 평균잔액 (전체)", 0, "KRW", total / n_total,
                 formula="휴면예금 잔액 계 ÷ 계좌수 계", citation=_C_DORM,
                 source_module=_M_DER),
        _remark("금액구간별 계좌수를 먼저 배분하고 잔액을 구간 대표금액으로 만들었다. "
                "반대로 잔액을 먼저 뽑아 대표금액으로 나누면 소액 구간 계좌수가 "
                "고객 수를 넘어선다 — 대표금액이 작아 총액의 몇 %만 줘도 계좌가 "
                "폭증하기 때문이다. 총계는 B9101과 같은 앵커다.", _C_DORM),
    ]
    t = tol(total)
    checks = [
        _sum_check("휴면예금 잔액 계 = 금액구간별 합", L, "1000", tuple(amt_codes), t),
        _sum_check("계좌수 계 = 금액구간별 합", L, "1010", tuple(acc_codes), 1e-9),
        _ratio_check("계좌당 평균잔액 = 잔액 ÷ 계좌수", L, "3000", "1000", "1010",
                     1e-6),
        _band_range_check("구간 평균잔액이 금액구간 범위 내 (이탈 구간 수)", bands),
        # 계좌수를 대표금액으로 역산하는 방식이 무너지면 소액 구간 계좌가 폭증한다.
        # 휴면 계좌수가 개인 고객 수를 넘으면 그 배분이 이미 틀린 것이다.
        FormCheck("계좌수 계 ≤ 개인 고객 수 (B1110)", 0.0,
                  max(0.0, n_total - retail_customers(ctx)["individual"]), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B9103

def _b9103(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """휴면예금 환급실적 및 신규발생 — 기말을 앵커에 두고 기초를 역산한다."""
    dd = dormant_deposits(ctx)
    L = [
        FormLine("1000", "기초잔액", 0, "KRW", dd["opening"],
                 formula=f"기말 − 신규 + 환급 + 출연으로 역산 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("1100", "반기 중 신규 휴면 편입", 0, "KRW", dd["new"],
                 formula=f"기말잔액 × 파생 편입률 · {_DERIVED}", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("1200", "반기 중 환급(지급)", 0, "KRW", dd["refund"],
                 formula=f"기말잔액 × 파생 환급률 · {_DERIVED}", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("1300", "서민금융진흥원 출연", 0, "KRW", dd["donation"],
                 formula=f"기말잔액 × 파생 출연율 · {_DERIVED}",
                 citation="서민의 금융생활 지원에 관한 법률 — 휴면예금 출연",
                 source_module=_M_DER),
        FormLine("2000", "기말잔액", 0, "KRW", dd["closing"],
                 formula=f"개인 예수금(실측) × 파생 휴면율 · {_ANCHOR}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "환급 건수", 0, "count", dd["refund_count"],
                 formula=f"환급액 ÷ 파생 건당 환급액 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER),
        FormLine("2020", "건당 평균 환급액", 0, "KRW",
                 dd["refund"] / dd["refund_count"],
                 formula="환급액 ÷ 환급 건수", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("3000", "환급률 (기말잔액 대비)", 0, "ratio",
                 dd["refund"] / dd["closing"],
                 formula="환급액 ÷ 기말잔액", citation=_C_DORM,
                 source_module=_M_DER),
        _remark("휴면예금 롤포워드 원장이 없다. **기말잔액을 앵커로 두고 기초잔액을 "
                "역산**했으므로 기초 + 신규 − 환급 − 출연 = 기말 항등식이 언제나 "
                "성립한다. 넷을 따로 뽑았다면 잔차가 남았을 것이다.", _C_DORM),
    ]
    t = tol(dd["closing"])
    checks = [
        FormCheck("기말 = 기초 + 신규 − 환급 − 출연", _val(L, "2000"),
                  _val(L, "1000") + _val(L, "1100") - _val(L, "1200")
                  - _val(L, "1300"), t),
        FormCheck("기말잔액 = B9101 휴면예금 잔액 계", dd["closing"],
                  _val(L, "2000"), t),
        _ratio_check("건당 평균 환급액 = 환급액 ÷ 건수", L, "2020", "1200", "2010",
                     1e-6),
        _ratio_check("환급률 = 환급액 ÷ 기말잔액", L, "3000", "1200", "2000", 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B9104

def _b9104(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """미거래 예금 현황(금액별·경과기간별) — 휴면 도래 전 단계다."""
    ia = inactive_deposits(ctx)
    total = ia["total"]
    L = [
        FormLine("1000", "미거래 예금 잔액 계", 0, "KRW", total,
                 formula=f"개인 예수금(실측) × 파생 미거래율 · {_ANCHOR}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "계좌수 계", 0, "count", ia["n_account"],
                 formula=f"총액 ÷ 구간 대표금액 가중평균 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "개인 예수금 대비 미거래 비율", 1, "ratio",
                 total / ia["deposit_base"],
                 formula="미거래 잔액 ÷ 개인 예수금", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("1030", "개인 예수금 (참고 — 앵커)", 1, "KRW",
                 ia["deposit_base"], formula="예수금 개인 안정 + 준안정 실측",
                 citation=_C99, source_module=_M_PRU),
    ]
    el_codes = []
    for i, (_, r) in enumerate(ia["elapsed"].iterrows(), start=1):
        code = str(2000 + i * 10)
        el_codes.append(code)
        L.append(FormLine(code, f"경과기간 · {r['band']}", 1, "KRW",
                          float(r["amount"]),
                          formula=f"경과기간 구성비 파생 · {_DERIVED}",
                          citation=_C_DORM, source_module=_M_DER))
    amt_codes, acc_codes = [], []
    for i, (_, r) in enumerate(ia["bands"].iterrows(), start=1):
        base = 3000 + i * 100
        amt_codes.append(str(base))
        acc_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"금액구간 · {r['band']}", 1, "KRW",
                     float(r["amount"]),
                     formula=f"구간 계좌수 × 구간 대표금액 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "계좌수", 2, "count", float(r["n_account"]),
                     formula=f"구간 구성비 파생 후 최대잔여법 배분 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER),
        ]
    L.append(_remark(
        "미거래 예금은 휴면 도래 전 단계이며 원장이 없다. 총계는 휴면예금과 같은 "
        "개인 예수금(실측)에 앵커했고 경과기간·금액구간 배분만 파생이다. 두 축은 "
        "같은 총액을 다르게 가른 것이므로 각각 총계와 대사한다.", _C_DORM))
    t = tol(total)
    checks = [
        _sum_check("미거래 잔액 계 = 경과기간별 합", L, "1000", tuple(el_codes), t),
        _sum_check("미거래 잔액 계 = 금액구간별 합", L, "1000", tuple(amt_codes), t),
        _sum_check("계좌수 계 = 금액구간별 합", L, "1010", tuple(acc_codes), 1e-9),
        _ratio_check("개인 예수금 대비 비율", L, "1020", "1000", "1030", 1e-12),
        _band_range_check("구간 평균잔액이 금액구간 범위 내 (이탈 구간 수)",
                          ia["bands"]),
        FormCheck("계좌수 계 ≤ 개인 고객 수 (B1110)", 0.0,
                  max(0.0, ia["n_account"]
                      - retail_customers(ctx)["individual"]), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B9105

def _b9105(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """미거래 예금 현황(연령별) — 예금주 연령 원장이 없어 전부 파생이다."""
    ia = inactive_deposits(ctx)
    ages = ia["ages"]
    total = ia["total"]
    n_total = float(ages["n_account"].sum())
    L = [
        FormLine("1000", "미거래 예금 잔액 계", 0, "KRW", total,
                 formula="B9104 잔액 계와 같은 값", citation=_C_DORM,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "계좌수 계", 0, "count", n_total,
                 formula="B9104 계좌수 계와 같은 값", citation=_C_DORM,
                 source_module=_M_DER, is_subtotal=True),
    ]
    amt_codes, acc_codes = [], []
    for i, (_, r) in enumerate(ages.iterrows(), start=1):
        base = 2000 + i * 100
        amt_codes.append(str(base))
        acc_codes.append(str(base + 10))
        n = float(r["n_account"])
        L += [
            FormLine(str(base), f"연령 · {r['band']}", 1, "KRW",
                     float(r["amount"]),
                     formula=("연령별 계좌수 × 연령 평잔배수를 총액에 맞춰 조정 · "
                              f"{_DERIVED}"),
                     citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "계좌수", 2, "count", n,
                     formula=f"연령 구성비 파생 후 최대잔여법 배분 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER),
            FormLine(str(base + 20), "계좌당 평균잔액", 2, "KRW",
                     float(r["amount"]) / n if n else 0.0,
                     formula="연령별 잔액 ÷ 계좌수", citation=_C_DORM,
                     source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "계좌당 평균잔액 (전체)", 0, "KRW", total / n_total,
                 formula="미거래 잔액 계 ÷ 계좌수 계", citation=_C_DORM,
                 source_module=_M_DER),
        _remark("예금주 연령 원장이 없어 연령 분포는 전부 파생이다. 계좌수를 먼저 "
                "배분하고 연령별 평잔배수를 곱해 잔액을 만든 뒤 총액에 맞춰 조정했다 "
                "— 계좌수와 잔액을 독립으로 뽑으면 20대 계좌 평잔이 60대보다 큰 "
                "서식이 나온다. 총계는 B9104와 같은 앵커다.", _C_DORM),
    ]
    t = tol(total)
    checks = [
        _sum_check("미거래 잔액 계 = 연령별 합", L, "1000", tuple(amt_codes), t),
        _sum_check("계좌수 계 = 연령별 합", L, "1010", tuple(acc_codes), 1e-9),
        FormCheck("잔액 계 = B9104 미거래 잔액 계", ia["total"], _val(L, "1000"), t),
        _ratio_check("계좌당 평균잔액 = 잔액 ÷ 계좌수", L, "3000", "1000", "1010",
                     1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B9106

def _b9106(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """휴면 자기앞수표 발행대금 환급실적 및 신규발생 — 결제성 예수금에 앵커한다."""
    cc = cashier_checks(ctx)
    L = [
        FormLine("1000", "기초잔액", 0, "KRW", cc["opening"],
                 formula=f"기말 − 신규 + 환급 + 출연으로 역산 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("1100", "반기 중 신규 휴면 편입", 0, "KRW", cc["new"],
                 formula=f"기말잔액 × 파생 편입률 · {_DERIVED}", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("1200", "반기 중 환급(지급)", 0, "KRW", cc["refund"],
                 formula=f"기말잔액 × 파생 환급률 · {_DERIVED}", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("1300", "서민금융진흥원 출연", 0, "KRW", cc["donation"],
                 formula=f"기말잔액 × 파생 출연율 · {_DERIVED}",
                 citation="서민의 금융생활 지원에 관한 법률 — 휴면성 신탁금·수표 출연",
                 source_module=_M_DER),
        FormLine("2000", "기말잔액", 0, "KRW", cc["closing"],
                 formula=f"자기앞수표 발행대금 × 파생 휴면율 · {_ANCHOR}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
        FormLine("2100", "자기앞수표 발행대금 잔액 (모수)", 0, "KRW",
                 cc["issued"],
                 formula=f"법인 결제성 예수금(실측) × 파생 발행비율 · {_ANCHOR}",
                 citation=_C99, source_module=_M_DER),
        FormLine("2110", "법인 결제성 예수금 (참고 — 앵커)", 1, "KRW",
                 cc["settle_deposit"], formula="재무상태표 실측",
                 citation=_C99, source_module=_M_PRU),
        FormLine("2120", "발행대금 대비 휴면 비율", 0, "ratio",
                 cc["closing"] / cc["issued"],
                 formula="휴면 기말잔액 ÷ 발행대금 잔액", citation=_C_DORM,
                 source_module=_M_DER),
        FormLine("2130", "환급 매수", 0, "count", cc["refund_count"],
                 formula=f"환급액 ÷ 파생 건당 환급액 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER),
        _remark("자기앞수표 발행대금 원장이 없다. 자기앞수표는 결제성 자금이므로 "
                "법인 결제성 예수금(실측)을 모수로 잡고 발행비율·휴면율을 파생했다. "
                "롤포워드는 휴면예금(B9103)과 같은 방식으로 기말을 앵커에 두고 "
                "기초를 역산한다.", _C_DORM),
    ]
    t = tol(max(cc["issued"], 1.0))
    checks = [
        FormCheck("기말 = 기초 + 신규 − 환급 − 출연", _val(L, "2000"),
                  _val(L, "1000") + _val(L, "1100") - _val(L, "1200")
                  - _val(L, "1300"), t),
        _ratio_check("휴면 비율 = 휴면잔액 ÷ 발행대금", L, "2120", "2000", "2100",
                     1e-12),
        FormCheck("발행대금 ≤ 법인 결제성 예수금", 0.0,
                  max(0.0, cc["issued"] - cc["settle_deposit"]), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B9107

def _b9107(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """휴면 자기앞수표 발행대금 현황(금액별)."""
    cc = cashier_checks(ctx)
    bands = cc["bands"]
    total = cc["closing"]
    n_total = float(bands["n_account"].sum())
    L = [
        FormLine("1000", "휴면 자기앞수표 발행대금 계", 0, "KRW", total,
                 formula="B9106 기말잔액과 같은 값", citation=_C_DORM,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "매수 계", 0, "count", n_total,
                 formula=f"총액 ÷ 구간 대표금액 가중평균 · {_DERIVED}",
                 citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
    ]
    amt_codes, cnt_codes = [], []
    for i, (_, r) in enumerate(bands.iterrows(), start=1):
        base = 2000 + i * 100
        amt_codes.append(str(base))
        cnt_codes.append(str(base + 10))
        L += [
            FormLine(str(base), f"금액구간 · {r['band']}", 1, "KRW",
                     float(r["amount"]),
                     formula=f"구간 매수 × 구간 대표금액 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "매수", 2, "count", float(r["n_account"]),
                     formula=f"구간 구성비 파생 후 최대잔여법 배분 · {_DERIVED}",
                     citation=_C_DORM, source_module=_M_DER),
        ]
    L += [
        FormLine("3000", "매당 평균 금액", 0, "KRW",
                 total / n_total if n_total else 0.0,
                 formula="발행대금 계 ÷ 매수 계", citation=_C_DORM,
                 source_module=_M_DER),
        _remark("자기앞수표 원장이 없다. 매수를 먼저 배분하고 금액을 구간 대표금액으로 "
                "만들었으므로 구간 평균금액이 구간을 벗어나지 않는다. 총계는 B9106 "
                "기말잔액과 같다.", _C_DORM),
    ]
    t = tol(max(total, 1.0))
    checks = [
        _sum_check("발행대금 계 = 금액구간별 합", L, "1000", tuple(amt_codes), t),
        _sum_check("매수 계 = 금액구간별 합", L, "1010", tuple(cnt_codes), 1e-9),
        FormCheck("발행대금 계 = B9106 기말잔액", cc["closing"], _val(L, "1000"), t),
        _ratio_check("매당 평균 = 발행대금 ÷ 매수", L, "3000", "1000", "1010", 1e-6),
        _band_range_check("구간 매당 금액이 금액구간 범위 내 (이탈 구간 수)", bands),
    ]
    return L, checks


# ---------------------------------------------------------------- B10101

def _b10101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """금리인하요구권 운영현황 — **대상 여신은 실제 포트폴리오**다."""
    rc = rate_cut_requests(ctx)
    ap = rc[rc["applied"]]
    ac = rc[rc["accepted"]]
    hh, co = rc[rc["is_household"]], rc[~rc["is_household"]]
    relief = float(rc["relief"].sum())
    avg_cut = float(ac["cut_rate"].mean()) if len(ac) else 0.0
    L = [
        FormLine("1000", "대상 여신 건수", 0, "count", float(len(rc)),
                 formula="가계·기업 여신 익스포저 수 — 실측 (국가·은행 익스포저 제외)",
                 citation=_C_RATE, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "대상 여신 잔액", 0, "KRW", float(rc["balance"].sum()),
                 formula="rdm_asset_quality 잔액 실측", citation=_C_RATE,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2000", "신청 건수", 0, "count", float(len(ap)),
                 formula=f"차주 PD가 낮을수록 신청 확률을 올린 배정 · {_DERIVED}",
                 citation=_C_RATE, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "신청 여신 잔액", 0, "KRW", float(ap["balance"].sum()),
                 formula="신청 배정 익스포저의 실측 잔액 합", citation=_C_RATE,
                 source_module=_M_DER),
        FormLine("2100", "수용 건수", 0, "count", float(len(ac)),
                 formula=f"신청 건 중 수용 배정 · {_DERIVED}", citation=_C_RATE,
                 source_module=_M_DER),
        FormLine("2110", "수용 여신 잔액", 0, "KRW", float(ac["balance"].sum()),
                 formula="수용 배정 익스포저의 실측 잔액 합", citation=_C_RATE,
                 source_module=_M_DER),
        FormLine("2200", "미수용 건수", 0, "count", float(len(ap) - len(ac)),
                 formula="신청 건수 − 수용 건수", citation=_C_RATE,
                 source_module=_M_DER),
        FormLine("3000", "수용률 (건수 기준)", 0, "ratio",
                 len(ac) / len(ap) if len(ap) else 0.0,
                 formula="수용 건수 ÷ 신청 건수", citation=_C_RATE,
                 source_module=_M_DER),
        FormLine("3010", "평균 금리인하폭 (연율)", 0, "ratio", avg_cut,
                 formula=f"수용 건 인하폭(연율 비율) 단순평균 · {_DERIVED}",
                 citation=_C_RATE, source_module=_M_DER),
        FormLine("3020", "연간 이자경감액", 0, "KRW", relief,
                 formula="수용 여신 잔액(실측) × 인하폭(파생)", citation=_C_RATE,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("4000", "가계여신 · 신청 건수", 1, "count",
                 float(int(hh["applied"].sum())), formula=_DERIVED,
                 citation=_C_RATE, source_module=_M_DER),
        FormLine("4010", "가계여신 · 수용 건수", 1, "count",
                 float(int(hh["accepted"].sum())), formula=_DERIVED,
                 citation=_C_RATE, source_module=_M_DER),
        FormLine("4020", "가계여신 · 이자경감액", 1, "KRW",
                 float(hh["relief"].sum()),
                 formula="잔액(실측) × 인하폭(파생)", citation=_C_RATE,
                 source_module=_M_DER),
        FormLine("5000", "기업여신 · 신청 건수", 1, "count",
                 float(int(co["applied"].sum())), formula=_DERIVED,
                 citation=_C_RATE, source_module=_M_DER),
        FormLine("5010", "기업여신 · 수용 건수", 1, "count",
                 float(int(co["accepted"].sum())), formula=_DERIVED,
                 citation=_C_RATE, source_module=_M_DER),
        FormLine("5020", "기업여신 · 이자경감액", 1, "KRW",
                 float(co["relief"].sum()),
                 formula="잔액(실측) × 인하폭(파생)", citation=_C_RATE,
                 source_module=_M_DER),
        _remark("신청·수용 원장이 없다. **대상 여신은 실제 포트폴리오**이고 신청·수용 "
                "여부와 인하폭만 파생이다. 익스포저마다 배정했으므로 대상 ≥ 신청 ≥ "
                "수용 관계가 서식 안에서 자동으로 성립한다. 신용도가 좋아진 차주가 "
                "신청·수용된다는 관계를 담기 위해 PD가 낮을수록 확률을 올렸다. "
                "국가·은행 익스포저는 금리인하 요구 대상이 아니므로 모집단에서 뺐다.",
                _C_RATE),
    ]
    t = tol(max(float(rc["balance"].sum()), 1.0))
    checks = [
        _sum_check("신청 건수 = 수용 + 미수용", L, "2000", ("2100", "2200"), 1e-9),
        _sum_check("신청 건수 = 가계 + 기업", L, "2000", ("4000", "5000"), 1e-9),
        _sum_check("수용 건수 = 가계 + 기업", L, "2100", ("4010", "5010"), 1e-9),
        _sum_check("이자경감액 = 가계 + 기업", L, "3020", ("4020", "5020"),
                   tol(max(relief, 1.0))),
        _ratio_check("수용률 = 수용 ÷ 신청", L, "3000", "2100", "2000", 1e-12),
        FormCheck("수용 여신 잔액 ≤ 신청 여신 잔액", 0.0,
                  max(0.0, _val(L, "2110") - _val(L, "2010")), t),
        FormCheck("신청 여신 잔액 ≤ 대상 여신 잔액", 0.0,
                  max(0.0, _val(L, "2010") - _val(L, "1010")), t),
        # 잔액만 대사하면 "대상 ≥ 신청 ≥ 수용"의 건수 축이 비어 있다.
        FormCheck("신청 건수 ≤ 대상 건수", 0.0,
                  max(0.0, _val(L, "2000") - _val(L, "1000")), 1e-9),
        FormCheck("수용 건수 ≤ 신청 건수", 0.0,
                  max(0.0, _val(L, "2100") - _val(L, "2000")), 1e-9),
    ]
    return L, checks


# ------------------------------------------------------- B11101~B11107 · B12101
#
# 여덟 서식 모두 `ADVISORY_LICENSED = False` 하나를 본다. 항목 편제만 서식마다
# 다르고 값은 전부 0이다.

def _b11101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """투자권유자문인력 현황 — 투자자문업 미영위."""
    L, checks = _not_operating((
        ("1000", "투자권유자문인력 계", 0, "count"),
        ("1010", "증권 투자권유자문인력", 1, "count"),
        ("1020", "펀드 투자권유자문인력", 1, "count"),
        ("1030", "파생상품 투자권유자문인력", 1, "count"),
        ("2000", "투자권유대행인 수", 0, "count"),
        ("3000", "투자자문 전담 임직원 수", 0, "count"),
    ), _C_ADV, ADVISORY_REASON + " 집합투자증권 판매(B8101~B8104) 인력은 이 "
        "서식의 대상이 아니며 판매 인력 원장도 없다.")
    return L, checks


def _b11102(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """투자자문 계약현황 — 투자자문업 미영위."""
    return _not_operating((
        ("1000", "투자자문 계약 건수", 0, "count"),
        ("1010", "당월 신규 계약 건수", 1, "count"),
        ("1020", "당월 해지 계약 건수", 1, "count"),
        ("2000", "계약금액 계", 0, "KRW"),
        ("2010", "일반투자자", 1, "KRW"),
        ("2020", "전문투자자", 1, "KRW"),
    ), _C_ADV, ADVISORY_REASON)


def _b11103(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자문수수료 수입 현황 — 투자자문업 미영위."""
    return _not_operating((
        ("1000", "자문수수료 수입 계 (당월)", 0, "KRW"),
        ("1010", "정액 수수료", 1, "KRW"),
        ("1020", "성과 연동 수수료", 1, "KRW"),
        ("2000", "누적 자문수수료 수입 (당기)", 0, "KRW"),
    ), _C_ADV, ADVISORY_REASON + " 손익계산서에 자문수수료 수익 계정 자체가 없다.")


def _b11104(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """투자자문재산 현황 — 투자자문업 미영위."""
    return _not_operating((
        ("1000", "투자자문재산 평가액 계", 0, "KRW"),
        ("1010", "당월 증가액", 1, "KRW"),
        ("1020", "당월 감소액", 1, "KRW"),
        ("2000", "자문재산 계약 건수", 0, "count"),
    ), _C_ADV, ADVISORY_REASON)


def _b11105(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """계약상대방별 투자자문재산 현황 — 투자자문업 미영위."""
    return _not_operating((
        ("1000", "투자자문재산 계", 0, "KRW"),
        ("1010", "개인 (일반투자자)", 1, "KRW"),
        ("1020", "법인 (일반투자자)", 1, "KRW"),
        ("1030", "전문투자자", 1, "KRW"),
        ("1040", "집합투자기구", 1, "KRW"),
        ("2000", "계약상대방 수", 0, "count"),
    ), _C_ADV, ADVISORY_REASON)


def _b11106(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """투자자문 대상 자산 현황 — 투자자문업 미영위."""
    return _not_operating((
        ("1000", "자문 대상 자산 계", 0, "KRW"),
        ("1010", "주식", 1, "KRW"),
        ("1020", "채무증권", 1, "KRW"),
        ("1030", "집합투자증권", 1, "KRW"),
        ("1040", "파생상품", 1, "KRW"),
        ("1050", "그 밖의 자산", 1, "KRW"),
    ), _C_ADV, ADVISORY_REASON)


def _b11107(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """투자자문재산에 관한 투자판단의 위탁 — 투자자문업 미영위."""
    return _not_operating((
        ("1000", "투자판단 위탁 계약 건수", 0, "count"),
        ("1010", "국내 수탁자", 1, "count"),
        ("1020", "국외 수탁자", 1, "count"),
        ("2000", "위탁 대상 자문재산 평가액", 0, "KRW"),
    ), _C_ADV, ADVISORY_REASON + " 위탁할 자문재산 자체가 없다.")


def _b12101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """전자적 투자조언장치 현황 — 투자자문업 미영위이므로 장치도 없다."""
    return _not_operating((
        ("1000", "운용 중인 전자적 투자조언장치 수", 0, "count"),
        ("1010", "투자자문형", 1, "count"),
        ("1020", "투자일임형", 1, "count"),
        ("2000", "서비스 이용 계약자 수", 0, "count"),
        ("3000", "운용 자산 평가액", 0, "KRW"),
    ), _C_ROBO, ADVISORY_REASON + " 전자적 투자조언장치는 투자자문·일임업 영위를 "
        "전제하므로 장치 자체가 존재하지 않는다.")


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B10101": (_C_RATE, "PRD-RDM", _b10101),
    "B1101": (_C99, "PRD-RDM", _b1101),
    "B1104": (f"{_C_BR} · {_C99}", "PRD-RDM", _b1104),
    "B1105": (f"{_C_EFT} · {_C99}", "PRD-RDM", _b1105),
    "B1107": (f"{_C_BR} · {_C99}", "PRD-RDM", _b1107),
    "B1108": (f"{_C_ANC} · {_C_CON}", "PRD-RDM", _b1108),
    "B1110": (f"{_C_EFT} · {_C99}", "PRD-RDM", _b1110),
    "B11101": (_C_ADV, "PRD-RDM", _b11101),
    "B11102": (_C_ADV, "PRD-RDM", _b11102),
    "B11103": (_C_ADV, "PRD-RDM", _b11103),
    "B11104": (_C_ADV, "PRD-RDM", _b11104),
    "B11105": (_C_ADV, "PRD-RDM", _b11105),
    "B11106": (_C_ADV, "PRD-RDM", _b11106),
    "B11107": (_C_ADV, "PRD-RDM", _b11107),
    "B1111": (f"{_C_EFT} · {_C99}", "PRD-RDM", _b1111),
    "B1112": (f"{_C_EFT} · {_C99}", "PRD-RDM", _b1112),
    "B1115": (_C_OUT, "PRD-RDM", _b1115),
    "B1116": (_C_ITO, "PRD-RDM", _b1116),
    "B12101": (_C_ROBO, "PRD-RDM", _b12101),
    "B8101": (_C_FUND, "PRD-RDM", _b8101),
    "B8102": (_C_FUND, "PRD-RDM", _b8102),
    "B8103": (_C_FUND, "PRD-RDM", _b8103),
    "B8104": (_C_FUND, "PRD-RDM", _b8104),
    "B9101": (_C_DORM, "PRD-ALM", _b9101),
    "B9102": (_C_DORM, "PRD-ALM", _b9102),
    "B9103": (_C_DORM, "PRD-ALM", _b9103),
    "B9104": (_C_DORM, "PRD-ALM", _b9104),
    "B9105": (_C_DORM, "PRD-ALM", _b9105),
    "B9106": (_C_DORM, "PRD-ALM", _b9106),
    "B9107": (_C_DORM, "PRD-ALM", _b9107),
}
