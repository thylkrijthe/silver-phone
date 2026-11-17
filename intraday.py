"""Download and align timestamped silver and EUR/USD bars."""

import numpy as np
import pandas as pd
import yfinance as yf

from silver_data import SILVER, TROY_OUNCES_PER_KG

FX_SYMBOL = "EURUSD=X"


def convert_intraday(silver, fx):
    """Match each silver bar with the latest FX bar at or before its timestamp."""
    series = []
    for quotes, name in ((silver, "usd_per_ounce"), (fx, "usd_per_eur")):
        if not isinstance(quotes.index, pd.DatetimeIndex) or quotes.index.tz is None:
            raise ValueError("The price feed did not provide timezone-aware intraday data.")
        quotes = quotes.loc[np.isfinite(quotes) & quotes.gt(0)].copy()
        quotes.index = quotes.index.tz_convert("UTC")
        quotes = quotes.sort_index()
        series.append(quotes.loc[~quotes.index.duplicated(keep="last")].rename(name))
    silver, fx = series
    if silver.empty or fx.empty:
        raise ValueError("The feed returned no recent silver or exchange-rate bars.")
    matches = pd.merge_asof(
        silver.to_frame(), fx.to_frame().assign(fx_time=fx.index),
        left_index=True, right_index=True, direction="backward", tolerance=pd.Timedelta(hours=1),
    ).dropna()
    if matches.empty:
        raise ValueError("No recent silver and exchange-rate bars could be matched.")
    if matches.index[-1] != silver.index[-1]:
        raise ValueError(f"No matching EUR/USD rate for the latest silver bar ({silver.index[-1]:%d %b %H:%M UTC}).")
    return matches.assign(silver_eur_per_kg=matches.usd_per_ounce / matches.usd_per_eur * TROY_OUNCES_PER_KG)


def download_intraday():
    quotes = yf.download(
        [SILVER, FX_SYMBOL], period="5d", interval="5m", ignore_tz=False,
        auto_adjust=False, progress=False, threads=False, timeout=10,
    )
    if quotes is None or quotes.empty or "Close" not in quotes:
        raise ValueError("The feed returned no intraday prices.")
    closes = quotes["Close"]
    if not {SILVER, FX_SYMBOL}.issubset(closes.columns):
        raise ValueError("The feed did not return both silver and EUR/USD.")
    return convert_intraday(closes[SILVER], closes[FX_SYMBOL])
