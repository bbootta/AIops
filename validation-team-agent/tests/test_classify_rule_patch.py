from pathlib import Path

from tools import classify_error as ce


def test_no_feedback_emits_explanatory_comment(tmp_path):
    fp = tmp_path / "fb.jsonl"
    out = ce.generate_rule_patch(feedback_path=fp)
    assert "no rule patch suggestion" in out


def test_patch_lines_use_re_escape_safe_form(tmp_path):
    fp = tmp_path / "fb.jsonl"
    ce.record_feedback("obscure pipeline thing happens", "documentation", feedback_path=fp)
    ce.record_feedback("another pipeline failure", "documentation", feedback_path=fp)
    out = ce.generate_rule_patch(feedback_path=fp, min_occurrences=2)
    assert "'documentation'" in out
    assert "pipeline" in out
    assert "\\b" in out  # word boundary 패턴 사용
    assert "count=" in out


def test_patch_skips_categories_without_candidates(tmp_path):
    fp = tmp_path / "fb.jsonl"
    ce.record_feedback("alpha quark", "data", feedback_path=fp)
    out = ce.generate_rule_patch(feedback_path=fp, min_occurrences=5)
    # data 카테고리 헤더는 보이지만 후보 없음 안내가 들어 있어야 한다.
    assert "category='data'" in out
    assert "no candidates" in out
