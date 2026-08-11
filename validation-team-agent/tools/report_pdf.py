"""검증 보고서 markdown → PDF 변환 (Q5-1).

``tools.report_template.render_html`` 의 print-friendly HTML 을 weasyprint 로
PDF 렌더링한다. weasyprint 는 **선택 의존성** (`pip install .[pdf]`) 이며,
미설치 환경에서는 명확한 안내와 함께 실패한다.

통제 (CLAUDE.md §5):
- DRAFT 워터마크 (헤더+푸터) 가 없는 보고서는 변환을 **거부**한다 — PDF 는
  유통되기 쉬운 형식이므로 외부 제출본 확정 금지 원칙을 코드로 강제한다.
- 본 도구의 산출물 역시 검증 보조 자료이며 최종 확정본이 아니다.

사용:
    python -m tools.report_pdf --in reports/workflow_100k.md --out reports/workflow_100k.pdf
    python -m tools.report_pdf --demo --out reports/demo.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class WatermarkMissingError(ValueError):
    """DRAFT 워터마크가 없는 보고서의 PDF 변환 시도."""


def pdf_available() -> bool:
    """weasyprint 가용 여부 (선택 의존성)."""
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def render_pdf(
    report_md: str,
    out_path: str | Path,
    *,
    title: str | None = None,
    page_break_before_h2: bool = True,
) -> Path:
    """워터마크 검증 후 markdown 보고서를 PDF 로 변환한다.

    Raises:
        WatermarkMissingError: DRAFT 헤더/푸터 워터마크 누락 시.
        ImportError: weasyprint 미설치 시.
    """
    from middleware.draft_watermark_guard import check_watermarks
    from tools.report_template import render_html

    wm = check_watermarks(report_md)
    if not wm["passed"]:
        raise WatermarkMissingError(
            "DRAFT 워터마크 누락 (header="
            f"{wm['has_header']}, footer={wm['has_footer']}). "
            "PDF 는 유통 위험이 커 워터마크 없는 보고서는 변환하지 않는다. "
            "tools.report_template.build_validation_report 로 생성한 보고서를 사용할 것."
        )

    try:
        import weasyprint
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise ImportError(
            "weasyprint 미설치 — PDF 변환은 선택 기능이다. "
            "`pip install validation-team-agent[pdf]` 또는 `pip install weasyprint`."
        ) from exc

    html = render_html(
        report_md,
        title=title,
        print_friendly=True,
        page_break_before_h2=page_break_before_h2,
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    weasyprint.HTML(string=html).write_pdf(str(out))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="report markdown → PDF (DRAFT 전용)")
    parser.add_argument("--in", dest="in_path", type=Path, default=None,
                        help="입력 markdown 보고서 경로")
    parser.add_argument("--demo", action="store_true",
                        help="합성 데이터 워크플로우 데모 보고서로 PDF 생성")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default=None)
    args = parser.parse_args(argv)

    if args.demo:
        from tools.run_workflow_demo import build_report_markdown, run_demo

        demo = run_demo(2_000, False, 42,
                        Path(__file__).resolve().parent.parent / "logs")
        md = build_report_markdown(demo, stress=False)
    elif args.in_path:
        md = args.in_path.read_text(encoding="utf-8")
    else:
        parser.error("--in 또는 --demo 중 하나가 필요하다")
        return 2

    try:
        out = render_pdf(md, args.out, title=args.title)
    except WatermarkMissingError as exc:
        sys.stderr.write(f"거부: {exc}\n")
        return 1
    sys.stdout.write(f"PDF 생성: {out} ({out.stat().st_size:,} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
