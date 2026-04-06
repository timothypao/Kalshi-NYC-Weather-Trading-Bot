"""NWS-oriented forecast inputs aligned with Central Park settlement logic."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import requests

NWS_BASE_URL = "https://api.weather.gov"
STATION_ID = "KNYC"
DEFAULT_HEADERS = {
    # NWS requests a descriptive User-Agent for API consumers.
    "User-Agent": "kalshi-nyc-weather-trading-bot (educational project)",
    "Accept": "application/geo+json",
}


def _get_json(url: str) -> dict[str, Any]:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def get_nyc_forecast() -> dict[str, Any]:
    """Return today's Central Park forecast high and precipitation probability.

    Uses station `KNYC` as the source of truth, then derives the official NWS
    forecast grid from that station's coordinates.
    """
    station_url = f"{NWS_BASE_URL}/stations/{STATION_ID}"
    station_data = _get_json(station_url)

    coordinates = station_data["geometry"]["coordinates"]
    lon, lat = coordinates[0], coordinates[1]

    points_url = f"{NWS_BASE_URL}/points/{lat},{lon}"
    points_data = _get_json(points_url)
    forecast_url = points_data["properties"]["forecast"]

    forecast_data = _get_json(forecast_url)
    periods = forecast_data["properties"]["periods"]
    if not periods:
        raise RuntimeError("No forecast periods returned by api.weather.gov")

    today = datetime.now().date()
    chosen_period: dict[str, Any] | None = None

    # Prefer today's daytime period (daily high). Fall back to first daytime.
    for period in periods:
        start_date = datetime.fromisoformat(period["startTime"]).date()
        if period.get("isDaytime") and start_date == today:
            chosen_period = period
            break

    if chosen_period is None:
        for period in periods:
            if period.get("isDaytime"):
                chosen_period = period
                break

    if chosen_period is None:
        chosen_period = periods[0]

    precip_prob = chosen_period.get("probabilityOfPrecipitation", {}).get("value")
    forecast_date = datetime.fromisoformat(chosen_period["startTime"]).date().isoformat()

    return {
        "station": STATION_ID,
        "forecast_high": chosen_period.get("temperature"),
        "precip_probability": precip_prob,
        "forecast_date": forecast_date,
    }


if __name__ == "__main__":
    print(json.dumps(get_nyc_forecast(), indent=2))
