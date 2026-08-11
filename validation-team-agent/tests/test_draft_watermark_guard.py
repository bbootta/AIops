from middleware import draft_watermark_guard as g


_FULL = """# 보고서

> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가

## 1. 요약
요약.

> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 인간 검증자의 검토와 승인을 거쳐야 합니다.
"""

_NO_HEADER = """# 보고서

## 1. 요약
요약.

> 본 문서는 검증 보조 산출물 초안입니다. 최종 검증 의견과 외부 제출은 인간 검증자의 검토와 승인을 거쳐야 합니다.
"""

_NO_FOOTER = """# 보고서

> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가

## 1. 요약
요약.
"""


def test_passes_with_both_marks():
    out = g.check_watermarks(_FULL)
    assert out == {"passed": True, "has_header": True, "has_footer": True}


def test_detects_missing_header():
    out = g.check_watermarks(_NO_HEADER)
    assert out["has_header"] is False
    assert out["has_footer"] is True
    assert out["passed"] is False


def test_detects_missing_footer():
    out = g.check_watermarks(_NO_FOOTER)
    assert out["has_header"] is True
    assert out["has_footer"] is False
    assert out["passed"] is False


def test_ensure_inserts_missing_marks():
    fixed = g.ensure_watermarks("# 보고서\n\n## 1. 요약\n요약.\n")
    out = g.check_watermarks(fixed)
    assert out["passed"] is True


def test_ensure_does_not_duplicate_existing_marks():
    fixed = g.ensure_watermarks(_FULL)
    assert fixed.count(g.HEADER_MARK) == 1
    assert fixed.count("본 문서는 검증 보조 산출물 초안입니다") == 1


def test_report_template_emits_watermarks():
    from tools.report_template import build_validation_report

    md = build_validation_report({"title": "T", "summary": "ok"})
    assert g.check_watermarks(md)["passed"] is True
