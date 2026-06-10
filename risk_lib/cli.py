"""CLI runner for the risk management harness.

Usage:
    python -m risk_lib.cli run                       # synthetic, prints summary
    python -m risk_lib.cli run --report report.md    # write markdown report
    python -m risk_lib.cli run --data book.csv       # use your own portfolio
    python -m risk_lib.cli run --seed 7 --floor 0.725
    python -m risk_lib.cli run --ccyb 0.005 --dsib 0.015 --years-ahead 3
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
