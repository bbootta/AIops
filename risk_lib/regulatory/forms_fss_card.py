"""금감원 FINES 업무보고서 — 신용카드 30건.

근거는 **여신전문금융업법·동 감독규정**이다. 은행업감독규정 조문은 달지 않는다 —
카드채권을 은행 조문으로 근거지으면 겸영은행의 신용카드부문 보고서가 여전업
감독기준과 대사되지 않는다. 다만 자산건전성 5단계 분류와 연체기간 구분은
`rdm_asset_quality`·`rdm_delinquency`의 **산출 정의를 그대로 쓴다**(B2815·B2821·
B2822) — 카드 서식이 자기 나름의 분류를 세우면 B2421·B4101과 어긋난다.

**이 저장소에는 카드 원장이 없다.** 카드채권은 `retail_other`의 부분집합으로
파생하고, 그 익스포저의 잔액·분류·연체·수익·비용은 **전부 산출 실측값**을 쓴다.
회원수·카드수·가맹점수 같은 건수와 상품 구성비만
`forms_fss_card_data`가 기준일 고정 시드로 만든다. 파생값이 들어간 라인은
**그 라인 자체의** formula에 "파생"임을 남긴다 — 상위 소계에만 적어 두면 서식이
flat table로 실체화될 때 하위 셀이 실측으로 읽힌다.

앵커가 아예 없는 것(선불·직불·체크카드, 해외회원, 부정사용, 포인트·선지급)은
formula에 "완전 파생"이라고 적고 비고 라인에 근거 부재를 남긴다.

B2825(가계신용)·B2831(고위험 대출)은 카드가 아니라 **가계여신 전체**가 대상이라
`forms_fss_retail_data.household`의 모집단을 그대로 재사용한다 — 같은 가계여신을
두 모듈이 각자 정의하면 B2426과 대사되지 않는다.

조문 인용은 확정적인 것만 조 번호까지 적고, 서식 별지 수준의 근거는
"여신전문금융업감독규정 업무보고서(FINES) 서식"으로 통일한다. 조 번호와 조 제목은
2026-06-30 기준 현행 법령으로 검증했다 — 자산건전성 분류는 감독규정 **제9조**,
대손충당금은 **제11조**, 신용카드업자의 부대업무는 여전법 **제13조**, 회원 모집은
**제14조의2**다. 우대수수료율은 조문에 숫자가 있는 것이 아니라 제18조의3에 따라
금융위가 고시하는 값이며 2025.2.14 시행분을 쓴다.

**기간 기준 주의.** `portfolio.revenue`·`operating_cost`는 연간이고 이용금액·
매출액은 월이다. 두 기간을 나누는 라인(B2824 수수료율, B2818 1인당 모집비용)은
혼합기준임을 라인명과 비고에 남긴다 — 특히 B2824는 기간을 맞추면 협상요율이
음수가 되어 역산이 성립하지 않는다는 사실까지 공시한다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_card_data import (
    ANCILLARY, AQ_ORDER, COST_ITEMS, CREDIT_SALE, DPD_BANDS, FRAUD_BEARERS,
    LIMIT_BANDS, MERCHANT_TIERS, PREF_FEE_RATE, PRODUCTS, RECRUIT_CHANNELS,
    REVENUE_ITEMS, card_book, card_type_summary, corporate_member, cost_mix,
    credit_cost, fraud_book, member_book, merchant_book, overseas_use,
    point_book, prepaid_book, prepay_service, revenue_mix, rng, tax_payment,
    ticket, turnover, use_total,
)
from risk_lib.regulatory.forms_fss_retail_data import household

_M_RDM = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_PRU = "risk_lib.prudential.financials"
_M_DER = "risk_lib.regulatory.forms_fss_card_data"

# 조문 번호는 2026-06-30 기준 현행 법령으로 검증했다. 조 제목을 그대로 쓴다 —
# 조문 번호와 제목이 어긋나면 대사하는 쪽이 엉뚱한 조문을 편다.
_L2 = "여신전문금융업법 제2조 신용카드·직불카드·선불카드·신용카드가맹점 정의"
_L13 = "여신전문금융업법 제13조 신용카드업자의 부대업무"
_L14 = "여신전문금융업법 제14조 신용카드·직불카드의 발급"
_L14_2 = "여신전문금융업법 제14조의2 신용카드회원의 모집"
_L16 = "여신전문금융업법 제16조 신용카드등의 부정사용에 대한 책임"
_L18_3 = "여신전문금융업법 제18조의3 가맹점수수료율의 차별금지 등"
_L19 = "여신전문금융업법 제19조 신용카드가맹점의 준수사항"
# 자산건전성 분류는 감독규정 제9조, 대손충당금은 제11조다. 제11조의2는
# 주택관련 담보대출 위험관리라 카드채권 서식의 근거가 아니다.
_R9 = "여신전문금융업감독규정 제9조 자산건전성 분류 등"
_R11 = "여신전문금융업감독규정 제11조 대손충당금 등 적립기준"
_RPT = "여신전문금융업감독규정 업무보고서(FINES) 서식"
_COM64 = "상법 제64조 상사소멸시효 5년"

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
_DERIVED_FULL = "앵커할 산출값 없음 — 완전 파생"
_DERIVED_SPLIT = "분할 기준이 파생값 — 금액은 원장 실측"


def _tol(total: float) -> float:
    return max(1.0, abs(total) * 1e-9)


def _ratio(num: float, den: float) -> float:
    return num / den if den else 0.0


def _split_lines(labels, values, base: int, *, level: int = 1, unit: str = "KRW",
                 citation: str, source_module: str, formula=None
                 ) -> tuple[list[FormLine], tuple[str, ...]]:
    """구성항목 한 벌 — 라벨 순서와 코드 순서를 묶어 소계 대사가 흔들리지 않게 한다."""
    L, codes = [], []
    for i, (lab, v) in enumerate(zip(labels, values), start=1):
        code = str(base + i * 10)
        codes.append(code)
        L.append(FormLine(code, str(lab), level, unit, float(v),
                          formula=formula(lab) if callable(formula) else formula,
                          citation=citation, source_module=source_module))
    return L, tuple(codes)


# ---------------------------------------------------------------- B2801

def _b2801(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """회원수 현황 — 개인 본인회원 수는 카드채권 차주의 실측 고유 건수다."""
    cb, m, corp = card_book(ctx), member_book(ctx), corporate_member(ctx)
    own, fam = float(len(m)), float(m["n_family"].sum())
    total = own + fam + corp["members"]
    dormant = float(m["dormant_member"].sum())
    L = [
        FormLine("1000", "총 회원수", 0, "count", total,
                 formula="본인(개인·법인) + 가족회원", citation=_L2,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "본인회원 (개인)", 1, "count", own,
                 formula=f"카드채권 차주 {len(m):,}인 — 실측 고유 건수",
                 citation=_L2, source_module=_M_RDM),
        FormLine("1020", "본인회원 (법인)", 1, "count", corp["members"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("1030", "가족회원", 1, "count", fam, formula=_DERIVED,
                 citation=_L2, source_module=_M_DER),
        FormLine("2000", "유효회원 (최근 1년 이용실적 보유)", 0, "count",
                 total - dormant,
                 formula=f"총 회원수 − 무실적회원 · {_DERIVED} · 무실적 판정은 "
                         "개인 본인회원 단위라 가족·법인회원은 전원 유효로 계상된다",
                 citation=_RPT, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "무실적회원", 0, "count", dormant,
                 formula=f"보유카드 전부가 무실적인 개인 본인회원 · {_DERIVED} · "
                         "분자 모집단은 개인 본인회원뿐이다 (B2803 참조)",
                 citation=_RPT, source_module=_M_DER),
    ]
    gl, gc = _split_lines(
        [f"{g}등급" for g in range(1, 11)],
        [float((cb["grade"] == g).sum()) for g in range(1, 11)], 3000,
        unit="count", citation=_RPT, source_module=_M_RDM,
        formula=lambda lab: "PD 십분위 — 실측 (1등급 최우량)")
    L += gl
    L.append(FormLine("4000", "연체 보유 회원수", 0, "count",
                      float(cb[cb["dpd"] > 0]["obligor_id"].nunique()),
                      formula="rdm_delinquency.dpd > 0 — 실측", citation=_RPT,
                      source_module=_M_RDM))
    checks = [
        _sum_check("총 회원수 = 본인(개인+법인) + 가족", L, "1000",
                   ("1010", "1020", "1030"), 1e-9),
        _sum_check("유효 + 무실적 = 총 회원수", L, "1000", ("2000", "2010"), 1e-9),
        _sum_check("등급별 회원수 합 = 개인 본인회원", L, "1010", gc, 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2802

def _b2802(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """발급수 현황 — 발급매수는 회원별 보유매수 파생의 합이다."""
    m, corp = member_book(ctx), corporate_member(ctx)
    own, fam = float(m["n_card"].sum()), float(m["n_family"].sum())
    total = own + fam + corp["cards"]
    r = rng("발급구분")
    # 당분기 발급구분 비율 — 발급일자 원장이 없어 총 발급매수에서 갈라 낸다.
    new_r, renew_r, reissue_r = (float(r.uniform(0.045, 0.075)),
                                 float(r.uniform(0.055, 0.090)),
                                 float(r.uniform(0.015, 0.035)))
    new, renew, reissue = total * new_r, total * renew_r, total * reissue_r
    L = [
        FormLine("1000", "신용카드 총 발급매수", 0, "count", total,
                 formula="본인(개인·법인) + 가족카드", citation=_L14,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "개인 본인카드", 1, "count", own,
                 formula=f"회원당 보유매수 · {_DERIVED}", citation=_L14,
                 source_module=_M_DER),
        FormLine("1020", "가족카드", 1, "count", fam, formula=_DERIVED,
                 citation=_L14, source_module=_M_DER),
        FormLine("1030", "법인카드", 1, "count", corp["cards"],
                 formula=_DERIVED_FULL, citation=_L14, source_module=_M_DER),
        FormLine("1040", "회원 1인당 보유매수", 0, "ratio",
                 _ratio(total, float(len(m) + m["n_family"].sum()
                                     + corp["members"])),
                 formula="총 발급매수 ÷ 총 회원수", citation=_RPT,
                 source_module=_M_DER),
        FormLine("2000", "당분기 발급매수", 0, "count", new + renew + reissue,
                 formula=f"신규 + 갱신 + 재발급 · {_DERIVED}", citation=_L14,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "신규발급", 1, "count", new,
                 formula=f"총 발급매수 × {new_r:.2%} · {_DERIVED}", citation=_L14,
                 source_module=_M_DER),
        FormLine("2020", "갱신발급", 1, "count", renew,
                 formula=f"총 발급매수 × {renew_r:.2%} · {_DERIVED}", citation=_L14,
                 source_module=_M_DER),
        FormLine("2030", "재발급", 1, "count", reissue,
                 formula=f"총 발급매수 × {reissue_r:.2%} · {_DERIVED}",
                 citation=_L14, source_module=_M_DER),
    ]
    checks = [
        _sum_check("총 발급매수 = 개인 + 가족 + 법인", L, "1000",
                   ("1010", "1020", "1030"), 1e-9),
        _sum_check("당분기 발급 = 신규 + 갱신 + 재발급", L, "2000",
                   ("2010", "2020", "2030"), 1e-6),
        FormCheck("당분기 발급매수 ≤ 총 발급매수", 0.0,
                  max(0.0, _val(L, "2000") - total), 1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B2803

def _b2803(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """무실적 현황 — 무실적 판정 모집단은 개인카드(본인+가족)다."""
    m, corp = member_book(ctx), corporate_member(ctx)
    held = float(m["n_held"].sum())
    dorm_card = float(m["n_dormant"].sum())
    dorm_mem = float(m["dormant_member"].sum())
    members = float(len(m) + m["n_family"].sum() + corp["members"])
    r = rng("무실적기간")
    long_share = float(r.uniform(0.30, 0.45))      # 2년 이상 무실적 비중
    L = [
        FormLine("1000", "총 회원수", 0, "count", members,
                 formula="B2801 총 회원수와 같은 모집단", citation=_RPT,
                 source_module=_M_DER),
        FormLine("1005", "무실적 판정 모집단 (개인 본인회원)", 0, "count",
                 float(len(m)),
                 formula="판정은 본인회원 단위 — 가족·법인회원은 판정 대상이 아니다",
                 citation=_RPT, source_module=_M_DER),
        FormLine("1010", "무실적 회원수 (1년 이상)", 0, "count", dorm_mem,
                 formula=f"보유카드 전부 무실적 · {_DERIVED}", citation=_RPT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "무실적 회원 비율 (판정 모집단 기준)", 0, "ratio",
                 _ratio(dorm_mem, float(len(m))),
                 formula="무실적 회원수 ÷ 개인 본인회원 — 분자·분모 모집단을 맞춘다",
                 citation=_RPT, source_module=_M_DER),
        FormLine("1021", "무실적 회원 비율 (총 회원수 기준)", 0, "ratio",
                 _ratio(dorm_mem, members),
                 formula="무실적 회원수 ÷ 총 회원수 — 분모에 판정 대상이 아닌 "
                         "가족·법인회원이 들어가 과소계상된다",
                 citation=_RPT, source_module=_M_DER),
        FormLine("2000", "개인 발급카드수", 0, "count", held,
                 formula="본인카드 + 가족카드 (법인카드 제외)", citation=_RPT,
                 source_module=_M_DER),
        FormLine("2010", "무실적 카드수 (1년 이상)", 0, "count", dorm_card,
                 formula=_DERIVED, citation=_RPT, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("2011", "1년 이상 2년 미만", 1, "count",
                 dorm_card * (1.0 - long_share),
                 formula=f"무실적 카드 × {1.0 - long_share:.1%} · {_DERIVED}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("2012", "2년 이상", 1, "count", dorm_card * long_share,
                 formula=f"무실적 카드 × {long_share:.1%} · {_DERIVED}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("2020", "무실적 카드 비율", 0, "ratio", _ratio(dorm_card, held),
                 formula="무실적 카드수 ÷ 개인 발급카드수", citation=_RPT,
                 source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="법인카드는 법인 단위 이용실적이라 개인카드의 휴면 "
                            "판정 기준을 적용할 수 없어 모집단에서 제외한다. "
                            "가족회원은 본인회원에 딸린 카드만 있고 회원 단위 "
                            "이용실적이 없어 휴면 판정을 본인회원(세대) 단위로 "
                            "한다 — 무실적 회원수의 분자는 개인 본인회원뿐이므로 "
                            "총 회원수로 나눈 라인 1021은 과소계상된다.",
                 citation=_RPT),
    ]
    checks = [
        _sum_check("기간별 무실적 카드 합 = 무실적 카드수", L, "2010",
                   ("2011", "2012"), 1e-6),
        _ratio_check("무실적 회원 비율 (판정 모집단)", L, "1020", "1010", "1005"),
        _ratio_check("무실적 회원 비율 (총 회원수)", L, "1021", "1010", "1000"),
        _ratio_check("무실적 카드 비율", L, "2020", "2010", "2000"),
        FormCheck("무실적 카드 ≤ 개인 발급카드", 0.0,
                  max(0.0, dorm_card - held), 1e-6),
        FormCheck("판정 모집단 ≤ 총 회원수", 0.0,
                  max(0.0, float(len(m)) - members), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2804

def _b2804(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """가맹점 현황 — 매출액 총액은 신용판매 이용금액에 앵커한다."""
    mk = merchant_book(ctx)
    n_total = float(mk["merchants"].sum())
    s_total = float(mk["sales"].sum())
    pref = mk[mk["tier"] != MERCHANT_TIERS[-1]]
    L = [
        FormLine("1000", "총 가맹점수", 0, "count", n_total,
                 formula=f"구간별 매출액 ÷ 구간 대표 연매출 · {_DERIVED}",
                 citation=_L19, source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "가맹점 매출액 (당월 신용판매)", 0, "KRW", s_total,
                 formula="일시불 + 할부 이용금액 — 카드채권 잔액에 앵커",
                 citation=_L19, source_module=_M_DER, is_subtotal=True),
    ]
    nl, nc = _split_lines(mk["tier"], mk["merchants"], 3000, unit="count",
                          citation=_L18_3, source_module=_M_DER,
                          formula=lambda lab: f"연매출 구간 배분 · {_DERIVED}")
    sl, sc = _split_lines(mk["tier"], mk["sales"], 4000, citation=_L18_3,
                          source_module=_M_DER,
                          formula=lambda lab: "매출 구성비 파생 · 총액은 앵커")
    L += nl + sl + [
        FormLine("5000", "우대수수료율 적용 가맹점수", 0, "count",
                 float(pref["merchants"].sum()),
                 formula="연매출 30억원 이하 영세·중소가맹점", citation=_L18_3,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("5010", "우대 적용 비율", 0, "ratio",
                 _ratio(float(pref["merchants"].sum()), n_total),
                 formula="우대 적용 가맹점수 ÷ 총 가맹점수", citation=_L18_3,
                 source_module=_M_DER),
        FormLine("5020", "가맹점당 평균 연매출", 0, "KRW",
                 _ratio(s_total * 12.0, n_total),
                 formula="매출액 × 12 ÷ 가맹점수", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(s_total)
    checks = [
        _sum_check("구간별 가맹점수 합 = 총 가맹점수", L, "1000", nc, 1e-9),
        _sum_check("구간별 매출액 합 = 총 매출액", L, "2000", sc, t),
        _sum_check("우대 적용 가맹점수 = 영세 + 중소1~3", L, "5000", nc[:-1], 1e-9),
        _ratio_check("우대 적용 비율", L, "5010", "5000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2805

def _b2805(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """국내회원 이용실적 — 상품별 잔액 합은 카드채권 실측 잔액과 정확히 같다."""
    cb, m = card_book(ctx), member_book(ctx)
    tv, tk = turnover(), ticket()
    bal = float(cb["balance"].sum())
    use = use_total(cb)
    cnt = float(sum(cb[f"cnt_{p}"].sum() for p in PRODUCTS))
    L = [
        FormLine("1000", "총 이용금액", 0, "KRW", use,
                 formula=f"상품별 잔액 × 월 회전율 · 회전율은 {_DERIVED}",
                 citation=_RPT, source_module=_M_DER, is_subtotal=True),
    ]
    ul, uc = _split_lines(PRODUCTS, [float(cb[f"use_{p}"].sum()) for p in PRODUCTS],
                          1000, citation=_RPT, source_module=_M_DER,
                          formula=lambda lab: f"월 회전율 {tv[lab]:.2f}회 · {_DERIVED}")
    L += ul
    L.append(FormLine("2000", "총 이용건수", 0, "count", cnt,
                      formula=f"이용금액 ÷ 건당 평균이용액 · {_DERIVED}",
                      citation=_RPT, source_module=_M_DER, is_subtotal=True))
    cl, cc = _split_lines(PRODUCTS, [float(cb[f"cnt_{p}"].sum()) for p in PRODUCTS],
                          2000, unit="count", citation=_RPT, source_module=_M_DER,
                          formula=lambda lab: f"건당 {tk[lab]:,.0f}원 가정 · {_DERIVED}")
    L += cl
    L.append(FormLine("3000", "카드채권 잔액", 0, "KRW", bal,
                      formula=f"rdm_asset_quality.balance 실측 · {len(cb):,}건",
                      citation=_R9, source_module=_M_RDM, is_subtotal=True))
    bl, bc = _split_lines(PRODUCTS, [float(cb[f"bal_{p}"].sum()) for p in PRODUCTS],
                          3000, citation=_RPT, source_module=_M_DER,
                          formula=lambda lab: _DERIVED_SPLIT)
    L += bl
    L.append(FormLine("4000", "회원 1인당 이용금액", 0, "KRW",
                      _ratio(use, float(len(m))),
                      formula="총 이용금액 ÷ 개인 본인회원", citation=_RPT,
                      source_module=_M_DER))
    t = _tol(max(use, bal))
    checks = [
        _sum_check("상품별 이용금액 합 = 총 이용금액", L, "1000", uc, t),
        _sum_check("상품별 이용건수 합 = 총 이용건수", L, "2000", cc, 1e-6),
        _sum_check("상품별 잔액 합 = 카드채권 잔액", L, "3000", bc, t),
        # 1인당 이용금액의 분모(회원수)는 라인이 아니라 회원 원장에서 오므로
        # _ratio_check를 쓸 수 없다 — 분모를 직접 놓고 대사한다.
        FormCheck("1인당 이용금액 × 회원수 = 총 이용금액", use,
                  _val(L, "4000") * float(len(m)), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2806

def _b2806(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """해외회원의 국내이용실적 — 카드채권 차주가 전부 국내라 완전 파생이다."""
    ov = overseas_use(ctx)
    cb = card_book(ctx)
    dom = use_total(cb, CREDIT_SALE)
    total = float(ov["amount"].sum())
    L = [
        FormLine("1000", "해외회원 국내이용금액", 0, "KRW", total,
                 formula=f"{_DERIVED_FULL} — 국내회원 신용판매 대비 비율", citation=_L2,
                 source_module=_M_DER, is_subtotal=True),
    ]
    al, ac = _split_lines([f"발행국 · {c}" for c in ov["country"]], ov["amount"],
                          2000, citation=_L2, source_module=_M_DER,
                          formula=lambda lab: _DERIVED_FULL)
    L += al
    L += [
        FormLine("3000", "해외회원 이용건수", 0, "count", float(ov["cases"].sum()),
                 formula=_DERIVED_FULL, citation=_RPT, source_module=_M_DER),
        FormLine("4000", "국내회원 신용판매 이용금액", 0, "KRW", dom,
                 formula="일시불 + 할부 — 카드채권 잔액에 앵커", citation=_RPT,
                 source_module=_M_DER),
        FormLine("4010", "국내회원 대비 비중", 0, "ratio", _ratio(total, dom),
                 formula="해외회원 이용금액 ÷ 국내회원 신용판매", citation=_RPT,
                 source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="카드채권 차주는 전부 국내(KR) 거주이고 해외 발행 카드 "
                            "원장이 없다. 발행국 구분만 포트폴리오의 국가 도메인에서 "
                            "가져오고 금액·건수는 앵커 없는 파생값이다.",
                 citation=_RPT),
    ]
    checks = [
        _sum_check("발행국별 합 = 해외회원 이용금액", L, "1000", ac, _tol(total)),
        _ratio_check("국내회원 대비 비중", L, "4010", "1000", "4000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2808

def _b2808(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """선불카드 이용 현황(유효기간 경과전) — 앵커할 산출값이 없는 완전 파생이다."""
    pre = prepaid_book(ctx)
    L = [
        FormLine("1000", "선불카드 발행액", 0, "KRW", pre["issued"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1010", "사용액", 1, "KRW", pre["used"], formula=_DERIVED_FULL,
                 citation=_L2, source_module=_M_DER),
        FormLine("1020", "미사용잔액", 1, "KRW", pre["unused"],
                 formula="발행액 − 사용액", citation=_L2, source_module=_M_DER),
        FormLine("2000", "유효기간 경과전 미사용잔액", 0, "KRW",
                 pre["unused_valid"], formula=_DERIVED_FULL, citation=_L2,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "유효기간 경과 미사용잔액", 0, "KRW", pre["expired"],
                 formula=f"{_DERIVED_FULL} — B2828에서 소멸시효를 따로 본다",
                 citation=_COM64, source_module=_M_DER),
        FormLine("3000", "발행좌수", 0, "count", pre["issued_cards"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("3010", "좌당 평균 발행액", 0, "KRW",
                 _ratio(pre["issued"], pre["issued_cards"]),
                 formula="발행액 ÷ 발행좌수", citation=_RPT, source_module=_M_DER),
        FormLine("4000", "사용률", 0, "ratio", _ratio(pre["used"], pre["issued"]),
                 formula="사용액 ÷ 발행액", citation=_RPT, source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="선불카드 원장이 없어 발행·사용·잔액이 모두 파생값이다. "
                            "발행액 − 사용액 = 미사용잔액 항등식만 파생 안에서 닫힌다.",
                 citation=_RPT),
    ]
    t = _tol(pre["issued"])
    checks = [
        _sum_check("발행액 = 사용액 + 미사용잔액", L, "1000", ("1010", "1020"), t),
        _sum_check("미사용잔액 = 경과전 + 경과", L, "1020", ("2000", "2010"), t),
        _ratio_check("좌당 평균 발행액", L, "3010", "1000", "3000", 1e-6),
        _ratio_check("사용률", L, "4000", "1010", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2809

def _b2809(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """직불카드 이용 현황 — 예금계좌 연동이라 카드채권 잔액이 없다."""
    cts = card_type_summary(ctx)
    row = cts[cts["card_type"] == "직불카드"].iloc[0]
    credit = float(cts[cts["card_type"] == "신용카드"]["usage"].iloc[0])
    r = rng("직불건당")
    tk = float(r.uniform(3.0e4, 6.0e4))
    cases = _ratio(float(row["usage"]), tk)
    L = [
        FormLine("1000", "직불카드 발급매수", 0, "count", float(row["cards"]),
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("1010", "이용회원수", 0, "count", float(row["members"]),
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("2000", "이용금액", 0, "KRW", float(row["usage"]),
                 formula=f"{_DERIVED_FULL} — 신용카드 이용금액 대비 배수",
                 citation=_L2, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "이용건수", 0, "count", cases,
                 formula=f"이용금액 ÷ 건당 {tk:,.0f}원 · {_DERIVED_FULL}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("3000", "회원 1인당 이용금액", 0, "KRW",
                 _ratio(float(row["usage"]), float(row["members"])),
                 formula="이용금액 ÷ 이용회원수", citation=_RPT,
                 source_module=_M_DER),
        FormLine("4000", "신용카드 이용금액", 0, "KRW", credit,
                 formula="B2805 총 이용금액", citation=_RPT, source_module=_M_DER),
        FormLine("4010", "신용카드 대비 비중", 0, "ratio",
                 _ratio(float(row["usage"]), credit),
                 formula="직불카드 이용금액 ÷ 신용카드 이용금액", citation=_RPT,
                 source_module=_M_DER),
    ]
    checks = [
        _ratio_check("1인당 이용금액", L, "3000", "2000", "1010", 1e-6),
        _ratio_check("신용카드 대비 비중", L, "4010", "2000", "4000"),
        FormCheck("직불카드 이용금액 ≤ 신용카드 이용금액", 0.0,
                  max(0.0, float(row["usage"]) - credit), _tol(credit)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2810

def _b2810(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """부정사용 책임분담 — 운영손실 원장에 외부사기 사건유형이 없어 완전 파생이다."""
    fb = fraud_book(ctx)
    cb = card_book(ctx)
    use = use_total(cb)
    total = float(fb["amount"].sum())
    L = [
        FormLine("1000", "부정사용 금액", 0, "KRW", total,
                 formula=f"이용금액 대비 bps · {_DERIVED_FULL}", citation=_L16,
                 source_module=_M_DER, is_subtotal=True),
    ]
    tl, tc = _split_lines([f"유형 · {t}" for t in fb["fraud_type"]], fb["amount"],
                          1000, citation=_L16, source_module=_M_DER,
                          formula=lambda lab: _DERIVED_FULL)
    L += tl
    bl, bc = _split_lines([f"책임분담 · {b}" for b in FRAUD_BEARERS],
                          [float(fb[b].sum()) for b in FRAUD_BEARERS], 2000,
                          citation=_L16, source_module=_M_DER,
                          formula=lambda lab: "제16조 원칙(원칙적 카드사 부담)을 "
                                              f"반영한 파생 구성비 · {_DERIVED_FULL}")
    L += bl
    L += [
        FormLine("3000", "부정사용 건수", 0, "count", float(fb.attrs["cases"]),
                 formula=f"{_DERIVED_FULL} — 유형별 건수는 만들지 않는다",
                 citation=_L16, source_module=_M_DER),
        FormLine("4000", "총 이용금액", 0, "KRW", use,
                 formula="B2805 총 이용금액", citation=_RPT, source_module=_M_DER),
        FormLine("4010", "부정사용 비율", 0, "ratio", _ratio(total, use),
                 formula="부정사용 금액 ÷ 총 이용금액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="opr_loss_event의 사건유형이 execution_delivery 하나뿐이라 "
                            "외부사기 손실로 앵커할 수 없다. 금액·건수·분담비율이 "
                            "모두 파생값이다.",
                 citation=_L16),
    ]
    t = _tol(max(total, 1.0))
    checks = [
        _sum_check("유형별 합 = 부정사용 금액", L, "1000", tc, t),
        _sum_check("책임분담 합 = 부정사용 금액", L, "1000", bc, t),
        _ratio_check("부정사용 비율", L, "4010", "1000", "4000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2811

def _b2811(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """부대업무비중 — 구분은 제13조(신용카드업자의 부대업무) 정의를 따른다.

    제13조제1항제1호의 부대업무는 "신용카드회원에 대한 자금의 융통"이라 현금서비스·
    카드론이 확실히 들어간다. 리볼빙은 신용판매 대금의 이월이어서 자금융통 해당
    여부가 판단사항이므로 제1호 기준 잔액을 별도 라인으로 두고 비고에 남긴다.
    """
    cb = card_book(ctx)
    bal = float(cb["balance"].sum())
    sale = float(sum(cb[f"bal_{p}"].sum() for p in CREDIT_SALE))
    anc = float(sum(cb[f"bal_{p}"].sum() for p in ANCILLARY))
    fin = float(sum(cb[f"bal_{p}"].sum() for p in ("현금서비스", "카드론")))
    L = [
        FormLine("1000", "카드채권 총 잔액", 0, "KRW", bal,
                 formula=f"rdm_asset_quality.balance 실측 · {len(cb):,}건",
                 citation=_R9, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "신용판매 채권", 1, "KRW", sale,
                 formula=f"일시불 + 할부 · {_DERIVED_SPLIT}", citation=_L13,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "부대업무 채권", 1, "KRW", anc,
                 formula=f"현금서비스 + 카드론 + 리볼빙 · {_DERIVED_SPLIT}",
                 citation=_L13, source_module=_M_DER, is_subtotal=True),
        FormLine("1030", "부대업무 비중", 0, "ratio", _ratio(anc, bal),
                 formula="부대업무 채권 ÷ 카드채권 총 잔액", citation=_L13,
                 source_module=_M_DER),
        FormLine("1040", "자금융통 채권 (제13조제1항제1호)", 1, "KRW", fin,
                 formula=f"현금서비스 + 카드론 · 리볼빙 제외 · {_DERIVED_SPLIT}",
                 citation=_L13, source_module=_M_DER, is_subtotal=True),
        FormLine("1050", "자금융통 비중 (제1호 기준)", 0, "ratio",
                 _ratio(fin, bal),
                 formula="자금융통 채권 ÷ 카드채권 총 잔액", citation=_L13,
                 source_module=_M_DER),
    ]
    sl, sc = _split_lines(CREDIT_SALE,
                          [float(cb[f"bal_{p}"].sum()) for p in CREDIT_SALE], 2000,
                          level=2, citation=_L13, source_module=_M_DER,
                          formula=lambda lab: _DERIVED_SPLIT)
    al, ac = _split_lines(ANCILLARY,
                          [float(cb[f"bal_{p}"].sum()) for p in ANCILLARY], 3000,
                          level=2, citation=_L13, source_module=_M_DER,
                          formula=lambda lab: _DERIVED_SPLIT)
    L += sl + al
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value="부대업무 채권에는 리볼빙을 포함했다. 제13조제1항"
                                 "제1호의 부대업무는 '신용카드회원에 대한 자금의 "
                                 "융통'이고 리볼빙은 신용판매 대금의 이월이어서 "
                                 "해당 여부가 판단사항이다 — 제1호만으로 본 잔액은 "
                                 "라인 1040·1050에 따로 뒀다. 상품 배분 자체는 "
                                 "실측 PD·한도소진율의 함수이나 원장이 아니다.",
                      citation=_L13))
    t = _tol(bal)
    checks = [
        _sum_check("신용판매 + 부대업무 = 카드채권 총 잔액", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("신용판매 세부 합 = 신용판매 채권", L, "1010", sc, t),
        _sum_check("부대업무 세부 합 = 부대업무 채권", L, "1020", ac, t),
        _sum_check("자금융통 채권 = 현금서비스 + 카드론", L, "1040",
                   (ac[0], ac[1]), t),
        _ratio_check("부대업무 비중", L, "1030", "1020", "1000"),
        _ratio_check("자금융통 비중 (제1호 기준)", L, "1050", "1040", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2812

def _b2812(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """리볼빙 결제제도 — 이월잔액은 실측 잔액의 배분이고 연체는 실측이다."""
    cb, m = card_book(ctx), member_book(ctx)
    bal = float(cb["balance"].sum())
    rev = float(cb["bal_리볼빙"].sum())
    delinq = float(cb[cb["dpd"] > 0]["bal_리볼빙"].sum())
    r = rng("리볼빙약정")
    agree = float(int(len(m) * float(r.uniform(0.18, 0.32))))
    pay_rate = float(r.uniform(0.08, 0.16))
    L = [
        FormLine("1000", "리볼빙 이월잔액", 0, "KRW", rev,
                 formula=f"카드채권 잔액의 상품 배분 · {_DERIVED_SPLIT}",
                 citation=_RPT, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "카드채권 총 잔액", 0, "KRW", bal,
                 formula="rdm_asset_quality.balance 실측", citation=_R9,
                 source_module=_M_RDM),
        FormLine("1020", "카드채권 대비 비중", 0, "ratio", _ratio(rev, bal),
                 formula="리볼빙 이월잔액 ÷ 카드채권 총 잔액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("2000", "리볼빙 약정회원수", 0, "count", agree,
                 formula=_DERIVED, citation=_RPT, source_module=_M_DER),
        FormLine("2010", "약정회원 1인당 이월잔액", 0, "KRW", _ratio(rev, agree),
                 formula="이월잔액 ÷ 약정회원수", citation=_RPT,
                 source_module=_M_DER),
        FormLine("3000", "리볼빙 이용금액", 0, "KRW", float(cb["use_리볼빙"].sum()),
                 formula=f"이월잔액 × 월 회전율 · {_DERIVED}", citation=_RPT,
                 source_module=_M_DER),
        FormLine("3010", "평균 약정결제비율", 0, "ratio", pay_rate,
                 formula=_DERIVED, citation=_RPT, source_module=_M_DER),
        FormLine("4000", "리볼빙 연체잔액", 0, "KRW", delinq,
                 formula="dpd > 0 익스포저의 리볼빙 배분액 — 연체 판정은 실측",
                 citation=_R9, source_module=_M_RDM, is_subtotal=True),
        FormLine("4010", "리볼빙 연체율", 0, "ratio", _ratio(delinq, rev),
                 formula="리볼빙 연체잔액 ÷ 리볼빙 이월잔액", citation=_RPT,
                 source_module=_M_RDM),
    ]
    t = _tol(bal)
    checks = [
        _ratio_check("카드채권 대비 비중", L, "1020", "1000", "1010"),
        _ratio_check("약정회원 1인당 이월잔액", L, "2010", "1000", "2000", 1e-6),
        _ratio_check("리볼빙 연체율", L, "4010", "4000", "1000"),
        FormCheck("리볼빙 연체잔액 ≤ 이월잔액", 0.0, max(0.0, delinq - rev), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2813

def _b2813(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """등급별 수수료율(이자율) — 요율이 파생이 아니라 실측 수익 ÷ 실측 잔액이다."""
    cb, rm = card_book(ctx), revenue_mix(ctx)
    g = (rm.groupby("grade", as_index=False)
         .agg(balance=("balance", "sum"), loan=("카드론이자수익", "sum"),
              cash=("현금서비스수수료수익", "sum"))
         .sort_values("grade"))
    n_ob = cb.groupby("grade")["obligor_id"].nunique()
    bal = float(g["balance"].sum())
    loan = float(g["loan"].sum())
    L = [
        FormLine("1000", "카드채권 잔액", 0, "KRW", bal,
                 formula="등급별 합계 — rdm_asset_quality.balance 실측",
                 citation=_R9, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "카드론 이자수익", 0, "KRW", loan,
                 formula="portfolio.revenue 실측의 상품 배분", citation=_RPT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "가중평균 실효이자율", 0, "ratio", _ratio(loan, bal),
                 formula="카드론 이자수익 ÷ 카드채권 잔액", citation=_RPT,
                 source_module=_M_DER),
    ]
    cash = float(g["cash"].sum())
    L.append(FormLine("1030", "현금서비스 수수료수익", 0, "KRW", cash,
                      formula="portfolio.revenue 실측의 상품 배분", citation=_RPT,
                      source_module=_M_DER, is_subtotal=True))
    L.append(FormLine("1040", "가중평균 현금서비스 실효수수료율", 0, "ratio",
                      _ratio(cash, bal),
                      formula="현금서비스 수수료수익 ÷ 카드채권 잔액", citation=_RPT,
                      source_module=_M_DER))
    bal_c, loan_c, cash_c, rate_c, crate_c = [], [], [], [], []
    for _, r in g.iterrows():
        base = 2000 + int(r["grade"]) * 100
        bal_c.append(str(base + 10))
        loan_c.append(str(base + 20))
        cash_c.append(str(base + 35))
        rate_c.append((str(base + 30), str(base + 20), str(base + 10)))
        crate_c.append((str(base + 40), str(base + 35), str(base + 10)))
        L += [
            FormLine(str(base), f"{int(r['grade'])}등급", 1, "count",
                     float(n_ob.get(int(r["grade"]), 0)),
                     formula="PD 십분위 — 실측 (1등급 최우량)", citation=_RPT,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "잔액", 2, "KRW", float(r["balance"]),
                     citation=_R9, source_module=_M_RDM),
            FormLine(str(base + 20), "카드론 이자수익", 2, "KRW", float(r["loan"]),
                     citation=_RPT, source_module=_M_DER),
            FormLine(str(base + 30), "실효이자율", 2, "ratio",
                     _ratio(float(r["loan"]), float(r["balance"])),
                     formula="등급별 이자수익 ÷ 등급별 잔액 — 실측", citation=_RPT,
                     source_module=_M_DER),
            # 요율만 두고 분자를 빼면 등급별 요율을 대사할 수 없다 — 분자를 함께 낸다.
            FormLine(str(base + 35), "현금서비스 수수료수익", 2, "KRW",
                     float(r["cash"]), citation=_RPT, source_module=_M_DER),
            FormLine(str(base + 40), "현금서비스 실효수수료율", 2, "ratio",
                     _ratio(float(r["cash"]), float(r["balance"])),
                     formula="등급별 현금서비스 수수료수익 ÷ 등급별 잔액 — 실측",
                     citation=_RPT, source_module=_M_DER),
        ]
    t = _tol(bal)
    checks = [
        _sum_check("등급별 잔액 합 = 카드채권 잔액", L, "1000", tuple(bal_c), t),
        _sum_check("등급별 이자수익 합 = 카드론 이자수익", L, "1010",
                   tuple(loan_c), _tol(loan)),
        _sum_check("등급별 현금서비스 수수료수익 합 = 합계", L, "1030",
                   tuple(cash_c), _tol(cash)),
        _ratio_check("가중평균 실효이자율", L, "1020", "1010", "1000"),
        _ratio_check("가중평균 현금서비스 실효수수료율", L, "1040", "1030", "1000"),
    ] + [_ratio_check(f"{i + 1}등급 실효이자율", L, rc, nc, dc)
         for i, (rc, nc, dc) in enumerate(rate_c)
         ] + [_ratio_check(f"{i + 1}등급 현금서비스 실효수수료율", L, rc, nc, dc)
              for i, (rc, nc, dc) in enumerate(crate_c)]
    return L, checks


# ---------------------------------------------------------------- B2814

def _b2814(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """한도금액별 이용한도·이용실적 — 한도는 잔액 ÷ 소진율 역산(실측)이다."""
    cb = card_book(ctx)
    lim = float(cb["limit"].sum())
    bal = float(cb["balance"].sum())
    L = [
        FormLine("1000", "총 이용한도", 0, "KRW", lim,
                 formula="잔액 ÷ 한도소진율 역산 — 실측 두 열의 함수",
                 citation=_RPT, source_module=_M_PTF, is_subtotal=True),
        FormLine("1010", "총 이용실적 (잔액)", 0, "KRW", bal,
                 formula="rdm_asset_quality.balance 실측", citation=_R9,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "한도소진율", 0, "ratio", _ratio(bal, lim),
                 formula="이용실적 ÷ 이용한도", citation=_RPT,
                 source_module=_M_PTF),
    ]
    lim_c, bal_c, util_c, cnt_c = [], [], [], []
    for i, (_, label) in enumerate(LIMIT_BANDS, start=1):
        s = cb[cb["limit_band"] == label]
        base = 2000 + i * 100
        lim_c.append(str(base + 10))
        bal_c.append(str(base + 20))
        cnt_c.append(str(base))
        util_c.append((str(base + 30), str(base + 20), str(base + 10)))
        L += [
            FormLine(str(base), label, 1, "count", float(len(s)),
                     formula="구간 경계는 가정 — FINES 별지 구간표 부재",
                     citation=_RPT, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "이용한도", 2, "KRW", float(s["limit"].sum()),
                     citation=_RPT, source_module=_M_PTF),
            FormLine(str(base + 20), "이용실적 (잔액)", 2, "KRW",
                     float(s["balance"].sum()), citation=_R9,
                     source_module=_M_RDM),
            FormLine(str(base + 30), "한도소진율", 2, "ratio",
                     _ratio(float(s["balance"].sum()), float(s["limit"].sum())),
                     formula="구간 이용실적 ÷ 구간 이용한도", citation=_RPT,
                     source_module=_M_PTF),
        ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value="한도소진율이 2% 미만인 계좌는 한도가 발산하므로 "
                                 "2%에서 잘랐다 — 그 계좌의 이용한도는 과소평가된다.",
                      citation=_RPT))
    t = _tol(lim)
    checks = [
        _sum_check("구간별 이용한도 합 = 총 이용한도", L, "1000", tuple(lim_c), t),
        _sum_check("구간별 이용실적 합 = 총 이용실적", L, "1010", tuple(bal_c), t),
        _ratio_check("한도소진율", L, "1020", "1010", "1000"),
        FormCheck("이용실적 ≤ 이용한도", 0.0, max(0.0, bal - lim), t),
        FormCheck("구간별 계좌수 합 = 카드채권 건수", float(len(cb)),
                  sum(_val(L, c) for c in cnt_c), 1e-9),
    ] + [_ratio_check(f"{LIMIT_BANDS[i][1]} 한도소진율", L, rc, nc, dc)
         for i, (rc, nc, dc) in enumerate(util_c)]
    return L, checks


# ---------------------------------------------------------------- B2815

def _b2815(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """연체채권비율(대환포함) — 대환은 연체와 겹치지 않게 파생해 중복계상을 막는다."""
    cb = card_book(ctx)
    bal = float(cb["balance"].sum())
    d1 = float(cb[cb["dpd"] >= 30]["balance"].sum())
    d_under = float(cb[(cb["dpd"] > 0) & (cb["dpd"] < 30)]["balance"].sum())
    roll = float(cb[cb["is_rollover"]]["balance"].sum())
    overlap = float(cb[cb["is_rollover"] & (cb["dpd"] > 0)]["balance"].sum())
    L = [
        FormLine("1000", "카드채권 잔액", 0, "KRW", bal,
                 formula=f"rdm_asset_quality.balance 실측 · {len(cb):,}건",
                 citation=_R9, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "1개월 미만 연체채권", 1, "KRW", d_under,
                 formula="0 < dpd < 30 — 실측", citation=_R9,
                 source_module=_M_RDM),
        FormLine("1020", "1개월 이상 연체채권", 1, "KRW", d1,
                 formula="dpd ≥ 30 — 실측", citation=_R9, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1030", "대환대출 잔액", 1, "KRW", roll,
                 formula=f"연체 없이 정상 분류된 고PD 계좌에서 파생 · {_DERIVED}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("2000", "대환포함 연체채권", 0, "KRW", d1 + roll,
                 formula="1개월 이상 연체채권 + 대환대출 — 모집단이 겹치지 않는다",
                 citation=_RPT, source_module=_M_DER, is_subtotal=True),
        FormLine("3000", "연체채권비율 (대환 제외)", 0, "ratio", _ratio(d1, bal),
                 formula="1개월 이상 연체채권 ÷ 카드채권 잔액", citation=_R9,
                 source_module=_M_RDM),
        FormLine("3010", "연체채권비율 (대환 포함)", 0, "ratio",
                 _ratio(d1 + roll, bal),
                 formula="대환포함 연체채권 ÷ 카드채권 잔액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("4000", "대환대출 건수", 0, "count",
                 float(int(cb["is_rollover"].sum())), formula=_DERIVED,
                 citation=_RPT, source_module=_M_DER),
    ]
    t = _tol(bal)
    checks = [
        _sum_check("대환포함 연체채권 = 1개월 이상 연체 + 대환", L, "2000",
                   ("1020", "1030"), t),
        _ratio_check("연체채권비율 (대환 제외)", L, "3000", "1020", "1000"),
        _ratio_check("연체채권비율 (대환 포함)", L, "3010", "2000", "1000"),
        FormCheck("대환 ∩ 연체 = 0 (중복계상 없음)", 0.0, overlap, t),
        FormCheck("대환포함 연체채권 ≤ 카드채권 잔액", 0.0,
                  max(0.0, d1 + roll - bal), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2816

def _b2816(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """수익구조 — 합계는 실측 revenue 합이라 손익계산서와 어긋나지 않는다."""
    cb, rm = card_book(ctx), revenue_mix(ctx)
    inc = ctx.tables["pru_income_statement"]
    op_rev = float(inc.loc[inc["item"] == "영업수익", "amount"].iloc[0])
    total = float(cb["revenue"].sum())
    bal = float(cb["balance"].sum())
    L = [
        FormLine("1000", "카드부문 총수익 (연간)", 0, "KRW", total,
                 formula=f"portfolio.revenue(= ead × 연간 스프레드) 실측 합 · "
                         f"카드 익스포저 {len(cb):,}건 · 연간 기준",
                 citation=_RPT, source_module=_M_PTF, is_subtotal=True),
    ]
    il, ic = _split_lines(REVENUE_ITEMS, [float(rm[i].sum()) for i in REVENUE_ITEMS],
                          1000, citation=_RPT, source_module=_M_DER,
                          formula=lambda lab: f"구성비만 파생 · {_DERIVED_SPLIT}")
    L += il + [
        FormLine("2000", "은행 영업수익", 0, "KRW", op_rev,
                 formula="pru_income_statement 영업수익", citation=_RPT,
                 source_module=_M_PRU),
        FormLine("2010", "카드부문 비중", 0, "ratio", _ratio(total, op_rev),
                 formula="카드부문 총수익 ÷ 은행 영업수익", citation=_RPT,
                 source_module=_M_PRU),
        FormLine("3000", "카드채권 잔액", 0, "KRW", bal, citation=_R9,
                 source_module=_M_RDM),
        FormLine("3010", "채권 잔액 대비 수익률", 0, "ratio", _ratio(total, bal),
                 formula="카드부문 총수익 ÷ 카드채권 잔액", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(total)
    checks = [
        _sum_check("항목별 수익 합 = 카드부문 총수익", L, "1000", ic, t),
        _ratio_check("카드부문 비중", L, "2010", "1000", "2000"),
        _ratio_check("채권 잔액 대비 수익률", L, "3010", "1000", "3000"),
        FormCheck("카드부문 총수익 ≤ 은행 영업수익", 0.0,
                  max(0.0, total - op_rev), _tol(op_rev)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2817

def _b2817(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """비용구조 — 판관비는 실측 operating_cost 합, 대손비용은 충당금 전입액 배분이다."""
    cb = card_book(ctx)
    cm = cost_mix(ctx)
    inc = ctx.tables["pru_income_statement"]
    op_cost = abs(float(inc.loc[inc["item"] == "영업비용", "amount"].iloc[0]))
    sga = float(cb["operating_cost"].sum())
    cc = credit_cost(ctx)
    rev = float(cb["revenue"].sum())
    total = sga + cc
    L = [
        FormLine("1000", "카드부문 총비용 (연간)", 0, "KRW", total,
                 formula="판매관리비 + 대손비용 — 연간 기준", citation=_RPT,
                 source_module=_M_PTF, is_subtotal=True),
        FormLine("1010", "판매관리비 (연간)", 1, "KRW", sga,
                 formula="portfolio.operating_cost 실측 합 — 연간 기준",
                 citation=_RPT,
                 source_module=_M_PTF, is_subtotal=True),
    ]
    il, ic = _split_lines(COST_ITEMS, [cm[i] for i in COST_ITEMS], 1100, level=2,
                          citation=_RPT, source_module=_M_DER,
                          formula=lambda lab: f"구성비만 파생 · {_DERIVED_SPLIT}")
    L += il + [
        FormLine("1020", "대손비용", 1, "KRW", cc,
                 formula="충당금 전입액 × 카드 ECL 비중 — 배분 기준은 실측",
                 citation=_R11, source_module=_M_ECL),
        FormLine("2000", "은행 영업비용", 0, "KRW", op_cost,
                 formula="pru_income_statement 영업비용 (절대값)", citation=_RPT,
                 source_module=_M_PRU),
        FormLine("2010", "판매관리비 비중", 0, "ratio", _ratio(sga, op_cost),
                 formula="카드 판매관리비 ÷ 은행 영업비용", citation=_RPT,
                 source_module=_M_PRU),
        FormLine("3000", "카드부문 총수익", 0, "KRW", rev, citation=_RPT,
                 source_module=_M_PTF),
        FormLine("3010", "비용률", 0, "ratio", _ratio(total, rev),
                 formula="카드부문 총비용 ÷ 카드부문 총수익", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(total)
    checks = [
        _sum_check("항목별 판관비 합 = 판매관리비", L, "1010", ic, t),
        _sum_check("총비용 = 판매관리비 + 대손비용", L, "1000",
                   ("1010", "1020"), t),
        _ratio_check("판매관리비 비중", L, "2010", "1010", "2000"),
        _ratio_check("비용률", L, "3010", "1000", "3000"),
        FormCheck("카드 판매관리비 ≤ 은행 영업비용", 0.0,
                  max(0.0, sga - op_cost), _tol(op_cost)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2818

def _b2818(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """모집경로별 회원모집 — 경로별 모집비용 합계가 B2817 모집비용과 같아야 한다."""
    m = member_book(ctx)
    cm = cost_mix(ctx)
    cost = cm["회원모집비용"]
    new = m[m["is_new"]]
    n_new = float(len(new))
    by = new.groupby("channel").size()
    counts = [float(by.get(c, 0)) for c in RECRUIT_CHANNELS]
    # 모집비용은 경로별 모집인원 비례로 배분한다 — 경로별 단가 원장이 없다.
    costs = [cost * (c / n_new) if n_new else 0.0 for c in counts]
    L = [
        FormLine("1000", "당분기 신규 회원모집 수", 0, "count", n_new,
                 formula=f"모집일자 원장 부재 · {_DERIVED}", citation=_L14_2,
                 source_module=_M_DER, is_subtotal=True),
    ]
    cl, cc = _split_lines([f"경로 · {c}" for c in RECRUIT_CHANNELS], counts, 1000,
                          unit="count", citation=_L14_2, source_module=_M_DER,
                          formula=lambda lab: _DERIVED)
    L += cl
    L.append(FormLine("2000", "회원모집비용 (연간)", 0, "KRW", cost,
                      formula="B2817 판매관리비 중 회원모집비용 — 연간 기준",
                      citation=_L14_2,
                      source_module=_M_DER, is_subtotal=True))
    kl, kc = _split_lines([f"모집비용 · {c}" for c in RECRUIT_CHANNELS], costs,
                          2000, citation=_L14_2, source_module=_M_DER,
                          formula=lambda lab: "경로별 모집인원 비례 배분 · "
                                              f"{_DERIVED}")
    L += kl
    L.append(FormLine("3000", "1인당 모집비용 (연간비용 ÷ 당분기 인원 · 혼합기준)",
                      0, "KRW", _ratio(cost, n_new),
                      formula="회원모집비용(연간) ÷ 신규 회원모집 수(당분기) — "
                              "분자·분모의 기간이 다르다",
                      citation=_RPT, source_module=_M_DER))
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value="회원모집비용은 portfolio.operating_cost 배분액이라 "
                                 "연간 기준이고 신규 회원모집 수는 당분기 파생값이라 "
                                 "라인 3000의 1인당 모집비용은 기간이 섞인 값이다. "
                                 "경로별 단가 원장이 없어 모집비용은 경로별 모집인원 "
                                 "비례로 배분했다.",
                      citation=_L14_2))
    checks = [
        _sum_check("경로별 모집인원 합 = 신규 회원모집 수", L, "1000", cc, 1e-9),
        _sum_check("경로별 모집비용 합 = 회원모집비용", L, "2000", kc, _tol(cost)),
        _ratio_check("1인당 모집비용 (혼합기준)", L, "3000", "2000", "1000", 1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B2819

def _b2819(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """포인트 운영내역 — 적립액은 신용판매 이용금액에 앵커한다."""
    pb = point_book(ctx)
    cb = card_book(ctx)
    sales = use_total(cb, CREDIT_SALE)
    cm = cost_mix(ctx)
    L = [
        FormLine("1000", "기초 포인트잔액", 0, "KRW", pb["기초잔액"],
                 formula=_DERIVED_FULL, citation=_RPT, source_module=_M_DER),
        FormLine("1010", "적립", 0, "KRW", pb["적립"],
                 formula=f"신용판매 이용금액 × 적립률 · 적립률은 {_DERIVED}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("1020", "사용", 0, "KRW", pb["사용"], formula=_DERIVED,
                 citation=_RPT, source_module=_M_DER),
        FormLine("1030", "소멸", 0, "KRW", pb["소멸"], formula=_DERIVED,
                 citation=_RPT, source_module=_M_DER),
        FormLine("1040", "기말 포인트잔액", 0, "KRW", pb["기말잔액"],
                 formula="기초 + 적립 − 사용 − 소멸", citation=_RPT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "신용판매 이용금액", 0, "KRW", sales,
                 formula="일시불 + 할부 — 카드채권 잔액에 앵커", citation=_RPT,
                 source_module=_M_DER),
        FormLine("2010", "포인트 적립률", 0, "ratio", _ratio(pb["적립"], sales),
                 formula="적립 ÷ 신용판매 이용금액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("2020", "포인트 사용률", 0, "ratio",
                 _ratio(pb["사용"], pb["적립"]), formula="사용 ÷ 적립",
                 citation=_RPT, source_module=_M_DER),
        FormLine("3000", "마케팅·포인트비용", 0, "KRW", cm["마케팅·포인트비용"],
                 formula="B2817 판매관리비 중 마케팅·포인트비용", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(pb["기초잔액"] + pb["적립"])
    checks = [
        FormCheck("기말 = 기초 + 적립 − 사용 − 소멸",
                  pb["기초잔액"] + pb["적립"] - pb["사용"] - pb["소멸"],
                  pb["기말잔액"], t),
        _ratio_check("포인트 적립률", L, "2010", "1010", "2000"),
        _ratio_check("포인트 사용률", L, "2020", "1020", "1010"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2820

def _b2820(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """선지급서비스 운영내역 — 앵커할 산출값이 없는 완전 파생이다."""
    ps = prepay_service(ctx)
    L = [
        FormLine("1000", "기초 선지급잔액", 0, "KRW", ps["기초잔액"],
                 formula=_DERIVED_FULL, citation=_RPT, source_module=_M_DER),
        FormLine("1010", "당분기 선지급액", 0, "KRW", ps["선지급액"],
                 formula=f"신용판매 이용금액 대비 비율 · {_DERIVED_FULL}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("1020", "회수액", 0, "KRW", ps["회수액"], formula=_DERIVED_FULL,
                 citation=_RPT, source_module=_M_DER),
        FormLine("1030", "상각액", 0, "KRW", ps["상각액"], formula=_DERIVED_FULL,
                 citation=_RPT, source_module=_M_DER),
        FormLine("1040", "기말 선지급잔액", 0, "KRW", ps["기말잔액"],
                 formula="기초 + 선지급 − 회수 − 상각", citation=_RPT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "선지급 약정회원수", 0, "count", ps["약정회원수"],
                 formula=_DERIVED_FULL, citation=_RPT, source_module=_M_DER),
        FormLine("2010", "회원 1인당 선지급잔액", 0, "KRW",
                 _ratio(ps["기말잔액"], ps["약정회원수"]),
                 formula="기말 선지급잔액 ÷ 약정회원수", citation=_RPT,
                 source_module=_M_DER),
        FormLine("3000", "선지급 연체잔액", 0, "KRW", ps["연체잔액"],
                 formula=_DERIVED_FULL, citation=_RPT, source_module=_M_DER),
        FormLine("3010", "선지급 연체율", 0, "ratio",
                 _ratio(ps["연체잔액"], ps["기말잔액"]),
                 formula="연체잔액 ÷ 기말 선지급잔액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="선지급서비스 원장이 없어 잔액·회수·상각이 모두 "
                            "파생값이다. 잔액 항등식만 파생 안에서 닫힌다.",
                 citation=_RPT),
    ]
    t = _tol(ps["기초잔액"] + ps["선지급액"])
    checks = [
        FormCheck("기말 = 기초 + 선지급 − 회수 − 상각",
                  ps["기초잔액"] + ps["선지급액"] - ps["회수액"] - ps["상각액"],
                  ps["기말잔액"], t),
        _ratio_check("1인당 선지급잔액", L, "2010", "1040", "2000", 1e-6),
        _ratio_check("선지급 연체율", L, "3010", "3000", "1040"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2821

def _b2821(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """카드채권 자산건전성 분류 — 5단계·최저적립률을 산출값 그대로 쓴다."""
    cb = card_book(ctx)
    bal = float(cb["balance"].sum())
    npl = float(cb[cb["npl"]]["balance"].sum())
    prov = float(cb["ifrs9_provision"].sum())
    minp = float(cb["min_provision"].sum())
    L = [
        FormLine("1000", "카드채권 총 잔액", 0, "KRW", bal,
                 formula=f"rdm_asset_quality.balance 실측 · {len(cb):,}건",
                 citation=_R9, source_module=_M_RDM, is_subtotal=True),
    ]
    bal_c, prov_c, min_c, cnt_c = [], [], [], []
    for i, cls in enumerate(AQ_ORDER, start=1):
        s = cb[cb["classification"] == cls]
        base = 1000 + i * 100
        bal_c.append(str(base))
        prov_c.append(str(base + 20))
        min_c.append(str(base + 30))
        cnt_c.append(str(base + 10))
        rate = float(s["min_provision_rate"].iloc[0]) if len(s) else 0.0
        L += [
            FormLine(str(base), f"분류 · {cls}", 1, "KRW",
                     float(s["balance"].sum()),
                     formula=f"{len(s):,}건 · 최저적립률 {rate:.2%}", citation=_R9,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_R9, source_module=_M_RDM),
            FormLine(str(base + 20), "대손충당금 (IFRS 9)", 2, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
            FormLine(str(base + 30), "최저적립액", 2, "KRW",
                     float(s["min_provision"].sum()), citation=_R11,
                     source_module=_M_RDM),
        ]
    L += [
        FormLine("2000", "고정이하여신", 0, "KRW", npl,
                 formula="고정 + 회수의문 + 추정손실", citation=_R9,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "고정이하여신비율", 0, "ratio", _ratio(npl, bal),
                 formula="고정이하여신 ÷ 카드채권 총 잔액", citation=_R9,
                 source_module=_M_RDM),
        FormLine("3000", "대손충당금 합계", 0, "KRW", prov, citation="IFRS 9 5.5",
                 source_module=_M_ECL, is_subtotal=True),
        FormLine("3010", "최저적립액 합계", 0, "KRW", minp, citation=_R11,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3020", "적립 부족액", 0, "KRW", max(0.0, minp - prov),
                 formula="max(0, 최저적립액 − 대손충당금)", citation=_R11,
                 source_module=_M_RDM),
        FormLine("3030", "충당금 적립비율", 0, "ratio", _ratio(prov, bal),
                 formula="대손충당금 ÷ 카드채권 총 잔액", citation=_R11,
                 source_module=_M_ECL),
    ]
    t = _tol(bal)
    checks = [
        _sum_check("분류별 잔액 합 = 카드채권 총 잔액", L, "1000", tuple(bal_c), t),
        _sum_check("고정이하여신 = 고정 + 회수의문 + 추정손실", L, "2000",
                   tuple(bal_c[2:]), t),
        _sum_check("분류별 충당금 합 = 대손충당금 합계", L, "3000",
                   tuple(prov_c), t),
        _sum_check("분류별 최저적립액 합 = 최저적립액 합계", L, "3010",
                   tuple(min_c), t),
        _ratio_check("고정이하여신비율", L, "2010", "2000", "1000"),
        _ratio_check("충당금 적립비율", L, "3030", "3000", "1000"),
        FormCheck("분류별 건수 합 = 카드채권 건수", float(len(cb)),
                  sum(_val(L, c) for c in cnt_c), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2822

def _b2822(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """카드채권 연체기간별 분류 — rdm_delinquency.dpd 실측 버킷을 그대로 쓴다."""
    cb = card_book(ctx)
    bal = float(cb["balance"].sum())
    over = float(cb[cb["dpd"] >= 30]["balance"].sum())
    L = [
        FormLine("1000", "카드채권 총 잔액", 0, "KRW", bal,
                 formula=f"rdm_asset_quality.balance 실측 · {len(cb):,}건",
                 citation=_R9, source_module=_M_RDM, is_subtotal=True),
    ]
    bal_c, cnt_c = [], []
    for i, (_, label) in enumerate(DPD_BANDS, start=1):
        s = cb[cb["dpd_band"] == label]
        base = 1000 + i * 100
        bal_c.append(str(base))
        cnt_c.append(str(base + 10))
        L += [
            FormLine(str(base), label, 1, "KRW", float(s["balance"].sum()),
                     formula="rdm_delinquency.dpd 실측 버킷", citation=_R9,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_R9, source_module=_M_RDM),
            FormLine(str(base + 20), "구성비", 2, "ratio",
                     _ratio(float(s["balance"].sum()), bal),
                     formula="구간 잔액 ÷ 총 잔액", citation=_RPT,
                     source_module=_M_RDM),
        ]
    L += [
        FormLine("2000", "1개월 이상 연체채권", 0, "KRW", over,
                 formula="1~3개월 + 3~6개월 + 6개월 이상", citation=_R9,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "연체채권비율", 0, "ratio", _ratio(over, bal),
                 formula="1개월 이상 연체채권 ÷ 카드채권 총 잔액", citation=_R9,
                 source_module=_M_RDM),
    ]
    t = _tol(bal)
    checks = [
        _sum_check("연체구간별 잔액 합 = 카드채권 총 잔액", L, "1000",
                   tuple(bal_c), t),
        _sum_check("1개월 이상 연체 = 1~3 + 3~6 + 6개월 이상", L, "2000",
                   tuple(bal_c[2:]), t),
        _ratio_check("연체채권비율", L, "2010", "2000", "1000"),
        FormCheck("연체구간별 건수 합 = 카드채권 건수", float(len(cb)),
                  sum(_val(L, c) for c in cnt_c), 1e-9),
    ] + [_ratio_check(f"{DPD_BANDS[i][1]} 구성비", L, str(1000 + (i + 1) * 100 + 20),
                      str(1000 + (i + 1) * 100), "1000")
         for i in range(len(DPD_BANDS))]
    return L, checks


# ---------------------------------------------------------------- B2823

def _b2823(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """카드종류별 현황 — 신용카드만 채권 잔액에 앵커되고 나머지는 파생이다."""
    cts = card_type_summary(ctx)
    L = []
    mem_c, card_c, use_c = [], [], []
    for i, (_, r) in enumerate(cts.iterrows(), start=1):
        base = i * 1000
        mem_c.append(str(base + 10))
        card_c.append(str(base + 20))
        use_c.append(str(base + 30))
        anchored = r["card_type"] == "신용카드"
        note = "카드채권 잔액에 앵커" if anchored else _DERIVED_FULL
        L += [
            FormLine(str(base), f"종류 · {r['card_type']}", 0, "text", None,
                     text_value=note, citation=_L2, source_module=_M_DER),
            FormLine(str(base + 10), "회원수", 1, "count", float(r["members"]),
                     formula=("본인·가족·법인회원 — 개인 본인회원은 실측"
                              if anchored else _DERIVED_FULL),
                     citation=_L2, source_module=_M_DER),
            FormLine(str(base + 20), "발급매수", 1, "count", float(r["cards"]),
                     formula=_DERIVED if anchored else _DERIVED_FULL,
                     citation=_L14, source_module=_M_DER),
            FormLine(str(base + 30), "이용금액", 1, "KRW", float(r["usage"]),
                     formula=note, citation=_RPT, source_module=_M_DER),
        ]
    L += [
        FormLine("9010", "회원수 합계 (종류별 단순합 · 중복 포함)", 0, "count",
                 float(cts["members"].sum()),
                 formula="종류별 단순합이라 신용·체크·직불을 같이 보유한 회원이 "
                         "중복 계상된다. 선불카드는 무기명이라 회원 개념이 없어 0",
                 citation=_L2, source_module=_M_DER, is_subtotal=True),
        FormLine("9011", "실제 개인 회원수 (중복 제거)", 0, "count",
                 float(len(member_book(ctx))),
                 formula="카드채권 차주의 실측 고유 건수 — 체크·직불 보유율은 "
                         "이 모집단에서 뽑으므로 종류별 합계와 다르다",
                 citation=_L2, source_module=_M_RDM),
        FormLine("9020", "발급매수 합계", 0, "count", float(cts["cards"].sum()),
                 citation=_L14, source_module=_M_DER, is_subtotal=True),
        FormLine("9030", "이용금액 합계", 0, "KRW", float(cts["usage"].sum()),
                 citation=_RPT, source_module=_M_DER, is_subtotal=True),
    ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value="회원수 합계는 카드종류별 단순합이라 한 사람이 "
                                 "신용·체크·직불을 같이 보유하면 중복 계상된다 — "
                                 "중복 제거 기준은 라인 9011이다. 직불카드는 "
                                 "1인 1매 가정이라 회원수와 발급매수가 같다. "
                                 "신용카드 외 세 종류는 앵커할 원장이 없다.",
                      citation=_L2))
    t = _tol(float(cts["usage"].sum()))
    checks = [
        _sum_check("종류별 회원수 합 = 합계", L, "9010", tuple(mem_c), 1e-9),
        _sum_check("종류별 발급매수 합 = 합계", L, "9020", tuple(card_c), 1e-9),
        _sum_check("종류별 이용금액 합 = 합계", L, "9030", tuple(use_c), t),
        FormCheck("중복 제거 회원수 ≤ 종류별 단순합", 0.0,
                  max(0.0, _val(L, "9011") - _val(L, "9010")), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2824

def _b2824(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """가맹점수수료율 현황 — 우대요율은 규정 고시값, 일반요율만 역산이다.

    **이 서식의 요율은 기간 기준이 섞여 있다.** 분자 가맹점수수료수익은
    `portfolio.revenue`(= ead × 연간 스프레드)의 배분액이라 연간 기준이고, 분모
    가맹점 매출액은 월 회전율로 만든 당월 신용판매액이다. 기간을 맞추면(매출 × 12)
    이 합성 포트폴리오의 카드수익이 우대수수료율 적용액에도 미치지 못해 일반가맹점
    협상요율이 음수가 된다 — 즉 기간정합적 역산이 성립하지 않는다. 값을 그럴듯하게
    만들려고 회전율을 조정하지 않고, 혼합기준임을 라인·비고에 그대로 남긴다.
    """
    mk = merchant_book(ctx)
    rm = revenue_mix(ctx)
    fee_total = float(rm["가맹점수수료수익"].sum())
    sales = float(mk["sales"].sum())
    gen_rate = float(mk["fee_rate"].iloc[-1])
    pref_max = max(PREF_FEE_RATE.values())
    L = [
        FormLine("1000", "가맹점 매출액 (당월 신용판매)", 0, "KRW", sales,
                 formula="일시불 + 할부 이용금액 — 월 기준", citation=_L19,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "가맹점수수료수익 (연간)", 0, "KRW", fee_total,
                 formula="portfolio.revenue(연간 스프레드) 실측의 상품 배분",
                 citation=_L18_3, source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "평균 가맹점수수료율 (연간수익 ÷ 당월매출 · 혼합기준)",
                 0, "ratio", _ratio(fee_total, sales),
                 formula="수수료수익 ÷ 매출액 — 분자·분모의 기간이 다르다",
                 citation=_L18_3, source_module=_M_DER),
        FormLine("1030", "평균 가맹점수수료율 (연환산 매출 기준)", 0, "ratio",
                 _ratio(fee_total, sales * 12.0),
                 formula="수수료수익 ÷ (매출액 × 12) — 기간정합 기준. 규정 "
                         "우대수수료율 최저값에도 못 미친다",
                 citation=_L18_3, source_module=_M_DER),
    ]
    s_c, f_c, r_c = [], [], []
    for i, (_, r) in enumerate(mk.iterrows(), start=1):
        base = 2000 + i * 100
        s_c.append(str(base + 10))
        f_c.append(str(base + 30))
        r_c.append((str(base + 20), str(base + 30), str(base + 10)))
        is_pref = r["tier"] in PREF_FEE_RATE
        L += [
            FormLine(str(base), r["tier"], 1, "count", float(r["merchants"]),
                     formula=f"가맹점당 연매출 {float(r['annual_avg']):,.0f}원 가정",
                     citation=_L18_3, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "매출액", 2, "KRW", float(r["sales"]),
                     formula="구성비 파생 · 총액은 앵커", citation=_L19,
                     source_module=_M_DER),
            FormLine(str(base + 20), "적용 수수료율", 2, "ratio",
                     float(r["fee_rate"]),
                     formula=("제18조의3에 따라 금융위가 고시한 우대수수료율 "
                              "(2025.2.14 시행분) — 파생 아님" if is_pref
                              else "협상요율 — 연간 수수료수익에서 당월 매출로 "
                                   "역산한 혼합기준 값"),
                     citation=_L18_3, source_module=_M_DER),
            FormLine(str(base + 30), "수수료수익", 2, "KRW", float(r["fee"]),
                     formula="매출액 × 적용 수수료율", citation=_L18_3,
                     source_module=_M_DER),
        ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value="수수료율의 분자(가맹점수수료수익)는 연간 기준"
                                 "(portfolio.revenue = ead × 연간 스프레드)이고 "
                                 "분모(가맹점 매출액)는 당월 신용판매액이라 라인 "
                                 "1020·구간별 요율은 기간이 섞인 값이다. 규정 "
                                 "우대수수료율과 직접 비교할 수 없다. 기간을 맞춘 "
                                 "라인 1030은 우대수수료율 최저값에도 못 미치는데, "
                                 "이는 합성 포트폴리오의 카드수익이 회전율 가정에서 "
                                 "나오는 매출 규모를 뒷받침하지 못하기 때문이다 — "
                                 "구조적 한계이며 요율을 맞추려 회전율을 조정하지 "
                                 "않았다. 구간별 가맹점수는 매출액 ÷ 대표 연매출 "
                                 "역산이라 파생값이다.",
                      citation=_L18_3))
    t = _tol(sales)
    checks = [
        _sum_check("구간별 매출액 합 = 가맹점 매출액", L, "1000", tuple(s_c), t),
        _sum_check("구간별 수수료수익 합 = 가맹점수수료수익", L, "1010",
                   tuple(f_c), _tol(fee_total)),
        _ratio_check("평균 가맹점수수료율 (혼합기준)", L, "1020", "1010", "1000"),
        # 아래 두 건은 **규정 적합성 검증이 아니다.** 혼합기준 역산값이 파생 구간을
        # 벗어나지 않는지 보는 내부 경계 확인이다. 기간정합 요율(라인 1030)은
        # 이 경계를 만족하지 못하며 그 사실은 비고 라인에 공시한다.
        FormCheck("역산 협상요율(혼합기준) ≥ 우대수수료율 최고값", 0.0,
                  max(0.0, pref_max - gen_rate), 1e-9),
        FormCheck("역산 협상요율(혼합기준) ≤ 2.3% (감독규정 상한)", 0.0,
                  max(0.0, gen_rate - 0.023), 1e-9),
        FormCheck("연환산 요율 = 혼합기준 요율 ÷ 12", _val(L, "1020") / 12.0,
                  _val(L, "1030"), 1e-12),
    ] + [_ratio_check(f"{mk['tier'].iloc[i]} 수수료율", L, rc, nc, dc)
         for i, (rc, nc, dc) in enumerate(r_c)]
    return L, checks


# ---------------------------------------------------------------- B2825

def _b2825(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """가계신용 현황 — 가계여신 전체가 대상이라 B2426과 같은 모집단을 쓴다."""
    h = household(ctx)
    cb = card_book(ctx)
    total = float(h["balance"].sum())
    mort = float(h[h["is_mortgage"]]["balance"].sum())
    sale = float(sum(cb[f"bal_{p}"].sum() for p in CREDIT_SALE))
    loan = total - sale
    delinq = float(h[h["dpd"] > 0]["balance"].sum())
    L = [
        FormLine("1000", "가계신용 총계", 0, "KRW", total,
                 formula=f"가계여신 {len(h):,}건 — rdm_asset_quality.balance 실측",
                 citation=_RPT, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "가계대출", 1, "KRW", loan,
                 formula="가계여신 잔액 − 판매신용", citation=_RPT,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1011", "주택담보대출", 2, "KRW", mort,
                 formula="asset_class = residential_mortgage — 실측",
                 citation=_RPT, source_module=_M_RDM),
        FormLine("1012", "기타 가계대출", 2, "KRW", loan - mort,
                 formula="기타가계 잔액 − 카드 신용판매", citation=_RPT,
                 source_module=_M_RDM),
        FormLine("1020", "판매신용 (카드 신용판매)", 1, "KRW", sale,
                 formula=f"일시불 + 할부 채권 · {_DERIVED_SPLIT}", citation=_L2,
                 source_module=_M_DER),
        FormLine("1030", "판매신용 비중", 0, "ratio", _ratio(sale, total),
                 formula="판매신용 ÷ 가계신용 총계", citation=_RPT,
                 source_module=_M_DER),
        FormLine("2000", "가계 차주 수", 0, "count",
                 float(h["obligor_id"].nunique()), citation=_RPT,
                 source_module=_M_RDM),
        FormLine("2010", "차주 1인당 가계신용", 0, "KRW",
                 _ratio(total, float(h["obligor_id"].nunique())),
                 formula="가계신용 총계 ÷ 차주 수", citation=_RPT,
                 source_module=_M_RDM),
        FormLine("3000", "연체 잔액", 0, "KRW", delinq,
                 formula="dpd > 0 — 실측", citation=_R9, source_module=_M_RDM),
        FormLine("3010", "연체율", 0, "ratio", _ratio(delinq, total),
                 formula="연체 잔액 ÷ 가계신용 총계", citation=_R9,
                 source_module=_M_RDM),
    ]
    t = _tol(total)
    checks = [
        _sum_check("가계신용 = 가계대출 + 판매신용", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("가계대출 = 주담대 + 기타 가계대출", L, "1010",
                   ("1011", "1012"), t),
        _ratio_check("판매신용 비중", L, "1030", "1020", "1000"),
        _ratio_check("차주 1인당 가계신용", L, "2010", "1000", "2000", 1e-6),
        _ratio_check("연체율", L, "3010", "3000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2826

def _b2826(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """국세·지방세 등 납부실적 — 신용판매 이용금액 중 납세 비중이 파생이다."""
    tp = tax_payment(ctx)
    cb = card_book(ctx)
    sales = use_total(cb, CREDIT_SALE)
    total = float(tp["amount"].sum())
    L = [
        FormLine("1000", "카드 납부금액", 0, "KRW", total,
                 formula=f"신용판매 이용금액 대비 비중 · {_DERIVED}", citation=_RPT,
                 source_module=_M_DER, is_subtotal=True),
    ]
    al, ac = _split_lines(tp["item"], tp["amount"], 1000, citation=_RPT,
                          source_module=_M_DER, formula=lambda lab: _DERIVED)
    L += al
    L.append(FormLine("2000", "카드 납부건수", 0, "count",
                      float(tp["cases"].sum()), formula=_DERIVED, citation=_RPT,
                      source_module=_M_DER, is_subtotal=True))
    cl, cc = _split_lines(tp["item"], tp["cases"], 2000, unit="count",
                          citation=_RPT, source_module=_M_DER,
                          formula=lambda lab: _DERIVED)
    L += cl + [
        FormLine("3000", "신용판매 이용금액", 0, "KRW", sales,
                 formula="일시불 + 할부 — 카드채권 잔액에 앵커", citation=_RPT,
                 source_module=_M_DER),
        FormLine("3010", "납부실적 비중", 0, "ratio", _ratio(total, sales),
                 formula="카드 납부금액 ÷ 신용판매 이용금액", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(total)
    checks = [
        _sum_check("항목별 납부금액 합 = 카드 납부금액", L, "1000", ac, t),
        _sum_check("항목별 납부건수 합 = 카드 납부건수", L, "2000", cc, 1e-9),
        _ratio_check("납부실적 비중", L, "3010", "1000", "3000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2827

def _b2827(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """국내회원 체크(직불)카드 이용실적 — 예금계좌 연동이라 완전 파생이다."""
    cts = card_type_summary(ctx)
    row = cts[cts["card_type"] == "체크카드"].iloc[0]
    credit = float(cts[cts["card_type"] == "신용카드"]["usage"].iloc[0])
    r = rng("체크건당")
    tk = float(r.uniform(2.0e4, 4.0e4))
    L = [
        FormLine("1000", "체크카드 이용금액", 0, "KRW", float(row["usage"]),
                 formula=f"{_DERIVED_FULL} — 신용카드 이용금액 대비 배수",
                 citation=_L2, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "이용건수", 0, "count", _ratio(float(row["usage"]), tk),
                 formula=f"이용금액 ÷ 건당 {tk:,.0f}원 · {_DERIVED_FULL}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("2000", "체크카드 회원수", 0, "count", float(row["members"]),
                 formula=f"신용카드 회원 중 보유율 파생 · {_DERIVED_FULL}",
                 citation=_L2, source_module=_M_DER),
        FormLine("2010", "체크카드 발급매수", 0, "count", float(row["cards"]),
                 formula=_DERIVED_FULL, citation=_L14, source_module=_M_DER),
        FormLine("3000", "회원 1인당 이용금액", 0, "KRW",
                 _ratio(float(row["usage"]), float(row["members"])),
                 formula="이용금액 ÷ 회원수", citation=_RPT, source_module=_M_DER),
        FormLine("4000", "신용카드 이용금액", 0, "KRW", credit,
                 formula="B2805 총 이용금액", citation=_RPT, source_module=_M_DER),
        FormLine("4010", "신용카드 대비 비중", 0, "ratio",
                 _ratio(float(row["usage"]), credit),
                 formula="체크카드 이용금액 ÷ 신용카드 이용금액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="체크카드는 예금계좌 연동이라 카드채권 잔액이 없다. "
                            "회원수·발급매수·이용금액이 모두 파생값이다.",
                 citation=_L2),
    ]
    checks = [
        _ratio_check("1인당 이용금액", L, "3000", "1000", "2000", 1e-6),
        _ratio_check("신용카드 대비 비중", L, "4010", "1000", "4000"),
        FormCheck("체크카드 이용금액 ≤ 신용카드 이용금액", 0.0,
                  max(0.0, float(row["usage"]) - credit), _tol(credit)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2828

def _b2828(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """소멸시효 경과 선불카드 미사용잔액 — 시효 기산은 상법 제64조를 따른다."""
    pre = prepaid_book(ctx)
    remain = pre["prescribed"] - pre["restored"]
    L = [
        FormLine("1000", "선불카드 미사용잔액", 0, "KRW", pre["unused"],
                 formula="발행액 − 사용액", citation=_L2, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1010", "유효기간 경과전", 1, "KRW", pre["unused_valid"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("1020", "유효기간 경과", 1, "KRW", pre["expired"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("2000", "소멸시효 경과 잔액", 0, "KRW", pre["prescribed"],
                 formula=f"유효기간 경과분 중 5년 경과 · {_DERIVED_FULL}",
                 citation=_COM64, source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "시효 경과 후 환급액", 1, "KRW", pre["restored"],
                 formula=_DERIVED_FULL, citation=_COM64, source_module=_M_DER),
        FormLine("2020", "시효 경과 잔여잔액", 1, "KRW", remain,
                 formula="소멸시효 경과 잔액 − 환급액", citation=_COM64,
                 source_module=_M_DER),
        FormLine("3000", "미사용잔액 대비 시효경과 비율", 0, "ratio",
                 _ratio(pre["prescribed"], pre["unused"]),
                 formula="소멸시효 경과 잔액 ÷ 미사용잔액", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(pre["unused"])
    checks = [
        _sum_check("미사용잔액 = 경과전 + 경과", L, "1000", ("1010", "1020"), t),
        _sum_check("시효 경과 잔액 = 환급 + 잔여", L, "2000",
                   ("2010", "2020"), t),
        _ratio_check("시효경과 비율", L, "3000", "2000", "1000"),
        FormCheck("소멸시효 경과 ≤ 유효기간 경과", 0.0,
                  max(0.0, pre["prescribed"] - pre["expired"]), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2829

def _b2829(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """선불카드 발급수 현황 — 앵커할 산출값이 없는 완전 파생이다."""
    pre = prepaid_book(ctx)
    existing = pre["issued_cards"] - pre["new_cards"]
    L = [
        FormLine("1000", "선불카드 총 발급좌수", 0, "count", pre["issued_cards"],
                 formula=f"발행액 ÷ 좌당 평균 발행액 · {_DERIVED_FULL}",
                 citation=_L2, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "당분기 신규발급", 1, "count", pre["new_cards"],
                 formula=_DERIVED_FULL, citation=_L14, source_module=_M_DER),
        FormLine("1020", "기발급 (전분기 이전)", 1, "count", existing,
                 formula="총 발급좌수 − 당분기 신규발급", citation=_L14,
                 source_module=_M_DER),
        FormLine("2000", "선불카드 발행액", 0, "KRW", pre["issued"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("2010", "좌당 평균 발행액", 0, "KRW",
                 _ratio(pre["issued"], pre["issued_cards"]),
                 formula="발행액 ÷ 총 발급좌수", citation=_RPT,
                 source_module=_M_DER),
        FormLine("3000", "신규발급 비율", 0, "ratio",
                 _ratio(pre["new_cards"], pre["issued_cards"]),
                 formula="당분기 신규발급 ÷ 총 발급좌수", citation=_RPT,
                 source_module=_M_DER),
    ]
    checks = [
        _sum_check("총 발급좌수 = 신규 + 기발급", L, "1000",
                   ("1010", "1020"), 1e-6),
        _ratio_check("좌당 평균 발행액", L, "2010", "2000", "1000", 1e-6),
        _ratio_check("신규발급 비율", L, "3000", "1010", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2830

def _b2830(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """선불카드 미사용잔액 및 포인트 기부현황 — 기부액은 파생이다."""
    pre, pb = prepaid_book(ctx), point_book(ctx)
    donation = pre["donated"] + pb["기부"]
    L = [
        FormLine("1000", "선불카드 미사용잔액", 0, "KRW", pre["unused"],
                 formula="발행액 − 사용액", citation=_L2, source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1010", "유효기간 경과전", 1, "KRW", pre["unused_valid"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("1020", "유효기간 경과", 1, "KRW", pre["expired"],
                 formula=_DERIVED_FULL, citation=_L2, source_module=_M_DER),
        FormLine("2000", "포인트 기말잔액", 0, "KRW", pb["기말잔액"],
                 formula="B2819 기말 포인트잔액", citation=_RPT,
                 source_module=_M_DER),
        FormLine("3000", "기부액 합계", 0, "KRW", donation,
                 formula="선불카드 미사용잔액 기부 + 포인트 기부", citation=_RPT,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3010", "선불카드 미사용잔액 기부", 1, "KRW", pre["donated"],
                 formula=f"소멸시효 경과분 중 기부 · {_DERIVED_FULL}",
                 citation=_COM64, source_module=_M_DER),
        FormLine("3020", "포인트 기부", 1, "KRW", pb["기부"],
                 formula=f"포인트 사용액 중 기부 · {_DERIVED_FULL}", citation=_RPT,
                 source_module=_M_DER),
        FormLine("4000", "포인트 잔액 대비 기부율", 0, "ratio",
                 _ratio(pb["기부"], pb["기말잔액"]),
                 formula="포인트 기부 ÷ 포인트 기말잔액", citation=_RPT,
                 source_module=_M_DER),
    ]
    t = _tol(pre["unused"])
    checks = [
        _sum_check("미사용잔액 = 경과전 + 경과", L, "1000", ("1010", "1020"), t),
        _sum_check("기부액 합계 = 선불 기부 + 포인트 기부", L, "3000",
                   ("3010", "3020"), _tol(max(donation, 1.0))),
        _ratio_check("포인트 잔액 대비 기부율", L, "4000", "3020", "2000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2831

def _b2831(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """고위험 대출 현황 — 가계여신 전체가 대상이고 세 판정기준이 모두 실측이다."""
    h = household(ctx).merge(ctx.portfolio[["exposure_id", "pd"]], on="exposure_id")
    cb = card_book(ctx)
    total = float(h["balance"].sum())
    # 판정기준은 전부 실측 열이다. 임계값만 감독 실무 기준(DTI 60%)과 분위수다.
    pd_cut = float(h["pd"].quantile(0.80))
    inc_cut = float(h["annual_income"].quantile(0.30))
    low_credit = h["pd"] >= pd_cut
    high_dti = h["dti"] >= 0.60
    low_income = h["annual_income"] <= inc_cut
    hits = (low_credit.astype(int) + high_dti.astype(int) + low_income.astype(int))
    hr = h[hits >= 2]
    hr_bal = float(hr["balance"].sum())
    hr_delinq = float(hr[hr["dpd"] > 0]["balance"].sum())
    card_hr = float(cb[cb["exposure_id"].isin(hr["exposure_id"])]["balance"].sum())
    L = [
        FormLine("1000", "가계여신 총 잔액", 0, "KRW", total,
                 formula=f"가계여신 {len(h):,}건 — B2825와 같은 모집단",
                 citation=_RPT, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "저신용 (PD 상위 20%)", 1, "KRW",
                 float(h[low_credit]["balance"].sum()),
                 formula=f"PD ≥ {pd_cut:.2%} — 실측 분위수", citation=_RPT,
                 source_module=_M_RDM),
        FormLine("1020", "고DTI (60% 이상)", 1, "KRW",
                 float(h[high_dti]["balance"].sum()),
                 formula="portfolio.dti ≥ 60% — 실측", citation=_RPT,
                 source_module=_M_RDM),
        FormLine("1030", "저소득 (하위 30%)", 1, "KRW",
                 float(h[low_income]["balance"].sum()),
                 formula=f"연소득 ≤ {inc_cut:,.0f}원 — income_log 역변환",
                 citation=_RPT, source_module=_M_RDM),
        FormLine("2000", "고위험 대출 잔액", 0, "KRW", hr_bal,
                 formula="세 기준 중 2개 이상 충족 — 기준별 모집단은 겹친다",
                 citation=_RPT, source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "고위험 대출 비중", 0, "ratio", _ratio(hr_bal, total),
                 formula="고위험 대출 잔액 ÷ 가계여신 총 잔액", citation=_RPT,
                 source_module=_M_RDM),
        FormLine("2020", "고위험 차주 수", 0, "count",
                 float(hr["obligor_id"].nunique()), citation=_RPT,
                 source_module=_M_RDM),
        FormLine("3000", "고위험 대출 연체잔액", 0, "KRW", hr_delinq,
                 formula="dpd > 0 — 실측", citation=_R9, source_module=_M_RDM),
        FormLine("3010", "고위험 대출 연체율", 0, "ratio",
                 _ratio(hr_delinq, hr_bal),
                 formula="고위험 연체잔액 ÷ 고위험 대출 잔액", citation=_R9,
                 source_module=_M_RDM),
        FormLine("4000", "고위험 대출 중 카드채권", 0, "KRW", card_hr,
                 formula=f"카드 배정 익스포저와의 교집합 · {_DERIVED_SPLIT}",
                 citation=_RPT, source_module=_M_DER),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="다중채무 여부는 판정에 넣지 않는다 — 차주당 여신이 "
                            "1건뿐이고 타 금융기관 채무 원장이 없어 측정할 수 없다.",
                 citation=_RPT),
    ]
    t = _tol(total)
    checks = [
        _ratio_check("고위험 대출 비중", L, "2010", "2000", "1000"),
        _ratio_check("고위험 대출 연체율", L, "3010", "3000", "2000"),
        FormCheck("고위험 대출 ≤ 가계여신 총 잔액", 0.0,
                  max(0.0, hr_bal - total), t),
        FormCheck("고위험 중 카드채권 ≤ 고위험 대출 잔액", 0.0,
                  max(0.0, card_hr - hr_bal), t),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2801": ("여신전문금융업법 제2조 · 제14조", "PRD-RDM", _b2801),
    "B2802": ("여신전문금융업법 제14조 신용카드·직불카드의 발급", "PRD-RDM", _b2802),
    "B2803": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2803),
    "B2804": ("여신전문금융업법 제18조의3 · 제19조", "PRD-RDM", _b2804),
    "B2805": ("여신전문금융업법 제2조 · 동 감독규정 업무보고서 서식",
              "PRD-RDM", _b2805),
    "B2806": ("여신전문금융업법 제2조 신용카드 정의", "PRD-RDM", _b2806),
    "B2808": ("여신전문금융업법 제2조 선불카드", "PRD-RDM", _b2808),
    "B2809": ("여신전문금융업법 제2조 직불카드", "PRD-RDM", _b2809),
    "B2810": ("여신전문금융업법 제16조 신용카드등의 부정사용에 대한 책임",
              "PRD-RDM", _b2810),
    "B2811": ("여신전문금융업법 제13조 신용카드업자의 부대업무", "PRD-RDM", _b2811),
    "B2812": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2812),
    "B2813": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2813),
    "B2814": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2814),
    "B2815": ("여신전문금융업감독규정 제9조 자산건전성 분류 등", "PRD-RDM", _b2815),
    "B2816": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2816),
    "B2817": ("여신전문금융업감독규정 제11조 대손충당금 등 적립기준",
              "PRD-ECL", _b2817),
    "B2818": ("여신전문금융업법 제14조의2 신용카드회원의 모집", "PRD-RDM", _b2818),
    "B2819": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2819),
    "B2820": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2820),
    "B2821": ("여신전문금융업감독규정 제9조 · 제11조", "PRD-ECL", _b2821),
    "B2822": ("여신전문금융업감독규정 제9조 자산건전성 분류 등", "PRD-RDM", _b2822),
    "B2823": ("여신전문금융업법 제2조 카드 종류 정의", "PRD-RDM", _b2823),
    "B2824": ("여신전문금융업법 제18조의3 가맹점수수료율의 차별금지 등",
              "PRD-RDM", _b2824),
    "B2825": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2825),
    "B2826": ("여신전문금융업감독규정 업무보고서 서식", "PRD-RDM", _b2826),
    "B2827": ("여신전문금융업법 제2조 직불카드", "PRD-RDM", _b2827),
    "B2828": ("상법 제64조 상사소멸시효 · 여신전문금융업법 제2조",
              "PRD-RDM", _b2828),
    "B2829": ("여신전문금융업법 제2조 선불카드", "PRD-RDM", _b2829),
    "B2830": ("여신전문금융업법 제2조 · 상법 제64조", "PRD-RDM", _b2830),
    "B2831": ("여신전문금융업감독규정 제9조 자산건전성 분류 등", "PRD-RDM", _b2831),
}
