"""Next-open execution and daily mark-to-market accounting."""

from dataclasses import dataclass
from math import isfinite

import pandas as pd


@dataclass(frozen=True)
class Account:
    capital: float = 100_000
    allocation: float = 0.25
    cost_bps: float = 10

    def __post_init__(self):
        if not (isfinite(self.capital) and self.capital > 0 and 0 < self.allocation <= 1):
            raise ValueError("Capital must be positive and allocation must be in (0, 1].")
        if not 0 <= self.cost_bps < 10_000:
            raise ValueError("Cost must be at least 0 and less than 10,000 bps.")


def simulate(bars, orders, account):
    """Execute Boolean holding instructions on their indexed open.

    The first row is a cash baseline and must have no buy instruction.
    Holdings are fractional adjusted-price units. Size at entry and let weight drift.
    """
    if len(bars) < 2 or not bars.index.equals(orders.index) or orders.isna().any() or orders.iloc[0]:
        raise ValueError("Provide aligned orders with a cash baseline and at least one trading session.")
    cash = account.capital
    units = 0.0
    rate = account.cost_bps / 10_000
    records = []
    for (open_price, close), hold in zip(bars[["Open", "Close"]].itertuples(index=False, name=None), orders):
        trade = 0.0
        if hold and units == 0:
            # Allocate a share of current cash to the purchase, including its fee.
            trade = cash * account.allocation / (1 + rate)
            units = trade / open_price
        elif not hold and units:
            trade = -units * open_price
            units = 0.0
        fee = abs(trade) * rate
        cash -= trade + fee
        position = units * close
        records.append((cash, units, trade, fee, position, cash + position))

    ledger = pd.DataFrame(
        records, index=bars.index,
        columns=["cash", "units", "trade_notional", "fee", "position_value", "equity"],
    )
    ledger["weight"] = ledger["position_value"] / ledger["equity"]
    ledger["return"] = ledger["equity"].pct_change()
    ledger["drawdown"] = ledger["equity"] / ledger["equity"].cummax() - 1
    return ledger


def compare(bars, orders, account):
    """Add a buy-once benchmark with the same initial cash, entry allocation and fee."""
    benchmark_orders = pd.Series(True, index=bars.index)
    benchmark_orders.iloc[0] = False
    strategy = simulate(bars, orders, account).add_prefix("strategy_")
    benchmark = simulate(bars, benchmark_orders, account).add_prefix("benchmark_")
    return pd.concat([bars, orders.rename("hold_at_open"), strategy, benchmark], axis=1)
