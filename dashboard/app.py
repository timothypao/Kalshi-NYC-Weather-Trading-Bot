"""Streamlit dashboard for monitoring forecasts and Kalshi KXHIGHNY markets."""

import streamlit as st

st.set_page_config(page_title="Kalshi NYC Weather", layout="wide")
st.title("Kalshi NYC high temperature — dashboard")
st.info("Connect `bot.weather`, `bot.kalshi`, and `bot.edge` here.")
