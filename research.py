"""Run a fixed-parameter comparison or a rolling out-of-sample evaluation."""

from dataclasses import asdict, replace
from itertools import product
from math import isfinite

import pandas as pd

from analytics import metrics
from backtest import compare, simulate
from strategies import signals


def fixed_run(bars, params, account, warmup=None):
    baseline = max(params.lookback, warmup or 0)
    if len(bars) < baseline + 2:
        raise ValueError("Select a longer date range or a shorter lookback.")
    indicators = signals(bars["Close"], params)
    orders = indicators["target"].shift(1, fill_value=False).iloc[baseline:].copy()
    orders.iloc[0] = False
    return compare(bars.iloc[baseline:], orders, account).join(indicators)


def parameter_grid(params):
    """Use lookbacks around the chosen value and vary strategy-specific settings."""
    windows = sorted({max(2, params.lookback // 2), params.lookback, params.lookback * 2})
    if params.strategy == "Mean reversion":
        return [
            replace(params, lookback=window, entry=params.entry * scale, exit=params.exit * scale)
            for window, scale in product(windows, (0.5, 1.0))
        ]
    if params.strategy == "Trend following":
        return [
            replace(params, lookback=window, fast=min(window - 1, fast))
            for window, fast in product(windows, sorted({max(1, params.fast // 2), params.fast}))
        ]
    return [replace(params, lookback=window) for window in windows]


def walk_forward(bars, params, account, train=504, test=126):
    """Choose by net training Sharpe and carry holdings across test folds."""
    if test < 1 or train < 2 or len(bars) < train + test:
        raise ValueError("The date range must cover a full training and test window.")
    candidates = list(dict.fromkeys(parameter_grid(params)))
    warmup = max(candidate.lookback for candidate in candidates)
    if train < warmup + 3:
        raise ValueError("Increase training sessions or reduce the lookback.")
    orders = pd.Series(False, index=bars.index[train - 1:])
    rows = []

    for start in range(train, len(bars), test):
        stop = min(start + test, len(bars))
        train_start = start - train
        training = bars.iloc[train_start:start]
        training_bars = training.iloc[warmup:]
        best_params = candidates[0]
        best_score = float("-inf")

        for candidate in candidates:
            training_targets = signals(training["Close"], candidate)["target"]
            training_orders = training_targets.shift(1, fill_value=False).iloc[warmup:].copy()
            training_orders.iloc[0] = False
            equity = simulate(training_bars, training_orders, account)["equity"]
            score = metrics(equity)["Sharpe (zero risk-free rate)"]
            if isfinite(score) and score > best_score:
                best_params, best_score = candidate, score

        # Each test order uses only closes through the preceding session.
        history = bars["Close"].iloc[train_start:stop - 1]
        targets = signals(history, best_params)["target"].iloc[train - 1:]
        orders.iloc[start - train + 1:stop - train + 1] = targets.to_numpy()
        rows.append({
            "train_start": training.index[0],
            "train_end": training.index[-1],
            "test_start": bars.index[start],
            "test_end": bars.index[stop - 1],
            "test_sessions": stop - start,
            "training_sharpe": best_score if isfinite(best_score) else None,
            **asdict(best_params),
        })

    run = compare(bars.iloc[train - 1:], orders, account)
    folds = pd.DataFrame(rows)
    first_equity = run["strategy_equity"].shift(1).reindex(folds["test_start"]).to_numpy()
    last_equity = run["strategy_equity"].reindex(folds["test_end"]).to_numpy()
    folds["test_return_pct"] = 100 * (last_equity / first_equity - 1)
    return run, folds
