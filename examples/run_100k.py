"""대규모(10만건) 익스포저 샘플로 전 부문 산출 + 보고서 생성 데모.

생성 → PD모형 → RWA(SA/IRB/시장/운영) → output floor → BIS → 레버리지 →
IFRS9 ECL(+분기 충당금 경로) → 모니터링 → 한도/집중 → RAPM →
스트레스(순/역/분기 자본경로) → 자체검증까지 한 번에 실행한다.

실행:
    python examples/run_100k.py                 # 요약 출력
    python examples/run_100k.py report_100k.md  # markdown 리포트 저장
"""

from __future__ import annotations

import sys
import time

from risk_lib.data_gen import generate_portfolio
from risk_lib.pipeline import run_pipeline
from risk_lib.report import render_markdown


def build_portfolio(seed: int = 2026):
    return generate_portfolio(
        n_corporate=28_000, n_retail=52_000, n_mortgage=18_000,
        n_sovereign=900, n_bank=1_100, seed=seed,
    )


def main() -> int:
    seed = 2026
    t0 = time.time()
    portfolio = build_portfolio(seed)
    result = run_pipeline(portfolio, seed=seed)
    md = render_markdown(result)
    elapsed = time.time() - t0

    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(md)

    v = result.validation
    print(f"익스포저: {len(portfolio):,}건  EAD: {portfolio['ead'].sum()/1e12:.1f}조")
    print(f"최종 RWA: {result.rwa['final_total']/1e12:.1f}조  "
          f"CET1: {result.bis.cet1_ratio:.2%}  "
          f"ECL(TTC): {result.ecl['total']/1e9:,.0f}십억")
    print(f"검증: {'PASS' if v.passes() else 'FAIL'}  {v.summary()}")
    print(f"소요: {elapsed:.1f}s")
    if out_path:
        print(f"리포트 저장: {out_path}")
    return 0 if v.passes() else 1


if __name__ == "__main__":
    raise SystemExit(main())
