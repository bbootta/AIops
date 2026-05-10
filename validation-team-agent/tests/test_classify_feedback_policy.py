import pytest

from tools import classify_error as ce


def test_blocks_feedback_with_email(tmp_path):
    fp = tmp_path / "fb.jsonl"
    with pytest.raises(ce.FeedbackPolicyError):
        ce.record_feedback(
            "Operation not permitted on ops box (admin@bank.example.com)",
            "permission",
            feedback_path=fp,
        )
    assert not fp.exists()


def test_allow_sensitive_overrides_block(tmp_path):
    fp = tmp_path / "fb.jsonl"
    rec = ce.record_feedback(
        "Operation not permitted on ops box (admin@bank.example.com)",
        "permission",
        feedback_path=fp,
        allow_sensitive=True,
    )
    assert rec["sensitive_overridden"] is True
    assert fp.exists()


def test_clean_feedback_writes_without_override(tmp_path):
    fp = tmp_path / "fb.jsonl"
    rec = ce.record_feedback(
        "VIF > 10 detected",
        "methodology",
        feedback_path=fp,
    )
    assert rec["sensitive_overridden"] is False


def test_notes_field_also_scanned(tmp_path):
    fp = tmp_path / "fb.jsonl"
    with pytest.raises(ce.FeedbackPolicyError):
        ce.record_feedback(
            "VIF > 10",
            "methodology",
            notes="reporter contact: secret@internal.example.com",
            feedback_path=fp,
        )
