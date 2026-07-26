"""금감원 FINES 업무보고서 — 자산건전성 (기업·일반여신) 14건.

근거는 은행업감독규정 제27조(자산건전성 5단계 분류)와 제29조(대손충당금
최저적립률)다. IFRS 9 5.5 기대신용손실과는 **별개 체계**이며 둘 다 보고 대상이라,
감독분류·최저적립액은 `rdm_asset_quality`에서, 회계 충당금은 `ecl_result`에서
각각 가져와 같은 라인에 나란히 싣는다. 최저적립률은
`risk_lib.datamodel.materialize_detail._MIN_PROVISION_RATE`를 import해 쓴다 —
서식이 자기 사본을 들고 있으면 규정 개정 때 조용히 갈라진다.

**원장에 없는 항목은 파생값이다.** 여신종별(자금용도)·채권재조정 방식·전기말
잔액·사유별 증감·지급보증 대지급 전이율은 포트폴리오에 열이 없어
`forms_fss_asset_data`가 기준일 고정 시드로 결정론적으로 만든다. 파생 라인은
formula에 "파생"임을 남긴다. 변동표(B2405·B2413·B2420·B2421)는 **기말을 산출값에
앵커**하고 기초·증감만 파생하므로, "기초 + 증가 − 감소 = 기말" FormCheck는
파생 난수끼리의 자기충족이 아니라 산출값과의 대사다.

난수는 아니지만 실측도 아닌 **대용값**이 둘 더 있다. B2408 유가증권 5단계 분류는
유가증권 건전성분류 원장이 없어 같은 발행자 성격 여신의 분류 구성비를 대용하고,
B2413 부외 상각채권 기말은 상각채권 원장이 없어 IFRS 9 3단계 ECL 합계를 준용한다.
둘 다 해당 라인 formula에 "대용"이라 적는다 — 실측처럼 보이면 안 된다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

from risk_lib.datamodel.materialize_detail import _MIN_PROVISION_RATE
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_asset_data import (
    AQ_ORDER, NPL_CLASSES, PRODUCTS, RESTRUCT_METHODS,
    derive_flow, guarantee_frame, loan_book, restructured,
)

_M_RDM = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_DER = "risk_lib.regulatory.forms_fss_asset_data"
_M_SELF = "risk_lib.regulatory.forms_fss_asset"
# 실현 LGD 백테스트의 실제 산출처. `risk_lib.credit.lgd`는 이 저장소에 없는 경로다 —
# 존재하지 않는 모듈을 출처로 달면 추적이 거기서 끊긴다.
_M_LGD = "risk_lib.models.lgd_model.lgd_backtest"
_C27 = "은행업감독규정 제27조 자산건전성 5단계 분류"
_C29 = "은행업감독규정 제29조 제1항 최저적립률"
_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"


def _flow_lines(base: int, title: str, closing: float, opening: float,
                inc: dict[str, float], dec: dict[str, float],
                inc_labels: tuple[str, ...], dec_labels: tuple[str, ...],
                anchor: str, *, anchor_module: str = _M_RDM,
                anchor_citation: str = _C27) -> list[FormLine]:
    """기초 → 증가 → 감소 → 기말 변동표 한 블록.

    기말은 앵커(산출값)이고 나머지는 파생이다. 앵커의 출처는 블록마다 다르므로
    (감독분류 원장 · ECL · 파생 대지급금) 호출자가 지정한다 — 여기서 _M_RDM으로
    못 박으면 ECL·파생에서 온 값이 원장값처럼 보인다.
    """
    L = [
        FormLine(str(base), f"{title} — 기말 잔액", 0, "KRW", closing,
                 formula=anchor, citation=anchor_citation,
                 source_module=anchor_module, is_subtotal=True),
        FormLine(str(base + 10), f"{title} — 기초 잔액", 1, "KRW", opening,
                 formula=f"{_DERIVED} (전기말 원장 미보유)", citation=_C27,
                 source_module=_M_DER),
        FormLine(str(base + 100), "증가 계", 1, "KRW", sum(inc.values()),
                 formula="기말 − 기초 + 감소 계로 역산", citation=_C27,
                 source_module=_M_DER, is_subtotal=True),
    ]
    for i, lab in enumerate(inc_labels, start=1):
        L.append(FormLine(f"{base + 100 + i * 10}", f"증가 · {lab}", 2, "KRW",
                          inc[lab], formula=_DERIVED, source_module=_M_DER))
    L.append(FormLine(str(base + 200), "감소 계", 1, "KRW", sum(dec.values()),
                      citation=_C27, source_module=_M_DER, is_subtotal=True))
    for i, lab in enumerate(dec_labels, start=1):
        L.append(FormLine(f"{base + 200 + i * 10}", f"감소 · {lab}", 2, "KRW",
                          dec[lab], formula=_DERIVED, source_module=_M_DER))
    return L


def _flow_checks(L: list[FormLine], base: int, title: str,
                 inc_labels: tuple[str, ...], dec_labels: tuple[str, ...]
                 ) -> list[FormCheck]:
    tol = max(1.0, abs(_val(L, str(base))) * 1e-9)
    return [
        FormCheck(f"{title} 기말 = 기초 + 증가 − 감소", _val(L, str(base)),
                  _val(L, str(base + 10)) + _val(L, str(base + 100))
                  - _val(L, str(base + 200)), tol),
        _sum_check(f"{title} 증가 계 = 사유별 합", L, str(base + 100),
                   tuple(str(base + 100 + i * 10)
                         for i in range(1, len(inc_labels) + 1)), tol),
        _sum_check(f"{title} 감소 계 = 사유별 합", L, str(base + 200),
                   tuple(str(base + 200 + i * 10)
                         for i in range(1, len(dec_labels) + 1)), tol),
    ]


# ---------------------------------------------------------------- B2402

def _b2402(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대손충당금 등 설정현황 — 감독 최저적립액·회계 충당금·대손준비금을 나란히."""
    aq = ctx.tables["rdm_asset_quality"]
    br = ctx.tables["ecl_provision_bridge"].sort_values("seq")
    total = float(aq["balance"].sum())
    min_p = float(aq["min_provision"].sum())
    ifrs = float(aq["ifrs9_provision"].sum())
    npl = float(aq[aq["classification"].isin(NPL_CLASSES)]["balance"].sum())
    L = [
        FormLine("1000", "총 여신 잔액", 0, "KRW", total, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2000", "감독규정 최저적립액 합계", 0, "KRW", min_p,
                 formula="Σ 잔액 × 분류별 최저적립률", citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3000", "대손충당금 (IFRS 9 ECL)", 0, "KRW", ifrs,
                 citation="IFRS 9 5.5 기대신용손실", source_module=_M_ECL,
                 is_subtotal=True),
    ]
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = aq[aq["classification"] == cls]
        L.append(FormLine(f"{1000 + j * 10}", f"{cls} — 잔액", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"{len(s):,}건", citation=_C27,
                          source_module=_M_RDM))
        L.append(FormLine(f"{2000 + j * 10}", f"{cls} — 최저적립액", 1, "KRW",
                          float(s["min_provision"].sum()),
                          formula=(f"최저적립률 기업 "
                                   f"{_MIN_PROVISION_RATE['기업여신'][cls]:.2%} · 가계 "
                                   f"{_MIN_PROVISION_RATE['가계여신'][cls]:.2%}"),
                          citation=_C29, source_module=_M_RDM))
        L.append(FormLine(f"{3000 + j * 10}", f"{cls} — 대손충당금", 1, "KRW",
                          float(s["ifrs9_provision"].sum()),
                          citation="IFRS 9 5.5", source_module=_M_ECL))
    L += [
        FormLine("4000", "대손준비금 소요액", 0, "KRW",
                 float(aq["reserve_shortfall"].sum()),
                 formula="Σ max(0, 최저적립액 − 충당금)  ※ 익스포저 단위",
                 citation="은행업감독규정 제29조 제2항", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("5000", "고정이하여신", 0, "KRW", npl, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("5100", "충당금 적립률", 0, "ratio",
                 ifrs / total if total else 0.0,
                 formula="대손충당금 ÷ 총 여신", source_module=_M_ECL),
        FormLine("5200", "고정이하여신 대비 충당금 커버리지", 0, "ratio",
                 ifrs / npl if npl else 0.0,
                 formula="대손충당금 ÷ 고정이하여신", source_module=_M_ECL),
    ]
    # 충당금 전입 명세는 파생이 아니라 ECL 브리지 산출 그대로다.
    L.append(FormLine("6000", "기초 대손충당금", 0, "KRW",
                      float(br[br["step"] == "opening"]["amount"].iloc[0]),
                      citation="IFRS 9 5.5 충당금 조정", source_module=_M_ECL,
                      is_subtotal=True))
    steps = ("pd_effect", "lgd_effect", "ead_effect", "migration_effect")
    for i, st in enumerate(steps, start=1):
        L.append(FormLine(f"{6000 + i * 10}", f"당기 변동 · {st}", 1, "KRW",
                          float(br[br["step"] == st]["amount"].iloc[0]),
                          formula="요인별 분해 (경로 의존 — 순서 고정)",
                          citation="IFRS 9 5.5", source_module=_M_ECL))
    L.append(FormLine("6900", "기말 대손충당금", 0, "KRW",
                      float(br[br["step"] == "closing"]["cumulative"].iloc[0]),
                      citation="IFRS 9 5.5", source_module=_M_ECL,
                      is_subtotal=True))

    # 최저적립액을 규정 요율표에서 독립 재계산해 원장 산출과 맞춘다.
    recomputed = sum(
        float(g["balance"].sum()) * _MIN_PROVISION_RATE[bt][cls]
        for (bt, cls), g in aq.groupby(["borrower_type", "classification"]))
    checks = [
        _sum_check("총 여신 = 분류별 합", L, "1000",
                   tuple(f"{1000 + j * 10}" for j in range(1, 6))),
        _sum_check("최저적립액 합계 = 분류별 합", L, "2000",
                   tuple(f"{2000 + j * 10}" for j in range(1, 6))),
        _sum_check("대손충당금 = 분류별 합", L, "3000",
                   tuple(f"{3000 + j * 10}" for j in range(1, 6))),
        FormCheck("최저적립액 = Σ 잔액 × 규정 요율", recomputed, min_p, 1.0),
        _ratio_check("충당금 적립률 = 충당금 ÷ 총여신", L, "5100", "3000", "1000"),
        _ratio_check("커버리지 = 충당금 ÷ 고정이하", L, "5200", "3000", "5000"),
        FormCheck("기말 충당금 = 기초 + 당기 변동",
                  _val(L, "6900"),
                  _val(L, "6000") + sum(_val(L, f"{6000 + i * 10}")
                                        for i in range(1, 5)), 1.0),
        # 브리지(요인분해)와 원장(익스포저 합)은 서로 다른 산출 경로다 — 같은
        # 서식에 나란히 실으면서 대사하지 않으면 갈라져도 아무도 모른다.
        FormCheck("기말 충당금(브리지) = 대손충당금 합계(원장)",
                  _val(L, "3000"), _val(L, "6900"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2403

def _b2403(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """여신종별 대손충당금 설정현황 — 여신종별은 파생 구분이다."""
    book = loan_book(ctx)
    total = float(book["balance"].sum())
    L = [
        FormLine("1000", "총 여신 잔액", 0, "KRW", total, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "감독규정 최저적립액 합계", 0, "KRW",
                 float(book["min_provision"].sum()), citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "대손충당금 합계 (IFRS 9)", 0, "KRW",
                 float(book["ifrs9_provision"].sum()),
                 citation="IFRS 9 5.5", source_module=_M_ECL, is_subtotal=True),
        FormLine("1030", "대손준비금 소요액 합계", 0, "KRW",
                 float(book["reserve_shortfall"].sum()),
                 citation="은행업감독규정 제29조 제2항", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1040", "총 충당금 적립률", 0, "ratio",
                 float(book["ifrs9_provision"].sum()) / total if total else 0.0,
                 formula="대손충당금 ÷ 총 여신", source_module=_M_ECL),
    ]
    for i, prod in enumerate(PRODUCTS, start=1):
        s = book[book["product"] == prod]
        bal = float(s["balance"].sum())
        base = 2000 + i * 100
        L += [
            FormLine(str(base), f"여신종별 · {prod}", 1, "KRW", bal,
                     formula=f"{len(s):,}건 · 여신종별은 {_DERIVED}",
                     citation=_C27, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "최저적립액", 2, "KRW",
                     float(s["min_provision"].sum()), citation=_C29,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "대손충당금 (IFRS 9)", 2, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
            FormLine(str(base + 30), "대손준비금 소요액", 2, "KRW",
                     float(s["reserve_shortfall"].sum()),
                     citation="은행업감독규정 제29조 제2항", source_module=_M_RDM),
            FormLine(str(base + 40), "충당금 적립률", 2, "ratio",
                     float(s["ifrs9_provision"].sum()) / bal if bal else 0.0,
                     formula="대손충당금 ÷ 여신종별 잔액", source_module=_M_ECL),
        ]
    n = len(PRODUCTS)
    checks = [
        _sum_check("여신종별 잔액 합 = 총 여신", L, "1000",
                   tuple(str(2000 + i * 100) for i in range(1, n + 1))),
        _sum_check("여신종별 최저적립액 합 = 합계", L, "1010",
                   tuple(str(2000 + i * 100 + 10) for i in range(1, n + 1))),
        _sum_check("여신종별 충당금 합 = 합계", L, "1020",
                   tuple(str(2000 + i * 100 + 20) for i in range(1, n + 1))),
        _sum_check("여신종별 준비금 합 = 합계", L, "1030",
                   tuple(str(2000 + i * 100 + 30) for i in range(1, n + 1))),
        _ratio_check("총 적립률 = 충당금 ÷ 총여신", L, "1040", "1020", "1000"),
    ]
    # 여신종별 적립률 칸은 대사가 없으면 틀려도 드러나지 않는다.
    checks += [
        _ratio_check(f"{prod} 적립률 = 충당금 ÷ 잔액", L,
                     str(2000 + i * 100 + 40), str(2000 + i * 100 + 20),
                     str(2000 + i * 100))
        for i, prod in enumerate(PRODUCTS, start=1)
    ]
    return L, checks


# ---------------------------------------------------------------- B2405

_B2405_INC = ("신규 부실 발생", "기존 여신 분류 하락", "이자 미수 전이")
_B2405_DEC = ("정상화 (분류 상향)", "현금 회수", "대손상각", "채권 매각·유동화",
              "담보 처분")


def _b2405(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """고정이하분류여신·무수익여신 사유별 증감내역 — 기말만 산출값, 나머지는 파생."""
    book = loan_book(ctx)
    npl_cls = float(book[book["classification"].isin(NPL_CLASSES)]["balance"].sum())
    npl_acc = float(book[book["npl"]]["balance"].sum())
    L: list[FormLine] = []
    checks: list[FormCheck] = []
    for base, title, closing, anchor in (
            (1000, "고정이하분류여신", npl_cls,
             "고정·회수의문·추정손실 분류 잔액 합"),
            (2000, "무수익여신", npl_acc,
             "3개월 이상 연체 또는 고정이하 분류 잔액 합")):
        opening, inc, dec = derive_flow(f"B2405:{title}", closing,
                                        _B2405_INC, _B2405_DEC)
        L += _flow_lines(base, title, closing, opening, inc, dec,
                         _B2405_INC, _B2405_DEC, anchor)
        checks += _flow_checks(L, base, title, _B2405_INC, _B2405_DEC)
    L.append(FormLine("3000", "무수익여신 − 고정이하여신 차액", 0, "KRW",
                      npl_acc - npl_cls,
                      formula="분류 기준이 연체일수 대용이라 두 정의가 겹친다",
                      citation=_C27, source_module=_M_RDM))
    return L, checks


# ---------------------------------------------------------------- B2407

def _b2407(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """채권재조정여신현황 — 대상 선정·방식은 파생, 잔액·충당금은 산출값."""
    book = loan_book(ctx)
    rs = restructured(ctx)
    total = float(book["balance"].sum())
    rs_bal = float(rs["balance"].sum()) if len(rs) else 0.0
    L = [
        FormLine("1000", "채권재조정여신 잔액", 0, "KRW", rs_bal,
                 formula=f"대상 선정 {_DERIVED} · 잔액은 선정 익스포저의 산출값",
                 citation="은행업감독규정 제27조 · IFRS 9 5.4.3 조건변경",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "채권재조정여신 건수", 0, "count", float(len(rs)),
                 source_module=_M_DER),
        FormLine("1020", "총 여신 대비 비율", 0, "ratio",
                 rs_bal / total if total else 0.0,
                 formula="재조정여신 ÷ 총 여신", source_module=_M_DER),
        FormLine("1030", "총 여신 잔액", 0, "KRW", total, citation=_C27,
                 source_module=_M_RDM),
    ]
    for i, m in enumerate(RESTRUCT_METHODS, start=1):
        s = rs[rs["method"] == m] if len(rs) else rs
        L.append(FormLine(f"{2000 + i * 10}", f"재조정 방식 · {m}", 1, "KRW",
                          float(s["balance"].sum()) if len(s) else 0.0,
                          formula=f"{len(s):,}건 · 방식 부여는 {_DERIVED}",
                          citation="IFRS 9 5.4.3", source_module=_M_DER))
    for j, cls in enumerate(AQ_ORDER, start=1):
        s = rs[rs["classification"] == cls] if len(rs) else rs
        L.append(FormLine(f"{3000 + j * 10}", f"건전성 분류 · {cls}", 1, "KRW",
                          float(s["balance"].sum()) if len(s) else 0.0,
                          formula=f"{len(s):,}건", citation=_C27,
                          source_module=_M_RDM))
    L += [
        FormLine("4000", "재조정여신 최저적립액", 0, "KRW",
                 float(rs["min_provision"].sum()) if len(rs) else 0.0,
                 citation=_C29, source_module=_M_RDM, is_subtotal=True),
        FormLine("4010", "재조정여신 대손충당금 (IFRS 9)", 0, "KRW",
                 float(rs["ifrs9_provision"].sum()) if len(rs) else 0.0,
                 citation="IFRS 9 5.5", source_module=_M_ECL, is_subtotal=True),
    ]
    checks = [
        _sum_check("재조정 방식별 합 = 재조정여신 잔액", L, "1000",
                   tuple(f"{2000 + i * 10}" for i in
                         range(1, len(RESTRUCT_METHODS) + 1))),
        _sum_check("건전성 분류별 합 = 재조정여신 잔액", L, "1000",
                   tuple(f"{3000 + j * 10}" for j in range(1, 6))),
        _ratio_check("재조정여신 비율 = 재조정 ÷ 총여신", L, "1020", "1000", "1030"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2408

# 재무상태표의 「유가증권」은 HQLA Level 2A·2B다 — Level 1(현금·국채)은
# 「현금 및 예치금」으로 표시되므로 이 서식에 국채·통안채는 들어오지 않는다.
# 종목구분을 임의로 「국공채」라 부르면 없는 보유를 있다고 쓰는 셈이라 등급 표기를
# 그대로 두고, 발행자 성격은 분류 구성비 대용에만 쓴다.
_SECURITY_GROUPS = (
    ("유가증권 Level 2A (공공기관·우량 발행자)", "유가증권 (Level 2A)",
     ("sovereign",)),
    ("유가증권 Level 2B (금융·기업 발행자)", "유가증권 (Level 2B)",
     ("bank", "corporate")),
)


def _b2408(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """유가증권의 건전성 분류.

    유가증권 잔액은 재무상태표 산출값이다. **5단계 분류는 원장에 없다** — 유가증권
    건전성분류 원장이 없어 같은 발행자 성격 여신(sovereign / bank·corporate)의 분류
    구성비를 대용으로 적용한다. 난수는 아니지만 실측도 아닌 **대용 배분**이므로
    해당 라인은 formula에 그렇게 남기고 출처를 이 서식 모듈로 표시한다.
    최저적립률도 유가증권 요율표가 따로 없어 기업여신 요율을 준용한다.
    """
    bs = ctx.tables["pru_balance_sheet"]
    book = loan_book(ctx)
    L: list[FormLine] = []
    checks: list[FormCheck] = []
    by_class = {c: 0.0 for c in AQ_ORDER}
    group_codes = []
    for gi, (label, bs_item, classes) in enumerate(_SECURITY_GROUPS, start=1):
        amount = float(bs.loc[bs["item"] == bs_item, "amount"].iloc[0])
        sub = book[book["asset_class"].isin(classes)]
        denom = float(sub["balance"].sum())
        base = 1000 + gi * 100
        group_codes.append(str(base))
        L.append(FormLine(str(base), f"{label} — 잔액", 0, "KRW", amount,
                          formula=f"재무상태표 「{bs_item}」",
                          citation="은행업감독규정 제27조 제1항 유가증권 분류",
                          source_module="risk_lib.prudential.financials",
                          is_subtotal=True))
        alloc = []
        for j, cls in enumerate(AQ_ORDER, start=1):
            share = (float(sub[sub["classification"] == cls]["balance"].sum())
                     / denom) if denom else (1.0 if cls == "정상" else 0.0)
            v = amount * share
            alloc.append(v)
            by_class[cls] += v
            L.append(FormLine(f"{base + j * 10}", f"{label} · {cls}", 1, "KRW",
                              v,
                              formula=(f"대용 배분(유가증권 건전성분류 원장 미보유) "
                                       f"— 잔액 × {'·'.join(classes)} 익스포저 "
                                       f"{cls} 구성비 {share:.4%}"),
                              citation=_C27, source_module=_M_SELF))
        checks.append(FormCheck(f"{label} 분류별 합 = 잔액", amount, sum(alloc),
                                max(1.0, amount * 1e-9)))
    total = sum(float(bs.loc[bs["item"] == it, "amount"].iloc[0])
                for _, it, _ in _SECURITY_GROUPS)
    L.insert(0, FormLine("1000", "유가증권 총액", 0, "KRW", total,
                         formula="Level 2A + Level 2B",
                         citation="은행업감독규정 제27조 제1항",
                         source_module="risk_lib.prudential.financials",
                         is_subtotal=True))
    min_total = 0.0
    for j, cls in enumerate(AQ_ORDER, start=1):
        L.append(FormLine(f"{2000 + j * 10}", f"분류 합계 · {cls}", 0, "KRW",
                          by_class[cls], formula="종목구분 대용 배분의 합",
                          citation=_C27, source_module=_M_SELF))
        # 유가증권은 기업여신 요율표를 준용한다 (가계 구분이 없다).
        rate = _MIN_PROVISION_RATE["기업여신"][cls]
        min_total += by_class[cls] * rate
        L.append(FormLine(f"{3000 + j * 10}", f"최저적립액 · {cls}", 1, "KRW",
                          by_class[cls] * rate,
                          formula=f"분류 잔액 × 기업여신 요율 {rate:.2%} 준용",
                          citation=_C29, source_module=_M_SELF))
    L.append(FormLine("3000", "최저적립액 합계", 0, "KRW", min_total,
                      citation=_C29, source_module=_M_RDM, is_subtotal=True))
    checks += [
        _sum_check("종목구분 합 = 유가증권 총액", L, "1000", tuple(group_codes),
                   max(1.0, total * 1e-9)),
        _sum_check("분류 합계 = 유가증권 총액", L, "1000",
                   tuple(f"{2000 + j * 10}" for j in range(1, 6)),
                   max(1.0, total * 1e-9)),
        _sum_check("최저적립액 합계 = 분류별 합", L, "3000",
                   tuple(f"{3000 + j * 10}" for j in range(1, 6)),
                   max(1.0, min_total * 1e-9)),
    ]
    return L, checks


# ---------------------------------------------------------------- B2410

_DPD_BANDS = ((1, 29, "1~29일"), (30, 59, "30~59일"), (60, 89, "60~89일"),
              (90, 10_000, "90일 이상"))


def _b2410(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """여신종별 연체대출채권 — 여신종별은 파생, 연체일수·잔액은 원장값."""
    book = loan_book(ctx)
    total = float(book["balance"].sum())
    od = book[book["dpd"] >= 1]
    od_bal = float(od["balance"].sum())
    L = [
        FormLine("1000", "총 대출채권 잔액", 0, "KRW", total, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "연체대출채권 (1일 이상)", 0, "KRW", od_bal,
                 formula=f"{len(od):,}건", citation=_C27, source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1020", "연체비율", 0, "ratio",
                 od_bal / total if total else 0.0,
                 formula="연체대출채권 ÷ 총 대출채권", source_module=_M_RDM),
    ]
    for i, prod in enumerate(PRODUCTS, start=1):
        s = book[book["product"] == prod]
        bal = float(s["balance"].sum())
        so = float(s[s["dpd"] >= 1]["balance"].sum())
        base = 2000 + i * 100
        L += [
            FormLine(str(base), f"여신종별 · {prod}", 1, "KRW", bal,
                     formula=f"여신종별은 {_DERIVED}", citation=_C27,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "연체대출채권", 2, "KRW", so,
                     citation=_C27, source_module=_M_RDM),
            FormLine(str(base + 20), "연체비율", 2, "ratio",
                     so / bal if bal else 0.0, source_module=_M_RDM),
        ]
    for k, (lo, hi, label) in enumerate(_DPD_BANDS, start=1):
        s = book[(book["dpd"] >= lo) & (book["dpd"] <= hi)]
        L.append(FormLine(f"{3000 + k * 10}", f"연체기간 · {label}", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"{len(s):,}건",
                          citation="은행업감독규정 시행세칙 연체기간 구분",
                          source_module=_M_RDM))
    n = len(PRODUCTS)
    checks = [
        _sum_check("여신종별 잔액 합 = 총 대출채권", L, "1000",
                   tuple(str(2000 + i * 100) for i in range(1, n + 1))),
        _sum_check("여신종별 연체 합 = 총 연체", L, "1010",
                   tuple(str(2000 + i * 100 + 10) for i in range(1, n + 1))),
        _sum_check("연체기간 구간 합 = 총 연체", L, "1010",
                   tuple(f"{3000 + k * 10}" for k in
                         range(1, len(_DPD_BANDS) + 1))),
        _ratio_check("연체비율 = 연체 ÷ 총 대출채권", L, "1020", "1010", "1000"),
    ]
    checks += [
        _ratio_check(f"{prod} 연체비율 = 연체 ÷ 잔액", L,
                     str(2000 + i * 100 + 20), str(2000 + i * 100 + 10),
                     str(2000 + i * 100))
        for i, prod in enumerate(PRODUCTS, start=1)
    ]
    return L, checks


# ---------------------------------------------------------------- B2413

_B2413_INC = ("당기 대손상각 실행", "미수이자 부외 전이")
_B2413_DEC = ("현금 회수", "채권 매각", "소멸시효 완성", "채무 면제")


def _b2413(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대손상각채권 변동상황.

    부외 상각채권 원장이 없다. 기말 잔액을 IFRS 9 3단계 ECL 합계(회수불능으로
    인식한 누적 손실액)에 앵커하고 기초·증감만 파생한다.
    """
    by_stage = ctx.result.ecl["by_stage"]
    stage3 = float(by_stage.loc[3, "ecl"]) if 3 in by_stage.index else 0.0
    stage3_ead = float(by_stage.loc[3, "ead"]) if 3 in by_stage.index else 0.0
    opening, inc, dec = derive_flow("B2413", stage3, _B2413_INC, _B2413_DEC)
    L = _flow_lines(1000, "부외 대손상각채권", stage3, opening, inc, dec,
                    _B2413_INC, _B2413_DEC,
                    "대용 앵커 — 부외 상각채권 원장 미보유, IFRS 9 3단계 ECL "
                    "합계(회수불능 인식 누적액)를 준용",
                    anchor_module=_M_ECL,
                    anchor_citation="IFRS 9 5.4.4 상각(write-off) · 은행업감독규정 제30조 대손상각")
    L += [
        FormLine("2000", "IFRS 9 3단계 익스포저 (EAD)", 0, "KRW", stage3_ead,
                 citation="IFRS 9 5.5.5 lifetime ECL · 부록 A 신용손상 정의", source_module=_M_ECL,
                 is_subtotal=True),
        # by_stage["coverage"]는 익스포저 단순평균이라 총액 비율과 다르다 —
        # 서식은 총액 기준을 요구하므로 여기서 직접 나눈다.
        FormLine("2010", "3단계 충당금 적립률", 0, "ratio",
                 stage3 / stage3_ead if stage3_ead else 0.0,
                 formula="3단계 ECL ÷ 3단계 EAD (총액 기준)", citation="IFRS 9 5.5",
                 source_module=_M_ECL),
        FormLine("2020", "당기 상각액 / 3단계 ECL", 0, "ratio",
                 sum(inc.values()) / stage3 if stage3 else 0.0,
                 formula="증가 계 ÷ 3단계 ECL", source_module=_M_DER),
    ]
    checks = _flow_checks(L, 1000, "부외 대손상각채권", _B2413_INC, _B2413_DEC)
    checks.append(_ratio_check("3단계 적립률 = ECL ÷ EAD", L, "2010", "1000",
                               "2000"))
    checks.append(_ratio_check("당기 상각 비율 = 증가계 ÷ 3단계 ECL", L, "2020",
                               "1100", "1000"))
    return L, checks


# ---------------------------------------------------------------- B2416-1

def _b2416_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """업종별 대출금의 무수익여신현황 — 전부 산출값이다 (파생 없음)."""
    book = loan_book(ctx)
    corp = book[book["asset_class"] == "corporate"]
    sectors = tuple(sorted(corp["sector"].dropna().unique()))
    total = float(corp["balance"].sum())
    npl = float(corp[corp["npl"]]["balance"].sum())
    L = [
        FormLine("1000", "기업대출금 합계", 0, "KRW", total,
                 formula="asset_class=corporate 기준 — 금융기관·공공자금 여신 제외",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "무수익여신 합계", 0, "KRW", npl,
                 formula="3개월 이상 연체 또는 고정이하 분류",
                 citation="은행업감독규정 제27조 · 무수익여신 산정기준",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "무수익여신비율", 0, "ratio",
                 npl / total if total else 0.0,
                 formula="무수익여신 ÷ 기업대출금", source_module=_M_RDM),
    ]
    for i, sec in enumerate(sectors, start=1):
        s = corp[corp["sector"] == sec]
        bal = float(s["balance"].sum())
        sn = float(s[s["npl"]]["balance"].sum())
        base = 2000 + i * 100
        L += [
            FormLine(str(base), f"업종 · {sec}", 1, "KRW", bal,
                     formula=f"{len(s):,}건", citation=_C27,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "무수익여신", 2, "KRW", sn,
                     citation=_C27, source_module=_M_RDM),
            FormLine(str(base + 20), "무수익여신비율", 2, "ratio",
                     sn / bal if bal else 0.0, source_module=_M_RDM),
            FormLine(str(base + 30), "대손충당금 (IFRS 9)", 2, "KRW",
                     float(s["ifrs9_provision"].sum()),
                     citation="IFRS 9 5.5", source_module=_M_ECL),
        ]
    n = len(sectors)
    checks = [
        _sum_check("업종별 대출금 합 = 기업대출금", L, "1000",
                   tuple(str(2000 + i * 100) for i in range(1, n + 1))),
        _sum_check("업종별 무수익여신 합 = 합계", L, "1010",
                   tuple(str(2000 + i * 100 + 10) for i in range(1, n + 1))),
        _ratio_check("무수익여신비율 = 무수익 ÷ 대출금", L, "1020", "1010", "1000"),
    ]
    checks += [
        _ratio_check(f"{sec} 무수익여신비율 = 무수익 ÷ 잔액", L,
                     str(2000 + i * 100 + 20), str(2000 + i * 100 + 10),
                     str(2000 + i * 100))
        for i, sec in enumerate(sectors, start=1)
    ]
    return L, checks


# ---------------------------------------------------------------- B2417

_B2417_TOP = 20


def _b2417(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """거액 요주의이하 분류여신 보유업체.

    차주 식별은 obligor_id로만 남긴다 — 서식에 개인정보성 식별자를 담지 않는다.
    """
    book = loan_book(ctx)
    tier1 = float(ctx.result.meta["capital"].tier1)
    threshold = tier1 * 0.001
    watch = book[book["classification"] != "정상"]
    by_ob = (watch.groupby("obligor_id")
             .agg(balance=("balance", "sum"),
                  provision=("ifrs9_provision", "sum"),
                  n=("exposure_id", "count"))
             .reset_index()
             .merge(ctx.tables["rdm_obligor"][["obligor_id", "sector"]],
                    on="obligor_id", how="left"))
    large = by_ob[by_ob["balance"] >= threshold].sort_values(
        ["balance", "obligor_id"], ascending=[False, True]).reset_index(drop=True)
    large_total = float(large["balance"].sum())
    L = [
        FormLine("1000", "자기자본 (기본자본)", 0, "KRW", tier1,
                 citation="은행법 제2조 자기자본",
                 source_module="risk_lib.capital.bis"),
        # 제53조의 거액여신은 자기자본 10% 초과분이다. 여기 기준은 그것이 아니라
        # 요주의이하 명세를 뽑기 위한 내부 보고기준(기본자본 0.1%)이므로, 조문을
        # 근거처럼 달지 않고 참고로만 적는다.
        FormLine("1010", "거액 기준금액", 0, "KRW", threshold,
                 formula="기본자본 × 0.1% — 내부 보고기준 (규정상 기준 아님)",
                 citation="내부 보고기준 · cf. 은행업감독규정 제53조 거액여신"
                          "(자기자본 10% 초과)"),
        FormLine("2000", "해당 업체 수", 0, "count", float(len(large)),
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "해당 요주의이하 여신 합계", 0, "KRW", large_total,
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("2020", "전체 요주의이하여신", 0, "KRW",
                 float(watch["balance"].sum()), citation=_C27,
                 source_module=_M_RDM),
        FormLine("2030", "거액 비중", 0, "ratio",
                 large_total / float(watch["balance"].sum())
                 if float(watch["balance"].sum()) else 0.0,
                 formula="거액 요주의이하 ÷ 전체 요주의이하", source_module=_M_RDM),
    ]
    head = large.head(_B2417_TOP)
    for i, (_, r) in enumerate(head.iterrows(), start=1):
        L.append(FormLine(f"3{i:03d}", f"보유업체 · {r['obligor_id']}", 1, "KRW",
                          float(r["balance"]),
                          formula=(f"업종 {r['sector']} · {int(r['n'])}건 · "
                                   f"충당금 {float(r['provision']):,.0f}"),
                          citation=_C27, source_module=_M_RDM))
    L.append(FormLine("3900", "기타 (명세 미기재 업체)", 1, "KRW",
                      large_total - float(head["balance"].sum()),
                      formula=f"상위 {_B2417_TOP}개사 외 {max(0, len(large) - _B2417_TOP):,}개사",
                      citation=_C27, source_module=_M_RDM))
    checks = [
        _sum_check("명세 + 기타 = 거액 요주의이하 합계", L, "2010",
                   tuple(f"3{i:03d}" for i in range(1, len(head) + 1))
                   + ("3900",), max(1.0, large_total * 1e-9)),
        _ratio_check("거액 비중 = 거액 ÷ 전체 요주의이하", L, "2030", "2010", "2020"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2420

_B2420_L_INC = ("원리금 미상환", "기한이익 상실", "재연체 발생")
_B2420_L_DEC = ("정상 회수", "대환·재약정", "대손상각", "채권 매각")
_B2420_G_INC = ("보증채무 이행 청구", "구상권 미회수 전이")
_B2420_G_DEC = ("구상권 회수", "담보 처분", "대손상각")


def _b2420(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """연체대출금 및 지급보증대지급금 발생현황 — 기말은 원장, 기초·사유는 파생."""
    book = loan_book(ctx)
    od_bal = float(book[book["dpd"] >= 1]["balance"].sum())
    gtee_base, subro = guarantee_frame(ctx)
    L: list[FormLine] = []
    checks: list[FormCheck] = []

    o, inc, dec = derive_flow("B2420:연체", od_bal, _B2420_L_INC, _B2420_L_DEC)
    L += _flow_lines(1000, "연체대출금", od_bal, o, inc, dec,
                     _B2420_L_INC, _B2420_L_DEC, "연체일수 1일 이상 여신 잔액 합")
    checks += _flow_checks(L, 1000, "연체대출금", _B2420_L_INC, _B2420_L_DEC)

    o2, inc2, dec2 = derive_flow("B2420:대지급", subro, _B2420_G_INC, _B2420_G_DEC)
    L += _flow_lines(2000, "지급보증대지급금", subro, o2, inc2, dec2,
                     _B2420_G_INC, _B2420_G_DEC,
                     f"지급보증 잔액(원장) × 대지급 전이율 — 전이율은 {_DERIVED}",
                     anchor_module=_M_DER,
                     anchor_citation="은행법 제2조 지급보증")
    checks += _flow_checks(L, 2000, "지급보증대지급금", _B2420_G_INC, _B2420_G_DEC)

    L += [
        FormLine("3000", "지급보증 잔액", 0, "KRW", gtee_base,
                 formula="지급보증성 부외약정(직접신용대체·거래관련) 미사용액",
                 citation="은행법 제2조 지급보증 · Basel III CRE20.94",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "대지급 전이율", 0, "ratio",
                 subro / gtee_base if gtee_base else 0.0,
                 formula=f"대지급금 ÷ 지급보증 잔액 · 전이율은 {_DERIVED}",
                 source_module=_M_DER),
    ]
    checks.append(_ratio_check("대지급 전이율 = 대지급금 ÷ 지급보증", L, "3010",
                               "2000", "3000"))
    return L, checks


# ---------------------------------------------------------------- B2421

_RECOVERY_SEGMENTS = (("corporate", "기업·금융·국가"),
                      ("retail_other", "가계 일반"),
                      ("residential_mortgage", "가계 주택담보"))
_SEG_CLASSES = {"corporate": ("corporate", "bank", "sovereign"),
                "retail_other": ("retail_other",),
                "residential_mortgage": ("residential_mortgage",)}
_B2421_METHOD = ("현금 상환", "담보 처분", "보증인 청구", "채권 매각")
_B2421_INC = ("연체 신규 발생", "대지급 신규 발생")


def _b2421(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """연체대출금 및 지급보증대지급금 회수현황.

    회수율은 난수가 아니라 `result.lgd_metrics`의 세그먼트별 **실현 LGD**에서
    1 − LGD로 뒤집어 쓴다. 회수방법 구성과 기초 미회수 잔액만 파생이다.
    """
    book = loan_book(ctx)
    lgdm = ctx.result.lgd_metrics
    od = book[book["dpd"] >= 1]
    od_bal = float(od["balance"].sum())
    _, subro = guarantee_frame(ctx)
    L = [
        FormLine("1000", "회수대상 채권 계", 0, "KRW", od_bal + subro,
                 formula="연체대출금(원장) + 지급보증대지급금(파생)",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "연체대출금", 1, "KRW", od_bal,
                 formula=f"{len(od):,}건", citation=_C27, source_module=_M_RDM),
        FormLine("1020", "지급보증대지급금", 1, "KRW", subro,
                 formula=f"지급보증 잔액 × 대지급 전이율 ({_DERIVED})",
                 citation="은행법 제2조 지급보증", source_module=_M_DER),
    ]
    seg_rec, seg_codes = [], []
    for i, (seg, label) in enumerate(_RECOVERY_SEGMENTS, start=1):
        bt = lgdm[seg]["backtest"]
        rate = 1.0 - float(bt["mean_realised"])
        s = od[od["asset_class"].isin(_SEG_CLASSES[seg])]
        amt = float(s["balance"].sum()) * rate
        seg_rec.append(amt)
        base = 2000 + i * 100
        seg_codes.append(str(base))
        L += [
            FormLine(str(base), f"세그먼트 회수액 · {label}", 1, "KRW", amt,
                     formula=(f"연체잔액 {float(s['balance'].sum()):,.0f} × 회수율"),
                     citation="Basel III CRE36.83 회수 인식 — 실현 LGD 기반 회수율",
                     source_module=_M_LGD),
            FormLine(str(base + 10), "회수율", 2, "ratio", rate,
                     formula=(f"1 − 실현 LGD {float(bt['mean_realised']):.4f} "
                              f"(관측 {int(bt['n']):,}건)"),
                     citation="CRE36.83", source_module=_M_LGD),
        ]
    # 대지급금은 기업 세그먼트의 실현 회수율을 준용한다.
    corp_rate = 1.0 - float(lgdm["corporate"]["backtest"]["mean_realised"])
    subro_rec = subro * corp_rate
    seg_rec.append(subro_rec)
    seg_codes.append("2400")
    L += [
        FormLine("2400", "세그먼트 회수액 · 지급보증대지급금", 1, "KRW", subro_rec,
                 formula="대지급금 × 기업 실현 회수율", citation="CRE36.83",
                 source_module=_M_LGD),
        FormLine("2410", "회수율", 2, "ratio", corp_rate,
                 citation="CRE36.83", source_module=_M_LGD),
    ]
    rec_total = sum(seg_rec)
    L.insert(3, FormLine("2000", "당기 회수액 계", 0, "KRW", rec_total,
                         citation=_C27, source_module=_M_LGD,
                         is_subtotal=True))

    closing = od_bal + subro - rec_total
    opening, inc, dec = derive_flow("B2421", closing, _B2421_INC, _B2421_METHOD,
                                    dec_total=rec_total)
    L.append(FormLine("3000", "회수방법별 계", 0, "KRW", sum(dec.values()),
                      citation=_C27, source_module=_M_DER, is_subtotal=True))
    for i, m in enumerate(_B2421_METHOD, start=1):
        L.append(FormLine(f"{3000 + i * 10}", f"회수방법 · {m}", 1, "KRW", dec[m],
                          formula=f"회수방법 구성은 {_DERIVED}",
                          source_module=_M_DER))
    L += [
        FormLine("4000", "기말 미회수 잔액", 0, "KRW", closing,
                 formula="회수대상 계 − 당기 회수액 계 (회수대상에 파생 대지급금 포함)",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("4010", "기초 미회수 잔액", 1, "KRW", opening,
                 formula=f"{_DERIVED} (전기말 원장 미보유)", source_module=_M_DER),
        FormLine("4100", "당기 발생 계", 1, "KRW", sum(inc.values()),
                 formula="기말 − 기초 + 당기 회수액으로 역산", source_module=_M_DER,
                 is_subtotal=True),
    ]
    for i, lab in enumerate(_B2421_INC, start=1):
        L.append(FormLine(f"{4100 + i * 10}", f"발생 · {lab}", 2, "KRW", inc[lab],
                          formula=_DERIVED, source_module=_M_DER))
    L.append(FormLine("4200", "당기 회수 계", 1, "KRW", rec_total,
                      citation=_C27, source_module=_M_LGD,
                      is_subtotal=True))
    tol = max(1.0, abs(closing) * 1e-9)
    checks = [
        _sum_check("회수대상 계 = 연체 + 대지급", L, "1000", ("1010", "1020")),
        _sum_check("당기 회수액 계 = 세그먼트별 합", L, "2000", tuple(seg_codes),
                   max(1.0, rec_total * 1e-9)),
        _sum_check("회수방법별 계 = 방법별 합", L, "3000",
                   tuple(f"{3000 + i * 10}" for i in
                         range(1, len(_B2421_METHOD) + 1)),
                   max(1.0, rec_total * 1e-9)),
        FormCheck("회수방법별 계 = 당기 회수액 계", rec_total,
                  _val(L, "3000"), max(1.0, rec_total * 1e-9)),
        FormCheck("기말 미회수 = 기초 + 발생 − 회수", _val(L, "4000"),
                  _val(L, "4010") + _val(L, "4100") - _val(L, "4200"), tol),
        _sum_check("당기 발생 계 = 사유별 합", L, "4100",
                   tuple(f"{4100 + i * 10}" for i in
                         range(1, len(_B2421_INC) + 1)), tol),
    ]
    return L, checks


# ---------------------------------------------------------------- B2424-1

def _b2424_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """기업대출금의 업종별 연체채권 현황 — 전부 산출값이다 (파생 없음)."""
    book = loan_book(ctx)
    corp = book[book["asset_class"] == "corporate"]
    sectors = tuple(sorted(corp["sector"].dropna().unique()))
    total = float(corp["balance"].sum())
    od_bal = float(corp[corp["dpd"] >= 1]["balance"].sum())
    L = [
        FormLine("1000", "기업대출금 합계", 0, "KRW", total,
                 formula="asset_class=corporate 기준 — 금융기관·공공자금 여신 제외",
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "연체채권 (1일 이상)", 0, "KRW", od_bal, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "연체비율", 0, "ratio",
                 od_bal / total if total else 0.0,
                 formula="연체채권 ÷ 기업대출금", source_module=_M_RDM),
        FormLine("1030", "90일 이상 연체채권", 0, "KRW",
                 float(corp[corp["dpd"] >= 90]["balance"].sum()),
                 citation="Basel III CRE36.69 부도 정의", source_module=_M_RDM,
                 is_subtotal=True),
    ]
    for i, sec in enumerate(sectors, start=1):
        s = corp[corp["sector"] == sec]
        bal = float(s["balance"].sum())
        so = float(s[s["dpd"] >= 1]["balance"].sum())
        base = 2000 + i * 100
        L += [
            FormLine(str(base), f"업종 · {sec}", 1, "KRW", bal,
                     formula=f"{len(s):,}건", citation=_C27,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "연체채권", 2, "KRW", so, citation=_C27,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "연체비율", 2, "ratio",
                     so / bal if bal else 0.0, source_module=_M_RDM),
            FormLine(str(base + 30), "90일 이상 연체채권", 2, "KRW",
                     float(s[s["dpd"] >= 90]["balance"].sum()),
                     citation="CRE36.69", source_module=_M_RDM),
        ]
    n = len(sectors)
    checks = [
        _sum_check("업종별 대출금 합 = 기업대출금", L, "1000",
                   tuple(str(2000 + i * 100) for i in range(1, n + 1))),
        _sum_check("업종별 연체채권 합 = 합계", L, "1010",
                   tuple(str(2000 + i * 100 + 10) for i in range(1, n + 1))),
        _sum_check("업종별 90일이상 합 = 합계", L, "1030",
                   tuple(str(2000 + i * 100 + 30) for i in range(1, n + 1))),
        _ratio_check("연체비율 = 연체 ÷ 기업대출금", L, "1020", "1010", "1000"),
    ]
    checks += [
        _ratio_check(f"{sec} 연체비율 = 연체 ÷ 잔액", L,
                     str(2000 + i * 100 + 20), str(2000 + i * 100 + 10),
                     str(2000 + i * 100))
        for i, sec in enumerate(sectors, start=1)
    ]
    return L, checks


# ---------------------------------------------------------------- B2425

def _b2425(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """미사용약정에 대한 충당금 적립현황.

    미사용액·신용환산율은 원장값(`rdm_exposure.undrawn` · CCF 구간)이고, 충당금은
    해당 익스포저의 IFRS 9 커버리지율을 신용환산액에 적용해 산출한다.
    """
    from risk_lib.capital.crm import CCF_BUCKETS
    book = loan_book(ctx).copy()
    book = book[book["ccf_type"].notna()]
    book["ccf"] = book["ccf_type"].map(CCF_BUCKETS).astype(float)
    book["cce"] = book["undrawn"] * book["ccf"]
    book["oba_prov"] = book["cce"] * book["coverage_ratio"]
    und = float(book["undrawn"].sum())
    cce = float(book["cce"].sum())
    prov = float(book["oba_prov"].sum())
    L = [
        FormLine("1000", "미사용약정 잔액 합계", 0, "KRW", und,
                 formula=f"부외약정 {len(book):,}건",
                 citation="Basel III CRE20.94 부외항목", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1010", "신용환산액 합계", 0, "KRW", cce,
                 formula="Σ 미사용액 × 신용환산율", citation="CRE20.94",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "충당금 적립액 합계", 0, "KRW", prov,
                 formula="Σ 신용환산액 × 익스포저 ECL 커버리지율",
                 citation="은행업감독규정 제29조 · IFRS 9 5.5.20 약정",
                 source_module=_M_ECL, is_subtotal=True),
        FormLine("1030", "평균 신용환산율", 0, "ratio",
                 cce / und if und else 0.0,
                 formula="신용환산액 ÷ 미사용약정 잔액", source_module=_M_RDM),
    ]
    types = tuple(t for t in CCF_BUCKETS if (book["ccf_type"] == t).any())
    for i, t in enumerate(types, start=1):
        s = book[book["ccf_type"] == t]
        base = 2000 + i * 100
        L += [
            FormLine(str(base), f"약정유형 · {t}", 1, "KRW",
                     float(s["undrawn"].sum()), formula=f"{len(s):,}건",
                     citation="CRE20.94", source_module=_M_RDM,
                     is_subtotal=True),
            FormLine(str(base + 10), "신용환산율", 2, "ratio",
                     float(CCF_BUCKETS[t]), citation="CRE20.94"),
            FormLine(str(base + 20), "신용환산액", 2, "KRW",
                     float(s["cce"].sum()), formula="미사용액 × 신용환산율",
                     citation="CRE20.94", source_module=_M_RDM),
            FormLine(str(base + 30), "충당금 적립액", 2, "KRW",
                     float(s["oba_prov"].sum()), citation="IFRS 9 5.5.20",
                     source_module=_M_ECL),
        ]
    n = len(types)
    recomputed = sum(float(book[book["ccf_type"] == t]["undrawn"].sum())
                     * float(CCF_BUCKETS[t]) for t in types)
    checks = [
        _sum_check("약정유형별 미사용액 합 = 합계", L, "1000",
                   tuple(str(2000 + i * 100) for i in range(1, n + 1))),
        _sum_check("약정유형별 신용환산액 합 = 합계", L, "1010",
                   tuple(str(2000 + i * 100 + 20) for i in range(1, n + 1))),
        _sum_check("약정유형별 충당금 합 = 합계", L, "1020",
                   tuple(str(2000 + i * 100 + 30) for i in range(1, n + 1))),
        FormCheck("신용환산액 = Σ 미사용액 × 규정 CCF", recomputed, cce, 1.0),
        _ratio_check("평균 신용환산율 = 환산액 ÷ 미사용액", L, "1030", "1010", "1000"),
    ]
    # 유형별 줄도 각자 대사한다 — 합계만 맞으면 유형 간 뒤바뀜을 못 잡는다.
    # 미사용액이 0인 유형은 환산율 칸이 규정 요율이라 나눗셈 대사가 성립하지 않는다.
    checks += [
        _ratio_check(f"{t} 환산율 = 환산액 ÷ 미사용액", L, str(2000 + i * 100 + 10),
                     str(2000 + i * 100 + 20), str(2000 + i * 100))
        for i, t in enumerate(types, start=1) if _val(L, str(2000 + i * 100))
    ]
    return L, checks


# ---------------------------------------------------------------- B2431

def _b2431(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """여신종별 충당금 설정 현황 — 여신종별 × 건전성분류 매트릭스."""
    book = loan_book(ctx)
    total = float(book["balance"].sum())
    min_total = float(book["min_provision"].sum())
    L = [
        FormLine("1000", "총 여신 잔액", 0, "KRW", total, citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "최저적립액 합계", 0, "KRW", min_total, citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "대손충당금 합계 (IFRS 9)", 0, "KRW",
                 float(book["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                 source_module=_M_ECL, is_subtotal=True),
        FormLine("1030", "최저적립 충족 여부", 0, "count",
                 1.0 if float(book["ifrs9_provision"].sum()) >= min_total else 0.0,
                 formula="1 = 충당금 합계 ≥ 최저적립액 합계 (부족분은 대손준비금)",
                 citation="은행업감독규정 제29조 제2항", source_module=_M_RDM),
    ]
    bal_codes, min_codes = [], []
    for i, prod in enumerate(PRODUCTS, start=1):
        s = book[book["product"] == prod]
        base = 2000 + i * 100
        L.append(FormLine(str(base), f"여신종별 · {prod}", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"여신종별은 {_DERIVED}", citation=_C27,
                          source_module=_M_DER, is_subtotal=True))
        for j, cls in enumerate(AQ_ORDER, start=1):
            c = s[s["classification"] == cls]
            code = str(base + j * 10)
            bal_codes.append(code)
            min_codes.append(f"{code}1")
            L.append(FormLine(code, f"{cls} — 잔액", 2, "KRW",
                              float(c["balance"].sum()),
                              formula=f"{len(c):,}건", citation=_C27,
                              source_module=_M_RDM))
            L.append(FormLine(f"{code}1", f"{cls} — 최저적립액", 3, "KRW",
                              float(c["min_provision"].sum()),
                              formula=(f"기업 {_MIN_PROVISION_RATE['기업여신'][cls]:.2%} · "
                                       f"가계 {_MIN_PROVISION_RATE['가계여신'][cls]:.2%}"),
                              citation=_C29, source_module=_M_RDM))
    n = len(PRODUCTS)
    checks = [
        _sum_check("여신종별 잔액 합 = 총 여신", L, "1000",
                   tuple(str(2000 + i * 100) for i in range(1, n + 1))),
        _sum_check("분류별 잔액 합 = 총 여신", L, "1000", tuple(bal_codes)),
        _sum_check("분류별 최저적립액 합 = 합계", L, "1010", tuple(min_codes)),
    ]
    # 매트릭스는 행별로도 닫혀야 한다 — 열 합계만 맞추면 행 간 이동을 못 잡는다.
    for i, prod in enumerate(PRODUCTS, start=1):
        base = 2000 + i * 100
        checks.append(_sum_check(f"{prod} 분류별 잔액 합 = 여신종별 잔액", L,
                                 str(base),
                                 tuple(str(base + j * 10) for j in range(1, 6))))
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2402": ("은행업감독규정 제29조 · IFRS 9 5.5", "PRD-ECL", _b2402),
    "B2403": ("은행업감독규정 제29조 제1항", "PRD-ECL", _b2403),
    "B2405": ("은행업감독규정 제27조", "PRD-RDM", _b2405),
    "B2407": ("은행업감독규정 제27조 · IFRS 9 5.4.3 조건변경", "PRD-RDM", _b2407),
    "B2408": ("은행업감독규정 제27조 제1항", "PRD-RDM", _b2408),
    "B2410": ("은행업감독규정 제27조 · 동 시행세칙 연체기간 구분", "PRD-RDM", _b2410),
    "B2413": ("은행업감독규정 제30조 대손상각 · IFRS 9 5.4.4", "PRD-ECL", _b2413),
    "B2416-1": ("은행업감독규정 제27조 · 무수익여신 산정기준", "PRD-RDM", _b2416_1),
    "B2417": ("은행업감독규정 제27조 · 제53조 거액여신", "PRD-RDM", _b2417),
    "B2420": ("은행업감독규정 제27조 · 은행법 제2조 지급보증", "PRD-RDM", _b2420),
    "B2421": ("은행업감독규정 제27조 · Basel III CRE36.83", "PRD-RDM", _b2421),
    "B2424-1": ("은행업감독규정 제27조", "PRD-RDM", _b2424_1),
    "B2425": ("은행업감독규정 제29조 · Basel III CRE20.94", "PRD-ECL", _b2425),
    "B2431": ("은행업감독규정 제29조 제1항", "PRD-ECL", _b2431),
}
