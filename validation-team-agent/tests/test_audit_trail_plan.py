"""run_validation의 audit_trail 섹션에 dry_run plan 요약이 첨부되는지."""

import re

from tools.run_validation import _build_demo_request, run


def test_audit_trail_contains_plan_id_sequence(tmp_path):
    out = run(_build_demo_request(), log_dir=tmp_path)
    md = out["report_md"]
    assert "plan:" in md
    audit_section = re.search(r"## 10\.[^\n]*\n([\s\S]+?)(?:\n## |\Z)", md)
    assert audit_section is not None
    audit_body = audit_section.group(1)
    assert "plan:" in audit_body
    for required in ("1.req", "4.report", "5.complete"):
        assert required in audit_body


def test_summarize_plan_truncates_long_plan():
    from tools import dry_run as dr

    plan = dr.simulate(dr._demo_request())
    short = dr.summarize_plan(plan, max_items=3)
    assert " → " in short
    assert "외" in short or len(plan) <= 3


def test_summarize_plan_short_plan_not_truncated():
    from tools import dry_run as dr

    fake_plan = [{"id": f"x.{i}"} for i in range(3)]
    out = dr.summarize_plan(fake_plan, max_items=8)
    assert out == "x.0 → x.1 → x.2"
    assert "외" not in out
