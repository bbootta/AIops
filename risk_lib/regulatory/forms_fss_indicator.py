"""금감원 FINES 업무보고서 — 리스크 지표 15건.

서식명·작성주기는 여기 적지 않는다. FINES 마스터(`fss_master.py`)가 정본이고
forms.py가 붙인다. 이 모듈은 규정근거·산출도메인·라인만 제공한다.

**이 그룹은 새 산출을 만들지 않는다.** 파이프라인이 이미 낸 값을 비율로
표현하는 것이 전부다. 같은 개념에 두 값이 생기면 어느 쪽이 정본인지 알 수
없게 되므로, 분자·분모는 `_core()` 한 곳에서만 만들고 15개 서식이 그것을
나눠 쓴다.

**"리스크량"의 정의** — 이 그룹 전체에서 리스크량은
`위험가중자산 × 8%`(최저 총자본비율 기준 규제 소요자본)다. 경제자본(EC)이
아니다. 예외는 신용편중리스크량(B2912) 하나뿐인데, 편중리스크는 Pillar 1
위험가중자산이 없어 ICAAP 경제자본 가산액을 쓸 수밖에 없다. 그 사실을 해당
서식의 formula와 B2915 합계 라인에 남긴다. 산식이 서식마다 갈라지지 않도록
`_amount()` 한 함수만 쓴다.

**경영실태평가와의 정합** — B2903 고정이하여신비율과 B2916 유동성 지표는
`risk_lib/prudential/camel.py`가 계량지표로 쓰는 바로 그 값이다. 두 값이
갈라지면 같은 은행이 서식과 경영실태평가에서 다른 등급을 받는다. 그래서
`pru_camel` 테이블의 지표값과 대사하는 FormCheck를 걸었다(B2903·B2913·B2916).

**연결기준(B2906-3·B2909-1)** — 연결 자회사 원장이 파이프라인에 없다. 숫자를
지어내지 않고 단독기준 값을 그대로 싣되, 연결 = 단독인 사유를 formula와 비고
라인에 남긴다.

**파생값 없음** — 이 그룹은 시드 고정 RNG로 파생한 항목이 하나도 없다. 모든
라인이 파이프라인 산출값 또는 정규 테이블의 원장값이다.

**규제 임계값은 사본을 두지 않는다** — 이상치 판정 15%는
`references.IRRBB_OUTLIER_EVE_PCT_TIER1`을, 판정 자체는 `IRRBBResult.outlier()`를
쓴다. 서식이 사본을 들면 규정 개정 때 BR-13과 조용히 갈라진다.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from risk_lib.icaap.economic_capital import concentration_addon_rate
from risk_lib.references import IRRBB_OUTLIER_EVE_PCT_TIER1
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)

_M_RWA = "risk_lib.capital.rwa_sa · risk_lib.capital.rwa_irb"
_M_MKT = "risk_lib.capital.market_risk"
_M_OPR = "risk_lib.capital.op_risk"
_M_CAP = "risk_lib.capital.bis"
_M_RDM = "risk_lib.datamodel.materialize_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_ALM = "risk_lib.alm.lcr · risk_lib.alm.nsfr · risk_lib.alm.irrbb"
_M_ICA = "risk_lib.icaap.economic_capital"
_M_PRU = "risk_lib.prudential"

_C26 = "은행업감독규정 제26조 제1항 최저 총자본비율 8%"
_C27 = "은행업감독규정 제27조 자산건전성 5단계 분류"
_C29 = "은행업감독규정 제29조 제1항 대손충당금 최저적립률"
_C31 = "은행업감독규정 제31조~제33조 경영실태평가 계량지표"

# 리스크량 환산율. 서식마다 8%를 다시 적으면 개정 때 한 곳만 고치고 만다.
_CAPITAL_RATIO = 0.08
_RA_DEF = "위험가중자산 × 8% (최저 총자본비율 기준 규제 소요자본)"

# 제27조 5단계. 잔액이 없는 분류도 칸은 있어야 한다 — 0과 미기재는 다르다.
_AQ_CLASSES = ("정상", "요주의", "고정", "회수의문", "추정손실")
_NPL_CLASSES = ("고정", "회수의문", "추정손실")

# 연결 자회사 원장 부재 — 지어내지 않고 단독을 싣는다는 사실을 한 문장으로 고정.
_CONSOL = ("연결 자회사 원장이 파이프라인에 없어 단독기준 값을 그대로 싣는다 "
           "— 연결 조정액을 지어내지 않는다")


def _amount(rwa: float) -> float:
    """리스크량 = 위험가중자산 × 8%. 이 그룹의 유일한 환산 경로다."""
    return float(rwa) * _CAPITAL_RATIO


def _core(ctx) -> dict[str, float]:
    """15개 서식이 공유하는 분자·분모.

    서식마다 다시 집계하면 같은 지표가 서식별로 갈라진다 — 총여신·자기자본처럼
    여러 서식에 동시에 나오는 값은 여기서 한 번만 만든다.
    """
    r = ctx.result
    aq = ctx.tables["rdm_asset_quality"]
    cap = r.meta["capital"]
    bs = ctx.tables["pru_balance_sheet"]
    ic = r.icaap
    ec = dict(zip(ic.ec_by_type["risk_type"], ic.ec_by_type["ec"]))
    hhi = r.concentration.set_index("dimension")["hhi"]
    return {
        "capital": float(cap.total),
        "tier1": float(cap.tier1),
        # 총여신 = 감독분류 대상 여신 잔액. camel.py 자산건전성 지표의 분모와
        # 같은 정의여야 서식과 경영실태평가가 갈라지지 않는다.
        "total_loans": float(aq["balance"].sum()),
        "total_assets": float(bs.loc[bs["item"] == "자산총계", "amount"].iloc[0]),
        "rwa_credit": float(r.rwa["credit_internal"]),
        "rwa_sa": float(r.rwa["sa"]),
        "rwa_irb": float(r.rwa["irb"]),
        "rwa_ccr": float(r.rwa["ccr"]),
        "rwa_market": float(r.rwa["market"]),
        "rwa_op": float(r.rwa["op"]),
        "rwa_structured": float(r.rwa.get("structured_total", 0.0)),
        "rwa_floor_addon": float(r.rwa["output_floor"].add_on),
        "rwa_total": float(r.rwa["final_total"]),
        "conc_addon": float(ic.concentration_addon),
        "credit_ec": float(ec["credit"]),
        "hhi_sector": float(hhi.get("sector", 0.0)),
        "hhi_country": float(hhi.get("country", 0.0)),
    }


def _aq_balance(ctx) -> dict[str, float]:
    """제27조 분류별 여신 잔액 — 잔액 없는 분류는 0."""
    aq = ctx.tables["rdm_asset_quality"]
    g = aq.groupby("classification")["balance"].sum()
    return {c: float(g.get(c, 0.0)) for c in _AQ_CLASSES}


def _aq_weighted(ctx) -> tuple[dict[str, float], dict[str, str]]:
    """분류별 손실위험도가중여신과 적용 가중치 설명.

    가중치는 제29조 최저적립률을 원장(`min_provision_rate`)에서 그대로 읽는다.
    서식이 가중치 사본을 들고 있으면 규정 개정 때 조용히 갈라진다.
    """
    aq = ctx.tables["rdm_asset_quality"]
    weighted, note = {}, {}
    for c in _AQ_CLASSES:
        sub = aq[aq["classification"] == c]
        weighted[c] = float((sub["balance"] * sub["min_provision_rate"]).sum())
        rates = sorted(set(sub["min_provision_rate"])) if len(sub) else []
        note[c] = (" · ".join(f"{x:.2%}" for x in rates) + " (제29조 최저적립률)"
                   if rates else "해당 분류 잔액 없음")
    return weighted, note


def _delinquency(ctx) -> tuple[pd.DataFrame, dict[str, float]]:
    """연체 원장(dpd)에 여신 잔액을 붙여 연체기간 구간별 잔액을 만든다."""
    dq = ctx.tables["rdm_delinquency"][["exposure_id", "dpd", "default_flag"]]
    bal = ctx.tables["rdm_asset_quality"][["exposure_id", "balance"]]
    t = dq.merge(bal, on="exposure_id", how="left")
    buckets = {}
    for label, lo, hi in (("1~29일", 1, 29), ("30~59일", 30, 59),
                          ("60~89일", 60, 89), ("90일 이상", 90, 10 ** 9)):
        sel = t[(t["dpd"] >= lo) & (t["dpd"] <= hi)]
        buckets[label] = float(sel["balance"].sum())
    return t, buckets


def _camel(ctx):
    """경영실태평가를 자산건전성 원장까지 넘겨 재산출한다.

    `pru_camel` 테이블은 `materialize_prudential`이 `evaluate_camel`을 부를 때
    자산건전성 원장(`rdm_asset_quality`)이 아직 그 dict에 없어 고정이하여신비율이
    0으로 채워져 있다. 그 값을 그대로 실으면 같은 서식 안에서 고정이하여신비율
    라인과 자산건전성 등급이 서로 모순된다. 그래서 서식은 camel.py의 산식을
    원장에 직접 적용한 결과를 싣고, 차이를 비고 라인에 남긴다 — camel.py나
    materialize_detail.py는 이 모듈의 소관이 아니므로 고치지 않는다.
    """
    from risk_lib.prudential.camel import evaluate_camel
    return evaluate_camel(ctx.result, ctx.tables)


def _camel_row(rating, component: str) -> pd.Series:
    return rating.detail.set_index("component").loc[component]


_CAMEL_NOTE = ("pru_camel 테이블은 자산건전성 지표가 0으로 채워져 있다 — "
               "materialize_prudential이 evaluate_camel을 부르는 시점에 "
               "자산건전성 원장이 아직 보이지 않기 때문이다. 이 서식은 camel.py "
               "산식을 원장에 직접 적용한 값을 싣는다. 나머지 5개 부문은 "
               "pru_camel과 동일하다.")


# ---------------------------------------------------------------- B2901

def _b2901(ctx):
    """예상손실비율 — 분자는 내부등급법 EL(PD×LGD×EAD)이다."""
    c = _core(ctx)
    rr = ctx.tables["rwa_result"]
    el_total = float(rr["expected_loss"].fillna(0.0).sum())
    pool = ctx.tables["rwa_irb_pool"]
    irb_ead = float(rr.loc[rr["approach"] != "SA", "ead_final"].sum())
    ecl = ctx.result.ecl
    L = [
        FormLine("1000", "총여신 (감독분류 대상 잔액)", 0, "KRW",
                 c["total_loans"], formula="제27조 분류 대상 여신 잔액 합계",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("1100", "내부등급법 적용 익스포저 (EAD)", 1, "KRW", irb_ead,
                 formula="표준방법 익스포저는 EL 개념이 없어 분자에 0으로 들어간다",
                 citation="Basel III CRE31", source_module=_M_RWA),
        FormLine("2000", "예상손실 (EL)", 0, "KRW", el_total,
                 formula="Σ PD × LGD × EAD (내부등급법 익스포저)",
                 citation="Basel III CRE31.4 · 은행업감독규정 제30조",
                 source_module=_M_RWA, is_subtotal=True),
    ]
    codes = []
    for i, (_, row) in enumerate(pool.groupby("asset_class", as_index=False)
                                 ["expected_loss"].sum().iterrows(), start=1):
        code = f"21{i:02d}"
        codes.append(code)
        L.append(FormLine(code, f"자산군 · {row['asset_class']}", 1, "KRW",
                          float(row["expected_loss"]),
                          formula="내부등급법 풀별 EL 합계",
                          citation="CRE31.4", source_module=_M_RWA))
    L += [
        FormLine("3000", "예상손실비율", 0, "ratio",
                 el_total / c["total_loans"], formula="예상손실 ÷ 총여신",
                 citation=_C31, source_module=_M_RWA),
        FormLine("4000", "참고 · IFRS 9 기대신용손실 (충당금)", 0, "KRW",
                 float(ecl["total"]),
                 formula="감독 EL과 별개 체계 — 회계 충당금이다",
                 citation="IFRS 9 5.5", source_module=_M_ECL),
        FormLine("4100", "참고 · 기대신용손실비율", 1, "ratio",
                 float(ecl["total"]) / c["total_loans"],
                 formula="기대신용손실 ÷ 총여신", source_module=_M_ECL),
    ]
    checks = [
        _sum_check("EL = 자산군별 EL 합", L, "2000", tuple(codes)),
        _ratio_check("예상손실비율 = EL ÷ 총여신", L, "3000", "2000", "1000"),
        _ratio_check("기대신용손실비율 = ECL ÷ 총여신", L, "4100", "4000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2902

def _b2902(ctx):
    """손실위험도가중여신비율 — 가중치는 제29조 최저적립률을 원장에서 읽는다."""
    c = _core(ctx)
    bal = _aq_balance(ctx)
    wgt, note = _aq_weighted(ctx)
    L = [FormLine("1000", "총여신", 0, "KRW", c["total_loans"],
                  citation=_C27, source_module=_M_RDM, is_subtotal=True)]
    bal_codes, wgt_codes = [], []
    for i, cls in enumerate(_AQ_CLASSES, start=1):
        bc, wc = f"11{i:02d}", f"21{i:02d}"
        bal_codes.append(bc)
        wgt_codes.append(wc)
        L.append(FormLine(bc, f"분류 · {cls}", 1, "KRW", bal[cls],
                          citation=_C27, source_module=_M_RDM))
        L.append(FormLine(wc, f"손실위험도가중 · {cls}", 1, "KRW", wgt[cls],
                          formula=f"잔액 × {note[cls]}", citation=_C29,
                          source_module=_M_RDM))
    L += [
        FormLine("2000", "손실위험도가중여신", 0, "KRW", sum(wgt.values()),
                 formula="Σ 분류별 잔액 × 제29조 최저적립률",
                 citation=_C29, source_module=_M_RDM, is_subtotal=True),
        FormLine("3000", "손실위험도가중여신비율", 0, "ratio",
                 sum(wgt.values()) / c["total_loans"],
                 formula="손실위험도가중여신 ÷ 총여신", citation=_C31,
                 source_module=_M_RDM),
        FormLine("9000", "가중치 출처", 0, "text", None,
                 text_value="손실위험도 가중치는 제29조 최저적립률을 원장 "
                            "min_provision_rate에서 읽는다 — 서식이 가중치 사본을 "
                            "들면 규정 개정 때 조용히 갈라진다.",
                 citation=_C29),
    ]
    checks = [
        _sum_check("총여신 = 분류별 잔액 합", L, "1000", tuple(bal_codes)),
        _sum_check("손실위험도가중여신 = 분류별 가중액 합", L, "2000",
                   tuple(wgt_codes)),
        _ratio_check("손실위험도가중여신비율 = 가중여신 ÷ 총여신", L, "3000",
                     "2000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2903

def _b2903(ctx):
    """고정이하여신비율 — camel.py 자산건전성 계량지표와 같은 값이어야 한다."""
    c = _core(ctx)
    bal = _aq_balance(ctx)
    rating = _camel(ctx)
    npl = sum(bal[k] for k in _NPL_CLASSES)
    watch_below = npl + bal["요주의"]
    L = [FormLine("1000", "총여신", 0, "KRW", c["total_loans"],
                  citation=_C27, source_module=_M_RDM, is_subtotal=True)]
    codes = {}
    for i, cls in enumerate(_AQ_CLASSES, start=1):
        code = f"11{i:02d}"
        codes[cls] = code
        L.append(FormLine(code, f"분류 · {cls}", 1, "KRW", bal[cls],
                          citation=_C27, source_module=_M_RDM))
    L += [
        FormLine("2000", "고정이하여신", 0, "KRW", npl,
                 formula="고정 + 회수의문 + 추정손실", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2100", "요주의이하여신", 0, "KRW", watch_below,
                 formula="요주의 + 고정이하여신", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3000", "고정이하여신비율", 0, "ratio",
                 npl / c["total_loans"], formula="고정이하여신 ÷ 총여신",
                 citation=_C31, source_module=_M_RDM),
        FormLine("3100", "요주의이하여신비율", 0, "ratio",
                 watch_below / c["total_loans"],
                 formula="요주의이하여신 ÷ 총여신", source_module=_M_RDM),
        FormLine("4000", "경영실태평가 자산건전성 등급", 0, "count",
                 float(_camel_row(rating, "자산건전성")["grade"]),
                 formula="고정이하여신비율 0.5%/1%/2%/4% 경계",
                 citation=_C31, source_module=f"{_M_PRU}.camel"),
        FormLine("9000", "경영실태평가 대사 비고", 0, "text", None,
                 text_value=_CAMEL_NOTE, citation=_C31),
    ]
    checks = [
        _sum_check("총여신 = 분류별 잔액 합", L, "1000",
                   tuple(codes[c_] for c_ in _AQ_CLASSES)),
        _sum_check("고정이하여신 = 고정+회수의문+추정손실", L, "2000",
                   tuple(codes[c_] for c_ in _NPL_CLASSES)),
        _sum_check("요주의이하여신 = 요주의 + 고정이하", L, "2100",
                   (codes["요주의"], "2000")),
        _ratio_check("고정이하여신비율 = 고정이하 ÷ 총여신", L, "3000",
                     "2000", "1000"),
        _ratio_check("요주의이하여신비율 = 요주의이하 ÷ 총여신", L, "3100",
                     "2100", "1000"),
        FormCheck("경영실태평가 자산건전성 지표와 동일",
                  float(_camel_row(rating, "자산건전성")["value"]),
                  _val(L, "3000"), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2904

def _b2904(ctx):
    """신용리스크량비율 — 리스크량은 신용 위험가중자산 × 8%다."""
    c = _core(ctx)
    ra = _amount(c["rwa_credit"])
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", c["capital"],
                 formula="보통주자본 + 기타기본자본 + 보완자본",
                 citation="은행업감독규정 제26조", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2000", "신용리스크 위험가중자산", 0, "KRW", c["rwa_credit"],
                 formula="표준방법 + 내부등급법 + 거래상대방신용리스크",
                 citation="Basel III CRE20~CRE36", source_module=_M_RWA,
                 is_subtotal=True),
        FormLine("2100", "표준방법 (SA)", 1, "KRW", c["rwa_sa"],
                 citation="CRE20", source_module="risk_lib.capital.rwa_sa"),
        FormLine("2200", "내부등급법 (IRB)", 1, "KRW", c["rwa_irb"],
                 citation="CRE31 · CRE32",
                 source_module="risk_lib.capital.rwa_irb"),
        FormLine("2300", "거래상대방신용리스크 (SA-CCR + CVA)", 1, "KRW",
                 c["rwa_ccr"], citation="CRE52 · MAR50",
                 source_module="risk_lib.ccr"),
        FormLine("3000", "신용리스크량", 0, "KRW", ra,
                 formula=f"신용 {_RA_DEF}", citation=_C26,
                 source_module=_M_RWA, is_subtotal=True),
        FormLine("4000", "신용리스크량비율", 0, "ratio", ra / c["capital"],
                 formula="신용리스크량 ÷ 자기자본", citation=_C31,
                 source_module=_M_RWA),
    ]
    checks = [
        _sum_check("신용RWA = SA + IRB + CCR", L, "2000",
                   ("2100", "2200", "2300")),
        FormCheck("신용리스크량 = 신용RWA × 8%",
                  _val(L, "2000") * _CAPITAL_RATIO, _val(L, "3000"), 1.0),
        _ratio_check("신용리스크량비율 = 리스크량 ÷ 자기자본", L, "4000",
                     "3000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2906-2·3

def _market_lines(ctx, c: dict[str, float]) -> list[FormLine]:
    comp = ctx.tables["rwa_market_component"]
    ra = _amount(c["rwa_market"])
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", c["capital"],
                 citation="은행업감독규정 제26조", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2000", "시장리스크 위험가중자산", 0, "KRW", c["rwa_market"],
                 formula="간편표준방법 소요자본 × 12.5",
                 citation="Basel MAR40", source_module=_M_MKT,
                 is_subtotal=True),
    ]
    for i, (_, row) in enumerate(comp.sort_values("risk_class").iterrows(),
                                 start=1):
        L.append(FormLine(f"21{i:02d}", f"위험군 · {row['risk_class']}", 1,
                          "KRW", float(row["rwa"]),
                          formula=f"소요자본 {float(row['capital']):,.0f}원 × 12.5",
                          citation="MAR40.2 위험군별 조정계수",
                          source_module=_M_MKT))
    L += [
        FormLine("3000", "시장리스크량", 0, "KRW", ra,
                 formula=f"시장 {_RA_DEF}", citation=_C26,
                 source_module=_M_MKT, is_subtotal=True),
        FormLine("4000", "시장리스크량비율", 0, "ratio", ra / c["capital"],
                 formula="시장리스크량 ÷ 자기자본", citation=_C31,
                 source_module=_M_MKT),
    ]
    return L


def _market_checks(ctx, L: list[FormLine]) -> list[FormCheck]:
    comp = ctx.tables["rwa_market_component"]
    codes = tuple(f"21{i:02d}" for i in range(1, len(comp) + 1))
    return [
        _sum_check("시장RWA = 위험군별 RWA 합", L, "2000", codes),
        FormCheck("시장리스크량 = 위험군별 소요자본 합",
                  float(comp["capital"].sum()), _val(L, "3000"), 1.0),
        _ratio_check("시장리스크량비율 = 리스크량 ÷ 자기자본", L, "4000",
                     "3000", "1000"),
    ]


def _b2906_2(ctx):
    """시장리스크량비율 (단독기준)."""
    L = _market_lines(ctx, _core(ctx))
    return L, _market_checks(ctx, L)


def _b2906_3(ctx):
    """시장리스크량비율 연결기준 — 연결 자회사 원장이 없어 단독과 같다."""
    c = _core(ctx)
    L = _market_lines(ctx, c)
    L.append(FormLine("9000", "연결기준 산출 범위", 0, "text", None,
                      text_value=_CONSOL + ". 연결 시장리스크 = 단독 시장리스크.",
                      citation="은행업감독규정 제26조 제2항 연결기준"))
    checks = _market_checks(ctx, L)
    checks.append(FormCheck("연결 시장리스크량 = 단독 시장리스크량",
                            _amount(c["rwa_market"]), _val(L, "3000"), 1.0))
    return L, checks


# ---------------------------------------------------------------- B2907

def _b2907(ctx):
    """트레이딩 포지션비율 — 트레이딩계정 순포지션 ÷ 총자산."""
    c = _core(ctx)
    pos = ctx.result.rwa["market_positions"]
    trades = ctx.tables["mkt_trade"]
    var = ctx.tables["mkt_var_es"]
    total_pos = float(pos["net_position"].abs().sum())
    L = [
        FormLine("1000", "총자산 (재무상태표 자산총계)", 0, "KRW",
                 c["total_assets"], citation="은행업감독규정 제99조 업무보고서",
                 source_module=f"{_M_PRU}.financials", is_subtotal=True),
        FormLine("2000", "트레이딩 포지션 합계", 0, "KRW", total_pos,
                 formula="위험군별 순포지션 절대값 합",
                 citation="Basel MAR11 트레이딩계정 편입기준",
                 source_module=_M_MKT, is_subtotal=True),
    ]
    codes = []
    for i, (_, row) in enumerate(pos.sort_values("risk_class").iterrows(),
                                 start=1):
        code = f"21{i:02d}"
        codes.append(code)
        L.append(FormLine(code, f"위험군 · {row['risk_class']}", 1, "KRW",
                          abs(float(row["net_position"])),
                          formula="순포지션 절대값", citation="MAR40.1",
                          source_module=_M_MKT))
    v99 = var[(var["measure"] == "VaR_99") & (var["horizon_days"] == 1)]
    L += [
        FormLine("3000", "트레이딩 포지션비율", 0, "ratio",
                 total_pos / c["total_assets"],
                 formula="트레이딩 포지션 ÷ 총자산", citation=_C31,
                 source_module=_M_MKT),
        FormLine("4000", "트레이딩 거래 건수", 0, "count", float(len(trades)),
                 citation="MAR11", source_module="risk_lib.market_data"),
        FormLine("4100", "트레이딩 명목금액 합계", 1, "KRW",
                 float(trades["notional"].sum()),
                 formula="트레이딩 원장 명목금액 합 — 순포지션과 달리 상계 전이다",
                 citation="MAR11", source_module="risk_lib.market_data"),
        FormLine("4200", "참고 · 1일 99% VaR", 0, "KRW",
                 float(v99["value"].iloc[0]) if len(v99) else 0.0,
                 formula="내부모형 백테스팅 기준 VaR",
                 citation="MAR99.5", source_module="risk_lib.frtb"),
    ]
    checks = [
        _sum_check("트레이딩 포지션 = 위험군별 합", L, "2000", tuple(codes)),
        _ratio_check("트레이딩 포지션비율 = 포지션 ÷ 총자산", L, "3000",
                     "2000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2909-1

def _b2909_1(ctx):
    """금리리스크지표 연결기준 — 최대 ΔEVE 감소 ÷ 기본자본."""
    irrbb = ctx.result.alm["irrbb"]
    eve = irrbb.delta_eve
    nii = irrbb.delta_nii
    tier1 = float(irrbb.tier1)
    worst = float(irrbb.worst_eve_decline)
    L = [
        FormLine("1000", "기본자본 (Tier 1)", 0, "KRW", tier1,
                 formula="보통주자본 + 기타기본자본",
                 citation="Basel SRP31.92 이상치 판정 분모",
                 source_module=_M_CAP, is_subtotal=True),
    ]
    for i, (_, row) in enumerate(eve.iterrows(), start=1):
        L.append(FormLine(f"11{i:02d}", f"ΔEVE · {row['scenario']}", 1, "KRW",
                          float(row["delta_eve"]),
                          formula=f"기본자본 대비 {float(row['pct_tier1']):.4%}",
                          citation="SRP31.90 6개 표준 금리충격",
                          source_module="risk_lib.alm.irrbb"))
    L += [
        FormLine("2000", "최대 경제적가치 감소액", 0, "KRW", worst,
                 formula=f"6개 표준충격 중 최대 감소 ({irrbb.worst_eve_scenario})",
                 citation="SRP31.92", source_module="risk_lib.alm.irrbb",
                 is_subtotal=True),
        FormLine("3000", "금리리스크지표", 0, "ratio", worst / tier1,
                 formula="최대 ΔEVE 감소 ÷ 기본자본 — 연결기준은 단독과 동일",
                 citation="은행업감독규정 제30조의2 · SRP31.92",
                 source_module="risk_lib.alm.irrbb"),
        # 15%를 서식에 다시 적지 않는다 — references가 정본이고 판정은
        # IRRBBResult.outlier()가 한다. BR-13과 같은 경로여야 갈라지지 않는다.
        FormLine("4000", "감독 이상치 기준", 0, "ratio",
                 IRRBB_OUTLIER_EVE_PCT_TIER1,
                 formula="초과 시 이상치 은행 — 감독상 조치 검토",
                 citation="Basel SRP31.92 outlier test"),
        FormLine("5000", "기준 초과 여부", 0, "count",
                 1.0 if irrbb.outlier() else 0.0,
                 formula="1 = 초과", source_module="risk_lib.alm.irrbb"),
    ]
    for i, (_, row) in enumerate(nii.iterrows(), start=1):
        L.append(FormLine(f"61{i:02d}", f"ΔNII · {row['scenario']}", 1, "KRW",
                          float(row["delta_nii"]),
                          formula="1년 순이자이익 변동",
                          citation="SRP31.34 순이자이익 관점",
                          source_module="risk_lib.alm.irrbb"))
    L.append(FormLine("9000", "연결기준 산출 범위", 0, "text", None,
                      text_value=_CONSOL + ". 연결 금리리스크지표 = 단독 지표.",
                      citation="은행업감독규정 제26조 제2항 연결기준"))
    checks = [
        FormCheck("최대 ΔEVE 감소 = 시나리오별 최대 감소",
                  float(-eve["delta_eve"].min()), _val(L, "2000"), 1.0),
        _ratio_check("금리리스크지표 = ΔEVE ÷ 기본자본", L, "3000",
                     "2000", "1000"),
        FormCheck("지표 = IRRBB 산출 기본자본 대비 비율",
                  float(irrbb.worst_pct_tier1), _val(L, "3000"), 1e-12),
        # 판정 라인에 대사가 없으면 기준을 넘겨도 서식이 스스로 알지 못한다.
        FormCheck("기준 초과 여부 = (지표 > 이상치 기준)",
                  1.0 if _val(L, "3000") > _val(L, "4000") else 0.0,
                  _val(L, "5000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2910

def _b2910(ctx):
    """연체대출채권비율 — 1개월(30일) 이상 연체채권 기준."""
    c = _core(ctx)
    t, buckets = _delinquency(ctx)
    over30 = sum(v for k, v in buckets.items() if k != "1~29일")
    all_due = sum(buckets.values())
    L = [FormLine("1000", "총여신", 0, "KRW", c["total_loans"],
                  citation=_C27, source_module=_M_RDM, is_subtotal=True),
         FormLine("2000", "연체대출채권 (1개월 이상)", 0, "KRW", over30,
                  formula="연체일수 30일 이상 여신 잔액",
                  citation="은행업감독규정 시행세칙 연체기간 구분",
                  source_module=_M_RDM, is_subtotal=True)]
    codes = {}
    for i, label in enumerate(("1~29일", "30~59일", "60~89일", "90일 이상"),
                              start=1):
        code = f"21{i:02d}"
        codes[label] = code
        L.append(FormLine(code, f"연체 {label}", 1, "KRW", buckets[label],
                          citation="시행세칙 연체기간 구분",
                          source_module=_M_RDM))
    L += [
        FormLine("3000", "연체대출채권비율", 0, "ratio",
                 over30 / c["total_loans"],
                 formula="1개월 이상 연체채권 ÷ 총여신", citation=_C31,
                 source_module=_M_RDM),
        FormLine("4000", "1일 이상 연체채권", 0, "KRW", all_due,
                 formula="연체일수 1일 이상 전체", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("4100", "1일 이상 연체비율", 1, "ratio",
                 all_due / c["total_loans"],
                 formula="1일 이상 연체채권 ÷ 총여신",
                 citation="시행세칙 연체기간 구분", source_module=_M_RDM),
        FormLine("5000", "부도 익스포저 건수", 0, "count",
                 float(int(t["default_flag"].sum())),
                 formula="90일 이상 연체 또는 상환불능",
                 citation="Basel III CRE36.69",
                 source_module="risk_lib.monitoring.delinquency"),
    ]
    checks = [
        _sum_check("연체대출채권 = 30일 이상 구간 합", L, "2000",
                   (codes["30~59일"], codes["60~89일"], codes["90일 이상"])),
        _sum_check("1일 이상 연체 = 전 구간 합", L, "4000",
                   tuple(codes[k] for k in codes)),
        _ratio_check("연체대출채권비율 = 연체채권 ÷ 총여신", L, "3000",
                     "2000", "1000"),
        _ratio_check("1일 이상 연체비율 = 연체채권 ÷ 총여신", L, "4100",
                     "4000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2911-1

def _b2911_1(ctx):
    """운영리스크량비율 — 신표준방법(SMA) 소요자본 기준."""
    c = _core(ctx)
    op = ctx.result.rwa["op_detail"]
    bi = ctx.tables["rwa_operational_bi"]
    ev = ctx.tables["opr_loss_event"]
    ra = _amount(c["rwa_op"])
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", c["capital"],
                 citation="은행업감독규정 제26조", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2000", "운영리스크 위험가중자산", 0, "KRW", c["rwa_op"],
                 formula="운영리스크 소요자본 × 12.5",
                 citation="Basel OPE25 신표준방법", source_module=_M_OPR,
                 is_subtotal=True),
        FormLine("2100", "사업지표 (BI)", 1, "KRW", float(op.bi),
                 formula="ILDC + SC + FC", citation="OPE25.2",
                 source_module=_M_OPR, is_subtotal=True),
    ]
    codes = []
    for i, (_, row) in enumerate(bi.iterrows(), start=1):
        code = f"211{i}"
        codes.append(code)
        L.append(FormLine(code, f"BI 구성 · {row['component']}", 2, "KRW",
                          float(row["amount"]),
                          formula=f"구성비 {float(row['share']):.1%}",
                          citation="OPE25.2", source_module=_M_OPR))
    L += [
        FormLine("2200", "사업지표요소 (BIC)", 1, "KRW", float(op.bic),
                 formula="BI 구간별 한계계수 적용", citation="OPE25.4",
                 source_module=_M_OPR),
        FormLine("2300", "내부손실승수 (ILM)", 1, "ratio", float(op.ilm),
                 formula="10년 평균 손실 기반 승수", citation="OPE25.9",
                 source_module=_M_OPR),
        FormLine("2400", "운영리스크 소요자본 (ORC)", 1, "KRW", float(op.orc),
                 formula="BIC × ILM", citation="OPE25.1", source_module=_M_OPR),
        FormLine("3000", "운영리스크량", 0, "KRW", ra,
                 formula=f"운영 {_RA_DEF}", citation=_C26, source_module=_M_OPR,
                 is_subtotal=True),
        FormLine("4000", "운영리스크량비율", 0, "ratio", ra / c["capital"],
                 formula="운영리스크량 ÷ 자기자본", citation=_C31,
                 source_module=_M_OPR),
        FormLine("5000", "참고 · 실제 운영손실 순액", 0, "KRW",
                 float(ev["net_loss"].sum()),
                 formula=f"손실사건 {len(ev):,}건 — 총손실 − 회수",
                 citation="OPE25.20 손실 자료", source_module="risk_lib.op_loss"),
    ]
    checks = [
        _sum_check("BI = ILDC + SC + FC", L, "2100", tuple(codes)),
        FormCheck("운영리스크 소요자본 = BIC × ILM",
                  float(op.bic) * float(op.ilm), _val(L, "2400"), 1.0),
        FormCheck("운영RWA = ORC × 12.5", float(op.orc) * 12.5,
                  _val(L, "2000"), 1.0),
        FormCheck("운영리스크량 = 운영RWA × 8%",
                  _val(L, "2000") * _CAPITAL_RATIO, _val(L, "3000"), 1.0),
        _ratio_check("운영리스크량비율 = 리스크량 ÷ 자기자본", L, "4000",
                     "3000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2912

def _b2912(ctx):
    """신용편중리스크량비율 — Pillar 1 위험가중자산이 없는 유일한 리스크량이다."""
    c = _core(ctx)
    conc = ctx.result.concentration
    addon = c["conc_addon"]
    pre = c["credit_ec"] - addon
    rate = concentration_addon_rate(c["hhi_sector"], c["hhi_country"])
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", c["capital"],
                 citation="은행업감독규정 제26조", source_module=_M_CAP,
                 is_subtotal=True),
    ]
    for i, (_, row) in enumerate(conc.iterrows(), start=1):
        L.append(FormLine(f"11{i:02d}", f"집중도 (HHI) · {row['dimension']}", 1,
                          "ratio", float(row["hhi"]),
                          formula=f"Σ 점유율² · 최대 점유율 "
                                  f"{float(row['top1_share']):.2%}",
                          citation="Basel SRP30 신용집중리스크",
                          source_module="risk_lib.limits.concentration"))
    L += [
        FormLine("2000", "신용 경제자본 (편중 가산 전)", 0, "KRW", pre,
                 formula="내부등급법 K×EAD + 표준방법 RWA × 8%",
                 citation="Basel SRP20 내부자본", source_module=_M_ICA,
                 is_subtotal=True),
        FormLine("2100", "편중 가산율", 1, "ratio", rate,
                 formula="min(15%, 0.5 × 업종 HHI + 0.3 × 국가 HHI) — "
                         "granularity adjustment 단순화",
                 citation="SRP30", source_module=_M_ICA),
        FormLine("3000", "신용편중리스크량", 0, "KRW", addon,
                 formula="신용 경제자본 × 편중 가산율 — 편중리스크는 Pillar 1 "
                         "위험가중자산이 없어 경제자본 가산액을 리스크량으로 쓴다",
                 citation="SRP30 · 은행업감독규정 제30조", source_module=_M_ICA,
                 is_subtotal=True),
        FormLine("4000", "신용편중리스크량비율", 0, "ratio",
                 addon / c["capital"],
                 formula="신용편중리스크량 ÷ 자기자본", citation=_C31,
                 source_module=_M_ICA),
    ]
    checks = [
        FormCheck("편중 가산 = 신용 경제자본 × 가산율", pre * rate,
                  _val(L, "3000"), 1.0),
        _ratio_check("신용편중리스크량비율 = 가산액 ÷ 자기자본", L, "4000",
                     "3000", "1000"),
        FormCheck("편중 가산율 상한 15% 이내", 0.0,
                  max(0.0, _val(L, "2100") - 0.15), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2913

def _risk_amounts(ctx, c: dict[str, float]) -> dict[str, float]:
    """B2913·B2915가 공유하는 리스크량 구성. 두 서식이 갈라지면 안 된다."""
    return {
        "신용": _amount(c["rwa_credit"]),
        # 구조화(집합투자증권·유동화)를 빼면 Pillar 1 소요자본과 총 리스크량이
        # 갈라진다 — 분모에는 들어간 위험가중자산이 리스크량에는 없기 때문이다.
        "구조화": _amount(c["rwa_structured"]),
        "시장": _amount(c["rwa_market"]),
        "운영": _amount(c["rwa_op"]),
        "산출하한 조정": _amount(c["rwa_floor_addon"]),
        "신용편중": c["conc_addon"],
    }


def _b2913(ctx):
    """종합리스크 지표 — 리스크 지표 15건의 headline을 한 장에 모은다."""
    c = _core(ctx)
    r = ctx.result
    ra = _risk_amounts(ctx, c)
    bal = _aq_balance(ctx)
    wgt, _ = _aq_weighted(ctx)
    _, buckets = _delinquency(ctx)
    rr = ctx.tables["rwa_result"]
    total_ra = sum(ra.values())
    npl = sum(bal[k] for k in _NPL_CLASSES)
    over30 = sum(v for k, v in buckets.items() if k != "1~29일")
    pos = ctx.result.rwa["market_positions"]
    irrbb = r.alm["irrbb"]
    rating = _camel(ctx)
    camel = rating.detail
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", c["capital"],
                 citation="은행업감독규정 제26조", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("1100", "위험가중자산 합계", 1, "KRW", c["rwa_total"],
                 citation="CRE20.1 · RBC20", source_module=_M_CAP),
        FormLine("1200", "총자본비율", 1, "ratio", float(r.bis.total_ratio),
                 formula="자기자본 ÷ 위험가중자산", source_module=_M_CAP),
        FormLine("1300", "총여신", 1, "KRW", c["total_loans"], citation=_C27,
                 source_module=_M_RDM),

        FormLine("2100", "예상손실비율 (B2901)", 0, "ratio",
                 float(rr["expected_loss"].fillna(0.0).sum()) / c["total_loans"],
                 formula="내부등급법 EL ÷ 총여신", citation=_C31,
                 source_module=_M_RWA),
        FormLine("2200", "손실위험도가중여신비율 (B2902)", 0, "ratio",
                 sum(wgt.values()) / c["total_loans"],
                 formula="제29조 최저적립률 가중여신 ÷ 총여신", citation=_C29,
                 source_module=_M_RDM),
        FormLine("2300", "고정이하여신비율 (B2903)", 0, "ratio",
                 npl / c["total_loans"], formula="고정이하여신 ÷ 총여신",
                 citation=_C27, source_module=_M_RDM),
        FormLine("2400", "연체대출채권비율 (B2910)", 0, "ratio",
                 over30 / c["total_loans"],
                 formula="1개월 이상 연체채권 ÷ 총여신", source_module=_M_RDM),
        FormLine("2500", "신용리스크량비율 (B2904)", 0, "ratio",
                 ra["신용"] / c["capital"], formula=f"신용 {_RA_DEF} ÷ 자기자본",
                 citation=_C26, source_module=_M_RWA),
        FormLine("2550", "구조화리스크량비율 (집합투자증권·유동화)", 0, "ratio",
                 ra["구조화"] / c["capital"],
                 formula=f"구조화 {_RA_DEF} ÷ 자기자본",
                 citation="CRE60 · CRE40",
                 source_module="risk_lib.datamodel.securitisation"),
        FormLine("2600", "시장리스크량비율 (B2906-2)", 0, "ratio",
                 ra["시장"] / c["capital"], formula=f"시장 {_RA_DEF} ÷ 자기자본",
                 citation="MAR40", source_module=_M_MKT),
        FormLine("2700", "운영리스크량비율 (B2911-1)", 0, "ratio",
                 ra["운영"] / c["capital"], formula=f"운영 {_RA_DEF} ÷ 자기자본",
                 citation="OPE25", source_module=_M_OPR),
        FormLine("2800", "신용편중리스크량비율 (B2912)", 0, "ratio",
                 ra["신용편중"] / c["capital"],
                 formula="ICAAP 편중 가산액 ÷ 자기자본 — 유일하게 경제자본 기준",
                 citation="SRP30", source_module=_M_ICA),
        FormLine("2900", "총 리스크량비율 (B2915)", 0, "ratio",
                 total_ra / c["capital"],
                 formula="리스크량 합계 ÷ 자기자본", citation=_C31,
                 source_module=_M_CAP, is_subtotal=True),

        FormLine("3000", "트레이딩 포지션비율 (B2907)", 0, "ratio",
                 float(pos["net_position"].abs().sum()) / c["total_assets"],
                 formula="트레이딩 순포지션 ÷ 총자산", source_module=_M_MKT),
        FormLine("3100", "금리리스크지표 (B2909-1)", 0, "ratio",
                 float(irrbb.worst_pct_tier1),
                 formula="최대 ΔEVE 감소 ÷ 기본자본", citation="SRP31.92",
                 source_module="risk_lib.alm.irrbb"),
        FormLine("3200", "유동성커버리지비율 (B2916)", 0, "ratio",
                 float(r.alm["lcr"].lcr), citation="Basel LCR20",
                 source_module=_M_ALM),
        FormLine("3300", "순안정자금조달비율 (B2916)", 0, "ratio",
                 float(r.alm["nsfr"].nsfr), citation="Basel NSF20.1",
                 source_module=_M_ALM),
        FormLine("3400", "Credit VaR (B2914)", 0, "KRW", c["credit_ec"],
                 formula="신용 경제자본 99.9% (편중 가산 포함)",
                 citation="SRP20", source_module=_M_ICA),

        FormLine("4000", "경영실태평가 종합등급", 0, "count",
                 float(rating.composite_grade),
                 formula=f"부문 가중평균 {rating.composite:.2f} → "
                         f"{rating.composite_label}",
                 citation=_C31, source_module=f"{_M_PRU}.camel",
                 is_subtotal=True),
    ]
    for i, (_, row) in enumerate(camel.iterrows(), start=1):
        L.append(FormLine(f"41{i:02d}", f"부문 · {row['component']}", 1, "count",
                          float(row["grade"]),
                          formula=f"{row['indicator']} {float(row['value']):.4f} · "
                                  f"가중치 {float(row['weight']):.0%}",
                          citation=str(row["basis"]),
                          source_module=f"{_M_PRU}.camel"))
    L.append(FormLine("9000", "경영실태평가 대사 비고", 0, "text", None,
                      text_value=_CAMEL_NOTE, citation=_C31))
    checks = [
        _ratio_check("총자본비율 = 자기자본 ÷ 위험가중자산", L, "1200",
                     "1000", "1100"),
        FormCheck("총 리스크량비율 = 구성 지표 합",
                  sum(_val(L, cd)
                      for cd in ("2500", "2550", "2600", "2700", "2800"))
                  + _amount(c["rwa_floor_addon"]) / c["capital"],
                  _val(L, "2900"), 1e-12),
        FormCheck("고정이하여신비율 = 경영실태평가 자산건전성 지표",
                  float(_camel_row(rating, "자산건전성")["value"]),
                  _val(L, "2300"), 1e-12),
        FormCheck("유동성커버리지비율 = 경영실태평가 유동성 지표",
                  float(_camel_row(rating, "유동성")["value"]),
                  _val(L, "3200"), 1e-12),
        FormCheck("경영실태평가 가중치 합 = 1", 1.0,
                  float(camel["weight"].sum()), 1e-9),
        # 비고 라인이 "나머지 5개 부문은 pru_camel과 동일하다"고 산문으로 주장한다.
        # 주장만 하고 대사하지 않으면 다른 부문이 갈라져도 아무도 모른다.
        FormCheck("자산건전성 외 5개 부문 등급 = pru_camel", 5.0,
                  float(sum(
                      1 for _, rw in camel.iterrows()
                      if rw["component"] != "자산건전성"
                      and float(rw["grade"]) == float(
                          ctx.tables["pru_camel"].set_index("component")
                          .loc[rw["component"], "grade"]))), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2914

def _b2914(ctx):
    """Credit VaR — ICAAP 신용 경제자본(99.9% 비예상손실)이 정본이다."""
    c = _core(ctx)
    ic = ctx.result.icaap
    rr = ctx.tables["rwa_result"]
    el = float(rr["expected_loss"].fillna(0.0).sum())
    pre = c["credit_ec"] - c["conc_addon"]
    L = [
        FormLine("1000", "Credit VaR (신용 경제자본)", 0, "KRW", c["credit_ec"],
                 formula="99.9% 신뢰수준 비예상손실 — 편중 가산 포함",
                 citation="Basel SRP20 · 은행업감독규정 제30조",
                 source_module=_M_ICA, is_subtotal=True),
        FormLine("1100", "내부등급법 비예상손실 (K × EAD)", 1, "KRW",
                 _amount(c["rwa_irb"]),
                 formula="IRB 위험가중자산 × 8% = Σ K × EAD",
                 citation="CRE31.4 99.9% ASRF", source_module=_M_RWA),
        FormLine("1200", "표준방법 소요자본", 1, "KRW", _amount(c["rwa_sa"]),
                 formula="표준방법 위험가중자산 × 8%", citation="CRE20",
                 source_module="risk_lib.capital.rwa_sa"),
        FormLine("1250", "구조화 소요자본 (집합투자증권·유동화)", 1, "KRW",
                 _amount(c["rwa_structured"]),
                 formula="구조화 위험가중자산 × 8%",
                 citation="CRE60 · CRE40",
                 source_module="risk_lib.datamodel.securitisation"),
        FormLine("1300", "신용편중 가산", 1, "KRW", c["conc_addon"],
                 formula="granularity adjustment (B2912와 같은 값)",
                 citation="SRP30", source_module=_M_ICA),
        FormLine("2000", "예상손실 (EL) — 참고", 0, "KRW", el,
                 formula="Credit VaR는 비예상손실 기준 — EL은 충당금이 흡수한다",
                 citation="CRE31.4", source_module=_M_RWA),
        FormLine("3000", "가용 자본 (AFR)", 0, "KRW",
                 float(ic.available_capital),
                 formula="자기자본 = 내부자본 적정성 판정 분모",
                 citation="SRP20", source_module=_M_ICA, is_subtotal=True),
        FormLine("4000", "Credit VaR ÷ 가용 자본", 0, "ratio",
                 c["credit_ec"] / float(ic.available_capital),
                 formula="신용 경제자본 소진율", citation=_C31,
                 source_module=_M_ICA),
        FormLine("5000", "신뢰수준", 0, "ratio", 0.999,
                 formula="1년 보유기간 · ASRF 모형",
                 citation="CRE31.4 · SRP20"),
        FormLine("9000", "규제자본과의 차이", 0, "text", None,
                 text_value="Credit VaR는 내부등급법 UL과 표준방법 소요자본에 편중 "
                            "가산을 더한 값이다. B2904 신용리스크량은 여기에 "
                            "거래상대방신용리스크 위험가중자산 × 8%가 더 들어가므로 "
                            "두 값은 같지 않다.",
                 citation="SRP20 · CRE52"),
    ]
    checks = [
        _sum_check("Credit VaR = IRB UL + 표준방법 자본 + 구조화 + 편중 가산",
                   L, "1000", ("1100", "1200", "1250", "1300")),
        _ratio_check("소진율 = Credit VaR ÷ 가용 자본", L, "4000",
                     "1000", "3000"),
        FormCheck("가용 자본 = 자기자본", c["capital"], _val(L, "3000"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2915

def _b2915(ctx):
    """총 리스크량비율 — 리스크량 5종 합계 ÷ 자기자본."""
    c = _core(ctx)
    ra = _risk_amounts(ctx, c)
    total_ra = sum(ra.values())
    pillar1 = _amount(c["rwa_total"])
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", c["capital"],
                 citation="은행업감독규정 제26조", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2000", "총 리스크량", 0, "KRW", total_ra,
                 formula="신용 + 구조화 + 시장 + 운영 + 산출하한 조정 + 신용편중",
                 citation=_C26, source_module=_M_CAP, is_subtotal=True),
    ]
    codes = []
    for i, (name, amt) in enumerate(ra.items(), start=1):
        code = f"21{i:02d}"
        codes.append(code)
        note = ("ICAAP 경제자본 가산액 — 편중리스크는 Pillar 1 위험가중자산이 없다"
                if name == "신용편중" else f"{name} {_RA_DEF}")
        L.append(FormLine(code, f"리스크량 · {name}", 1, "KRW", amt,
                          formula=note, citation=_C26, source_module=_M_CAP))
    L += [
        FormLine("3000", "총 리스크량비율", 0, "ratio", total_ra / c["capital"],
                 formula="총 리스크량 ÷ 자기자본", citation=_C31,
                 source_module=_M_CAP),
        FormLine("4000", "Pillar 1 규제 소요자본", 0, "KRW", pillar1,
                 formula="위험가중자산 합계 × 8%", citation=_C26,
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("4100", "Pillar 1 소요자본비율", 1, "ratio",
                 pillar1 / c["capital"],
                 formula="규제 소요자본 ÷ 자기자본 — 총자본비율의 역수 × 8%",
                 source_module=_M_CAP),
        FormLine("4200", "Pillar 2 가산 (신용편중)", 1, "KRW", ra["신용편중"],
                 formula="총 리스크량 − Pillar 1 소요자본",
                 citation="SRP30", source_module=_M_ICA),
        FormLine("5000", "자기자본 여유", 0, "KRW", c["capital"] - total_ra,
                 formula="자기자본 − 총 리스크량", source_module=_M_CAP),
    ]
    checks = [
        _sum_check("총 리스크량 = 6개 리스크량 합", L, "2000", tuple(codes)),
        _ratio_check("총 리스크량비율 = 리스크량 ÷ 자기자본", L, "3000",
                     "2000", "1000"),
        FormCheck("Pillar 1 소요자본 = 위험가중자산 × 8%",
                  c["rwa_total"] * _CAPITAL_RATIO, _val(L, "4000"), 1.0),
        FormCheck("Pillar 1 = 총 리스크량 − Pillar 2 가산",
                  total_ra - ra["신용편중"], _val(L, "4000"), 1.0),
        _ratio_check("Pillar 1 소요자본비율 = 소요자본 ÷ 자기자본", L, "4100",
                     "4000", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2916

def _b2916(ctx):
    """유동성리스크 지표 — LCR·NSFR·국내 유동성 지표·만기불일치."""
    c = _core(ctx)
    r = ctx.result
    lcr = r.alm["lcr"]
    nsfr = r.alm["nsfr"]
    dom = ctx.tables["pru_liquidity_ratio"]
    gap = ctx.tables["alm_repricing_gap"]
    rating = _camel(ctx)
    # 1년 이내 누적갭 — 만기불일치는 1년 경계에서 본다.
    cum_1y = float(gap.loc[gap["bucket"] == "6-12m", "cumulative_gap"].iloc[0])
    L = [
        FormLine("1100", "고유동성자산 (HQLA)", 1, "KRW",
                 float(lcr.hqla_total), formula="Level 1 + 2A + 2B (감액 후)",
                 citation="Basel LCR30", source_module="risk_lib.alm.lcr"),
        FormLine("1200", "순현금유출액 (30일)", 1, "KRW",
                 float(lcr.net_outflow),
                 formula="총유출 − min(유입, 총유출 × 75%)",
                 citation="LCR40", source_module="risk_lib.alm.lcr"),
        FormLine("1000", "유동성커버리지비율 (LCR)", 0, "ratio",
                 float(lcr.lcr), formula="HQLA ÷ 순현금유출액",
                 citation="LCR20.1 · 은행업감독규정 제26조 제1항",
                 source_module="risk_lib.alm.lcr", is_subtotal=True),
        FormLine("1300", "LCR 규제기준", 1, "ratio", 1.00,
                 citation="은행업감독규정 제26조 제1항"),

        FormLine("2100", "가용안정자금 (ASF)", 1, "KRW", float(nsfr.asf_total),
                 citation="Basel NSF20", source_module="risk_lib.alm.nsfr"),
        FormLine("2200", "필요안정자금 (RSF)", 1, "KRW", float(nsfr.rsf_total),
                 citation="NSF30", source_module="risk_lib.alm.nsfr"),
        FormLine("2000", "순안정자금조달비율 (NSFR)", 0, "ratio",
                 float(nsfr.nsfr), formula="가용안정자금 ÷ 필요안정자금",
                 citation="NSF20.1", source_module="risk_lib.alm.nsfr",
                 is_subtotal=True),
        FormLine("2300", "NSFR 규제기준", 1, "ratio", 1.00,
                 citation="은행업감독규정 제26조 제1항 · NSF20.1"),
    ]
    for i, (_, row) in enumerate(dom.iterrows(), start=1):
        base = 3000 + i * 100
        L += [
            FormLine(str(base), str(row["metric"]), 0, "ratio",
                     float(row["value"]), formula="분자 ÷ 분모",
                     citation=str(row["citation"]),
                     source_module=f"{_M_PRU}.liquidity", is_subtotal=True),
            FormLine(str(base + 10), "기준", 1, "ratio", float(row["threshold"]),
                     formula="이상" if str(row["direction"]) == "min" else "이하",
                     citation=str(row["citation"])),
            FormLine(str(base + 20), "충족 여부", 1, "count",
                     1.0 if bool(row["passes"]) else 0.0, formula="1 = 충족",
                     source_module=f"{_M_PRU}.liquidity"),
        ]
    L += [
        FormLine("4100", "1년 이내 누적 만기갭", 1, "KRW", cum_1y,
                 formula="자산 − 부채 누적 (6-12m 구간까지)",
                 citation="Basel SRP31 재가격 갭",
                 source_module="risk_lib.alm.balance_sheet"),
        FormLine("4200", "총자산", 1, "KRW", c["total_assets"],
                 citation="은행업감독규정 제99조 업무보고서",
                 source_module=f"{_M_PRU}.financials"),
        FormLine("4000", "만기불일치비율 (1년 이내)", 0, "ratio",
                 cum_1y / c["total_assets"],
                 formula="1년 이내 누적 만기갭 ÷ 총자산 — 음수는 부채 초과",
                 citation=_C31, source_module="risk_lib.alm.balance_sheet",
                 is_subtotal=True),
        FormLine("5000", "경영실태평가 유동성 등급", 0, "count",
                 float(_camel_row(rating, "유동성")["grade"]),
                 formula="LCR 등급에 국내 유동성 지표 위반 건수를 반영",
                 citation=_C31, source_module=f"{_M_PRU}.camel"),
        FormLine("5100", "국내 유동성 지표 위반 건수", 1, "count",
                 float(int((~dom["passes"]).sum())),
                 formula="위반 1건당 유동성 등급 1단계 하향",
                 source_module=f"{_M_PRU}.camel"),
    ]
    checks = [
        _ratio_check("LCR = HQLA ÷ 순현금유출액", L, "1000", "1100", "1200"),
        _ratio_check("NSFR = ASF ÷ RSF", L, "2000", "2100", "2200"),
        _ratio_check("만기불일치비율 = 누적갭 ÷ 총자산", L, "4000",
                     "4100", "4200"),
        FormCheck("LCR = 경영실태평가 유동성 지표",
                  float(_camel_row(rating, "유동성")["value"]),
                  _val(L, "1000"), 1e-12),
        # 유동성 부문은 pru_camel과 갈라지지 않는다 — 갈라지는 것은 자산건전성
        # 하나뿐이라는 사실을 서식이 스스로 확인한다.
        FormCheck("유동성 등급 = pru_camel 유동성 등급",
                  float(ctx.tables["pru_camel"].set_index("component")
                        .loc["유동성", "grade"]),
                  _val(L, "5000"), 1e-9),
    ]
    for i, (_, row) in enumerate(dom.iterrows(), start=1):
        base = 3000 + i * 100
        ok = (float(row["value"]) >= float(row["threshold"])
              if str(row["direction"]) == "min"
              else float(row["value"]) <= float(row["threshold"]))
        checks.append(FormCheck(f"{row['metric']} 충족 판정이 방향과 일치",
                                1.0 if ok else 0.0, _val(L, str(base + 20)),
                                1e-9))
        # 라인은 "분자 ÷ 분모"라고 적어 놓고 대사를 하지 않으면, 원장의 분자·분모가
        # 지표값과 어긋나도 서식이 그대로 나간다. 원장에 두 칸이 다 있으므로 건다.
        den = float(row["denominator"])
        checks.append(FormCheck(f"{row['metric']} = 분자 ÷ 분모",
                                float(row["numerator"]) / den if den else 0.0,
                                _val(L, str(base)), 1e-9))
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2901": ("Basel III CRE31.4 기대손실 · 은행업감독규정 제30조", "PRD-ECL",
              _b2901),
    "B2902": ("은행업감독규정 제29조 제1항 · 제31조 경영실태평가", "PRD-RDM",
              _b2902),
    "B2903": ("은행업감독규정 제27조 · 제31조 경영실태평가", "PRD-RDM", _b2903),
    "B2904": ("은행업감독규정 제26조 제1항 · Basel III CRE20~CRE36", "PRD-RWA",
              _b2904),
    "B2906-2": ("은행업감독규정 제26조 제1항 · Basel MAR40 간편표준방법",
                "PRD-MKT", _b2906_2),
    "B2906-3": ("은행업감독규정 제26조 제2항 연결기준 · Basel MAR40", "PRD-MKT",
                _b2906_3),
    "B2907": ("Basel MAR11 트레이딩계정 편입기준 · 은행업감독규정 제99조",
              "PRD-MKT", _b2907),
    "B2909-1": ("은행업감독규정 제30조의2 · Basel SRP31.90 6개 충격 · "
                "SRP31.92 이상치 판정 (연결기준)", "PRD-ALM",
                _b2909_1),
    "B2910": ("은행업감독규정 제27조 · 동 시행세칙 연체기간 구분", "PRD-RDM",
              _b2910),
    "B2911-1": ("은행업감독규정 제26조 제1항 · Basel OPE25 신표준방법", "PRD-RWA",
                _b2911_1),
    "B2912": ("Basel SRP30 신용집중리스크 · 은행업감독규정 제30조", "PRD-RDM",
              _b2912),
    "B2913": ("은행업감독규정 제31조~제33조 경영실태평가 계량지표", "PRD-CAP",
              _b2913),
    "B2914": ("Basel SRP20 내부자본 · 은행업감독규정 제30조", "PRD-CAP", _b2914),
    "B2915": ("은행업감독규정 제26조 제1항 · 제30조", "PRD-CAP", _b2915),
    "B2916": ("은행업감독규정 제26조 제1항·제63조 · Basel LCR20.1 · NSF20.1",
              "PRD-ALM", _b2916),
}
