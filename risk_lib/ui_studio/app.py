"""에이전틱 UI 스튜디오 렌더러 — 자체 완결 단일 HTML.

외부 CDN·폰트·스크립트를 쓰지 않는다(폐쇄망 전제). 데이터는 Studio 스냅샷을
JSON으로 인라인하고, 화면은 그 JSON만 읽는다 — 화면과 원장이 갈라질 여지를
없애기 위해서다. 미리보기 행 수는 상한을 두되 **모집단 건수는 그대로 표시**한다.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

import pandas as pd

from risk_lib.datamodel import catalog as cat
from risk_lib import commercial as _com
from risk_lib.ui_studio.req_trace import build_trace as _req_rows
from risk_lib.ui_studio.req_trace import coverage as _req_coverage
from risk_lib.ui_studio.studio import DEMO_PROMPTS, DEMO_QUERIES, Studio

PREVIEW_ROWS = 12

# 화면 안에서 조회·필터를 실제로 돌리기 위한 행 예산. 시연 대상 테이블은
# 넉넉히, 나머지는 미리보기 수준으로만 싣는다.
INTERACTIVE_ROWS = 200
INTERACTIVE_ROWS_DEMO = 3000
DEMO_TABLES = (
    "rdm_asset_quality", "rdm_exposure", "rdm_exposure_balance",
    "rwa_sa_bucket", "rwa_irb_pool", "ecl_result", "crm_ews_signal",
    "alm_lcr_item", "alm_nsfr_item", "mkt_ipv", "opr_loss_event",
    "reg_form_line", "st_capital_path", "st_calc_trace",
    "pru_balance_sheet", "pru_income_statement", "pru_liquidity_ratio",
    "pru_ownership_limit", "pru_camel", "pru_prompt_action",
    # 백테스트 예외 달력은 250 영업일 전체가 있어야 그림이 된다 — 200행에서
    # 자르면 달력의 마지막 두 달이 비는데, 그 공백은 "예외 없음"으로 읽힌다.
    "mkt_backtest_exception",
    # 코드 마스터는 정렬의 정본이다 — 잘리면 잘린 코드셋만 사다리가 무너져,
    # 어떤 화면은 맞고 어떤 화면은 틀리는 최악의 상태가 된다.
    "rdm_code_master",
)

_ENGINE_JS = (Path(__file__).with_name("engine.js")).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 직렬화

def _cell(v):
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) else v
    if isinstance(v, (int, bool, str)):
        return v
    if v is pd.NA or (hasattr(pd, "isna") and not isinstance(v, (list, tuple))
                      and pd.isna(v)):
        return None
    return str(v)


# 컬럼 표시명은 **카탈로그(ColumnSpec.korean)가 정본**이다. 화면에서 따로
# 지으면 두 벌이 갈라진다. 같은 물리명이 테이블마다 다른 업무 명칭을 갖는
# 컬럼이 50종 있으므로(예: ead → EAD/익스포저, status → 게이트 상태/매핑 상태)
# 전역 사전이 아니라 테이블별로 푼다.
_SPEC_BY_NAME = {sp.name: sp for sp in cat.ALL_TABLES}


def _labels(table: str | None, columns: list[str]) -> list[str | None]:
    sp = _SPEC_BY_NAME.get(table or "")
    m = {c.name: (c.korean or None) for c in sp.columns} if sp else {}
    return [m.get(c) for c in columns]


def _frame(df: pd.DataFrame, limit: int = PREVIEW_ROWS,
           table: str | None = None,
           labels: dict[str, str] | None = None) -> dict:
    head = df.head(limit)
    cols = [str(c) for c in df.columns]
    return {
        "table": table,
        "columns": cols,
        "labels": ([labels.get(c) for c in cols] if labels
                   else _labels(table, cols)),
        "rows": [[_cell(v) for v in row] for row in head.itertuples(index=False)],
        "total": int(len(df)),
        "shown": int(len(head)),
    }


def _adj_frame(s: Studio) -> pd.DataFrame:
    from risk_lib.adjustments import demo_ledger
    led = demo_ledger(s.result, asof=s.asof)
    return pd.DataFrame([{
        "adjustment_id": a.adjustment_id, "figure_id": a.figure_id,
        "label": a.label, "base_value": a.base_value,
        "adjusted_value": a.adjusted_value, "delta": a.delta,
        "reason": a.reason, "evidence_ref": a.evidence_ref,
        "requester": a.requester, "approver": a.approver,
        "expires_on": a.expires_on, "status": a.status,
    } for a in led.adjustments])


def _reverse_dict(s: Studio) -> dict:
    r = s.result.reverse_stress
    return {
        "metric": r.metric, "target_ratio": r.target_ratio,
        "base_ratio": r.base_ratio, "critical_severity": r.critical_severity,
        "resilient": bool(r.resilient), "converged": bool(r.converged),
        "ratio_at_break": r.ratio_at_break,
        "rwa_at_break": r.rwa_total_at_break, "ecl_at_break": r.ecl_at_break,
        "implied_gdp_shock": r.implied_gdp_shock,
        "implied_lgd_addon": r.implied_lgd_addon,
    }


def _kpis(s: Studio) -> list[dict]:
    r = s.result
    t = s.tables
    aq = t["rdm_asset_quality"]
    npl = float(aq[aq["classification"].isin(("고정", "회수의문", "추정손실"))]
                ["balance"].sum())
    bal = float(aq["balance"].sum()) or 1.0
    checks = t["val_check"]
    n_fail = int((checks["status"] == "FAIL").sum())
    n_warn = int((checks["status"] == "WARN").sum())
    reg_checks = t["reg_form_check"]
    trough = r.stress_path_trough
    sev = trough[trough["scenario"] == "severely_adverse"]
    return [
        {"label": "보통주자본비율 (CET1)", "value": f"{r.bis.cet1_ratio:.2%}",
         "sub": f"요구 {r.bis.required['cet1']:.2%} · 여유 "
                f"{r.bis.surplus_shortfall['cet1']*100:+.2f}%p",
         "tone": "good" if r.bis.surplus_shortfall["cet1"] >= 0 else "bad",
         "lineage": "BR-01 / 3100"},
        {"label": "위기상황 CET1 저점",
         "value": f"{float(sev['trough_cet1'].iloc[0]):.2%}" if len(sev) else "—",
         "sub": f"심각 시나리오 · {sev['trough_quarter'].iloc[0]}" if len(sev) else "",
         "tone": "warn" if len(sev) and not bool(sev["passes_all"].iloc[0]) else "good",
         "lineage": "BR-14 / 2300"},
        {"label": "기대신용손실 (ECL)",
         "value": f"{float(r.ecl['total'])/1e8:,.0f}억원",
         "sub": f"고정이하여신비율 {npl/bal:.2%}",
         "tone": "neutral", "lineage": "BR-11 / 2000"},
        {"label": "유동성커버리지비율 (LCR)",
         "value": f"{float(r.alm['lcr'].lcr):.1%}",
         "sub": f"NSFR {float(r.alm['nsfr'].nsfr):.1%} · 최저 100%",
         "tone": "good" if r.alm["lcr"].lcr >= 1.0 else "bad",
         "lineage": "BR-08 / 5000"},
        {"label": "자체검증", "value": f"FAIL {n_fail} · WARN {n_warn}",
         "sub": f"총 {len(checks)}건", "tone": "good" if n_fail == 0 else "bad",
         "lineage": "val_check"},
        {"label": "업무보고서 대사",
         "value": f"{int((reg_checks['status']=='PASS').sum())}/{len(reg_checks)}",
         "sub": f"서식 {len(t['reg_form'])}장 · 라인 {len(t['reg_form_line'])}행",
         "tone": "good" if not int((reg_checks["status"] == "FAIL").sum()) else "bad",
         "lineage": "reg_form_check"},
    ]


def _payload(s: Studio) -> dict:
    t = s.tables
    spec_by_name = {sp.name: sp for sp in cat.ALL_TABLES}

    catalog_rows = []
    for sp in cat.ALL_TABLES:
        df = t.get(sp.name)
        catalog_rows.append({
            "name": sp.name, "korean": sp.korean, "product": sp.product,
            "grain": sp.grain, "columns": len(sp.columns),
            "pk": ", ".join(sp.primary_key) or "—",
            "fk": len(sp.foreign_keys),
            "rows": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
            "materialised": isinstance(df, pd.DataFrame),
        })

    previews = {name: _frame(df, table=name) for name, df in t.items()
                if isinstance(df, pd.DataFrame) and name in spec_by_name}

    # ---- 브라우저에서 실제로 조회·필터가 돌아가려면 데이터가 화면 안에
    # 있어야 한다. 전량을 실으면 파일이 감당이 안 되므로 상한을 두되,
    # **모집단 건수를 함께 남겨** 잘린 사실이 화면에 드러나게 한다.
    views_meta, data = {}, {}
    fp = t["ui_field_policy"]
    policy_by_view: dict[str, list[dict]] = {}
    for _, r in fp.iterrows():
        policy_by_view.setdefault(str(r["view_id"]), []).append({
            "field_name": str(r["field_name"]), "korean": str(r["korean"]),
            "permitted": bool(r["permitted"]), "masking": str(r["masking"]),
            "min_aggregation": int(r["min_aggregation"]),
        })
    for _, v in t["ui_view"].iterrows():
        vid = str(v["view_id"])
        tref = v["table_ref"]
        if not isinstance(tref, str) or tref not in t:
            continue
        df = t[tref]
        budget = (INTERACTIVE_ROWS_DEMO if tref in DEMO_TABLES
                  else INTERACTIVE_ROWS)
        views_meta[vid] = {
            "view_id": vid, "view_name": str(v["view_name"]),
            "domain": str(v["domain"]), "table_ref": tref,
            "row_limit": int(v["row_limit"]),
            "fields": policy_by_view.get(vid, []),
            "total_rows": int(len(df)), "embedded_rows": int(min(len(df), budget)),
        }
        if tref not in data:
            data[tref] = _frame(df, budget, table=tref)

    plans = []
    for p in s.plans:
        res = s.plan_results.get(p.plan_id, pd.DataFrame())
        _vrow = s.view_row(p.view_id)
        _tref = str(_vrow["table_ref"]) if _vrow is not None else None
        plans.append({
            "plan_id": p.plan_id, "view_id": p.view_id, "intent": p.intent,
            "utterance": p.utterance, "population": p.population,
            "ast": p.condition_ast, "policy": p.policy, "hash": p.query_hash,
            "status": p.status, "block_reason": p.block_reason,
            "n_rows": p.n_rows, "result": _frame(res, 8, table=_tref),
            "steps": [
                ("01 의도", p.intent), ("02 기준일", p.asof),
                ("03 모집단", p.population),
                ("04 조건", " ∧ ".join(c.describe() for c in p.conditions) or "—"),
                ("05 정책", p.policy),
            ],
        })

    proposals = []
    for pr in s.proposals:
        # 승인된 제안만 실제 데이터로 미리보기를 만든다 — 거부된 제안이
        # 화면에 그려지면 "거부됐다"는 통제가 무의미해진다.
        preview = {"columns": [], "rows": [], "total": 0, "shown": 0}
        if pr.status == "approved":
            vrow = s.view_row(pr.view_id)
            src = t.get(str(vrow["table_ref"])) if vrow is not None else None
            if isinstance(src, pd.DataFrame) and pr.columns:
                cols = [c for c in pr.columns if c in src.columns]
                sub = src[cols]
                num = next((c for c in cols
                            if pd.api.types.is_numeric_dtype(sub[c])), None)
                if num:
                    sub = sub.sort_values(num, ascending=False)
                preview = _frame(sub, min(pr.row_limit, 10),
                                 table=str(vrow["table_ref"]))
                preview["bar_column"] = num
                # 막대 라벨은 **범주형** 열이어야 한다 — 숫자 열을 라벨로 쓰면
                # 축과 값이 같은 종류가 되어 차트가 읽히지 않는다.
                preview["label_column"] = next(
                    (c for c in cols
                     if not pd.api.types.is_numeric_dtype(sub[c])), None)
        proposals.append({
            "proposal_id": pr.proposal_id, "view_id": pr.view_id,
            "prompt": pr.prompt, "layout": pr.layout_text(),
            "blocks": list(pr.blocks), "columns": list(pr.columns),
            "row_limit": pr.row_limit, "status": pr.status,
            "preview": preview,
            "checks": [
                ("필드 권한", pr.field_policy_pass),
                ("스키마·단위", pr.schema_pass),
                ("집계 최소단위", pr.aggregation_pass),
                ("사람 적용승인", pr.status == "approved"),
            ],
            "rejected": list(pr.rejected_fields),
        })

    forms = [{
        "form_id": b.spec.form_id, "form_no": b.spec.form_no_display,
        "official": b.spec.form_no.is_official,
        "form_name": b.spec.form_name,
        "frequency": b.spec.frequency, "citation": b.spec.citation,
        "section": b.spec.section,
        "n_lines": len(b.lines), "n_checks": len(b.checks),
        "n_failed": b.n_failed,
        "lines": [{
            "code": ln.line_code, "name": ln.line_name, "level": ln.level,
            "unit": ln.unit,
            "value": _cell(ln.value) if ln.unit != "text" else ln.text_value,
            "formula": ln.formula or "", "citation": ln.citation or "",
            "module": ln.source_module or "", "subtotal": ln.is_subtotal,
        } for ln in b.lines],
    } for b in s.built_forms]

    return {
        "meta": {
            "asof": s.asof, "run_id": s.run_id, "digest": s.digest,
            "seed": s.result.meta.get("seed", 42),
            "n_tables": len(cat.ALL_TABLES),
            "n_columns": sum(len(sp.columns) for sp in cat.ALL_TABLES),
            "n_rows": int(sum(len(df) for df in t.values()
                              if isinstance(df, pd.DataFrame))),
        },
        "kpis": _kpis(s),
        "catalog": catalog_rows,
        "previews": previews,
        "views": _frame(t["ui_view"], 10_000, table="ui_view"),
        "field_policy": _frame(t["ui_field_policy"], 10_000, table="ui_field_policy"),
        "view_meta": views_meta,
        "data": data,
        "demo_queries": [
            {"view_id": v, "utterance": u, "intent": i}
            for v, u, i in DEMO_QUERIES if v in views_meta
        ],
        "demo_prompts": [
            {"view_id": v, "prompt": q}
            for v, q in DEMO_PROMPTS if v in views_meta
        ],
        "plans": plans,
        "proposals": proposals,
        "forms": forms,
        "form_checks": _frame(t["reg_form_check"], 200, table="reg_form_check"),
        "agents": _frame(t["agent_registry"], 100, table="agent_registry"),
        "activity": _frame(t["agent_activity"], 100, table="agent_activity"),
        "killswitch": _frame(t["agent_killswitch"], 50, table="agent_killswitch"),
        "evidence_nodes": _frame(t["gov_evidence_node"], 50, table="gov_evidence_node"),
        "evidence_edges": _frame(t["gov_evidence_edge"], 50, table="gov_evidence_edge"),
        "approvals": _frame(t["gov_approval"], 100, table="gov_approval"),
        "changes": _frame(t["chg_change_request"], 50, table="chg_change_request"),
        "change_impacts": _frame(t["chg_impact_map"], 200, table="chg_impact_map"),
        "change_tests": _frame(t["chg_regression_test"], 100, table="chg_regression_test"),
        "reconciliation": _frame(t["rdm_reconciliation"], 50, table="rdm_reconciliation"),
        "contracts": _frame(t["rdm_source_contract"], 50, table="rdm_source_contract"),
        "canonical_map": _frame(t["rdm_canonical_map"], 200, table="rdm_canonical_map"),
        "validation": _frame(t["val_check"], 400, table="val_check"),
        "independent": {
            "status": str(t["val_independent_request"]["status"].iloc[0]),
            "reason": str(t["val_independent_request"]["reason"].iloc[0]),
            "request_id": str(t["val_independent_request"]["request_id"].iloc[0]),
            "requested_to": str(t["val_independent_request"]["requested_to"].iloc[0]),
            "branch": str(t["val_independent_request"]["branch"].iloc[0]),
            "n_targets": int(t["val_independent_request"]["n_recalc_targets"].iloc[0]),
            "self_validation": " · ".join(
                f"{k} {v}" for k, v in sorted(
                    (s.iv_request.self_validation if s.iv_request else {}).items())),
            "assumptions": list(s.iv_request.known_assumptions) if s.iv_request else [],
        },
        "independent_targets": _frame(t["val_independent_target"], 50, table="val_independent_target"),
        # v9.6.0 업무요건 추적 — 증빙 참조는 tests/test_req_trace.py 가 실재를
        # 검증한다. 여기 실리는 것은 주장 목록이 아니라 검사를 통과한 목록이다.
        "req_trace": {"coverage": _req_coverage(), "rows": _req_rows()},
        # 오버레이(수동조정) 원장 — DAT-006. 엔진 산출값을 사람이 덮어쓴
        # 기록이다. 기록 없는 조정은 재현 불가의 시작이므로 전 건이 사유·증빙·
        # 승인·만료를 갖는다.
        "adjustments": _frame(_adj_frame(s), 100, labels={
            "adjustment_id": "조정 식별자", "figure_id": "대상 수치",
            "label": "항목", "base_value": "엔진 산출값",
            "adjusted_value": "조정 후 값", "delta": "조정폭",
            "reason": "사유", "evidence_ref": "증빙 참조",
            "requester": "요청자", "approver": "승인자",
            "expires_on": "만료일", "status": "상태"}),
        # 한도·소진 — 다차원 한도 엔진 산출.
        "limits": _frame(s.result.limits, 200, labels={
            "limit": "한도명", "dimension": "차원", "bucket": "구간",
            "exposure": "익스포저", "threshold": "한도액",
            "utilisation": "소진율", "severity": "심각도"}),
        # 역스트레스 — 자본 임계를 뚫는 심도를 푼다 (BNK-ST-006).
        "reverse_stress": _reverse_dict(s),
        # 사업성(COM) — 규제 산출물이 아니다. 제출 지문·독립검증 대상에 넣지
        # 않으며, 전 수치가 가정 원장에서 계산으로만 나온다.
        "commercial": {
            "assumptions": _frame(_com.assumption_frame(), 50, labels={
                "assumption_id": "가정 ID", "description": "설명",
                "value": "값", "unit": "단위"}),
            "quotes": _frame(_com.quote_frame(), 10, labels={
                "package": "패키지", "name": "이름", "scope": "포함 범위",
                "build_cost": "순구축대가", "lifecycle_annual": "Lifecycle(연)",
                "arr": "ARR", "year1_total": "1년차 합계", "tco_3y": "3년 TCO",
                "payback_years": "회수기간(년)"}),
            "roi": _frame(_com.roi_frame(), 10, labels={
                "benefit_id": "편익 ID", "description": "설명",
                "assumption_ref": "출처 가정", "annual_value": "연 편익"}),
            "funnel": _frame(_com.funnel_frame(), 10, labels={
                "stage_id": "단계 ID", "stage": "단계", "exit_criteria": "전환 기준"}),
            "double_counting": _com.check_no_double_counting(),
        },
        "domains": sorted({r["product"] for r in catalog_rows}),
    }


# ---------------------------------------------------------------- HTML

# 팔레트는 두 벌뿐이고, 세 자리(기본·OS 선호·명시 토글)에 같은 값을 쓴다.
# 손으로 세 번 적으면 한 자리만 고치는 날이 온다 — 값은 여기 한 번만 둔다.
#
# 색 체계는 RYNTA 브로셔 UI(v9.5.0)의 것을 그대로 쓴다 — 딥네이비 바탕에
# **역할 기반** 색: 엔진(결정론적 산출)=파랑, 에이전트(제안)=보라,
# 사람(승인)=앰버, 증빙(계보)=틸. 상태색(ok/watch/danger)과 역할색을
# 분리해 두는 것이 이 체계의 핵심이다 — 경보색을 장식에 쓰면 경보가 죽는다.
_DARK = {
    "--bg": "#06111d", "--panel": "#0a1928", "--panel2": "#0d2134",
    "--panel3": "#102941", "--line": "rgba(146,188,220,.17)",
    "--text": "#eef7ff", "--muted": "#8ea4b8",
    "--accent": "#42a9ff",            # 엔진 — 결정론적 산출
    "--agent": "#a78bfa",             # 에이전트 — 제안 전용
    "--human": "#f6bb56",             # 사람 — 승인 권한
    "--lineage": "#2dd4bf",           # 증빙 — 계보·검증
    "--good": "#44d19d", "--warn": "#f6bb56", "--bad": "#fb6472",
    "--chip": "rgba(255,255,255,.045)",
    "--on-accent": "#04111b",         # 파랑 위 잉크 — 어두운 판은 검정이 선다
    "--card-grad": "linear-gradient(150deg,#0d2134,rgba(7,20,33,.95))",
    "--shadow": "0 10px 34px rgba(0,0,0,.12)",
}
# 밝은 판은 같은 역할 체계를 종이 위로 옮긴 것이다 — 의미색은 채도를 내려야
# 흰 바탕에서 읽히고, 파랑 위 잉크는 흰색이어야 선다.
_LIGHT = {
    **_DARK,
    "--bg": "#f3f7fb", "--panel": "#fff", "--panel2": "#ecf2f8",
    "--panel3": "#e1eaf3", "--line": "#d3dee8",
    "--text": "#14212e", "--muted": "#5c6f81",
    "--accent": "#1264c4", "--agent": "#6d4fd0", "--human": "#8a5a00",
    "--lineage": "#0d7d70",
    "--good": "#177a52", "--warn": "#935f00", "--bad": "#cc2f45",
    "--chip": "#ecf2f8", "--on-accent": "#fff",
    "--card-grad": "linear-gradient(150deg,#fff,#f7fafd)",
    "--shadow": "0 10px 30px rgba(20,45,70,.08)",
}


def _tokens(d: dict[str, str]) -> str:
    return "".join(f"{k}:{v};" for k, v in d.items())


# 뷰어가 테마를 직접 고르는 환경(아티팩트 등)에서는 루트에 data-theme이 찍히고,
# 그 지정이 OS 선호보다 뒤에 와야 두 방향 모두 이긴다.
_PALETTE = f"""
:root{{{_tokens(_DARK)}}}
@media (prefers-color-scheme:light){{:root{{{_tokens(_LIGHT)}}}}}
:root[data-theme="light"]{{{_tokens(_LIGHT)}}}
:root[data-theme="dark"]{{{_tokens(_DARK)}}}
"""

_CSS = _PALETTE + """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:13px/1.5 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",
"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif}
a{color:var(--accent)}
.topbar{position:sticky;top:0;z-index:20}
header{background:var(--panel);
border-bottom:1px solid var(--line);padding:11px 20px;min-height:50px;
display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.brand{font-weight:800;font-size:15px;letter-spacing:-.01em}
.brand span{color:var(--accent)}
.hchip{background:var(--chip);border:1px solid var(--line);border-radius:8px;
padding:4px 9px;font-size:10.5px;font-weight:650;letter-spacing:.03em;
color:var(--muted)}
label.hchip{display:inline-flex;align-items:center;gap:5px}
.asofsel{padding:1px 5px;font-size:11px;border-radius:5px}
.kill{margin-left:auto;background:transparent;border:1px solid var(--bad);
color:var(--bad);border-radius:8px;padding:5px 13px;font-size:11px;
font-weight:750;letter-spacing:.03em;cursor:pointer}
.kill.on{background:var(--bad);color:#fff}
.killbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
padding:10px 20px;background:var(--panel);border-bottom:1px solid var(--bad);
box-shadow:inset 3px 0 0 var(--bad);font-size:11px}
.killbar[hidden]{display:none}
.killbar label{color:var(--bad);font-weight:750}
.killbar input{flex:1 1 320px;min-width:0;background:var(--bg);
color:var(--text);border:1px solid var(--line);border-radius:8px;
padding:6px 10px;font:inherit}
.killbar button{border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer;
border:1px solid var(--line);background:var(--chip);color:var(--text)}
.killbar .killgo{border-color:var(--bad);background:var(--bad);color:#fff}
.killnote{color:var(--muted);flex:1 1 100%}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.layout{display:grid;grid-template-columns:224px minmax(0,1fr);
align-items:start}
nav{position:sticky;top:96px;max-height:calc(100vh - 96px);overflow-y:auto;
display:flex;flex-direction:column;gap:1px;padding:12px 10px 24px;
background:var(--bg);border-right:1px solid var(--line)}
.navgroup{color:var(--text);font-size:10.5px;font-weight:800;
letter-spacing:.08em;padding:7px 8px;margin-top:10px;cursor:pointer;
user-select:none;background:var(--panel2);border:1px solid var(--line);
border-radius:8px}
.navgroup:first-child{margin-top:0}
.navgroup::before{content:'▾ ';color:var(--accent)}
.navgroup.closed::before{content:'▸ ';color:var(--muted)}
nav button{background:transparent;border:none;color:var(--muted);
margin-left:9px;padding:6px 10px 6px 13px;cursor:pointer;font-size:12px;
text-align:left;font-weight:650;font-family:inherit;
border-left:2px solid var(--line);border-radius:0 8px 8px 0}
nav button:hover{color:var(--text);background:var(--chip);
border-left-color:var(--muted)}
nav button.on{background:var(--accent);color:var(--on-accent);
border-left-color:var(--accent);font-weight:750}
nav button[hidden]{display:none}
.navgroup.sub{margin-left:11px;margin-top:4px;font-size:10px;
background:transparent;border:none;border-left:2px solid var(--line);
border-radius:0;color:var(--muted);padding:5px 8px}
nav button.lvl2{margin-left:22px}
nav button.lvl3{margin-left:34px}
main{padding:20px;min-width:0}
@media(max-width:900px){
  .layout{grid-template-columns:1fr}
  nav{position:static;max-height:none;flex-direction:row;flex-wrap:wrap;
  border-right:none;border-bottom:1px solid var(--line)}
  .navgroup{flex:1 1 100%}
}
section{display:none}section.on{display:block}
h2{font-size:24px;line-height:1.15;letter-spacing:-.03em;margin:2px 0 6px}
.lead{color:var(--muted);font-size:12px;margin:0 0 16px;max-width:96ch}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.card{background:var(--card-grad);border:1px solid var(--line);
border-radius:16px;padding:15px;min-width:0;box-shadow:var(--shadow);
margin:10px 0}
.card .card{box-shadow:none;margin:0}
.card h3{margin:0 0 9px;font-size:13px;font-weight:800;letter-spacing:-.01em}
.kpi .lab{font-size:10.5px;font-weight:700;letter-spacing:.05em;
color:var(--muted)}
.kpi .val{font-size:25px;font-weight:800;letter-spacing:-.02em;margin:6px 0 3px;
font-variant-numeric:tabular-nums}
.kpi .sub{font-size:11px;color:var(--muted)}
.kpi .ln{font-size:10px;color:var(--lineage);font-weight:650;margin-top:7px}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.tw{overflow:auto;border:1px solid var(--line);border-radius:11px;margin:10px 0;
max-height:912px}   /* ≈ 30행 + 머리글 — 넘치면 그리드 안에서 스크롤 */
table{border-collapse:collapse;width:100%;font-size:11.5px;min-width:520px}
th{background:var(--panel2);color:var(--muted);text-align:left;padding:7px 9px;
font-weight:750;letter-spacing:.02em;border-bottom:1px solid var(--line);
white-space:nowrap;position:sticky;top:0}
td{padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(66,169,255,.06)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.sub td{background:var(--panel2);font-weight:650}
.pill{display:inline-block;padding:2px 9px;border-radius:7px;font-size:10px;
font-weight:750;letter-spacing:.04em;border:1px solid var(--line);
background:var(--chip)}
.pill.good{border-color:var(--good);color:var(--good)}
.pill.warn{border-color:var(--warn);color:var(--warn)}
.pill.bad{border-color:var(--bad);color:var(--bad)}
.meta{font-size:11px;color:var(--muted);margin:6px 0}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.step{background:var(--chip);border:1px solid var(--line);border-radius:10px;
padding:8px 11px;min-width:130px}
.step b{display:block;font-size:9.5px;color:var(--muted);font-weight:750;
letter-spacing:.06em}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
font-size:11px}
.bar{height:9px;background:var(--chip);border-radius:5px;overflow:hidden}
.bar i{display:block;height:100%;
background:linear-gradient(90deg,var(--accent),var(--lineage))}
.sel{background:var(--panel2);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:6px 9px;font-family:inherit;font-size:12px}
.split{display:grid;gap:12px;grid-template-columns:minmax(260px,1fr) 2.2fr}
@media(max-width:900px){.split{grid-template-columns:1fr}}
.list{max-height:520px;overflow:auto;border:1px solid var(--line);
border-radius:11px}
.list button{display:block;width:100%;text-align:left;background:transparent;
border:none;border-bottom:1px solid var(--line);color:var(--text);
padding:8px 11px;cursor:pointer;font-family:inherit;font-size:12px}
.list button:hover{background:var(--chip)}
.list button.on{background:var(--accent);color:var(--on-accent)}
.list button small{display:block;color:var(--muted);font-size:10px}
.list button.on small{color:var(--on-accent);opacity:.75}
.listsec{background:var(--panel2);border-bottom:1px solid var(--line);
padding:6px 11px;font-size:10.5px;font-weight:750;letter-spacing:.05em;
color:var(--muted)}
.flow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:10px 0}
.node{background:var(--chip);border:1px solid var(--line);border-radius:10px;
padding:8px 11px;min-width:120px}
.node b{display:block;font-size:9.5px;color:var(--muted);font-weight:750;
letter-spacing:.05em}
.arrow{color:var(--muted)}
.note{border:1px solid rgba(66,169,255,.27);border-left:3px solid var(--accent);
background:rgba(66,169,255,.055);padding:9px 12px;border-radius:0 10px 10px 0;
font-size:11.5px;color:var(--muted);margin:12px 0}
.note.bad{border-color:rgba(251,100,114,.35);border-left-color:var(--bad);
background:rgba(251,100,114,.06);color:var(--bad)}
.note[hidden]{display:none}
footer{padding:20px;color:var(--muted);font-size:11px;
border-top:1px solid var(--line);margin-top:24px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start;margin:10px 0}
.input{flex:1;min-width:280px;background:var(--panel);color:var(--text);
border:1px solid var(--line);border-radius:9px;padding:8px 11px;
font-family:inherit;font-size:12.5px}
.input:focus{outline:none;border-color:var(--accent)}
textarea.input{resize:vertical;line-height:1.5}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}
.chip{background:var(--chip);border:1px solid var(--line);color:var(--muted);
border-radius:8px;padding:4px 11px;font-size:11px;font-weight:600;
cursor:pointer;font-family:inherit;max-width:100%;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.chip:hover{color:var(--text);border-color:var(--accent)}
.chip.on{background:var(--accent);color:var(--on-accent);
border-color:var(--accent)}
.btn{background:var(--chip);border:1px solid var(--line);color:var(--text);
border-radius:8px;padding:6px 13px;font-size:12px;font-weight:650;
cursor:pointer;font-family:inherit}
.btn:hover:not(:disabled){border-color:var(--accent)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.primary{background:var(--accent);border-color:var(--accent);
color:var(--on-accent);font-weight:750}
.spark{width:100%;height:120px;display:block}
.blocks{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr));
margin:10px 0;align-items:start}
.blocks .blk{min-width:0;background:var(--chip);border:1px solid var(--line);
border-radius:12px;padding:12px;overflow:hidden}
.blocks .blk.viz-table,.blocks .blk.viz-kpi{grid-column:1/-1}
@media(max-width:1100px){.blocks{grid-template-columns:1fr}}
.blkhead{display:flex;gap:8px;align-items:center;font-size:12px;
font-weight:750;margin:2px 0 8px}
.aisum{display:flex;gap:9px;align-items:baseline;margin:2px 0 12px;
padding:9px 13px;border-radius:10px;font-size:12.5px;
background:var(--chip);border:1px solid var(--line)}
.aisum.good{border-left:3px solid var(--good)}
.aisum.warn{border-left:3px solid var(--warn)}
.aisum.bad{border-left:3px solid var(--bad)}
.aisum-tag{flex:none;font-size:9.5px;font-weight:800;letter-spacing:.08em;
color:var(--lineage)}
.blockhead{display:flex;align-items:center;gap:10px;width:100%;
background:transparent;border:none;color:var(--text);cursor:pointer;
font-family:inherit;font-size:13px;font-weight:750;padding:2px 0;text-align:left}
.blockhead small{margin-left:auto;color:var(--muted);font-weight:400;font-size:11px}
.bnum{background:var(--accent);color:var(--on-accent);border-radius:6px;
padding:2px 7px;font-size:11px;font-weight:750;
font-variant-numeric:tabular-nums}
"""

_JS = r"""
const RUNS = window.__RYNTA_RUNS__;
let D = window.__RYNTA__;               /* 활성 실행 — 기준일 전환 시 재지정 */
const $ = (s,r=document)=>r.querySelector(s);
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;
if(x!=null)e.textContent=x;return e};
const esc=s=>String(s==null?'':s);
const fmtNum=v=>typeof v==='number'
  ? (Math.abs(v)>=1000?v.toLocaleString('ko-KR',{maximumFractionDigits:0})
     :v.toLocaleString('ko-KR',{maximumFractionDigits:6})) : esc(v);

/* 컬럼 표시명 — 카탈로그 라벨(f.labels)이 기본이고, 설정 화면의 세션 재정의
   (STATE.labelOverrides)가 그 위에 얹힌다. 물리명은 버리지 않고 th.title로
   남긴다 — 감사자는 어느 원장 컬럼인지 물리명으로 찾는다. */
function colLabel(f,i){
  const phys=f.columns[i];
  const ovr=f.table&&STATE.labelOverrides[f.table];
  return (ovr&&ovr[phys])||(f.labels&&f.labels[i])||phys;
}

function table(f,{numeric=true,rowClass=null}={}){
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  const isNum=f.columns.map((_,i)=>numeric&&f.rows.some(r=>typeof r[i]==='number'));
  f.columns.forEach((c,i)=>{const lab=colLabel(f,i);
    const h=el('th',isNum[i]?'num':null,lab);
    if(lab!==c)h.title=c;               /* 물리명은 툴팁으로 */
    tr.appendChild(h)});
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  f.rows.forEach((r,i)=>{const x=el('tr');
    if(rowClass){const c=rowClass(r,i);if(c)x.className=c}
    r.forEach((v,i)=>{const td=el('td',isNum[i]?'num':null,
      v===null?'—':fmtNum(v));x.appendChild(td)});
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);
  const box=el('div');box.appendChild(w);
  if(f.total>f.shown){const m=el('div','meta',
    `미리보기 ${f.shown.toLocaleString()}행 / 전체 ${f.total.toLocaleString()}행 — 잘린 부분이 있다`);
    box.appendChild(m)}
  return box;
}
function pill(txt,tone){const p=el('span','pill'+(tone?' '+tone:''),txt);return p}
function ok(b){return pill(b?'통과':'미통과', b?'good':'bad')}

/* ---- 시각화 헬퍼 — 모든 값은 payload 원장에서 그대로 온다 ----
   프레임이 잘려 실렸으면(shown<total) 집계가 모집단과 다르므로, 그 사실을
   차트에 적는다. 조용한 절단은 "전체를 봤다"로 읽힌다. */
function fmtMoney(v){
  const a=Math.abs(v);
  if(a>=1e12)return (v/1e12).toFixed(1)+'조';
  if(a>=1e8)return (v/1e8).toFixed(0)+'억';
  /* 반올림하지 않는다 — 위험가중치 0.2를 0으로 보이면 표시가 거짓이 된다 */
  return fmtNum(v);
}
function frameIdx(f){const i={};f.columns.forEach((c,k)=>{i[c]=k});return i}
function srcMeta(f,extra){
  const cut=f.shown<f.total;
  const m=el('div','meta'+(cut?' warn':''),
    `원장 ${f.table} · ${cut?`표본 ${f.shown.toLocaleString()}/${f.total.toLocaleString()}행 기준`
                          :`${f.total.toLocaleString()}행 전량`}${extra?' · '+extra:''}`);
  return m;
}

/* 수평 그라디언트 막대 — 구성·기여도 */
function barList(items,{money=true}={}){
  const w=el('div');
  const max=Math.max(...items.map(x=>Math.abs(x.value)))||1;
  items.forEach(x=>{
    const line=el('div');line.style.margin='7px 0';
    const head=el('div','meta');
    head.style.display='flex';head.style.justifyContent='space-between';
    const lab=el('span',null,x.label);if(x.phys)lab.title=x.phys;
    head.appendChild(lab);
    const v=el('span','mono '+(x.tone||''),
      (money?fmtMoney(x.value):fmtNum(x.value))+(x.sub?' · '+x.sub:''));
    head.appendChild(v);line.appendChild(head);
    const b=el('div','bar'),f=el('i');
    f.style.width=(Math.abs(x.value)/max*100).toFixed(1)+'%';
    if(x.tone==='bad')f.style.background='var(--bad)';
    else if(x.tone==='warn')f.style.background='var(--warn)';
    b.appendChild(f);line.appendChild(b);w.appendChild(line)});
  return w;
}
function hbars(items,{title,src,money=true}={}){
  const c=el('div','card');
  if(title)c.appendChild(el('h3',null,title));
  c.appendChild(barList(items,{money}));
  if(src)c.appendChild(src);
  return c;
}

/* 영역 곡선 — 비정형 '추이' 블록용. 스파크보다 큰 캔버스, 기준선·격자·
   마지막 값 강조. 값은 전부 원장에서 온다. */
function areaLine(values,{height=190,label=null}={}){
  const w=920,h=height,padL=14,padR=64,padT=14,padB=18;
  const max=Math.max(...values,0),min=Math.min(...values,0);
  const span=(max-min)||1;
  const x=k=>padL+k*(w-padL-padR)/Math.max(values.length-1,1);
  const y=v=>h-padB-((v-min)/span)*(h-padT-padB);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('class','spark');
  svg.style.height=height+'px';
  /* 격자 3줄 */
  [0.25,0.5,0.75].forEach(t=>{
    const gy=padT+(h-padT-padB)*t;
    const l=document.createElementNS(ns,'line');
    l.setAttribute('x1',padL);l.setAttribute('x2',w-padR);
    l.setAttribute('y1',gy);l.setAttribute('y2',gy);
    l.setAttribute('stroke','currentColor');l.setAttribute('opacity','.08');
    svg.appendChild(l)});
  const pts=values.map((v,k)=>`${x(k).toFixed(1)},${y(v).toFixed(1)}`);
  /* 면 채움 */
  const area=document.createElementNS(ns,'polygon');
  area.setAttribute('points',
    `${x(0).toFixed(1)},${y(min).toFixed(1)} `+pts.join(' ')+
    ` ${x(values.length-1).toFixed(1)},${y(min).toFixed(1)}`);
  area.setAttribute('fill','var(--accent)');area.setAttribute('opacity','.10');
  svg.appendChild(area);
  const pl=document.createElementNS(ns,'polyline');
  pl.setAttribute('points',pts.join(' '));
  pl.setAttribute('fill','none');pl.setAttribute('stroke','var(--accent)');
  pl.setAttribute('stroke-width','2');svg.appendChild(pl);
  /* 마지막 값 강조 */
  const last=values[values.length-1];
  const dot=document.createElementNS(ns,'circle');
  dot.setAttribute('cx',x(values.length-1));dot.setAttribute('cy',y(last));
  dot.setAttribute('r','4');dot.setAttribute('fill','var(--accent)');
  svg.appendChild(dot);
  const t=document.createElementNS(ns,'text');
  t.setAttribute('x',x(values.length-1)+8);t.setAttribute('y',y(last)+4);
  t.setAttribute('fill','currentColor');t.setAttribute('font-size','11');
  t.setAttribute('font-weight','700');
  t.textContent=(label?label+' ':'')+fmtMoney(last);
  svg.appendChild(t);
  const box=el('div');box.appendChild(svg);return box;
}

/* 진행 미터 — 증빙·검증 진행률 */
function meter(label,num,den,tone){
  const line=el('div');line.style.margin='8px 0';
  const head=el('div','meta');
  head.style.display='flex';head.style.justifyContent='space-between';
  head.appendChild(el('span',null,label));
  head.appendChild(el('span','mono '+(tone||''),`${num} / ${den}`));
  line.appendChild(head);
  const b=el('div','bar'),f=el('i');
  f.style.width=(den?num/den*100:0).toFixed(1)+'%';
  if(tone==='warn')f.style.background='var(--warn)';
  if(tone==='bad')f.style.background='var(--bad)';
  b.appendChild(f);line.appendChild(b);
  return line;
}

/* 색점 상태 큐 — 의사결정·KRI */
function dotlist(items){
  const w=el('div');
  items.forEach(x=>{
    const r=el('div');r.style.cssText=
      'display:flex;gap:9px;align-items:center;padding:6px 2px;'+
      'border-bottom:1px solid var(--line);font-size:11.5px';
    const dot=el('span');dot.style.cssText=
      'width:8px;height:8px;border-radius:50%;flex:none;background:var(--'+
      (x.tone||'muted')+')';
    r.appendChild(dot);
    const lab=el('span',null,x.label);lab.style.flex='1';r.appendChild(lab);
    if(x.right)r.appendChild(el('span','meta '+(x.tone||''),x.right));
    w.appendChild(r)});
  return w;
}

/* 백테스트 예외 달력 — 영업일 1칸, 예외는 위반색 */
function calheat(f){
  const i=frameIdx(f);
  const c=el('div','card');
  c.appendChild(el('h3',null,'백테스팅 예외 달력'));
  const wrap=el('div');
  wrap.style.cssText='display:flex;flex-wrap:wrap;gap:3px';
  let nEx=0;
  f.rows.slice().sort((a,b)=>String(a[i.obs_date]).localeCompare(String(b[i.obs_date])))
   .forEach(r=>{
    const ex=!!r[i.exception];if(ex)nEx++;
    const d=el('span');
    d.title=`${r[i.obs_date]} · 손익 ${fmtMoney(r[i.pnl])} · VaR ${fmtMoney(r[i.var_99])}`+
            (ex?' · 예외':'');
    d.style.cssText='width:11px;height:11px;border-radius:3px;background:'+
      (ex?'var(--bad)':'var(--chip)')+';border:1px solid var(--line)';
    wrap.appendChild(d)});
  c.appendChild(wrap);
  c.appendChild(el('div','meta',
    `예외 ${nEx}건 / 관측 ${f.rows.length}일 — 신호등 구간은 원장 zone 열`));
  c.appendChild(srcMeta(f));
  return c;
}

/* 손익 대 VaR 경계 — 관측일 순 이중 곡선, 예외는 점 */
function pnlChart(f){
  const i=frameIdx(f);
  const rows=f.rows.slice().sort((a,b)=>
    String(a[i.obs_date]).localeCompare(String(b[i.obs_date])));
  const w=920,h=200,padL=10,padR=10,padT=10,padB=10;
  const pnl=rows.map(r=>r[i.pnl]),neg=rows.map(r=>-r[i.var_99]);
  const all=pnl.concat(neg);
  const max=Math.max(...all),min=Math.min(...all),span=(max-min)||1;
  const x=k=>padL+k*(w-padL-padR)/Math.max(rows.length-1,1);
  const y=v=>h-padB-((v-min)/span)*(h-padT-padB);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('class','spark');
  svg.style.height='200px';
  [[pnl,'var(--accent)'],[neg,'var(--bad)']].forEach(([vs,col])=>{
    const pl=document.createElementNS(ns,'polyline');
    pl.setAttribute('points',vs.map((v,k)=>`${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(' '));
    pl.setAttribute('fill','none');pl.setAttribute('stroke',col);
    pl.setAttribute('stroke-width',col.includes('bad')?'1.4':'1.8');
    if(col.includes('bad'))pl.setAttribute('stroke-dasharray','5 3');
    svg.appendChild(pl)});
  rows.forEach((r,k)=>{
    if(!r[i.exception])return;
    const dot=document.createElementNS(ns,'circle');
    dot.setAttribute('cx',x(k));dot.setAttribute('cy',y(r[i.pnl]));
    dot.setAttribute('r','3.5');dot.setAttribute('fill','var(--bad)');
    svg.appendChild(dot)});
  const c=el('div','card');
  c.appendChild(el('h3',null,'일별 손익 대 VaR 경계 (99%)'));
  c.appendChild(svg);
  c.appendChild(el('div','meta','실선 손익 · 점선 −VaR — 점선 아래 손익이 백테스팅 예외다'));
  c.appendChild(srcMeta(f));
  return c;
}

/* 프레임 → 그룹 합계 — 잘린 프레임이면 합계가 모집단이 아님을 호출자가 안다 */
function groupSum(f,keyCol,valCol){
  const i=frameIdx(f),m=new Map();
  f.rows.forEach(r=>{
    const k=r[i[keyCol]];
    const cur=m.get(k)||{sum:0,n:0};
    cur.sum+=(r[i[valCol]]||0);cur.n++;m.set(k,cur)});
  return [...m.entries()].map(([k,v])=>({key:k,sum:v.sum,n:v.n}))
    .sort((a,b)=>b.sum-a.sum);
}

/* ---- 부문별 분석 차트 — 원장이 있는 부문에만 그린다 ---- */
const DOMAIN_CHARTS={
  'PRD-RWA':root=>{
    const sa=D.data['rwa_sa_bucket'];
    if(sa){const i=frameIdx(sa);
      root.appendChild(hbars(sa.rows.map(r=>({
        label:`${r[i.asset_class]} · RW ${(r[i.risk_weight]*100).toFixed(0)}%`,
        value:r[i.rwa],sub:`EAD ${fmtMoney(r[i.ead])}`}))
        .sort((a,b)=>b.value-a.value),
        {title:'위험가중자산 구성 — 표준방법 자산군×위험가중치',src:srcMeta(sa)}))}
    const irb=D.data['rwa_irb_pool'];
    if(irb){const i=frameIdx(irb);
      root.appendChild(hbars(irb.rows.map(r=>({
        label:`${r[i.asset_class]} · PD ${r[i.pd_band]}`,
        value:r[i.rwa],sub:`평균 RW ${(r[i.rw_average]*100).toFixed(0)}%`}))
        .sort((a,b)=>b.value-a.value).slice(0,10),
        {title:'내부등급법 풀별 위험가중자산 — PD 구간',src:srcMeta(irb)}))}
  },
  'PRD-MKT':root=>{
    const bt=D.data['mkt_backtest_exception'];
    if(bt){root.appendChild(pnlChart(bt));root.appendChild(calheat(bt))}
    const ipv=D.data['mkt_ipv'];
    if(ipv){const i=frameIdx(ipv);
      const open=ipv.rows.filter(r=>r[i.is_break]);
      root.appendChild(hbars(open.sort((a,b)=>b[i.days_open]-a[i.days_open])
        .slice(0,8).map(r=>({label:`${r[i.trade_id]} · ${r[i.source]}`,
          value:r[i.days_open],sub:`차이 ${fmtMoney(r[i.diff])}`,
          tone:r[i.days_open]>=5?'bad':'warn'})),
        {title:'독립가격검증(IPV) 미해소 — 경과일 상위',money:false,
         src:srcMeta(ipv,`미해소 ${open.length}건`)}))}
  },
  'PRD-ECL':root=>{
    const f=D.data['ecl_result'];
    if(!f)return;
    const g=groupSum(f,'stage','ecl');
    root.appendChild(hbars(g.map(x=>({
      label:`Stage ${x.key}${x.key===2?' — SICR 전이':x.key===3?' — 손상':''}`,
      value:x.sum,sub:`${x.n.toLocaleString()}건`,
      tone:x.key===3?'bad':x.key===2?'warn':undefined})),
      {title:'기대신용손실 구성 — 단계별',src:srcMeta(f)}));
  },
  'PRD-CRM':root=>{
    const f=D.data['crm_ews_signal'];
    if(!f)return;
    const i=frameIdx(f),g=groupSum(f,'level','ead');
    root.appendChild(hbars(g.map(x=>({
      label:`조기경보 ${x.key}`,value:x.sum,sub:`${x.n.toLocaleString()}건`,
      tone:x.key==='경보'?'bad':x.key==='주의'?'warn':undefined})),
      {title:'조기경보 단계별 익스포저(EAD)',src:srcMeta(f)}));
  },
  'PRD-ALM':root=>{
    const f=D.data['alm_lcr_item'];
    if(!f)return;
    const i=frameIdx(f);
    root.appendChild(hbars(f.rows.map(r=>({
      label:`${r[i.section]} · ${r[i.category]}`,value:Math.abs(r[i.weighted]),
      sub:`적용률 ${(r[i.factor]*100).toFixed(0)}%`,
      tone:r[i.section]==='OUTFLOW'?'warn':undefined}))
      .sort((a,b)=>b.value-a.value),
      {title:'유동성커버리지비율 구성 — 가중 후 금액',src:srcMeta(f)}));
  },
  'PRD-OPR':root=>{
    const f=D.data['opr_loss_event'];
    if(f){const g=groupSum(f,'event_type','net_loss');
      root.appendChild(hbars(g.map(x=>({label:x.key,value:x.sum,
        sub:`${x.n.toLocaleString()}건`})),
        {title:'운영손실 순손실 구성 — 사건유형별',src:srcMeta(f)}))}
    const k=D.data['opr_kri'];
    if(k){const i=frameIdx(k);
      const c=el('div','card');
      c.appendChild(el('h3',null,'핵심리스크지표(KRI) 상태'));
      c.appendChild(dotlist(k.rows.map(r=>({
        label:r[i.kri_name],
        right:`${fmtNum(r[i.value])} / 경보 ${fmtNum(r[i.threshold_red])}`,
        tone:r[i.status]==='red'?'bad':r[i.status]==='amber'?'warn':'good'}))));
      c.appendChild(srcMeta(k));root.appendChild(c)}
  },
};


/* ---- 00 콕핏 ---- */
function cockpit(root){
  const g=el('div','grid');
  D.kpis.forEach(k=>{const c=el('div','card kpi');
    c.appendChild(el('div','lab',k.label));
    c.appendChild(el('div','val '+(k.tone||''),k.value));
    c.appendChild(el('div','sub',k.sub));
    c.appendChild(el('div','ln','↗ 계보 · '+k.lineage));
    g.appendChild(c)});
  root.appendChild(g);

  /* --- 인사이트 리본 — 전 부문 원장에서 규칙으로 뽑은 문장들 --- */
  const ins=cockpitInsights();
  if(ins.length){
    const rib=el('div','card');
    rib.appendChild(el('h3',null,'인사이트 — 지금 봐야 할 것'));
    rib.appendChild(dotlist(ins.map(x=>({label:x.t,
      tone:x.tone==='bad'?'bad':x.tone==='warn'?'warn':'good'}))));
    rib.appendChild(el('div','meta',
      '규칙 기반 자동 분석 — 결정론(같은 데이터면 같은 문장) · 외부 LLM 호출 없음'));
    root.appendChild(rib);
  }

  /* --- 위기 경로 + 역스트레스 — 전사 자본의 앞날 --- */
  const two0=el('div');two0.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1.5fr 1fr';
  if(window.matchMedia('(max-width:900px)').matches)
    two0.style.gridTemplateColumns='1fr';
  const cp=D.data['st_capital_path'];
  if(cp){const i=frameIdx(cp);
    const scenarios=[...new Set(cp.rows.map(r=>r[i.scenario]))];
    const quarters=[...new Set(cp.rows.map(r=>r[i.quarter]))];
    const series=scenarios.map(sc=>({name:sc,
      values:quarters.map(q=>{const r=cp.rows.find(x=>x[i.scenario]===sc&&
        x[i.quarter]===q);return r?r[i.cet1_ratio]:null})}));
    const c=el('div','card');
    c.appendChild(el('h3',null,'위기상황 보통주자본비율 경로 — 3시나리오'));
    c.appendChild(multiLine(series,quarters,0.08));
    c.appendChild(srcMeta(cp));
    two0.appendChild(c)}
  const rv=D.reverse_stress;
  if(rv){const c=el('div','card');
    c.appendChild(el('h3',null,'역스트레스 — 임계까지의 거리'));
    c.appendChild(meter('임계 심도 (심각=1.0 기준)',
      Math.min(rv.critical_severity,1),1,
      rv.critical_severity<1?'bad':undefined));
    c.appendChild(el('div','meta',
      `심도 ${rv.critical_severity.toFixed(3)}에서 ${rv.metric.toUpperCase()} `+
      `${(rv.target_ratio*100).toFixed(0)}% 붕괴 · 함의 GDP `+
      `${(rv.implied_gdp_shock*100).toFixed(2)}% · LGD +`+
      `${(rv.implied_lgd_addon*100).toFixed(2)}%p`));
    const lm=D.limits,li2=frameIdx(lm);
    c.appendChild(el('h3',null,'한도 소진 상위'));
    c.appendChild(barList(lm.rows.slice()
      .sort((a,b)=>b[li2.utilisation]-a[li2.utilisation]).slice(0,4)
      .map(r=>({label:`${r[li2.limit]} · ${r[li2.bucket]}`,
        value:r[li2.utilisation]*100,
        tone:r[li2.severity]==='breach'?'bad':
             r[li2.severity]==='warning'?'warn':undefined})),{money:false}));
    two0.appendChild(c)}
  root.appendChild(two0);

  /* --- 예외 스트림 — 조치가 붙은 미해소 예외 상위 --- */
  const exq=D.data['gov_exception_action'];
  if(exq){const xi=frameIdx(exq);
    const c=el('div','card');
    c.appendChild(el('h3',null,'예외 스트림 — 자동상계 금지'));
    c.appendChild(dotlist(exq.rows.slice(0,6).map(r=>({
      label:`${r[xi.exception_id]} · ${r[xi.finding]}`,
      right:`${r[xi.status]} · 기한 ${r[xi.due_days]}일`,
      tone:r[xi.severity]==='중대'?'bad':'warn'}))));
    if(exq.shown<exq.total)c.appendChild(el('div','meta',
      `표시 6건 / 전체 ${exq.total.toLocaleString()}건 — 예외·조치 화면에서 전량`));
    root.appendChild(c)}

  /* --- 구성 브리지 + 통제 진행 — 캡처(v9.5.0)의 콕핏 모듈 --- */
  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1.4fr 1fr';
  if(window.matchMedia('(max-width:900px)').matches)
    two.style.gridTemplateColumns='1fr';
  const sa=D.data['rwa_sa_bucket'];
  if(sa){const i=frameIdx(sa);
    two.appendChild(hbars(sa.rows.map(r=>({
      label:`${r[i.asset_class]} · RW ${(r[i.risk_weight]*100).toFixed(0)}%`,
      value:r[i.rwa]})).sort((a,b)=>b.value-a.value).slice(0,7),
      {title:'위험가중자산 구성 — 표준방법',src:srcMeta(sa)}))}
  const ctl=el('div','card');
  ctl.appendChild(el('h3',null,'통제 진행 — 증빙·대사·검증'));
  const ev=D.evidence_nodes,evi=frameIdx(ev);
  ctl.appendChild(meter('증빙 계보 완결',
    ev.rows.filter(r=>r[evi.status]==='완결').length,ev.rows.length));
  const rc=D.reconciliation,rci=frameIdx(rc);
  ctl.appendChild(meter('집계·대사 통과',
    rc.rows.filter(r=>r[rci.status]==='PASS').length,rc.rows.length));
  const vl=D.validation,vli=frameIdx(vl);
  const nfail=vl.rows.filter(r=>r[vli.status]==='FAIL').length;
  ctl.appendChild(meter('자체검증 PASS',
    vl.rows.filter(r=>r[vli.status]==='PASS').length,vl.rows.length,
    nfail?'bad':undefined));
  const ap=D.approvals,api=frameIdx(ap);
  const pend=ap.rows.filter(r=>r[api.decision]!=='승인');
  ctl.appendChild(el('h3',null,'의사결정 큐'));
  ctl.appendChild(dotlist((pend.length?pend:ap.rows).slice(0,6).map(r=>({
    label:`${r[api.subject_type]} · ${r[api.subject_id]}`,
    right:r[api.decision],
    tone:r[api.decision]==='승인'?'good':r[api.decision]==='반려'?'bad':'warn'}))));
  if(ap.shown<ap.total)ctl.appendChild(el('div','meta',
    `표시 범위 — 승인 원장 ${ap.total.toLocaleString()}건 중 ${ap.shown.toLocaleString()}건`));
  two.appendChild(ctl);
  root.appendChild(two);

  const c1=el('div','card');c1.appendChild(el('h3',null,'증빙 계보 · 7단계 — 단계를 누르면 상세'));
  const flow=el('div','flow');
  const drill=el('div');                     /* 드릴다운 패널 (PLT-018) */
  D.evidence_nodes.rows.forEach((r,i)=>{
    const [ , nid, stage, label, ref, status]=r;
    const n=el('div','node');n.style.cursor='pointer';
    n.appendChild(el('b',null,`0${i+1} ${stage}`));
    n.appendChild(el('div',null,label));
    const s=el('div');s.appendChild(pill(status,
      status==='완결'?'good':status==='검토'?'warn':'bad'));
    n.appendChild(s);flow.appendChild(n);
    n.onclick=()=>{
      drill.innerHTML='';
      const d=el('div','note');
      d.textContent=`단계 ${stage} · ${label} — 참조 ${ref||'—'} · 상태 ${status} · 노드 ${nid}`;
      drill.appendChild(d);
      /* 실행 간 대조 — 실은 실행 전부의 지문·규모를 나란히 (버전 diff) */
      const runs=Object.keys(RUNS).sort();
      drill.appendChild(table({columns:
        ['기준일','실행 ID','산출 지문','제출 서식','원장 행수','3선 게이트'],
        rows:runs.map(a=>{const m=RUNS[a].meta,iv=RUNS[a].independent;
          return [a,m.run_id,m.digest.slice(0,16),
                  RUNS[a].forms.length,m.n_rows,iv.status]}),
        total:runs.length,shown:runs.length},{numeric:false}));
      if(runs.length>1){
        const uniq=new Set(runs.map(a=>RUNS[a].meta.digest));
        drill.appendChild(el('div','meta',uniq.size===1
          ?'실행 간 지문 동일 — 같은 산출물이다'
          :`실행 간 지문 상이 ${uniq.size}종 — 기준일이 다르면 산출물도 다른 판이다`));
      }
    };
    if(i<D.evidence_nodes.rows.length-1)flow.appendChild(el('span','arrow','→'));
  });
  c1.appendChild(flow);
  c1.appendChild(drill);
  c1.appendChild(table(D.evidence_edges));
  root.appendChild(c1);

  const c2=el('div','card');c2.appendChild(el('h3',null,'집계·대사 예외 큐 — 자동상계 금지'));
  c2.appendChild(table(D.reconciliation,{rowClass:r=>r[8]==='FAIL'?'':null}));
  c2.appendChild(el('h3',null,'원천 인터페이스 계약 (Interface Watch)'));
  c2.appendChild(table(D.contracts));
  root.appendChild(c2);

  const c3=el('div','card');c3.appendChild(el('h3',null,'의사결정 큐 · 4-Eyes 승인'));
  c3.appendChild(table(D.approvals));
  root.appendChild(c3);
}

/* ---- 정형 조회 스튜디오 (라이브) ---- */
const STATE = {killed: false, killScope: '전사', approved: {}, history: {},
  labelOverrides: {}};

function viewSelect(onChange, filterFn){
  const sel=el('select','sel');
  Object.values(D.view_meta).filter(filterFn||(()=>true))
    .sort((a,b)=>a.domain.localeCompare(b.domain))
    .forEach(v=>{const o=el('option');o.value=v.view_id;
      o.textContent=`${v.domain} · ${v.view_name}`;sel.appendChild(o)});
  sel.onchange=()=>onChange(sel.value);
  return sel;
}
function chips(items, onPick){
  const box=el('div','chips');
  items.forEach(t=>{const b=el('button','chip',t);
    b.onclick=()=>onPick(t);box.appendChild(b)});
  return box;
}

function structured(root){
  root.appendChild(el('p','lead',
    '문장을 고치면 조회계획이 즉시 다시 만들어진다. 자연어는 승인된 스키마·필드·연산자·권한으로만 번역되며, '+
    '인식하지 못한 필드는 조용히 무시하지 않고 차단 사유로 남는다. 화면 열과 레이아웃은 고정이다.'));

  const bar=el('div','toolbar');
  let viewId=(D.demo_queries[0]||{}).view_id||Object.keys(D.view_meta)[0];
  const sel=viewSelect(v=>{viewId=v;syncMeta();run()});
  sel.value=viewId;
  const input=el('input','input');
  input.type='text';
  input.placeholder='예) 연체일수 30 이상 그리고 잔액 100억 이상';
  input.value=(D.demo_queries[0]||{}).utterance||'';
  bar.appendChild(sel);bar.appendChild(input);
  root.appendChild(bar);

  const presetBox=el('div');root.appendChild(presetBox);
  const metaLine=el('div','meta');root.appendChild(metaLine);
  const pane=el('div');root.appendChild(pane);

  function syncMeta(){
    const v=D.view_meta[viewId];
    presetBox.innerHTML='';
    const mine=D.demo_queries.filter(q=>q.view_id===viewId).map(q=>q.utterance);
    const usable=v.fields.filter(f=>f.permitted&&f.min_aggregation===1);
    const num=usable.filter(f=>D.data[v.table_ref].rows.some(
      r=>typeof r[D.data[v.table_ref].columns.indexOf(f.field_name)]==='number'));
    const fallback=[];
    if(num.length>=2)fallback.push(`${num[0].korean} 0 초과 그리고 ${num[1].korean} 0 이상`);
    usable.slice(0,2).forEach(f=>fallback.push(`${f.korean} 0 이상`));
    /* 차단 시연 — 마스킹 필드가 있으면 그것을 조건으로 쓰는 문장을 하나 준다.
       통제가 실제로 걸리는 걸 눈으로 보여주는 게 시연의 핵심이다. */
    const masked=v.fields.find(f=>f.masking!=='none'||!f.permitted);
    fallback.push(masked
      ? `${masked.korean} X0001  ← 차단 시연`
      /* 마스킹 필드가 없는 View라도 차단 경로는 보여줄 수 있어야 한다 —
         조건 없는 문장은 전건 조회로 통과하지 않는다. */
      : '전부 다 보여줘  ← 차단 시연');
    presetBox.appendChild(chips(mine.concat(fallback),t=>{
      input.value=t.replace(/\s*←.*$/,'');run()}));
    metaLine.textContent=
      `View ${v.view_id} · 원장 ${v.table_ref} · 조회 가능 필드 `+
      `${v.fields.filter(f=>f.permitted).length}/${v.fields.length} · 화면 내 데이터 `+
      `${v.embedded_rows.toLocaleString()}행 (모집단 ${v.total_rows.toLocaleString()}행) · 행 상한 ${v.row_limit}`;
  }

  function run(){
    const v=D.view_meta[viewId];
    const plan=RY.compileQuery(input.value,{viewId:v.view_id,asof:D.meta.asof,
      fields:v.fields, population:v.view_name});
    const res=RY.execute(plan, D.data[v.table_ref], v.row_limit);
    renderLivePlan(pane, res.plan, res, v);
  }
  input.addEventListener('input',run);
  syncMeta();run();
}

function renderLivePlan(pane, plan, res, v){
  pane.innerHTML='';
  const c=el('div','card');
  const killed=killedFor(v.domain);       /* 범위형 — 부문 밖 조회는 산다 */
  const st=el('div','steps');
  const cond=plan.conditions.map(RY.describe).join(' ∧ ')||'—';
  [['01 의도',plan.utterance.slice(0,40)||'조회'],['02 기준일',plan.asof],
   ['03 모집단',v.view_name],['04 조건',cond],['05 정책',plan.policy]]
   .forEach(([k,val])=>{const b=el('div','step');
     b.appendChild(el('b',null,k));b.appendChild(el('div',null,val));st.appendChild(b)});
  c.appendChild(st);

  const m=el('div','meta');
  m.appendChild(document.createTextNode('조회 지문 '+plan.query_hash+' · 계획 '+plan.plan_id+' · '));
  m.appendChild(pill(killed?'비상정지 — 실행 차단'
    :plan.status==='validated'?'Read-only 실행':'차단',
    killed?'bad':plan.status==='validated'?'good':'bad'));
  c.appendChild(m);
  c.appendChild(el('div','mono','AST: '+plan.ast));
  if(plan.block_reason)c.appendChild(el('div','note','차단 사유 — '+plan.block_reason));
  if(killed)c.appendChild(el('div','note',
    'Kill Switch가 걸려 있어 신규 조회를 실행하지 않는다. 진행 중이던 결정론적 계산은 완료 후 중단된다.'));

  if(plan.status==='validated'&&!killed){
    c.appendChild(el('h3',null,
      `고정 컬럼 결과 · 모집단 ${plan.n_rows.toLocaleString()}건`));
    const src=D.data[v.table_ref];
    c.appendChild(table({table:src.table,columns:res.columns,
      labels:res.columns.map(x=>colLabel(src,src.columns.indexOf(x))),
      rows:res.rows,total:plan.n_rows,shown:res.rows.length}));
    if(v.embedded_rows<v.total_rows)c.appendChild(el('div','meta',
      `※ 화면에는 원장 ${v.total_rows.toLocaleString()}행 중 ${v.embedded_rows.toLocaleString()}행이 실려 있다 — 위 건수는 그 범위 기준이다.`));
  }
  pane.appendChild(c);
}

/* ---- 비정형 Adaptive UI (라이브) ---- */
function adaptive(root){
  root.appendChild(el('p','lead',
    '프롬프트를 고치면 레이아웃 제안이 즉시 바뀐다. 프롬프트는 UI 구성안만 만들 뿐 승인되지 않은 필드, '+
    '행 수준 개인정보, 규제산출 변경, 판단 확정은 하지 않는다. 세 검증을 모두 통과해야 사람이 승인할 수 있고, '+
    '승인 전에는 화면에 반영되지 않는다.'));

  const bar=el('div','toolbar');
  let viewId=(D.demo_prompts[0]||{}).view_id||Object.keys(D.view_meta)[0];
  const sel=viewSelect(v=>{viewId=v;syncMeta();run()});
  sel.value=viewId;
  const ta=el('textarea','input');
  ta.rows=2;
  ta.placeholder='예) 자산군별 기여도를 막대차트로 보여주고 아래에 EAD·위험가중치 검토 표를 배치해줘. 상위 10건.';
  ta.value=(D.demo_prompts[0]||{}).prompt||'';
  bar.appendChild(sel);bar.appendChild(ta);
  root.appendChild(bar);

  const presetBox=el('div');root.appendChild(presetBox);
  const fieldHint=el('div','meta');root.appendChild(fieldHint);
  const pane=el('div');root.appendChild(pane);

  function syncMeta(){
    const v=D.view_meta[viewId];
    presetBox.innerHTML='';
    const mine=D.demo_prompts.filter(q=>q.view_id===viewId).map(q=>q.prompt);
    /* 예시 문장은 열 타입을 보고 만든다 — 앞에서 4개를 자르면 기준일·식별자
       같은 열이 문장에 들어가 막대에 값 열이 없거나 라벨이 전부 같은,
       요청 의도가 드러나지 않는 레이아웃이 된다 (검수 지적). */
    const frame=D.data[v.table_ref];
    const fi={};frame.columns.forEach((c,k)=>{fi[c]=k});
    const usable=v.fields.filter(f=>f.permitted&&f.masking==='none'
      &&f.field_name in fi);
    const distinct=f=>new Set(frame.rows.slice(0,50)
      .map(r=>r[fi[f.field_name]])).size>1;
    const nums=usable.filter(f=>frame.rows.some(
      r=>typeof r[fi[f.field_name]]==='number')&&distinct(f));
    const cats=usable.filter(f=>frame.rows.some(
      r=>typeof r[fi[f.field_name]]==='string')&&distinct(f));
    const fallback=[];
    if(cats[0]&&nums[0])fallback.push(
      `${cats[0].korean}별 ${nums[0].korean} 기여도를 막대차트로 보여주고 아래에 `+
      `${nums.slice(0,3).map(f=>f.korean).join('·')} 검토 표를 배치해줘. 상위 10건.`);
    if(nums[0])fallback.push(`${nums[0].korean} 추이를 보여줘`);
    if(nums.length>=2)fallback.push(
      `${nums.slice(0,3).map(f=>f.korean).join('와 ')}를 카드로 보여줘`);
    else if(cats[0]&&nums[0])fallback.push(
      `${cats[0].korean}와 ${nums[0].korean}를 카드로 보여줘`);
    presetBox.appendChild(chips(mine.concat(fallback),t=>{ta.value=t;run()}));
    fieldHint.textContent='사용 가능한 열 — '+v.fields
      .filter(f=>f.permitted&&f.masking==='none').map(f=>f.korean).join(' · ');
  }
  function run(){
    const v=D.view_meta[viewId];
    const pr=RY.compose(ta.value,{viewId:v.view_id,fields:v.fields,
      rowLimit:v.row_limit});
    renderProposal(pane, pr, v, run);
  }
  ta.addEventListener('input',run);
  syncMeta();run();
}

function renderProposal(pane, pr, v, rerun){
  pane.innerHTML='';
  const approved=STATE.approved[v.view_id];
  const c=el('div','card');
  c.appendChild(el('h3',null,pr.proposal_id+' · '+v.view_name));
  const st=el('div','steps');
  [['필드 권한',pr.field_policy_pass],['스키마·단위',pr.schema_pass],
   ['집계 최소단위',pr.aggregation_pass],
   ['사람 적용승인',!!(approved&&approved.proposal_id===pr.proposal_id)]]
   .forEach(([k,val])=>{const b=el('div','step');
     b.appendChild(el('b',null,k));const d=el('div');d.appendChild(ok(val));
     b.appendChild(d);st.appendChild(b)});
  c.appendChild(st);
  const m=el('div','meta');
  m.appendChild(document.createTextNode('제안 레이아웃 — '));
  m.appendChild(el('span','mono',pr.layout_text));
  c.appendChild(m);

  const acts=el('div','toolbar');
  const bPrev=el('button','btn','미리보기 생성');
  const bApp=el('button','btn primary','승인 적용');
  const bRb=el('button','btn','Rollback');
  /* 비상정지는 이 탭에도 미친다 — 정형 조회만 막고 여기를 열어 두면
     "정지"가 화면 절반에만 걸린 통제가 된다. */
  bApp.disabled=!pr.all_pass||killedFor(v.domain);
  bRb.disabled=!STATE.history[v.view_id]||!STATE.history[v.view_id].length;
  acts.appendChild(bPrev);acts.appendChild(bApp);acts.appendChild(bRb);
  c.appendChild(acts);

  const status=el('div','meta');
  status.appendChild(pill(
    approved&&approved.proposal_id===pr.proposal_id?'승인 적용':
    pr.all_pass?'미리보기 · 승인 대기':'정책 거부',
    approved&&approved.proposal_id===pr.proposal_id?'good':
    pr.all_pass?'warn':'bad'));
  c.appendChild(status);

  if(pr.rejected_fields.length)c.appendChild(el('div','note',
    '차단된 열 — '+pr.rejected_fields.join(', ')+' (미승인 필드는 레이아웃에 세울 수 없다)'));
  else if(!pr.aggregation_pass)c.appendChild(el('div','note',
    '집계 최소단위 위반 — 마스킹 필드를 행 단위 열로 세울 수 없다'));
  else if(!pr.schema_pass)c.appendChild(el('div','note',
    '승인된 열을 하나도 짚지 못했다 — 위 "사용 가능한 열"의 이름을 문장에 포함할 것'));

  /* 거부 사유는 화면에 적는다. alert()은 샌드박스 iframe에서 차단되므로
     승인이 거부돼도 아무 말 없이 끝난다 — 거부를 못 본 승인이 제일 위험하다. */
  const errBox=el('div','note bad');errBox.hidden=true;
  c.appendChild(errBox);

  const previewBox=el('div');
  c.appendChild(previewBox);
  pane.appendChild(c);

  function draw(applied){
    previewBox.innerHTML='';
    if(killedFor(v.domain)){previewBox.appendChild(el('div','note',
      'Kill Switch가 걸려 있어 미리보기·승인을 실행하지 않는다.'));return}
    if(!pr.all_pass){previewBox.appendChild(el('div','note',
      '정책검증 미통과 — 미리보기를 그리지 않는다.'));return}
    previewBox.appendChild(el('h3',null,
      applied?'승인 적용 화면':'미리보기 (운영 반영 전)'));
    renderBlocks(previewBox, pr, v);
  }
  bPrev.onclick=()=>{errBox.hidden=true;draw(false);};
  bApp.onclick=()=>{
    try{
      const a=RY.approve(pr,'리스크관리부장');
      (STATE.history[v.view_id]=STATE.history[v.view_id]||[])
        .push(STATE.approved[v.view_id]||null);
      STATE.approved[v.view_id]=a;
      errBox.hidden=true;
      rerun();
    }catch(e){
      errBox.textContent='승인 거부 — '+e.message;
      errBox.hidden=false;
    }
  };
  bRb.onclick=()=>{
    const h=STATE.history[v.view_id]||[];
    STATE.approved[v.view_id]=h.pop()||null;
    rerun();
  };
  if(approved&&approved.proposal_id===pr.proposal_id)draw(true);
  else if(pr.all_pass)draw(false);
  else draw(false);
}

function renderBlocks(box, pr, v){
  const frame=D.data[v.table_ref];
  const idx={};frame.columns.forEach((c,i)=>{idx[c]=i});
  const lab=c=>colLabel(frame, idx[c]);          /* 물리명 → 표시명 */
  const cols=pr.columns.filter(c=>c in idx);
  let numCol=cols.find(c=>frame.rows.some(r=>typeof r[idx[c]]==='number'));
  /* "기여도를 막대로"처럼 값 열이 문장에 없으면 요청한 레이아웃 자체가
     사라진다. 이 View의 승인·비마스킹 숫자 열 중 첫 번째로 그리되,
     기본 열을 썼다는 사실을 블록에 공시한다 — 조용한 대체는 없다. */
  let numFallback=false;
  if(!numCol){
    const ok=new Set(v.fields.filter(f=>f.permitted&&f.masking==='none')
      .map(f=>f.field_name));
    numCol=frame.columns.find(c=>ok.has(c)&&
      frame.rows.some(r=>typeof r[idx[c]]==='number'));
    if(numCol)numFallback=true;
  }
  const isLabelish=c=>c!==numCol&&
    frame.rows.some(r=>typeof r[idx[c]]==='string')&&
    new Set(frame.rows.slice(0,50).map(r=>r[idx[c]])).size>1; /* 고유값 1개는 라벨이 아니다 */
  let labCol=cols.find(isLabelish)||frame.columns.find(isLabelish)||
    cols.find(c=>c!==numCol&&frame.rows.some(r=>typeof r[idx[c]]==='string'));
  let rows=frame.rows.slice();
  if(numCol)rows.sort((a,b)=>(b[idx[numCol]]||0)-(a[idx[numCol]]||0));
  rows=rows.slice(0,pr.row_limit);
  const sub={table:frame.table,columns:cols,labels:cols.map(lab),
             rows:rows.map(r=>cols.map(c=>r[idx[c]])),
             total:frame.total,shown:rows.length};

  /* 블록 순서는 프롬프트에 나온 순서 그대로다 — 사용자가 "위에 차트, 아래에 표"
     라고 쓰면 그 순서로 배치돼야 레이아웃이 바뀐 것으로 읽힌다.
     배치는 2열 그리드다: 차트(막대·추이)는 반 폭으로 나란히 서고, 카드 줄과
     표는 전체 폭을 쓴다 — 실무 요청("차트 옆에 차트, 아래 검토 표")의 기본
     구도다. 좁은 화면은 1열로 내려간다. */
  const grid=el('div','blocks');
  const blkHead=(kind,text,phys)=>{
    const h=el('div','blkhead');
    const b=el('span','pill',kind);
    h.appendChild(b);
    const t=el('span',null,text);if(phys)t.title=phys;
    h.appendChild(t);
    return h;
  };
  pr.blocks.forEach(([viz,title])=>{
    const blk=el('div','blk viz-'+viz);  /* 'bar' 원클래스는 막대 트랙(.bar)과 충돌한다 */
    if(viz==='kpi'){
      const g=el('div','grid');
      cols.slice(0,4).forEach(cName=>{
        const j=idx[cName];
        const nums=rows.map(r=>r[j]).filter(x=>typeof x==='number');
        const card=el('div','card kpi');
        const kl=el('div','lab',lab(cName));kl.title=cName;
        card.appendChild(kl);
        if(nums.length){
          const sum=nums.reduce((a,b)=>a+b,0);
          card.appendChild(el('div','val',fmtMoney(sum)));
          card.appendChild(el('div','sub',
            `평균 ${fmtMoney(sum/nums.length)} · 최대 ${fmtMoney(Math.max(...nums))} · ${nums.length}건`));
        } else {
          card.appendChild(el('div','val',String(rows.length)+'행'));
          card.appendChild(el('div','sub','건수'));
        }
        card.appendChild(el('div','ln','↗ 원장 · '+v.table_ref+'.'+cName));
        g.appendChild(card)});
      blk.appendChild(blkHead('카드',title||'핵심 지표'));
      blk.appendChild(g);
    } else if(viz==='bar'&&numCol){
      blk.appendChild(blkHead('막대',`${title} · ${lab(numCol)}`,numCol));
      if(numFallback)blk.appendChild(el('div','meta',
        `값 열이 문장에 없어 이 View의 기본 값 열(${lab(numCol)})로 그렸다 — 다른 열은 문장에 이름을 적으면 된다`));
      const top=rows.slice(0,10).map((r,i)=>({
        label:labCol?esc(r[idx[labCol]]):'#'+(i+1),
        value:r[idx[numCol]]||0,
        phys:labCol}));
      /* 상위 밖은 버리지 않고 합쳐 보인다 — 조용한 절단 금지 */
      if(rows.length>10){
        const rest=rows.slice(10).reduce((a,r)=>a+(r[idx[numCol]]||0),0);
        top.push({label:`그 외 ${rows.length-10}건`,value:rest,tone:'warn'});
      }
      blk.appendChild(barList(top));
    } else if(viz==='line'&&numCol){
      blk.appendChild(blkHead('추이',`${title} · ${lab(numCol)}`,numCol));
      if(numFallback)blk.appendChild(el('div','meta',
        `값 열이 문장에 없어 이 View의 기본 값 열(${lab(numCol)})로 그렸다`));
      blk.appendChild(areaLine(rows.map(r=>r[idx[numCol]]||0).slice(0,60),
        {label:lab(numCol)}));
    } else if((viz==='bar'||viz==='line')&&!numCol){
      /* 숫자 열이 안 잡혔는데 차트를 조용히 표로 바꾸면 사용자는 요청이
         무시된 줄 모른다 — 무엇이 빠졌고 어떻게 고치는지 그 자리에 적는다. */
      blk.appendChild(blkHead(viz==='bar'?'막대':'추이',title||''));
      blk.appendChild(el('div','note',
        (viz==='bar'?'막대차트':'추이')+'는 숫자 열이 필요하다 — 문장에 값 열'+
        '(예: '+v.fields.filter(f=>f.permitted&&f.masking==='none')
          .slice(0,3).map(f=>f.korean).join(' · ')+')을 함께 적으면 그린다.'));
      blk.classList.add('viz-table');
    } else {
      blk.appendChild(blkHead('표',title||'검토 표'));
      blk.appendChild(table(sub));
      blk.classList.add('viz-table');
    }
    grid.appendChild(blk);
  });
  box.appendChild(grid);
  box.appendChild(el('div','meta',
    `원장 ${v.table_ref} · 화면 내 ${frame.shown.toLocaleString()}행`+
    (frame.shown<frame.total?` (모집단 ${frame.total.toLocaleString()}행 중)`:' 전량')+
    ` · 정렬 ${numCol?lab(numCol)+' 내림차순':'원장 순'}`));
}

function sparkline(values, title, phys){
  const w=680,h=120,pad=6;
  const max=Math.max(...values,0),min=Math.min(...values,0);
  const span=(max-min)||1;
  const pts=values.slice(0,60).map((v,i,arr)=>{
    const x=pad+i*(w-2*pad)/Math.max(arr.length-1,1);
    const y=h-pad-((v-min)/span)*(h-2*pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`}).join(' ');
  const box=el('div');
  const mt=el('div','meta',title);if(phys)mt.title=phys;
  box.appendChild(mt);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  svg.setAttribute('class','spark');
  const pl=document.createElementNS(ns,'polyline');
  pl.setAttribute('points',pts);
  pl.setAttribute('fill','none');
  pl.setAttribute('stroke','var(--accent)');
  pl.setAttribute('stroke-width','2');
  svg.appendChild(pl);box.appendChild(svg);
  return box;
}


/* ---- E 위기상황: 심각도별 전 단계 산출과정 ---- */
const TRACE_BLOCKS=['거시','충격축','신용파라미터','신용RWA','시장','은행계정금리',
  '운영','유동성','손익','자본','RWA합계','비율','판정'];

function traceRows(){
  const f=D.data['st_calc_trace'];
  if(!f)return null;
  const i={};f.columns.forEach((c,k)=>{i[c]=k});
  return {f,i};
}
function stressDeepDive(root){
  const T=traceRows();
  if(!T){root.appendChild(el('div','note','추적표가 없다.'));return}
  const {f,i}=T;
  root.appendChild(el('p','lead',
    '14개 충격 축(신용 5 · 시장 4 · 운영 1 · 유동성 2 · 수익 2)이 같은 심도에서 동시에 발동하고, '+
    '신용파라미터 → 신용RWA → 시장 → 은행계정금리 → 운영 → 유동성 → 손익 → 자본 → RWA합계 → '+
    '비율 → 판정으로 전이되는 전 과정을 심각도별·분기별로 펼친다. 각 단계는 산식·투입값·규정 '+
    '근거를 함께 가지며, 마지막 단계 값은 스트레스 경로 결과와 정확히 일치한다.'));

  const scenarios=[...new Set(f.rows.map(r=>r[i.scenario]))];
  const quarters=[...new Set(f.rows.map(r=>r[i.quarter]))];
  let scenario=scenarios[scenarios.length-1], quarter=quarters[0];
  const collapsed=new Set();

  /* 저점 분기 = 선택 시나리오의 보통주자본비율 최솟값 분기 */
  function troughQuarter(sc){
    let best=null,bv=Infinity;
    f.rows.forEach(r=>{
      if(r[i.scenario]===sc&&r[i.step]==='보통주자본비율'&&r[i.value]<bv){
        bv=r[i.value];best=r[i.quarter]}});
    return best;
  }
  quarter=troughQuarter(scenario)||quarters[0];

  const bar=el('div','toolbar');
  const scBox=el('div','chips');
  scenarios.forEach(sc=>{const b=el('button','chip',sc);
    b.onclick=()=>{scenario=sc;quarter=troughQuarter(sc)||quarters[0];draw()};
    scBox.appendChild(b)});
  const qsel=el('select','sel');
  quarters.forEach(q=>{const o=el('option');o.value=q;o.textContent=q;qsel.appendChild(o)});
  qsel.onchange=()=>{quarter=qsel.value;draw()};
  const btnTrough=el('button','btn','저점 분기로');
  btnTrough.onclick=()=>{quarter=troughQuarter(scenario);draw()};
  bar.appendChild(scBox);bar.appendChild(qsel);bar.appendChild(btnTrough);
  root.appendChild(bar);

  const pane=el('div');root.appendChild(pane);

  function pick(sc,q,step){
    const r=f.rows.find(x=>x[i.scenario]===sc&&x[i.quarter]===q&&x[i.step]===step);
    return r?r[i.value]:null;
  }
  function fmtUnit(v,u){
    if(v===null)return '—';
    if(u==='ratio')return (v*100).toFixed(4)+'%';
    if(u==='count')return fmtNum(v);
    return fmtNum(v);
  }

  function draw(){
    [...scBox.children].forEach(b=>b.classList.toggle('on',b.textContent===scenario));
    qsel.value=quarter;
    pane.innerHTML='';

    /* --- 심각도 비교: 같은 분기, 모든 시나리오 --- */
    const cmp=el('div','card');
    cmp.appendChild(el('h3',null,`심각도 비교 · ${quarter}`));
    /* 비율 열은 %로 환산해 둔다 — 0.0819를 그대로 두면 금액 열과 자릿수가
       섞여 읽히지 않는다. 열 이름에 단위를 박아 오해를 없앤다. */
    const pc=v=>v===null?null:v*100;
    cmp.appendChild(table({
      columns:['시나리오','충격 심도','PD(충격) %','LGD(충격) %','충당금 전입',
               '트레이딩 손익','운영손실','당기순이익','RWA 합계','LCR %',
               'CET1 %','총자본비율 %','요구치 충족'],
      rows:scenarios.map(sc=>[sc,
        pick(sc,quarter,'충격 심도 (severity)'),
        pc(pick(sc,quarter,'PD (충격 후)')),
        pc(pick(sc,quarter,'LGD (충격 후)')),
        pick(sc,quarter,'충당금 전입'),
        pick(sc,quarter,'트레이딩 손익 합계'),
        pick(sc,quarter,'운영손실 (연간)'),
        pick(sc,quarter,'당기순이익'),
        pick(sc,quarter,'위험가중자산 합계'),
        pc(pick(sc,quarter,'유동성커버리지비율')),
        pc(pick(sc,quarter,'보통주자본비율')),
        pc(pick(sc,quarter,'총자본비율')),
        pick(sc,quarter,'요구치 충족')===1?'충족':'침범']),
      total:scenarios.length,shown:scenarios.length}));
    pane.appendChild(cmp);

    /* --- CET1 경로: 시나리오별 --- */
    const path=el('div','card');
    path.appendChild(el('h3',null,'보통주자본비율 경로 · 심각도별'));
    const series=scenarios.map(sc=>({name:sc,
      values:quarters.map(q=>pick(sc,q,'보통주자본비율'))}));
    const req=pick(scenario,quarter,'보통주자본 요구비율');
    path.appendChild(multiLine(series,quarters,req));
    pane.appendChild(path);

    /* --- 전 단계 워터폴 --- */
    const steps=f.rows.filter(r=>r[i.scenario]===scenario&&r[i.quarter]===quarter)
                      .sort((a,b)=>a[i.seq]-b[i.seq]);
    TRACE_BLOCKS.forEach(bk=>{
      const rows=steps.filter(r=>r[i.block]===bk);
      if(!rows.length)return;
      const c=el('div','card');
      const h=el('button','blockhead');
      h.appendChild(el('span','bnum',String(TRACE_BLOCKS.indexOf(bk)+1).padStart(2,'0')));
      h.appendChild(document.createTextNode(' '+bk));
      h.appendChild(el('small',null,`${rows.length}단계`));
      const body=el('div');
      const open=!collapsed.has(bk);
      h.onclick=()=>{collapsed.has(bk)?collapsed.delete(bk):collapsed.add(bk);draw()};
      c.appendChild(h);
      if(open){
        body.appendChild(table({
          columns:['#','단계','산출값','단위','산식','투입값','근거'],
          rows:rows.map(r=>[r[i.seq],r[i.step],
            fmtUnit(r[i.value],r[i.unit]),r[i.unit],r[i.formula],
            r[i.inputs],r[i.citation]]),
          total:rows.length,shown:rows.length},{numeric:false}));
        c.appendChild(body);
      }
      pane.appendChild(c);
    });

    const note=el('div','note',
      '14개 충격 축(신용 5 · 시장 4 · 운영 1 · 유동성 2 · 수익 2)이 같은 심도에서 동시에 발동한다. '+
      '자본은 증분 ECL이 아니라 세후이익 변화로 롤포워드되며(충당금이 이익에 이미 들어 있다), '+
      '산출하한 분모도 함께 충격받는다. 추적표의 값은 스트레스 경로 결과와 정확히 일치한다.');
    pane.appendChild(note);
  }
  draw();
}

function multiLine(series, labels, threshold){
  const w=900,h=240,padL=56,padR=10,padT=12,padB=26;
  const all=series.flatMap(s=>s.values).filter(v=>v!==null);
  if(threshold!==null&&threshold!==undefined)all.push(threshold);
  const max=Math.max(...all),min=Math.min(...all);
  const span=(max-min)||1;
  const x=k=>padL+k*(w-padL-padR)/Math.max(labels.length-1,1);
  const y=v=>h-padB-((v-min)/span)*(h-padT-padB);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  svg.setAttribute('class','spark');
  svg.style.height='240px';
  /* ok·watch·danger·engine — 상태 3색 + 엔진 파랑 (v9.5.0 역할 팔레트) */
  const colors=['#44d19d','#f6bb56','#fb6472','#42a9ff'];
  if(threshold!==null&&threshold!==undefined){
    const l=document.createElementNS(ns,'line');
    l.setAttribute('x1',padL);l.setAttribute('x2',w-padR);
    l.setAttribute('y1',y(threshold));l.setAttribute('y2',y(threshold));
    l.setAttribute('stroke','currentColor');l.setAttribute('stroke-dasharray','4 3');
    l.setAttribute('opacity','.5');svg.appendChild(l);
    const t=document.createElementNS(ns,'text');
    t.setAttribute('x',padL);t.setAttribute('y',y(threshold)-4);
    t.setAttribute('fill','currentColor');t.setAttribute('font-size','10');
    t.setAttribute('opacity','.7');
    t.textContent=`요구 ${(threshold*100).toFixed(2)}%`;svg.appendChild(t);
  }
  series.forEach((s,si)=>{
    const pts=s.values.map((v,k)=>v===null?null:`${x(k)},${y(v)}`)
                      .filter(Boolean).join(' ');
    const pl=document.createElementNS(ns,'polyline');
    pl.setAttribute('points',pts);pl.setAttribute('fill','none');
    pl.setAttribute('stroke',colors[si%colors.length]);
    pl.setAttribute('stroke-width','2');svg.appendChild(pl);
    const t=document.createElementNS(ns,'text');
    t.setAttribute('x',w-padR);t.setAttribute('y',y(s.values[s.values.length-1])-4);
    t.setAttribute('text-anchor','end');t.setAttribute('font-size','10');
    t.setAttribute('fill',colors[si%colors.length]);
    t.textContent=s.name;svg.appendChild(t);
  });
  labels.forEach((lb,k)=>{
    if(k%2)return;
    const t=document.createElementNS(ns,'text');
    t.setAttribute('x',x(k));t.setAttribute('y',h-8);
    t.setAttribute('text-anchor','middle');t.setAttribute('font-size','9');
    t.setAttribute('fill','currentColor');t.setAttribute('opacity','.6');
    t.textContent=lb;svg.appendChild(t);
  });
  const box=el('div');box.appendChild(svg);return box;
}

/* ---- 부문 뷰 ---- */
function domain(root, product, title, lead){
  root.appendChild(el('p','lead',lead));
  /* 캡처(v9.5.0)식 분석 모듈 — 이 부문 원장이 payload에 있으면 그린다 */
  if(DOMAIN_CHARTS[product])DOMAIN_CHARTS[product](root);
  const wrap=el('div','split');
  const list=el('div','list');const pane=el('div');
  const rows=D.catalog.filter(r=>r.product===product);
  rows.forEach((r,i)=>{
    const b=el('button');b.appendChild(document.createTextNode(r.korean));
    b.appendChild(el('small',null,`${r.name} · ${r.rows.toLocaleString()}행 · ${r.columns}열`));
    b.onclick=()=>{[...list.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');renderTable(pane,r)};
    list.appendChild(b);
    if(i===0){b.classList.add('on');renderTable(pane,r)}
  });
  wrap.appendChild(list);wrap.appendChild(pane);root.appendChild(wrap);
}
function renderTable(pane,r){
  pane.innerHTML='';
  const c=el('div','card');
  c.appendChild(el('h3',null,`${r.korean} · ${r.name}`));
  c.appendChild(el('div','meta',`입도 — ${r.grain}`));
  c.appendChild(el('div','meta',`기본키 ${r.pk} · 외래키 ${r.fk}개 · 컬럼 ${r.columns}개`));
  const f=D.previews[r.name];
  if(f)c.appendChild(table(f));else c.appendChild(el('div','note','미실체화 테이블'));
  pane.appendChild(c);
}

/* ---- 감독보고 ---- */
function regulatory(root){
  root.appendChild(el('p','lead',
    '금융감독원 배포 기준 업무보고서. 라인마다 산식·규정근거·산출 모듈을 함께 남긴다. '+
    '서식 식별자(BR-01…)는 내부 코드이며 배포본 서식번호와의 매핑이 필요하다.'));
  const wrap=el('div','split');
  const list=el('div','list');const pane=el('div');
  let sec=null;
  D.forms.forEach((f,i)=>{
    if(f.section!==sec){sec=f.section;list.appendChild(el('div','listsec',sec))}
    const b=el('button');b.appendChild(document.createTextNode(`${f.form_no} ${f.form_name}`));
    b.appendChild(el('small',null,`${f.form_id} · ${f.frequency} · ${f.n_lines}행 · 검증 ${f.n_checks}건 실패 ${f.n_failed}`));
    b.onclick=()=>{[...list.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');renderForm(pane,f)};
    list.appendChild(b);
    if(i===0){b.classList.add('on');renderForm(pane,f)}
  });
  wrap.appendChild(list);wrap.appendChild(pane);root.appendChild(wrap);
  const c=el('div','card');c.appendChild(el('h3',null,'서식 자체 대사'));
  c.appendChild(table(D.form_checks,{rowClass:r=>r[6]==='FAIL'?'bad':null}));
  root.appendChild(c);
}
function renderForm(pane,f){
  pane.innerHTML='';
  const c=el('div','card');
  c.appendChild(el('h3',null,`[${f.form_no}] ${f.form_name}`));
  c.appendChild(el('div','meta',`${f.section} · 내부 ID ${f.form_id} · 제출주기 ${f.frequency} · 근거 ${f.citation}`));
  if(!f.official)c.appendChild(el('div','note',
    '서식번호는 내부 배정 코드다 — 금감원 배포본 서식번호 확보 후 대조가 필요하다.'));
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['라인','항목명','단위','값','산식','규정 근거'].forEach(x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  f.lines.forEach(ln=>{
    const x=el('tr',ln.subtotal?'sub':null);
    x.appendChild(el('td',null,ln.code));
    x.appendChild(el('td',null,' '.repeat(ln.level*4)+ln.name));
    x.appendChild(el('td',null,ln.unit));
    let v=ln.value;
    if(ln.unit==='ratio'&&typeof v==='number')v=(v*100).toFixed(4)+'%';
    else if(typeof v==='number')v=fmtNum(v);
    x.appendChild(el('td','num',v==null?'—':v));
    x.appendChild(el('td',null,ln.formula));
    x.appendChild(el('td',null,ln.citation));
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);
  pane.appendChild(c);
}

/* ---- 검증 · 에이전트 · 변경 · 카탈로그 ---- */
function validation(root){
  root.appendChild(el('p','lead',
    '검증은 두 층이다. 자체검증(2선)은 같은 코드·같은 가정으로 점검하고, 상시 독립검증(3선)은 '+
    '개발조직과 분리된 적합성검증 팀에이전트가 다시 계산한다. 2선 PASS만으로는 결재할 수 없다.'));

  /* --- 3선 게이트 --- */
  const iv=D.independent;
  const g=el('div','card');
  g.appendChild(el('h3',null,'상시 독립검증 (3선) — 게이트'));
  const tone=iv.status==='적합'?'good':iv.status==='부적합'?'bad':'warn';
  const kg=el('div','grid');
  [['게이트 상태',iv.status,tone],['요청 식별자',iv.request_id,''],
   ['수신 팀',iv.requested_to,''],['수신 브랜치',iv.branch,''],
   ['재계산 대상',iv.n_targets+'종',''],
   ['자체검증(2선)',iv.self_validation,'']].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+(t||''),String(v)));
    kg.appendChild(c)});
  g.appendChild(kg);
  g.appendChild(el('div','note',
    '이 판정은 화면을 산출한 실행 시점의 스냅샷이다. 이후 도착한 3선 응답이나 '+
    '판정 변경은 이 화면에 반영되지 않는다 — 현재 상태의 정본은 저장소 게이트'+
    '(check_gate)다.'));
  g.appendChild(el('div','note',iv.reason+
    ' — 게이트는 fail-closed다. 응답이 없으면 통과가 아니라 대기이며 결재 상신이 막힌다. '+
    '판정이 경부적합이면 상태는 조건부이며, 결재 책임자가 잔여위험·후속조건·이행기한·'+
    '배포 범위를 기록해야만 통과한다 — 조건부는 적합이 아니다.'));
  g.appendChild(el('h3',null,'독립 재계산 대상'));
  g.appendChild(table(D.independent_targets));
  g.appendChild(el('h3',null,'3선이 도전해야 할 가정'));
  const ul=el('div');
  iv.assumptions.forEach((a,i)=>{const d=el('div','meta','· '+a);ul.appendChild(d)});
  g.appendChild(ul);
  root.appendChild(g);

  const c=el('div','card');
  c.appendChild(el('h3',null,'자체검증 (2선) 결과 — 같은 코드·같은 가정'));
  c.appendChild(table(D.validation,{rowClass:r=>r[2]==='FAIL'?'bad':null}));
  root.appendChild(c);
}
function agents(root){
  root.appendChild(el('p','lead',
    '계획·등록도구·데이터범위·승인·로그를 확인한다. 사람의 승인을 받기 전 에이전트는 조회 전용 또는 제안 전용이며, '+
    '운영 반영 권한(write_allowed)은 전 에이전트가 거짓이다 — NO AUTONOMOUS WRITE.'));
  const a=el('div','card');a.appendChild(el('h3',null,'에이전트 레지스트리 · 최소 권한'));
  a.appendChild(table(D.agents));root.appendChild(a);
  const b=el('div','card');b.appendChild(el('h3',null,'활동 원장 — 주체·도구·출력·게이트'));
  b.appendChild(table(D.activity));root.appendChild(b);
  const k=el('div','card');k.appendChild(el('h3',null,'범위형 비상정지 이력'));
  k.appendChild(table(D.killswitch));
  k.appendChild(el('div','note',
    '안전중지는 진행 중 결정론적 계산을 마치고 신규 도구 호출을 차단한다. 중요 범위는 독립된 2차 확인이 필요하다.'));
  root.appendChild(k);
}
function changes(root){
  root.appendChild(el('p','lead',
    '신규 익스포저·상품·규정·데이터 변경의 영향을 분석하고 계산·보고서를 매핑하며 통제된 브랜치와 테스트를 작성한다 — 자동배포하지 않는다.'));
  [['변경 요청',D.changes],['영향도 맵 · 데이터→산식→보고→담당자',D.change_impacts],
   ['회귀테스트 매트릭스',D.change_tests]].forEach(([t,f])=>{
    const c=el('div','card');c.appendChild(el('h3',null,t));
    c.appendChild(table(f));root.appendChild(c)});
  const m=el('div','card');m.appendChild(el('h3',null,'표준코드 매핑 — 미매핑은 산출 누락으로 직결'));
  m.appendChild(table(D.canonical_map));root.appendChild(m);
}
function catalogView(root){
  root.appendChild(el('p','lead',
    `정규 테이블 ${D.meta.n_tables}장 · 컬럼 ${D.meta.n_columns}개 · 실체화 행 ${D.meta.n_rows.toLocaleString()}행. `+
    '각 View의 필드 권한과 마스킹 정책이 조회 가능 범위를 결정한다.'));
  const sel=el('select','sel');
  const opt=el('option');opt.value='';opt.textContent='전체 부문';sel.appendChild(opt);
  D.domains.forEach(d=>{const o=el('option');o.value=d;o.textContent=d;sel.appendChild(o)});
  root.appendChild(sel);
  const c=el('div','card');root.appendChild(c);
  const draw=()=>{c.innerHTML='';
    const rows=D.catalog.filter(r=>!sel.value||r.product===sel.value);
    c.appendChild(el('h3',null,`테이블 ${rows.length}장`));
    c.appendChild(table({columns:['테이블','한글명','부문','입도','컬럼','기본키','FK','행'],
      rows:rows.map(r=>[r.name,r.korean,r.product,r.grain,r.columns,r.pk,r.fk,r.rows]),
      total:rows.length,shown:rows.length}))};
  sel.onchange=draw;draw();
  const p=el('div','card');p.appendChild(el('h3',null,'승인 View 원장'));
  p.appendChild(table(D.views));root.appendChild(p);
}

/* ---- ⚙ 설정 ----
   설정 화면의 원칙: **화면은 계산기가 아니다.** 표시명·기준일 전환은 세션
   안에서 즉시 적용되지만(산출값 무관), 서식번호 매핑·시나리오 파라미터는
   산출물의 정체를 바꾸므로 화면에서 적용하지 않는다 — 변경 제안서를 만들어
   주고, 적용은 코드 반영 + 파이프라인 재실행(2선 자체검증 + 3선 재요청)으로만
   이뤄진다. 화면에서 바꾼 값이 제출 지문과 다른 수치를 그리는 순간 그 화면은
   산출물이 아니라 조작이 된다. */

function runRegistry(root){
  const c=el('div','card set-runs');
  c.appendChild(el('h3',null,'실은 실행 (기준일 전환 대상)'));
  c.appendChild(el('div','meta',
    '기준일 전환은 미리 산출해 실은 실행 사이의 전환이다. 새 기준일은 '+
    'run_pipeline 재실행으로만 생긴다 — 화면이 즉석에서 만들 수 없다. '+
    '게이트 열은 각 실행을 산출한 시점의 스냅샷이며, 이후 3선 응답은 '+
    '반영되지 않는다.'));
  c.appendChild(table({columns:['기준일','실행 ID','산출 지문','시드',
      '3선 요청','게이트','자체검증(2선)'],
    rows:Object.keys(RUNS).sort().map(a=>{const r=RUNS[a];
      return [a,r.meta.run_id,r.meta.digest.slice(0,12),r.meta.seed,
        r.independent.request_id,r.independent.status,
        r.independent.self_validation]}),
    total:Object.keys(RUNS).length,shown:Object.keys(RUNS).length},
    {numeric:false}));
  root.appendChild(c);
}

function labelSettings(root){
  const c=el('div','card set-labels');
  c.appendChild(el('h3',null,'컬럼 표시명 매핑'));
  c.appendChild(el('div','meta',
    '정본은 데이터모델 카탈로그(ColumnSpec.korean)다. 여기서 바꾼 표시명은 이 '+
    '세션의 화면에만 적용되며, 영구 반영은 카탈로그 수정으로 한다. 물리명은 '+
    '항상 열 머리글 툴팁으로 남는다.'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  Object.keys(D.data).sort().forEach(t=>{const o=el('option');
    o.value=t;o.textContent=t;sel.appendChild(o)});
  bar.appendChild(sel);c.appendChild(bar);
  const pane=el('div');c.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const f=D.data[sel.value];
    const ovr=STATE.labelOverrides[sel.value]||{};
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    ['물리명','카탈로그 표시명','세션 재정의'].forEach(x=>tr.appendChild(el('th',null,x)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody'), inputs={};
    f.columns.forEach((cName,i)=>{
      const x=el('tr');
      x.appendChild(el('td','mono',cName));
      x.appendChild(el('td',null,(f.labels&&f.labels[i])||'—'));
      const td=el('td');
      const inp=el('input','input');inp.type='text';
      inp.value=ovr[cName]||'';inp.placeholder='(카탈로그 표시명 사용)';
      inp.style.minWidth='140px';
      inputs[cName]=inp;td.appendChild(inp);x.appendChild(td);
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);pane.appendChild(w);
    const acts=el('div','toolbar');
    const apply=el('button','btn primary','세션에 적용');
    const reset=el('button','btn','재정의 지우기');
    apply.onclick=()=>{
      const m={};
      Object.entries(inputs).forEach(([k,inp])=>{
        const v=inp.value.trim();if(v)m[k]=v});
      if(Object.keys(m).length)STATE.labelOverrides[sel.value]=m;
      else delete STATE.labelOverrides[sel.value];
      repaintAll();};
    reset.onclick=()=>{delete STATE.labelOverrides[sel.value];repaintAll();};
    acts.appendChild(apply);acts.appendChild(reset);pane.appendChild(acts);
  }
  sel.onchange=draw;draw();
  root.appendChild(c);
}

/* FINES 서식번호 형식 — 배포 코드는 B/BA/BF + 숫자 3~5자리(+ -가지번호),
   내부 관리 서식은 RM-####. 마스터(fss_master)의 실존 형식에서 온 규칙이다 —
   B10101(금리인하요구권)·B11101~07(투자자문업)처럼 5자리 숫자부가 실재하므로
   4자리로 자르면 실코드 9종이 형식 위반으로 거부된다. */
const FORM_NO_RE=/^(?:B[AF]?\d{3,5}(?:-\d+)?|RM-\d{4})$/;
/* 중복 비교는 표시문자열이 아니라 코드로 한다 — 내부관리 서식의 form_no는
   "RM-6401 (내부관리)"처럼 접미사가 붙어, 그대로 키로 쓰면 "RM-6401" 입력이
   중복 검사를 지나간다. */
const formNoKey=s=>String(s).split(' ')[0];

function formMapSettings(root){
  const c=el('div','card set-formmap');
  c.appendChild(el('h3',null,'서식번호 매핑 — 내부 코드 ↔ 금감원 배포 서식번호'));
  c.appendChild(el('div','meta',
    '서식번호는 제출본의 정체다. 여기서는 매핑 변경을 **제안서로만** 만든다 — '+
    '적용은 risk_lib/regulatory/form_ids.py 반영 후 파이프라인 재실행으로만 '+
    '이뤄지며, 화면이 즉석에서 바꾸면 제출 지문과 어긋난 화면이 된다.'));
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['내부 코드','서식명','현행 서식번호','배포본 확정','변경 제안'].forEach(
    x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody'), inputs={};
  D.forms.forEach(f=>{
    const x=el('tr');
    x.appendChild(el('td','mono',f.form_id));
    x.appendChild(el('td',null,f.form_name));
    x.appendChild(el('td','mono',f.form_no));
    const td0=el('td');td0.appendChild(pill(f.official?'확정':'내부 배정',
      f.official?'good':'warn'));x.appendChild(td0);
    const td=el('td');
    const inp=el('input','input');inp.type='text';inp.placeholder='(유지)';
    inp.style.minWidth='110px';inputs[f.form_id]=inp;
    td.appendChild(inp);x.appendChild(td);
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);

  const acts=el('div','toolbar');
  const gen=el('button','btn primary','변경 제안 생성');
  acts.appendChild(gen);c.appendChild(acts);
  const err=el('div','note bad');err.hidden=true;c.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed){err.textContent='비상정지 중 — 변경 제안을 만들지 않는다.';
      err.hidden=false;return}
    const changes=[],bad=[];
    const used={};D.forms.forEach(f=>{used[formNoKey(f.form_no)]=f.form_id});
    Object.entries(inputs).forEach(([fid,inp])=>{
      const v=inp.value.trim();if(!v)return;
      if(!FORM_NO_RE.test(v)){bad.push(`${fid}: '${v}' — 형식 위반 (B/BA/BF+숫자(-가지) 또는 RM-####)`);return}
      if(used[formNoKey(v)]&&used[formNoKey(v)]!==fid){bad.push(`${fid}: '${v}' — ${used[formNoKey(v)]}가 이미 사용`);return}
      const cur=D.forms.find(f=>f.form_id===fid);
      used[formNoKey(v)]=fid;       /* 제안값끼리의 충돌도 잡는다 */
      changes.push({form_id:fid,from:cur.form_no,to:v})});
    if(bad.length){err.textContent='검증 실패 '+bad.length+'건 — '+bad.join(' · ');
      err.hidden=false;return}
    if(!changes.length){err.textContent='변경된 행이 없다.';err.hidden=false;return}
    out.textContent=JSON.stringify({
      proposal:'서식번호 매핑 변경',asof:D.meta.asof,run_id:D.meta.run_id,
      changes,
      apply_path:'risk_lib/regulatory/form_ids.py',
      procedure:['코드 반영','파이프라인 재실행','자체검증(2선) FAIL 0 확인',
                 '독립검증(3선) 재요청','게이트 통과 후 결재'],
      note:'화면에는 적용되지 않는다 — 제출 지문이 걸린 값이다.'},null,2);
  };
  root.appendChild(c);
}

function scenarioSettings(root){
  const T=traceRows();
  const c=el('div','card set-scenario');
  c.appendChild(el('h3',null,'위기상황 시나리오 설정 — 충격 축 파라미터'));
  c.appendChild(el('div','meta',
    '충격 축 14종의 단위충격 × 심도 구조를 편집해 **변경 제안서**를 만든다. '+
    '화면은 재계산하지 않는다 — 시나리오 파라미터는 RWA·비율·판정 전체에 '+
    '전이되므로, 적용은 파이프라인 재실행과 검증 두 층을 다시 거쳐야 한다.'));
  if(!T){c.appendChild(el('div','note','추적표가 없다.'));root.appendChild(c);return}
  const {f,i}=T;
  const scenarios=[...new Set(f.rows.map(r=>r[i.scenario]))];
  /* 축별 단위충격은 산식 문자열('심도 × 단위충격(0.05 ratio)')에서 읽는다 —
     추적표가 정본이고, 여기 따로 적으면 두 벌이 갈라진다. */
  const axes=[];const seen=new Set();
  f.rows.forEach(r=>{
    if(r[i.block]!=='충격축'||seen.has(r[i.step]))return;
    seen.add(r[i.step]);
    const m=/단위충격\(([-\d.]+)\s*(\S+)\)/.exec(r[i.formula]||'');
    axes.push({step:r[i.step],unit:m?m[2]:r[i.unit],base:m?parseFloat(m[1]):null})});
  /* 심도는 분기마다 다르고 정점까지 선형 상승한다 — 첫 행(1분기)을 집으면
     시나리오 정의 심도를 최대 4~5배 과소 표기한다. 검토자가 단위충격 × 심도로
     정점 충격을 어림하는 화면이므로 **정점(최대) 심도**를 뽑는다. */
  const sever={};
  scenarios.forEach(sc=>{
    let mx=null;
    f.rows.forEach(x=>{
      if(x[i.scenario]===sc&&/심도/.test(x[i.step])&&typeof x[i.value]==='number')
        mx=mx===null?x[i.value]:Math.max(mx,x[i.value])});
    sever[sc]=mx});

  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['충격 축','단위','현행 단위충격','제안 단위충격'].forEach(
    x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody'),inputs={};
  axes.forEach(a=>{
    const x=el('tr');
    x.appendChild(el('td',null,a.step));
    x.appendChild(el('td','mono',a.unit));
    x.appendChild(el('td','num',a.base===null?'—':String(a.base)));
    const td=el('td');
    const inp=el('input','input');inp.type='text';inp.placeholder='(유지)';
    inp.style.minWidth='90px';inputs[a.step]=inp;
    td.appendChild(inp);x.appendChild(td);tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);
  c.appendChild(el('div','meta','시나리오별 정점 심도 — '+scenarios.map(
    sc=>`${sc} ${sever[sc]===null?'—':sever[sc]}`).join(' · ')+
    ' (분기별 심도는 정점까지 선형 상승)'));

  const acts=el('div','toolbar');
  const gen=el('button','btn primary','변경 제안 생성');
  acts.appendChild(gen);c.appendChild(acts);
  const err=el('div','note bad');err.hidden=true;c.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed){err.textContent='비상정지 중 — 변경 제안을 만들지 않는다.';
      err.hidden=false;return}
    const changes=[],bad=[];
    Object.entries(inputs).forEach(([step,inp])=>{
      const v=inp.value.trim();if(!v)return;
      if(!/^-?\d+(?:\.\d+)?$/.test(v)){bad.push(`${step}: '${v}' — 숫자가 아니다`);return}
      const cur=axes.find(a=>a.step===step);
      changes.push({axis:step,unit:cur.unit,from:cur.base,to:parseFloat(v)})});
    if(bad.length){err.textContent='검증 실패 — '+bad.join(' · ');
      err.hidden=false;return}
    if(!changes.length){err.textContent='변경된 축이 없다.';err.hidden=false;return}
    out.textContent=JSON.stringify({
      proposal:'위기상황 시나리오 충격 축 변경',asof:D.meta.asof,
      run_id:D.meta.run_id,changes,
      impact:['신용파라미터→신용RWA→시장→은행계정금리→운영→유동성→손익→자본→비율→판정 전 단계',
              '업무보고서 위기상황 서식','자본계획·회복계획 연계 경보'],
      apply_path:'risk_lib/stress/axes.py (충격 축 · 심도 정의)',
      procedure:['코드 반영','파이프라인 재실행','자체검증(2선) FAIL 0 확인',
                 '독립검증(3선) 재요청','게이트 통과 후 결재'],
      note:'화면은 재계산하지 않는다 — 이 제안은 입력이지 산출이 아니다.'},null,2);
  };
  root.appendChild(c);
}

/* ---- 요건 추적 — v9.6.0 BRD 131건 대비 구현 재고조사 ---- */
function reqTrace(root){
  const R=D.req_trace;
  root.appendChild(el('p','lead',
    'RYNTA v9.6.0 업무요건정의서 Level 1 요건 131건을 이 하네스의 실재 증빙'+
    '(모듈·원장·화면·테스트)에 대조한다. 증빙 참조는 테스트가 실재를 검증하므로 '+
    '여기 뜨는 상태는 주장이 아니라 검사를 통과한 목록이다. 미반영은 숨기지 '+
    '않는다 — 커버리지는 자랑이 아니라 재고조사다.'));

  const c0=el('div','card');
  c0.appendChild(el('h3',null,'커버리지 — '+R.coverage.source));
  const g=el('div','grid');
  [['반영',R.coverage['반영'],'good'],['부분',R.coverage['부분'],'warn'],
   ['미반영',R.coverage['미반영'],'bad'],
   ['검증된 증빙 참조',R.coverage.n_evidence,'']].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+t,String(v)));
    if(k!=='검증된 증빙 참조')
      c.appendChild(el('div','sub',(v/R.coverage.n*100).toFixed(0)+'% / '+R.coverage.n+'건'));
    g.appendChild(c)});
  c0.appendChild(g);
  c0.appendChild(meter('반영(부분 포함 안 함)',R.coverage['반영'],R.coverage.n));
  c0.appendChild(el('div','meta','원문 SHA-256 '+R.coverage.source_sha256.slice(0,16)+
    '… — 레지스터는 tools/gen_requirements.py 가 원문에서 생성한다'));
  root.appendChild(c0);

  const bar=el('div','toolbar');
  const fSt=el('select','sel');
  ['전체 상태','반영','부분','미반영'].forEach(x=>{const o=el('option');
    o.value=x==='전체 상태'?'':x;o.textContent=x;fSt.appendChild(o)});
  const fPr=el('select','sel');
  ['전체 영역'].concat([...new Set(R.rows.map(r=>r.id.split('-')[0]))].sort())
    .forEach(x=>{const o=el('option');o.value=x==='전체 영역'?'':x;
      o.textContent=x;fPr.appendChild(o)});
  const q=el('input','input');q.type='text';q.placeholder='ID·제목 검색';
  bar.appendChild(fSt);bar.appendChild(fPr);bar.appendChild(q);
  root.appendChild(bar);

  const pane=el('div','card');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const kw=q.value.trim().toLowerCase();
    const rows=R.rows.filter(r=>
      (!fSt.value||r.status===fSt.value)&&
      (!fPr.value||r.id.startsWith(fPr.value+'-'))&&
      (!kw||(r.id+' '+r.title).toLowerCase().includes(kw)));
    pane.appendChild(el('h3',null,`요건 ${rows.length}건`));
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    ['요건','업권','우선순위','상태','증빙 (검증됨)','비고'].forEach(
      x=>tr.appendChild(el('th',null,x)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody');
    rows.forEach(r=>{
      const x=el('tr');
      const td0=el('td');td0.appendChild(el('div','mono',r.id));
      td0.appendChild(el('div',null,r.title));x.appendChild(td0);
      x.appendChild(el('td',null,r.sector));
      x.appendChild(el('td',null,r.priority));
      const td3=el('td');td3.appendChild(pill(r.status,
        r.status==='반영'?'good':r.status==='부분'?'warn':'bad'));
      x.appendChild(td3);
      const td4=el('td');
      r.evidence.forEach(e=>{
        const s=el('span','pill');s.style.marginRight='4px';
        s.textContent=e.kind+' · '+e.ref;s.title=e.kind;td4.appendChild(s)});
      if(!r.evidence.length)td4.appendChild(el('span','meta','—'));
      x.appendChild(td4);
      x.appendChild(el('td','meta',r.note||''));
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);pane.appendChild(w);
  }
  fSt.onchange=draw;fPr.onchange=draw;q.addEventListener('input',draw);
  draw();
}

/* ---- 오버레이 (인간 수정) — 기록 없는 조정은 재현 불가의 시작이다 ---- */
function overlay(root){
  root.appendChild(el('p','lead',
    '엔진 산출값을 사람이 덮어쓴 기록(수동조정 원장)과 새 오버레이 제안. 전 건이 '+
    '사유·증빙·승인자·만료일을 갖는다. 이 화면은 값을 바꾸지 않는다 — 제안서를 '+
    '만들고, 적용은 원장 등재 + 파이프라인 재실행 + 검증 두 층을 거친다.'));
  const f=D.adjustments;
  const c0=el('div','card');
  c0.appendChild(el('h3',null,'수동조정 원장'));
  c0.appendChild(table(f));c0.appendChild(srcMeta(f));
  root.appendChild(c0);

  const c=el('div','card set-overlay');
  c.appendChild(el('h3',null,'새 오버레이 제안'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  D.kpis.forEach(k=>{const o=el('option');o.value=k.label;
    o.textContent=k.label+' — 현재 '+k.value;sel.appendChild(o)});
  const val=el('input','input');val.type='text';val.placeholder='수정값';
  val.style.maxWidth='160px';
  const why=el('input','input');why.type='text';
  why.placeholder='사유 (필수) — 데이터 지연·일회성 사건·모형 한계 등';
  const ev=el('input','input');ev.type='text';
  ev.placeholder='증빙 참조 (필수) — 문서번호·티켓';ev.style.maxWidth='220px';
  bar.appendChild(sel);bar.appendChild(val);bar.appendChild(why);bar.appendChild(ev);
  c.appendChild(bar);
  const gen=el('button','btn primary','오버레이 제안 생성');
  c.appendChild(gen);
  const err=el('div','note bad');err.hidden=true;c.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed&&STATE.killScope==='전사'){
      err.textContent='비상정지 중 — 제안을 만들지 않는다.';err.hidden=false;return}
    if(!why.value.trim()||!ev.value.trim()){
      err.textContent='사유와 증빙 참조는 필수다 — 기록 없는 조정은 없다.';
      err.hidden=false;return}
    if(!val.value.trim()){err.textContent='수정값을 입력하라.';err.hidden=false;return}
    const k=D.kpis.find(x=>x.label===sel.value);
    out.textContent=JSON.stringify({
      proposal:'수동조정(오버레이)',asof:D.meta.asof,run_id:D.meta.run_id,
      target:k.label,engine_value:k.value,proposed_value:val.value.trim(),
      reason:why.value.trim(),evidence_ref:ev.value.trim(),
      apply_path:'risk_lib/adjustments.py (ManualAdjustment 등재)',
      procedure:['원장 등재(승인자·만료일 포함)','4-Eyes 승인',
                 '파이프라인 재실행','자체검증(2선)','독립검증(3선) 재요청'],
      note:'화면 값은 바뀌지 않는다 — 조정은 원장을 거쳐야 산출물이 된다.'},null,2);
  };
  root.appendChild(c);
}

/* ---- 코드 마스터 관리 — 코드그룹 / 코드 2단 구성 ----
   왼쪽은 코드그룹(코드셋) 목록과 그 속성, 오른쪽은 선택한 그룹의 코드 목록.
   그룹을 고르지 않고 코드만 나열하면 91개 코드셋 428행이 한 표에 섞여
   "어느 그룹의 코드인가"를 사람이 눈으로 세게 된다. */
function codeMasterAdmin(root){
  root.appendChild(el('p','lead',
    '정렬·표시의 정본(rdm_code_master)을 코드그룹 단위로 관리한다. 왼쪽에서 '+
    '그룹을 고르면 오른쪽에 그 그룹의 코드가 순서대로 뜬다. 순서 재정의는 이 '+
    '세션의 화면 정렬에 즉시 적용되고, 정본 변경은 카탈로그 수정 제안으로만 한다.'));
  const f=D.data['rdm_code_master'];
  const i=frameIdx(f);
  STATE.codeOverride=STATE.codeOverride||{};

  /* 그룹 요약 — 코드 수·출처 테이블·재정의 여부 */
  const groups={};
  f.rows.forEach(r=>{
    const g=r[i.code_set];
    (groups[g]=groups[g]||{n:0,src:new Set()});
    groups[g].n++;groups[g].src.add(r[i.source_table]);
  });
  const names=Object.keys(groups).sort();
  let sel=names[0];

  const wrap=el('div','split');
  const left=el('div','card set-codegroup');
  const right=el('div','card set-codemaster');
  wrap.appendChild(left);wrap.appendChild(right);
  root.appendChild(wrap);

  function drawGroups(){
    left.innerHTML='';
    left.appendChild(el('h3',null,`코드그룹 ${names.length}종`));
    const q=el('input','input');q.type='search';
    q.placeholder='그룹명 검색 (예: grade · status)';
    left.appendChild(q);
    const list=el('div','list');list.style.marginTop='8px';
    function fill(){
      list.innerHTML='';
      const kw=q.value.trim().toLowerCase();
      names.filter(g=>!kw||g.toLowerCase().includes(kw)).forEach(g=>{
        const b=el('button');
        b.appendChild(document.createTextNode(g));
        const ovr=STATE.codeOverride[g]?' · 재정의됨':'';
        b.appendChild(el('small',null,
          `코드 ${groups[g].n}개 · 출처 ${[...groups[g].src][0]}${ovr}`));
        if(g===sel)b.classList.add('on');
        b.onclick=()=>{sel=g;fill();drawCodes()};
        list.appendChild(b)});
    }
    q.addEventListener('input',fill);fill();
    left.appendChild(list);
    left.appendChild(el('div','meta',
      `총 코드 ${f.total.toLocaleString()}행 — 카탈로그 allowed 선언에서 생성`));
  }

  function currentCodes(){
    const ovr=STATE.codeOverride[sel];
    if(ovr)return [...ovr];
    return f.rows.filter(r=>r[i.code_set]===sel)
      .sort((a,b)=>a[i.sort_order]-b[i.sort_order]).map(r=>r[i.code]);
  }

  function drawCodes(){
    right.innerHTML='';
    right.appendChild(el('h3',null,`코드 — ${sel}`));
    right.appendChild(el('div','meta',
      `출처 ${[...groups[sel].src].join(' · ')} · 선언 순서가 곧 업무 순서다`));
    const codes=currentCodes();
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    ['순서','코드','이동'].forEach(x=>tr.appendChild(el('th',null,x)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody');
    codes.forEach((code,k)=>{
      const x=el('tr');
      x.appendChild(el('td','num',String(k)));
      x.appendChild(el('td','mono',code));
      const td=el('td');
      const up=el('button','btn','↑');up.disabled=k===0;
      const dn=el('button','btn','↓');dn.disabled=k===codes.length-1;
      up.onclick=()=>{const c2=[...codes];[c2[k-1],c2[k]]=[c2[k],c2[k-1]];
        STATE.codeOverride[sel]=c2;drawCodes()};
      dn.onclick=()=>{const c2=[...codes];[c2[k+1],c2[k]]=[c2[k],c2[k+1]];
        STATE.codeOverride[sel]=c2;drawCodes()};
      td.appendChild(up);td.appendChild(dn);x.appendChild(td);
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);right.appendChild(w);

    const acts=el('div','toolbar');
    const apply=el('button','btn primary','세션에 적용');
    const reset=el('button','btn','재정의 지우기');
    const gen=el('button','btn','정본 변경 제안');
    const outBox=el('pre','mono');outBox.style.whiteSpace='pre-wrap';
    apply.onclick=()=>{
      _CODE_ORDER=null;
      const ovr=STATE.codeOverride[sel];
      if(ovr){codeRank('','');_CODE_ORDER[sel]=
        Object.fromEntries(ovr.map((c2,k)=>[c2,k]))}
      repaintAll();};
    reset.onclick=()=>{delete STATE.codeOverride[sel];
      _CODE_ORDER=null;repaintAll();};
    gen.onclick=()=>{
      const ovr=STATE.codeOverride[sel];
      outBox.textContent=JSON.stringify({
        proposal:'코드 마스터 순서 변경',code_set:sel,
        from:f.rows.filter(r=>r[i.code_set]===sel)
          .sort((a,b)=>a[i.sort_order]-b[i.sort_order]).map(r=>r[i.code]),
        to:ovr||'(변경 없음)',
        apply_path:'risk_lib/datamodel/catalog.py (allowed 선언 순서)',
        note:'정본은 카탈로그다 — 세션 재정의는 이 화면을 닫으면 사라진다.'},null,2);
    };
    acts.appendChild(apply);acts.appendChild(reset);acts.appendChild(gen);
    right.appendChild(acts);right.appendChild(outBox);
  }
  drawGroups();drawCodes();
}

/* ---- 시뮬레이션 — 설명용 산술. 승인·제출값이 아니다 ---- */
function simulation(root){
  root.appendChild(el('p','lead',
    '자본비율 항등식(비율 = 자본 ÷ 위험가중자산)의 설명용 산술이다. 입력을 '+
    '움직이면 비율이 어떻게 반응하는지 즉시 본다 — 파이프라인 재계산이 아니며 '+
    '승인·제출값이 아니다. 실제 영향도는 시나리오 설정 제안 → 재실행 → 검증 '+
    '두 층으로만 확정된다.'));
  const cs=D.data['cap_stack'];
  const i=frameIdx(cs);
  /* cap_stack 은 구성 스택(CET1·AT1·T2 금액)이다 — Tier1·총자본은 누계다 */
  const amt=t=>{const r=cs.rows.find(x=>x[i.tier]===t);return r?r[i.amount]:0};
  const cet1r=cs.rows.find(x=>x[i.tier]==='CET1');
  if(!cet1r){root.appendChild(el('div','note','자본 스택 원장이 없다'));return}
  const capCET1=amt('CET1'),capT1=capCET1+amt('AT1'),
        capTOT=capT1+amt('T2');
  const rwa=capCET1/cet1r[i.ratio];            /* 항등식으로 도출한 RWA 총액 */
  /* RWA 구성비 — 표준방법 구간 합(신용) 대비 잔여를 시장·운영으로 본다는
     가정은 쓰지 않는다. 구성 비중은 입력이다 — 지어내지 않는다. */
  const bar=el('div','toolbar');
  function num(ph,v){const x=el('input','input');x.type='number';x.step='0.1';
    x.value=v;x.style.maxWidth='130px';x.title=ph;
    const wrap=el('label','meta',ph+' ');wrap.appendChild(x);return [wrap,x]}
  const [w1,dRwa]=num('Δ위험가중자산 %',0);
  const [w2,dCap]=num('Δ자본 (억원)',0);
  bar.appendChild(w1);bar.appendChild(w2);
  root.appendChild(bar);
  const pane=el('div');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const dR=(parseFloat(dRwa.value)||0)/100;
    const dC=(parseFloat(dCap.value)||0)*1e8;
    const rwa2=rwa*(1+dR);
    const g=el('div','grid');
    /* 요구비율은 CET1 만 원장(required)에 있다 — Tier1·총자본 요구는 지어내지
       않고 표시하지 않는다. */
    [['보통주자본(CET1)',capCET1,cet1r[i.required]],
     ['기본자본(Tier1)',capT1,null],['총자본',capTOT,null]].forEach(([nm,cap,req])=>{
      const before=cap/rwa,after=(cap+dC)/rwa2;
      const c=el('div','card kpi');
      c.appendChild(el('div','lab',nm+' 비율'));
      c.appendChild(el('div','val '+(req==null?'':(after>=req?'good':'bad')),
        (after*100).toFixed(2)+'%'));
      c.appendChild(el('div','sub',
        `현행 ${(before*100).toFixed(2)}%`+
        (req!=null?` · 요구 ${(req*100).toFixed(2)}% · 여유 ${((after-req)*100).toFixed(2)}%p`
                  :' · 요구비율은 원장에 없어 표시하지 않는다')));
      c.appendChild(el('div','ln','↗ 원장 · cap_stack (항등식 재계산)'));
      g.appendChild(c)});
    pane.appendChild(g);
    /* 민감도 표 — RWA ±1%, 자본 ±100억 */
    const rowsv=[];
    [[-0.01,0],[0.01,0],[0,-1e10],[0,1e10]].forEach(([a,b])=>{
      const r2=rwa*(1+a);
      rowsv.push([a?`RWA ${a>0?'+':''}${(a*100).toFixed(0)}%`:`자본 ${b>0?'+':''}${fmtMoney(b)}`,
        ((capCET1+b)/r2*100).toFixed(3)+'%',
        (((capCET1+b)/r2-cet1r[i.ratio])*10000).toFixed(1)+'bp'])});
    const c2=el('div','card');
    c2.appendChild(el('h3',null,'민감도 — 보통주자본비율'));
    c2.appendChild(table({columns:['충격','비율','변화'],rows:rowsv,
      total:rowsv.length,shown:rowsv.length},{numeric:false}));
    c2.appendChild(el('div','note',
      '설명용 산술이다 — RWA 변화가 위기 경로·유동성·손익에 미치는 2차 효과는 '+
      '여기 없다. 그 영향은 시나리오 설정 제안 → 파이프라인 재실행으로만 본다.'));
    pane.appendChild(c2);
  }
  dRwa.oninput=draw;dCap.oninput=draw;draw();
}

/* ---- 한도·소진 ---- */
function limitsScreen(root){
  root.appendChild(el('p','lead',
    '동일차주·업종·국가 등 다차원 한도와 소진율. 위반은 심각도와 함께 표시된다.'));
  const f=D.limits;
  const i=frameIdx(f);
  root.appendChild(hbars(f.rows.slice()
    .sort((a,b)=>b[i.utilisation]-a[i.utilisation]).slice(0,12)
    .map(r=>({label:`${r[i.limit]} · ${r[i.bucket]}`,
      value:r[i.utilisation]*100,sub:`한도 ${fmtMoney(r[i.threshold])}`,
      tone:r[i.severity]==='breach'?'bad':r[i.severity]==='warning'?'warn':undefined})),
    {title:'소진율 상위 (%)',money:false,src:srcMeta(f)}));
  const c=el('div','card');c.appendChild(el('h3',null,'한도 원장'));
  c.appendChild(table(f));c.appendChild(srcMeta(f));root.appendChild(c);
}

/* ---- 역스트레스 ---- */
function reverseStress(root){
  root.appendChild(el('p','lead',
    '순방향 위기상황이 "이 시나리오면 자본이 어떻게 되나"를 묻는다면, 역방향은 '+
    '"어느 심도가 자본 임계를 뚫는가"를 푼다. 여기 값은 파이프라인이 푼 해다 — '+
    '화면 계산이 아니다.'));
  const r=D.reverse_stress;
  const g=el('div','grid');
  [['대상 지표',r.metric.toUpperCase()+' 비율',''],
   ['임계 비율',(r.target_ratio*100).toFixed(2)+'%',''],
   ['현행 비율',(r.base_ratio*100).toFixed(2)+'%','good'],
   ['임계 심도',r.critical_severity.toFixed(3),r.resilient?'good':'warn'],
   ['파열점 비율',(r.ratio_at_break*100).toFixed(3)+'%','warn'],
   ['함의 GDP 충격',(r.implied_gdp_shock*100).toFixed(2)+'%','bad'],
  ].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+t,String(v)));
    g.appendChild(c)});
  root.appendChild(g);
  const c=el('div','card');
  c.appendChild(el('h3',null,'파열점의 산출 상태'));
  c.appendChild(table({columns:['항목','값'],rows:[
    ['수렴 여부',r.converged?'수렴':'미수렴'],
    ['현행이 이미 임계 이하인가',r.resilient===false&&r.base_ratio>r.target_ratio?'아니오':'검토'],
    ['파열점 위험가중자산',fmtMoney(r.rwa_at_break)],
    ['파열점 기대신용손실',fmtMoney(r.ecl_at_break)],
    ['함의 LGD 가산',(r.implied_lgd_addon*100).toFixed(2)+'%p'],
  ],total:5,shown:5},{numeric:false}));
  c.appendChild(el('div','note',
    '심도 1.0 미만에서 임계가 뚫리면(임계 심도 < 1) 심각 시나리오보다 약한 '+
    '충격에도 요구비율을 지키지 못한다는 뜻이다 — 자본계획·회복계획 연계 대상.'));
  root.appendChild(c);
}

/* ---- 금리리스크 · 유동성리스크 (ALM 분리) ---- */
const rateRisk=screenOf({
  lead:'은행계정 금리리스크(IRRBB) — 6대 금리충격의 EVE·NII 영향과 리프라이싱 갭.',
  charts:root=>{const f=D.data['alm_irrbb_shock'];
    if(!f)return;const i=frameIdx(f);
    root.appendChild(hbars(f.rows.map(r=>({label:r[i.scenario],
      value:Math.abs(r[i.delta_eve]),
      sub:`Tier1 대비 ${(r[i.pct_tier1]*100).toFixed(2)}%`,
      tone:r[i.pct_tier1]>=0.15?'bad':r[i.pct_tier1]>=0.1?'warn':undefined}))
      .sort((a,b)=>b.value-a.value),
      {title:'금리충격 시나리오별 ΔEVE (절대값) — 이상치 기준 Tier1 15%',
       src:srcMeta(f)}))},
  tables:[['금리충격(IRRBB)','alm_irrbb_shock'],
          ['리프라이싱 갭','alm_repricing_gap'],['ALM 종합','alm_result']]});
const liquidityRisk=screenOf({
  lead:'유동성리스크 — LCR·NSFR 구성과 가중 후 금액. 규제 최저 100%.',
  charts:root=>{if(DOMAIN_CHARTS['PRD-ALM'])DOMAIN_CHARTS['PRD-ALM'](root)},
  tables:[['유동성커버리지(LCR) 구성','alm_lcr_item'],
          ['순안정자금조달(NSFR) 구성','alm_nsfr_item']]});

/* ---- 코드 매핑 — 계정·상품 × 리스크 대상·특성 (공통=RDM, 그 외=각 스키마) */
function codeScope(root){
  root.appendChild(el('p','lead',
    '계정·상품 코드가 어느 리스크의 모집단에 들어가는지의 매핑이다. 매핑이 '+
    '없으면 코드 하나가 조용히 모든 산출에서 빠진다 — 대사는 들어온 것끼리만 '+
    '비교한다. 대상여부는 특성에서 규칙으로 파생되고(code_scope), 예외는 '+
    '여기서 제안으로만 만든다.'));
  const bar=el('div','toolbar');
  const mode=el('select','sel');
  [['account','계정코드'],['product','상품코드']].forEach(([v,t])=>{
    const o=el('option');o.value=v;o.textContent=t;mode.appendChild(o)});
  bar.appendChild(mode);root.appendChild(bar);
  const pane=el('div');root.appendChild(pane);
  const yn=v=>pill(v?'대상':'제외', v?'good':undefined);
  function draw(){
    pane.innerHTML='';
    if(mode.value==='account'){
      const am=D.data['rdm_account_master'],ai=frameIdx(am);
      const cr=D.data['crm_code_scope'],ci=frameIdx(cr);
      const al=D.data['alm_code_scope'],li=frameIdx(al);
      const crBy={};cr.rows.forEach(r=>{crBy[r[ci.account_code]]=r});
      const alBy={};al.rows.forEach(r=>{alBy[r[li.account_code]]=r});
      const c=el('div','card');
      c.appendChild(el('h3',null,'계정코드 × 리스크 대상·엔진 연계 매트릭스'));
      c.appendChild(el('div','meta',
        '신용환산율·위험가중 범위는 산출 엔진 상수(capital.crm·rwa_sa)에서, '+
        '모집단(건수·EAD)은 익스포저 원장에서, LCR 적용률은 산출 원장에서 '+
        '직접 읽는다 — 별사본이 없으니 매핑이 낡을 수 없다.'));
      const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
      ['계정','명칭','신용','자산군·접근법','위험가중',
       '신용환산(CCF)','모집단 실측','금리','유동성','LCR 분류·적용률']
        .forEach(x=>tr.appendChild(el('th',null,x)));
      th.appendChild(tr);t.appendChild(th);
      const tb=el('tbody');
      am.rows.forEach(r=>{
        const code=r[ai.account_code];
        const c2=crBy[code],l2=alBy[code];
        const x=el('tr');
        x.appendChild(el('td','mono',code));
        x.appendChild(el('td',null,r[ai.account_name]));
        const td0=el('td');td0.appendChild(yn(!!(c2&&c2[ci.in_scope])));x.appendChild(td0);
        x.appendChild(el('td','meta',c2&&c2[ci.asset_class]!=='—'
          ?c2[ci.asset_class]+' · '+c2[ci.approach]:'—'));
        x.appendChild(el('td','meta',c2?c2[ci.rw_range]:'—'));
        x.appendChild(el('td','meta',c2&&c2[ci.ccf_type]!=='—'
          ?c2[ci.ccf_type]+' · '+(c2[ci.ccf_rate]*100).toFixed(0)+'%':'—'));
        x.appendChild(el('td','meta',c2&&c2[ci.n_exposures]
          ?c2[ci.n_exposures].toLocaleString()+'건 · '+fmtMoney(c2[ci.ead_total]):'—'));
        [[l2&&l2[li.irrbb_scope]],[l2&&l2[li.liquidity_scope]]]
          .forEach(([v])=>{const td=el('td');td.appendChild(yn(!!v));x.appendChild(td)});
        x.appendChild(el('td','meta',l2&&l2[li.lcr_category]!=='—'
          ?l2[li.lcr_category]+(l2[li.lcr_factor]!=null
            ?' · '+(l2[li.lcr_factor]*100).toFixed(0)+'%':''):'—'));
        tb.appendChild(x)});
      t.appendChild(tb);w.appendChild(t);c.appendChild(w);
      c.appendChild(srcMeta(am,'대상여부: crm_code_scope · alm_code_scope (규칙 파생)'));
      pane.appendChild(c);
    } else {
      const pm=D.data['rdm_product_master'],pi=frameIdx(pm);
      const mk=D.data['mkt_code_scope'],mi=frameIdx(mk);
      const op=D.data['opr_code_scope'],oi=frameIdx(op);
      const mkBy={};mk.rows.forEach(r=>{mkBy[r[mi.product_code]]=r});
      const opBy={};op.rows.forEach(r=>{opBy[r[oi.product_code]]=r});
      const c=el('div','card');
      c.appendChild(el('h3',null,'상품코드 × 리스크 대상 매트릭스'));
      const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
      ['상품','명칭','북','시장','FRTB 위험군','거래 실측','운영',
       '손실사건 매핑·실측','산출방법']
        .forEach(x=>tr.appendChild(el('th',null,x)));
      th.appendChild(tr);t.appendChild(th);
      const tb=el('tbody');
      pm.rows.forEach(r=>{
        const code=r[pi.product_code];
        const m2=mkBy[code],o2=opBy[code];
        const x=el('tr');
        x.appendChild(el('td','mono',code));
        x.appendChild(el('td',null,r[pi.product_name]));
        x.appendChild(el('td',null,r[pi.book]));
        const td0=el('td');td0.appendChild(yn(!!(m2&&m2[mi.in_scope])));x.appendChild(td0);
        x.appendChild(el('td','meta',m2?m2[mi.frtb_class]:'—'));
        x.appendChild(el('td','meta',m2&&m2[mi.n_trades]
          ?m2[mi.trade_kind]+' · '+m2[mi.n_trades].toLocaleString()+'건':'—'));
        const td1=el('td');td1.appendChild(yn(!!(o2&&o2[oi.in_scope])));x.appendChild(td1);
        x.appendChild(el('td','meta',o2
          ?o2[oi.event_mapping]+' · '+o2[oi.n_events].toLocaleString()+'건':'—'));
        x.appendChild(el('td','meta',o2?o2[oi.capital_method]:'—'));
        tb.appendChild(x)});
      t.appendChild(tb);w.appendChild(t);c.appendChild(w);
      c.appendChild(srcMeta(pm,'대상여부: mkt_code_scope · opr_code_scope (규칙 파생)'));
      pane.appendChild(c);
    }
    /* 예외 제안 */
    const c3=el('div','card set-codescope');
    c3.appendChild(el('h3',null,'대상여부 예외 제안'));
    const b2=el('div','toolbar');
    const code=el('input','input');code.type='text';code.placeholder='코드 (예: 1340 / P-CRD)';
    code.style.maxWidth='170px';
    const risk=el('select','sel');
    ['신용','시장','운영','금리(IRRBB)','유동성'].forEach(x=>{
      const o=el('option');o.value=x;o.textContent=x;risk.appendChild(o)});
    const to=el('select','sel');
    [['true','대상 포함'],['false','대상 제외']].forEach(([v,t2])=>{
      const o=el('option');o.value=v;o.textContent=t2;to.appendChild(o)});
    const why=el('input','input');why.type='text';why.placeholder='사유 (필수)';
    b2.appendChild(code);b2.appendChild(risk);b2.appendChild(to);b2.appendChild(why);
    c3.appendChild(b2);
    const gen=el('button','btn primary','예외 제안 생성');c3.appendChild(gen);
    const err=el('div','note bad');err.hidden=true;c3.appendChild(err);
    const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c3.appendChild(out);
    gen.onclick=()=>{
      err.hidden=true;out.textContent='';
      if(!code.value.trim()||!why.value.trim()){
        err.textContent='코드와 사유는 필수다.';err.hidden=false;return}
      out.textContent=JSON.stringify({
        proposal:'코드 대상여부 예외',code:code.value.trim(),
        risk:risk.value,to_in_scope:to.value==='true',reason:why.value.trim(),
        apply_path:'risk_lib/datamodel/code_scope.py (규칙 또는 예외 등재)',
        procedure:['규칙·예외 반영','파이프라인 재실행','자체검증(2선)',
                   '독립검증(3선) 재요청'],
        note:'화면 매트릭스는 규칙 파생이다 — 예외도 코드가 돼야 산출에 반영된다.'},null,2);
    };
    pane.appendChild(c3);
  }
  mode.onchange=draw;draw();
}

/* ---- 화면 요약 — 조회 순간의 데이터에서 규칙으로 뽑는 한 줄 ----
   외부 LLM 호출은 하지 않는다(폐쇄망·CSP 차단·재현성). 같은 데이터면 같은
   문장이 나온다 — 요약도 산출물이므로 결정론이어야 한다. */
function cockpitInsights(){
  const out=[];
  try{
    const sev=D.kpis.find(k=>k.label.includes('위기상황'));
    if(sev&&sev.tone==='warn')out.push({t:`위기 ${sev.label.replace(' CET1 저점','')} 저점 ${sev.value} — 요구비율 침범, 자본계획·회복계획 연계 대상`,tone:'bad'});
    const rv=D.reverse_stress;
    if(rv&&rv.critical_severity<1)out.push({t:`역스트레스 임계 심도 ${rv.critical_severity.toFixed(2)} — 심각(1.0)보다 약한 충격에 임계 붕괴`,tone:'bad'});
    const lm=D.limits,li=frameIdx(lm);
    const br=lm.rows.filter(r=>r[li.severity]==='breach');
    if(br.length)out.push({t:`한도 위반 ${br.length}건 — 최고 소진 ${(Math.max(...lm.rows.map(r=>r[li.utilisation]))*100).toFixed(0)}% (${br[0][li.limit]})`,tone:'bad'});
    const ex=D.data['gov_exception_action'];
    if(ex){const xi=frameIdx(ex);
      const grave=ex.rows.filter(r=>r[xi.severity]==='중대').length;
      if(grave)out.push({t:`미해소 예외 ${ex.total}건 중 중대 ${grave}건 — 예외·조치 화면에서 기한 추적`,tone:'warn'})}
    const ipv=D.data['mkt_ipv'];
    if(ipv){const ii=frameIdx(ipv);
      const old=ipv.rows.filter(r=>r[ii.is_break]&&r[ii.days_open]>=5).length;
      if(old)out.push({t:`가격검증 미해소 5일 초과 ${old}건 — 상위보고 대상`,tone:'warn'})}
    const v=D.validation,vi=frameIdx(v);
    if(!v.rows.some(r=>r[vi.status]==='FAIL'))
      out.push({t:`자체검증 ${v.rows.length}건 FAIL 0 · 서식 대사 ${D.form_checks.total.toLocaleString()}건 실패 0 — 3선 게이트 ${D.independent.status}`,tone:'good'});
  }catch(e){}
  return out;
}
const SUMMARIES={
  '콕핏':()=>cockpitInsights()[0],
  '한도':()=>{const f=D.limits,i=frameIdx(f);
    const br=f.rows.filter(r=>r[i.severity]==='breach').length;
    const wr=f.rows.filter(r=>r[i.severity]==='warning').length;
    return br?{t:`한도 ${f.total}건 중 위반 ${br} · 경보 ${wr} — 위반 구간부터 검토하라`,tone:'bad'}
      :{t:`한도 ${f.total}건 — 위반 없음 · 경보 ${wr}건`,tone:wr?'warn':'good'}},
  '역스트레스':()=>{const r=D.reverse_stress;
    return {t:`임계 심도 ${r.critical_severity.toFixed(2)}에서 ${r.metric.toUpperCase()} ${(r.target_ratio*100).toFixed(0)}% 붕괴 — 함의 GDP ${(r.implied_gdp_shock*100).toFixed(1)}%`,
      tone:r.critical_severity<1?'bad':'good'}},
  '오버레이':()=>{const f=D.adjustments,i=frameIdx(f);
    const pend=f.rows.filter(r=>r[i.status]!=='approved').length;
    return {t:`수동조정 ${f.total}건 — 미승인 ${pend}건 · 전 건 사유·증빙·만료 보유`,
      tone:pend?'warn':'good'}},
  '예외·조치':()=>{const f=D.data['gov_exception_action'],i=frameIdx(f);
    const g=f.rows.filter(r=>r[i.severity]==='중대').length;
    return {t:`예외 ${f.total}건 (중대 ${g}) — 자동상계 금지, 종결은 사람 승인 후`,
      tone:g?'warn':'good'}},
  '백테스팅':()=>{const f=D.data['mkt_backtest_exception'],i=frameIdx(f);
    const n=f.rows.filter(r=>r[i.exception]).length;
    return {t:`관측 ${f.rows.length}일 중 예외 ${n}건 — ${n<=4?'녹색':'주의'} 구간`,
      tone:n<=4?'good':'warn'}},
  '유동성리스크':()=>{const f=D.data['alm_result'],i=frameIdx(f);
    const bad=f.rows.filter(r=>r[i.passes]===false).length;
    return {t:bad?`유동성 지표 ${bad}건 최저치 미달`:'LCR·NSFR 전 지표 최저치 상회',
      tone:bad?'bad':'good'}},
  '금리리스크':()=>{const f=D.data['alm_irrbb_shock'],i=frameIdx(f);
    const mx=f.rows.reduce((a,r)=>r[i.pct_tier1]>a[i.pct_tier1]?r:a,f.rows[0]);
    return {t:`최대 충격 ${mx[i.scenario]} — ΔEVE가 Tier1의 ${(mx[i.pct_tier1]*100).toFixed(1)}% (이상치 기준 15%)`,
      tone:mx[i.pct_tier1]>=0.15?'bad':'good'}},
  '모형 인벤토리':()=>{const f=D.data['crm_model'];if(!f)return null;
    const i=frameIdx(f);
    const dom=new Set(f.rows.map(r=>r[i.domain])).size;
    const over=f.rows.filter(r=>r[i.is_overdue]).length;
    return {t:`모형 ${f.total}건 · 도메인 ${dom}종 — 검증 기한 초과 ${over}건`,
      tone:over?'bad':'good'}},
  '검증 일정':()=>{const f=D.data['crm_model'];if(!f)return null;
    const i=frameIdx(f);
    const nxt=f.rows.slice().sort((a,b)=>String(a[i.next_due]).localeCompare(String(b[i.next_due])))[0];
    return {t:`가장 이른 차기 기한 ${nxt[i.next_due]} (${nxt[i.model_id]}) — 기한 경과는 산출 사용 불가를 뜻한다`,tone:'warn'}},
  '변별력·안정성':()=>{const f=D.data['crm_performance'];if(!f)return null;
    const i=frameIdx(f);
    const low=f.rows.filter(r=>(r[i.gini]||0)<0.4).length;
    return {t:`성능 ${f.total}건 — Gini 양호기준(40%) 미달 ${low}건`,
      tone:low?'warn':'good'}},
  '등급 보정':()=>{const f=D.data['crm_pd_calibration'];if(!f)return null;
    const i=frameIdx(f);
    const bad=f.rows.filter(r=>!r[i.within_tolerance]).length;
    return {t:`등급 ${f.total}건 중 허용범위 밖 ${bad}건 — O/E 괴리가 기준을 넘은 등급은 재보정 대상`,
      tone:bad?'warn':'good'}},
  '모형리스크':()=>({t:'Tier 1 은 연 1회 독립검증·챌린저 유지 — 모형은 만들어 두는 것이 아니라 주기적으로 다시 증명하는 자산이다',tone:'good'}),
  /* 이 원장은 "등급 유지" 와 "부도(D) 전이" 만 만든다 — 등급 간 상·하향은
     관측 구조상 존재할 수 없다. 상향 0건을 발견처럼 적으면 재등급을 측정해
     보니 없더라는 뜻이 되어 읽는 사람을 속인다. 있는 것만 말한다. */
  '등급 전이':()=>{const f=D.data['crm_rating_migration'];if(!f)return null;
    const i=frameIdx(f);
    const seg=new Set(f.rows.map(r=>r[i.segment])).size;
    const dflt=f.rows.filter(r=>r[i.to_grade]==='D');
    const mx=dflt.reduce((a,r)=>(r[i.share]||0)>(a?a[i.share]||0:0)?r:a,null);
    return {t:mx
      ? `세그먼트 ${seg}종 · 전이 ${f.total}쌍 (등급 유지 대 부도) — 최대 부도전이 ${mx[i.segment]} ${mx[i.from_grade]}→D ${((mx[i.share]||0)*100).toFixed(1)}%`
      : `세그먼트 ${seg}종 · 전이 ${f.total}쌍 — 관측 부도전이 없음`,
      tone:mx&&(mx[i.share]||0)>=0.1?'warn':'good'}},
  '집합투자증권':()=>{const f=D.data['rwa_fund_result'];if(!f)return null;
    const i=frameIdx(f);const m={};
    f.rows.forEach(r=>{m[r[i.adopted_method]]=(m[r[i.adopted_method]]||0)+1});
    return {t:`펀드 ${f.total}건 — 채택 ${Object.entries(m).map(([k,v])=>k+' '+v).join(' · ')} · 정보 부족은 1250% fallback`,tone:'good'}},
  '유동화':()=>{const f=D.data['rwa_sec_result'];if(!f)return null;
    const i=frameIdx(f);
    const fl=f.rows.filter(r=>r[i.floor_applied]).length;
    return {t:`트렌치 ${f.total}건 — 하한 적용 ${fl}건 (15% · STC 선순위 10%) · 계층 IRBA→ERBA→SA`,tone:'good'}},
  '파생상품':()=>{const f=D.data['rdm_derivative_master'];if(!f)return null;
    const i=frameIdx(f);
    const n=f.rows.reduce((a,r)=>a+(r[i.notional]||0),0);
    return {t:`거래 ${f.total}건 · 명목 ${fmtMoney(n)} — SA-CCR 은 기존 엔진(α=1.4) 재사용`,tone:'good'}},
  '집계 원장':()=>{const f=D.data['agg_credit_exposure'];if(!f)return null;
    const i=frameIdx(f);
    const e=f.rows.reduce((a,r)=>a+(r[i.ead]||0),0);
    return {t:`신용 축 집계 ${f.total}행 · EAD ${fmtMoney(e)} — 도메인마다 축이 다르다`,tone:'good'}},
  '산출 방법론':()=>({t:'원장에 세 방법 결과가 다 있다 — 방법 변경 영향을 재계산 없이 본다. 적용은 재실행·검증 두 층',tone:'warn'}),
  '코드 매핑':()=>{const cr=D.data['crm_code_scope'],i=frameIdx(cr);
    const n=cr.rows.filter(r=>r[i.in_scope]).length;
    return {t:`계정 ${cr.total}종 중 신용 대상 ${n} — 대상여부는 규칙 파생, 예외는 제안으로만`,tone:'good'}},
  '시뮬레이션':()=>({t:'설명용 산술 — 승인·제출값 아님. 실제 영향은 재실행·검증으로만 확정된다',tone:'warn'}),
  '상업성':()=>{const q=D.commercial.quotes,i=frameIdx(q);
    const best=q.rows.reduce((a,r)=>r[i.payback_years]<a[i.payback_years]?r:a,q.rows[0]);
    return {t:`회수기간 최단 ${best[i.name]} ${best[i.payback_years]}년 — 전 수치 가정 원장 파생·이중계상 검증 통과`,tone:'good'}},
  '요건 추적':()=>{const c=D.req_trace.coverage;
    return {t:`131건 중 반영 ${c['반영']} · 부분 ${c['부분']} · 미반영 ${c['미반영']} — 증빙 ${c.n_evidence}건 전부 기계 검증`,tone:'good'}},
  '감독보고':()=>({t:`서식 ${D.forms.length}장 · 검증 ${D.form_checks.total.toLocaleString()}건 실패 ${D.forms.reduce((a,f)=>a+f.n_failed,0)} — 편제·라인·인용 기준선 고정`,tone:'good'}),
  '검증':()=>({t:`2선 ${D.independent.self_validation} · 3선 게이트 ${D.independent.status} — 게이트는 fail-closed`,
    tone:D.independent.status==='적합'?'good':'warn'}),
};
function insertSummary(label,section){
  const f=SUMMARIES[label];
  if(!f)return;
  let sm=null;try{sm=f()}catch(e){return}
  if(!sm)return;
  const d=el('div','aisum '+(sm.tone||''));
  d.appendChild(el('span','aisum-tag','요약'));
  d.appendChild(el('span',null,sm.t));
  d.title='규칙 기반 자동 분석 — 결정론(같은 데이터면 같은 문장) · 외부 LLM 호출 없음(폐쇄망)';
  const h2=section.querySelector('h2');
  h2?h2.after(d):section.prepend(d);
}

function scenarioScreen(root){
  root.appendChild(el('p','lead',
    '위기상황 시나리오의 정의를 한 화면에서 본다 — 충격 축 14종의 단위충격, '+
    '시나리오별 분기 심도 경로, 신규 시나리오 제안. 화면은 재계산하지 않는다 — '+
    '적용은 코드 반영 + 파이프라인 재실행 + 검증 두 층이다.'));
  /* 분기 심도 경로 — 추적표에서 그대로 */
  const T=traceRows();
  if(T){
    const {f,i}=T;
    const scenarios=[...new Set(f.rows.map(r=>r[i.scenario]))];
    const quarters=[...new Set(f.rows.map(r=>r[i.quarter]))];
    const series=scenarios.map(sc=>({name:sc,
      values:quarters.map(q=>{const r=f.rows.find(x=>x[i.scenario]===sc&&
        x[i.quarter]===q&&/심도/.test(x[i.step]));return r?r[i.value]:null})}));
    const c=el('div','card');
    c.appendChild(el('h3',null,'시나리오별 분기 심도 경로 — 정점까지 선형 상승'));
    c.appendChild(multiLine(series,quarters,null));
    c.appendChild(srcMeta(f));
    root.appendChild(c);
  }
  scenarioSettings(root);
  /* 신규 시나리오 제안 */
  const c2=el('div','card set-newscen');
  c2.appendChild(el('h3',null,'신규 시나리오 제안'));
  const bar=el('div','toolbar');
  const nm=el('input','input');nm.type='text';nm.placeholder='시나리오 이름 (예: 부동산 급락)';
  const sv=el('input','input');sv.type='text';sv.placeholder='정점 심도 (예: 1.5)';
  sv.style.maxWidth='140px';
  bar.appendChild(nm);bar.appendChild(sv);c2.appendChild(bar);
  const gen=el('button','btn primary','시나리오 제안 생성');c2.appendChild(gen);
  const err=el('div','note bad');err.hidden=true;c2.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c2.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed&&STATE.killScope==='전사'){
      err.textContent='비상정지 중 — 제안을 만들지 않는다.';err.hidden=false;return}
    if(!nm.value.trim()){err.textContent='이름을 입력하라.';err.hidden=false;return}
    if(!/^\d+(\.\d+)?$/.test(sv.value.trim())){
      err.textContent='정점 심도는 숫자다.';err.hidden=false;return}
    out.textContent=JSON.stringify({
      proposal:'신규 위기상황 시나리오',name:nm.value.trim(),
      peak_severity:parseFloat(sv.value),
      apply_path:'risk_lib/stress/scenario.py · axes.py',
      procedure:['시나리오 정의 코드 반영','파이프라인 재실행',
                 '자체검증(2선)','독립검증(3선) 재요청','게이트 통과 후 결재'],
      note:'심도 경로·충격 축 배수는 기존 체계를 따른다 — 화면은 재계산하지 않는다.'},null,2);
  };
  root.appendChild(c2);
}

/* ---- 산출 방법론 설정 — 어느 방법으로 산출할지의 정책 ----
   방법 선택은 산출값을 바꾼다. 그래서 화면은 **제안서만** 만들고, 적용은
   코드 반영 + 파이프라인 재실행 + 검증 두 층이다. 다만 각 방법의 결과가
   이미 원장에 다 들어 있으므로(LTA/MBA/fallback · SA/ERBA/IRBA), 방법을
   바꿨을 때 값이 얼마나 달라지는지는 **재계산 없이 즉시** 보여줄 수 있다. */
/* ---- 모형 거버넌스 화면군 ----
   모형은 신용에만 있지 않다 — 원장이 crm_ 스키마에 산다는 것과 그 모형이
   신용 모형이라는 것은 다른 말이다(사용자 지적). 도메인 축으로 다시 세운다. */

function modelInventory(root){
  root.appendChild(el('p','lead',
    '전 도메인 모형 인벤토리다 — 신용(PD·LGD·ECL·빈티지)뿐 아니라 시장(VaR·XVA)· '+
    'ALM(IRRBB·LCR/NSFR)·위기상황·기후·전사(RAF)까지. 등급(Tier)은 모형 중요도이며 '+
    '검증 주기를 정한다. 기한이 지난 모형의 산출값은 사용 전 재검증 대상이다.'));
  const f=D.data['crm_model'];
  if(!f){root.appendChild(el('div','note','모형 원장이 없다'));return}
  const i=frameIdx(f);
  const g=el('div','grid');
  const byDom={},byTier={};
  f.rows.forEach(r=>{byDom[r[i.domain]]=(byDom[r[i.domain]]||0)+1;
    byTier['Tier '+r[i.tier]]=(byTier['Tier '+r[i.tier]]||0)+1});
  const over=f.rows.filter(r=>r[i.is_overdue]).length;
  const uat=f.rows.filter(r=>r[i.status]!=='PROD').length;
  [['등록 모형',f.total,''],['도메인',Object.keys(byDom).length,''],
   ['검증 기한 초과',over,over?'bad':'good'],
   ['운영 전(UAT 등)',uat,uat?'warn':'good']].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));c.appendChild(el('div','val '+t,String(v)));
    g.appendChild(c)});
  root.appendChild(g);

  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1fr 1fr';
  two.appendChild(hbars(Object.entries(byDom).map(([k,v])=>({label:k,value:v}))
    .sort((a,b)=>b.value-a.value),{title:'도메인별 모형 수',money:false}));
  two.appendChild(hbars(Object.entries(byTier).map(([k,v])=>({label:k,value:v}))
    .sort((a,b)=>a.label.localeCompare(b.label)),
    {title:'등급(Tier)별 모형 수 — 1이 가장 중요',money:false}));
  root.appendChild(two);

  const bar=el('div','toolbar');
  const dsel=el('select','sel');
  ['전체 도메인'].concat(Object.keys(byDom).sort()).forEach(d=>{
    const o=el('option');o.value=d==='전체 도메인'?'':d;o.textContent=d;
    dsel.appendChild(o)});
  bar.appendChild(dsel);root.appendChild(bar);
  const pane=el('div','card');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const rows=f.rows.filter(r=>!dsel.value||r[i.domain]===dsel.value);
    pane.appendChild(el('h3',null,`모형 ${rows.length}건`));
    pane.appendChild(table({table:'crm_model',
      columns:['model_id','model_name','domain','tier','status','owner','purpose'],
      labels:['모형','모형명','도메인','등급','상태','소유부서','목적'],
      rows:rows.map(r=>[r[i.model_id],r[i.model_name],r[i.domain],r[i.tier],
        r[i.status],r[i.owner],r[i.purpose]]),
      total:rows.length,shown:rows.length},{numeric:false}));
    pane.appendChild(srcMeta(f));
  }
  dsel.onchange=draw;draw();
}

function modelValidationSchedule(root){
  root.appendChild(el('p','lead',
    '검증 주기는 등급이 정한다 — Tier 1 은 연 1회, Tier 2 는 2년, Tier 3 은 3년이 '+
    '통상이다. 기한 경과는 "아직 안 했다"가 아니라 **그 모형의 산출을 쓸 수 없다**는 '+
    '뜻이므로 경과일을 원장에 두고 화면이 읽는다.'));
  const f=D.data['crm_model'];
  if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.slice().sort((a,b)=>
    String(a[i.next_due]).localeCompare(String(b[i.next_due])));

  /* 기한까지 남은 일수 — 경과분은 원장의 days_overdue 를 그대로 쓴다.
     화면이 날짜를 다시 빼면 원장과 어긋날 수 있다. */
  const base=Date.parse(D.meta.asof+'T00:00:00Z');
  const rem=r=>r[i.is_overdue]?-(r[i.days_overdue]||0)
    :Math.round((Date.parse(r[i.next_due]+'T00:00:00Z')-base)/86400000);
  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1fr 1fr';
  two.appendChild(hbars(rows.map(r=>({label:r[i.model_id],
    value:Math.max(rem(r),0),
    sub:r[i.is_overdue]?`기한 초과 ${r[i.days_overdue]}일`
      :`${r[i.next_due]} · Tier ${r[i.tier]}`,
    tone:r[i.is_overdue]?'bad':rem(r)<=90?'warn':undefined})),
    {title:'차기 검증까지 남은 일수 — 90일 이내는 착수 대상',money:false,
     src:srcMeta(f)}));
  const byDom={};rows.forEach(r=>{const d=r[i.domain];
    if(byDom[d]==null||rem(r)<byDom[d])byDom[d]=rem(r)});
  two.appendChild(hbars(Object.entries(byDom)
    .sort((a,b)=>a[1]-b[1])
    .map(([k,v])=>({label:k,value:Math.max(v,0),
      sub:v<0?`경과 ${-v}일`:`${v}일 남음`,
      tone:v<0?'bad':v<=90?'warn':undefined})),
    {title:'도메인별 가장 임박한 기한',money:false}));
  root.appendChild(two);

  const c=el('div','card');
  c.appendChild(el('h3',null,'검증 일정 — 차기 기한 순'));
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['모형','도메인','등급','최근 검증','차기 기한','상태','소유부서']
    .forEach(x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  rows.forEach(r=>{
    const x=el('tr');
    x.appendChild(el('td','mono',r[i.model_id]));
    x.appendChild(el('td',null,r[i.domain]));
    x.appendChild(el('td','num',String(r[i.tier])));
    x.appendChild(el('td',null,String(r[i.last_validation]||'—')));
    x.appendChild(el('td',null,String(r[i.next_due]||'—')));
    const td=el('td');
    td.appendChild(r[i.is_overdue]
      ? pill(`기한 초과 ${r[i.days_overdue]}일`,'bad')
      : pill('기한 내','good'));
    x.appendChild(td);
    x.appendChild(el('td','meta',r[i.owner]));
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);
  c.appendChild(srcMeta(f));
  root.appendChild(c);

  const c2=el('div','card');
  c2.appendChild(el('h3',null,'의존 관계와 알려진 한계'));
  c2.appendChild(el('div','meta',
    '상류 모형이 바뀌면 하류도 재검증 대상이다. 한계를 원장에 적지 않으면 '+
    '사용자가 모른 채 쓴다.'));
  c2.appendChild(table({table:'crm_model',
    columns:['model_id','dependencies','known_limitations'],
    labels:['모형','의존 모형·데이터','알려진 한계'],
    rows:f.rows.map(r=>[r[i.model_id],r[i.dependencies],r[i.known_limitations]]),
    total:f.total,shown:f.rows.length},{numeric:false}));
  root.appendChild(c2);
}

function modelPerformance(root){
  root.appendChild(el('p','lead',
    '신용 모형의 변별력(Gini·KS)과 안정성(PSI). Gini 는 높을수록, PSI 는 낮을수록 '+
    '좋다 — PSI 0.25 를 넘으면 모집단이 개발 시점과 달라졌다는 신호다.'));
  const f=D.data['crm_performance'];
  if(!f){root.appendChild(el('div','note','성능 원장이 없다'));return}
  const i=frameIdx(f);
  root.appendChild(hbars(f.rows.map(r=>({
    label:`${r[i.model_id]} · ${r[i.segment]}`, value:(r[i.gini]||0)*100,
    sub:`KS ${((r[i.ks]||0)*100).toFixed(1)} · PSI ${(r[i.psi]||0).toFixed(3)}`,
    tone:(r[i.gini]||0)<0.4?'warn':undefined})),
    {title:'변별력 Gini (%) — 양호 기준 40%',money:false,src:srcMeta(f)}));
  const c=el('div','card');
  c.appendChild(el('h3',null,'성능 지표 원장'));
  c.appendChild(table(f));root.appendChild(c);
}

function modelCalibration(root){
  root.appendChild(el('p','lead',
    '등급별 예측 PD 와 실측 부도율의 대조다. O/E 비율이 1 에서 멀수록 보정이 '+
    '어긋난 것이며, 허용범위 밖 등급은 재보정 대상이다.'));
  const f=D.data['crm_pd_calibration'];
  if(!f){root.appendChild(el('div','note','보정 원장이 없다'));return}
  const i=frameIdx(f);
  const bad=f.rows.filter(r=>!r[i.within_tolerance]).length;
  const c0=el('div','card');
  c0.appendChild(el('h3',null,'보정 상태'));
  c0.appendChild(meter('허용범위 내 등급',f.rows.length-bad,f.rows.length,
    bad?'warn':undefined));
  c0.appendChild(el('div','meta',
    `허용범위 밖 ${bad}건 — 예측 PD 와 실측 부도율의 괴리가 기준을 넘은 등급`));
  root.appendChild(c0);
  root.appendChild(hbars(f.rows.slice(0,12).map(r=>({
    label:`${r[i.segment]} · ${r[i.grade]}`, value:r[i.oe_ratio]||0,
    sub:`예측 ${((r[i.pd_predicted]||0)*100).toFixed(2)}% · 실측 ${((r[i.dr_observed]||0)*100).toFixed(2)}%`,
    tone:r[i.within_tolerance]?undefined:'bad'})),
    {title:'등급별 O/E 비율 — 1.0 이 완전 일치',money:false,src:srcMeta(f)}));
  const c=el('div','card');
  c.appendChild(el('h3',null,'보정 원장'));
  c.appendChild(table(f));root.appendChild(c);
}

function modelRiskGovernance(root){
  root.appendChild(el('p','lead',
    '모형리스크 관리 — 등급별 거버넌스 요구, 운영 상태, 검증 기한. 모형은 '+
    '만들어 놓고 두는 것이 아니라 주기적으로 다시 증명해야 하는 자산이다.'));
  const f=D.data['crm_model'];
  if(!f)return;
  const i=frameIdx(f);
  const TIER_REQ={1:['연 1회 독립검증','상시 성능 모니터링','이사회 보고 대상',
                     '챌린저 모형 유지'],
                  2:['2년 주기 독립검증','반기 성능 모니터링','경영진 보고'],
                  3:['3년 주기 독립검증','연 1회 성능 점검']};
  const CYCLE={1:12,2:24,3:36};
  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1fr 1fr';
  two.appendChild(hbars([1,2,3].map(t=>({label:`Tier ${t}`,
    value:f.rows.filter(r=>r[i.tier]===t).length,
    sub:`검증 주기 ${CYCLE[t]}개월`,
    tone:t===1?'warn':undefined})),
    {title:'등급별 모형 수와 검증 주기 — 등급이 주기를 정한다',money:false,
     src:srcMeta(f)}));
  const own={};f.rows.forEach(r=>{own[r[i.owner]]=(own[r[i.owner]]||0)+1});
  two.appendChild(hbars(Object.entries(own)
    .sort((a,b)=>b[1]-a[1]).map(([k,v])=>({label:k,value:v})),
    {title:'소유부서별 모형 수 — 책임 소재가 분산되면 재검증이 밀린다',
     money:false}));
  root.appendChild(two);

  const c=el('div','card');
  c.appendChild(el('h3',null,'등급별 거버넌스 요구 (SR 11-7 계열)'));
  const rows=[];
  [1,2,3].forEach(t=>{
    const ms=f.rows.filter(r=>r[i.tier]===t);
    rows.push([`Tier ${t}`, ms.length,
      ms.map(r=>r[i.model_id]).join(' · ')||'—',
      TIER_REQ[t].join(' · ')]);
  });
  c.appendChild(table({columns:['등급','모형 수','해당 모형','거버넌스 요구'],
    rows, total:3, shown:3},{numeric:false}));
  root.appendChild(c);

  const c2=el('div','card');
  c2.appendChild(el('h3',null,'운영 상태 분포'));
  const st={};f.rows.forEach(r=>{st[r[i.status]]=(st[r[i.status]]||0)+1});
  c2.appendChild(dotlist(Object.entries(st).map(([k,v])=>({
    label:`${k} — ${v}건`, right:k==='PROD'?'운영 중':'운영 전',
    tone:k==='PROD'?'good':'warn'}))));
  c2.appendChild(el('div','note',
    '운영 전(UAT·개발) 모형의 산출은 공표·제출에 쓰지 않는다. 상태가 원장에 '+
    '있으므로 어느 화면이든 같은 판정을 본다.'));
  root.appendChild(c2);
}

function methodology(root){
  root.appendChild(el('p','lead',
    '집합투자증권(CRE60)·유동화(CRE40) 는 여러 산출 방법이 규정에 함께 있고, '+
    '어느 것을 쓸지는 정보 가용성과 정책이 정한다. 원장에 세 방법 결과가 모두 '+
    '들어 있으므로 방법을 바꿨을 때의 차이를 재계산 없이 본다 — 화면은 값을 '+
    '바꾸지 않고, 적용은 코드 반영 + 재실행 + 2선·3선 검증을 거친다.'));

  /* --- 집합투자증권 --- */
  const fr=D.data['rwa_fund_result'];
  if(fr){
    const i=frameIdx(fr);
    const c=el('div','card set-method-fund');
    c.appendChild(el('h3',null,'집합투자증권 — LTA · MBA · Fallback (CRE60)'));
    const bar=el('div','toolbar');
    const sel=el('select','sel');
    [['as_is','원장 채택값 (정보 가용성 기준)'],
     ['look_through','전건 LTA 강제 (CRE60.5)'],
     ['mandate','전건 MBA 강제 (CRE60.7)'],
     ['fallback','전건 Fallback 1250% (CRE60.9)']].forEach(([v,t])=>{
      const o=el('option');o.value=v;o.textContent=t;sel.appendChild(o)});
    bar.appendChild(sel);c.appendChild(bar);
    const pane=el('div');c.appendChild(pane);
    const COL={look_through:'rwa_lta',mandate:'rwa_mba',fallback:'rwa_fallback'};
    function draw(){
      pane.innerHTML='';
      const base=fr.rows.reduce((a,r)=>a+(r[i.adopted_rwa]||0),0);
      const pick=sel.value;
      const alt=fr.rows.reduce((a,r)=>a+(pick==='as_is'
        ? (r[i.adopted_rwa]||0) : (r[i[COL[pick]]]||0)),0);
      const g=el('div','grid');
      [['원장 채택 RWA',base,''],
       ['선택 방법 RWA',alt,alt>base?'bad':alt<base?'good':''],
       ['차이',alt-base,Math.abs(alt-base)<1?'':'warn']].forEach(([k,v,t])=>{
        const cc=el('div','card kpi');
        cc.appendChild(el('div','lab',k));
        cc.appendChild(el('div','val '+t,fmtMoney(v)));
        cc.appendChild(el('div','sub',base?((v/base-1)*100).toFixed(1)+'% (채택 대비)':''));
        g.appendChild(cc)});
      pane.appendChild(g);
      pane.appendChild(table({table:'rwa_fund_result',
        columns:['fund_id','fund_name','adopted_method','rw_lta','rw_mba','rw_fallback','adopted_rwa'],
        labels:['펀드','펀드명','채택 방법','LTA RW','MBA RW','Fallback RW','채택 RWA'],
        rows:fr.rows.map(r=>[r[i.fund_id],r[i.fund_name],r[i.adopted_method],
          r[i.rw_lta],r[i.rw_mba],r[i.rw_fallback],r[i.adopted_rwa]]),
        total:fr.total,shown:fr.rows.length}));
      pane.appendChild(el('div','meta',
        'LTA 는 편입자산을 직접 보유한 것처럼, MBA 는 운용지침 한도까지 투자했다고 '+
        '가정한다. 정보가 부족하면 Fallback 1250%.'));
    }
    sel.onchange=draw;draw();
    root.appendChild(c);
  }

  /* --- 유동화 --- */
  const sr=D.data['rwa_sec_result'];
  if(sr){
    const i=frameIdx(sr);
    const c=el('div','card set-method-sec');
    c.appendChild(el('h3',null,'유동화 — SEC-IRBA · ERBA · SA (CRE40.41 계층)'));
    const bar=el('div','toolbar');
    const sel=el('select','sel');
    [['as_is','원장 채택값 (CRE40.41 계층)'],
     ['irba','전건 SEC-IRBA (가능한 건만)'],
     ['erba','전건 SEC-ERBA (등급 있는 건만)'],
     ['sa','전건 SEC-SA']].forEach(([v,t])=>{
      const o=el('option');o.value=v;o.textContent=t;sel.appendChild(o)});
    bar.appendChild(sel);c.appendChild(bar);
    const pane=el('div');c.appendChild(pane);
    const COL={irba:'rwa_irba',erba:'rwa_erba',sa:'rwa_sa'};
    function draw2(){
      pane.innerHTML='';
      const base=sr.rows.reduce((a,r)=>a+(r[i.adopted_rwa]||0),0);
      let alt=0,skipped=0;
      sr.rows.forEach(r=>{
        if(sel.value==='as_is'){alt+=r[i.adopted_rwa]||0;return}
        const v=r[i[COL[sel.value]]];
        /* 산출 불가(등급 없음 등)를 0으로 채우지 않는다 — 채우면 자본이
           사라지고 그 사실이 화면 어디에도 안 남는다. */
        if(v==null||Number.isNaN(v)){skipped++;alt+=r[i.adopted_rwa]||0}
        else alt+=v;
      });
      const g=el('div','grid');
      [['원장 채택 RWA',base,''],['선택 방법 RWA',alt,alt>base?'bad':alt<base?'good':''],
       ['차이',alt-base,Math.abs(alt-base)<1?'':'warn']].forEach(([k,v,t])=>{
        const cc=el('div','card kpi');
        cc.appendChild(el('div','lab',k));
        cc.appendChild(el('div','val '+t,fmtMoney(v)));
        g.appendChild(cc)});
      pane.appendChild(g);
      if(skipped)pane.appendChild(el('div','note',
        `산출 불가 ${skipped}건은 채택값을 유지했다 — 0으로 채우면 자본이 `+
        `사라지고 그 사실이 화면에 남지 않는다.`));
      pane.appendChild(table({table:'rwa_sec_result',
        columns:['tranche_id','tranche_name','adopted_method','rw_sa','rw_erba','rw_irba','adopted_rw','floor_applied'],
        labels:['트렌치','트렌치명','채택','SA RW','ERBA RW','IRBA RW','채택 RW','하한 적용'],
        rows:sr.rows.map(r=>[r[i.tranche_id],r[i.tranche_name],r[i.adopted_method],
          r[i.rw_sa],r[i.rw_erba],r[i.rw_irba],r[i.adopted_rw],r[i.floor_applied]]),
        total:sr.total,shown:sr.rows.length}));
      pane.appendChild(el('div','meta',
        '계층은 IRBA → ERBA → SA 순이다(CRE40.41). 위험가중 하한은 15%, '+
        'STC 선순위는 10%(CRE44.5).'));
    }
    sel.onchange=draw2;draw2();
    root.appendChild(c);
  }

  /* --- 제안 --- */
  const c3=el('div','card set-method-proposal');
  c3.appendChild(el('h3',null,'방법론 변경 제안'));
  const bar=el('div','toolbar');
  const dom=el('select','sel');
  ['집합투자증권','유동화','파생(SA-CCR)'].forEach(x=>{
    const o=el('option');o.value=x;o.textContent=x;dom.appendChild(o)});
  const why=el('input','input');why.type='text';
  why.placeholder='변경 사유 (필수) — 정보 가용성 변화·감독 지적·정책 결정 등';
  bar.appendChild(dom);bar.appendChild(why);c3.appendChild(bar);
  const gen=el('button','btn primary','제안 생성');c3.appendChild(gen);
  const err=el('div','note bad');err.hidden=true;c3.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c3.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed&&STATE.killScope==='전사'){
      err.textContent='비상정지 중 — 제안을 만들지 않는다.';err.hidden=false;return}
    if(!why.value.trim()){err.textContent='사유는 필수다.';err.hidden=false;return}
    const path={'집합투자증권':'risk_lib/datamodel/funds.py (approach 결정 규칙)',
      '유동화':'risk_lib/datamodel/securitisation.py (CRE40.41 계층)',
      '파생(SA-CCR)':'risk_lib/ccr.py (SF·α·담보 인식)'}[dom.value];
    out.textContent=JSON.stringify({
      proposal:'산출 방법론 변경',domain:dom.value,reason:why.value.trim(),
      asof:D.meta.asof,run_id:D.meta.run_id,apply_path:path,
      procedure:['방법론 코드 반영','파이프라인 재실행','자체검증(2선) FAIL 0',
                 '독립검증(3선) 재요청 — 방법론 변경은 지문을 바꾼다',
                 '게이트 통과 후 결재'],
      note:'화면은 원장에 이미 있는 대안 값을 보여줄 뿐 산출을 바꾸지 않는다.'},null,2);
  };
  root.appendChild(c3);
}

function settings(root){
  root.appendChild(el('p','lead',
    '표시명·기준일 전환은 세션 안에서 즉시 적용된다(산출값 무관). 서식번호 '+
    '매핑과 시나리오 파라미터는 산출물의 정체를 바꾸므로 화면에서 적용하지 '+
    '않는다 — 변경 제안서를 만들고, 적용은 코드 반영 + 파이프라인 재실행 + '+
    '검증 두 층(자체검증·독립검증)을 다시 거친다.'));
  runRegistry(root);
  labelSettings(root);
  formMapSettings(root);
  /* 시나리오 설정은 별도 화면(위기상황 > 시나리오 설정)으로 옮겼다 */
}

/* ---- 범위형 비상정지 (PLT-016) — 부문 단위로 조회를 세운다 ---- */
function killedFor(domain){
  return STATE.killed&&(STATE.killScope==='전사'||domain===STATE.killScope);
}

/* ---- 도메인 세부화면 — 원장 나열 + 부문 차트. 전 값이 payload 원장이다 ---- */
/* ---- 코드 마스터 정렬 — rdm_code_master 가 정본이다 ----
   등급·건전성 분류는 선언 순서가 업무 순서다. 가나다순은 틀린 정렬이다. */
let _CODE_ORDER=null;
function codeRank(tableName,col){
  if(!_CODE_ORDER){
    _CODE_ORDER={};
    const f=D.data['rdm_code_master'];
    if(f){const i=frameIdx(f);
      f.rows.forEach(r=>{
        (_CODE_ORDER[r[i.code_set]]=_CODE_ORDER[r[i.code_set]]||{})
          [r[i.code]]=r[i.sort_order]})}
  }
  return _CODE_ORDER[tableName+'.'+col]||_CODE_ORDER[col]||null;
}
function sortByCode(values,tableName,col){
  const rank=codeRank(tableName,col);
  const out=[...values];
  if(rank)out.sort((a,b)=>(rank[a]??1e9)-(rank[b]??1e9));
  return out;
}

/* 전이행렬 피봇 — 세그먼트 선택, 행·열은 코드 마스터 순서, 대각선 강조 */
function migrationPivot(root){
  const f=D.data['crm_rating_migration'];
  if(!f)return;
  const i=frameIdx(f);
  const c=el('div','card');
  c.appendChild(el('h3',null,'등급 전이행렬 — 피봇'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  sortByCode([...new Set(f.rows.map(r=>r[i.segment]))],
             'crm_rating_migration','segment')
    .forEach(sg=>{const o=el('option');o.value=sg;
      o.textContent='세그먼트 · '+sg;sel.appendChild(o)});
  bar.appendChild(sel);c.appendChild(bar);
  const pane=el('div');c.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const rows=f.rows.filter(r=>r[i.segment]===sel.value);
    const grades=sortByCode(
      [...new Set(rows.flatMap(r=>[r[i.from_grade],r[i.to_grade]]))],
      'crm_rating_migration','from_grade');
    const cell={};let mx=0;
    rows.forEach(r=>{
      const k=r[i.from_grade]+'>'+r[i.to_grade];
      cell[k]=(cell[k]||0)+r[i.share];mx=Math.max(mx,cell[k])});
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    tr.appendChild(el('th',null,'시작 \\ 도착'));
    grades.forEach(g=>tr.appendChild(el('th','num',g)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody');
    grades.forEach(fr=>{
      const x=el('tr');
      const h=el('td',null,fr);h.style.fontWeight='700';x.appendChild(h);
      grades.forEach(to=>{
        const v=cell[fr+'>'+to];
        const td=el('td','num',v==null?'—':(v*100).toFixed(1)+'%');
        if(v!=null){
          td.style.background=`rgba(66,169,255,${(0.06+0.5*v/mx).toFixed(3)})`;
          td.title=`${fr} → ${to} · ${(v*100).toFixed(2)}%`;
        }
        if(fr===to)td.style.boxShadow='inset 0 0 0 1px var(--lineage)';
        x.appendChild(td)});
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);pane.appendChild(w);
    pane.appendChild(el('div','meta',
      `세그먼트 ${sel.value} · 전이 ${rows.length}건 — 행·열은 코드 마스터 `+
      `순서(등급 사다리), 대각선 테두리는 등급 유지`));
    pane.appendChild(srcMeta(f));
  }
  sel.onchange=draw;draw();
  root.appendChild(c);
}

function autoCharts(root,specs){
  (specs||[]).forEach(([title,tab,labCols,valCol,opt])=>{
    const f=D.data[tab];if(!f)return;
    const i=frameIdx(f);
    const g=new Map();
    f.rows.forEach(r=>{
      const k=labCols.map(c=>r[i[c]]).join(' · ');
      g.set(k,(g.get(k)||0)+(valCol?(r[i[valCol]]||0):1))});
    const items=[...g.entries()].map(([k,v])=>({label:k,value:v}))
      .sort((a,b)=>b.value-a.value).slice(0,10);
    root.appendChild(hbars(items,{title,money:opt?.money!==false,
      src:srcMeta(f)}))});
}
function screenOf(defs){
  return root=>{
    root.appendChild(el('p','lead',defs.lead));
    if(defs.charts)defs.charts(root);
    autoCharts(root,defs.autochart);
    (defs.forms||[]).forEach(fid=>{
      const f=D.forms.find(x=>x.form_id===fid);
      if(f){const pane=el('div');renderForm(pane,f);root.appendChild(pane)}
    });
    defs.tables.forEach(([title,key])=>{
      const f=D.data[key];
      const c=el('div','card');c.appendChild(el('h3',null,title));
      if(f){c.appendChild(table(f));c.appendChild(srcMeta(f))}
      else c.appendChild(el('div','note','원장 '+key+' 이 payload에 없다'));
      root.appendChild(c)});
  };
}

function exceptionQueue(root){
  const f=D.data['gov_exception_action'];
  if(!f)return;
  const i=frameIdx(f);
  const g=groupSum(f,'status','due_days');
  root.appendChild(hbars(g.map(x=>({label:'상태 '+x.key,value:x.n,
    sub:null,tone:x.key==='접수'?'warn':x.key==='조치중'?'bad':undefined})),
    {title:'예외 상태 분포 — 자동상계 금지, 종결은 사람 승인 후',
     money:false,src:srcMeta(f)}));
}

function commercial(root){
  const C=D.commercial;
  root.appendChild(el('p','lead',
    '사업성 산출 — 규제 산출물이 아니다. 제출 지문·독립검증 대상에 넣지 않으며, '+
    '모든 금액은 가정 원장에서 계산으로만 나온다. 가정 없이 등장하는 금액이 '+
    '하나라도 있으면 그 표는 견적이 아니라 소설이다. 전부 합성 가정이며 실제 '+
    '견적은 계약 가정으로 교체된다.'));
  const dc=C.double_counting;
  const note=el('div','note'+(dc.length?' bad':''));
  note.textContent=dc.length
    ? 'ROI 이중계상 '+dc.length+'건 — '+dc.join(' · ')
    : 'ROI 이중계상 검증 통과 — 편익 항목마다 출처 가정이 하나씩이다 (COM-007)';
  root.appendChild(note);
  [['패키지 견적 (COM-002·003·004·005)','quotes'],
   ['ROI 편익 — 항목별 1회 계상 (COM-007)','roi'],
   ['가정 원장 (COM-001·006)','assumptions'],
   ['GTM Funnel 단계 정의 (COM-008)','funnel']].forEach(([t,k])=>{
    const c=el('div','card');c.appendChild(el('h3',null,t));
    c.appendChild(table(C[k]));root.appendChild(c)});
}

const DETAIL_SCREENS=[
  ['원천·계약','A · 원천 인터페이스 — 계약·스냅샷·표준 매핑',screenOf({
    lead:'원천 시스템과의 인터페이스 계약, 수신 스냅샷, 표준코드 매핑을 원장으로 통제한다. 계약 위반은 적재 전에 차단된다.',
    autochart:[['원천 시스템별 수신 행수','rdm_source_contract',
                ['source_system'],'actual_rows',{money:false}]],
    tables:[['원천 인터페이스 계약','rdm_source_contract'],
            ['수신 스냅샷 원장','rdm_snapshot'],
            ['표준코드 매핑','rdm_canonical_map']]})],
  ['DQ·대사','A · 데이터품질 — 규칙·판정·대사',screenOf({
    lead:'DQ 규칙과 판정, 원천–산출 대사를 한 화면에서 본다. 실패는 예외·조치 큐로 넘어간다.',
    autochart:[['판정 심각도별 건수','rdm_dq_result',['severity'],null,{money:false}],
               ['DQ 규칙 유형 분포','rdm_dq_rule',['rule_type'],null,{money:false}]],
    tables:[['DQ 규칙 원장','rdm_dq_rule'],['DQ 판정 결과','rdm_dq_result'],
            ['집계·대사','rdm_reconciliation']]})],
  ['예외·조치','A · 예외·조치 워크플로 — 접수→조치→종결',screenOf({
    lead:'대사·DQ·IPV 세 원장의 미해소 예외가 표준 조치·담당·기한이 붙은 하나의 큐로 모인다. 예외를 보여주는 것과 조치가 추적되는 것은 다르다 — 종결은 사람 승인 후에만 한다.',
    charts:exceptionQueue,
    tables:[['예외·조치 큐','gov_exception_action'],
            ['경보·조치 정책 바인딩','gov_alert_policy']]})],
  ['담보·보증','A · 담보·보증·재무 원장',screenOf({
    lead:'담보·보증·차주 재무 원장 — 신용위험경감과 LGD의 원천이다.',
    autochart:[['담보유형별 평가액','rdm_collateral',['collateral_type'],'market_value'],
               ['보증유형별 보증액','rdm_guarantee',['protection_type'],'guaranteed_amount']],
    tables:[['담보 원장','rdm_collateral'],['보증 원장','rdm_guarantee'],
            ['차주 재무','rdm_obligor_financial']]})],
  ['등급 전이','MDL · 등급 전이행렬 — 세그먼트별 피봇',screenOf({
    lead:'모형 카드, PD 보정, 변별력·안정성 성능, 등급 이동행렬 — 모형 거버넌스의 원장들이다. 전이행렬 피봇의 행·열은 코드 마스터(등급 사다리) 순서다.',
    charts:migrationPivot,
    tables:[['모형 카드','crm_model'],['PD 보정','crm_pd_calibration'],
            ['모형 성능','crm_performance'],['등급 이동행렬','crm_rating_migration'],
            ['LGD 구성요소','crm_lgd_component']]})],
  ['조기경보','B · 조기경보(EWS) — 신호·단계·조치',screenOf({
    lead:'차주 단위 조기경보 신호와 단계, 권고 조치. 에이전트가 순위를 제안하고 사람이 결정한다.',
    charts:root=>{if(DOMAIN_CHARTS['PRD-CRM'])DOMAIN_CHARTS['PRD-CRM'](root)},
    tables:[['조기경보 신호','crm_ews_signal']]})],
  ['가격검증·IPV','C · 독립가격검증 — 거래·위험요소·IPV',screenOf({
    lead:'거래 원장, 위험요소 매핑, 독립가격검증 결과. 미해소 5일 초과는 상위보고 대상이다.',
    charts:root=>{if(DOMAIN_CHARTS['PRD-MKT'])
      {const ipv=D.data['mkt_ipv'];if(ipv){const i=frameIdx(ipv);
        const open=ipv.rows.filter(r=>r[i.is_break]);
        root.appendChild(hbars(open.sort((a,b)=>b[i.days_open]-a[i.days_open])
          .slice(0,8).map(r=>({label:`${r[i.trade_id]} · ${r[i.source]}`,
            value:r[i.days_open],sub:`차이 ${fmtMoney(r[i.diff])}`,
            tone:r[i.days_open]>=5?'bad':'warn'})),
          {title:'미해소 경과일 상위',money:false,
           src:srcMeta(ipv,`미해소 ${open.length}건`)}))}}},
    tables:[['거래 원장','mkt_trade'],['위험요소','mkt_risk_factor'],
            ['독립가격검증','mkt_ipv']]})],
  ['백테스팅','C · VaR 백테스팅 — 예외 달력·손익 대 경계',screenOf({
    lead:'일별 손익과 VaR 경계의 실측 대조. 예외는 신호등 구간 판정으로 이어진다.',
    charts:root=>{const bt=D.data['mkt_backtest_exception'];
      if(bt){root.appendChild(pnlChart(bt));root.appendChild(calheat(bt))}},
    tables:[['백테스팅 관측 원장','mkt_backtest_exception']]})],
  ['VaR·ES','C · VaR·기대손실(ES) 원장',screenOf({
    lead:'과거시뮬레이션 VaR·ES 산출 원장 — 백테스팅·소요자기자본의 원천이다.',
    autochart:[['측정치별 금액','mkt_var_es',['measure','confidence'],'value']],
    tables:[['VaR·ES','mkt_var_es']]})],
  ['손실·회수','D · 운영손실 — 사건·회수·자본',screenOf({
    lead:'내·외부 손실사건, 회수, 운영리스크 소요자본. 총손실 → 적격회수 → 순손실 순서로 읽는다.',
    charts:root=>{if(DOMAIN_CHARTS['PRD-OPR'])DOMAIN_CHARTS['PRD-OPR'](root)},
    tables:[['손실사건 원장','opr_loss_event'],['회수 원장','opr_recovery'],
            ['운영리스크 자본','opr_capital']]})],
  ['KRI·통제','D · KRI·통제 — 지표·통제·경보정책',screenOf({
    lead:'핵심리스크지표와 통제 원장, 그리고 경보가 떴을 때 무엇을 해야 하는지의 정책 바인딩.',
    autochart:[['통제 증빙 상태','opr_control',['evidence_status'],null,{money:false}]],
    tables:[['핵심리스크지표','opr_kri'],['통제 원장','opr_control'],
            ['경보·조치 정책','gov_alert_policy']]})],
  ['NCR·건전성','S · 증권 건전성 — NCR·재무·적기시정조치',screenOf({
    lead:'순자본비율(NCR) 구성과 증권 건전성 원장 — 은행 BIS와 분모·분자·규정 체계가 완전히 다르다.',
    autochart:[['NCR 구성요소별 금액','ncr_component',['category','component'],'amount']],
    tables:[['NCR 구성','ncr_component'],['재무상태','pru_balance_sheet'],
            ['유동성 비율','pru_liquidity_ratio'],['경영실태평가(CAMEL)','pru_camel'],
            ['적기시정조치','pru_prompt_action']]})],
  ['시장 RWA','C · 시장리스크 위험가중자산 — 소요자기자본 서식·VaR/ES 원장',screenOf({
    lead:'시장리스크 소요자기자본 서식(B2326)과 그 원천인 VaR·ES 원장. 서식 라인마다 산식·규정 근거가 붙어 있다.',
    forms:['BR-05'],
    tables:[['VaR·ES 원장','mkt_var_es']]})],
  ['운영 RWA','D · 운영리스크 위험가중자산 — 소요자기자본 서식·산출방법',screenOf({
    lead:'운영리스크 소요자기자본 서식(BA2325-1)과 산출방법별 자본·위험가중자산 원장.',
    charts:root=>{const f=D.data['opr_capital'];
      if(!f)return;const i=frameIdx(f);
      root.appendChild(hbars(f.rows.map(r=>({
        label:'산출방법 '+r[i.method],value:r[i.rwa],
        sub:'소요자본 '+fmtMoney(r[i.capital])})),
        {title:'산출방법별 위험가중자산',src:srcMeta(f)}))},
    forms:['BR-06'],
    tables:[['운영리스크 자본 원장','opr_capital']]})],
  ['집합투자증권','CIU · 집합투자증권 — 모펀드·편입자산·운용지침 (CRE60)',screenOf({
    lead:'모펀드 마스터와 편입자산·운용지침을 분리해 LTA·MBA 를 둘 다 산출한다. LTA 는 편입자산을 직접 보유한 것처럼, MBA 는 운용지침 한도까지 투자했다고 가정하며, 정보가 부족하면 1250% fallback 이다.',
    autochart:[['펀드별 채택 위험가중자산','rwa_fund_result',['fund_name'],'adopted_rwa'],
               ['자산군별 편입 시가','rdm_fund_holding',['asset_class'],'market_value']],
    tables:[['펀드 마스터','rdm_fund_master'],['편입자산 (LTA 입력)','rdm_fund_holding'],
            ['운용지침 한도 (MBA 입력)','rdm_fund_mandate'],
            ['위험가중자산 — 세 방법·채택값','rwa_fund_result']]})],
  ['파생상품','DRV · 파생 마스터·기초자산·넷팅집합 (CRE52 SA-CCR)',screenOf({
    lead:'거래 마스터와 기초자산(다리)을 분리해 SA-CCR EAD 와 시장리스크 민감도를 둘 다 낸다. SA-CCR 엔진은 기존 risk_lib/ccr.py 를 그대로 쓴다 — 기초자산의 자산군 어휘가 그 엔진의 감독계수 키와 같다.',
    autochart:[['거래상대방별 명목','rdm_derivative_master',['counterparty'],'notional'],
               ['자산군별 명목','rdm_derivative_underlying',['asset_class'],'notional']],
    tables:[['파생 마스터','rdm_derivative_master'],['기초자산 (다리)','rdm_derivative_underlying'],
            ['넷팅집합','rdm_netting_set'],['FRTB 위험군별 민감도','mkt_derivative_sensitivity']]})],
  ['유동화','SEC · 유동화 딜·트렌치·풀 (CRE40~45 SA·ERBA·IRBA)',screenOf({
    lead:'딜 마스터와 트렌치·기초자산 풀을 분리해 SEC-SA·ERBA·IRBA 를 모두 산출하고 CRE40.41 계층(IRBA→ERBA→SA)으로 채택한다. 위험가중 하한은 15%, STC 선순위는 10%다.',
    autochart:[['딜별 보유 위험가중자산','rwa_sec_result',['deal_name'],'adopted_rwa'],
               ['트렌치별 보유액','rdm_sec_tranche',['tranche_name'],'holding_amount']],
    tables:[['유동화 딜 마스터','rdm_sec_master'],['트렌치','rdm_sec_tranche'],
            ['기초자산 풀','rdm_sec_pool'],['위험가중자산 — 세 방법·채택값','rwa_sec_result']]})],
  ['집계 원장','AGG · 도메인별 익스포저 집계 — 축이 도메인마다 다르다',screenOf({
    lead:'도메인마다 집계 축과 필요 컬럼이 다르다. 하나의 원장을 각자 집계하면 같은 "익스포저 합"이 도메인마다 달라지고 어느 쪽이 맞는지 사후에 알 수 없다 — 그래서 집계를 원장으로 고정했다. 신용·ALM 집계의 EAD 합은 익스포저 원장 총계와 일치한다.',
    autochart:[['자산군별 익스포저(신용 축)','agg_credit_exposure',['asset_class'],'ead'],
               ['리프라이싱 구간별 익스포저(ALM 축)','agg_alm_exposure',['repricing_bucket'],'ead']],
    tables:[['신용 집계','agg_credit_exposure'],['시장 집계','agg_market_exposure'],
            ['운영손실 집계','agg_operational_loss'],['ALM 집계','agg_alm_exposure'],
            ['위기상황 집계','agg_stress_exposure']]})],
  ['상업성','$ · 사업성 — 견적·ROI·Funnel (규제 산출물 아님)',commercial],
  ['시뮬레이션','SIM · 자본비율 영향도 — 설명용 산술 (승인·제출값 아님)',simulation],
  ['한도','LIM · 다차원 한도·소진율',limitsScreen],
  ['오버레이','OVR · 수동조정(오버레이) — 인간 수정의 통제된 기록',overlay],
  ['역스트레스','RST · 역방향 위기상황 — 자본 임계를 뚫는 심도',reverseStress],
  ['시나리오 설정','SET · 위기상황 시나리오 설정 — 축·심도·신규 제안',scenarioScreen],
  ['코드 마스터','SET · 코드 마스터 관리 — 정렬 정본',codeMasterAdmin],
  ['코드 매핑','SET · 계정·상품 코드 × 리스크 대상·특성 매핑',codeScope],
  ['모형 인벤토리','MDL · 모형 인벤토리 — 전 도메인 (신용·시장·ALM·위기·기후·전사)',modelInventory],
  ['검증 일정','MDL · 모형 검증 일정 — 주기·경과·의존·한계',modelValidationSchedule],
  ['모형리스크','MDL · 모형리스크 관리 — 등급별 거버넌스·운영 상태',modelRiskGovernance],
  ['변별력·안정성','MDL · 신용모형 성능 — Gini·KS·PSI',modelPerformance],
  ['등급 보정','MDL · 등급 보정 — 예측 PD 대 실측 부도율 (O/E)',modelCalibration],
  ['산출 방법론','SET · 산출 방법론 — LTA/MBA · SEC 계층 선택',methodology],
  ['금리리스크','E · 은행계정 금리리스크(IRRBB) — 충격·갭',rateRisk],
  ['유동성리스크','E · 유동성리스크 — LCR·NSFR',liquidityRisk],
];

/* 메뉴 트리 — 그룹은 시각적 계층일 뿐, 리프 순서가 화면의 정체다.
   앞 4개 리프(콕핏·정형·비정형·A RDM) 순서는 바꾸지 않는다. */
/* 항목은 리프 라벨(문자열) 또는 [하위그룹, [...]] — 트리는 재귀로 그린다. */
/* 부문 마커(A/B/C…·Δ)는 메뉴에서 뺀다 — 트리 들여쓰기가 이미 부문을
   말한다. 부문 개요는 2레벨 리프-부모, 마커 없던 세부화면은 3레벨이다. */
const NAVGROUPS=[
  ['통제센터',['콕핏','시뮬레이션','한도']],
  ['조회·컴포저',['정형 조회','비정형 UI']],
  /* 모형은 신용에만 있지 않다 — 도메인 축으로 따로 세운다(사용자 지적).
     원장이 crm_ 스키마에 산다는 것과 신용 모형이라는 것은 다른 말이다. */
  ['모형',[
    ['모형 인벤토리',['검증 일정','모형리스크']],
    ['신용모형',['변별력·안정성','등급 보정','등급 전이']],
  ]],
  ['리스크데이터',[
    ['RDM',['원천·계약','DQ·대사','예외·조치','담보·보증','집계 원장']],
    ['선행 원장',['집합투자증권','파생상품','유동화']],
  ]],
  ['위험가중자산(RWA)',[
    ['신용',['조기경보','신용 RWA','ECL']],
    ['시장',['가격검증·IPV','백테스팅','VaR·ES','시장 RWA']],
    ['운영',['손실·회수','KRI·통제','운영 RWA']],
  ]],
  ['ALM·위기상황',[
    ['ALM',['금리리스크','유동성리스크']],
    ['위기상황',['시나리오 설정','역스트레스']],
  ]],
  ['증권 건전성',['NCR·건전성']],
  ['보고',['감독보고']],
  ['검증·거버넌스',[
    ['검증',['요건 추적']],
    '에이전트','변경','오버레이',
  ]],
  ['사업성',['상업성']],
  ['데이터·설정',[
    '데이터모델',
    ['⚙ 설정',['코드 마스터','코드 매핑','산출 방법론']],
  ]],
];

const TABS=[
  ['콕핏','00 전사 리스크 콕핏',cockpit],
  ['정형 조회','정형 조회 스튜디오 · Governed Query',structured],
  ['비정형 UI','비정형 Adaptive UI Composer',adaptive],
  ['RDM','A · 리스크데이터 — 유연집계·가공·정합성·계보',
   r=>domain(r,'PRD-RDM',null,'원천계약부터 표준 매핑, 버전형 가공, 다차원 집계, DQ·대사, 승인 스냅샷까지 통제한다.')],
  ['신용','B · 신용리스크 — 모형·파라미터·회수·경보',
   r=>domain(r,'PRD-CRM',null,'등급·PD/LGD/EAD·부도/회수 품질·담보배분·조기경보를 연결한다.')],
  ['신용 RWA','B · 신용리스크 위험가중자산',
   r=>domain(r,'PRD-RWA',null,'표준방법 구간별·내부등급법 PD 구간별로 분해해 업무보고서 라인과 같은 입도로 둔다.')],
  ['ECL','B · 기대신용손실',
   r=>domain(r,'PRD-ECL',null,'Stage 전이·SICR 트리거·충당금 증감 브리지를 분해한다.')],
  ['시장','C · 시장리스크 — 가격평가·위험요소·ES·백테스팅',
   r=>domain(r,'PRD-MKT',null,'벤치마크 가격·시장데이터 계보·위험요소·ES·백테스팅을 연결한다.')],
  ['운영','D · 운영리스크 — 손실데이터·PSMOR',
   r=>domain(r,'PRD-OPR',null,'내·외부 사건·회수·KRI·PSMOR 원칙 매핑을 연결한다. 매핑이며 준수 인증이 아니다.')],
  ['ALM','E · ALM — IRRBB·LCR·NSFR',
   r=>domain(r,'PRD-ALM',null,'항목별 잔액·적용률·가중 후 금액까지 분해해 규제 비율의 원인을 추적한다.')],
  ['위기상황','E · 통합위기상황분석 — 심각도별 전 단계 산출과정',stressDeepDive],
  ['감독보고','R · 금감원 업무보고서',regulatory],
  ['검증','F · 검증 두 층 — 자체검증(2선) · 상시 독립검증(3선)',validation],
  ['에이전트','G · 에이전트 운영 · 권한 · Kill Switch',agents],
  ['변경','Δ · 리스크 변경 팩토리',changes],
  ['데이터모델','정규 데이터모델 카탈로그',catalogView],
  ['요건 추적','REQ · v9.6.0 업무요건 추적 — 131건 대비 구현 재고조사',reqTrace],
  ...DETAIL_SCREENS.map(([lab,title,fn])=>[lab,title,fn]),
  ['⚙ 설정','⚙ · 설정 — 기준일 · 표시명 · 코드 매핑 · 시나리오',settings],
];

let repaintAll=()=>{};                   /* boot에서 실체가 채워진다 */

function setRun(a){
  /* 승인·이력은 **실행에 속한다**. proposal_id는 (view, 프롬프트)의 해시라
     실행이 바뀌어도 같으므로, 그대로 두면 이전 기준일 데이터로 받은 승인이
     새 기준일 화면에 "승인 적용"으로 뜬다 — 다른 산출물에 승인 도장이
     옮겨 찍히는 것이다. 실행별로 보관하고 전환 시 맞바꾼다. */
  STATE.byRun=STATE.byRun||{};
  STATE.byRun[D.meta.asof]={approved:STATE.approved,history:STATE.history};
  const kept=STATE.byRun[a]||{approved:{},history:{}};
  STATE.approved=kept.approved;STATE.history=kept.history;

  D=RUNS[a];
  $('#chip-run').textContent=D.meta.run_id;
  $('#chip-digest').textContent='지문 '+D.meta.digest.slice(0,12);
  $('#chip-seed').textContent='시드 '+D.meta.seed;
  $('#chip-rows').textContent=
    `테이블 ${D.meta.n_tables}장 · ${D.meta.n_rows.toLocaleString()}행`;
  const fa=$('#foot-asof');if(fa)fa.textContent=a;
  const fs=$('#foot-seed');if(fs)fs.textContent=String(D.meta.seed);
  document.title='RYNTA 에이전틱 UI 스튜디오 · '+a;
  repaintAll();
}

function boot(){
  const nav=$('nav'),main=$('main');
  const byLabel={};TABS.forEach(t=>{byLabel[t[0]]=t});
  let first=null,idx=0;
  function addLeaf(label,depth,collect){
    const t=byLabel[label];
    if(!t)return;
    const [,title,fn]=t;
    const b=el('button','lvl'+depth,label);
    const s=el('section');s.id='tab'+(idx++);
    b.onclick=()=>{
      [...nav.querySelectorAll('button')].forEach(x=>x.classList.remove('on'));
      [...main.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');s.classList.add('on');
      if(!s.dataset.done){const h=el('h2',null,title);s.appendChild(h);fn(s);
        insertSummary(label,s);
        s.dataset.done='1'}
      window.scrollTo({top:0});
    };
    collect.push(b);nav.appendChild(b);main.appendChild(s);
    if(!first)first=b;
  }
  function addGroup(gname,items,depth){
    const gh=el('div','navgroup'+(depth?' sub lvl'+depth:''),gname);
    const under=[];                      /* 이 그룹 아래 전부 — 접기 대상 */
    gh.onclick=()=>{gh.classList.toggle('closed');
      const closed=gh.classList.contains('closed');
      under.forEach(x=>{x.hidden=closed;
        if(x.classList&&x.classList.contains('navgroup'))
          x.classList.toggle('closed',closed)})};
    nav.appendChild(gh);
    items.forEach(item=>{
      if(typeof item==='string'){addLeaf(item,depth+1,under)}
      else{const [sub,subItems]=item;
        if(byLabel[sub]){
          /* 리프-부모 — 화면을 여는 항목이면서 자식(3레벨)을 거느린다 */
          addLeaf(sub,depth+1,under);
          subItems.forEach(ch=>addLeaf(ch,depth+2,under));
        } else {
          const before=nav.children.length;
          addGroup(sub,subItems,depth+1);
          for(let k=before;k<nav.children.length;k++)under.push(nav.children[k]);
        }}
    });
  }
  NAVGROUPS.forEach(([gname,items])=>addGroup(gname,items,0));
  if(first)first.onclick();
  /* 사유 입력은 **화면 안**에서 받는다. prompt()는 샌드박스 iframe(임베드·
     아티팩트)에서 차단되어 null을 돌려주고, 그러면 통제가 아무 반응 없이
     죽는다 — 있는 것처럼 보이면서 작동하지 않는 통제가 제일 나쁘다. */
  const kb=$('.kill'), bar=$('.killbar'), rin=$('#killreason');
  const ksc=$('#killscope');
  ['전사'].concat([...new Set(Object.values(D.view_meta).map(v=>v.domain))].sort())
    .forEach(d=>{const o=el('option');o.value=d;o.textContent=d;
      ksc.appendChild(o)});
  const repaint=()=>{
    [...main.children].forEach(x=>{x.dataset.done='';x.innerHTML=''});
    [...nav.querySelectorAll('button')].forEach(b=>{
      if(b.classList.contains('on'))b.onclick()});
  };
  repaintAll=repaint;

  /* 기준일 전환 — 실은 실행 사이의 전환이다. 옵션은 실행 목록에서 나온다. */
  const asel=$('#asofsel');
  Object.keys(RUNS).sort().forEach(a=>{
    const o=el('option');o.value=a;o.textContent=a;asel.appendChild(o)});
  asel.value=D.meta.asof;
  asel.onchange=()=>setRun(asel.value);

  const engage=()=>{
    const reason=(rin.value||'').trim();
    if(!reason){rin.focus();return;}        /* 사유 없는 정지는 없다 */
    STATE.killed=true;STATE.killReason=reason;
    STATE.killScope=ksc.value||'전사';       /* 범위형 정지 (PLT-016) */
    kb.textContent='Kill Switch 해제'+(STATE.killScope==='전사'?''
      :' · '+STATE.killScope);
    kb.classList.add('on');
    bar.hidden=true;repaint();
  };
  kb.onclick=()=>{
    if(STATE.killed){
      STATE.killed=false;kb.textContent='Kill Switch';kb.classList.remove('on');
      bar.hidden=true;repaint();return;
    }
    bar.hidden=!bar.hidden;
    if(!bar.hidden){rin.focus();rin.select();}
  };
  $('.killgo').onclick=engage;
  $('.killno').onclick=()=>{bar.hidden=true;kb.focus();};
  rin.onkeydown=e=>{
    if(e.key==='Enter')engage();
    if(e.key==='Escape'){bar.hidden=true;kb.focus();}
  };
}
boot();
"""


def render(studios: Studio | list[Studio]) -> str:
    """한 개 이상의 실행 스냅샷을 한 화면으로 그린다.

    기준일 전환은 **미리 산출해 실은 실행 사이의 전환**이다. 화면은 계산기가
    아니므로 새 기준일을 즉석에서 만들 수 없다 — 만들 수 있는 것처럼 보이면
    검증 안 된 수치가 화면에 생긴다. 실행마다 자기 run_id·지문·검증 상태를
    갖고, 전환하면 그 실행의 것으로 전부 바뀐다.
    """
    ss = [studios] if isinstance(studios, Studio) else sorted(
        studios, key=lambda x: x.asof)
    runs = {s.asof: _payload(s) for s in ss}
    primary = ss[-1].asof                    # 최신 기준일이 기본 화면
    m = runs[primary]["meta"]
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RYNTA 에이전틱 UI 스튜디오 · {html.escape(primary)}</title>
<style>{_CSS}</style></head><body>
<div class="topbar">
<header>
  <div class="brand">RYNTA <span>·</span> 에이전틱 UI 스튜디오</div>
  <label class="hchip" for="asofsel">기준일
    <select id="asofsel" class="sel asofsel"></select></label>
  <span class="hchip" id="chip-run">{html.escape(m['run_id'])}</span>
  <span class="hchip" id="chip-digest">지문 {html.escape(m['digest'][:12])}</span>
  <span class="hchip" id="chip-seed">시드 {m['seed']}</span>
  <span class="hchip" id="chip-rows">테이블 {m['n_tables']}장 · {m['n_rows']:,}행</span>
  <span class="hchip">Read-only · PII Mask</span>
  <button class="kill">Kill Switch</button>
</header>
<div class="killbar" hidden>
  <label for="killscope">범위</label>
  <select id="killscope" class="sel"></select>
  <label for="killreason">비상정지 사유 (필수)</label>
  <input id="killreason" type="text"
         value="시장데이터 지연 확인 중 신규 재계산 보류">
  <button class="killgo">정지</button>
  <button class="killno">취소</button>
  <span class="killnote">중요 범위는 운영에서 독립된 2차 확인이 추가로 필요하다.</span>
</div>
</div>
<div class="layout">
<nav aria-label="메뉴"></nav>
<main></main>
</div>
<footer>
  결정론적 엔진 · 제안 전용 에이전트 · 사람의 최종 승인 권한 · 증빙 계보.
  화면의 모든 값은 합성 포트폴리오에서 <code>run_pipeline(seed=<span
  id="foot-seed">{m['seed']}</span>,
  asof='<span id="foot-asof">{html.escape(primary)}</span>')</code>로 산출한
  것이며 실제 기관 수치가 아니다.
  에이전트는 신용등급·여신승인, PD·LGD·EAD 등 핵심 위험파라미터, ECL·충당금,
  RWA·BIS 비율, 감독제출·공시, 경영조치를 자동확정하지 않는다.
  <br>약어: RDM(리스크데이터관리) · RWA(위험가중자산) · ECL(기대신용손실) ·
  ALM(자산부채관리) · IRRBB(은행계정 금리리스크) · LCR(유동성커버리지비율) ·
  NSFR(순안정자금조달비율) · IPV(독립가격검증) · SICR(신용위험 유의적 증가) ·
  DQ(데이터품질) · AST(구문트리) · PSMOR(운영리스크 건전관리 원칙).
</footer>
<script>window.__RYNTA_RUNS__={json.dumps(runs, ensure_ascii=False, default=str,
                                          separators=(",", ":"))};
window.__RYNTA__=window.__RYNTA_RUNS__[{json.dumps(primary)}];</script>
<script>{_ENGINE_JS}</script>
<script>{_JS}</script>
</body></html>"""


def write_app(s: Studio | list[Studio], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(s), encoding="utf-8")
    return p
