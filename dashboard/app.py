"""Streamlit dashboard: decisions log, outcomes, and edge calibration."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.kalshi import parse_band_midpoint_f_from_ticker

DECISIONS_CSV = ROOT / "data" / "historical" / "decisions.csv"
OUTCOMES_CSV = ROOT / "data" / "historical" / "outcomes.csv"
NYC = ZoneInfo("America/New_York")

EMPTY_HINT = (
    "No data yet — run `python -m bot.main` to generate your first signal "
    "(use `--dry-run` to test without writing the log)."
)


def _load_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if df.empty:
        return None
    return df


def _direction_from_edge(edge: float) -> str:
    return "yes" if float(edge) > 0 else "no"


def _ticker_matches_actual_band(ticker: str, actual_high_band: float) -> bool:
    """True if the decision's target contract is the band that settled (midpoint match)."""
    if pd.isna(actual_high_band):
        return False
    actual = float(actual_high_band)
    parsed = parse_band_midpoint_f_from_ticker(str(ticker))
    if parsed is not None and abs(parsed - actual) < 0.01:
        return True
    t = str(ticker)
    for token in (f"B{actual}", f"B{actual:g}"):
        if token in t:
            return True
    if actual == int(actual):
        if f"B{int(actual)}" in t:
            return True
    return False


def main() -> None:
    st.set_page_config(page_title="Kalshi NYC Weather", layout="wide")
    st.title("Kalshi NYC high temperature — dashboard")

    decisions_df = _load_csv(DECISIONS_CSV)
    outcomes_df = _load_csv(OUTCOMES_CSV)

    # --- 1. Today's signal ---
    st.subheader("Today's signal")
    if decisions_df is None:
        st.info(EMPTY_HINT)
    else:
        decisions_df = decisions_df.copy()
        if "timestamp" in decisions_df.columns:
            decisions_df["_ts"] = pd.to_datetime(
                decisions_df["timestamp"], utc=True, errors="coerce"
            )
        else:
            decisions_df["_ts"] = pd.NaT

        day_str = datetime.now(NYC).date().isoformat()
        today_rows = decisions_df[decisions_df["date"].astype(str) == day_str]
        if not today_rows.empty:
            sub = today_rows.sort_values("_ts", ascending=False, na_position="last")
            row = sub.iloc[0]
        elif decisions_df["_ts"].notna().any():
            row = decisions_df.loc[decisions_df["_ts"].idxmax()]
            st.caption("No decision logged for today's date (NYC); showing most recent run.")
        else:
            row = decisions_df.iloc[-1]
            st.caption("No usable timestamps; showing last row in the log.")

        fh = row.get("forecast_high", "")
        ticker = row.get("target_ticker", "")
        edge = float(row.get("edge", 0) or 0)
        direction = _direction_from_edge(edge)
        braw = row.get("boundary_risk", False)
        if isinstance(braw, str):
            b_risk = braw.strip().lower() in ("true", "1", "yes")
        else:
            b_risk = bool(braw)

        appr = row.get("approved", False)
        if isinstance(appr, str):
            approved = appr.strip().lower() in ("true", "1", "yes")
        else:
            approved = bool(appr)
        reason = str(row.get("reason", "") or "")

        risk_badge = (
            '<span style="background:#1b5e20;color:white;padding:4px 10px;'
            'border-radius:6px;font-weight:600;">Approved</span>'
            if approved
            else '<span style="background:#b71c1c;color:white;padding:4px 10px;'
            'border-radius:6px;font-weight:600;">Rejected</span>'
        )
        boundary_html = (
            '<span style="background:#b71c1c;color:white;padding:4px 10px;'
            'border-radius:6px;font-weight:600;">Boundary risk</span>'
            if b_risk
            else '<span style="color:#666;">No boundary risk</span>'
        )

        st.markdown(
            f"""
<div style="border:1px solid #ddd;border-radius:12px;padding:1.25rem 1.5rem;
background:linear-gradient(180deg,#fafafa 0%,#fff 100%);margin-bottom:1rem;">
  <div style="font-size:1.75rem;font-weight:700;margin-bottom:0.5rem;">{fh}°F forecast high</div>
  <div style="font-size:1.1rem;margin-bottom:0.35rem;"><b>Target:</b> <code>{ticker}</code></div>
  <div style="font-size:1.1rem;margin-bottom:0.35rem;"><b>Edge:</b> {edge:.4f} &nbsp;|&nbsp; <b>Direction:</b> {direction.upper()}</div>
  <div style="margin:0.75rem 0;">{boundary_html}</div>
  <div style="margin-top:0.5rem;">{risk_badge}
  {f'<span style="margin-left:12px;color:#555;">{reason}</span>' if reason else ""}
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # --- 2. Decision log ---
    st.subheader("Decision log")
    if decisions_df is None:
        st.info(EMPTY_HINT)
    else:
        log = decisions_df.drop(columns=["_ts"], errors="ignore").copy()
        if "timestamp" in log.columns:
            log["_ts"] = pd.to_datetime(log["timestamp"], utc=True, errors="coerce")
            log = log.sort_values("_ts", ascending=False, na_position="last")
        log = log.drop(columns=["_ts"], errors="ignore")
        cols = [
            "date",
            "forecast_high",
            "target_ticker",
            "edge",
            "boundary_risk",
            "approved",
            "position_size",
            "reason",
        ]
        show = log[[c for c in cols if c in log.columns]]
        st.dataframe(show, use_container_width=True, height=400)

    st.divider()

    # --- 3. Outcome tracker ---
    st.subheader("Outcome tracker")
    if decisions_df is None:
        st.info(EMPTY_HINT)
    elif outcomes_df is None:
        st.warning(
            "No outcomes file yet — run `python scripts/backfill_history.py` to build "
            "`data/historical/outcomes.csv`."
        )
    else:
        dec = decisions_df.drop(columns=["_ts"], errors="ignore").copy()
        out = outcomes_df.copy()
        merged = dec.merge(out, on="date", how="inner", suffixes=("", "_out"))
        merged["correct"] = merged.apply(
            lambda r: _ticker_matches_actual_band(
                str(r.get("target_ticker", "")), r.get("actual_high_band")
            ),
            axis=1,
        )
        disp = merged[
            ["forecast_high", "target_ticker", "actual_high_band", "correct"]
        ].copy()
        if disp.empty:
            st.info("No overlapping dates between decisions and outcomes yet.")
        else:
            acc = float(disp["correct"].mean()) * 100
            st.markdown(
                f"**Overall accuracy:** {acc:.1f}% — share of rows where the target ticker "
                "matches the settled band midpoint."
            )
            st.dataframe(disp, use_container_width=True, height=320)

    st.divider()

    # --- 4. Edge calibration ---
    st.subheader("Edge calibration")
    if decisions_df is None:
        st.info(EMPTY_HINT)
    else:
        chart_df = decisions_df.drop(columns=["_ts"], errors="ignore").copy()
        if "timestamp" not in chart_df.columns or "edge" not in chart_df.columns:
            st.warning("Decisions log is missing timestamp or edge column.")
        else:
            chart_df["_ts"] = pd.to_datetime(chart_df["timestamp"], utc=True, errors="coerce")
            chart_df = chart_df.sort_values("_ts").dropna(subset=["_ts", "edge"])
            chart_df["edge"] = pd.to_numeric(chart_df["edge"], errors="coerce")
            chart_df = chart_df.dropna(subset=["edge"])
            if chart_df.empty:
                st.info("No plottable edge values after parsing timestamps.")
            else:
                line = chart_df.set_index("_ts")[["edge"]]
                st.line_chart(line)
                st.caption(
                    "Positive edge = model more bullish YES than the market ask; "
                    "persistent bias suggests miscalibration."
                )


main()
