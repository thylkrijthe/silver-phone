"""Convert continuous silver futures quotes into euros per kilogram."""

from datetime import date, datetime
import json
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

START = date(2018, 1, 1)
TROY_OUNCES_PER_KG = 1000 / 31.1034768
SILVER = "SI=F"
FX_URL = "https://api.frankfurter.dev/v1/2017-12-20..?base=EUR&symbols=USD"


def convert_to_eur_kg(prices, usd_per_eur):
    """Use the prior published daily FX rate at open and latest rate at close."""
    fx = usd_per_eur.sort_index()
    if fx.empty or not fx.index.is_unique or not np.isfinite(fx).all() or (fx <= 0).any():
        raise ValueError("The EUR/USD feed returned invalid reference rates.")
    open_fx = fx.reindex(prices.index - pd.Timedelta(days=1), method="ffill").to_numpy()
    close_fx = fx.reindex(prices.index, method="ffill").to_numpy()
    bars = prices[["Open", "Close"]].div(
        pd.DataFrame({"Open": open_fx, "Close": close_fx}, index=prices.index)
    ) * TROY_OUNCES_PER_KG
    if bars.empty or not np.isfinite(bars).all().all() or (bars <= 0).any().any():
        raise ValueError("Silver or EUR/USD data was missing or invalid.")
    return bars


def download_silver():
    """Return completed daily silver-futures bars from 2018 through the latest session."""
    today = datetime.now(ZoneInfo("America/New_York")).date()
    try:
        prices = yf.download(
            SILVER, start=START.isoformat(), end=today.isoformat(), interval="1d",
            auto_adjust=False, multi_level_index=False, progress=False, threads=False, timeout=15,
        )
        with urlopen(FX_URL, timeout=15) as response:
            rates = json.load(response)["rates"]
        usd_per_eur = pd.Series({day: row["USD"] for day, row in rates.items()}, dtype=float)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Could not download silver or EUR/USD history: {error}") from error
    if prices is None or prices.empty or not {"Open", "Close"}.issubset(prices.columns):
        raise ValueError("Yahoo Finance returned no daily silver futures bars. Try again later.")
    prices.index = pd.DatetimeIndex(prices.index).tz_localize(None)
    prices = prices.sort_index()
    prices.index.name = "date"
    usd_per_eur.index = pd.DatetimeIndex(usd_per_eur.index)
    if (
        not prices.index.is_unique
        or (prices.index[0] - pd.Timestamp(START)).days > 7
        or (pd.Timestamp(today) - prices.index[-1]).days > 7
        or usd_per_eur.empty
        or (prices.index[-1] - usd_per_eur.index.max()).days > 7
    ):
        raise ValueError("The download was stale or did not cover the requested history from 2018.")
    return convert_to_eur_kg(prices, usd_per_eur)
