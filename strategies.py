"""Long-or-cash targets determined using data through the current close."""

from dataclasses import dataclass
from math import isfinite

import pandas as pd

STRATEGIES = ("Mean reversion", "Momentum", "Trend following")


@dataclass(frozen=True)
class Parameters:
    strategy: str = "Mean reversion"
    lookback: int = 20
    fast: int = 10
    entry: float = 0.02
    exit: float = 0.02

    def __post_init__(self):
        if self.strategy not in STRATEGIES or self.lookback < 2:
            raise ValueError("Choose a supported strategy and a lookback of at least 2.")
        if self.strategy == "Trend following" and not 1 <= self.fast < self.lookback:
            raise ValueError("The fast moving average must be shorter than the slow one.")
        if not (0 <= self.entry < 1 and isfinite(self.exit) and self.exit >= 0):
            raise ValueError("Invalid mean-reversion thresholds.")


def signals(close, params):
    """Return indicators and a binary target for each close."""
    window = params.lookback
    if params.strategy == "Momentum":
        momentum = close.pct_change(window)
        return pd.DataFrame({"momentum": momentum, "target": momentum.gt(0)})

    slow = close.rolling(window).mean()
    if params.strategy == "Trend following":
        fast = close.rolling(params.fast).mean()
        return pd.DataFrame({"slow_sma": slow, "fast_sma": fast, "target": fast.gt(slow)})

    gap = close / slow - 1
    in_market = False
    targets = []
    for deviation in gap:
        if deviation < -params.entry:
            in_market = True
        elif deviation > params.exit:
            in_market = False
        targets.append(in_market)
    return pd.DataFrame({"slow_sma": slow, "target": targets})
