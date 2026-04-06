"""Compare forecast beliefs to market prices and estimate edge."""

from __future__ import annotations

import math
import json
import re
from typing import Any

from .weather import get_nyc_forecast
from .kalshi import get_today_market

EDGE_THRESHOLD = 0.12
BIAS_CORRECTION = 0.0
TEMPERATURE_SIGMOID_SCALE_F = 5.0  # Larger => smoother probability curve


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

    return {
        "trade": trade_flag,
        "direction": direction,
        "edge": edge,
        "our_probability": our_probability,
        "market_probability": market_probability,
    }


def forecast_to_probability(forecast_high: float, market: dict[str, Any]) -> float:
    """Convert an NWS forecast high into probability for the active contract.

    Extracts the temperature threshold from the market ticker:
    e.g. `KXHIGHNY-26APR06-T54` => threshold = 54.

    Uses a simple sigmoid based on how far forecast_high is from the threshold.
    """
    ticker = market.get("ticker")
    if not ticker:
        raise ValueError("Market dict must include 'ticker' for threshold extraction.")

    m = re.search(r"-T(\d+)$", str(ticker))
    if not m:
        # Some tickers may contain additional suffixes; fall back to first "-T###" match.
        m2 = re.search(r"-T(\d+)", str(ticker))
        if not m2:
            raise ValueError(f"Could not extract threshold from ticker: {ticker}")
        threshold_f = float(m2.group(1))
    else:
        threshold_f = float(m.group(1))

    distance_f = float(forecast_high) - threshold_f
    z = distance_f / TEMPERATURE_SIGMOID_SCALE_F
    return 1.0 / (1.0 + math.exp(-z))


def should_trade(signal: dict[str, Any]) -> bool:
    edge_value = float(signal.get("edge", 0.0))
    return bool(signal.get("trade")) and abs(edge_value) > EDGE_THRESHOLD


if __name__ == "__main__":
    forecast = get_nyc_forecast()
    market = get_today_market()
    signal = compute_signal(forecast, market)
    print(json.dumps(signal, indent=2))
