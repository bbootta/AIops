"""금감원 FINES 업무보고서 — 자산건전성 (가계·주담대·부동산) 14건.

근거는 은행업감독규정 제27조(자산건전성 분류)·제29조(대손충당금)와
제29조의2(주택관련담보대출 리스크관리)다. LTV·DTI 구간 경계는 동 시행세칙
별표6의 주택관련담보대출 한도 체계(LTV 40/50/60/70/80% · DTI 30/40/50/60%)를
따른다 — 서식이 자기 나름의 구간을 쓰면 감독당국 집계와 대사되지 않는다.

**LTV·DTI·잔존만기·담보유형은 파생값이 아니다.** LTV·DTI는
`portfolio.ltv`/`portfolio.dti` 실측값이고, 담보구분은 `rdm_collateral`·
`rdm_guarantee` 원장에서 온다. 소득구간은 `income_log`의 결정론적 역변환이라
난수가 끼지 않지만 **환산 단위는 가정**이다(`INCOME_UNIT_KRW`).
원장이 없는 것(지역·자금용도·상환방식·신규취급 여부·과거 연체상각 추이)만
`forms_fss_retail_data`가 기준일 고정 시드로 만든다. 파생값이 들어간 라인은
**그 라인 자체의** formula에 "파생"임을 남긴다 — 파생 분할(지역·용도·상환방식)
안의 하위 셀도 예외가 아니다. 상위 소계에만 적어 두면 서식이 flat table로
실체화될 때 하위 셀이 실측으로 읽힌다.
연체·상각 추이(B2428)는 **당월을 산출값에 앵커**하고 과거
배수만 파생하므로 시계열이 당월 실적과 어긋나면 산출 오류다.

명세 서식(B2419·B2427·B2435)의 기준금액은 **내부 보고기준**이다. 은행업감독규정
제53조의 거액여신(자기자본 10% 초과)이 아니므로 조문을 근거처럼 달지 않는다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from risk_lib.datamodel.materialize_detail import reserve_net_gap, reserve_requirement
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_retail_data import (
    AQ_ORDER, COLLATERAL_BUCKETS, DTI_BANDS, INCOME_BANDS, LTV_BANDS,
    MATURITY_BANDS, NPL_CLASSES, PURPOSES, REGIONS, REPAY_TYPES,
    arrears_history, collateral_book, corporate_book, household, writeoff_rate,
)

_M_RDM = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_DER = "risk_lib.regulatory.forms_fss_retail_data"
_M_CAP = "risk_lib.capital.bis"

_C27 = "은행업감독규정 제27조 자산건전성 5단계 분류"
_C29 = "은행업감독규정 제29조 제1항 최저적립률"
_C292 = ("은행업감독규정 제29조의2 주택관련담보대출 리스크관리 · "
         "동 시행세칙 별표6 LTV·DTI 한도")
_C53 = "은행업감독규정 제53조 거액여신"
# 제53조의 거액여신은 자기자본 10% 초과분이다. 이 서식들이 명세 대상을 고르는
# 기준(기본자본 0.5% · 0.05% · 0.005%)은 그것이 아니라 내부 보고기준이므로
# 조문을 근거처럼 달지 않고 참고로만 적는다 (forms_fss_asset._b2417과 같은 처리).
_C53_CF = ("내부 보고기준 · cf. 은행업감독규정 제53조 거액여신"
           "(자기자본 10% 초과)")
_C99 = "은행업감독규정 제99조 업무보고서"
_CRE22 = "Basel III CRE22 적격 담보 · 감독 haircut"
_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
_DERIVED_SPLIT = "분할 기준이 파생값 — 금액은 원장 실측"

_TOP_N = 20                    # 명세 서식에 개별 기재하는 상한 (나머지는 '기타')
_LTV_CAP = 0.70                # 시행세칙 별표6 일반지역 주택담보인정비율 한도


def _tol(total: float) -> float:
    return max(1.0, abs(total) * 1e-9)


def _wavg(df: pd.DataFrame, col: str) -> float:
    """잔액 가중평균. 값이 없는 행(기업의 LTV 등)은 모수에서 뺀다."""
    s = df[df[col].notna()]
    w = float(s["balance"].sum())
    return float((s[col] * s["balance"]).sum() / w) if w else 0.0


def _band_lines(df: pd.DataFrame, col: str, bands: tuple[tuple[float, str], ...],
                base: int, *, citation: str, module: str,
                value_col: str = "balance",
                note: str | None = None) -> tuple[list[FormLine], tuple[str, ...]]:
    """구간별 잔액 라인 한 벌 — 구간 라벨 순서를 코드 순서와 일치시킨다.

    `note`는 모집단이 파생 분할(지역 등)로 잘린 경우에 쓴다. 파생 분할 안의
    구간 라인은 라인 자체에 파생 표시가 없으면 실측으로 읽힌다.
    """
    L, codes = [], []
    for j, (_, label) in enumerate(bands, start=1):
        s = df[df[col] == label]
        code = str(base + j * 10)
        codes.append(code)
        L.append(FormLine(code, label, 2, "KRW", float(s[value_col].sum()),
                          formula=f"{len(s):,}건" + (f" · {note}" if note else ""),
                          citation=citation, source_module=module))
    return L, tuple(codes)


# ---------------------------------------------------------------- B2414

def _b2414(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """담보별 대출금현황 — 담보 원장·보증 원장에서 담보구분을 만든다 (파생 아님)."""
    cb = collateral_book(ctx)
    total = float(cb["balance"].sum())
    app = float(cb["appraised"].sum())
    rec = float(cb["recognized"].sum())
    unsec = float(cb[cb["bucket"] == "신용(무담보)"]["balance"].sum())
    L = [
        FormLine("1000", "총 대출금 잔액", 0, "KRW", total,
                 formula=f"익스포저 {len(cb):,}건", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "담보·보증부 대출금", 1, "KRW", total - unsec,
                 formula="담보 원장 또는 보증 원장이 있는 익스포저",
                 citation=_CRE22, source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "신용(무담보) 대출금", 1, "KRW", unsec,
                 citation=_CRE22, source_module=_M_RDM),
        FormLine("1100", "담보평가액 합계", 0, "KRW", app,
                 formula="담보는 시가, 보증은 보장금액", citation=_CRE22,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1110", "담보인정액 합계", 0, "KRW", rec,
                 formula="담보 = 시가 × (1 − 감독 haircut) · 보증 = 적격 보장금액",
                 citation=_CRE22, source_module=_M_RDM, is_subtotal=True),
        FormLine("1120", "담보인정비율", 0, "ratio", rec / total if total else 0.0,
                 formula="담보인정액 ÷ 총 대출금", citation=_CRE22,
                 source_module=_M_RDM),
    ]
    bal, apps, recs, sec, ratios = [], [], [], [], []
    for i, b in enumerate(COLLATERAL_BUCKETS, start=1):
        s = cb[cb["bucket"] == b]
        base = 2000 + i * 100
        bal.append(str(base))
        apps.append(str(base + 20))
        recs.append(str(base + 30))
        ratios.append((b, str(base + 40), str(base + 20), str(base)))
        if b != "신용(무담보)":
            sec.append(str(base))
        sb = float(s["balance"].sum())
        sa = float(s["appraised"].sum())
        L += [
            FormLine(str(base), f"담보구분 · {b}", 1, "KRW", sb,
                     formula="담보 원장 collateral_type 매핑" if i < 4
                     else ("보증 원장 rdm_guarantee" if i == 4 else "담보·보증 없음"),
                     citation=_CRE22, source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "담보평가액", 2, "KRW", sa,
                     citation=_CRE22, source_module=_M_RDM),
            FormLine(str(base + 30), "담보인정액", 2, "KRW",
                     float(s["recognized"].sum()), citation=_CRE22,
                     source_module=_M_RDM),
            FormLine(str(base + 40), "잔액 대비 담보평가액", 2, "ratio",
                     sa / sb if sb else 0.0, formula="담보평가액 ÷ 잔액",
                     citation=_CRE22, source_module=_M_RDM),
        ]
    t = _tol(total)
    checks = [
        _sum_check("담보구분별 잔액 합 = 총 대출금", L, "1000", tuple(bal), t),
        _sum_check("담보·보증부 = 신용 외 담보구분 합", L, "1010", tuple(sec), t),
        _sum_check("담보·보증부 + 신용 = 총 대출금", L, "1000", ("1010", "1020"), t),
        _sum_check("담보구분별 평가액 합 = 합계", L, "1100", tuple(apps), t),
        _sum_check("담보구분별 인정액 합 = 합계", L, "1110", tuple(recs), t),
        _ratio_check("담보인정비율 = 인정액 ÷ 총 대출금", L, "1120", "1110", "1000"),
        FormCheck("담보인정액 ≤ 담보평가액", 0.0, max(0.0, rec - app), t),
    ] + [
        _ratio_check(f"{b} 잔액 대비 담보평가액", L, rc, ac, bc)
        for b, rc, ac, bc in ratios
    ]
    return L, checks


# ---------------------------------------------------------------- B2419

def _b2419(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """거액 신규여신 취급업체 명세 — 차주 식별은 obligor_id로만 남긴다."""
    cb = corporate_book(ctx)
    tier1 = float(ctx.result.meta["capital"].tier1)
    threshold = tier1 * 0.005
    new = cb[cb["is_new"]]
    new_total = float(new["new_amount"].sum())
    by_ob = (new.groupby("obligor_id")
             .agg(amount=("new_amount", "sum"), n=("exposure_id", "count"))
             .reset_index()
             .merge(ctx.tables["rdm_obligor"][["obligor_id", "sector", "country"]],
                    on="obligor_id", how="left"))
    large = by_ob[by_ob["amount"] >= threshold].sort_values(
        ["amount", "obligor_id"], ascending=[False, True]).reset_index(drop=True)
    large_total = float(large["amount"].sum())
    L = [
        FormLine("1000", "자기자본 (기본자본)", 0, "KRW", tier1,
                 citation="은행법 제2조 자기자본",
                 source_module=_M_CAP),
        FormLine("1010", "거액 기준금액", 0, "KRW", threshold,
                 formula="기본자본 × 0.5% — 내부 보고기준 (규정상 기준 아님)",
                 citation=_C53_CF, source_module=_M_CAP),
        FormLine("1020", "월중 기업여신 신규취급액", 0, "KRW", new_total,
                 formula=f"신규취급 여부는 {_DERIVED} · {int(new['is_new'].sum()):,}건",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1030", "월중 신규취급 업체 수", 0, "count", float(len(by_ob)),
                 formula=_DERIVED, source_module=_M_DER),
        FormLine("2000", "거액 신규여신 취급업체 수", 0, "count", float(len(large)),
                 formula="내부 보고기준 초과 업체", citation=_C53_CF,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2010", "거액 신규여신 합계", 0, "KRW", large_total,
                 formula="내부 보고기준 초과분", citation=_C53_CF,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2020", "거액 비중", 0, "ratio",
                 large_total / new_total if new_total else 0.0,
                 formula="거액 신규여신 ÷ 월중 신규취급액", source_module=_M_DER),
    ]
    head = large.head(_TOP_N)
    for i, (_, r) in enumerate(head.iterrows(), start=1):
        L.append(FormLine(f"3{i:03d}", f"취급업체 · {r['obligor_id']}", 1, "KRW",
                          float(r["amount"]),
                          formula=(f"업종 {r['sector']} · 소재 {r['country']} · "
                                   f"{int(r['n'])}건"),
                          citation=_C53_CF, source_module=_M_DER))
    L.append(FormLine("3900", "기타 (명세 미기재 업체)", 1, "KRW",
                      large_total - float(head["amount"].sum()),
                      formula=f"상위 {_TOP_N}개사 외 {max(0, len(large) - _TOP_N):,}개사",
                      citation=_C53_CF, source_module=_M_DER))
    t = _tol(max(large_total, 1.0))
    checks = [
        _sum_check("명세 + 기타 = 거액 신규여신 합계", L, "2010",
                   tuple(f"3{i:03d}" for i in range(1, len(head) + 1)) + ("3900",), t),
        _ratio_check("거액 비중 = 거액 ÷ 월중 신규취급", L, "2020", "2010", "1020"),
        FormCheck("거액 신규여신 ≤ 월중 신규취급액", 0.0,
                  max(0.0, large_total - new_total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2426

def _b2426(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """가계대출금 현황보고서 — 가계여신 총괄표."""
    h = household(ctx)
    aq = ctx.tables["rdm_asset_quality"]
    ledger = float(aq[aq["borrower_type"] == "가계여신"]["balance"].sum())
    total = float(h["balance"].sum())
    mort = float(h[h["is_mortgage"]]["balance"].sum())
    delinq = float(h[h["dpd"] > 0]["balance"].sum())
    npl = float(h[h["npl"]]["balance"].sum())
    prov = float(h["ifrs9_provision"].sum())
    L = [
        FormLine("1000", "가계대출금 총계", 0, "KRW", total,
                 formula=f"차주 {h['obligor_id'].nunique():,}인 · {len(h):,}건",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "주택담보대출", 1, "KRW", mort,
                 formula="asset_class = residential_mortgage", citation=_C292,
                 source_module=_M_RDM),
        FormLine("1020", "기타 가계대출", 1, "KRW", total - mort,
                 formula="asset_class = retail_other", citation=_C99,
                 source_module=_M_RDM),
        FormLine("1030", "차주 수", 0, "count", float(h["obligor_id"].nunique()),
                 citation=_C99, source_module=_M_RDM),
        FormLine("1040", "여신 건수", 0, "count", float(len(h)), citation=_C99,
                 source_module=_M_RDM),
    ]
    cls_codes = []
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = h[h["classification"] == cls]
        code = str(2000 + j * 10)
        cls_codes.append(code)
        L.append(FormLine(code, f"건전성분류 · {cls}", 1, "KRW",
                          float(s["balance"].sum()), formula=f"{len(s):,}건",
                          citation=_C27, source_module=_M_RDM))
    L += [
        FormLine("3000", "연체 잔액 (1일 이상)", 0, "KRW", delinq,
                 formula=f"{int((h['dpd'] > 0).sum()):,}건", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "연체율", 0, "ratio", delinq / total if total else 0.0,
                 formula="연체 잔액 ÷ 가계대출금 총계", source_module=_M_RDM),
        FormLine("3020", "고정이하여신", 0, "KRW", npl,
                 formula="분류 " + "·".join(NPL_CLASSES), citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3030", "고정이하여신비율", 0, "ratio", npl / total if total else 0.0,
                 formula="고정이하여신 ÷ 가계대출금 총계", source_module=_M_RDM),
        FormLine("4000", "대손충당금 (IFRS 9 ECL)", 0, "KRW", prov,
                 citation="IFRS 9 5.5 기대신용손실", source_module=_M_ECL,
                 is_subtotal=True),
        FormLine("4010", "감독규정 최저적립액", 0, "KRW",
                 float(h["min_provision"].sum()),
                 formula="Σ 잔액 × 가계여신 분류별 최저적립률", citation=_C29,
                 source_module=_M_RDM),
        FormLine("4020", "대손준비금 순차액", 0, "KRW", reserve_net_gap(h),
                 formula="Σ max(0, 최저적립액 − 충당금)  ※ 익스포저 단위",
                 citation="은행업감독규정 제29조 제2항", source_module=_M_RDM),
        FormLine("4030", "충당금 적립률", 0, "ratio", prov / total if total else 0.0,
                 formula="대손충당금 ÷ 가계대출금 총계", source_module=_M_ECL),
        FormLine("5000", "주택담보대출 가중평균 LTV", 0, "ratio",
                 _wavg(h[h["is_mortgage"]], "ltv"),
                 formula="Σ(LTV × 잔액) ÷ Σ잔액 — 원장 실측 LTV", citation=_C292,
                 source_module=_M_PTF),
        FormLine("5010", "가계대출 가중평균 DTI", 0, "ratio", _wavg(h, "dti"),
                 formula="Σ(DTI × 잔액) ÷ Σ잔액 — 원장 실측 DTI", citation=_C292,
                 source_module=_M_PTF),
        FormLine("5020", "월중 신규취급액", 0, "KRW", float(h["new_amount"].sum()),
                 formula=f"신규취급 여부는 {_DERIVED}", source_module=_M_DER),
    ]
    t = _tol(total)
    checks = [
        _sum_check("주담대 + 기타가계 = 가계대출금 총계", L, "1000",
                   ("1010", "1020"), t),
        _sum_check("건전성분류별 합 = 가계대출금 총계", L, "1000",
                   tuple(cls_codes), t),
        FormCheck("가계대출금 총계 = 건전성분류 원장 가계여신 잔액", ledger, total, t),
        _ratio_check("연체율 = 연체 잔액 ÷ 총계", L, "3010", "3000", "1000"),
        _ratio_check("고정이하여신비율 = 고정이하 ÷ 총계", L, "3030", "3020", "1000"),
        _ratio_check("충당금 적립률 = 충당금 ÷ 총계", L, "4030", "4000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2426-1

def _b2426_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """소득구간별 가계대출 월중 신규취급 및 월말 잔액.

    소득구간은 난수가 아니라 `income_log`의 역변환이다. 다만 **환산 단위는
    가정**이다 — 원장(`datamodel/catalog`)은 `income_log`를 `log_KRW`로 적어
    두었으나 그대로 쓰면 연소득이 3.6만원이 되어 성립하지 않으므로, 천원 단위
    로그소득으로 가정해 `연소득 = exp(income_log) × 1,000`으로 되돌린다.
    가정이 틀리면 이 서식의 구간 분포가 통째로 한 구간에 몰린다
    (`forms_fss_retail_data.INCOME_UNIT_KRW`).
    """
    h = household(ctx)
    total = float(h["balance"].sum())
    new_total = float(h["new_amount"].sum())
    n_new = int(h["is_new"].sum())
    L = [
        FormLine("1000", "월말 가계대출 잔액 총계", 0, "KRW", total,
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "월중 신규취급액 총계", 0, "KRW", new_total,
                 formula=f"신규취급 여부는 {_DERIVED} (연체 중 여신은 제외)",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "월중 신규취급 건수", 0, "count", float(n_new),
                 formula=_DERIVED, source_module=_M_DER, is_subtotal=True),
        FormLine("1030", "월말 잔액 건수 총계", 0, "count", float(len(h)),
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
    ]
    bal_c, new_c, cnt_c, bcnt_c = [], [], [], []
    for i, (_, label) in enumerate(INCOME_BANDS, start=1):
        s = h[h["income_band"] == label]
        sn = s[s["is_new"]]
        base = 2000 + i * 100
        bal_c.append(str(base))
        bcnt_c.append(str(base + 10))
        new_c.append(str(base + 20))
        cnt_c.append(str(base + 30))
        L += [
            FormLine(str(base), f"소득구간 · {label}", 1, "KRW",
                     float(s["balance"].sum()),
                     formula=("연소득 = exp(income_log) × 1,000 — 원장 역변환 "
                              "(난수 없음) · 단위배수 1,000은 가정"),
                     citation=_C292, source_module=_M_PTF, is_subtotal=True),
            FormLine(str(base + 10), "월말 잔액 건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "월중 신규취급액", 2, "KRW",
                     float(sn["balance"].sum()), formula=_DERIVED,
                     source_module=_M_DER),
            FormLine(str(base + 30), "월중 신규취급 건수", 2, "count",
                     float(len(sn)), formula=_DERIVED, source_module=_M_DER),
            FormLine(str(base + 40), "평균 연소득", 2, "KRW",
                     float(s["annual_income"].mean()) if len(s) else 0.0,
                     formula="구간 내 단순평균 · 단위배수 1,000은 가정",
                     source_module=_M_PTF),
            FormLine(str(base + 50), "가중평균 DTI", 2, "ratio", _wavg(s, "dti"),
                     formula="Σ(DTI × 잔액) ÷ Σ잔액", citation=_C292,
                     source_module=_M_PTF),
        ]
    t = _tol(total)
    checks = [
        _sum_check("소득구간별 월말 잔액 합 = 총계", L, "1000", tuple(bal_c), t),
        _sum_check("소득구간별 신규취급액 합 = 총계", L, "1010", tuple(new_c),
                   _tol(max(new_total, 1.0))),
        _sum_check("소득구간별 신규취급 건수 합 = 총계", L, "1020", tuple(cnt_c), 1e-9),
        _sum_check("소득구간별 월말 잔액 건수 합 = 총계", L, "1030",
                   tuple(bcnt_c), 1e-9),
        FormCheck("월중 신규취급액 ≤ 월말 잔액", 0.0,
                  max(0.0, new_total - total), t),
        FormCheck("월중 신규취급 건수 ≤ 월말 잔액 건수", 0.0,
                  max(0.0, float(n_new - len(h))), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2427

def _b2427(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """거액예금담보대출 취급명세 — 예금·적금담보는 담보 원장에서 식별한다."""
    cb = collateral_book(ctx)
    dep = cb[cb["bucket"] == "예금·적금담보"].reset_index(drop=True)
    tier1 = float(ctx.result.meta["capital"].tier1)
    threshold = tier1 * 0.00005
    total = float(dep["balance"].sum())
    large = dep[dep["balance"] >= threshold].sort_values(
        ["balance", "exposure_id"], ascending=[False, True]).reset_index(drop=True)
    large_total = float(large["balance"].sum())
    L = [
        FormLine("1000", "자기자본 (기본자본)", 0, "KRW", tier1,
                 citation="은행법 제2조 자기자본",
                 source_module=_M_CAP),
        FormLine("1010", "거액 기준금액", 0, "KRW", threshold,
                 formula="기본자본 × 0.005% — 내부 보고기준 (규정상 기준 아님)",
                 citation=_C53_CF, source_module=_M_CAP),
        FormLine("2000", "예금담보대출 총 잔액", 0, "KRW", total,
                 formula=f"담보 원장 collateral_type = cash · {len(dep):,}건",
                 citation=_CRE22, source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "건수", 0, "count", float(len(dep)), citation=_C99,
                 source_module=_M_RDM),
        FormLine("2020", "담보 예금 평가액", 0, "KRW", float(dep["appraised"].sum()),
                 citation=_CRE22, source_module=_M_RDM),
        FormLine("2030", "담보인정액", 0, "KRW", float(dep["recognized"].sum()),
                 formula="예금담보 감독 haircut 0%", citation=_CRE22,
                 source_module=_M_RDM),
        FormLine("3000", "거액 해당 건수", 0, "count", float(len(large)),
                 formula="내부 보고기준 초과 건", citation=_C53_CF,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "거액 취급 합계", 0, "KRW", large_total,
                 formula="내부 보고기준 초과분", citation=_C53_CF,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3020", "거액 비중", 0, "ratio",
                 large_total / total if total else 0.0,
                 formula="거액 취급액 ÷ 예금담보대출 총 잔액", source_module=_M_RDM),
        FormLine("3030", "거액분 담보인정비율", 0, "ratio",
                 float(large["recognized"].sum()) / large_total
                 if large_total else 0.0,
                 formula="거액분 담보인정액 ÷ 거액 취급액", citation=_CRE22,
                 source_module=_M_RDM),
    ]
    head = large.head(_TOP_N)
    for i, (_, r) in enumerate(head.iterrows(), start=1):
        L.append(FormLine(f"4{i:03d}", f"취급건 · {r['obligor_id']}", 1, "KRW",
                          float(r["balance"]),
                          formula=(f"담보 예금 {float(r['appraised']):,.0f} · "
                                   f"인정액 {float(r['recognized']):,.0f}"),
                          citation=_C53_CF, source_module=_M_RDM))
    L.append(FormLine("4900", "기타 (명세 미기재 건)", 1, "KRW",
                      large_total - float(head["balance"].sum()),
                      formula=f"상위 {_TOP_N}건 외 {max(0, len(large) - _TOP_N):,}건",
                      citation=_C53_CF, source_module=_M_RDM))
    L.append(FormLine("3040", "거액분 담보인정액", 0, "KRW",
                      float(large["recognized"].sum()),
                      formula="거액 취급건의 담보인정액 합", citation=_CRE22,
                      source_module=_M_RDM))
    t = _tol(max(total, 1.0))
    checks = [
        _sum_check("명세 + 기타 = 거액 취급 합계", L, "3010",
                   tuple(f"4{i:03d}" for i in range(1, len(head) + 1)) + ("4900",), t),
        _ratio_check("거액 비중 = 거액 ÷ 예금담보대출 총 잔액", L, "3020",
                     "3010", "2000"),
        _ratio_check("거액분 담보인정비율 = 거액분 인정액 ÷ 거액 취급액", L, "3030",
                     "3040", "3010"),
        FormCheck("담보인정액 ≤ 담보평가액", 0.0,
                  max(0.0, _val(L, "2030") - _val(L, "2020")), t),
        FormCheck("거액 취급액 ≤ 예금담보대출 총 잔액", 0.0,
                  max(0.0, large_total - total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2428

def _b2428(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """신규연체 및 상각추이 — 당월은 산출값, 과거 11개월은 파생 배수다.

    당월 신규연체는 연체일수 1~30일 구간(당월 중 연체 진입)으로 잡는다.
    상각 원장이 없어 상각액은 고정이하여신 대비 파생률로 만든다.
    """
    aq = ctx.tables["rdm_asset_quality"]
    total = float(aq["balance"].sum())
    fresh = aq[(aq["dpd"] >= 1) & (aq["dpd"] <= 30)]
    new_arr = float(fresh["balance"].sum())
    npl = float(aq[aq["classification"].isin(NPL_CLASSES)]["balance"].sum())
    rate = writeoff_rate()
    wo = npl * rate
    delinq = float(aq[aq["dpd"] > 0]["balance"].sum())
    hh = fresh[fresh["borrower_type"] == "가계여신"]
    corp_ids = set(ctx.portfolio[ctx.portfolio["asset_class"] == "corporate"]
                   ["exposure_id"])
    co = fresh[fresh["exposure_id"].isin(corp_ids)]
    other = new_arr - float(hh["balance"].sum()) - float(co["balance"].sum())
    L = [
        FormLine("1000", "당월 신규연체 발생액", 0, "KRW", new_arr,
                 formula="연체일수 1~30일 익스포저 잔액 (당월 중 연체 진입)",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "당월 신규연체 건수", 0, "count", float(len(fresh)),
                 citation=_C27, source_module=_M_RDM),
        FormLine("1020", "당월 상각액", 0, "KRW", wo,
                 formula=f"고정이하여신 × 상각률 {rate:.3%} — 상각률은 {_DERIVED}",
                 citation="은행업감독규정 제30조 대손상각", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1030", "당월말 연체 잔액", 0, "KRW", delinq,
                 formula=f"연체일수 1일 이상 {int((aq['dpd'] > 0).sum()):,}건",
                 citation=_C27, source_module=_M_RDM),
        FormLine("1040", "총 여신 잔액", 0, "KRW", total, citation=_C99,
                 source_module=_M_RDM),
        FormLine("1050", "연체율", 0, "ratio", delinq / total if total else 0.0,
                 formula="당월말 연체 잔액 ÷ 총 여신", source_module=_M_RDM),
        FormLine("1060", "고정이하여신", 0, "KRW", npl, citation=_C27,
                 source_module=_M_RDM),
        FormLine("2000", "당월 신규연체 · 가계여신", 1, "KRW",
                 float(hh["balance"].sum()), formula=f"{len(hh):,}건",
                 citation=_C27, source_module=_M_RDM),
        FormLine("2010", "당월 신규연체 · 기업여신", 1, "KRW",
                 float(co["balance"].sum()), formula=f"{len(co):,}건",
                 citation=_C27, source_module=_M_RDM),
        FormLine("2020", "당월 신규연체 · 기타(은행·국가)", 1, "KRW", other,
                 citation=_C27, source_module=_M_RDM),
    ]
    series = arrears_history(str(ctx.result.meta["asof"]), new_arr, wo)
    for i, (month, sn, sw) in enumerate(series, start=1):
        L += [
            FormLine(str(3000 + i * 10), f"{month} 신규연체", 2, "KRW", sn,
                     formula="당월은 산출값 · 과거는 파생 배수",
                     citation=_C27, source_module=_M_DER),
            FormLine(str(4000 + i * 10), f"{month} 상각액", 2, "KRW", sw,
                     formula="당월은 산출값 · 과거는 파생 배수",
                     citation="은행업감독규정 제30조", source_module=_M_DER),
        ]
    t = _tol(max(new_arr, 1.0))
    n = len(series)
    checks = [
        # 아래 소계검증은 '기타'가 잔차라 항등식이다 — 잔차가 음수면 가계·기업
        # 모집단이 겹쳤다는 뜻이므로 부호를 따로 본다.
        _sum_check("차주구분별 신규연체 합 = 당월 신규연체", L, "1000",
                   ("2000", "2010", "2020"), t),
        FormCheck("기타(은행·국가) 신규연체 ≥ 0 (가계·기업 모집단 비중복)",
                  0.0, min(0.0, other), t),
        FormCheck("추이 최종월 신규연체 = 당월 산출값", new_arr,
                  _val(L, str(3000 + n * 10)), t),
        FormCheck("추이 최종월 상각액 = 당월 산출값", wo,
                  _val(L, str(4000 + n * 10)), _tol(max(wo, 1.0))),
        _ratio_check("연체율 = 연체 잔액 ÷ 총 여신", L, "1050", "1030", "1040"),
        FormCheck("당월 신규연체 ≤ 당월말 연체 잔액", 0.0,
                  max(0.0, new_arr - delinq), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2429

def _b2429(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """주택담보대출의 건전성 현황."""
    h = household(ctx)
    rm = h[h["is_mortgage"]]
    hh_total = float(h["balance"].sum())
    total = float(rm["balance"].sum())
    npl = float(rm[rm["npl"]]["balance"].sum())
    delinq = float(rm[rm["dpd"] > 0]["balance"].sum())
    prov = float(rm["ifrs9_provision"].sum())
    over_cap = float(rm[rm["ltv"] > _LTV_CAP]["balance"].sum())
    L = [
        FormLine("1000", "주택담보대출 총 잔액", 0, "KRW", total,
                 formula=f"{len(rm):,}건 · 차주 {rm['obligor_id'].nunique():,}인",
                 citation=_C292, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "건수", 0, "count", float(len(rm)), citation=_C99,
                 source_module=_M_RDM),
        FormLine("1020", "가계대출금 총계", 0, "KRW", hh_total, citation=_C99,
                 source_module=_M_RDM),
        FormLine("1030", "가계대출 대비 비중", 0, "ratio",
                 total / hh_total if hh_total else 0.0,
                 formula="주담대 잔액 ÷ 가계대출금 총계", source_module=_M_RDM),
    ]
    cls_codes = []
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = rm[rm["classification"] == cls]
        code = str(2000 + j * 10)
        cls_codes.append(code)
        L.append(FormLine(code, f"건전성분류 · {cls}", 1, "KRW",
                          float(s["balance"].sum()), formula=f"{len(s):,}건",
                          citation=_C27, source_module=_M_RDM))
    stage_codes = []
    for j, st in enumerate((1, 2, 3), start=1):
        s = rm[rm["stage"] == st]
        code = str(2100 + j * 10)
        stage_codes.append(code)
        L.append(FormLine(code, f"IFRS 9 Stage {st}", 1, "KRW",
                          float(s["balance"].sum()), formula=f"{len(s):,}건",
                          citation="IFRS 9 5.5 3단계 손상", source_module=_M_ECL))
    L += [
        FormLine("3000", "연체 잔액 (1일 이상)", 0, "KRW", delinq,
                 formula=f"{int((rm['dpd'] > 0).sum()):,}건", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "연체율", 0, "ratio", delinq / total if total else 0.0,
                 formula="연체 잔액 ÷ 주담대 총 잔액", source_module=_M_RDM),
        FormLine("3020", "고정이하여신", 0, "KRW", npl, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3030", "고정이하여신비율", 0, "ratio",
                 npl / total if total else 0.0,
                 formula="고정이하여신 ÷ 주담대 총 잔액", source_module=_M_RDM),
        FormLine("4000", "대손충당금 (IFRS 9 ECL)", 0, "KRW", prov,
                 citation="IFRS 9 5.5", source_module=_M_ECL, is_subtotal=True),
        FormLine("4010", "감독규정 최저적립액", 0, "KRW",
                 float(rm["min_provision"].sum()), citation=_C29,
                 source_module=_M_RDM),
        FormLine("4020", "대손준비금 순차액", 0, "KRW", reserve_net_gap(rm),
                 citation="은행업감독규정 제29조 제2항", source_module=_M_RDM),
        FormLine("4030", "고정이하여신 대비 충당금 커버리지", 0, "ratio",
                 prov / npl if npl else 0.0,
                 formula="대손충당금 ÷ 고정이하여신", source_module=_M_ECL),
        FormLine("5000", "가중평균 LTV", 0, "ratio", _wavg(rm, "ltv"),
                 formula="Σ(LTV × 잔액) ÷ Σ잔액 — 원장 실측", citation=_C292,
                 source_module=_M_PTF),
        FormLine("5010", f"LTV {_LTV_CAP:.0%} 초과 잔액", 0, "KRW", over_cap,
                 formula="시행세칙 별표6 일반지역 한도 초과분", citation=_C292,
                 source_module=_M_PTF),
        FormLine("5020", "LTV 한도 초과 비중", 0, "ratio",
                 over_cap / total if total else 0.0,
                 formula="한도 초과 잔액 ÷ 주담대 총 잔액", source_module=_M_PTF),
        FormLine("5030", "가중평균 DTI", 0, "ratio", _wavg(rm, "dti"),
                 citation=_C292, source_module=_M_PTF),
    ]
    t = _tol(total)
    checks = [
        _sum_check("건전성분류별 합 = 주담대 총 잔액", L, "1000", tuple(cls_codes), t),
        _sum_check("Stage별 합 = 주담대 총 잔액", L, "1000", tuple(stage_codes), t),
        _ratio_check("가계대출 대비 비중", L, "1030", "1000", "1020"),
        _ratio_check("연체율 = 연체 ÷ 총 잔액", L, "3010", "3000", "1000"),
        _ratio_check("고정이하여신비율", L, "3030", "3020", "1000"),
        _ratio_check("고정이하여신 대비 충당금 커버리지", L, "4030", "4000", "3020"),
        _ratio_check("LTV 한도 초과 비중", L, "5020", "5010", "1000"),
        FormCheck("주담대 잔액 ≤ 가계대출금 총계", 0.0,
                  max(0.0, total - hh_total), t),
        FormCheck("고정이하여신 ≤ 연체 잔액", 0.0, max(0.0, npl - delinq), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2430

def _b2430(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """주택담보대출의 지역별 LTV 현황.

    LTV는 원장 실측값이고 구간 경계만 감독기준이다. **지역만 파생**한다 —
    포트폴리오에 소재지 열이 없어 소득 z-점수로 수도권 가중을 올려 배정한다.
    """
    h = household(ctx)
    rm = h[h["is_mortgage"]].reset_index(drop=True)
    total = float(rm["balance"].sum())
    coll = collateral_book(ctx)[["exposure_id", "appraised"]]
    rm = rm.merge(coll, on="exposure_id", how="left")
    rm["appraised"] = rm["appraised"].fillna(0.0)
    L = [
        FormLine("1000", "주택담보대출 총 잔액", 0, "KRW", total,
                 formula=f"{len(rm):,}건", citation=_C292, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1010", "담보 부동산 평가액", 0, "KRW",
                 float(rm["appraised"].sum()),
                 formula="담보 원장 시가", citation=_CRE22, source_module=_M_RDM),
        FormLine("1020", "가중평균 LTV", 0, "ratio", _wavg(rm, "ltv"),
                 formula="Σ(LTV × 잔액) ÷ Σ잔액 — 원장 실측", citation=_C292,
                 source_module=_M_PTF),
        FormLine("1030", f"LTV {_LTV_CAP:.0%} 초과 잔액", 0, "KRW",
                 float(rm[rm["ltv"] > _LTV_CAP]["balance"].sum()),
                 citation=_C292, source_module=_M_PTF),
    ]
    L.append(FormLine("1040", "건수", 0, "count", float(len(rm)), citation=_C99,
                      source_module=_M_RDM, is_subtotal=True))
    region_codes, region_cnt, region_app, region_checks = [], [], [], []
    for i, reg in enumerate(REGIONS, start=1):
        s = rm[rm["region"] == reg]
        base = 2000 + i * 1000
        region_codes.append(str(base))
        region_cnt.append(str(base + 10))
        region_app.append(str(base + 30))
        sb = float(s["balance"].sum())
        L += [
            FormLine(str(base), f"지역 · {reg}", 1, "KRW", sb,
                     formula=f"{_DERIVED} (소득 z-점수 가중) · {len(s):,}건",
                     citation=_C292, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), "가중평균 LTV", 2, "ratio", _wavg(s, "ltv"),
                     formula=f"Σ(LTV × 잔액) ÷ Σ잔액 — LTV는 실측 · {_DERIVED_SPLIT}",
                     citation=_C292, source_module=_M_DER),
            FormLine(str(base + 30), "담보 부동산 평가액", 2, "KRW",
                     float(s["appraised"].sum()), formula=_DERIVED_SPLIT,
                     citation=_CRE22, source_module=_M_DER),
        ]
        lines, codes = _band_lines(s, "ltv_band", LTV_BANDS, base + 100,
                                   citation=_C292, module=_M_DER,
                                   note=f"지역 {_DERIVED_SPLIT}")
        L += lines
        region_checks.append(_sum_check(f"{reg} LTV 구간별 합 = 지역 잔액", L,
                                        str(base), codes, _tol(max(sb, 1.0))))
    lines, all_codes = _band_lines(rm, "ltv_band", LTV_BANDS, 6000,
                                   citation=_C292, module=_M_PTF,
                                   note="전체 주담대 · 원장 실측 LTV")
    L += lines
    t = _tol(total)
    checks = [
        _sum_check("지역별 합 = 주담대 총 잔액", L, "1000", tuple(region_codes), t),
        _sum_check("지역별 건수 합 = 주담대 건수", L, "1040", tuple(region_cnt), 1e-9),
        _sum_check("지역별 담보 부동산 평가액 합 = 합계", L, "1010",
                   tuple(region_app), _tol(max(float(rm["appraised"].sum()), 1.0))),
        _sum_check("LTV 구간별 합 = 주담대 총 잔액", L, "1000", all_codes, t),
    ] + region_checks
    return L, checks


# ---------------------------------------------------------------- B2430-1

def _b2430_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """DTI 구간별 주택담보대출 월중 신규취급 현황.

    DTI는 원장 실측값, 구간 경계는 시행세칙 별표6 기준이다. 신규취급 여부만 파생.
    """
    h = household(ctx)
    rm = h[h["is_mortgage"]]
    new = rm[rm["is_new"]]
    total = float(rm["balance"].sum())
    new_total = float(new["balance"].sum())
    L = [
        FormLine("1000", "월중 주담대 신규취급액", 0, "KRW", new_total,
                 formula=f"신규취급 여부는 {_DERIVED} · {len(new):,}건",
                 citation=_C292, source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "월중 신규취급 건수", 0, "count", float(len(new)),
                 formula=_DERIVED, source_module=_M_DER, is_subtotal=True),
        FormLine("1020", "신규취급분 가중평균 DTI", 0, "ratio", _wavg(new, "dti"),
                 formula="Σ(DTI × 잔액) ÷ Σ잔액 — 원장 실측 DTI", citation=_C292,
                 source_module=_M_PTF),
        FormLine("1030", "월말 주담대 잔액", 0, "KRW", total, citation=_C292,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1040", "신규취급분 가중평균 LTV", 0, "ratio", _wavg(new, "ltv"),
                 citation=_C292, source_module=_M_PTF),
    ]
    new_c, cnt_c, bal_c = [], [], []
    for j, (_, label) in enumerate(DTI_BANDS, start=1):
        s = rm[rm["dti_band"] == label]
        sn = s[s["is_new"]]
        base = 2000 + j * 100
        new_c.append(str(base))
        cnt_c.append(str(base + 10))
        bal_c.append(str(base + 30))
        L += [
            FormLine(str(base), f"{label} — 월중 신규취급액", 1, "KRW",
                     float(sn["balance"].sum()),
                     formula="DTI는 원장 실측 · 신규취급 여부는 파생",
                     citation=_C292, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "신규취급 건수", 2, "count", float(len(sn)),
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), "신규취급분 가중평균 LTV", 2, "ratio",
                     _wavg(sn, "ltv"), citation=_C292, source_module=_M_PTF),
            FormLine(str(base + 30), "월말 잔액", 2, "KRW",
                     float(s["balance"].sum()), formula=f"{len(s):,}건",
                     citation=_C292, source_module=_M_RDM),
        ]
    t = _tol(total)
    checks = [
        _sum_check("DTI 구간별 신규취급액 합 = 총계", L, "1000", tuple(new_c),
                   _tol(max(new_total, 1.0))),
        _sum_check("DTI 구간별 신규취급 건수 합 = 총계", L, "1010", tuple(cnt_c), 1e-9),
        _sum_check("DTI 구간별 월말 잔액 합 = 주담대 잔액", L, "1030",
                   tuple(bal_c), t),
        FormCheck("월중 신규취급액 ≤ 월말 주담대 잔액", 0.0,
                  max(0.0, new_total - total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2432

def _b2432(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """상업용부동산대출 현황 — 부동산업(sector = real_estate) 기업여신."""
    cb = corporate_book(ctx)
    corp_total = float(cb["balance"].sum())
    cre = cb[cb["sector"] == "real_estate"]
    total = float(cre["balance"].sum())
    tier1 = float(ctx.result.meta["capital"].tier1)
    app = float(cre["market_value"].fillna(0.0).sum())
    L = [
        FormLine("1000", "상업용부동산대출 잔액", 0, "KRW", total,
                 formula=f"기업여신 중 부동산업 {len(cre):,}건",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "건수", 0, "count", float(len(cre)), citation=_C99,
                 source_module=_M_RDM),
        FormLine("1020", "차주 수", 0, "count", float(cre["obligor_id"].nunique()),
                 citation=_C99, source_module=_M_RDM),
        FormLine("1030", "기업여신 총 잔액", 0, "KRW", corp_total, citation=_C99,
                 source_module=_M_RDM),
        FormLine("1040", "기업여신 대비 비중", 0, "ratio",
                 total / corp_total if corp_total else 0.0,
                 formula="상업용부동산대출 ÷ 기업여신 총 잔액", source_module=_M_RDM),
        FormLine("1050", "자기자본 (기본자본)", 0, "KRW", tier1,
                 citation="은행법 제2조 자기자본", source_module=_M_CAP),
        FormLine("1060", "자기자본 대비 비중", 0, "ratio",
                 total / tier1 if tier1 else 0.0,
                 formula="상업용부동산대출 ÷ 기본자본", citation=_C53_CF,
                 source_module=_M_CAP),
    ]
    cls_codes = []
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = cre[cre["classification"] == cls]
        code = str(2000 + j * 10)
        cls_codes.append(code)
        L.append(FormLine(code, f"건전성분류 · {cls}", 1, "KRW",
                          float(s["balance"].sum()), formula=f"{len(s):,}건",
                          citation=_C27, source_module=_M_RDM))
    ctypes = (ctx.tables["rdm_collateral"]
              .merge(cre[["exposure_id"]], on="exposure_id")["collateral_type"]
              .value_counts())
    L += [
        # 담보평가액은 담보 원장에 실제로 잡힌 담보의 시가다 — 이 하니스의 기업여신
        # 담보는 부동산이 아니므로 '상업용부동산의 감정가'로 읽히면 안 된다.
        FormLine("3000", "담보평가액", 0, "KRW", app,
                 formula=("담보 원장 시가 — 담보유형 "
                          + ("·".join(f"{k} {v:,}건" for k, v in ctypes.items())
                             or "담보 원장 없음")
                          + " (담보부동산 감정가가 아니다)"),
                 citation=_CRE22, source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "담보인정액", 0, "KRW", float(cre["recognized"].sum()),
                 formula="시가 × (1 − 감독 haircut)", citation=_CRE22,
                 source_module=_M_RDM),
        FormLine("3020", "잔액 대비 담보평가액", 0, "ratio",
                 app / total if total else 0.0,
                 formula="담보평가액 ÷ 잔액", citation=_CRE22, source_module=_M_RDM),
        FormLine("4000", "연체 잔액 (1일 이상)", 0, "KRW",
                 float(cre[cre["dpd"] > 0]["balance"].sum()),
                 formula=f"{int((cre['dpd'] > 0).sum()):,}건", citation=_C27,
                 source_module=_M_RDM),
        FormLine("4010", "고정이하여신", 0, "KRW",
                 float(cre[cre["npl"]]["balance"].sum()), citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("4020", "대손충당금 (IFRS 9 ECL)", 0, "KRW",
                 float(cre["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                 source_module=_M_ECL),
        FormLine("4030", "감독규정 최저적립액", 0, "KRW",
                 float(cre["min_provision"].sum()), citation=_C29,
                 source_module=_M_RDM),
    ]
    ctry_codes = []
    for j, ctry in enumerate(sorted(cre["country"].unique()), start=1):
        s = cre[cre["country"] == ctry]
        code = str(5000 + j * 10)
        ctry_codes.append(code)
        L.append(FormLine(code, f"소재국 · {ctry}", 1, "KRW",
                          float(s["balance"].sum()), formula=f"{len(s):,}건",
                          citation=_C99, source_module=_M_RDM))
    t = _tol(max(total, 1.0))
    checks = [
        _sum_check("건전성분류별 합 = 상업용부동산대출 잔액", L, "1000",
                   tuple(cls_codes), t),
        _sum_check("소재국별 합 = 상업용부동산대출 잔액", L, "1000",
                   tuple(ctry_codes), t),
        _ratio_check("기업여신 대비 비중", L, "1040", "1000", "1030"),
        _ratio_check("자기자본 대비 비중", L, "1060", "1000", "1050"),
        _ratio_check("잔액 대비 담보평가액", L, "3020", "3000", "1000"),
        FormCheck("상업용부동산대출 ≤ 기업여신 총 잔액", 0.0,
                  max(0.0, total - corp_total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2433

def _b2433(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자금용도별 가계대출 — 자금용도는 파생값이다."""
    h = household(ctx)
    total = float(h["balance"].sum())
    mort = float(h[h["is_mortgage"]]["balance"].sum())
    L = [
        FormLine("1000", "가계대출금 총계", 0, "KRW", total,
                 formula=f"{len(h):,}건", citation=_C99, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1010", "주택담보대출 소계", 0, "KRW", mort, citation=_C292,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "기타 가계대출 소계", 0, "KRW", total - mort,
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
    ]
    pc, mc, oc = [], [], []
    for i, pur in enumerate(PURPOSES, start=1):
        s = h[h["purpose"] == pur]
        base = 2000 + i * 100
        pc.append(str(base))
        mc.append(str(base + 20))
        oc.append(str(base + 30))
        L += [
            FormLine(str(base), f"자금용도 · {pur}", 1, "KRW",
                     float(s["balance"].sum()),
                     formula=f"{_DERIVED} (LTV·한도소진율·DTI 가중) · {len(s):,}건",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), "주택담보대출분", 2, "KRW",
                     float(s[s["is_mortgage"]]["balance"].sum()),
                     formula=f"용도 {_DERIVED_SPLIT}",
                     citation=_C292, source_module=_M_DER),
            FormLine(str(base + 30), "기타 가계대출분", 2, "KRW",
                     float(s[~s["is_mortgage"]]["balance"].sum()),
                     formula=f"용도 {_DERIVED_SPLIT}",
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 40), "가중평균 DTI", 2, "ratio", _wavg(s, "dti"),
                     formula=("Σ(DTI × 잔액) ÷ Σ잔액 — DTI는 원장 실측 · "
                              f"용도 {_DERIVED_SPLIT}"),
                     citation=_C292, source_module=_M_DER),
            FormLine(str(base + 50), "연체 잔액", 2, "KRW",
                     float(s[s["dpd"] > 0]["balance"].sum()),
                     formula=f"연체일수는 원장 실측 · 용도 {_DERIVED_SPLIT}",
                     citation=_C27, source_module=_M_DER),
            FormLine(str(base + 60), "월중 신규취급액", 2, "KRW",
                     float(s["new_amount"].sum()), formula=_DERIVED,
                     source_module=_M_DER),
        ]
    t = _tol(total)
    checks = [
        _sum_check("자금용도별 합 = 가계대출금 총계", L, "1000", tuple(pc), t),
        _sum_check("용도별 주담대분 합 = 주택담보대출 소계", L, "1010", tuple(mc), t),
        _sum_check("용도별 기타가계분 합 = 기타 가계대출 소계", L, "1020",
                   tuple(oc), t),
        _sum_check("주담대 + 기타가계 = 가계대출금 총계", L, "1000",
                   ("1010", "1020"), t),
    ] + [
        _sum_check(f"{pur} 주담대분 + 기타분 = 용도 소계", L, str(2000 + i * 100),
                   (str(2000 + i * 100 + 20), str(2000 + i * 100 + 30)), t)
        for i, pur in enumerate(PURPOSES, start=1)
    ]
    return L, checks


# ---------------------------------------------------------------- B2434

def _b2434(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """가계대출 상환방식별 현황 및 만기구조.

    상환방식은 파생, 잔존만기는 원장 실측값이다. 하니스 포트폴리오는 상품별
    계약만기가 균일(주담대 20년 · 기타가계 1년)해 만기구간이 두 곳에 몰린다 —
    분포가 아니라 원장이 그렇다.
    """
    h = household(ctx)
    total = float(h["balance"].sum())
    mort = float(h[h["is_mortgage"]]["balance"].sum())
    amort = float(h[h["repay_type"] == "분할상환"]["balance"].sum())
    L = [
        FormLine("1000", "가계대출금 총계", 0, "KRW", total,
                 formula=f"{len(h):,}건", citation=_C99, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1010", "분할상환 비중", 0, "ratio",
                 amort / total if total else 0.0,
                 formula="분할상환 잔액 ÷ 가계대출금 총계", source_module=_M_DER),
        FormLine("1020", "분할상환 잔액", 0, "KRW", amort,
                 formula=f"상환방식 {_DERIVED_SPLIT}", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1030", "주택담보대출 소계", 0, "KRW", mort,
                 formula="asset_class = residential_mortgage (원장 실측)",
                 citation=_C292, source_module=_M_RDM, is_subtotal=True),
    ]
    rc, mc = [], []
    for i, rt in enumerate(REPAY_TYPES, start=1):
        s = h[h["repay_type"] == rt]
        base = 2000 + i * 100
        rc.append(str(base))
        mc.append(str(base + 20))
        if rt == "분할상환":
            amort_code = str(base)
        L += [
            FormLine(str(base), f"상환방식 · {rt}", 1, "KRW",
                     float(s["balance"].sum()),
                     formula=f"{_DERIVED} (LTV·한도소진율 가중) · {len(s):,}건",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_DER),
            FormLine(str(base + 20), "주택담보대출분", 2, "KRW",
                     float(s[s["is_mortgage"]]["balance"].sum()),
                     formula=f"상환방식 {_DERIVED_SPLIT}", citation=_C292,
                     source_module=_M_DER),
            FormLine(str(base + 30), "가중평균 LTV", 2, "ratio", _wavg(s, "ltv"),
                     formula=("주담대분 기준 — LTV는 원장 실측 · "
                              f"상환방식 {_DERIVED_SPLIT}"),
                     citation=_C292, source_module=_M_DER),
            FormLine(str(base + 40), "가중평균 DTI", 2, "ratio", _wavg(s, "dti"),
                     formula=("Σ(DTI × 잔액) ÷ Σ잔액 — DTI는 원장 실측 · "
                              f"상환방식 {_DERIVED_SPLIT}"),
                     citation=_C292, source_module=_M_DER),
        ]
    L.append(FormLine("5000", "잔존만기 구조", 0, "KRW", total,
                      formula="원장 실측 잔존만기", citation=_C99,
                      source_module=_M_RDM, is_subtotal=True))
    lines, mcodes = _band_lines(h, "maturity_band", MATURITY_BANDS, 5000,
                                citation=_C99, module=_M_RDM,
                                note="원장 실측 잔존만기")
    L += lines
    t = _tol(total)
    checks = [
        _sum_check("상환방식별 합 = 가계대출금 총계", L, "1000", tuple(rc), t),
        _sum_check("상환방식별 주담대분 합 = 주택담보대출 소계", L, "1030",
                   tuple(mc), t),
        _sum_check("잔존만기 구간별 합 = 가계대출금 총계", L, "5000", mcodes, t),
        FormCheck("분할상환 잔액 = 상환방식 · 분할상환 라인", _val(L, amort_code),
                  _val(L, "1020"), t),
        _ratio_check("분할상환 비중 = 분할상환 ÷ 총계", L, "1010", "1020", "1000"),
        FormCheck("주택담보대출 소계 ≤ 가계대출금 총계", 0.0,
                  max(0.0, mort - total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2435

def _b2435(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """은행 여신심사위원회 승인 주택관련 담보대출 현황.

    심사위 부의 대상은 원장 실측값으로만 판정한다 — 부의기준금액(자기자본 연동)
    초과 또는 시행세칙 별표6 LTV 한도 초과. 난수가 끼지 않는다.
    """
    h = household(ctx)
    rm = h[h["is_mortgage"]]
    tier1 = float(ctx.result.meta["capital"].tier1)
    threshold = tier1 * 0.0005
    total = float(rm["balance"].sum())
    big = rm["balance"] >= threshold
    over = rm["ltv"] > _LTV_CAP
    sel = rm[big | over]
    sel_total = float(sel["balance"].sum())
    only_big = float(rm[big & ~over]["balance"].sum())
    only_ltv = float(rm[~big & over]["balance"].sum())
    both = float(rm[big & over]["balance"].sum())
    L = [
        FormLine("1000", "자기자본 (기본자본)", 0, "KRW", tier1,
                 citation="은행법 제2조 자기자본",
                 source_module=_M_CAP),
        FormLine("1010", "심사위 부의기준금액", 0, "KRW", threshold,
                 formula="기본자본 × 0.05% — 내부 부의기준 (규정상 기준 아님)",
                 citation=_C53_CF, source_module=_M_CAP),
        FormLine("1020", "규제 LTV 한도", 0, "ratio", _LTV_CAP,
                 formula="시행세칙 별표6 일반지역 주택담보인정비율", citation=_C292,
                 source_module="risk_lib.regulatory.forms_fss_retail"),
        FormLine("1030", "주택담보대출 총 잔액", 0, "KRW", total, citation=_C292,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2000", "심사위 승인 대상 건수", 0, "count", float(len(sel)),
                 citation=_C292, source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "심사위 승인 대상 잔액", 0, "KRW", sel_total,
                 formula="부의기준금액 초과 또는 LTV 한도 초과", citation=_C292,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2020", "주담대 대비 비중", 0, "ratio",
                 sel_total / total if total else 0.0,
                 formula="승인 대상 잔액 ÷ 주담대 총 잔액", source_module=_M_RDM),
        FormLine("2100", "부의사유 · 금액기준 초과", 1, "KRW", only_big,
                 formula=f"{int((big & ~over).sum()):,}건", citation=_C53_CF,
                 source_module=_M_RDM),
        FormLine("2110", "부의사유 · LTV 한도 초과", 1, "KRW", only_ltv,
                 formula=f"{int((~big & over).sum()):,}건", citation=_C292,
                 source_module=_M_PTF),
        FormLine("2120", "부의사유 · 금액·LTV 동시 초과", 1, "KRW", both,
                 formula=f"{int((big & over).sum()):,}건", citation=_C292,
                 source_module=_M_PTF),
        FormLine("3000", "승인 대상 가중평균 LTV", 0, "ratio", _wavg(sel, "ltv"),
                 formula="Σ(LTV × 잔액) ÷ Σ잔액 — 원장 실측", citation=_C292,
                 source_module=_M_PTF),
        FormLine("3010", "승인 대상 가중평균 DTI", 0, "ratio", _wavg(sel, "dti"),
                 citation=_C292, source_module=_M_PTF),
        FormLine("3020", "승인 대상 고정이하여신", 0, "KRW",
                 float(sel[sel["npl"]]["balance"].sum()), citation=_C27,
                 source_module=_M_RDM),
        FormLine("3030", "승인 대상 대손충당금", 0, "KRW",
                 float(sel["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                 source_module=_M_ECL),
    ]
    ltv_lines, ltv_codes = _band_lines(sel, "ltv_band", LTV_BANDS, 4000,
                                       citation=_C292, module=_M_PTF)
    L += ltv_lines
    t = _tol(max(total, 1.0))
    checks = [
        _sum_check("부의사유별 합 = 승인 대상 잔액", L, "2010",
                   ("2100", "2110", "2120"), t),
        _sum_check("LTV 구간별 합 = 승인 대상 잔액", L, "2010", ltv_codes, t),
        _ratio_check("주담대 대비 비중", L, "2020", "2010", "1030"),
        FormCheck("승인 대상 잔액 ≤ 주담대 총 잔액", 0.0,
                  max(0.0, sel_total - total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- B2436

# 대체투자 유형 → 업종 매핑. 이 하니스에는 투자자산 원장이 없어 실물자산 기반
# 기업여신 업종을 프록시로 쓴다. 매핑이 비어 있는 유형은 해당 익스포저가 없다.
_ALT_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("부동산 개발·임대", ("real_estate",)),
    ("SOC·에너지 프로젝트", ("energy",)),
    ("선박·항공 금융", ("shipping",)),
    ("사모펀드(PEF)", ()),
    ("헤지펀드", ()),
    ("기타 대체투자", ()),
)


def _b2436(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대체투자 자산운용 현황(외은제외).

    투자자산 원장이 없어 실물자산 기반 업종 기업여신을 프록시로 집계한다.
    PEF·헤지펀드·기타는 해당 익스포저가 없어 0이며, 그 사실을 서식에 남긴다.
    부동산 항목은 B2432(상업용부동산대출)와 모집단이 겹친다.
    """
    cb = corporate_book(ctx)
    tier1 = float(ctx.result.meta["capital"].tier1)
    sectors = tuple(s for _, ss in _ALT_TYPES for s in ss)
    alt = cb[cb["sector"].isin(sectors)]
    total = float(alt["balance"].sum())
    L = [
        FormLine("1000", "대체투자 자산 잔액 합계", 0, "KRW", total,
                 formula=f"실물자산 기반 업종 기업여신 프록시 · {len(alt):,}건",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "건수", 0, "count", float(len(alt)), citation=_C99,
                 source_module=_M_RDM),
        FormLine("1020", "자기자본 (기본자본)", 0, "KRW", tier1,
                 citation="은행법 제2조 자기자본",
                 source_module=_M_CAP),
        FormLine("1030", "자기자본 대비 비중", 0, "ratio",
                 total / tier1 if tier1 else 0.0,
                 formula="대체투자 잔액 ÷ 기본자본", citation=_C53,
                 source_module=_M_RDM),
    ]
    L += [
        FormLine("1040", "고정이하여신 합계", 0, "KRW",
                 float(alt[alt["npl"]]["balance"].sum()), citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1050", "대손충당금 합계 (IFRS 9 ECL)", 0, "KRW",
                 float(alt["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                 source_module=_M_ECL, is_subtotal=True),
    ]
    codes, empty, npl_c, prov_c = [], [], [], []
    for i, (label, ss) in enumerate(_ALT_TYPES, start=1):
        s = alt[alt["sector"].isin(ss)] if ss else alt.iloc[:0]
        if not ss:
            empty.append(label)
        base = 2000 + i * 100
        codes.append(str(base))
        npl_c.append(str(base + 20))
        prov_c.append(str(base + 30))
        L += [
            FormLine(str(base), f"대체투자 유형 · {label}", 1, "KRW",
                     float(s["balance"].sum()),
                     formula=(f"업종 {'·'.join(ss)} 프록시 · {len(s):,}건"
                              if ss else "해당 익스포저 없음 — 투자자산 원장 미보유"),
                     citation=_C99, source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "고정이하여신", 2, "KRW",
                     float(s[s["npl"]]["balance"].sum()) if len(s) else 0.0,
                     citation=_C27, source_module=_M_RDM),
            FormLine(str(base + 30), "대손충당금 (IFRS 9 ECL)", 2, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("투자자산 원장이 없어 실물자산 기반 업종 "
                                  "기업여신을 프록시로 집계한다. "
                                  f"해당 익스포저 없음: {', '.join(empty)}. "
                                  "부동산 항목은 B2432와 모집단이 겹친다."),
                      citation=_C99))
    t = _tol(max(total, 1.0))
    checks = [
        _sum_check("유형별 합 = 대체투자 잔액 합계", L, "1000", tuple(codes), t),
        _sum_check("유형별 고정이하여신 합 = 합계", L, "1040", tuple(npl_c), t),
        _sum_check("유형별 대손충당금 합 = 합계", L, "1050", tuple(prov_c), t),
        _ratio_check("자기자본 대비 비중", L, "1030", "1000", "1020"),
        FormCheck("고정이하여신 ≤ 대체투자 잔액 합계", 0.0,
                  max(0.0, _val(L, "1040") - total), t),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2414": ("은행업감독규정 제27조 · Basel III CRE22 적격 담보", "PRD-RDM", _b2414),
    "B2419": ("은행업감독규정 제53조 거액여신", "PRD-RDM", _b2419),
    "B2426": ("은행업감독규정 제27조 · 제29조 · IFRS 9 5.5", "PRD-RDM", _b2426),
    "B2426-1": ("은행업감독규정 제29조의2 · 동 시행세칙 별표6", "PRD-RDM", _b2426_1),
    "B2427": ("은행업감독규정 제53조 · Basel III CRE22", "PRD-RDM", _b2427),
    "B2428": ("은행업감독규정 제27조 · 제30조 대손상각", "PRD-RDM", _b2428),
    "B2429": ("은행업감독규정 제27조 · 제29조의2", "PRD-RDM", _b2429),
    "B2430": ("은행업감독규정 제29조의2 · 동 시행세칙 별표6 LTV 한도", "PRD-RDM", _b2430),
    "B2430-1": ("은행업감독규정 제29조의2 · 동 시행세칙 별표6 DTI 한도",
                "PRD-RDM", _b2430_1),
    "B2432": ("은행업감독규정 제27조 · 제53조", "PRD-RDM", _b2432),
    "B2433": ("은행업감독규정 제29조의2 · 제99조 업무보고서", "PRD-RDM", _b2433),
    "B2434": ("은행업감독규정 제29조의2 · 제99조 업무보고서", "PRD-ALM", _b2434),
    "B2435": ("은행업감독규정 제29조의2 · 동 시행세칙 별표6", "PRD-RDM", _b2435),
    "B2436": ("은행업감독규정 제53조 · 제99조 업무보고서", "PRD-RDM", _b2436),
}
