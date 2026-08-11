"""Round 72 — 검증의견서 초안 (10섹션 규격 + HITL 확정)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def pack_stress(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r72s")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


@pytest.fixture(scope="module")
def pack_normal(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r72n")
    demo = run_demo(800, False, 42, out / "logs")
    request = build_request(800, stress=False, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_opinion_draft_page_generated(pack_stress):
    out, files = pack_stress
    names = {p.name for p in files}
    assert "opinion_draft.html" in names


def test_all_10_sections_present(pack_stress):
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    for section in ("1. 요약", "2. 검증 목적", "3. 입력 데이터",
                    "4. 검증 방법", "5. 주요 결과", "6. 이상 징후",
                    "7. 한계와 리스크", "8. 검증 의견 초안",
                    "9. 추가 확인", "10. 감사추적"):
        assert section in text, f"{section} 누락"


def test_stress_opinion_states_reservation_reason(pack_stress):
    """fail 존재 시 — 적합 의견 유보 사유 문구."""
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert "유보할 사유" in text


def test_normal_opinion_allows_review(pack_normal):
    """fail 없을 시 — 적합 의견 검토 가능 문구."""
    out, _ = pack_normal
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert "적합 의견 검토가 가능" in text


def test_opinion_never_finalizes(pack_stress):
    """의견 확정 금지 — HITL 명시 (CLAUDE.md §5·§7)."""
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert "확정 아님" in text
    assert "인간 검증자" in text
    assert "MRMC" in text


def test_approval_signature_block_present(pack_stress):
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert "승인 란" in text
    for role in ("검증 담당자", "검증팀장", "MRMC 검토"):
        assert role in text


def test_provenance_fingerprint_in_section3(pack_stress):
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert "SHA-256" in text
    assert "재실행 명령" in text


def test_cross_links_to_pack_pages(pack_stress):
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    for href in ("explainability.html", "index.html", "executive.html",
                 "change_audit.html"):
        assert f'href="{href}"' in text


def test_index_and_executive_link_to_opinion(pack_stress):
    out, _ = pack_stress
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="opinion_draft.html"' in idx
    assert 'href="opinion_draft.html"' in exe


def test_opinion_page_has_toc_and_print_ready(pack_stress):
    """10 섹션이므로 sticky TOC 자동 + 인쇄 쿼리 상속."""
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert '<nav class="toc">' in text
    assert "@media print" in text


def test_opinion_self_contained(pack_stress):
    out, _ = pack_stress
    text = (out / "opinion_draft.html").read_text(encoding="utf-8")
    assert "<script" not in text
    assert "https://" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
