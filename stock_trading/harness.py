"""Orchestrator harness — coordinates the four specialist trading agents."""

import anthropic
from anthropic import beta_tool
from stock_trading.agents import market_analyst, risk_manager, portfolio_manager, trader

_client = anthropic.Anthropic()

_SYSTEM = """\
You are the Head of Trading at a quantitative hedge fund. You coordinate a team of \
four specialists to evaluate and execute trading decisions:

1. **Market Analyst** — technical and fundamental analysis, directional bias
2. **Risk Manager** — VaR calculation, position limits, risk approval
3. **Portfolio Manager** — allocation impact, diversification, construction review
4. **Trader** — order execution with minimal slippage

Your workflow for any trade idea:
1. Consult the Market Analyst for analysis and directional conviction
2. Consult the Risk Manager to assess risk and get approval
3. Consult the Portfolio Manager to evaluate portfolio-construction fit
4. Only instruct the Trader to execute if all three specialists support the trade
5. Deliver a concise final report summarizing the entire decision chain

If any specialist raises a hard block (risk limit breach, negative conviction, \
portfolio degradation), do NOT proceed to execution. Explain the decision clearly.\
"""


@beta_tool
def consult_market_analyst(query: str) -> str:
    """Consult the Market Analyst for technical and fundamental analysis.

    Args:
        query: Analysis request (e.g., 'Analyze AAPL for a potential 100-share buy').
    """
    print(f"\n  [Market Analyst] {query[:70]}...")
    result = market_analyst.analyze(query)
    print("  [Market Analyst] Analysis complete.")
    return result


@beta_tool
def consult_risk_manager(query: str) -> str:
    """Consult the Risk Manager to assess risk and check position limits.

    Args:
        query: Risk assessment request (e.g., 'Assess risk of buying 100 shares of AAPL').
    """
    print(f"\n  [Risk Manager] {query[:70]}...")
    result = risk_manager.assess(query)
    print("  [Risk Manager] Assessment complete.")
    return result


@beta_tool
def consult_portfolio_manager(query: str) -> str:
    """Consult the Portfolio Manager to evaluate portfolio construction impact.

    Args:
        query: Portfolio review request (e.g., 'Review impact of buying 100 shares of AAPL').
    """
    print(f"\n  [Portfolio Manager] {query[:70]}...")
    result = portfolio_manager.review(query)
    print("  [Portfolio Manager] Review complete.")
    return result


@beta_tool
def instruct_trader(query: str) -> str:
    """Instruct the Trader to execute an approved order.

    Only call this after receiving approval from both the Risk Manager and
    Portfolio Manager.

    Args:
        query: Execution instruction (e.g., 'Execute a buy of 100 shares of AAPL — approved').
    """
    print(f"\n  [Trader] {query[:70]}...")
    result = trader.execute(query)
    print("  [Trader] Execution complete.")
    return result


def run(scenario: str) -> None:
    """Run the full trading team harness for the given scenario."""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario}")
    print(f"{'='*60}")

    last_text = ""
    for message in _client.beta.messages.tool_runner(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[consult_market_analyst, consult_risk_manager, consult_portfolio_manager, instruct_trader],
        messages=[{"role": "user", "content": scenario}],
    ):
        for block in message.content:
            if block.type == "text" and block.text:
                last_text = block.text

    print(f"\n{'='*60}")
    print("ORCHESTRATOR FINAL REPORT")
    print(f"{'='*60}")
    print(last_text)
