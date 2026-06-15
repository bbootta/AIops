"""Entry point for the stock trading team agent harness."""

import sys
from stock_trading.harness import run

SCENARIOS = [
    "We have a buy signal on AAPL. Evaluate buying 100 shares and execute if appropriate.",
    "Consider trimming our GOOGL position by 15 shares given recent antitrust news.",
    "Evaluate buying 200 shares of NVDA given the AI tailwinds — be aggressive if the risk profile allows.",
    "Review our current portfolio and suggest any rebalancing trades needed.",
]

USAGE = """\
Usage:
  python -m stock_trading.main [--execute] '<your scenario>'

Flags:
  --execute    Enable the Trader tool (full pipeline). Default is research-only.
               Even with --execute, place_order is a no-op unless
               STOCK_TRADING_LIVE=1 is also set in the environment.\
"""


if __name__ == "__main__":
    args = sys.argv[1:]
    # Safe default: research-only. Caller must opt in to execution.
    research_only = True
    if "--execute" in args:
        research_only = False
        args = [a for a in args if a != "--execute"]
    # Keep --research as an explicit no-op alias so existing invocations
    # still work and clearly read as "research-only".
    if "--research" in args:
        research_only = True
        args = [a for a in args if a != "--research"]

    if args:
        scenario = " ".join(args)
    else:
        scenario = SCENARIOS[0]
        print(f"No scenario provided. Using default:\n  {scenario}\n")
        print(USAGE)
        print("\nOther example scenarios:")
        for i, s in enumerate(SCENARIOS[1:], 1):
            print(f"  {i}. {s}")
        print()

    run(scenario, research_only=research_only)
