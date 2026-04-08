"""Kalshi API helpers for series KXHIGHNY and related markets."""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any

import requests

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
SERIES_TICKER = "KXHIGHNY"


def parse_band_midpoint_f_from_ticker(ticker: str) -> float | None:
    """Band midpoint °F from ticker, e.g. KXHIGHNY-26APR06-B54.5 -> 54.5."""
    m = re.search(r"-B(\d+\.?\d*)$", str(ticker))
    if not m:
        m = re.search(r"-B(\d+\.?\d*)", str(ticker))
    if not m:
        return None
    return float(m.group(1))


def _parse_threshold_f_from_ticker(ticker: str) -> float | None:
    """Kept for compatibility: KXHIGHNY uses ``-B`` band midpoints, not ``-T``."""
    return parse_band_midpoint_f_from_ticker(ticker)


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def get_today_market() -> list[dict[str, Any]]:
    """Return all open KXHIGHNY markets for today's date token.

    Each item has: ticker, title, yes_price, no_price, volume, band_midpoint
    (``band_midpoint`` is None when the ticker has no ``-B...`` segment).
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

    out: list[dict[str, Any]] = []
    for m in todays_markets:
        t = m.get("ticker") or ""
        out.append(
            {
                "ticker": m.get("ticker"),
                "title": m.get("title"),
                "yes_price": _to_float(m.get("yes_ask_dollars")),
                "no_price": _to_float(m.get("no_ask_dollars")),
                "volume": _to_float(m.get("volume_fp")),
                "band_midpoint": parse_band_midpoint_f_from_ticker(t),
            }
        )

    out.sort(key=lambda row: (row["band_midpoint"] is None, row["band_midpoint"] or 0.0))
    return out


def get_market_orderbook(ticker: str) -> dict[str, Any]:
    """Return the current order book for the given market ticker."""
    url = f"{BASE_URL}/markets/{ticker}/orderbook"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json().get("orderbook_fp", {})


if __name__ == "__main__":
    today_markets = get_today_market()
    print("Open KXHIGHNY markets for today (band midpoint & yes ask):")
    for row in today_markets:
        print(
            json.dumps(
                {
                    "ticker": row["ticker"],
                    "band_midpoint": row["band_midpoint"],
                    "yes_price": row["yes_price"],
                },
                indent=2,
            )
        )
