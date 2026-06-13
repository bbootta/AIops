"""Round 43 — 챔피언 vs 챌린저 비교."""

from __future__ import annotations

import pytest


def test_credit_sample_includes_challenger_score():
    from tools.sample_generators import credit_scoring_sample

    df = credit_scoring_sample(n=2000, seed=42)
    assert "score" in df.columns
    assert "score_challenger" in df.columns
    # 챌린저는 챔피언과 동일하지 않다 — 실제 비교 의미가 있어야
    assert not (df["score"] == df["score_challenger"]).all()


def test_challenger_score_is_deterministic():
    from tools.sample_generators import credit_scoring_sample

    d1 = credit_scoring_sample(n=1000, seed=42)
    d2 = credit_scoring_sample(n=1000, seed=42)
    assert (d1["score_challenger"] == d2["score_challenger"]).all()


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r43")
    demo = run_demo(2_000, False, 42, out / "logs")
    request = build_request(2_000, stress=False, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_challenger_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "challenger.html" in names


def test_challenger_page_shows_all_three_metrics(pack):
    out, _ = pack
    text = (out / "challenger.html").read_text(encoding="utf-8")
    for metric in ("KS", "AUROC", "Gini"):
        assert metric in text


def test_challenger_page_shows_delta_with_sign(pack):
    out, _ = pack
    text = (out / "challenger.html").read_text(encoding="utf-8")
    # Δ 컬럼 + 부호
    assert "Δ" in text or "(챌린저 − 챔피언)" in text


def test_challenger_page_emits_decision(pack):
    out, _ = pack
    text = (out / "challenger.html").read_text(encoding="utf-8")
    # 결론 문구 중 하나는 등장
    assert ("챌린저 우세" in text or "유사 수준" in text or "챔피언 우세" in text)


def test_challenger_page_links_back_to_credit(pack):
    out, _ = pack
    text = (out / "challenger.html").read_text(encoding="utf-8")
    assert 'href="credit.html"' in text


def test_credit_page_links_to_challenger(pack):
    out, _ = pack
    text = (out / "credit.html").read_text(encoding="utf-8")
    assert 'href="challenger.html"' in text


def test_index_links_to_challenger(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="challenger.html"' in idx


def test_challenger_page_self_contained_and_draft(pack):
    out, _ = pack
    text = (out / "challenger.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text


def test_challenger_page_explains_mrmc_threshold(pack):
    out, _ = pack
    text = (out / "challenger.html").read_text(encoding="utf-8")
    assert "MRMC" in text
    assert "AUROC" in text
