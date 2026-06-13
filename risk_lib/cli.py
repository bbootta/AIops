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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
