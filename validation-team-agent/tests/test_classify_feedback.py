import json
from pathlib import Path

import pytest

from tools import classify_error as ce


def test_record_feedback_creates_jsonl_entry(tmp_path: Path):
    fp = tmp_path / "fb.jsonl"
    rec = ce.record_feedback(
        "PermissionError: denied",
        confirmed_category="permission",
        feedback_path=fp,
    )
    assert rec["agreement"] is True
    assert rec["predicted_category"] == "permission"
    line = fp.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["confirmed_category"] == "permission"


def test_record_feedback_logs_disagreement(tmp_path: Path):
    fp = tmp_path / "fb.jsonl"
    rec = ce.record_feedback(
        "PermissionError: denied",
        confirmed_category="documentation",
        feedback_path=fp,
    )
    assert rec["agreement"] is False
    assert rec["predicted_category"] == "permission"


def test_record_feedback_rejects_invalid_category(tmp_path: Path):
    fp = tmp_path / "fb.jsonl"
    with pytest.raises(ValueError):
        ce.record_feedback("x", confirmed_category="nonsense", feedback_path=fp)


def test_feedback_summary_aggregates(tmp_path: Path):
    fp = tmp_path / "fb.jsonl"
    ce.record_feedback("PermissionError", "permission", feedback_path=fp)
    ce.record_feedback("PermissionError", "documentation", feedback_path=fp)
    ce.record_feedback("VIF > 10", "methodology", feedback_path=fp)
    summary = ce.feedback_summary(feedback_path=fp)
    assert summary["total"] == 3
    assert summary["agreement"] == 2
    assert summary["agreement_rate"] == pytest.approx(2 / 3)
    assert "permission->documentation" in summary["mismatches"]


def test_feedback_summary_returns_zero_when_no_file(tmp_path: Path):
    summary = ce.feedback_summary(feedback_path=tmp_path / "absent.jsonl")
    assert summary == {"total": 0, "agreement": 0, "agreement_rate": 0.0, "mismatches": {}}
