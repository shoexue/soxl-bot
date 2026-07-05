import pandas as pd
from itertools import product

soxl = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date"
)

soxl = soxl[soxl.index >= "2021-07-05"].copy()

threshold = -1.75
signal = soxl["z_score"] < threshold
episode_start = signal & ~signal.shift(1, fill_value=False)
signal_dates = soxl.index[episode_start]

stops = [-0.08, -0.10, -0.12, -0.15]
targets = [0.08, 0.12, 0.15, 0.20]
max_holds = [3, 5, 10]

results = []

for stop_loss, profit_target, max_hold in product(stops, targets, max_holds):

    trade_returns = []

    for signal_date in signal_dates:
        signal_pos = soxl.index.get_loc(signal_date)
        entry_pos = signal_pos + 1

        if entry_pos + max_hold - 1 >= len(soxl):
            continue

        entry_price = soxl.iloc[entry_pos]["Open"]
        exit_price = None

        for i in range(max_hold):
            day = soxl.iloc[entry_pos + i]

            stop_price = entry_price * (1 + stop_loss)
            target_price = entry_price * (1 + profit_target)

            hit_stop = day["Low"] <= stop_price
            hit_target = day["High"] >= target_price

            if hit_stop and hit_target:
                # Conservative assumption: stop happened first
                exit_price = stop_price
                break
            elif hit_stop:
                exit_price = stop_price
                break
            elif hit_target:
                exit_price = target_price
                break

        if exit_price is None:
            exit_price = soxl.iloc[entry_pos + max_hold - 1]["Close"]

        trade_return = (exit_price / entry_price) - 1
        trade_returns.append(trade_return)

    returns = pd.Series(trade_returns)

    results.append({
        "stop_loss": stop_loss,
        "profit_target": profit_target,
        "max_hold": max_hold,
        "trades": len(returns),
        "avg_return": returns.mean(),
        "median_return": returns.median(),
        "win_rate": (returns > 0).mean(),
        "worst_trade": returns.min(),
        "best_trade": returns.max(),
        "total_return_simple": returns.sum(),
    })

results_df = pd.DataFrame(results)

results_df = results_df.sort_values(
    by=["median_return", "avg_return"],
    ascending=False
)

results_df.to_csv("data/exit_backtest_results.csv", index=False)

pd.set_option("display.max_rows", 100)

print(
    results_df.to_string(
        index=False,
        formatters={
            "stop_loss": "{:.0%}".format,
            "profit_target": "{:.0%}".format,
            "avg_return": "{:.2%}".format,
            "median_return": "{:.2%}".format,
            "win_rate": "{:.2%}".format,
            "worst_trade": "{:.2%}".format,
            "best_trade": "{:.2%}".format,
            "total_return_simple": "{:.2%}".format,
        }
    )
)