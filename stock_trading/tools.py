"""Shared mock market data and trading utilities used by all specialist agents."""

import random
from datetime import date, timedelta

_PRICES: dict[str, float] = {
    "AAPL": 185.50,
    "GOOGL": 175.20,
    "MSFT": 415.80,
    "AMZN": 198.60,
    "TSLA": 172.30,
    "NVDA": 875.40,
    "META": 505.10,
}

_PORTFOLIO: dict = {
    "cash": 100_000.0,
    "positions": {
        "MSFT": {"shares": 50, "avg_cost": 400.00},
        "GOOGL": {"shares": 30, "avg_cost": 160.00},
    },
}

_ORDERS: list[dict] = []


def get_price(symbol: str) -> dict:
    symbol = symbol.upper()
    if symbol not in _PRICES:
        return {"error": f"Unknown symbol: {symbol}"}
    price = _PRICES[symbol]
    change_pct = random.uniform(-2.5, 2.5)
    prev_close = price / (1 + change_pct / 100)
    return {
        "symbol": symbol,
        "price": round(price, 2),
        "change": round(price - prev_close, 2),
        "change_pct": round(change_pct, 2),
        "volume": random.randint(5_000_000, 80_000_000),
    }


def get_history(symbol: str, days: int = 30) -> dict:
    symbol = symbol.upper()
    if symbol not in _PRICES:
        return {"error": f"Unknown symbol: {symbol}"}
    base = _PRICES[symbol]
    history = []
    price = base * 0.85
    today = date.today()
    for i in range(days):
        price *= 1 + random.uniform(-0.025, 0.028)
        history.append({
            "date": str(today - timedelta(days=days - i)),
            "close": round(price, 2),
        })
    history[-1]["close"] = round(base, 2)
    return {"symbol": symbol, "history": history}


def get_technicals(symbol: str) -> dict:
    symbol = symbol.upper()
    if symbol not in _PRICES:
        return {"error": f"Unknown symbol: {symbol}"}
    price = _PRICES[symbol]
    return {
        "symbol": symbol,
        "rsi_14": round(random.uniform(30, 70), 1),
        "macd": round(random.uniform(-5, 5), 2),
        "macd_signal": round(random.uniform(-4, 4), 2),
        "sma_20": round(price * random.uniform(0.95, 1.05), 2),
        "sma_50": round(price * random.uniform(0.90, 1.10), 2),
        "bollinger_upper": round(price * 1.08, 2),
        "bollinger_lower": round(price * 0.92, 2),
    }


_NEWS: dict[str, list[str]] = {
    "AAPL": [
        "Apple reports record iPhone sales in Q1 2026",
        "Analysts raise AAPL price target to $210 on AI integration",
    ],
    "GOOGL": [
        "Google Cloud revenue beats estimates, up 28% YoY",
        "Antitrust ruling may impact Google's search dominance",
    ],
    "MSFT": [
        "Microsoft Copilot adoption surges across enterprise",
        "Azure growth reaccelerates to 35% in latest quarter",
    ],
    "AMZN": [
        "Amazon AWS launches new AI inference chips",
        "Prime membership hits 300M globally",
    ],
    "TSLA": [
        "Tesla Full Self-Driving v13 receives regulatory approval",
        "EV price competition intensifies in China market",
    ],
    "NVDA": [
        "NVIDIA Blackwell GPUs sold out through 2026",
        "Data center revenue up 140% as AI buildout continues",
    ],
    "META": [
        "Meta AI assistant reaches 1 billion monthly active users",
        "Reality Labs VR headset sales disappoint",
    ],
}


def get_news(symbol: str) -> dict:
    symbol = symbol.upper()
    headlines = _NEWS.get(symbol, [f"No recent news for {symbol}"])
    return {"symbol": symbol, "headlines": headlines}


def get_portfolio() -> dict:
    total_value = _PORTFOLIO["cash"]
    positions_detail = {}
    for sym, pos in _PORTFOLIO["positions"].items():
        if sym in _PRICES:
            market_value = pos["shares"] * _PRICES[sym]
            total_value += market_value
            positions_detail[sym] = {
                "shares": pos["shares"],
                "avg_cost": pos["avg_cost"],
                "current_price": _PRICES[sym],
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(market_value - pos["shares"] * pos["avg_cost"], 2),
            }
    return {
        "cash": round(_PORTFOLIO["cash"], 2),
        "positions": positions_detail,
        "total_value": round(total_value, 2),
    }


def compute_var(symbol: str, shares: int, confidence: float = 0.95) -> dict:
    if symbol.upper() not in _PRICES:
        return {"error": f"Unknown symbol: {symbol}"}
    price = _PRICES[symbol.upper()]
    position_value = price * shares
    daily_vol = random.uniform(0.015, 0.035)
    z = 1.645 if confidence == 0.95 else 2.326
    var = round(position_value * daily_vol * z, 2)
    return {
        "symbol": symbol.upper(),
        "shares": shares,
        "position_value": round(position_value, 2),
        "daily_volatility_pct": round(daily_vol * 100, 2),
        "var_95_daily": var,
        "confidence": confidence,
    }


def check_limits(symbol: str, shares: int, side: str) -> dict:
    symbol = symbol.upper()
    port = get_portfolio()
    total = port["total_value"]
    price = _PRICES.get(symbol, 0)
    trade_value = price * shares

    current_position_value = 0.0
    if symbol in port["positions"]:
        current_position_value = port["positions"][symbol]["market_value"]

    if side.lower() == "buy":
        new_position_value = current_position_value + trade_value
    else:
        new_position_value = max(0.0, current_position_value - trade_value)

    position_pct = (new_position_value / total * 100) if total > 0 else 0
    cash_after = port["cash"] - trade_value if side.lower() == "buy" else port["cash"] + trade_value
    cash_pct = (cash_after / total * 100) if total > 0 else 0

    violations = []
    if position_pct > 20:
        violations.append(f"{symbol} would be {position_pct:.1f}% of portfolio (max 20%)")
    if cash_pct < 10:
        violations.append(f"Cash would drop to {cash_pct:.1f}% of portfolio (min 10%)")
    if side.lower() == "buy" and cash_after < 0:
        violations.append("Insufficient cash for this trade")

    return {
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "trade_value": round(trade_value, 2),
        "position_pct_after": round(position_pct, 2),
        "cash_pct_after": round(cash_pct, 2),
        "violations": violations,
        "approved": len(violations) == 0,
    }


def place_order(symbol: str, side: str, shares: int) -> dict:
    symbol = symbol.upper()
    if symbol not in _PRICES:
        return {"error": f"Unknown symbol: {symbol}", "status": "REJECTED"}

    price = _PRICES[symbol]
    slippage = random.uniform(0.0005, 0.002)
    exec_price = price * (1 + slippage) if side.lower() == "buy" else price * (1 - slippage)
    exec_price = round(exec_price, 2)
    total_cost = exec_price * shares

    if side.lower() == "buy":
        if _PORTFOLIO["cash"] < total_cost:
            return {"status": "REJECTED", "reason": "Insufficient cash", "required": total_cost, "available": _PORTFOLIO["cash"]}
        _PORTFOLIO["cash"] -= total_cost
        if symbol in _PORTFOLIO["positions"]:
            pos = _PORTFOLIO["positions"][symbol]
            new_shares = pos["shares"] + shares
            new_avg = (pos["shares"] * pos["avg_cost"] + shares * exec_price) / new_shares
            pos["shares"] = new_shares
            pos["avg_cost"] = round(new_avg, 2)
        else:
            _PORTFOLIO["positions"][symbol] = {"shares": shares, "avg_cost": exec_price}
    else:
        pos = _PORTFOLIO["positions"].get(symbol)
        if not pos or pos["shares"] < shares:
            held = pos["shares"] if pos else 0
            return {"status": "REJECTED", "reason": "Insufficient shares", "required": shares, "held": held}
        _PORTFOLIO["cash"] += total_cost
        pos["shares"] -= shares
        if pos["shares"] == 0:
            del _PORTFOLIO["positions"][symbol]

    order = {
        "order_id": f"ORD-{len(_ORDERS) + 1:04d}",
        "symbol": symbol,
        "side": side.upper(),
        "shares": shares,
        "exec_price": exec_price,
        "total_value": round(total_cost, 2),
        "slippage_bps": round(slippage * 10000, 1),
        "status": "FILLED",
    }
    _ORDERS.append(order)
    return order
