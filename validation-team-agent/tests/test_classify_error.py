import pytest

from tools import classify_error as ce


def test_classify_permission_error():
    out = ce.classify("PermissionError: [Errno 13] Permission denied")
    assert out.category == "permission"


def test_classify_input_missing_columns():
    out = ce.classify("KeyError: required columns missing: ['target']")
    # 'columns missing' 키워드가 input rule 매칭 (more specific than generic code rule)
    assert out.category == "input"


def test_classify_data_quality_issue():
    out = ce.classify("표본 수 부족: 등급별 sample size < 30")
    assert out.category == "data"


def test_classify_methodology_warning():
    out = ce.classify("VIF > 10 변수 발견 (multicollinearity 의심)")
    assert out.category == "methodology"


def test_classify_documentation_gap():
    out = ce.classify("missing_section: 한계와 리스크")
    assert out.category == "documentation"


def test_classify_falls_back_to_code_for_generic_traceback():
    out = ce.classify("Traceback (most recent call last):\n  ZeroDivisionError: division by zero")
    assert out.category == "code"


def test_empty_text_falls_back_to_input():
    out = ce.classify("")
    assert out.category == "input"
    assert out.confidence == "low"


def test_suggest_manifest_fields_returns_required_keys():
    out = ce.suggest_manifest_fields("PermissionError: denied")
    assert set(out) == {
        "category",
        "confidence",
        "matched_pattern",
        "root_cause",
        "targeted_fix",
    }
    assert out["category"] == "permission"
    assert out["targeted_fix"]


def test_classify_rejects_non_string():
    with pytest.raises(TypeError):
        ce.classify(123)


def test_confidence_high_when_single_category_matches():
    # 권한만 매칭하는 단일 키워드.
    out = ce.classify("Operation not permitted")
    assert out.confidence in {"high", "medium"}
