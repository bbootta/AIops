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


def _frame(df: pd.DataFrame, limit: int = PREVIEW_ROWS) -> dict:
    head = df.head(limit)
    return {
        "columns": [str(c) for c in df.columns],
        "rows": [[_cell(v) for v in row] for row in head.itertuples(index=False)],
        "total": int(len(df)),
        "shown": int(len(head)),
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

    previews = {name: _frame(df) for name, df in t.items()
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
            data[tref] = _frame(df, budget)

    plans = []
    for p in s.plans:
        res = s.plan_results.get(p.plan_id, pd.DataFrame())
        plans.append({
            "plan_id": p.plan_id, "view_id": p.view_id, "intent": p.intent,
            "utterance": p.utterance, "population": p.population,
            "ast": p.condition_ast, "policy": p.policy, "hash": p.query_hash,
            "status": p.status, "block_reason": p.block_reason,
            "n_rows": p.n_rows, "result": _frame(res, 8),
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
                preview = _frame(sub, min(pr.row_limit, 10))
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
        "views": _frame(t["ui_view"], 10_000),
        "field_policy": _frame(t["ui_field_policy"], 10_000),
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
        "form_checks": _frame(t["reg_form_check"], 200),
        "agents": _frame(t["agent_registry"], 100),
        "activity": _frame(t["agent_activity"], 100),
        "killswitch": _frame(t["agent_killswitch"], 50),
        "evidence_nodes": _frame(t["gov_evidence_node"], 50),
        "evidence_edges": _frame(t["gov_evidence_edge"], 50),
        "approvals": _frame(t["gov_approval"], 100),
        "changes": _frame(t["chg_change_request"], 50),
        "change_impacts": _frame(t["chg_impact_map"], 200),
        "change_tests": _frame(t["chg_regression_test"], 100),
        "reconciliation": _frame(t["rdm_reconciliation"], 50),
        "contracts": _frame(t["rdm_source_contract"], 50),
        "canonical_map": _frame(t["rdm_canonical_map"], 200),
        "validation": _frame(t["val_check"], 400),
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
        "independent_targets": _frame(t["val_independent_target"], 50),
        "domains": sorted({r["product"] for r in catalog_rows}),
    }


# ---------------------------------------------------------------- HTML

_CSS = """
:root{--bg:#0d1117;--panel:#151b23;--panel2:#1c232c;--line:#262d38;
--text:#e6edf3;--muted:#8b95a5;--accent:#4a9eff;--good:#3fb950;--warn:#d29922;
--bad:#f85149;--chip:#21262d}
@media (prefers-color-scheme:light){:root{--bg:#f6f8fa;--panel:#fff;
--panel2:#f0f3f6;--line:#d8dee4;--text:#1f2328;--muted:#636c76;--chip:#eaeef2}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:13px/1.55 "Malgun Gothic","맑은 고딕",-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent)}
header{position:sticky;top:0;z-index:20;background:var(--panel);
border-bottom:1px solid var(--line);padding:10px 18px;
display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.brand{font-weight:700;font-size:15px;letter-spacing:.02em}
.brand span{color:var(--accent)}
.hchip{background:var(--chip);border:1px solid var(--line);border-radius:999px;
padding:3px 10px;font-size:11px;color:var(--muted)}
.kill{margin-left:auto;background:transparent;border:1px solid var(--bad);
color:var(--bad);border-radius:6px;padding:5px 12px;font-size:11px;cursor:pointer}
nav{display:flex;gap:2px;flex-wrap:wrap;padding:8px 18px;background:var(--panel2);
border-bottom:1px solid var(--line);position:sticky;top:47px;z-index:19}
nav button{background:transparent;border:1px solid transparent;color:var(--muted);
padding:6px 11px;border-radius:6px;cursor:pointer;font-size:12px;font-family:inherit}
nav button:hover{color:var(--text);background:var(--chip)}
nav button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
main{padding:18px;max-width:1500px;margin:0 auto}
section{display:none}section.on{display:block}
h2{font-size:17px;margin:0 0 4px}
.lead{color:var(--muted);font-size:12px;margin:0 0 16px;max-width:96ch}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:14px}
.card h3{margin:0 0 8px;font-size:13px}
.kpi .lab{font-size:11px;color:var(--muted)}
.kpi .val{font-size:22px;font-weight:700;margin:5px 0 2px}
.kpi .sub{font-size:11px;color:var(--muted)}
.kpi .ln{font-size:10px;color:var(--accent);margin-top:6px}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:11.5px;min-width:520px}
th{background:var(--panel2);text-align:left;padding:7px 9px;font-weight:600;
border-bottom:1px solid var(--line);white-space:nowrap;position:sticky;top:0}
td{padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.sub td{background:var(--panel2);font-weight:600}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:10px;
border:1px solid var(--line);background:var(--chip)}
.pill.good{border-color:var(--good);color:var(--good)}
.pill.warn{border-color:var(--warn);color:var(--warn)}
.pill.bad{border-color:var(--bad);color:var(--bad)}
.meta{font-size:11px;color:var(--muted);margin:6px 0}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.step{background:var(--panel2);border:1px solid var(--line);border-radius:7px;
padding:7px 10px;min-width:130px}
.step b{display:block;font-size:10px;color:var(--muted);font-weight:600}
.mono{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:11px}
.bar{height:9px;background:var(--chip);border-radius:5px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--accent)}
.sel{background:var(--panel2);color:var(--text);border:1px solid var(--line);
border-radius:6px;padding:6px 9px;font-family:inherit;font-size:12px}
.split{display:grid;gap:12px;grid-template-columns:minmax(260px,1fr) 2.2fr}
@media(max-width:900px){.split{grid-template-columns:1fr}}
.list{max-height:520px;overflow:auto;border:1px solid var(--line);
border-radius:8px}
.list button{display:block;width:100%;text-align:left;background:transparent;
border:none;border-bottom:1px solid var(--line);color:var(--text);
padding:8px 10px;cursor:pointer;font-family:inherit;font-size:12px}
.list button:hover{background:var(--chip)}
.list button.on{background:var(--accent);color:#fff}
.list button small{display:block;color:var(--muted);font-size:10px}
.list button.on small{color:#dbeafe}
.flow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:10px 0}
.node{background:var(--panel2);border:1px solid var(--line);border-radius:8px;
padding:8px 11px;min-width:120px}
.node b{display:block;font-size:10px;color:var(--muted)}
.arrow{color:var(--muted)}
.note{border-left:3px solid var(--accent);background:var(--panel2);
padding:9px 12px;border-radius:0 8px 8px 0;font-size:11.5px;color:var(--muted);
margin:12px 0}
footer{padding:20px 18px;color:var(--muted);font-size:11px;
border-top:1px solid var(--line);margin-top:24px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start;margin:10px 0}
.input{flex:1;min-width:280px;background:var(--panel);color:var(--text);
border:1px solid var(--line);border-radius:6px;padding:8px 11px;
font-family:inherit;font-size:12.5px}
.input:focus{outline:none;border-color:var(--accent)}
textarea.input{resize:vertical;line-height:1.5}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}
.chip{background:var(--chip);border:1px solid var(--line);color:var(--muted);
border-radius:999px;padding:4px 11px;font-size:11px;cursor:pointer;
font-family:inherit;max-width:100%;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.chip:hover{color:var(--text);border-color:var(--accent)}
.btn{background:var(--chip);border:1px solid var(--line);color:var(--text);
border-radius:6px;padding:6px 13px;font-size:12px;cursor:pointer;
font-family:inherit}
.btn:hover:not(:disabled){border-color:var(--accent)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.spark{width:100%;height:120px;display:block}
.kill.on{background:var(--bad);color:#fff}
.blockhead{display:flex;align-items:center;gap:10px;width:100%;
background:transparent;border:none;color:var(--text);cursor:pointer;
font-family:inherit;font-size:13px;font-weight:600;padding:2px 0;text-align:left}
.blockhead small{margin-left:auto;color:var(--muted);font-weight:400;font-size:11px}
.bnum{background:var(--accent);color:#fff;border-radius:5px;padding:2px 7px;
font-size:11px;font-variant-numeric:tabular-nums}
.chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.listsec{background:var(--panel2);border-bottom:1px solid var(--line);
padding:6px 10px;font-size:11px;font-weight:600;color:var(--muted)}
"""

_JS = r"""
const D = window.__RYNTA__;
const $ = (s,r=document)=>r.querySelector(s);
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;
if(x!=null)e.textContent=x;return e};
const esc=s=>String(s==null?'':s);
const fmtNum=v=>typeof v==='number'
  ? (Math.abs(v)>=1000?v.toLocaleString('ko-KR',{maximumFractionDigits:0})
     :v.toLocaleString('ko-KR',{maximumFractionDigits:6})) : esc(v);

function table(f,{numeric=true,rowClass=null}={}){
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  const isNum=f.columns.map((_,i)=>numeric&&f.rows.some(r=>typeof r[i]==='number'));
  f.columns.forEach((c,i)=>{const h=el('th',isNum[i]?'num':null,c);
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

  const c1=el('div','card');c1.appendChild(el('h3',null,'증빙 계보 · 7단계'));
  const flow=el('div','flow');
  D.evidence_nodes.rows.forEach((r,i)=>{
    const [ , nid, stage, label, ref, status]=r;
    const n=el('div','node');n.appendChild(el('b',null,`0${i+1} ${stage}`));
    n.appendChild(el('div',null,label));
    const s=el('div');s.appendChild(pill(status,
      status==='완결'?'good':status==='검토'?'warn':'bad'));
    n.appendChild(s);flow.appendChild(n);
    if(i<D.evidence_nodes.rows.length-1)flow.appendChild(el('span','arrow','→'));
  });
  c1.appendChild(flow);
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
const STATE = {killed: false, approved: {}, history: {}};

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
  const killed=STATE.killed;
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
    c.appendChild(table({columns:res.columns,rows:res.rows,
      total:plan.n_rows,shown:res.rows.length}));
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
    const cols=v.fields.filter(f=>f.permitted&&f.masking==='none')
      .slice(0,4).map(f=>f.korean);
    const fallback=[
      `${cols.slice(0,2).join('과 ')} 기여도를 막대차트로 보여주고 아래에 검토 표를 배치해줘. 상위 10건.`,
      `${cols.slice(0,3).join(', ')} 추이를 보여줘`,
      `${cols.slice(0,2).join('와 ')}를 카드로 보여줘`];
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
  bApp.disabled=!pr.all_pass;
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

  const previewBox=el('div');
  c.appendChild(previewBox);
  pane.appendChild(c);

  function draw(applied){
    previewBox.innerHTML='';
    if(!pr.all_pass){previewBox.appendChild(el('div','note',
      '정책검증 미통과 — 미리보기를 그리지 않는다.'));return}
    previewBox.appendChild(el('h3',null,
      applied?'승인 적용 화면':'미리보기 (운영 반영 전)'));
    renderBlocks(previewBox, pr, v);
  }
  bPrev.onclick=()=>draw(false);
  bApp.onclick=()=>{
    try{
      const a=RY.approve(pr,'리스크관리부장');
      (STATE.history[v.view_id]=STATE.history[v.view_id]||[])
        .push(STATE.approved[v.view_id]||null);
      STATE.approved[v.view_id]=a;
      rerun();
    }catch(e){alert(e.message)}
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
  const cols=pr.columns.filter(c=>c in idx);
  const numCol=cols.find(c=>frame.rows.some(r=>typeof r[idx[c]]==='number'));
  const labCol=cols.find(c=>c!==numCol&&frame.rows.some(r=>typeof r[idx[c]]==='string'));
  let rows=frame.rows.slice();
  if(numCol)rows.sort((a,b)=>(b[idx[numCol]]||0)-(a[idx[numCol]]||0));
  rows=rows.slice(0,pr.row_limit);
  const sub={columns:cols,rows:rows.map(r=>cols.map(c=>r[idx[c]])),
             total:frame.total,shown:rows.length};

  /* 블록 순서는 프롬프트에 나온 순서 그대로다 — 사용자가 "위에 차트, 아래에 표"
     라고 쓰면 그 순서로 배치돼야 레이아웃이 바뀐 것으로 읽힌다. */
  pr.blocks.forEach(([viz,title])=>{
    if(viz==='kpi'){
      const g=el('div','grid');
      cols.slice(0,4).forEach(cName=>{
        const j=idx[cName];
        const nums=rows.map(r=>r[j]).filter(x=>typeof x==='number');
        const card=el('div','card kpi');
        card.appendChild(el('div','lab',cName));
        card.appendChild(el('div','val',nums.length
          ? fmtNum(nums.reduce((a,b)=>a+b,0)) : String(rows.length)+'행'));
        card.appendChild(el('div','sub',nums.length?'합계':'건수'));
        g.appendChild(card)});
      box.appendChild(g);
    } else if(viz==='bar'&&numCol){
      const max=Math.max(...rows.map(r=>Math.abs(r[idx[numCol]]||0)))||1;
      const w=el('div');
      w.appendChild(el('div','meta',`${title} · ${numCol}`));
      rows.slice(0,12).forEach((r,i)=>{
        const line=el('div');line.style.margin='6px 0';
        line.appendChild(el('div','meta',
          (labCol?esc(r[idx[labCol]]):'#'+(i+1))+' · '+fmtNum(r[idx[numCol]])));
        const b=el('div','bar'),f=el('i');
        f.style.width=(Math.abs(r[idx[numCol]]||0)/max*100).toFixed(1)+'%';
        b.appendChild(f);line.appendChild(b);w.appendChild(line)});
      box.appendChild(w);
    } else if(viz==='line'&&numCol){
      box.appendChild(sparkline(rows.map(r=>r[idx[numCol]]||0), title+' · '+numCol));
    } else {
      box.appendChild(table(sub));
    }
  });
}

function sparkline(values, title){
  const w=680,h=120,pad=6;
  const max=Math.max(...values,0),min=Math.min(...values,0);
  const span=(max-min)||1;
  const pts=values.slice(0,60).map((v,i,arr)=>{
    const x=pad+i*(w-2*pad)/Math.max(arr.length-1,1);
    const y=h-pad-((v-min)/span)*(h-2*pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`}).join(' ');
  const box=el('div');
  box.appendChild(el('div','meta',title));
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
  const colors=['#3fb950','#d29922','#f85149','#4a9eff'];
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

const TABS=[
  ['콕핏','00 전사 리스크 콕핏',cockpit],
  ['정형 조회','정형 조회 스튜디오 · Governed Query',structured],
  ['비정형 UI','비정형 Adaptive UI Composer',adaptive],
  ['A RDM','A · 리스크데이터 — 유연집계·가공·정합성·계보',
   r=>domain(r,'PRD-RDM',null,'원천계약부터 표준 매핑, 버전형 가공, 다차원 집계, DQ·대사, 승인 스냅샷까지 통제한다.')],
  ['B 신용','B · 신용리스크 — 모형·파라미터·회수·경보',
   r=>domain(r,'PRD-CRM',null,'등급·PD/LGD/EAD·부도/회수 품질·담보배분·조기경보를 연결한다.')],
  ['B RWA','B · 위험가중자산',
   r=>domain(r,'PRD-RWA',null,'표준방법 구간별·내부등급법 PD 구간별로 분해해 업무보고서 라인과 같은 입도로 둔다.')],
  ['B ECL','B · 기대신용손실',
   r=>domain(r,'PRD-ECL',null,'Stage 전이·SICR 트리거·충당금 증감 브리지를 분해한다.')],
  ['C 시장','C · 시장리스크 — 가격평가·위험요소·ES·백테스팅',
   r=>domain(r,'PRD-MKT',null,'벤치마크 가격·시장데이터 계보·위험요소·ES·백테스팅을 연결한다.')],
  ['D 운영','D · 운영리스크 — 손실데이터·PSMOR',
   r=>domain(r,'PRD-OPR',null,'내·외부 사건·회수·KRI·PSMOR 원칙 매핑을 연결한다. 매핑이며 준수 인증이 아니다.')],
  ['E ALM','E · ALM — IRRBB·LCR·NSFR',
   r=>domain(r,'PRD-ALM',null,'항목별 잔액·적용률·가중 후 금액까지 분해해 규제 비율의 원인을 추적한다.')],
  ['E 위기상황','E · 통합위기상황분석 — 심각도별 전 단계 산출과정',stressDeepDive],
  ['R 감독보고','R · 금감원 업무보고서',regulatory],
  ['F 검증','F · 검증 두 층 — 자체검증(2선) · 상시 독립검증(3선)',validation],
  ['G 에이전트','G · 에이전트 운영 · 권한 · Kill Switch',agents],
  ['Δ 변경','Δ · 리스크 변경 팩토리',changes],
  ['데이터모델','정규 데이터모델 카탈로그',catalogView],
];

function boot(){
  const nav=$('nav'),main=$('main');
  TABS.forEach(([label,title,fn],i)=>{
    const b=el('button',null,label);
    const s=el('section');s.id='tab'+i;
    b.onclick=()=>{
      [...nav.children].forEach(x=>x.classList.remove('on'));
      [...main.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');s.classList.add('on');
      if(!s.dataset.done){const h=el('h2',null,title);s.appendChild(h);fn(s);
        s.dataset.done='1'}
      window.scrollTo({top:0});
    };
    nav.appendChild(b);main.appendChild(s);
    if(i===0)b.onclick();
  });
  const kb=$('.kill');
  kb.onclick=()=>{
    if(!STATE.killed){
      const reason=prompt('비상정지 사유를 입력하세요 (필수). 중요 범위는 운영에서 '+
        '독립된 2차 확인이 추가로 필요합니다.','시장데이터 지연 확인 중 신규 재계산 보류');
      if(!reason)return;                    /* 사유 없는 정지는 없다 */
      STATE.killed=true;STATE.killReason=reason;
      kb.textContent='Kill Switch 해제';kb.classList.add('on');
    } else {
      STATE.killed=false;kb.textContent='Kill Switch';kb.classList.remove('on');
    }
    /* 정지 상태는 화면 전체에 즉시 반영된다 — 정형 조회 탭을 다시 그린다. */
    [...main.children].forEach(x=>{x.dataset.done='';x.innerHTML=''});
    [...nav.children].forEach((b,i)=>{if(b.classList.contains('on'))b.onclick()});
  };
}
boot();
"""


def render(s: Studio) -> str:
    d = _payload(s)
    m = d["meta"]
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RYNTA 에이전틱 UI 스튜디오 · {html.escape(m['asof'])}</title>
<style>{_CSS}</style></head><body>
<header>
  <div class="brand">RYNTA <span>·</span> 에이전틱 UI 스튜디오</div>
  <span class="hchip">기준일 {html.escape(m['asof'])}</span>
  <span class="hchip">{html.escape(m['run_id'])}</span>
  <span class="hchip">지문 {html.escape(m['digest'][:12])}</span>
  <span class="hchip">시드 {m['seed']}</span>
  <span class="hchip">테이블 {m['n_tables']}장 · {m['n_rows']:,}행</span>
  <span class="hchip">Read-only · PII Mask</span>
  <button class="kill">Kill Switch</button>
</header>
<nav></nav>
<main></main>
<footer>
  결정론적 엔진 · 제안 전용 에이전트 · 사람의 최종 승인 권한 · 증빙 계보.
  화면의 모든 값은 합성 포트폴리오에서 <code>run_pipeline(seed={m['seed']},
  asof='{html.escape(m['asof'])}')</code>로 산출한 것이며 실제 기관 수치가 아니다.
  에이전트는 신용등급·여신승인, PD·LGD·EAD 등 핵심 위험파라미터, ECL·충당금,
  RWA·BIS 비율, 감독제출·공시, 경영조치를 자동확정하지 않는다.
  <br>약어: RDM(리스크데이터관리) · RWA(위험가중자산) · ECL(기대신용손실) ·
  ALM(자산부채관리) · IRRBB(은행계정 금리리스크) · LCR(유동성커버리지비율) ·
  NSFR(순안정자금조달비율) · IPV(독립가격검증) · SICR(신용위험 유의적 증가) ·
  DQ(데이터품질) · AST(구문트리) · PSMOR(운영리스크 건전관리 원칙).
</footer>
<script>window.__RYNTA__={json.dumps(d, ensure_ascii=False, default=str,
                                     separators=(",", ":"))};</script>
<script>{_ENGINE_JS}</script>
<script>{_JS}</script>
</body></html>"""


def write_app(s: Studio, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(s), encoding="utf-8")
    return p
