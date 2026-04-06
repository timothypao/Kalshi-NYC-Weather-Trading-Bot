"""Kalshi API helpers for series KXHIGHNY and related markets."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
SERIES_TICKER = "KXHIGHNY"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def get_today_market() -> dict[str, Any]:
    """Return today's active KXHIGHNY market details.

    Returns a dict with keys: ticker, title, yes_price, no_price, volume.
    """
    url = f"{BASE_URL}/markets?series_ticker={SERIES_TICKER}&status=open"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    markets = response.json().get("markets", [])
    if not markets:
        raise RuntimeError("No open markets returned for series KXHIGHNY.")

    today_token = datetime.now().strftime("%y%b%d").upper()  # e.g. 26APR06
    todays_markets = [m for m in markets if today_token in m.get("ticker", "")]
    if not todays_markets:
        raise RuntimeError(
            f"No open KXHIGHNY market found for today token '{today_token}'."
        )

    # If multiple strikes are open today, pick the most active by volume.
    market = max(todays_markets, key=lambda m: float(m.get("volume_fp", 0) or 0))

    return {
        "ticker": market.get("ticker"),
        "title": market.get("title"),
        "yes_price": _to_float(market.get("yes_ask_dollars")),
        "no_price": _to_float(market.get("no_ask_dollars")),
        "volume": _to_float(market.get("volume_fp")),
    }


def get_market_orderbook(ticker: str) -> dict[str, Any]:
    """Return the current order book for the given market ticker."""
    url = f"{BASE_URL}/markets/{ticker}/orderbook"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json().get("orderbook_fp", {})


if __name__ == "__main__":
    today_market = get_today_market()
    print("Today's active KXHIGHNY market:")
    print(json.dumps(today_market, indent=2))
    print()

    print(f"Order book for {today_market['ticker']}:")
    print(json.dumps(get_market_orderbook(today_market["ticker"]), indent=2))
