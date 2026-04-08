"""Position sizing, exposure limits, and trading guardrails."""

from __future__ import annotations

import json
import re
from typing import Any

from .edge import compute_signal
from .kalshi import get_today_market, parse_band_midpoint_f_from_ticker
from .weather import get_nyc_forecast


class RiskManager:
    def __init__(
        self,
        max_daily_loss_dollars: float = 20.0,
        max_position_dollars: float = 10.0,
    ) -> None:
        self.max_daily_loss_dollars = float(max_daily_loss_dollars)
        self.max_position_dollars = float(max_position_dollars)

    def check_position_size(self, signal: dict[str, Any], requested_dollars: float) -> float:
        if signal.get("boundary_risk"):
            return 0.0
        req = max(0.0, float(requested_dollars))
        return min(req, self.max_position_dollars)

    def check_daily_loss(self, realized_pnl: float) -> bool:
        """Return False if PnL is worse than the daily loss cap (more negative than -limit)."""
        return float(realized_pnl) >= -self.max_daily_loss_dollars

    def approve_trade(
        self,
        signal: dict[str, Any],
        requested_dollars: float,
        realized_pnl: float,
    ) -> dict[str, Any]:
        if not self.check_daily_loss(realized_pnl):
            return {
                "approved": False,
                "position_size": 0.0,
                "reason": (
                    f"Daily loss limit: realized_pnl={realized_pnl} "
                    f"is below {-self.max_daily_loss_dollars} (max loss "
                    f"{self.max_daily_loss_dollars} dollars)."
                ),
            }
        size = self.check_position_size(signal, requested_dollars)
        if size <= 0.0:
            if signal.get("boundary_risk"):
                r = "Rejected: signal has boundary_risk=True (no position)."
            else:
                r = "Rejected: approved position size is zero (requested size or cap)."
            return {"approved": False, "position_size": 0.0, "reason": r}
        return {"approved": True, "position_size": size, "reason": ""}


def _select_market_for_forecast(forecast: dict[str, Any], markets: list[dict[str, Any]]) -> dict[str, Any]:
    fh = float(forecast["forecast_high"])
    resolved: list[tuple[dict[str, Any], float]] = []
    for m in markets:
        if m.get("band_midpoint") is not None:
            resolved.append((m, float(m["band_midpoint"])))
            continue
        t = m.get("ticker") or ""
        b = parse_band_midpoint_f_from_ticker(t)
        if b is not None:
            resolved.append((m, b))
            continue
        mm = re.search(r"-T(\d+)", t)
        if mm:
            resolved.append((m, float(mm.group(1))))
    if not resolved:
        raise RuntimeError("No open market today with a parsable band or -T fallback.")
    return min(resolved, key=lambda item: abs(item[1] - fh))[0]


if __name__ == "__main__":
    forecast = get_nyc_forecast()
    markets = get_today_market()
    market = _select_market_for_forecast(forecast, markets)
    signal = compute_signal(forecast, market)

    rm = RiskManager()
    requested = 10.0
    realized = 0.0
    decision = rm.approve_trade(signal, requested, realized)

    print(json.dumps({"signal": signal, "risk": decision}, indent=2))
