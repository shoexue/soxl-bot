import pandas as pd

# -------------------------
# 1. Load data
# -------------------------

df = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date"
)

# Only use recent 5 years
df = df[df.index >= "2021-07-05"].copy()


# -------------------------
# 2. Settings
# -------------------------

thresholds = [
    -1.0,
    -1.25,
    -1.5,
    -1.75,
    -2.0
]

holding_periods = [
    1,
    2,
    3,
    5,
    10
]

results = []


# -------------------------
# 3. Test each threshold
# -------------------------

for threshold in thresholds:

    signal = df["z_score"] < threshold

    # Only count the FIRST day of each signal episode
    episode_start = signal & ~signal.shift(1, fill_value=False)

    signal_indices = df.index[episode_start]

    for hold_days in holding_periods:

        returns = []

        for signal_date in signal_indices:

            signal_pos = df.index.get_loc(signal_date)

            # Need enough future data
            entry_pos = signal_pos + 1
            exit_pos = entry_pos + hold_days - 1

            if exit_pos >= len(df):
                continue

            # Enter next trading day at Open
            entry_price = df.iloc[entry_pos]["Open"]

            # Exit at Close after N sessions
            exit_price = df.iloc[exit_pos]["Close"]

            trade_return = (
                exit_price / entry_price
            ) - 1

            returns.append(trade_return)

        if len(returns) == 0:
            continue

        returns = pd.Series(returns)

        results.append({
            "threshold": threshold,
            "hold_days": hold_days,
            "trades": len(returns),
            "avg_return": returns.mean(),
            "median_return": returns.median(),
            "win_rate": (returns > 0).mean()
        })


# -------------------------
# 4. Display results
# -------------------------

results_df = pd.DataFrame(results)

pd.set_option("display.max_rows", None)

print(
    results_df.to_string(
        index=False,
        formatters={
            "avg_return": "{:.2%}".format,
            "median_return": "{:.2%}".format,
            "win_rate": "{:.2%}".format
        }
    )
)

results_df.to_csv(
    "data/threshold_results.csv",
    index=False
)