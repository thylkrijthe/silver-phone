"""Performance tables, charts and export."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def metrics(equity, currency="$"):
    daily = equity.pct_change().dropna()
    total = equity.iloc[-1] / equity.iloc[0] - 1
    deviation = daily.std(ddof=1)
    return {
        f"Ending value ({currency})": equity.iloc[-1],
        "Total return (%)": 100 * total,
        "Annualized return (%)": 100 * np.expm1(np.log1p(total) * 252 / len(daily)),
        "Annualized volatility (%)": 100 * deviation * np.sqrt(252),
        "Sharpe (zero risk-free rate)": daily.mean() / deviation * np.sqrt(252) if deviation > 0 else np.nan,
        "Max drawdown (%)": 100 * (equity / equity.cummax() - 1).min(),
    }


def summary(run, currency="$"):
    return pd.DataFrame({
        "Strategy": metrics(run["strategy_equity"], currency),
        "Buy and hold": metrics(run["benchmark_equity"], currency),
    }).T


def chart(run, label, currency="$", price_label="Adjusted price ($)", close_label="Adjusted close"):
    fig, (price, equity, risk) = plt.subplots(3, 1, sharex=True, figsize=(11, 8), layout="constrained")
    price.plot(run.index, run["Close"], label=close_label)
    for indicator in ("slow_sma", "fast_sma"):
        if indicator in run:
            price.plot(run.index, run[indicator], label=indicator.replace("_", " "), alpha=.75)
    for direction, name, marker in [(1, "Buy at open", "^"), (-1, "Sell at open", "v")]:
        mask = np.sign(run["strategy_trade_notional"]) == direction
        if mask.any():
            price.scatter(run.index[mask], run.loc[mask, "Open"], marker=marker, label=name, s=22)
    price.set(title=label, ylabel=price_label)
    price.legend(loc="best")
    for prefix, name in [("strategy", "Strategy"), ("benchmark", "Buy and hold")]:
        equity.plot(run.index, run[f"{prefix}_equity"], label=name)
        risk.plot(run.index, run[f"{prefix}_drawdown"] * 100, label=name)
    equity.set(ylabel=f"Equity ({currency})")
    equity.legend(loc="best")
    risk.set(ylabel="Drawdown (%)", xlabel="Date")
    for axis in (price, equity, risk):
        axis.grid(alpha=.2)
    return fig


def export(directory, run, figure, settings, folds=None, currency="$"):
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    run.to_csv(destination / "daily.csv", index_label="date")
    summary(run, currency).to_csv(destination / "metrics.csv", index_label="portfolio")
    pd.Series(settings, name="value").to_csv(destination / "settings.csv", index_label="setting")
    if folds is not None:
        folds.to_csv(destination / "folds.csv", index=False)
    figure.savefig(destination / "chart.png", dpi=160)
