from tools import classify_error as ce


def test_pr_body_no_feedback(tmp_path):
    fp = tmp_path / "fb.jsonl"
    body = ce.generate_rule_patch_pr_body(feedback_path=fp)
    assert "## Summary" in body
    assert "## Test plan" in body
    assert "## Patch" in body
    # 후보가 없어도 PR body는 안전하게 작성된다.
    assert "0개" in body or "(없음)" in body


def test_pr_body_contains_patch_codeblock(tmp_path):
    fp = tmp_path / "fb.jsonl"
    ce.record_feedback("obscure pipeline thing happens", "documentation", feedback_path=fp)
    ce.record_feedback("another pipeline failure", "documentation", feedback_path=fp)
    body = ce.generate_rule_patch_pr_body(feedback_path=fp, min_occurrences=2)
    assert "```python" in body
    assert "pipeline" in body
    assert "documentation" in body
    assert "Test plan" in body
