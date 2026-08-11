from tools import dry_run as dr


def test_simulate_minimal_request_has_core_steps():
    plan = dr.simulate({"score_col": "score", "target_col": "target"})
    names = [s["name"] for s in plan]
    assert any("요청 재구성" in n for n in names)
    assert any("변별력" in n for n in names)
    assert any("보고서 초안" in n for n in names)
    assert any("완결성" in n for n in names)
    assert any("인용" in n for n in names)


def test_simulate_skips_calibration_without_grade_pd():
    plan = dr.simulate({"score_col": "score", "target_col": "target"})
    assert not any("등급별 캘리브레이션" in s["name"] for s in plan)


def test_simulate_includes_calibration_and_psi_when_inputs_present():
    plan = dr.simulate(
        {
            "score_col": "score",
            "target_col": "target",
            "set_col": "set",
            "grade_col": "grade",
            "pd_col": "pd",
        }
    )
    names = [s["name"] for s in plan]
    assert any("안정성" in n for n in names)
    assert any("등급별 캘리브레이션" in n for n in names)


def test_render_markdown_smoke():
    plan = dr.simulate(dr._demo_request())
    md = dr.render_markdown(plan)
    assert md.startswith("# Orchestrator Dry-Run Plan")
    assert "보고서 초안" in md
    assert "시뮬레이션" in md


def test_simulate_includes_expected_outputs():
    plan = dr.simulate(dr._demo_request())
    cite_step = next(s for s in plan if s["id"] == "5.cite")
    assert "citations" in cite_step["expected_outputs"]


def test_render_markdown_shows_expected_outputs():
    plan = dr.simulate(dr._demo_request())
    md = dr.render_markdown(plan)
    assert "expected_outputs" in md
