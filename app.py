"""Mobile interface for the silver holdings and research tools."""

from dataclasses import replace
from datetime import date
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import chart, summary
import matplotlib.pyplot as plt
from backtest import Account
from intraday import download_intraday
from research import fixed_run, walk_forward
from silver_data import START, download_silver
from silver_holdings import Holding, value_history
from strategies import Parameters, STRATEGIES

TEAL = "#176c62"
COPPER = "#ae6d31"
CHART_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


@st.cache_data(ttl=900, show_spinner=False)
def daily_prices():
    return download_silver()


@st.cache_data(ttl=50, show_spinner=False)
def intraday_prices():
    return download_intraday()


def euro(value):
    return f"€{value:,.2f}"


def show_chart(series, unit, key, intraday=False):
    figure = go.Figure()
    for (name, values), color in zip(series.items(), (TEAL, COPPER, "#5967a3", "#826157")):
        time_label = "%{x|%d %b %H:%M} UTC" if intraday else "%{x|%d %b %Y}"
        figure.add_scatter(
            x=values.index, y=values, name=name, mode="lines", line={"color": color, "width": 2},
            hovertemplate=f"{time_label}<br>%{{y:,.2f}} {unit}<extra>%{{fullData.name}}</extra>",
        )
    buttons = (
        [dict(count=1, label="1 day", step="day", stepmode="backward")]
        if intraday else
        [dict(count=n, label=label, step="month", stepmode="backward")
         for n, label in [(1, "1M"), (6, "6M"), (12, "1Y")]]
    )
    figure.update_layout(
        height=385, margin={"l": 5, "r": 12, "t": 48, "b": 12},
        dragmode="zoom", uirevision=key, paper_bgcolor="#fbfaf7", plot_bgcolor="#fbfaf7",
        xaxis={"type": "date", "rangeselector": {"buttons": [*buttons, {"step": "all", "label": "All"}]}},
        yaxis={"title": unit, "tickformat": ",.0f", "fixedrange": False},
        legend={"orientation": "h", "x": 0, "y": -.18},
        showlegend=len(series) > 1,
    )
    st.plotly_chart(figure, width="stretch", config=CHART_CONFIG, key=key)


def holdings_page():
    st.header("My silver")
    existing = st.session_state.get("holding")
    with st.form("holding-inputs"):
        quantity = st.number_input("Silver weight", min_value=0., max_value=1e9, step=1.,
                                   value=float(existing.quantity) if existing else 0., key="weight-input")
        units = ("troy oz", "kg")
        unit = st.radio("Unit", units, horizontal=True,
                        index=units.index(existing.unit) if existing else 0, key="unit-input",
                        format_func=lambda value: "Troy ounces" if value == "troy oz" else "Kilograms")
        start = st.date_input("Held since", value=existing.start_date if existing else START,
                              min_value=START, max_value=date.today(), key="holding-start-input")
        submitted = st.form_submit_button("Calculate value", type="primary", width="stretch")
    holding = existing
    try:
        if submitted:
            holding = Holding(quantity, unit, start)
        if holding is None:
            return
        with st.spinner("Loading daily silver prices…"):
            history = value_history(daily_prices(), holding)
        st.session_state.holding = holding
    except (OSError, ValueError) as error:
        st.error(str(error))
        return
    values = history["holding_value_eur"]
    st.metric("Latest estimate", euro(values.iloc[-1]),
              f"{values.iloc[-1] / values.iloc[0] - 1:+.1%} since {values.index[0]:%d %b %Y}")
    st.caption(f"{holding.kg:,.3f} kg · Close on {values.index[-1]:%d %b %Y} · "
               f"Starting reference value {euro(values.iloc[0])}")
    show_chart({"Holding value": values}, "€", "holding-history")
    st.download_button("Download holding history", history.to_csv(index_label="date"),
                       "silver-holding-history.csv", "text/csv")


def intraday_panel():
    live = st.toggle("Refresh every minute", value=True)
    holding = st.session_state.get("holding")
    show_holding = st.checkbox("Show my holding value", value=False) if holding else False

    @st.fragment(run_every="60s" if live else None)
    def quote():
        st.button("Check now")
        try:
            bars = intraday_prices()
            st.session_state.latest_intraday = bars
        except (ValueError, OSError) as error:
            st.warning(f"Could not refresh. {error}")
            bars = st.session_state.get("latest_intraday")
            if bars is None:
                return
        values = bars["silver_eur_per_kg"]
        if show_holding:
            values = values * holding.kg
        st.metric("Estimated holding value" if show_holding else "Latest silver price",
                  euro(values.iloc[-1]) if show_holding else f"{euro(values.iloc[-1])}/kg")
        st.caption(f"Silver bar {values.index[-1]:%d %b, %H:%M UTC} · "
                   f"FX bar {bars.fx_time.iloc[-1]:%d %b, %H:%M UTC} · Feed may be delayed")
        show_chart({"Silver": values}, "€" if show_holding else "€/kg",
                   f"intraday-{show_holding}", intraday=True)

    quote()


def prices_page():
    st.header("Price history")
    view = st.radio("View", ["Daily history", "Intraday"], horizontal=True)
    if view == "Intraday":
        intraday_panel()
        return
    try:
        with st.spinner("Loading daily silver prices…"):
            bars = daily_prices()
    except (OSError, ValueError) as error:
        st.error(str(error))
        return
    st.metric("Latest daily close", f'{euro(bars["Close"].iloc[-1])}/kg')
    st.caption(f"Through {bars.index[-1]:%d %b %Y}")
    show_chart({"Silver": bars["Close"]}, "€/kg", "silver-daily")
    st.download_button("Download daily prices", bars.rename(
        columns={"Open": "open_eur_per_kg", "Close": "close_eur_per_kg"}
    ).to_csv(index_label="date"), "silver-prices.csv", "text/csv")


def run_strategy(mode, params, account, train, test):
    bars = daily_prices()
    if mode == "Walk-forward":
        ledger, folds = walk_forward(bars, params, account, train, test)
        return {params.strategy: ledger}, folds
    if mode == "Compare strategies":
        return {name: fixed_run(bars, replace(params, strategy=name), account)
                for name in STRATEGIES}, None
    return {params.strategy: fixed_run(bars, params, account)}, None


def strategy_results(ledgers, folds):
    first = next(iter(ledgers.values()))
    equity = {name: run["strategy_equity"] for name, run in ledgers.items()}
    equity["Buy and hold"] = first["benchmark_equity"]
    show_chart(equity, "€", "strategy-equity")
    table = {name: summary(run, currency="€").loc["Strategy"] for name, run in ledgers.items()}
    table["Buy and hold"] = summary(first, currency="€").loc["Buy and hold"]
    st.dataframe(pd.DataFrame(table).T.round(2), width="stretch")
    if folds is not None:
        with st.expander("Walk-forward test periods"):
            st.dataframe(folds, width="stretch", hide_index=True)
            st.download_button("Download test periods", folds.to_csv(index=False),
                               "silver-walk-forward.csv", "text/csv")

    name = st.selectbox("Strategy detail", options=list(ledgers))
    run = ledgers[name]
    with st.expander("Price, trade markers and drawdown"):
        figure = chart(run, f"Silver · {name}", currency="€",
                       price_label="Silver price (€/kg)", close_label="Daily close")
        try:
            image = BytesIO()
            figure.savefig(image, dpi=145, format="png")
            st.image(image.getvalue(), width="stretch")
            st.download_button("Download chart", image.getvalue(), "silver-strategy.png", "image/png")
        finally:
            plt.close(figure)
    st.download_button("Download daily strategy results", run.to_csv(index_label="date"),
                       "silver-strategy.csv", "text/csv")


def strategy_page():
    st.header("Strategy lab")
    mode = st.selectbox("Mode", ["Single strategy", "Compare strategies", "Walk-forward"])
    name = st.selectbox("Strategy", STRATEGIES) if mode != "Compare strategies" else STRATEGIES[0]
    with st.form("strategy"):
        window = st.number_input("Lookback (sessions)", min_value=5, max_value=250, value=20)
        with st.expander("Adjust allocation, fees and strategy settings"):
            capital = st.number_input("Starting capital (€)", min_value=1., max_value=1e9, value=10_000.)
            allocation = st.slider("Allocation (%)", 1, 100, 25)
            fee = st.number_input("Fee per trade (basis points)", min_value=0., max_value=9999., value=10.)
            if mode == "Compare strategies" or name == STRATEGIES[0]:
                entry = st.number_input("Buy below average (%)", min_value=0., max_value=99., value=2.)
                exit_threshold = st.number_input("Sell above average (%)", min_value=0., max_value=100., value=2.)
            else:
                entry = exit_threshold = 2.
            fast = st.number_input("Fast moving average (sessions)", 1, 249, 10) if (
                mode == "Compare strategies" or name == STRATEGIES[2]
            ) else 10
        train, test = 504, 126
        if mode == "Walk-forward":
            train = st.number_input("Training sessions", min_value=3, max_value=5000, value=train)
            test = st.number_input("Test sessions", min_value=1, max_value=2000, value=test)
        submitted = st.form_submit_button("Run backtest", type="primary", width="stretch")
    if submitted:
        try:
            if (mode == "Compare strategies" or name == STRATEGIES[2]) and fast >= window:
                raise ValueError("The fast moving average must be shorter than the lookback.")
            params = Parameters(name, window, fast, entry / 100, exit_threshold / 100)
            account = Account(capital, allocation / 100, fee)
            with st.spinner("Running the backtest…"):
                st.session_state.strategy_result = (mode, name, *run_strategy(mode, params, account, train, test))
        except (OSError, ValueError) as error:
            st.error(str(error))
            return
    result = st.session_state.get("strategy_result")
    if result is not None and result[:2] == (mode, name):
        strategy_results(*result[2:])


st.set_page_config(page_title="Silver tracker", page_icon="◈", layout="centered")
st.title("Silver tracker")
page = st.radio("Section", ["My silver", "Price history", "Strategy lab"],
                horizontal=True, label_visibility="collapsed")
{"My silver": holdings_page, "Price history": prices_page, "Strategy lab": strategy_page}[page]()
st.caption("Prices use silver futures converted to euros. Dealer prices for physical silver may differ.")
