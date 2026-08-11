"""Round 40 — 설명가능성 (Explainability): 임계 근거 + narrative."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------- attribution SSoT ----------

def test_explainability_ssot_has_attribution_per_critical_step():
    data = json.loads(
        (ROOT / "harness" / "explainability_attributions.json")
        .read_text(encoding="utf-8"))
    steps = {a["step"] for a in data["attributions"]}
    for required in ("3.capital", "3.icaap", "3.liquidity", "3.irrbb",
                     "3.alm", "3.market", "3.operational", "3.cva",
                     "3.ccr", "3.conc", "3.disc", "3.psi", "3.cal"):
        assert required in steps, f"{required} attribution 누락"


def test_attribution_fields_complete():
    from tools.explainability import load_attributions

    for a in load_attributions():
        for f in ("step", "metric", "formula", "minimum", "source",
                  "interpretation", "policy_ssot"):
            assert a.get(f), f"{a.get('step')} {f} 누락"


def test_attribution_lookup_by_step():
    from tools.explainability import attributions_for

    cap = attributions_for("3.capital")
    assert any("CET1" in a["metric"] for a in cap)
    assert all(a["step"] == "3.capital" for a in cap)


# ---------- narrative ----------

def test_narrate_includes_status_and_formula():
    from tools.explainability import narrate

    out = narrate("3.liquidity", {"status": "fail",
                                  "detail": "LCR 0.800 below_min"})
    assert "fail" in out
    assert "위반 사유" in out
    assert "HQLA" in out or "100%" in out
    assert "임의 완화" in out  # CLAUDE.md §5 명시


def test_narrate_ok_explains_threshold():
    from tools.explainability import narrate

    out = narrate("3.capital", {"status": "ok", "detail": "ratios passed"})
    assert "정상" in out
    assert "산식" in out


def test_narrate_skipped_returns_safe_message():
    from tools.explainability import narrate

    out = narrate("3.icaap", {"status": "skipped", "detail": "입력 미제공"})
    # skipped 는 narrative 가 비어있어도 OK — 입력 부재 정보만 노출
    assert "skipped" in out or "입력 미제공" in out


def test_narrate_unknown_step_returns_base():
    from tools.explainability import narrate

    out = narrate("3.unknown", {"status": "ok", "detail": "x"})
    assert "ok" in out and "x" in out


def test_render_attribution_block_returns_html_with_ssot():
    from tools.explainability import render_attribution_block

    html = render_attribution_block("3.liquidity")
    assert "<details>" in html
    assert "LCR" in html and "NSFR" in html
    assert "harness/liquidity_risk_thresholds.json" in html


# ---------- pack 통합 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r40")
    demo = run_demo(800, True, 42, out / "logs")
    request = build_request(800, stress=True, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_alm_page_has_why_section_and_attribution(pack):
    out, _ = pack
    text = (out / "alm.html").read_text(encoding="utf-8")
    assert "왜 이 결과인가" in text
    assert "BCBS LIQ40" in text or "BCBS LIQ20" in text
    assert "임계 규제 근거" in text


def test_capital_page_has_attribution(pack):
    out, _ = pack
    text = (out / "capital_icaap.html").read_text(encoding="utf-8")
    assert "왜 이 결과인가" in text
    assert "BCBS" in text


def test_market_page_has_attribution(pack):
    out, _ = pack
    text = (out / "market_ops.html").read_text(encoding="utf-8")
    assert "MAR99" in text
    assert "OPE25" in text or "SMA" in text


def test_concentration_page_has_attribution(pack):
    out, _ = pack
    text = (out / "concentration.html").read_text(encoding="utf-8")
    assert "BCBS LEX" in text
    assert "은행법" in text


def test_credit_page_has_narrative_and_attribution(pack):
    out, _ = pack
    text = (out / "credit.html").read_text(encoding="utf-8")
    assert "왜 이 결과인가" not in text  # credit 은 inline narrative 만
    # KS/AUROC 출처
    assert "KS" in text
    # narrative + attribution 블록
    assert "임계 규제 근거" in text


def test_explainability_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "explainability.html" in names
    text = (out / "explainability.html").read_text(encoding="utf-8")
    # 모든 핵심 step 의 metric 이 한 표에 등장
    for sub in ("CET1", "LCR", "NSFR", "ΔEVE / Tier1", "VaR backtest"):
        assert sub in text


def test_explainability_page_self_contained(pack):
    out, _ = pack
    text = (out / "explainability.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text


def test_executive_links_to_explainability(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="explainability.html"' in text


def test_no_arbitrary_relaxation_text_in_attribution_block(pack):
    out, _ = pack
    expl = (out / "explainability.html").read_text(encoding="utf-8")
    assert "임의 완화" in expl
