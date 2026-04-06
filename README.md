# Kalshi NYC Weather Trading Bot

Python tooling to read **NYC high-temperature** forecast inputs and evaluate or trade the Kalshi market **“Highest temperature in NYC today?”** (series ticker **`KXHIGHNY`**).

The bot is designed around the fact that **this market does not settle on a generic NYC forecast**. It settles on the **National Weather Service (NWS) Daily Climate Report** for the **Central Park** observation station — the official recorded high used for that report is what matters for resolution, not a broad “NYC” model grid or a third-party app.

## Kalshi structure: `KXHIGHNY`

Kalshi organizes prediction markets in three layers:

1. **Series** — The reusable product line, identified by ticker **`KXHIGHNY`** (daily NYC high-temperature markets).
2. **Event** — A single day’s question (e.g. “Highest temperature in NYC on &lt;date&gt;?”), which groups the contracts for that date.
3. **Market** — Each tradeable binary (or multi-outcome) contract within the event (e.g. separate ranges or thresholds for the high temperature).

When building pipelines, resolve **series → event (by date) → market (by strike / range)** so quotes and positions match the exact contract you intend to trade.

## Project layout

| Path | Role |
|------|------|
| `bot/weather.py` | NWS / Central Park–relevant forecast and climate inputs |
| `bot/kalshi.py` | Kalshi API helpers (quotes, orders, series metadata) |
| `bot/edge.py` | Edge / mispricing logic between forecast and market |
| `bot/risk.py` | Sizing, limits, and guardrails |
| `dashboard/app.py` | Streamlit UI for monitoring |
| `scripts/backtest.py` | Historical or replay-style analysis |
| `data/historical/` | Local caches (gitignored) |

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set `KALSHI_API_KEY` **only if** you need authenticated actions (e.g. placing orders). Public, read-only market data does not require an API key.

## Disclaimer

This repository is for educational and research purposes. Trading involves risk; nothing here is financial advice.
