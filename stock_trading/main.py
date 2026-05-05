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
  python -m stock_trading.main [--research] '<your scenario>'

Flags:
  --research    Research-only mode — analysts consulted, no trades executed.\
"""


if __name__ == "__main__":
    args = sys.argv[1:]
    research_only = False
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
