from tools.report_template import build_validation_report


def test_korean_default_no_translation():
    md = build_validation_report({"title": "T", "summary": "표본 부족 한계"})
    assert "(sample)" not in md
    assert "표본" in md


def test_english_translates_glossary_terms():
    md = build_validation_report({"title": "T", "summary": "표본 부족 한계"}, lang="en")
    assert "표본 (sample)" in md
    assert "한계 (limitation)" in md


def test_english_no_translation_when_disabled():
    md = build_validation_report(
        {"title": "T", "summary": "표본 부족 한계"},
        lang="en",
        translate_body=False,
    )
    assert "(sample)" not in md
    assert "표본" in md
    assert "## 1. Summary" in md  # 제목은 영문 유지


def test_translation_handles_list_body():
    md = build_validation_report(
        {
            "title": "T",
            "limitations": ["표본 부족", "다중공선성 의심"],
        },
        lang="en",
    )
    assert "표본 (sample)" in md
    assert "다중공선성 (multicollinearity)" in md
