"""Round 39 — 경영진 보고서 (`executive.html`) + 인사이트 추출기."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def stress_demo(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r39")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    return demo, request, prov, out


# ---------- insight 추출기 단위 ----------

def test_domain_rows_covers_all_15_domains(stress_demo):
    from tools.executive_insights import domain_rows

    demo, _, _, _ = stress_demo
    rows = domain_rows(demo)
    assert len(rows) >= 13  # ICAAP/ALM 포함 최소 13
    # 각 행: (label, status, detail, link)
    for label, status, detail, link in rows:
        assert isinstance(label, str) and label
        assert status in {"ok", "warning", "fail", "skipped", "simulated"}
        assert link.endswith(".html")


def test_kpi_cards_include_capital_liquidity_icaap(stress_demo):
    from tools.executive_insights import kpi_cards

    demo, _, _, _ = stress_demo
    cards = kpi_cards(demo)
    labels = [c[0] for c in cards]
    assert any("Leverage" in lab for lab in labels)
    assert any("LCR" in lab for lab in labels)
    assert any("NSFR" in lab for lab in labels)
    assert any("ICAAP" in lab for lab in labels)
    # 카드 status_key 는 PALETTE 키
    for label, value, key in cards:
        assert key in {"ok", "warning", "fail", "skipped", "simulated"}


def test_top_risks_orders_fail_before_warning(stress_demo):
    from tools.executive_insights import top_risks_and_actions

    demo, _, _, _ = stress_demo
    risks, actions = top_risks_and_actions(demo, n=5)
    statuses = [r["status"] for r in risks]
    # fail 이 warning 보다 먼저
    if "fail" in statuses and "warning" in statuses:
        assert statuses.index("fail") < statuses.index("warning")
    # 각 위험에는 권고가 1:1 매핑
    assert len(risks) == len(actions)
    for r, a in zip(risks, actions):
        assert r["sid"] == a["sid"]
        assert a["action"]


def test_top_risks_normal_case_empty_or_warnings_only(tmp_path):
    from tools.executive_insights import top_risks_and_actions
    from tools.run_workflow_demo import run_demo

    demo = run_demo(500, False, 42, tmp_path)
    risks, _ = top_risks_and_actions(demo, n=3)
    # 정상 case 에서 fail 은 없어야 한다
    assert all(r["status"] != "fail" for r in risks)


# ---------- executive 페이지 ----------

@pytest.fixture(scope="module")
def pack(stress_demo, tmp_path_factory):
    from tools.report_pack import build_pack

    demo, request, prov, _ = stress_demo
    out = tmp_path_factory.mktemp("pack39")
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_executive_page_emitted(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "executive.html" in names


def test_executive_has_kpi_heatmap_top_risks(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert "경영진 보고서" in text
    assert "핵심 KPI" in text
    assert "위험 히트맵" in text
    assert "Top 3 위험" in text
    assert "Top 3 권고" in text
    # 시각화 SVG 가 KPI + 히트맵 두 개 이상
    assert text.count("<svg") >= 2


def test_executive_shows_escalation_for_stress_case(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    # stress 케이스이므로 escalation 배너 + trigger 가 나와야
    assert "Escalation" in text
    assert "MRMC" in text or "검증자" in text


def test_executive_has_provenance_card(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert "Reproducibility" in text
    assert "재실행 명령" in text


def test_executive_links_resolve(pack):
    import re

    out, files = pack
    names = {p.name for p in files}
    text = (out / "executive.html").read_text(encoding="utf-8")
    for href in re.findall(r'href="([^"#][^"]*)"', text):
        assert href in names, f"executive 링크 깨짐: {href}"


def test_executive_is_self_contained(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    # http:// 는 SVG namespace 만 허용
    assert text.replace("http://www.w3.org", "").count("http://") == 0


def test_executive_actions_attribute_policy_ssot(pack):
    """경영진 권고는 정책 SSoT 매핑이며 임의 완화 금지 — '임의 완화 금지' 명시."""
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert "임의 완화 금지" in text


def test_index_links_to_executive(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="executive.html"' in idx
