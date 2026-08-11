"""Round 31 — Q5-1: 보고서 PDF 출력 (워터마크 강제)."""

from __future__ import annotations

import pytest

from tools.report_pdf import WatermarkMissingError, pdf_available, render_pdf

_WATERMARKED_MD = None


def _watermarked_md() -> str:
    global _WATERMARKED_MD
    if _WATERMARKED_MD is None:
        from tools.report_template import build_validation_report

        _WATERMARKED_MD = build_validation_report({
            "title": "PDF 테스트 보고서",
            "summary": "합성 데이터 점검 요약 (출처: `tests/test_v2_round31.py`).",
            "purpose": "PDF 변환 단위 테스트.",
            "input_data": ["합성 표본"],
            "method": ["render_pdf"],
            "results": "- 점검값 1.0 (출처: `tests/test_v2_round31.py`)",
            "anomalies": "- 없음.",
            "limitations": ["테스트 전용"],
            "draft_opinion": "테스트 — 의견 아님.",
            "follow_ups": ["없음"],
            "audit_trail": "tests/test_v2_round31.py",
        })
    return _WATERMARKED_MD


# ---------- 워터마크 강제 (weasyprint 불필요) ----------

def test_render_pdf_refuses_without_watermark(tmp_path):
    with pytest.raises(WatermarkMissingError):
        render_pdf("# 제목\n본문", tmp_path / "x.pdf")


def test_render_pdf_refuses_header_only(tmp_path):
    md = "> [DRAFT — 외부 제출 금지] 인간 검증자 승인 전 사용 불가\n\n# 제목\n"
    with pytest.raises(WatermarkMissingError):
        render_pdf(md, tmp_path / "x.pdf")


def test_watermark_error_is_value_error():
    assert issubclass(WatermarkMissingError, ValueError)


# ---------- 실제 PDF 렌더 (weasyprint 있을 때만) ----------

needs_pdf = pytest.mark.skipif(not pdf_available(), reason="weasyprint 미설치 (선택 의존성)")


@needs_pdf
def test_render_pdf_creates_file(tmp_path):
    out = render_pdf(_watermarked_md(), tmp_path / "r.pdf", title="t")
    data = out.read_bytes()
    assert data[:5] == b"%PDF-"
    assert len(data) > 1_000


@needs_pdf
def test_cli_demo_generates_pdf(tmp_path):
    from tools.report_pdf import main

    out = tmp_path / "demo.pdf"
    rc = main(["--demo", "--out", str(out)])
    assert rc == 0
    assert out.read_bytes()[:5] == b"%PDF-"


@needs_pdf
def test_cli_refuses_unwatermarked_input(tmp_path):
    from tools.report_pdf import main

    src = tmp_path / "bad.md"
    src.write_text("# 제목\n워터마크 없음\n", encoding="utf-8")
    rc = main(["--in", str(src), "--out", str(tmp_path / "bad.pdf")])
    assert rc == 1
    assert not (tmp_path / "bad.pdf").exists()


# ---------- CLI dispatch ----------

def test_vta_cli_has_report_pdf_dispatch():
    from vta.cli.__main__ import _DISPATCH

    assert _DISPATCH[("report", "pdf")] == "tools.report_pdf"
