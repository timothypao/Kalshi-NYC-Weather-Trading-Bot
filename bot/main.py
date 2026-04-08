"""Single entrypoint: forecast → markets → signal → risk, optional decision log."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .edge import compute_signal
from .kalshi import get_today_market
from .risk import RiskManager, _select_market_for_forecast
from .weather import get_nyc_forecast

ROOT = Path(__file__).resolve().parent.parent
DECISIONS_CSV = ROOT / "data" / "historical" / "decisions.csv"

DECISION_FIELDS = [
    "timestamp",
    "date",
    "forecast_high",
    "target_ticker",
    "edge",
    "boundary_risk",
    "approved",
    "position_size",
    "reason",
]


def run_pipeline(dry_run: bool) -> dict[str, Any]:
    forecast = get_nyc_forecast()
    markets = get_today_market()
    target_market = _select_market_for_forecast(forecast, markets)
    signal = compute_signal(forecast, target_market)
    risk = RiskManager().approve_trade(signal, requested_dollars=10.0, realized_pnl=0.0)

    out: dict[str, Any] = {
        "forecast": forecast,
        "markets": markets,
        "target_market": target_market,
        "signal": signal,
        "risk": risk,
    }

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": forecast.get("forecast_date", ""),
        "forecast_high": forecast.get("forecast_high"),
        "target_ticker": target_market.get("ticker", ""),
        "edge": signal.get("edge"),
        "boundary_risk": signal.get("boundary_risk"),
        "approved": risk.get("approved"),
        "position_size": risk.get("position_size"),
        "reason": risk.get("reason", ""),
    }

    if not dry_run:
        DECISIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
        write_header = not DECISIONS_CSV.exists() or DECISIONS_CSV.stat().st_size == 0
        with DECISIONS_CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
            if write_header:
                w.writeheader()
            w.writerow({k: row[k] for k in DECISION_FIELDS})

    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Run NYC weather → Kalshi edge → risk pipeline.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline but do not append to data/historical/decisions.csv",
    )
    args = p.parse_args()
    result = run_pipeline(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
