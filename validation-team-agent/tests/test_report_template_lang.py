import pytest

from tools.report_template import (
    SECTION_TITLES,
    SECTION_TITLES_EN,
    build_validation_report,
)


def test_korean_default():
    md = build_validation_report({"title": "T", "summary": "ok"})
    assert "## 1. 요약" in md
    assert "## 10. 감사추적 및 변경 이력" in md


def test_english_lang_emits_english_titles():
    md = build_validation_report({"title": "T", "summary": "ok"}, lang="en")
    assert "## 1. Summary" in md
    assert "## 10. Audit Trail and Change History" in md


def test_english_keeps_korean_watermark_for_guard_compatibility():
    md = build_validation_report({"title": "T", "summary": "ok"}, lang="en")
    # 워터마크 점검 도구가 한글 문구를 기대하므로 한글 워터마크는 보존되어야 한다.
    assert "본 문서는 검증 보조 산출물 초안입니다" in md
    assert "외부 제출 금지" in md
    # 영어 안내도 함께 노출.
    assert "human reviewer approval" in md


def test_unsupported_lang_raises():
    with pytest.raises(ValueError):
        build_validation_report({"title": "T"}, lang="ja")


def test_section_titles_have_same_keys_in_both_langs():
    assert set(SECTION_TITLES) == set(SECTION_TITLES_EN)
