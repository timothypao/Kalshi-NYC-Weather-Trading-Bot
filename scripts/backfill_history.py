"""Fetch settled KXHIGHNY outcomes from Kalshi and write training labels to CSV.

Each row is one calendar day where exactly one market resolved YES. For ``-B…``
band contracts, ``actual_high_band`` is the band midpoint parsed from the ticker.
Legacy ``-T…`` threshold contracts have no band in the ticker; we then use
``expiration_value`` (the settlement / observed high) as ``actual_high_band``.

Pair with historical NWS forecast pulls for the same dates to build full training rows.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.kalshi import parse_band_midpoint_f_from_ticker

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
SERIES_TICKER = "KXHIGHNY"
STATUS = "settled"
LIMIT = 200
OUT_PATH = ROOT / "data" / "historical" / "outcomes.csv"

DATE_IN_TICKER = re.compile(r"KXHIGHNY-(\d{2}[A-Z]{3}\d{2})-")


def _date_from_ticker(ticker: str) -> str:
    m = DATE_IN_TICKER.search(ticker)
    if not m:
        raise ValueError(f"No date token in ticker: {ticker}")
    token = m.group(1)
    d = datetime.strptime(token, "%y%b%d").date()
    return d.isoformat()


def _actual_high_band_yes(market: dict[str, Any]) -> float:
    ticker = str(market.get("ticker") or "")
    mid = parse_band_midpoint_f_from_ticker(ticker)
    if mid is not None:
        return mid
    exp = market.get("expiration_value")
    if exp in (None, ""):
        raise ValueError(f"No -B segment and no expiration_value for {ticker}")
    return float(exp)


def fetch_all_settled_yes_rows() -> list[dict[str, Any]]:
    cursor: str | None = None
    by_date: dict[str, float] = {}
    conflicts: list[tuple[str, float, float]] = []

    while True:
        params: dict[str, Any] = {
            "series_ticker": SERIES_TICKER,
            "status": STATUS,
            "limit": LIMIT,
        }
        if cursor:
            params["cursor"] = cursor
        r = requests.get(BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        payload = r.json()
        for m in payload.get("markets") or []:
            if m.get("result") != "yes":
                continue
            tick = m.get("ticker")
            if not tick:
                continue
            try:
                day = _date_from_ticker(str(tick))
                val = _actual_high_band_yes(m)
            except (ValueError, TypeError):
                continue
            if day in by_date and by_date[day] != val:
                conflicts.append((day, by_date[day], val))
            by_date[day] = val

        cursor = payload.get("cursor")
        if not cursor:
            break

    for day, old, new in conflicts:
        print(
            f"warning: duplicate YES date {day}: had {old}, overwriting with {new}",
            file=sys.stderr,
        )

    rows = [{"date": d, "actual_high_band": v} for d, v in sorted(by_date.items())]
    return rows


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = fetch_all_settled_yes_rows()
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "actual_high_band"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
