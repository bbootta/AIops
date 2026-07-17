"""Report package orchestrator.

`build_report_set(result, out_dir)`  — page_registry.PAGES 기반으로 전체 페이지
세트(66p)를 기록. `build_full_report_package` — executive/printable/board pack/
audit ledger/manifest + ops/ 2계층 패키지를 산출.

페이지 빌더는 risk_lib/ops_pages/ (core_* 포함), chrome은 report_chrome 참조.
"""

from __future__ import annotations

from pathlib import Path

from risk_lib.pipeline import PipelineResult
from risk_lib.page_registry import PAGES
# Re-exported for the many consumers (board_pack, printable, localization,
# html_exec, systemic, case_studies, ...) that import chrome from here.
from risk_lib.report_chrome import (  # noqa: F401
    CSS, NAV, ALM_SUB,
    _nav_html, _page, _table, _kpi, _badge, _won, _pct, _esc,
)


# ============================================================================
# Builder
# ============================================================================


def build_report_set(result: PipelineResult, out_dir: str | Path,
                     portfolio=None) -> dict[str, str]:
    """Write the whole report set to out_dir; return {filename: absolute path}.

    Page set is driven by page_registry.PAGES; builders resolve lazily so
    the ops_pages modules (which import this module's chrome) load on demand.
    `portfolio` is required for Pillar 3 / vintage / DQ pages — those are
    skipped if it is omitted.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for spec in PAGES:
        if spec.needs_portfolio and portfolio is None:
            continue
        builder = spec.resolve()
        content = (builder(result, portfolio) if spec.needs_portfolio
                   else builder(result))
        p = out / spec.filename
        p.write_text(content, encoding="utf-8")
        written[spec.filename] = str(p.resolve())
    return written


def _quarter_label(asof_iso: str) -> str:
    y, m = asof_iso[:4], int(asof_iso[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def build_full_report_package(
    result: PipelineResult,
    out_dir: str | Path,
    *,
    portfolio=None,
    manifest=None,
    history_path: str | Path | None = None,
) -> dict[str, str]:
    """Two-tier package: executive.html (root) + ops/ (operational deep-dive)
    plus manifest.json. Returns {label: absolute_path}.

    The CRO opens executive.html; analysts use ops/index.html. All cross-links
    are relative so the directory is portable.

    `history_path`: 분기 축적 원장(JSON) 경로. 주면 이번 manifest 스냅샷을
    append(같은 분기는 교체)하고 trend_history.html을 산출하며, 2기 이상
    쌓이면 경영진 보고서에 전기 대비(QoQ) 섹션이 나타난다.
    """
    from risk_lib.html_exec import build_executive
    from risk_lib.printable import build_printable_html
    from risk_lib.audit_trail import build_ledger_from_result
    from risk_lib.board_pack import build_board_pack
    from risk_lib.localization import build_english_board_pack
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    ops_dir = out / "ops"
    written_ops = build_report_set(result, ops_dir, portfolio=portfolio)

    # 시계열 원장 축적 + QoQ 추세 (2기 이상일 때만 exec 노출)
    trend_flags = None
    trend_path = None
    if history_path is not None and manifest is not None:
        from risk_lib.timeseries_ledger import (
            TimeSeriesLedger, build_timeseries_report)
        ts = TimeSeriesLedger.load(history_path)
        period = _quarter_label(str(manifest.parameters.get("asof", "")) or
                                result.meta["asof"])
        ts.add_from_manifest(period, manifest)
        ts.save(history_path)
        trend_path = build_timeseries_report(ts, out / "trend_history.html")
        if len(ts.snapshots) >= 2:
            trend_flags = ts.trend_flags()

    exec_path = build_executive(result, out,
                                manifest_digest=getattr(manifest, "headline_digest", ""),
                                trend_flags=trend_flags)
    # printable HTML is the recommended PDF route — browser Print-to-PDF
    printable_path = build_printable_html(result, out / "printable.html",
                                           manifest=manifest)
    manifest_path = None
    if manifest is not None:
        manifest_path = out / "manifest.json"
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    # Audit ledger + Risk Committee board pack (Top-IB style)
    git_commit = (manifest.code.get("git_commit", "")
                  if manifest is not None else "")
    ledger = build_ledger_from_result(result, git_commit=git_commit or "")
    ledger_path = ledger.export_json(out / "audit_ledger.json")
    board_pack_path = build_board_pack(
        result, out / "board_pack.html",
        ledger_path=str(out / "audit_ledger.json"),
    )
    board_pack_en_path = build_english_board_pack(
        result, out / "board_pack_en.html")
    return {
        "executive": str(exec_path.resolve()),
        "printable": str(printable_path),
        "board_pack": board_pack_path,
        "board_pack_en": board_pack_en_path,
        "audit_ledger": ledger_path,
        "ops_dir": str(ops_dir.resolve()),
        **{f"ops/{k}": v for k, v in written_ops.items()},
        **({"manifest": str(manifest_path.resolve())} if manifest_path else {}),
        **({"trend_history": trend_path,
            "history_ledger": str(Path(history_path).resolve())}
           if trend_path else {}),
    }
