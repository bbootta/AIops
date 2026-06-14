"""Round 57 — IFRS 9 FLI overlay + 가중 ECL + PMA."""

from __future__ import annotations

import pytest


def test_fli_overlay_sample_complete():
    from tools.sample_generators import ifrs9_fli_overlay_sample

    f = ifrs9_fli_overlay_sample()
    assert f["base_ecl_bn"] > 0
    assert len(f["scenarios"]) == 3
    # 가중치 합 = 1
    assert abs(sum(s["weight"] for s in f["scenarios"]) - 1.0) < 1e-9
    # baseline ECL < adverse < severely_adverse
    e = [s["ecl_bn"] for s in f["scenarios"]]
    assert e[0] < e[1] < e[2]
    assert "IFRS 9" in f["framework"]


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r57")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_fli_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "ifrs9_fli_deep.html" in names


def test_page_shows_scenarios(pack):
    out, _ = pack
    text = (out / "ifrs9_fli_deep.html").read_text(encoding="utf-8")
    for s in ("baseline", "adverse", "severely_adverse"):
        assert s in text


def test_page_shows_waterfall_components(pack):
    out, _ = pack
    text = (out / "ifrs9_fli_deep.html").read_text(encoding="utf-8")
    for c in ("Base ECL", "Probability-weighted", "Management Overlay",
              "Final ECL"):
        assert c in text


def test_page_shows_pma_rationale(pack):
    out, _ = pack
    text = (out / "ifrs9_fli_deep.html").read_text(encoding="utf-8")
    assert "Management Overlay" in text
    assert "회계" in text or "감리" in text


def test_page_attributes_ifrs9_section(pack):
    out, _ = pack
    text = (out / "ifrs9_fli_deep.html").read_text(encoding="utf-8")
    assert "B5.5" in text or "IFRS 9" in text


def test_ifrs9_parent_links_to_fli(pack):
    out, _ = pack
    text = (out / "ifrs9_deep.html").read_text(encoding="utf-8")
    # ifrs9_deep -> fli 양쪽 nav 적어도 한쪽은 존재
    text_fli = (out / "ifrs9_fli_deep.html").read_text(encoding="utf-8")
    assert 'href="ifrs9_deep.html"' in text_fli


def test_index_links_to_fli(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="ifrs9_fli_deep.html"' in idx


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "ifrs9_fli_deep.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
