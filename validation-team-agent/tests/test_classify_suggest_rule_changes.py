from pathlib import Path

from tools import classify_error as ce


def test_no_feedback_returns_empty(tmp_path):
    out = ce.suggest_rule_changes(feedback_path=tmp_path / "absent.jsonl")
    assert out == []


def test_aggregates_keywords_per_confirmed_category(tmp_path):
    fp = tmp_path / "fb.jsonl"
    # documentation으로 confirmed지만 분류기는 매칭 안 됨 (mismatch). 같은 키워드 'pipeline' 2회 등장.
    ce.record_feedback("obscure pipeline thing happens", "documentation", feedback_path=fp)
    ce.record_feedback("another pipeline thing breaks", "documentation", feedback_path=fp)
    out = ce.suggest_rule_changes(feedback_path=fp, min_occurrences=2, top_k=3)
    docs = next(r for r in out if r["confirmed_category"] == "documentation")
    keys = dict(docs["suggested_keywords"])
    assert keys.get("pipeline") == 2
    assert docs["n_samples"] == 2


def test_filters_below_min_occurrences(tmp_path):
    fp = tmp_path / "fb.jsonl"
    # 분류기 매칭 안 되는 토큰들로 mismatch 유도. 같은 토큰이 2회 등장하지 않도록 모두 다른 단어.
    ce.record_feedback("alpha quark", "data", feedback_path=fp)
    ce.record_feedback("beta gluon", "data", feedback_path=fp)
    out = ce.suggest_rule_changes(feedback_path=fp, min_occurrences=2)
    data_row = next(r for r in out if r["confirmed_category"] == "data")
    assert data_row["suggested_keywords"] == []


def test_skips_agreement_records(tmp_path):
    fp = tmp_path / "fb.jsonl"
    # PermissionError → permission 매칭 → agreement=True. 키워드 추출 대상 아님.
    ce.record_feedback("PermissionError denied", "permission", feedback_path=fp)
    ce.record_feedback("PermissionError denied", "permission", feedback_path=fp)
    out = ce.suggest_rule_changes(feedback_path=fp, min_occurrences=2)
    assert out == []
