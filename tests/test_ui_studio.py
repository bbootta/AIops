"""에이전틱 UI 스튜디오 — 자연어 컴파일러·레이아웃 정책·통제 원장·렌더링.

핵심 명제:
  1) 자연어는 **승인된 필드만** 조건으로 만들 수 있고, 인식 실패는 조용히
     통과하지 않고 차단 사유로 남는다.
  2) 레이아웃 제안은 세 검증을 모두 통과해야만 사람이 승인할 수 있다.
  3) 어떤 에이전트도 운영 반영 권한을 갖지 않는다 (NO AUTONOMOUS WRITE).
  4) 화면에 나오는 수치는 원장에서 온다 — 별도 계산 경로가 없다.
"""

from __future__ import annotations

import json
import re

import pandas as pd
import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import governance as gov
from risk_lib.ui_studio import layout as lay
from risk_lib.ui_studio.app import render
from risk_lib.ui_studio.nl_query import compile_query, execute
from risk_lib.ui_studio.studio import build_studio


@pytest.fixture(scope="module")
def studio(result, portfolio):
    return build_studio(result, portfolio)


def _fields(rows):
    return pd.DataFrame(rows, columns=["view_id", "field_name", "korean",
                                       "permitted", "masking", "min_aggregation"])


_DEMO_FIELDS = _fields([
    ("V_T", "ltv", "담보인정비율", True, "none", 1),
    ("V_T", "ead", "익스포저(EAD)", True, "none", 1),
    ("V_T", "classification", "건전성 분류", True, "none", 1),
    ("V_T", "obligor_id", "차주 식별자", True, "mask", 5),
    ("V_T", "secret", "미승인 항목", False, "deny", 1),
])


# ----- 자연어 컴파일러 --------------------------------------------------------

def test_percent_and_scale_literals():
    p = compile_query("담보인정비율 70% 초과 그리고 익스포저(EAD) 100억 이상",
                      view_id="V_T", asof="2026-06-11", fields=_DEMO_FIELDS)
    assert p.status == "validated"
    assert [(c.field, c.op, c.value) for c in p.conditions] == [
        ("ltv", ">", 0.70), ("ead", ">=", 1e10)]


def test_categorical_equality_without_operator():
    p = compile_query("건전성 분류 고정", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    assert [(c.field, c.op, c.value) for c in p.conditions] == [
        ("classification", "==", "고정")]


def test_unapproved_field_is_blocked_not_ignored():
    p = compile_query("미승인 항목 5 초과", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    assert p.status == "blocked"
    assert "미승인" in p.block_reason


def test_masked_field_cannot_be_used_as_a_condition():
    """마스킹 필드를 조건으로 쓰면 특정 개체를 지목해 행을 되받을 수 있다."""
    p = compile_query("차주 식별자 OBL_0001", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    assert p.status == "blocked"
    assert "집계 최소단위" in p.block_reason


def test_unparseable_sentence_does_not_become_a_full_scan():
    p = compile_query("전부 다 보여줘", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    assert p.status == "blocked"
    assert p.condition_ast == "TRUE"


def test_query_hash_depends_on_policy_and_asof():
    a = compile_query("담보인정비율 70% 초과", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    b = compile_query("담보인정비율 70% 초과", view_id="V_T", asof="2026-09-30",
                      fields=_DEMO_FIELDS)
    c = compile_query("담보인정비율 70% 초과", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS, policy="Read-only")
    assert a.query_hash != b.query_hash != c.query_hash
    assert a.query_hash != c.query_hash


def test_execution_applies_every_condition():
    df = pd.DataFrame({"ltv": [0.6, 0.8, 0.9], "ead": [1e9, 2e10, 5e9]})
    p = compile_query("담보인정비율 70% 초과 그리고 익스포저(EAD) 100억 이상",
                      view_id="V_T", asof="2026-06-11", fields=_DEMO_FIELDS)
    out, p2 = execute(p, df, row_limit=100)
    assert len(out) == 1 and p2.n_rows == 1


def test_blocked_plan_returns_no_rows():
    df = pd.DataFrame({"ltv": [0.9]})
    p = compile_query("미승인 항목 1 초과", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    out, _ = execute(p, df, row_limit=100)
    assert out.empty


def test_row_limit_truncates_but_population_count_survives():
    df = pd.DataFrame({"ltv": [0.9] * 50})
    p = compile_query("담보인정비율 70% 초과", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    out, p2 = execute(p, df, row_limit=10)
    assert len(out) == 10 and p2.n_rows == 50


def test_missing_column_blocks_instead_of_raising():
    p = compile_query("담보인정비율 70% 초과", view_id="V_T", asof="2026-06-11",
                      fields=_DEMO_FIELDS)
    out, p2 = execute(p, pd.DataFrame({"other": [1]}), row_limit=10)
    assert out.empty and p2.status == "blocked" and "없는 필드" in p2.block_reason


# ----- 레이아웃 정책 ----------------------------------------------------------

def test_layout_picks_allowed_visualisations():
    p = lay.compose("담보인정비율 기여도를 막대차트로 보고 아래 검토 표",
                    view_id="V_T", fields=_DEMO_FIELDS)
    assert [v for v, _ in p.blocks] == ["bar", "table"]
    assert set(v for v, _ in p.blocks) <= set(lay.ALLOWED_VIZ)


def test_layout_rejects_denied_columns_and_says_which():
    p = lay.compose("미승인 항목과 담보인정비율을 표로", view_id="V_T",
                    fields=_DEMO_FIELDS)
    assert not p.field_policy_pass and p.rejected_fields == ("secret",)
    assert p.status == "rejected"


def test_layout_rejects_row_level_masked_columns():
    p = lay.compose("차주 식별자와 익스포저(EAD)를 표로", view_id="V_T",
                    fields=_DEMO_FIELDS)
    assert not p.aggregation_pass and p.status == "rejected"


def test_layout_top_n_is_capped_by_the_view_row_limit():
    p = lay.compose("담보인정비율 상위 900건을 표로", view_id="V_T",
                    fields=_DEMO_FIELDS, row_limit=500)
    assert p.row_limit == 500


def test_failed_proposal_cannot_be_approved():
    p = lay.compose("미승인 항목 표", view_id="V_T", fields=_DEMO_FIELDS)
    with pytest.raises(ValueError):
        lay.approve(p, approver="리스크관리부장")


def test_approval_requires_an_approver():
    p = lay.compose("담보인정비율 표", view_id="V_T", fields=_DEMO_FIELDS)
    with pytest.raises(ValueError):
        lay.approve(p, approver="")
    assert lay.approve(p, approver="리스크관리부장").status == "approved"


# ----- 통제 원장 --------------------------------------------------------------

def test_every_canonical_table_has_a_governed_view():
    views, policies = gov.build_views()
    refs = set(views["table_ref"].dropna())
    assert {s.name for s in cat.ALL_TABLES} <= refs
    # 필드 정책은 컬럼 하나도 빠뜨리지 않는다 — 빠지면 조회가 조용히 막힌다.
    for spec in cat.ALL_TABLES:
        got = policies[policies["view_id"] == f"V_{spec.name.upper()}"]
        assert set(got["field_name"]) == {c.name for c in spec.columns}


def test_no_agent_has_operational_write_permission():
    reg = gov.build_agent_registry()
    assert len(reg) >= 10
    assert not reg["write_allowed"].any(), "NO AUTONOMOUS WRITE 위반"
    assert set(reg["mode"]) <= {"조회전용", "제안전용", "승인우선"}


def test_agent_registry_comes_from_the_real_agent_definitions():
    reg = gov.build_agent_registry()
    names = set(reg["agent_name"])
    assert {"risk-orchestrator", "risk-validator", "market-risk-analyst"} <= names


def test_activity_ledger_ends_with_a_human_gate(studio):
    act = studio.tables["agent_activity"].sort_values("seq")
    assert act.iloc[-1]["gate"] == "대기"
    assert "CRO" in act.iloc[-1]["actor"]


def test_evidence_graph_is_connected_seven_stages(studio):
    nodes = studio.tables["gov_evidence_node"]
    edges = studio.tables["gov_evidence_edge"]
    assert list(nodes["stage"]) == list(cat.EVIDENCE_STAGES)
    ids = set(nodes["node_id"])
    assert set(edges["from_node"]) <= ids and set(edges["to_node"]) <= ids
    # 첫 노드를 뺀 모든 노드는 들어오는 간선이 하나 이상 있어야 계보가 된다.
    incoming = set(edges["to_node"])
    assert ids - incoming == {nodes.iloc[0]["node_id"]}


def test_approvals_enforce_segregation_of_duties(studio):
    ap = studio.tables["gov_approval"]
    assert len(ap) > 0
    for _, r in ap.iterrows():
        assert bool(r["segregation_ok"]) == (r["reviewer"] != r["approver"])
        if not r["segregation_ok"]:
            assert r["decision"] != "승인"


def test_change_requests_never_allow_deploy(studio):
    chg = studio.tables["chg_change_request"]
    assert not chg["deploy_allowed"].any()


def test_change_requests_trace_back_to_unmapped_codes(studio):
    cmap = studio.tables["rdm_canonical_map"]
    unmapped = set(cmap[cmap["status"] == "unmapped"]["source_code"])
    ids = {c.replace("CHG-", "") for c in studio.tables["chg_change_request"]["change_id"]}
    assert ids == unmapped


# ----- 스튜디오 조립 ----------------------------------------------------------

def test_studio_materialises_the_entire_catalog(studio):
    assert set(studio.tables) >= {s.name for s in cat.ALL_TABLES}


def test_studio_plans_execute_against_real_tables(studio):
    assert studio.plans
    validated = [p for p in studio.plans if p.status == "validated"]
    assert validated, "실행된 조회계획이 하나도 없다"
    for p in validated:
        assert p.plan_id in studio.plan_results
        assert p.n_rows >= len(studio.plan_results[p.plan_id])


def test_studio_includes_a_deliberately_blocked_plan(studio):
    """차단 경로가 실제로 걸리는 걸 화면에서 보여줘야 통제가 증명된다."""
    assert any(p.status == "blocked" for p in studio.plans)


def test_studio_includes_a_rejected_layout_proposal(studio):
    assert any(p.status == "rejected" for p in studio.proposals)
    assert any(p.status == "approved" for p in studio.proposals)


def test_digest_matches_the_regulatory_submission(studio):
    subs = studio.tables["reg_submission"]
    assert set(subs["digest"]) == {studio.digest}


# ----- 렌더링 -----------------------------------------------------------------

def test_render_is_self_contained(studio):
    h = render(studio)
    assert h.startswith("<!doctype html>")
    # 폐쇄망 전제 — 외부 리소스를 **가져오는** 순간 화면이 열리지 않는다.
    # (SVG 네임스페이스 URI는 요청이 아니라 상수이므로 예외다.)
    assert not re.search(r"(?:src|href)\s*=\s*[\"']https?://", h)
    assert not re.search(r"@import\s+url\(", h)
    assert not re.search(r"\bfetch\s*\(|XMLHttpRequest|new WebSocket", h)
    for url in re.findall(r"https?://[^\s\"'`)]+", h):
        assert url.startswith("http://www.w3.org/"), url
    assert "<script>window.__RYNTA_RUNS__=" in h


def _runs(h: str) -> dict:
    m = re.search(r"window\.__RYNTA_RUNS__=(\{.*\});\nwindow\.__RYNTA__", h, re.S)
    assert m, "실행 payload 를 찾지 못했다"
    return json.loads(m.group(1))


def _primary(h: str) -> str:
    m = re.search(r'window\.__RYNTA__=window\.__RYNTA_RUNS__\[("[-\d]+")\];', h)
    assert m, "기본 실행 지정을 찾지 못했다"
    return json.loads(m.group(1))


def test_render_embeds_a_parseable_payload(studio):
    h = render(studio)
    d = _runs(h)[_primary(h)]
    assert d["meta"]["n_tables"] == len(cat.ALL_TABLES)
    assert len(d["forms"]) == len(studio.built_forms)
    assert len(d["catalog"]) == len(cat.ALL_TABLES)
    assert all(r["materialised"] for r in d["catalog"])


def test_rendered_kpis_match_the_engine(studio):
    h = render(studio)
    d = _runs(h)[_primary(h)]
    cet1 = next(k for k in d["kpis"] if "CET1" in k["label"])
    assert cet1["value"] == f"{studio.result.bis.cet1_ratio:.2%}"


def test_every_payload_column_has_a_catalog_label(studio):
    """화면에 뜨는 모든 표의 모든 컬럼이 카탈로그 표시명을 갖는다.

    표시명의 정본은 카탈로그(ColumnSpec.korean)다 — 화면이 물리명을 그대로
    내보내면 그 컬럼은 검토된 업무 명칭 없이 노출된 것이다. 새 테이블·새
    컬럼이 표시명 없이 들어오면 여기서 실패한다 — 개별 화면이 아니라 payload
    전체를 훑으므로 새 화면을 추가해도 검사를 빠져나갈 수 없다.
    """
    h = render(studio)
    d = _runs(h)[_primary(h)]
    missing: list[str] = []
    checked = [0]

    def walk(o, path):
        if isinstance(o, dict):
            if isinstance(o.get("columns"), list) and isinstance(o.get("rows"), list):
                checked[0] += 1
                labs = o.get("labels") or [None] * len(o["columns"])
                missing.extend(
                    f"{o.get('table') or path}/{c}"
                    for c, l in zip(o["columns"], labs) if l is None)
            else:
                for k, v in o.items():
                    walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(d, "$")
    assert not missing, (
        f"카탈로그 표시명 없는 컬럼 {len(missing)}건 — ColumnSpec.korean 을 "
        f"채워라:\n  " + "\n  ".join(missing[:20]))
    # 공허 통과 방어 — 프레임 탐지가 깨져 0건을 검사하고 통과하면 이 검사는
    # 있는 것처럼 보이는 죽은 통제가 된다 (검토 지적). 검사한 프레임 수를 센다.
    assert checked[0] >= 80, f"검사한 프레임이 {checked[0]}개뿐 — 탐지가 깨졌다"


def test_labels_resolve_per_table_not_globally(studio):
    """같은 물리명이 payload 안에서 **서로 다른** 라벨로 풀린 실례를 단언한다.

    물리명 50종이 테이블마다 다른 한글명을 갖는다(ead → EAD/익스포저 등).
    처음에는 obligor_id 하나만 봤는데, 그 컬럼은 어느 테이블에서나 같은
    라벨이라 전역 사전으로 회귀해도 통과했다 — 이름만 '테이블별'인 검사였다
    (검토 지적). 충돌 컬럼이 실제로 다르게 풀린 두 자리를 찾아 고정한다.
    """
    h = render(studio)
    d = _runs(h)[_primary(h)]
    by_col: dict[str, set[str]] = {}
    for f in d["previews"].values():
        for c, l in zip(f["columns"], f["labels"]):
            by_col.setdefault(c, set()).add(l)
    diverging = {c: ls for c, ls in by_col.items() if len(ls) > 1}
    # 카탈로그에 충돌 컬럼이 50종 있으므로 미리보기에도 여럿 나와야 정상이다.
    assert len(diverging) >= 5, (
        f"충돌 컬럼이 {len(diverging)}종뿐 — 전역 사전으로 회귀했는지 확인하라: "
        f"{sorted(diverging)[:5]}")


def test_multi_run_render_carries_every_run(studio):
    """실행 여러 개를 실으면 전부 payload에 있고, 최신 기준일이 기본이다.

    기준일 전환은 미리 산출한 실행 사이의 전환이다 — 화면은 계산기가 아니다.
    """
    import dataclasses
    older = dataclasses.replace(studio, asof="2026-03-31",
                                run_id="RUN-20260331")
    h = render([studio, older])
    runs = _runs(h)
    assert set(runs) == {studio.asof, "2026-03-31"}
    assert _primary(h) == studio.asof          # 최신 기준일이 기본 화면
    assert 'id="asofsel"' in h                 # 헤더에서 전환할 수 있다
    for a, d in runs.items():
        assert d["meta"]["asof"] == a


def test_render_carries_the_no_autonomous_write_statement(studio):
    h = render(studio)
    assert "자동확정하지 않는다" in h
    assert "합성 포트폴리오" in h      # 실제 기관 수치가 아님을 화면에 남긴다


def test_agent_registry_has_risk_tiers(studio):
    """AIG-001 — 에이전트마다 위험등급이 있고, 규제 산출 에이전트는 상이다."""
    reg = studio.tables["agent_registry"]
    assert set(reg["risk_tier"]) <= {"상", "중", "하"}
    assert (reg["risk_tier"] == "상").any()          # 규제 산출 에이전트 존재
    rwa = reg[reg["agent_name"].str.contains("rwa")]
    assert (rwa["risk_tier"] == "상").all()


def test_exception_queue_derives_only_from_the_three_ledgers(studio):
    """RDM-007 — 예외는 대사·DQ·IPV 세 원장에서만 온다. 손으로 넣는 예외가
    생기는 순간 큐와 원장이 갈라진다."""
    q = studio.tables["gov_exception_action"]
    assert set(q["source_ledger"]) <= {
        "rdm_reconciliation", "rdm_dq_result", "mkt_ipv"}
    # IPV 미해소 건수와 큐의 IPV 예외 건수가 일치한다
    ipv = studio.tables["mkt_ipv"]
    assert (q["source_ledger"] == "mkt_ipv").sum() == int(ipv["is_break"].sum())


def test_alert_policy_binds_action_to_every_alert_type(studio):
    """PLT-015 — 경보 유형마다 표준 조치·SLA·담당·차단 여부가 붙어 있다."""
    pol = studio.tables["gov_alert_policy"]
    assert len(pol) >= 5
    assert pol["bound_action"].str.len().gt(0).all()
    assert (pol["sla_days"] >= 1).all()
    # 자체검증 실패는 제출을 차단한다 — fail-closed 의 정책판
    val = pol[pol["alert_type"] == "자체검증 실패"]
    assert bool(val["blocks_submission"].iloc[0])


def test_code_master_preserves_declared_business_order(studio):
    """코드 마스터 — 카탈로그 선언 순서가 그대로 정렬 순서다.

    등급을 가나다순으로 정렬하면 AAA 다음에 B가 온다 — 등급 사다리가
    아니다. 선언 순서(AAA → AA+ → … → D)가 정본이고, 충돌하는 컬럼명
    (status 등)은 table.column 으로 한정돼 섞이지 않는다.
    """
    m = studio.tables["rdm_code_master"]
    fg = m[m["code_set"] == "from_grade"].sort_values("sort_order")
    assert list(fg["code"])[:4] == ["AAA", "AA+", "AA", "AA-"]
    assert list(fg["code"])[-1] == "D"
    # 충돌 컬럼은 한정된 셋으로 존재한다
    assert (m["code_set"].str.contains(r"\.").any())
    assert not m.duplicated(["code_set", "code"]).any()


def test_code_scope_reads_engine_constants_not_copies(studio):
    """코드 매핑의 CCF율·LCR 적용률이 엔진·원장과 **같은 객체에서** 온다.

    별사본을 두면 엔진이 바뀔 때 매핑만 낡는다 — CRE20.94 요율이 코드에
    두 번 적히는 순간부터 그중 하나는 틀릴 준비가 된 것이다.
    """
    from risk_lib.capital.crm import CCF_BUCKETS
    cr = studio.tables["crm_code_scope"]
    for _, r in cr[cr["ccf_type"] != "—"].iterrows():
        assert r["ccf_rate"] == CCF_BUCKETS[r["ccf_type"]]
    al = studio.tables["alm_code_scope"]
    li = studio.tables["alm_lcr_item"]
    fac = dict(zip(li["category"], li["factor"]))
    mapped = al[al["lcr_category"] != "—"]
    assert len(mapped) >= 8
    for _, r in mapped.iterrows():
        if r["lcr_factor"] is not None:
            assert r["lcr_factor"] == fac[r["lcr_category"]]


def test_code_scope_population_matches_exposure_ledger(studio):
    """계정 매핑의 모집단 실측(EAD 합)이 익스포저 원장 집계와 일치한다.

    조인 키는 **계정코드**다. 이전엔 자산군으로 조인했고 이 검사도 자산군을
    기대했다 — 검사가 틀린 계약을 고정하고 있었으므로 2.28배 중복을 잡지
    못했다. 검사가 코드와 같은 오해를 공유하면 통제가 아니다.
    """
    cr = studio.tables["crm_code_scope"]
    exp = studio.tables["rdm_exposure"]
    by_acct = exp.groupby("account_code")["ead"].sum()
    for _, r in cr[cr["n_exposures"] > 0].iterrows():
        assert abs(r["ead_total"] - float(by_acct.get(r["account_code"], 0.0))) < 1.0
    # 시장·운영 실측도 원장 합과 맞는다
    mk = studio.tables["mkt_code_scope"]
    tr = studio.tables["mkt_trade"].groupby("kind")["trade_id"].count()
    for _, r in mk[mk["trade_kind"] != "—"].iterrows():
        assert r["n_trades"] == int(tr.get(r["trade_kind"], 0))


def test_account_population_sums_to_total_ead_no_duplication(studio):
    """계정별 모집단 합 = 총 EAD. 자산군으로 조인하면 깨진다.

    코드 스코프의 "모집단 실측"을 자산군으로 조인하던 시기에는 corporate에
    매핑된 계정 3개(1220·1240·1310)가 같은 익스포저를 각각 전부 세어
    합계가 실제의 2.28배였다 — 화면에 "실측"이라 적혀 있으므로 읽는 사람은
    계정별 잔액으로 읽는다. 조인 키가 틀린 채 "실측"이라 표기한 F-701 유형.
    """
    exp = studio.tables["rdm_exposure"]
    assert {"account_code", "product_code"} <= set(exp.columns)
    assert exp["account_code"].notna().all()

    cr = studio.tables["crm_code_scope"]
    assert abs(cr["ead_total"].sum() - float(exp["ead"].sum())) < 1.0
    assert cr["n_exposures"].sum() == len(exp)

    # 상품 쪽도 같은 항등식
    mk = studio.tables["mkt_code_scope"]
    assert abs(mk["ead_total"].sum() - float(exp["ead"].sum())) < 1.0


def test_exposure_codes_reference_the_masters(studio):
    """익스포저의 코드는 마스터에 실재하는 코드다 — 유령 코드 금지."""
    exp = studio.tables["rdm_exposure"]
    am = set(studio.tables["rdm_account_master"]["account_code"])
    pm = set(studio.tables["rdm_product_master"]["product_code"])
    assert set(exp["account_code"]) <= am
    assert set(exp["product_code"]) <= pm
