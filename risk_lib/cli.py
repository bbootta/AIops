"""CLI runner for the risk management harness.

Usage:
    python -m risk_lib.cli run                       # synthetic, prints summary
    python -m risk_lib.cli run --report report.md    # write markdown report
    python -m risk_lib.cli run --data book.csv       # use your own portfolio
    python -m risk_lib.cli run --seed 7 --floor 0.725
    python -m risk_lib.cli run --ccyb 0.005 --dsib 0.015 --years-ahead 3

    # CRO two-tier report package (executive + ops + manifest)
    python -m risk_lib.cli report-set --out cro/
    python -m risk_lib.cli report-set --out cro/ --portfolio book.csv

    # Reproducibility check
    python -m risk_lib.cli reproduce --manifest cro/manifest.json
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from risk_lib.pipeline import run_pipeline
from risk_lib.report import render_markdown


def _cmd_run(args: argparse.Namespace) -> int:
    portfolio = None
    if args.data:
        portfolio = pd.read_csv(args.data)

    buffers = {
        "capital_conservation": args.ccb,
        "countercyclical": args.ccyb,
        "dsib": args.dsib,
    }

    result = run_pipeline(
        portfolio,
        seed=args.seed,
        hurdle_rate=args.hurdle,
        output_floor=args.floor,
        buffers=buffers,
        years_ahead=args.years_ahead,
    )

    md = render_markdown(result)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"리포트 작성 완료: {args.report}")
    else:
        print(md)

    v = result.validation
    if not v.passes():
        print("\n[검증 실패] FAIL 체크가 존재하여 결재 불가.", file=sys.stderr)
        return 1
    return 0


def _cmd_report_set(args: argparse.Namespace) -> int:
    """Build two-tier HTML report package + RunManifest."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.html_report import build_full_report_package
    from risk_lib.repro import build_manifest, now_utc

    if args.portfolio:
        portfolio = pd.read_csv(args.portfolio)
    else:
        portfolio = generate_portfolio(seed=args.seed)

    buffers = {"capital_conservation": args.ccb,
               "countercyclical": args.ccyb, "dsib": args.dsib}
    start = now_utc()
    result = run_pipeline(portfolio, seed=args.seed,
                          hurdle_rate=args.hurdle, output_floor=args.floor,
                          buffers=buffers, years_ahead=args.years_ahead)
    end = now_utc()
    manifest = build_manifest(
        portfolio=portfolio,
        parameters={"seed": args.seed, "hurdle_rate": args.hurdle,
                    "output_floor": args.floor, "buffers": buffers,
                    "years_ahead": args.years_ahead},
        result=result, start_utc=start, end_utc=end,
        notes=args.notes or "",
    )
    written = build_full_report_package(result, args.out, portfolio=portfolio,
                                         manifest=manifest)
    print(f"\nCRO 패키지 작성 완료:")
    print(f"  executive.html — {written['executive']}")
    print(f"  manifest.json  — {written['manifest']}")
    print(f"  ops/ — {len([k for k in written if k.startswith('ops/')])}개 페이지")
    print(f"  headline digest: {manifest.headline_digest[:24]}...")
    return 0 if result.validation.passes() else 1


def _cmd_notify(args: argparse.Namespace) -> int:
    """Build alert payloads (slack JSON / email HTML / markdown) to a dir."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.notifications import collect_alerts, write_bundle
    from risk_lib.repro import build_manifest, now_utc

    portfolio = generate_portfolio(seed=args.seed)
    start = now_utc()
    result = run_pipeline(portfolio, seed=args.seed)
    end = now_utc()
    manifest = build_manifest(portfolio=portfolio, parameters={"seed": args.seed},
                              result=result, start_utc=start, end_utc=end)
    bundle = collect_alerts(result)
    bundle.headline_digest = manifest.headline_digest
    paths = write_bundle(bundle, args.out)
    print(f"알림 페이로드 {len(paths)}개 작성 — 최악 등급 {bundle.worst_severity()}")
    for k, v in paths.items():
        print(f"  {k}  →  {v}")
    # exit nonzero if there are any RED/FAIL alerts so CI can wake the team
    sev_max = bundle.worst_severity()
    return 0 if sev_max not in ("RED", "FAIL") else 2


def _cmd_serve(args: argparse.Namespace) -> int:
    """Run the JSON HTTP API server."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.repro import build_manifest, now_utc
    from risk_lib.api import serve

    portfolio = generate_portfolio(seed=args.seed)
    start = now_utc()
    result = run_pipeline(portfolio, seed=args.seed)
    end = now_utc()
    manifest = build_manifest(portfolio=portfolio, parameters={"seed": args.seed},
                              result=result, start_utc=start, end_utc=end)
    try:
        serve(result, manifest=manifest, host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    """Send alert payload to a webhook."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.integrations import dispatch_alerts
    portfolio = generate_portfolio(seed=args.seed)
    result = run_pipeline(portfolio, seed=args.seed)
    r = dispatch_alerts(result, args.url, kind=args.kind, dry_run=args.dry_run)
    if args.dry_run:
        print(f"[dry-run] POST {r.request.url}")
        print(f"  body ({len(r.request.body)} bytes): {r.request.body[:200]}...")
        return 0
    print(f"dispatch {'성공' if r.ok else '실패'} — status {r.status}"
          + (f" · error {r.error}" if r.error else ""))
    return 0 if r.ok else 2


def _cmd_api_spec(args: argparse.Namespace) -> int:
    """Emit OpenAPI + GraphQL schema files."""
    from risk_lib.integrations import write_api_specs
    paths = write_api_specs(args.out)
    print("API 스펙 작성 완료:")
    for k, v in paths.items():
        print(f"  {k} → {v}")
    return 0


def _cmd_export_json(args: argparse.Namespace) -> int:
    """Export all headline + deep-dive tables as JSON files."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.repro import build_manifest, now_utc
    from risk_lib.api import export_json

    portfolio = generate_portfolio(seed=args.seed)
    start = now_utc()
    result = run_pipeline(portfolio, seed=args.seed)
    end = now_utc()
    manifest = build_manifest(portfolio=portfolio, parameters={"seed": args.seed},
                              result=result, start_utc=start, end_utc=end)
    paths = export_json(result, args.out, manifest=manifest)
    print(f"JSON 내보내기 완료 ({len(paths)}개):")
    for k, v in paths.items(): print(f"  {k}  →  {v}")
    return 0


def _build_studio(args: argparse.Namespace):
    """CLI 두 명령이 같은 스냅샷을 쓰도록 조립을 한 곳에 둔다."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.ui_studio.studio import build_studio

    portfolio = generate_portfolio(seed=args.seed)
    result = run_pipeline(portfolio, seed=args.seed, asof=args.asof)
    return build_studio(result, portfolio,
                        institution=getattr(args, "institution", "(기관명)"))


def _cmd_reg_report(args: argparse.Namespace) -> int:
    """금감원 배포 기준 업무보고서 엑셀."""
    import os
    from risk_lib.regulatory import write_workbook

    studio = _build_studio(args)
    out = write_workbook(studio.built_forms, args.out, asof=studio.asof,
                         meta={"seed": args.seed,
                               "institution": args.institution})
    checks = studio.tables["reg_form_check"]
    n_fail = int((checks["status"] == "FAIL").sum())
    print(f"업무보고서 작성 완료 — {out} ({os.path.getsize(out)/1024:.1f} KB)")
    print(f"  서식 {len(studio.built_forms)}장 · 라인 "
          f"{len(studio.tables['reg_form_line']):,}행 · "
          f"자체대사 {len(checks)}건 (실패 {n_fail}건)")
    print(f"  산출 지문 {studio.digest[:16]} · 기준일 {studio.asof} · seed {args.seed}")
    if n_fail:
        print("  검증 실패가 있어 제출 상태는 draft로 남습니다.")
    return 1 if n_fail else 0


def _cmd_ui_studio(args: argparse.Namespace) -> int:
    """에이전틱 UI 스튜디오 — 전 모듈 관리 화면.

    --asof 는 콤마 목록을 받는다. 여러 기준일을 주면 실행을 전부 산출해 한
    화면에 싣고, 화면의 기준일 전환은 그 실행들 사이를 오간다 — 화면이
    즉석에서 새 기준일을 계산하는 것이 아니다.
    """
    import os
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.datamodel import catalog as cat
    from risk_lib.ui_studio.app import write_app
    from risk_lib.ui_studio.studio import build_studio

    asofs = [a.strip() for a in (args.asof or "").split(",") if a.strip()] or [None]
    portfolio = generate_portfolio(seed=args.seed)
    studios = []
    for a in asofs:
        result = run_pipeline(portfolio, seed=args.seed, asof=a)
        studios.append(build_studio(result, portfolio))
        print(f"  산출 {studios[-1].run_id} · 지문 {studios[-1].digest[:16]}")
    out = write_app(studios if len(studios) > 1 else studios[0], args.out)
    s = studios[-1]
    n_rows = sum(len(df) for df in s.tables.values())
    print(f"에이전틱 UI 작성 완료 — {out} ({os.path.getsize(out)/1024:.1f} KB)")
    print(f"  기준일 {len(studios)}종 · 테이블 {len(cat.ALL_TABLES)}장 · "
          f"행 {n_rows:,} (최신 기준) · 조회계획 {len(s.plans)}건")
    return 0


def _cmd_validation_request(args: argparse.Namespace) -> int:
    """상시 독립검증(3선) 요청 생성 + 게이트 확인."""
    from risk_lib.validation.independent import check_gate

    studio = _build_studio(args)
    path = studio.iv_request.write(args.dir)
    gate = check_gate(studio.iv_request, args.dir)
    print(f"독립검증 요청 작성 — {path}")
    print(f"  요청 {studio.iv_request.request_id} → "
          f"{studio.iv_request.requested_to} / {studio.iv_request.branch}")
    print(f"  재계산 대상 {len(studio.iv_request.recalc_targets)}종 · "
          f"도전 대상 가정 {len(studio.iv_request.known_assumptions)}건")
    sv = studio.iv_request.self_validation
    print(f"  자체검증(2선) " + " · ".join(f"{k} {v}" for k, v in sorted(sv.items())))
    print(f"  게이트 {gate.status} — {gate.reason}")
    # 게이트가 적합이 아니면 종료코드 1 — 결재 파이프라인이 조용히 지나가지 않는다.
    return 0 if gate.approved else 1


def _cmd_deliverables(args: argparse.Namespace) -> int:
    """산출물 보관 — 기준일자마다 판을 쌓고 이력을 스캔해 갱신한다."""
    from risk_lib.archive import ARCHIVE_ROOT, archive, write_ledger
    from risk_lib.data_gen import generate_portfolio

    root = args.root or ARCHIVE_ROOT
    portfolio = generate_portfolio(seed=args.seed)
    result = run_pipeline(portfolio, seed=args.seed, asof=args.asof)
    info = archive(result, portfolio, asof=args.asof, root=root,
                   run_date=args.run_date, seed=args.seed)
    paths = write_ledger(root)
    print(f"산출물 보관 — {root}/{info.asof}/{info.label}")
    print(f"  요청 {info.request_id} · 게이트 {info.gate_status}")
    print(f"  서식 {info.n_forms:,} · 라인 {info.n_form_lines:,} · "
          f"서식검증 실패 {info.n_form_checks_failed}")
    print(f"  제출본 지문 {info.submission_digest[:16]}… · "
          f"코드 {info.git_revision[:12]}")
    print(f"  이력 {paths['csv']} · {paths['md']}")
    # 게이트가 열리지 않았으면 종료코드로 알린다 — 결재 파이프라인이 조용히
    # 지나가지 않게 한다.
    return 0 if info.gate_status == "적합" else 1


def _cmd_printable(args: argparse.Namespace) -> int:
    """Generate a print-optimised single-file HTML. Open in browser and
    'Print -> Save as PDF' for a perfectly-rendered Korean PDF."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.repro import build_manifest, now_utc
    from risk_lib.printable import build_printable_html

    portfolio = generate_portfolio(seed=args.seed)
    start = now_utc()
    result = run_pipeline(portfolio, seed=args.seed)
    end = now_utc()
    manifest = build_manifest(portfolio=portfolio, parameters={"seed": args.seed},
                              result=result, start_utc=start, end_utc=end)
    out = build_printable_html(result, args.out, manifest=manifest)
    import os
    print(f"인쇄용 HTML 작성 완료 — {out} ({os.path.getsize(out)/1024:.1f} KB)")
    print(f"\nPDF로 저장하려면 브라우저로 이 파일을 열고 '인쇄 -> PDF로 저장'을 선택하세요.")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    """Compare N manifest.json files and emit a tidy history."""
    import json
    from pathlib import Path
    from risk_lib.comparison import history_from_manifests
    paths = [Path(p) for p in args.manifests]
    hist = history_from_manifests(paths)
    if args.out:
        Path(args.out).write_text(hist.to_csv(index=False), encoding="utf-8")
        print(f"history CSV: {args.out}")
    else:
        print(hist.to_string(index=False))
    return 0


def _cmd_reproduce(args: argparse.Namespace) -> int:
    """Re-run with the parameters saved in a manifest and verify digest match."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.repro import RunManifest, build_manifest, diff_manifests, now_utc

    saved = RunManifest.read(args.manifest)
    params = saved.parameters
    print(f"재현 시도 — 기존 digest: {saved.headline_digest[:24]}...")
    portfolio = generate_portfolio(seed=params.get("seed", 42))
    start = now_utc()
    result = run_pipeline(portfolio,
                          seed=params.get("seed", 42),
                          hurdle_rate=params.get("hurdle_rate", 0.10),
                          output_floor=params.get("output_floor", 0.725),
                          buffers=params.get("buffers"),
                          years_ahead=params.get("years_ahead", 2))
    end = now_utc()
    new_m = build_manifest(portfolio=portfolio, parameters=params,
                           result=result, start_utc=start, end_utc=end)
    print(f"신규 digest:           {new_m.headline_digest[:24]}...")
    if new_m.headline_digest == saved.headline_digest:
        print("✓ 재현 성공 — headline 다이제스트 정확히 일치")
        return 0
    diff = diff_manifests(saved, new_m)
    print("✗ 재현 실패 — 다음 필드가 변경됨:", file=sys.stderr)
    for k in diff:
        if k != "timing":
            print(f"  - {k}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="risk_lib", description="리스크관리 하네스 러너")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="전체 파이프라인 실행")
    run_p.add_argument("--data", help="포트폴리오 CSV 경로 (미지정 시 합성 데이터)")
    run_p.add_argument("--report", help="markdown 리포트 출력 경로")
    run_p.add_argument("--seed", type=int, default=42, help="재현성 시드")
    run_p.add_argument("--hurdle", type=float, default=0.10, help="RAPM hurdle rate")
    run_p.add_argument("--floor", type=float, default=0.725, help="output floor 비율")
    run_p.add_argument("--ccb", type=float, default=0.025,
                       help="자본보전버퍼 (default 2.5%%)")
    run_p.add_argument("--ccyb", type=float, default=0.0,
                       help="경기대응완충자본 (default 0%%)")
    run_p.add_argument("--dsib", type=float, default=0.01,
                       help="D-SIB 가산자본 (default 1.0%%)")
    run_p.add_argument("--years-ahead", type=int, default=2,
                       help="분기 스트레스/ECL 경로 지평(연도)")
    run_p.set_defaults(func=_cmd_run)

    # report-set
    rs = sub.add_parser("report-set", help="두 단계 HTML 보고서 패키지 생성 (CRO용)")
    rs.add_argument("--out", required=True, help="출력 디렉터리")
    rs.add_argument("--portfolio", help="포트폴리오 CSV (미지정 시 합성)")
    rs.add_argument("--seed", type=int, default=42)
    rs.add_argument("--hurdle", type=float, default=0.10)
    rs.add_argument("--floor", type=float, default=0.725)
    rs.add_argument("--ccb", type=float, default=0.025)
    rs.add_argument("--ccyb", type=float, default=0.0)
    rs.add_argument("--dsib", type=float, default=0.01)
    rs.add_argument("--years-ahead", type=int, default=2)
    rs.add_argument("--notes", default="", help="manifest에 기록할 메모")
    rs.set_defaults(func=_cmd_report_set)

    # reproduce
    rp = sub.add_parser("reproduce",
                        help="manifest를 재실행하여 headline digest 일치 검증")
    rp.add_argument("--manifest", required=True)
    rp.set_defaults(func=_cmd_reproduce)

    # notify
    nf = sub.add_parser("notify", help="Slack/이메일/Markdown 알림 페이로드 생성")
    nf.add_argument("--out", required=True, help="출력 디렉터리")
    nf.add_argument("--seed", type=int, default=42)
    nf.set_defaults(func=_cmd_notify)

    # serve
    sv = sub.add_parser("serve", help="JSON HTTP API 서버 실행")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--seed", type=int, default=42)
    sv.set_defaults(func=_cmd_serve)

    # export-json
    ej = sub.add_parser("export-json", help="모든 headline·deep-dive 표 JSON 저장")
    ej.add_argument("--out", required=True, help="출력 디렉터리")
    ej.add_argument("--seed", type=int, default=42)
    ej.set_defaults(func=_cmd_export_json)

    # printable (browser Print-to-PDF source)
    pp = sub.add_parser("printable",
                         help="경영진 1-pager 인쇄용 HTML (브라우저 'Print to PDF'로 PDF 생성)")
    pp.add_argument("--out", required=True, help="HTML 출력 경로")
    pp.add_argument("--seed", type=int, default=42)
    pp.set_defaults(func=_cmd_printable)

    # compare
    cmp_p = sub.add_parser("compare",
                            help="N개 manifest.json 비교 (시점 간 history)")
    cmp_p.add_argument("--manifests", nargs="+", required=True)
    cmp_p.add_argument("--out", help="CSV 저장 경로 (생략 시 stdout)")
    cmp_p.set_defaults(func=_cmd_compare)

    dp = sub.add_parser("dispatch", help="알림을 webhook(Slack 등)으로 발송")
    dp.add_argument("--url", required=True, help="webhook URL")
    dp.add_argument("--seed", type=int, default=42)
    dp.add_argument("--kind", default="slack",
                    choices=["slack", "teams", "pagerduty", "generic"])
    dp.add_argument("--dry-run", action="store_true",
                    help="발송하지 않고 요청만 출력")
    dp.set_defaults(func=_cmd_dispatch)

    ap = sub.add_parser("api-spec", help="OpenAPI + GraphQL 스키마 생성")
    ap.add_argument("--out", required=True, help="출력 디렉터리")
    ap.set_defaults(func=_cmd_api_spec)

    rg = sub.add_parser("reg-report",
                        help="금감원 배포 기준 업무보고서 엑셀 생성")
    rg.add_argument("--out", required=True, help=".xlsx 출력 경로")
    rg.add_argument("--seed", type=int, default=42)
    rg.add_argument("--asof", default=None, help="기준일 (YYYY-MM-DD)")
    rg.add_argument("--institution", default="(기관명)")
    rg.set_defaults(func=_cmd_reg_report)

    dv = sub.add_parser(
        "deliverables",
        help="산출물 Pack을 기준일자/수행일자·판 경로에 보관하고 이력을 갱신")
    dv.add_argument("--asof", required=True, help="기준일자 (YYYY-MM-DD)")
    dv.add_argument("--seed", type=int, default=42)
    dv.add_argument("--root", default=None,
                    help="보관 루트 (기본: 리스크관리 팀에이전트 경로)")
    dv.add_argument("--run-date", default=None,
                    help="수행일자 (기본: 오늘). 과거 판을 재구성할 때만 쓴다")
    dv.set_defaults(func=_cmd_deliverables)

    iv = sub.add_parser("validation-request",
                        help="상시 독립검증(3선) 요청 생성 + 게이트 확인")
    iv.add_argument("--dir", default="docs/independent_validation",
                    help="요청·응답 교환 디렉터리")
    iv.add_argument("--seed", type=int, default=42)
    iv.add_argument("--asof", default=None, help="기준일 (YYYY-MM-DD)")
    iv.set_defaults(func=_cmd_validation_request)

    ui = sub.add_parser("ui-studio",
                        help="에이전틱 UI 스튜디오 HTML 생성 (전 모듈 관리 화면)")
    ui.add_argument("--out", required=True, help="HTML 출력 경로")
    ui.add_argument("--seed", type=int, default=42)
    ui.add_argument("--asof", default=None,
                    help="기준일 (YYYY-MM-DD, 콤마로 여러 개 — 전부 산출해 싣는다)")
    ui.set_defaults(func=_cmd_ui_studio)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
