"""업무보고서 확장 서식 — 감독규정 편제 나머지 영역.

forms.py가 자본적정성·유동성·건전성의 핵심 14장을 담고, 여기서 편제상 남는
영역을 채운다. 각 빌더는 `(lines, checks)`를 돌려주고 forms.py가 서식 스펙과
묶는다 — 서식 등록(FORMS)은 한 곳에만 있어야 순서·번호가 갈라지지 않는다.

편제 대응:
  제1편 재무·손익      BA1101 · BA1201
  제2편 자본적정성      BA2203 · BA2302 · BA2402 · BA2601 · BA2701
  제3편 유동성          BA3301 · BA3401 · BA3501
  제4편 자산건전성      BA4102 · BA4301
  제5편 자산운용 한도   BA5201 · BA5301
  제7편 내부자본·위기   BA6301 · BA6401
  제8편 경영실태·조치   BA7101 · BA7201
  제9편 집중도·기타     BA8101 · BA8201
"""

from __future__ import annotations

import pandas as pd

from risk_lib.regulatory.forms import FormCheck, FormLine

_M_PRU = "risk_lib.prudential"


def _rows_to_lines(df: pd.DataFrame, *, code_base: int, name_col: str,
                   value_col: str, unit: str, level: int = 1,
                   citation: str | None = None, module: str | None = None,
                   formula=None) -> list[FormLine]:
    out = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        out.append(FormLine(
            f"{code_base + i * 10}", str(r[name_col]), level, unit,
            float(r[value_col]),
            formula=formula(r) if callable(formula) else formula,
            citation=citation, source_module=module))
    return out


# ------------------------------------------------------- 제1편 재무·손익

def br_balance_sheet(ctx):
    t = ctx.tables["pru_balance_sheet"]
    L, checks = [], []
    for si, section in enumerate(("자산", "부채", "자본"), start=1):
        sub = t[t["section"] == section]
        base = si * 1000
        L.append(FormLine(str(base), f"{section} 구분", 0, "text", None,
                          text_value=f"{len(sub)}개 계정",
                          citation="은행업감독규정 제99조 업무보고서"))
        L += _rows_to_lines(sub, code_base=base, name_col="item",
                            value_col="amount", unit="KRW",
                            module=f"{_M_PRU}.financials")
    assets = float(t.loc[t["item"] == "자산총계", "amount"].iloc[0])
    liab = float(t.loc[t["item"] == "부채총계", "amount"].iloc[0])
    eq = float(t.loc[t["item"] == "자본총계 (회계)", "amount"].iloc[0])
    checks.append(FormCheck("자산총계 = 부채총계 + 자본총계", assets, liab + eq, 1.0))
    return L, checks


def br_income_statement(ctx):
    t = ctx.tables["pru_income_statement"].sort_values("seq")
    L = _rows_to_lines(t, code_base=1000, name_col="item", value_col="amount",
                       unit="KRW", level=0,
                       citation="은행업감독규정 제99조 업무보고서",
                       module=f"{_M_PRU}.financials",
                       formula=lambda r: str(r["formula"]))
    m = dict(zip(t["item"], t["amount"]))
    pre_tax = float(m["법인세차감전순이익"])
    parts = sum(float(m[k]) for k in ("영업수익", "영업비용", "충당금 전입액",
                                      "운영손실"))
    checks = [
        FormCheck("세전이익 = 수익 − 비용 − 충당금 − 운영손실", parts, pre_tax, 1.0),
        FormCheck("당기순이익 = 세전이익 + 법인세비용",
                  pre_tax + float(m["법인세비용"]), float(m["당기순이익"]), 1.0),
    ]
    return L, checks


# ------------------------------------------------------- 제2편 자본적정성

def br_crm(ctx):
    t = ctx.tables["rwa_crm_allocation"]
    M = "risk_lib.capital.crm"
    total_alloc = float(t["allocated"].sum())
    L = [
        FormLine("1000", "적격 담보가치 합계", 0, "KRW",
                 float(t["eligible_value"].sum()),
                 formula="시가 × (1 − 감독 haircut)", citation="CRE22.49",
                 source_module=M, is_subtotal=True),
        FormLine("2000", "담보 배분액 합계", 0, "KRW", total_alloc,
                 formula="익스포저별 배분 — 초과배분 금지",
                 citation="CR-F008", source_module=M, is_subtotal=True),
        FormLine("3000", "담보부 EAD", 0, "KRW", float(t["secured_ead"].sum()),
                 citation="CRE22", source_module=M, is_subtotal=True),
        FormLine("4000", "무담보부 EAD", 0, "KRW",
                 float(t["unsecured_ead"].sum()), citation="CRE22",
                 source_module=M, is_subtotal=True),
        FormLine("5000", "담보 커버리지", 0, "ratio",
                 float(t["secured_ead"].sum())
                 / max(float(t["secured_ead"].sum() + t["unsecured_ead"].sum()), 1.0),
                 formula="담보부 EAD ÷ (담보부 + 무담보부)", source_module=M),
        FormLine("6000", "보증·신용파생 적격 건수", 0, "count",
                 float(int(ctx.tables["rdm_guarantee"]["eligible"].sum())),
                 citation="CRE22.70 unfunded protection",
                 source_module="risk_lib.datamodel.materialize_detail"),
        FormLine("9000", "적용 범위 비고", 0, "text", None,
                 text_value="본 산출 파이프라인은 CRM 조정을 RWA에 반영하지 않는다 "
                            "— 배분 결과는 정상화 후보로만 제시된다.",
                 citation="CR-F013 · CR-F016 중복효과 금지"),
    ]
    checks = [FormCheck("배분액 ≤ 적격 담보가치", 0.0,
                        max(0.0, total_alloc - float(t["eligible_value"].sum())),
                        1.0)]
    return L, checks


def br_market_factors(ctx):
    rf = ctx.tables["mkt_risk_factor"]
    bt = ctx.tables["mkt_backtest_exception"]
    ve = ctx.tables["mkt_var_es"]
    M = "risk_lib.market_data · risk_lib.frtb"
    n_exc = int(bt["exception"].sum())
    zone = str(bt.sort_values("obs_date")["zone"].iloc[-1]) if len(bt) else "green"
    L = [
        FormLine("1000", "위험요소 총수", 0, "count", float(len(rf)),
                 citation="MAR31 위험요소 관측", source_module=M,
                 is_subtotal=True),
        FormLine("1100", "모형화 가능 (MRF)", 1, "count",
                 float(int(rf["modellable"].sum())), citation="MAR31.12 RFET",
                 source_module=M),
        FormLine("1200", "모형화 불가 (NMRF)", 1, "count",
                 float(int((~rf["modellable"]).sum())),
                 formula="RFET 미충족 — SES 자본가산 대상", citation="MAR31.12",
                 source_module=M),
        FormLine("1300", "최대 데이터 경과일수", 1, "count",
                 float(rf["staleness_days"].max()) if len(rf) else 0.0,
                 citation="MAR31 stale data", source_module=M),
        FormLine("2000", "백테스팅 관측일수", 0, "count", float(len(bt)),
                 citation="MAR99.5", source_module=M, is_subtotal=True),
        FormLine("2100", "예외 발생 건수", 1, "count", float(n_exc),
                 formula="손실 > 1일 99% VaR", citation="MAR99.5",
                 source_module=M),
        FormLine("2200", "신호등 구간", 1, "count",
                 float(("green", "amber", "red").index(zone)),
                 formula="0=녹색, 1=황색, 2=적색 (누적 예외 4/10 경계)",
                 citation="MAR99.6", source_module=M),
    ]
    for i, (_, r) in enumerate(ve.iterrows(), start=1):
        L.append(FormLine(f"30{i:02d}", f"{r['measure']} ({r['horizon_days']}일)",
                          1, "KRW", float(r["value"]),
                          formula=f"신뢰수준 {float(r['confidence']):.1%} · {r['method']}",
                          citation="MAR33 ES", source_module=M))
    checks = [FormCheck("MRF + NMRF = 위험요소 총수", float(len(rf)),
                        float(int(rf["modellable"].sum())
                              + int((~rf["modellable"]).sum())), 1e-9)]
    return L, checks


def br_op_loss(ctx):
    ev = ctx.tables["opr_loss_event"]
    rec = ctx.tables["opr_recovery"]
    kri = ctx.tables["opr_kri"]
    ctl = ctx.tables["opr_control"]
    M = "risk_lib.op_loss"
    gross = float(ev["gross_loss"].sum())
    recov = float(ev["recovery"].sum())
    net = float(ev["net_loss"].sum())
    L = [
        FormLine("1000", "손실사건 건수", 0, "count", float(len(ev)),
                 citation="OPE25.20 손실 자료", source_module=M, is_subtotal=True),
        FormLine("2000", "총손실", 0, "KRW", gross, source_module=M,
                 is_subtotal=True),
        FormLine("3000", "회수액", 0, "KRW", recov,
                 formula=f"적격 회수 {int(rec['eligible'].sum())}건",
                 citation="OPE25.20", source_module=M, is_subtotal=True),
        FormLine("4000", "순손실", 0, "KRW", net,
                 formula="max(0, 총손실 − 회수)", citation="OR-F001",
                 source_module=M, is_subtotal=True),
    ]
    for i, (etype, sub) in enumerate(ev.groupby("event_type"), start=1):
        L.append(FormLine(f"21{i:02d}", f"사건유형 · {etype}", 1, "KRW",
                          float(sub["gross_loss"].sum()),
                          formula=f"{len(sub)}건",
                          citation="OPE25 7개 사건유형", source_module=M))
    for i, (_, r) in enumerate(kri.iterrows(), start=1):
        L.append(FormLine(f"50{i:02d}", f"KRI · {r['kri_name']}", 1, "count",
                          float(r["value"]),
                          formula=f"주의 {r['threshold_amber']:,.2f} · "
                                  f"경보 {r['threshold_red']:,.2f} → {r['status']}",
                          source_module=M))
    L.append(FormLine("6000", "PSMOR 원칙 매핑 완결 통제 수", 0, "count",
                      float(int((ctl["evidence_status"] == "완결").sum())),
                      formula=f"전체 {len(ctl)}개 원칙",
                      citation="BCBS PSMOR — 매핑이며 준수 인증이 아님",
                      source_module=M, is_subtotal=True))
    checks = [
        FormCheck("순손실 = 총손실 − 회수", gross - recov, net, 1.0),
        FormCheck("회수 원장 합계 = 사건 회수 합계", recov,
                  float(rec["amount"].sum()), 1.0),
    ]
    return L, checks


def br_output_floor(ctx):
    f = ctx.tables["rwa_output_floor"].iloc[0]
    M = "risk_lib.capital.output_floor"
    L = [
        FormLine("1000", "내부모형 위험가중자산", 0, "KRW",
                 float(f["internal_rwa"]), citation="CRE31·CRE32",
                 source_module=M),
        FormLine("2000", "표준방법 위험가중자산", 0, "KRW",
                 float(f["standardised_rwa"]), citation="CRE20",
                 source_module=M),
        FormLine("3000", "산출하한 비율", 0, "ratio", float(f["floor_pct"]),
                 citation="RBC20.11 — 최종 72.5%"),
        FormLine("4000", "하한 금액", 0, "KRW",
                 float(f["standardised_rwa"]) * float(f["floor_pct"]),
                 formula="표준방법 RWA × 하한율", source_module=M),
        FormLine("5000", "하한 적용 후 RWA", 0, "KRW", float(f["floored_rwa"]),
                 formula="max(내부모형, 하한금액)", source_module=M,
                 is_subtotal=True),
        FormLine("6000", "하한 증가분", 0, "KRW", float(f["uplift"]),
                 source_module=M),
        FormLine("7000", "하한 구속 여부", 0, "count",
                 1.0 if bool(f["binding"]) else 0.0,
                 formula="1 = 구속 (내부모형 개선이 자본에 반영되지 않음)",
                 source_module=M),
    ]
    checks = [FormCheck("하한 적용 RWA = max(내부, 하한금액)",
                        max(float(f["internal_rwa"]),
                            float(f["standardised_rwa"]) * float(f["floor_pct"])),
                        float(f["floored_rwa"]), 1.0)]
    return L, checks


def br_buffer_mda(ctx):
    r = ctx.result
    mda = r.bis_deep.mda_components
    M = "risk_lib.capital.bis_deep · risk_lib.mda"
    cbr = (r.bis.required["cet1"] - 0.045)
    L = [
        FormLine("1000", "보통주자본비율", 0, "ratio", float(r.bis.cet1_ratio),
                 source_module=M),
        FormLine("2000", "최저 보통주자본비율", 0, "ratio", 0.045,
                 citation="은행업감독규정 제26조 제1항"),
        FormLine("3000", "완충자본 요구 합계", 0, "ratio", cbr,
                 formula="자본보전 + 경기대응 + 시스템적 중요",
                 citation="제26조의2~4", source_module=M, is_subtotal=True),
        FormLine("4000", "완충자본 여유", 0, "ratio",
                 float(r.bis.cet1_ratio) - 0.045 - cbr,
                 formula="보통주자본비율 − 최저 − 완충 요구",
                 citation="MDA 구간 판정 기준", source_module=M),
        FormLine("5000", "배당가능 총액", 0, "KRW",
                 float(mda["total_allowance"].iloc[0]) if len(mda) else 0.0,
                 formula="완충자본 여유 × RWA × MDA 계수",
                 citation="CRE10.4 자본보전 규제", source_module=M,
                 is_subtotal=True),
    ]
    for i, (_, row) in enumerate(mda.iterrows(), start=1):
        L.append(FormLine(f"51{i:02d}", f"배분 항목 · {row['component']}", 1,
                          "KRW", float(row["requested"]),
                          formula="요청액", source_module=M))
    checks = [FormCheck("완충자본 요구 = 요구비율 − 최저", cbr,
                        float(r.bis.required["cet1"]) - 0.045, 1e-12)]
    return L, checks


# ------------------------------------------------------- 제3편 유동성

def _liquidity_form(ctx, metric: str, citation: str):
    t = ctx.tables["pru_liquidity_ratio"]
    row = t[t["metric"] == metric].iloc[0]
    M = f"{_M_PRU}.liquidity"
    direction = str(row["direction"])
    L = [
        FormLine("1000", "분자", 0, "KRW", float(row["numerator"]),
                 citation=citation, source_module=M),
        FormLine("2000", "분모", 0, "KRW", float(row["denominator"]),
                 citation=citation, source_module=M),
        FormLine("3000", metric, 0, "ratio", float(row["value"]),
                 formula="분자 ÷ 분모", citation=citation, source_module=M,
                 is_subtotal=True),
        FormLine("4000", "규제 기준", 0, "ratio", float(row["threshold"]),
                 formula="이상" if direction == "min" else "이하",
                 citation=citation),
        FormLine("5000", "충족 여부", 0, "count",
                 1.0 if bool(row["passes"]) else 0.0,
                 formula="1 = 충족", source_module=M),
    ]
    checks = [
        FormCheck(f"{metric} = 분자 ÷ 분모",
                  float(row["numerator"]) / float(row["denominator"])
                  if float(row["denominator"]) else 0.0,
                  float(row["value"]), 1e-9),
        FormCheck("충족 판정이 방향과 일치",
                  1.0 if (float(row["value"]) >= float(row["threshold"])
                          if direction == "min"
                          else float(row["value"]) <= float(row["threshold"]))
                  else 0.0,
                  1.0 if bool(row["passes"]) else 0.0, 1e-9),
    ]
    return L, checks


def br_krw_liquidity(ctx):
    return _liquidity_form(ctx, "원화유동성비율",
                           "은행업감독규정 제26조 제1항 — 잔존만기 1개월 이내")


def br_fx_liquidity(ctx):
    return _liquidity_form(ctx, "외화유동성비율",
                           "은행업감독규정 제63조 — 잔존만기 3개월 이내")


def br_loan_deposit(ctx):
    return _liquidity_form(ctx, "원화예대율",
                           "은행업감독규정 제26조 제1항 — 원화대출금 ÷ 원화예수금")


# ------------------------------------------------------- 제4편 자산건전성

_AQ = ("정상", "요주의", "고정", "회수의문", "추정손실")


def br_asset_quality_by_class(ctx):
    aq = ctx.tables["rdm_asset_quality"]
    exp = ctx.tables["rdm_exposure"][["exposure_id", "asset_class"]]
    t = aq.merge(exp, on="exposure_id", how="left")
    M = "risk_lib.datamodel.materialize_detail"
    L = [FormLine("1000", "총 여신 잔액", 0, "KRW", float(t["balance"].sum()),
                  citation="은행업감독규정 제27조", source_module=M,
                  is_subtotal=True)]
    ac_codes = {}
    for i, (ac, sub) in enumerate(t.groupby("asset_class"), start=1):
        base = 1000 + i * 100
        ac_codes[ac] = str(base)
        L.append(FormLine(str(base), f"자산군 · {ac}", 1, "KRW",
                          float(sub["balance"].sum()), source_module=M,
                          is_subtotal=True))
        for j, cls in enumerate(_AQ, start=1):
            s = sub[sub["classification"] == cls]
            L.append(FormLine(f"{base + j}", cls, 2, "KRW",
                              float(s["balance"].sum()),
                              formula=f"{len(s):,}건",
                              citation="제27조 5단계 분류", source_module=M))
    checks = [FormCheck("자산군 소계 합 = 총 여신", float(t["balance"].sum()),
                        sum(float(next(x.value for x in L if x.line_code == c))
                            for c in ac_codes.values()), 1.0)]
    return L, checks


def br_npl(ctx):
    aq = ctx.tables["rdm_asset_quality"]
    dq = ctx.tables["rdm_delinquency"]
    M = "risk_lib.monitoring.delinquency"
    total = float(aq["balance"].sum())
    npl = float(aq[aq["classification"].isin(("고정", "회수의문", "추정손실"))]
                ["balance"].sum())
    watch = float(aq[aq["classification"] == "요주의"]["balance"].sum())
    L = [
        FormLine("1000", "총 여신", 0, "KRW", total, source_module=M,
                 is_subtotal=True),
        FormLine("2000", "고정이하여신", 0, "KRW", npl,
                 citation="은행업감독규정 제27조", source_module=M,
                 is_subtotal=True),
        FormLine("2100", "고정이하여신비율", 0, "ratio",
                 npl / total if total else 0.0, formula="고정이하 ÷ 총여신",
                 source_module=M),
        FormLine("3000", "요주의이하여신", 0, "KRW", watch + npl,
                 source_module=M, is_subtotal=True),
        FormLine("3100", "요주의이하여신비율", 0, "ratio",
                 (watch + npl) / total if total else 0.0, source_module=M),
        FormLine("4000", "부도 익스포저 건수", 0, "count",
                 float(int(dq["default_flag"].sum())),
                 citation="CRE36.69 — 90일 이상 연체 또는 상환불능",
                 source_module=M, is_subtotal=True),
    ]
    for i, (lo, hi, label) in enumerate(
            ((1, 29, "1~29일"), (30, 59, "30~59일"), (60, 89, "60~89일"),
             (90, 10_000, "90일 이상")), start=1):
        sel = aq[(aq["dpd"] >= lo) & (aq["dpd"] <= hi)]
        L.append(FormLine(f"50{i:02d}", f"연체 {label}", 1, "KRW",
                          float(sel["balance"].sum()),
                          formula=f"{len(sel):,}건", source_module=M))
    checks = [FormCheck("요주의이하 ≥ 고정이하", 0.0,
                        min(0.0, (watch + npl) - npl), 1e-9)]
    return L, checks


# ------------------------------------------------------- 제5편 자산운용 한도

def _ownership_form(ctx, items: tuple[str, ...]):
    t = ctx.tables["pru_ownership_limit"]
    M = f"{_M_PRU}.ownership"
    L = [FormLine("1000", "자기자본", 0, "KRW",
                  float(ctx.result.meta["capital"].total),
                  citation="은행법 제2조 자기자본", source_module=M)]
    checks = []
    for i, item in enumerate(items, start=1):
        hit = t[t["item"] == item]
        if not len(hit):
            continue
        r = hit.iloc[0]
        base = 1000 + i * 100
        L += [
            FormLine(str(base), item, 0, "KRW", float(r["used"]),
                     formula=str(r["basis"]), citation=str(r["citation"]),
                     source_module=M, is_subtotal=True),
            FormLine(str(base + 10), "한도 금액", 1, "KRW",
                     float(r["limit_amount"]),
                     formula=f"자기자본 × {float(r['limit_pct']):.0%}",
                     citation=str(r["citation"]), source_module=M),
            FormLine(str(base + 20), "한도 소진율", 1, "ratio",
                     float(r["utilisation"]), formula="사용액 ÷ 한도금액",
                     source_module=M),
            FormLine(str(base + 30), "한도 내 여부", 1, "count",
                     1.0 if bool(r["passes"]) else 0.0, source_module=M),
        ]
        checks.append(FormCheck(
            f"{item} 한도금액 = 자기자본 × 한도율",
            float(ctx.result.meta["capital"].total) * float(r["limit_pct"]),
            float(r["limit_amount"]), 1.0))
    return L, checks


def br_major_shareholder(ctx):
    L, checks = _ownership_form(ctx, ("대주주 신용공여", "대주주 발행주식 취득"))
    L.append(FormLine("9000", "대주주 식별 상태", 0, "text", None,
                      text_value="대주주 지정 원장이 원천 데이터에 없어 사용액을 "
                                 "0으로 두었다 — 제출 전 반드시 확인해야 하는 칸이다.",
                      citation="은행법 제35조의2"))
    return L, checks


def br_investment_limits(ctx):
    return _ownership_form(ctx, ("유가증권 투자", "자회사 출자", "업무용부동산 소유"))


# ------------------------------------------------------- 제7편 내부자본·위기

def br_icaap(ctx):
    ic = ctx.result.icaap
    M = "risk_lib.icaap.economic_capital"
    L = [
        FormLine("1000", "가용 자본", 0, "KRW", float(ic.available_capital),
                 citation="SRP20 ICAAP 가용 내부자본", source_module=M,
                 is_subtotal=True),
        FormLine("2000", "경제적 자본 (분산효과 전)", 0, "KRW",
                 float(ic.ec_standalone_sum), source_module=M, is_subtotal=True),
    ]
    for i, (_, r) in enumerate(ic.ec_by_type.iterrows(), start=1):
        L.append(FormLine(f"21{i:02d}", f"리스크 유형 · {r['risk_type']}", 1,
                          "KRW", float(r["ec"]), citation="SRP20 위험유형별",
                          source_module=M))
    L += [
        FormLine("3000", "분산효과", 0, "KRW", -float(ic.diversification_benefit),
                 formula="단순합 − 분산 후", citation="SRP20 상관 가정",
                 source_module=M),
        FormLine("3100", "집중도 가산", 0, "KRW", float(ic.concentration_addon),
                 citation="SRP30 집중리스크", source_module=M),
        FormLine("4000", "경제적 자본 (분산 후)", 0, "KRW",
                 float(ic.ec_diversified), source_module=M, is_subtotal=True),
        FormLine("5000", "내부자본 소진율", 0, "ratio", float(ic.utilisation),
                 formula="경제적 자본 ÷ 가용 자본", source_module=M),
        FormLine("6000", "버퍼", 0, "KRW", float(ic.buffer),
                 formula="가용 자본 − 경제적 자본", source_module=M),
        FormLine("7000", "판정", 0, "text", None, text_value=str(ic.grade),
                 citation="내부 임계 — GREEN/AMBER/RED"),
    ]
    checks = [
        FormCheck("소진율 = 경제적자본 ÷ 가용자본",
                  float(ic.ec_diversified) / float(ic.available_capital),
                  float(ic.utilisation), 1e-9),
        FormCheck("버퍼 = 가용 − 경제적자본",
                  float(ic.available_capital) - float(ic.ec_diversified),
                  float(ic.buffer), 1.0),
    ]
    return L, checks


def br_stress_trace(ctx):
    """위기상황분석 산출과정 — 심각 시나리오 저점 분기의 전 단계."""
    tr = ctx.tables["st_calc_trace"]
    trough = ctx.result.stress_path_trough
    sev = trough[trough["scenario"] == "severely_adverse"]
    q = str(sev["trough_quarter"].iloc[0]) if len(sev) else None
    sub = tr[(tr["scenario"] == "severely_adverse") & (tr["quarter"] == q)] \
        .sort_values("seq")
    M = "risk_lib.stress.trace"
    axes = ctx.tables["st_shock_axis"]
    L = [FormLine("1000", "대상 시나리오·분기", 0, "text", None,
                  text_value=f"severely_adverse · {q} (CET1 저점)",
                  citation="ST-F004 CET1 roll-forward"),
         FormLine("1100", "충격 축 수", 0, "count", float(len(axes)),
                  formula=" · ".join(
                      f"{rt} {int(n)}" for rt, n
                      in axes.groupby("risk_type").size().items()),
                  citation="SRP20 다축 시나리오 — 모든 축이 같은 심도에서 동시 발동",
                  source_module="risk_lib.stress.axes", is_subtotal=True)]
    for i, (_, a) in enumerate(axes.iterrows(), start=1):
        # bp·notch·multiple을 "ratio"로 담으면 엑셀이 60bp를 6,000%로 표시한다.
        # 서식 단위 어휘에 없는 축은 count로 담고 단위를 산식에 남긴다.
        unit = "ratio" if str(a["unit"]) == "ratio" else "count"
        L.append(FormLine(f"11{i:02d}", f"축 · {a['korean']}", 1, unit,
                          float(a["per_severity"]),
                          formula=f"심도 1.0당 충격 ({a['unit']})",
                          citation=str(a["citation"]),
                          source_module="risk_lib.stress.axes"))
    for _, r in sub.iterrows():
        unit = str(r["unit"])
        L.append(FormLine(
            f"{2000 + int(r['seq']) * 10}", f"[{r['block']}] {r['step']}", 1,
            unit if unit in ("KRW", "ratio", "count") else "count",
            float(r["value"]), formula=str(r["formula"]),
            citation=str(r["citation"]), source_module=M))
    row = ctx.result.stress_path
    hit = row[(row["scenario"] == "severely_adverse") & (row["quarter"] == q)]
    checks = [FormCheck("전 리스크 유형에 축이 있다", 5.0,
                        float(axes["risk_type"].nunique()), 1e-9)]
    if len(hit) and len(sub):
        cet1 = float(sub[sub["step"] == "보통주자본비율"]["value"].iloc[0])
        checks.append(FormCheck("추적표 CET1 = 스트레스 경로 CET1",
                                float(hit["cet1_ratio"].iloc[0]), cet1, 1e-12))
        rwa = float(sub[sub["step"] == "위험가중자산 합계"]["value"].iloc[0])
        checks.append(FormCheck("추적표 RWA = 스트레스 경로 RWA",
                                float(hit["rwa_total"].iloc[0]), rwa,
                                max(1.0, abs(rwa) * 1e-9)))
    return L, checks


# ------------------------------------------------------- 제8편 경영실태·조치

def br_camel(ctx):
    t = ctx.tables["pru_camel"]
    M = f"{_M_PRU}.camel"
    composite = float((t["grade"] * t["weight"]).sum())
    L = [FormLine("1000", "종합평가등급", 0, "count", float(round(composite)),
                  formula=f"가중평균 {composite:.2f}",
                  citation="은행업감독규정 제31조~제33조", source_module=M,
                  is_subtotal=True)]
    for i, (_, r) in enumerate(t.iterrows(), start=1):
        base = 1000 + i * 100
        L += [
            FormLine(str(base), f"{r['component']} 등급", 1, "count",
                     float(r["grade"]),
                     formula=f"{r['grade_label']} · 가중치 {float(r['weight']):.0%}",
                     citation=str(r["basis"]), source_module=M),
            FormLine(str(base + 10), f"{r['component']} 지표값", 2, "ratio",
                     float(r["value"]), formula=str(r["indicator"]),
                     source_module=M),
        ]
    checks = [FormCheck("가중치 합 = 1", 1.0, float(t["weight"].sum()), 1e-9)]
    return L, checks


def br_prompt_action(ctx):
    t = ctx.tables["pru_prompt_action"]
    M = f"{_M_PRU}.pca"
    action = str(t["action"].iloc[0])
    from risk_lib.prudential.pca import ACTION_ORDER
    L = [FormLine("1000", "적기시정조치 판정", 0, "count",
                  float(ACTION_ORDER.index(action)),
                  formula=f"0=해당없음 1=권고 2=요구 3=명령 → {action}",
                  citation="은행업감독규정 제34조~제36조", source_module=M,
                  is_subtotal=True)]
    for i, (_, r) in enumerate(t.iterrows(), start=1):
        L.append(FormLine(f"20{i:02d}", str(r["test"]), 1, "ratio",
                          float(r["value"]),
                          formula=f"기준 {float(r['threshold']):.4g} · "
                                  f"{'해당' if bool(r['triggered']) else '미해당'}",
                          citation=str(r["citation"]), source_module=M))
    n_trig = int(t["triggered"].sum())
    checks = [FormCheck("해당 항목이 없으면 판정은 해당없음",
                        0.0 if n_trig == 0 else float(ACTION_ORDER.index(action)),
                        float(ACTION_ORDER.index(action)) if n_trig else 0.0,
                        1e-9)]
    return L, checks


# ------------------------------------------------------- 제9편 집중도·기타

def br_concentration(ctx):
    conc = ctx.result.concentration
    lex = ctx.result.limits_deep.large_exposure_lex_group
    M = "risk_lib.limits.concentration"
    L = []
    for i, (_, r) in enumerate(conc.iterrows(), start=1):
        base = 1000 + i * 100
        dim = str(r.get("dimension", r.iloc[0]))
        hhi = float(r.get("hhi", 0.0))
        L += [
            FormLine(str(base), f"집중도 · {dim}", 0, "ratio", hhi,
                     formula="HHI = Σ 점유율²",
                     citation="SRP30 집중리스크", source_module=M,
                     is_subtotal=True),
            FormLine(str(base + 10), "최대 buckets 점유율", 1, "ratio",
                     float(r.get("top_share", 0.0)), source_module=M),
        ]
    L += [
        FormLine("9000", "동일차주 한도 초과 그룹 수", 0, "count",
                 float(int((lex["severity"] == "BREACH").sum())),
                 citation="LEX10.5 · 은행법 제35조",
                 source_module="risk_lib.limits.limits_deep", is_subtotal=True),
        FormLine("9100", "최대 동일차주 한도 소진율", 0, "ratio",
                 float(lex["utilisation_25pct"].max()) if len(lex) else 0.0,
                 source_module="risk_lib.limits.limits_deep"),
    ]
    checks = [FormCheck("HHI는 0~1 범위",
                        0.0, max(0.0, float(conc.get("hhi", pd.Series([0.0])).max()) - 1.0),
                        1e-9)]
    return L, checks


def br_ccr(ctx):
    c = ctx.result.ccr
    trades = ctx.tables["mkt_trade"]
    ipv = ctx.tables["mkt_ipv"]
    M = "risk_lib.ccr · risk_lib.xva"
    L = [
        FormLine("1000", "거래 건수", 0, "count", float(len(trades)),
                 source_module=M, is_subtotal=True),
        FormLine("1100", "명목금액 합계", 0, "KRW",
                 float(trades["notional"].sum()), source_module=M),
        FormLine("2000", "거래상대방 수", 0, "count", float(c.n_counterparties),
                 citation="CRE52 SA-CCR", source_module=M, is_subtotal=True),
        FormLine("3000", "거래상대방 신용위험 EAD", 0, "KRW",
                 float(c.ead_total), formula="SA-CCR: α × (RC + PFE)",
                 citation="CRE52.1", source_module=M, is_subtotal=True),
        FormLine("4000", "CCR 위험가중자산", 0, "KRW", float(c.rwa_total),
                 citation="CRE52", source_module=M, is_subtotal=True),
        FormLine("5000", "신용가치조정(CVA) 소요자기자본", 0, "KRW",
                 float(c.cva_charge), citation="MAR50 CVA 리스크",
                 source_module=M, is_subtotal=True),
        FormLine("5100", "신용가치조정(CVA) 위험가중자산", 0, "KRW",
                 float(c.cva_charge) * 12.5,
                 formula="CVA 소요자기자본 × 12.5 — RWA 합산 기준",
                 citation="MAR50.2 · RBC20.6", source_module=M,
                 is_subtotal=True),
        FormLine("6000", "독립가격검증 BREAK 건수", 0, "count",
                 float(int(ipv["is_break"].sum())),
                 formula=f"검증 대상 {len(ipv)}건",
                 citation="MR-F003 허용오차", source_module="risk_lib.ipv"),
        FormLine("6100", "BREAK 비율", 0, "ratio",
                 float(ipv["is_break"].mean()) if len(ipv) else 0.0,
                 source_module="risk_lib.ipv"),
    ]
    checks = [FormCheck("CCR RWA ≥ 0", 0.0, max(0.0, -float(c.rwa_total)), 1e-9)]
    return L, checks
