"""원장·화면 계보 추출기와 배선 통제 (risk_lib/datamodel/lineage.py).

이 스위트가 지키는 것은 두 가지다.

1. 추출기가 실제로 계보를 뽑는지. 뽑지 못하면 조용히 빈 결과를 내고, 그러면
   모든 원장이 고아로 보이거나(과다) 모든 원장이 배선된 것으로 보인다(과소).
   두 방향 모두 위반 사례로 발동을 확인한다.
2. 배선이 조용히 무너지지 않는지. 화면·서식에 연결되지 않은 새 원장이
   판정 없이 늘거나, 연결 원장 없는 화면이 사유 없이 늘면 실패한다.
"""

from __future__ import annotations

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel import lineage as lin


@pytest.fixture(scope="module")
def graph():
    return lin.build_lineage()


# ---------------------------------------------------------------- 추출기

def test_screen_scan_finds_screens_and_tables(graph):
    """화면 선언을 못 읽으면 계보 전체가 빈다."""
    assert len(graph.screens) > 50
    assert sum(1 for r in graph.screens.values() if not r["generic"]) > 50


def test_screenof_table_declaration_is_read(graph):
    """`const x=screenOf({tables:[…]})` 는 여는 괄호가 첫 글자가 아니다.

    첫 줄만 잘라 받으면 이 화면의 원장 선언이 통째로 사라진다.
    """
    assert "alm_irrbb_result" in graph.screens["금리리스크"]["tables"]
    assert "alm_nii_result" in graph.screens["금리리스크"]["tables"]


def test_payload_key_path_is_followed(graph):
    """화면이 `D.agents` 처럼 파이썬이 만든 키를 읽는 경로."""
    assert "agent_registry" in graph.screens["에이전트"]["tables"]
    assert "val_check" in graph.screens["검증"]["tables"]


def test_domain_screen_expands_its_product(graph):
    """`domain(r,'PRD-RDM')` 화면은 그 부문 원장을 전부 그린다."""
    rdm = {s.name for s in cat.ALL_TABLES if s.product == "PRD-RDM"}
    assert rdm <= graph.screens["RDM"]["tables"]


def test_product_literal_alone_does_not_expand_a_domain(graph):
    """부문 코드가 문자열로 있다는 것만으로 전개하면 안 된다.

    조기경보 화면은 `DOMAIN_CHARTS['PRD-CRM']` 하나를 부르지만 신용 부문
    원장 29장을 그리지는 않는다.
    """
    crm = {s.name for s in cat.ALL_TABLES if s.product == "PRD-CRM"}
    drawn = graph.screens["조기경보"]["tables"]
    assert drawn == {"crm_ews_signal"}
    assert not crm <= drawn


def test_comments_are_not_scanned_as_references():
    """주석에 적힌 식별자를 참조로 세면 화면 하나가 전 원장을 그린다.

    `wireExecLinks` 주석의 `TABS` 때문에 종합보고서가 227장을 그리는 것으로
    나왔던 적이 있다.
    """
    js = lin.js_source()
    assert "/*" not in js
    assert "nav 버튼 순서는" not in js


def test_form_scan_finds_ledgers(graph):
    assert graph.forms
    assert "rwa_sa_bucket" in graph.reported()
    assert "alm_lcr_item" in graph.reported()


def test_every_catalog_table_has_a_declaring_module(graph):
    """스펙 선언 모듈을 못 찾으면 산출 계보의 소유자 축이 빈다."""
    missing = sorted({s.name for s in cat.ALL_TABLES} - set(graph.owners))
    assert missing == []


def test_fk_edges_come_from_declarations():
    edges = lin.fk_edges()
    assert edges
    for e in edges:
        assert e.kind == "fk"
        assert e.src in {s.name for s in cat.ALL_TABLES}


def test_orchestrator_reads_do_not_become_ledger_dependencies(graph):
    """`_stage_ledgers` 하나가 도메인 간 가짜 의존 48건을 만들었다."""
    bad = [e for e in graph.edges
           if e.kind == "feeds" and "_stage_" in e.via]
    assert bad == []


def test_lineage_is_deterministic():
    a, b = lin.build_lineage(), lin.build_lineage()
    assert a.edges == b.edges
    assert {k: sorted(v["tables"]) for k, v in a.screens.items()} == \
           {k: sorted(v["tables"]) for k, v in b.screens.items()}


# ---------------------------------------------------------------- 배선 통제

def test_no_unregistered_unwired_ledger(graph):
    """화면·서식이 안 쓰는 원장은 전부 판정 대장에 있어야 한다."""
    assert lin.check_orphans(graph) == []


def test_unwired_count_is_capped(graph):
    assert len(graph.unwired()) <= lin.MAX_UNWIRED


def test_every_judgement_has_a_reason():
    for name, j in lin.ORPHAN_REGISTRY.items():
        assert j.verdict in lin.VERDICTS, name
        assert j.reason.strip(), name
        if j.verdict == "편입 대상":
            assert j.action.strip(), f"{name}: 편입 방법이 비었다"


def test_registry_has_no_stale_entry(graph):
    """배선된 원장이 판정 대장에 남으면 미배선 건수가 실제보다 커진다."""
    stale = sorted(set(lin.ORPHAN_REGISTRY) - set(graph.unwired()))
    assert stale == []


def test_registry_targets_real_tables():
    names = {s.name for s in cat.ALL_TABLES}
    assert sorted(set(lin.ORPHAN_REGISTRY) - names) == []


def test_screens_without_ledger_are_declared(graph):
    assert lin.check_screens(graph) == []


# ---------------------------------------------------------------- 위반 발동

def test_check_orphans_fires_on_a_new_unwired_ledger(graph):
    """위반 사례를 만들어 검사가 실제로 발동하는지 확인한다."""
    victim = sorted(graph.rendered())[0]
    stripped = {k: {**v, "tables": v["tables"] - {victim}}
                for k, v in graph.screens.items()}
    forms = {k: v - {victim} for k, v in graph.forms.items()}
    broken = lin.Lineage(specs=graph.specs, edges=graph.edges,
                         screens=stripped, forms=forms, owners=graph.owners,
                         producers=graph.producers)
    v = lin.check_orphans(broken)
    assert any(victim in line for line in v)


def test_check_screens_fires_on_a_screen_with_no_ledger(graph):
    label = "콕핏"
    stripped = dict(graph.screens)
    stripped[label] = {**graph.screens[label], "tables": set()}
    broken = lin.Lineage(specs=graph.specs, edges=graph.edges,
                         screens=stripped, forms=graph.forms,
                         owners=graph.owners, producers=graph.producers)
    assert any(label in line for line in lin.check_screens(broken))


# ---------------------------------------------------------------- 도표

def test_domain_diagrams_cover_every_block(graph):
    for block in lin.BLOCK_ORDER:
        build = lin.mermaid_domain_build(graph, block)
        use = lin.mermaid_domain_use(graph, block)
        assert build.startswith("flowchart")
        assert use.startswith("flowchart")
        for t in lin.domain_tables(graph, block):
            assert lin._mid("T", t) in build


def test_block_ids_do_not_collide():
    """치환문자를 하나로 뭉개면 '신용'과 '시장'이 같은 노드가 된다."""
    ids = [lin._bid(b) for b in lin.BLOCK_ORDER]
    assert len(set(ids)) == len(ids)
    node_ids = [lin._mid("T", t) for t in ("신용", "시장", "운영", "위기상황")]
    assert len(set(node_ids)) == 4


def test_every_catalog_product_maps_to_a_block():
    unmapped = sorted({s.product for s in cat.ALL_TABLES}
                      - set(lin.DOMAIN_BLOCK))
    assert unmapped == [], f"조감도 블록에 없는 부문: {unmapped}"


def test_doc_is_regenerable(tmp_path, graph):
    """문서는 생성물이다. 손으로 고치면 다음 재생성에서 사라진다."""
    out = tmp_path / "DATA_FLOW.md"
    out.write_text(lin.render_doc(graph), encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    assert "python -m risk_lib.datamodel.lineage" in text
    assert text.count("```mermaid") == 1 + 2 * len(lin.BLOCK_ORDER) + 1
    assert "미배선 원장" in text
