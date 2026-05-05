"""Entry point for the stock trading team agent harness."""

import sys
from stock_trading.harness import run

SCENARIOS = [
    "We have a buy signal on AAPL. Evaluate buying 100 shares and execute if appropriate.",
    "Consider trimming our GOOGL position by 15 shares given recent antitrust news.",
    "Evaluate buying 200 shares of NVDA given the AI tailwinds — be aggressive if the risk profile allows.",
    "Review our current portfolio and suggest any rebalancing trades needed.",
]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        scenario = " ".join(sys.argv[1:])
    else:
        scenario = SCENARIOS[0]
        print(f"No scenario provided. Using default:\n  {scenario}\n")
        print("Usage: python -m stock_trading.main '<your scenario>'")
        print(f"Other examples:")
        for i, s in enumerate(SCENARIOS[1:], 1):
            print(f"  {i}. {s}")
        print()

    run(scenario)
