"""브라우저 엔진(engine.js)과 파이썬 엔진의 동치성.

화면이 서버 왕복 없이 즉시 반응하려면 컴파일러가 브라우저에도 있어야 한다.
그 순간 구현이 둘이 되고, 둘이 갈라지면 **화면이 원장과 다른 답을 낸다** —
시연에서는 통과하고 운영에서 틀리는 최악의 형태다. 이 테스트가 그 간극을 막는다.

같은 입력에 대해 두 구현의 조회계획(AST·지문·판정·차단사유), 실행 결과 건수,
레이아웃 제안(열·블록·3중 검증·제안 ID)이 모두 일치해야 한다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from risk_lib.ui_studio import layout as lay
from risk_lib.ui_studio.nl_query import compile_query, execute

_ENGINE = Path(__file__).resolve().parents[1] / "risk_lib" / "ui_studio" / "engine.js"
_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(_NODE is None, reason="node 미설치")

FIELDS = [
    {"view_id": "V_T", "field_name": "ltv", "korean": "담보인정비율",
     "permitted": True, "masking": "none", "min_aggregation": 1},
    {"view_id": "V_T", "field_name": "ead", "korean": "익스포저(EAD)",
     "permitted": True, "masking": "none", "min_aggregation": 1},
    {"view_id": "V_T", "field_name": "balance", "korean": "잔액",
     "permitted": True, "masking": "none", "min_aggregation": 1},
    {"view_id": "V_T", "field_name": "classification", "korean": "건전성 분류",
     "permitted": True, "masking": "none", "min_aggregation": 1},
    {"view_id": "V_T", "field_name": "dpd", "korean": "연체일수",
     "permitted": True, "masking": "none", "min_aggregation": 1},
    {"view_id": "V_T", "field_name": "obligor_id", "korean": "차주 식별자",
     "permitted": True, "masking": "mask", "min_aggregation": 5},
    {"view_id": "V_T", "field_name": "secret", "korean": "미승인 항목",
     "permitted": False, "masking": "deny", "min_aggregation": 1},
]
FIELDS_DF = pd.DataFrame(FIELDS)

UTTERANCES = [
    "담보인정비율 70% 초과",
    "담보인정비율 70% 초과 그리고 잔액 100억 이상",
    "연체일수 30 이상 및 잔액 1조 미만",
    "건전성 분류 고정",
    "건전성 분류 정상 아닌",
    "익스포저(EAD) 0.5 이하",
    "차주 식별자 OBL_0001",              # 마스킹 필드 조건 → 차단
    "미승인 항목 3 초과",                 # 미승인 필드 → 차단
    "전부 다 보여줘",                     # 조건 없음 → 차단
    "담보인정비율",                       # 값 없음 → 차단
    "연체일수 30 이상, 담보인정비율 0.8 초과, 잔액 5000만 이상",
]

PROMPTS = [
    "자산군별 기여도를 막대차트로 보여주고 아래에 잔액 검토 표를 배치해줘. 상위 10건.",
    "잔액 추이를 보여줘",
    "차주 식별자와 잔액을 행 단위 표로",         # 집계 최소단위 위반
    "미승인 항목을 표로",                       # 미승인 필드
    "건전성 분류와 잔액을 카드로 보여줘",
    "담보인정비율 상위 900건 표",               # 상한 캡
]

ROWS = [
    {"ltv": 0.65, "ead": 1.2e10, "balance": 5.0e9, "classification": "정상",
     "dpd": 0, "obligor_id": "OBL_0001"},
    {"ltv": 0.75, "ead": 3.0e9, "balance": 2.0e10, "classification": "요주의",
     "dpd": 45, "obligor_id": "OBL_0002"},
    {"ltv": 0.90, "ead": 0.4, "balance": 6.0e7, "classification": "고정",
     "dpd": 120, "obligor_id": "OBL_0003"},
    {"ltv": 0.55, "ead": 8.0e9, "balance": 9.0e11, "classification": "정상",
     "dpd": 15, "obligor_id": "OBL_0004"},
]
ROWS_DF = pd.DataFrame(ROWS)


def _run_node() -> dict:
    frame = {
        "columns": list(ROWS_DF.columns),
        "rows": [[None if pd.isna(v) else v for v in r]
                 for r in ROWS_DF.itertuples(index=False)],
    }
    script = f"""
const RY = require({str(_ENGINE)!r});
const fields = {json.dumps(FIELDS, ensure_ascii=False)};
const frame = {json.dumps(frame, ensure_ascii=False)};
const out = {{queries: [], proposals: []}};
for (const u of {json.dumps(UTTERANCES, ensure_ascii=False)}) {{
  const p = RY.compileQuery(u, {{viewId: "V_T", asof: "2026-06-30", fields}});
  const r = RY.execute(p, frame, 100);
  out.queries.push({{
    utterance: u, ast: p.ast, hash: p.query_hash, plan_id: p.plan_id,
    status: r.plan.status, block_reason: r.plan.block_reason,
    n_rows: r.plan.n_rows, shown: r.rows.length,
    describe: p.conditions.map(RY.describe),
  }});
}}
for (const q of {json.dumps(PROMPTS, ensure_ascii=False)}) {{
  const pr = RY.compose(q, {{viewId: "V_T", fields, rowLimit: 500}});
  out.proposals.push({{
    prompt: q, proposal_id: pr.proposal_id, columns: pr.columns,
    blocks: pr.blocks.map(b => b[0]), row_limit: pr.row_limit,
    field_policy_pass: pr.field_policy_pass, schema_pass: pr.schema_pass,
    aggregation_pass: pr.aggregation_pass, status: pr.status,
    rejected: pr.rejected_fields,
  }});
}}
process.stdout.write(JSON.stringify(out));
"""
    r = subprocess.run([_NODE, "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def js():
    return _run_node()


def test_query_plans_match(js):
    for got in js["queries"]:
        plan = compile_query(got["utterance"], view_id="V_T",
                             asof="2026-06-30", fields=FIELDS_DF)
        rows, plan = execute(plan, ROWS_DF, row_limit=100)
        u = got["utterance"]
        assert got["ast"] == plan.condition_ast, u
        assert got["hash"] == plan.query_hash, u
        assert got["plan_id"] == plan.plan_id, u
        assert got["status"] == plan.status, u
        assert got["block_reason"] == plan.block_reason, u
        assert got["n_rows"] == plan.n_rows, u
        assert got["shown"] == len(rows), u
        assert got["describe"] == [c.describe() for c in plan.conditions], u


def test_at_least_one_blocked_and_one_validated(js):
    statuses = {q["status"] for q in js["queries"]}
    assert statuses == {"validated", "blocked"}


def test_layout_proposals_match(js):
    for got in js["proposals"]:
        pr = lay.compose(got["prompt"], view_id="V_T", fields=FIELDS_DF,
                         row_limit=500)
        q = got["prompt"]
        assert got["proposal_id"] == pr.proposal_id, q
        assert got["columns"] == list(pr.columns), q
        assert got["blocks"] == [b for b, _ in pr.blocks], q
        assert got["row_limit"] == pr.row_limit, q
        assert got["field_policy_pass"] == pr.field_policy_pass, q
        assert got["schema_pass"] == pr.schema_pass, q
        assert got["aggregation_pass"] == pr.aggregation_pass, q
        assert got["status"] == pr.status, q
        assert got["rejected"] == list(pr.rejected_fields), q


def test_proposals_cover_pass_and_reject(js):
    assert {p["status"] for p in js["proposals"]} == {"previewed", "rejected"}


def test_engine_js_is_inlined_by_the_renderer(result, portfolio):
    """엔진을 별도 파일로 두면 폐쇄망에서 화면이 죽는다 — 반드시 인라인."""
    from risk_lib.ui_studio.app import render
    from risk_lib.ui_studio.studio import build_studio
    h = render(build_studio(result, portfolio))
    assert "RY.compileQuery" in h
    assert "function sha256Hex" in h
    assert "engine.js" not in h.replace("engine.js와", "")  # src 참조 금지
