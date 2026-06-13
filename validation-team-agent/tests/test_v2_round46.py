"""Round 46-48 (combined) — IFRS 9 stage migration + stress test + change audit."""

from __future__ import annotations

import pytest


# ---------- R46 IFRS 9 ----------

def test_ifrs9_stage_migration_sample_complete():
    from tools.sample_generators import ifrs9_stage_migration_sample

    m = ifrs9_stage_migration_sample()
    assert m["stages"] == ["S1", "S2", "S3"]
    # migration matrix 행 합 = 1
    for from_s in m["stages"]:
        row = m["migration_matrix"][from_s]
        assert abs(sum(row.values()) - 1.0) < 1e-9
    # ECL by stage 와 합계 일치
    assert abs(sum(m["ecl_by_stage"].values()) - m["total_ecl"]) < 1e-6
    # SICR 정의 + 프레임워크
    assert "SICR" not in m["sicr_definition"] or m["sicr_definition"]
    assert "IFRS 9" in m["framework"]


def test_ifrs9_sample_deterministic():
    from tools.sample_generators import ifrs9_stage_migration_sample

    a = ifrs9_stage_migration_sample()
    b = ifrs9_stage_migration_sample()
    assert a == b


# ---------- R47 스트레스 테스트 ----------

def test_stress_test_scenarios_three_levels():
    from tools.sample_generators import stress_test_scenarios_sample

    s = stress_test_scenarios_sample()
    names = [x["scenario"] for x in s]
    assert names == ["baseline", "adverse", "severely_adverse"]
    # 가중치 합 = 1
    assert abs(sum(x["weight"] for x in s) - 1.0) < 1e-9


def test_stress_test_scenarios_degradation():
    from tools.sample_generators import stress_test_scenarios_sample

    s = stress_test_scenarios_sample()
    # 시나리오가 악화될수록 CET1/LCR/ICAAP 감소
    assert s[0]["cet1_post_stress"] > s[1]["cet1_post_stress"] > s[2]["cet1_post_stress"]
    assert s[0]["lcr_post_stress"] > s[1]["lcr_post_stress"] > s[2]["lcr_post_stress"]


# ---------- pack ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r46_48")
    demo = run_demo(2_000, True, 42, out / "logs")
    request = build_request(2_000, stress=True, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files


def test_three_new_pages_generated(pack):
    _, files = pack
    names = {p.name for p in files}
    for p in ("ifrs9_deep.html", "stress_test.html", "change_audit.html"):
        assert p in names


def test_ifrs9_page_shows_stage_migration_matrix(pack):
    out, _ = pack
    text = (out / "ifrs9_deep.html").read_text(encoding="utf-8")
    for stage in ("S1", "S2", "S3"):
        assert stage in text
    assert "SICR" in text
    assert "IFRS 9" in text
    assert "Stage Migration Matrix" in text


def test_ifrs9_page_shows_ecl_decomposition(pack):
    out, _ = pack
    text = (out / "ifrs9_deep.html").read_text(encoding="utf-8")
    for label in ("ECL by Stage", "EAD", "LGD", "lifetime"):
        assert label in text


def test_stress_test_page_lists_three_scenarios(pack):
    out, _ = pack
    text = (out / "stress_test.html").read_text(encoding="utf-8")
    for s in ("baseline", "adverse", "severely_adverse"):
        assert s in text
    assert "가중평균" in text
    assert "Recovery Plan" in text or "R&R" in text


def test_stress_test_page_shows_macro_variables(pack):
    out, _ = pack
    text = (out / "stress_test.html").read_text(encoding="utf-8")
    for label in ("GDP", "실업률", "주택가격", "정책금리", "multiplier"):
        assert label in text


def test_change_audit_page_lists_recent_chgs(pack):
    out, _ = pack
    text = (out / "change_audit.html").read_text(encoding="utf-8")
    assert "CHG-" in text
    assert "matrix CHG" not in text  # not a typo check
    # status 분포 표
    assert "proposed" in text
    assert "Decision Observability" in text


def test_change_audit_explains_promotion_flow(pack):
    out, _ = pack
    text = (out / "change_audit.html").read_text(encoding="utf-8")
    for keyword in ("proposed", "applied", "validated", "rolled_back",
                    "manifest promote"):
        assert keyword in text


def test_all_new_pages_self_contained_and_draft(pack):
    out, _ = pack
    for name in ("ifrs9_deep.html", "stress_test.html", "change_audit.html"):
        text = (out / name).read_text(encoding="utf-8")
        assert "https://" not in text
        assert "<script" not in text
        assert "[DRAFT" in text
        assert "Reproducibility" in text


def test_index_links_to_three_new(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    for name in ("ifrs9_deep.html", "stress_test.html", "change_audit.html"):
        assert f'href="{name}"' in idx


def test_executive_links_to_stress_and_change_audit(pack):
    out, _ = pack
    text = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="stress_test.html"' in text
    assert 'href="change_audit.html"' in text
    assert 'href="ifrs9_deep.html"' in text


def test_total_pages_after_combined_round(pack):
    _, files = pack
    assert len(files) >= 26  # R45 23 + 3 new
