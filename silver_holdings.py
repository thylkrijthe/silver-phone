"""Value a fixed physical silver holding using the silver reference series."""

from dataclasses import dataclass
from datetime import date
from math import isfinite
import pandas as pd

from silver_data import START, TROY_OUNCES_PER_KG

@dataclass(frozen=True)
class Holding:
    quantity: float
    unit: str
    start_date: date

    def __post_init__(self):
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("Enter a positive silver quantity.")
        if self.unit not in ("kg", "troy oz"):
            raise ValueError("Choose kilograms or troy ounces.")
        if self.start_date < START:
            raise ValueError("The price history starts in 2018.")

    @property
    def kg(self):
        return float(self.quantity) if self.unit == "kg" else self.quantity / TROY_OUNCES_PER_KG


def value_history(bars, holding):
    """Value the same quantity on every available close from the selected date."""
    prices = bars.loc[bars.index >= pd.Timestamp(holding.start_date), "Close"]
    if prices.empty:
        raise ValueError("Choose a starting date on or before the latest completed quote.")
    return pd.DataFrame({
        "silver_eur_per_kg": prices,
        "silver_kg": holding.kg,
        "silver_troy_oz": holding.kg * TROY_OUNCES_PER_KG,
        "holding_value_eur": prices * holding.kg,
    })

