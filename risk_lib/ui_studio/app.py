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
from risk_lib.ui_studio.studio import Studio

PREVIEW_ROWS = 12


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
        "form_id": b.spec.form_id, "form_name": b.spec.form_name,
        "frequency": b.spec.frequency, "citation": b.spec.citation,
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

/* ---- 정형 조회 스튜디오 ---- */
function structured(root){
  root.appendChild(el('p','lead',
    '자연어를 승인된 스키마·필드·연산자·권한으로 변환한다. 화면 열과 레이아웃은 고정하고 조회조건만 구성한다. '+
    '인식하지 못한 필드는 조용히 무시하지 않고 차단 사유로 남는다.'));
  const wrap=el('div','split');
  const list=el('div','list');
  const pane=el('div');
  D.plans.forEach((p,i)=>{
    const b=el('button');b.appendChild(document.createTextNode(p.intent));
    const s=el('small',null,`${p.view_id} · ${p.status==='validated'?'검증됨':'차단'} · ${p.n_rows.toLocaleString()}행`);
    b.appendChild(s);
    b.onclick=()=>{[...list.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');renderPlan(pane,p)};
    list.appendChild(b);
    if(i===0){b.classList.add('on');renderPlan(pane,p)}
  });
  wrap.appendChild(list);wrap.appendChild(pane);root.appendChild(wrap);
}
function renderPlan(pane,p){
  pane.innerHTML='';
  const c=el('div','card');
  c.appendChild(el('h3',null,'사용자 문장'));
  c.appendChild(el('div','mono',p.utterance));
  const st=el('div','steps');
  p.steps.forEach(([k,v])=>{const s=el('div','step');
    s.appendChild(el('b',null,k));s.appendChild(el('div',null,v));st.appendChild(s)});
  c.appendChild(st);
  const meta=el('div','meta');
  meta.appendChild(document.createTextNode('조회 지문 '+p.hash+' · '));
  meta.appendChild(pill(p.status==='validated'?'Read-only 실행':'차단',
    p.status==='validated'?'good':'bad'));
  c.appendChild(meta);
  c.appendChild(el('div','mono','AST: '+p.ast));
  if(p.block_reason){const n=el('div','note','차단 사유 — '+p.block_reason);
    c.appendChild(n)}
  c.appendChild(el('h3',null,`고정 컬럼 결과 · 모집단 ${p.n_rows.toLocaleString()}건`));
  c.appendChild(table(p.result));
  pane.appendChild(c);
}

/* ---- 비정형 Adaptive UI ---- */
function adaptive(root){
  root.appendChild(el('p','lead',
    '프롬프트는 UI 구성안만 만든다. 승인되지 않은 필드, 행 수준 개인정보, 규제산출 변경, 판단 확정은 하지 않는다. '+
    '세 검증을 모두 통과해야 사람이 승인할 수 있고, 승인 전에는 화면에 반영되지 않는다.'));
  D.proposals.forEach(p=>{
    const c=el('div','card');
    c.appendChild(el('h3',null,p.proposal_id+' · '+p.view_id));
    c.appendChild(el('div','mono',p.prompt));
    const st=el('div','steps');
    p.checks.forEach(([k,v])=>{const s=el('div','step');
      s.appendChild(el('b',null,k));const d=el('div');d.appendChild(ok(v));
      s.appendChild(d);st.appendChild(s)});
    c.appendChild(st);
    const m=el('div','meta');
    m.appendChild(document.createTextNode('제안 레이아웃 — '));
    m.appendChild(el('span','mono',p.layout));
    c.appendChild(m);
    const s2=el('div','meta');
    s2.appendChild(pill(p.status==='approved'?'승인 적용':
      p.status==='rejected'?'정책 거부':'미리보기',
      p.status==='approved'?'good':p.status==='rejected'?'bad':'warn'));
    c.appendChild(s2);
    if(p.rejected.length){c.appendChild(el('div','note',
      '차단된 열 — '+p.rejected.join(', ')+' (미승인 또는 마스킹 필드)'))}
    else if(!p.checks[2][1]){c.appendChild(el('div','note',
      '집계 최소단위 위반 — 마스킹 필드를 행 단위 열로 세울 수 없다'))}
    if(p.status==='approved'&&p.preview.rows.length){
      c.appendChild(el('h3',null,'승인 적용 화면'));
      const bc=p.preview.bar_column;
      if(bc&&p.blocks.some(b=>b[0]==='bar'||b[0]==='line')){
        const j=p.preview.columns.indexOf(bc);
        const lab=p.preview.columns.indexOf(p.preview.label_column);
        const max=Math.max(...p.preview.rows.map(r=>Math.abs(r[j]||0)))||1;
        const box=el('div');
        p.preview.rows.forEach(r=>{
          const line=el('div');line.style.margin='6px 0';
          const t=el('div','meta');
          t.textContent=(lab>=0?esc(r[lab]):bc)+' · '+fmtNum(r[j]);
          const b=el('div','bar'),i=el('i');
          i.style.width=(Math.abs(r[j]||0)/max*100).toFixed(1)+'%';
          b.appendChild(i);line.appendChild(t);line.appendChild(b);
          box.appendChild(line)});
        c.appendChild(box);
      }
      c.appendChild(table(p.preview));
    }
    root.appendChild(c);
  });
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
  D.forms.forEach((f,i)=>{
    const b=el('button');b.appendChild(document.createTextNode(`${f.form_id} ${f.form_name}`));
    b.appendChild(el('small',null,`${f.frequency} · ${f.n_lines}행 · 검증 ${f.n_checks}건 실패 ${f.n_failed}`));
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
  c.appendChild(el('h3',null,`[${f.form_id}] ${f.form_name}`));
  c.appendChild(el('div','meta',`제출주기 ${f.frequency} · 근거 ${f.citation}`));
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
    '상시 모니터링과 개발조직에서 분리된 독립 재계산을 하나의 관문으로 통제한다. FAIL이 하나라도 있으면 결재 불가.'));
  const c=el('div','card');c.appendChild(el('h3',null,'자체검증 결과'));
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
  ['E 위기상황','E · 통합위기상황분석 — 시나리오→자본',
   r=>domain(r,'PRD-ST',null,'거시경로에서 위험전이·손익·RWA·자본까지 하나의 통제경로로 연결한다.')],
  ['R 감독보고','R · 금감원 업무보고서',regulatory],
  ['F 검증','F · 상시·독립 적합성검증 게이트',validation],
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
  $('.kill').onclick=()=>{
    alert('범위형 비상정지 — 데모 화면에서는 실제 정지를 실행하지 않는다.\n'+
      '운영에서는 에이전트·도구·워크플로·테넌트 범위를 선택하고 사유와 '+
      '독립된 2차 확인을 거쳐야 하며, 진행 중 결정론적 계산은 완료 후 중단된다.');
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
<script>window.__RYNTA__={json.dumps(d, ensure_ascii=False, default=str)};</script>
<script>{_JS}</script>
</body></html>"""


def write_app(s: Studio, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(s), encoding="utf-8")
    return p
