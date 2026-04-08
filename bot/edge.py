"""Compare forecast beliefs to market prices and estimate edge."""

from __future__ import annotations

import math
import json
import re
from typing import Any

from .weather import get_nyc_forecast
from .kalshi import get_today_market, parse_band_midpoint_f_from_ticker

EDGE_THRESHOLD = 0.12
BIAS_CORRECTION = 0.0
# z = SIGMOID_K * (forecast_high - threshold_F). ~0.15 softens vs. dividing distance by ~5.
SIGMOID_K = 0.15
# Compress deviation from 0.5 so +5°F/+10°F/~+15°F land near 0.62/0.73/0.80 (with cap below).
SIGMOID_SPREAD = 0.74
OUR_PROB_CAP = 0.80
BOUNDARY_RISK_EPSILON_F = 1.0


def _target_band_midpoint_f(market: dict[str, Any]) -> float:
    """Band midpoint or legacy -T level used as the contract reference temperature."""
    ticker = market.get("ticker")
    if not ticker:
        raise ValueError("Market dict must include 'ticker' for band midpoint extraction.")

    midpoint_f = market.get("band_midpoint")
    if midpoint_f is None:
        midpoint_f = parse_band_midpoint_f_from_ticker(str(ticker))
    if midpoint_f is None:
        m = re.search(r"-T(\d+)$", str(ticker))
        if not m:
            m = re.search(r"-T(\d+)", str(ticker))
        if not m:
            raise ValueError(f"Could not extract band midpoint or -T fallback from ticker: {ticker}")
        midpoint_f = float(m.group(1))
    return float(midpoint_f)


def compute_signal(forecast: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    """Compare our NWS-based view vs. the Kalshi KXHIGHNY market."""
    forecast_high = forecast.get("forecast_high")
    if forecast_high is None:
        raise ValueError("Forecast dict must include 'forecast_high'.")

    yes_price = market.get("yes_price")
    if yes_price is None:
        raise ValueError("Market dict must include 'yes_price'.")

    # Kalshi prices are expressed as a $ price for a $1 payout contract.
    market_probability = float(yes_price)

    our_probability = forecast_to_probability(float(forecast_high), market)
    our_probability = max(0.0, min(1.0, our_probability + BIAS_CORRECTION))

    edge = float(our_probability) - float(market_probability)
    direction = "yes" if edge > 0 else "no"
    trade_flag = abs(edge) > EDGE_THRESHOLD

    target_band_midpoint = _target_band_midpoint_f(market)
    boundary_risk = abs(float(forecast_high) - target_band_midpoint) < BOUNDARY_RISK_EPSILON_F

    return {
        "trade": trade_flag,
        "direction": direction,
        "edge": edge,
        "our_probability": our_probability,
        "market_probability": market_probability,
        "boundary_risk": boundary_risk,
    }


def forecast_to_probability(forecast_high: float, market: dict[str, Any]) -> float:
    """Convert an NWS forecast high into probability for the active contract.

    Uses the contract band midpoint (``-B54.5`` in the ticker), or ``band_midpoint``
    on the market dict. Legacy ``-T54`` tickers are still supported as a fallback.
    """
    threshold_f = _target_band_midpoint_f(market)
    distance_f = float(forecast_high) - threshold_f
    z = SIGMOID_K * distance_f
    raw = 1.0 / (1.0 + math.exp(-z))
    prob = 0.5 + (raw - 0.5) * SIGMOID_SPREAD
    return max(0.0, min(OUR_PROB_CAP, prob))


def should_trade(signal: dict[str, Any]) -> bool:
    edge_value = float(signal.get("edge", 0.0))
    return bool(signal.get("trade")) and abs(edge_value) > EDGE_THRESHOLD


def _midpoint_f_for_selection(market: dict[str, Any]) -> float | None:
    if market.get("band_midpoint") is not None:
        return float(market["band_midpoint"])
    t = market.get("ticker") or ""
    b = parse_band_midpoint_f_from_ticker(t)
    if b is not None:
        return b
    m = re.search(r"-T(\d+)", t)
    return float(m.group(1)) if m else None


if __name__ == "__main__":
    forecast = get_nyc_forecast()
    markets = get_today_market()
    fh = float(forecast["forecast_high"])
    resolved = [(m, _midpoint_f_for_selection(m)) for m in markets]
    resolved = [(m, mid) for m, mid in resolved if mid is not None]
    if not resolved:
        raise RuntimeError("No open market today with a parsable band or -T fallback.")
    market = min(resolved, key=lambda item: abs(item[1] - fh))[0]
    signal = compute_signal(forecast, market)
    print(json.dumps(signal, indent=2))
