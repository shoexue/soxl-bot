import pandas as pd


STARTING_CAPITAL = 10_000
SIGNAL_THRESHOLD = -1.75

STOP_LOSS = -0.12
PROFIT_TARGET = 0.20
MAX_HOLD = 5
SLIPPAGE = 0.001

QQQ_MA_WINDOWS = [50, 100, 200]

TEST_WINDOWS = {
    "Full available": None,
    "Recent 5y": "2021-07-05",
    "Older only": "2010-01-01",
}


soxl_raw = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date"
)

qqq_raw = pd.read_csv(
    "data/QQQ.csv",
    parse_dates=["Date"],
    index_col="Date"
)


def max_drawdown(equity):
    peak = equity.cummax()
    dd = (equity / peak) - 1
    return dd.min()


def run_backtest(data, signals):
    capital = STARTING_CAPITAL
    trades = []
    equity_records = []

    i = 0

    while i < len(data):
        date = data.index[i]
        equity_records.append({"Date": date, "Equity": capital})

        if not signals.iloc[i]:
            i += 1
            continue

        entry_pos = i + 1

        if entry_pos >= len(data):
            break

        raw_entry = data.iloc[entry_pos]["Open"]
        entry_price = raw_entry * (1 + SLIPPAGE)

        stop_price = entry_price * (1 + STOP_LOSS)
        target_price = entry_price * (1 + PROFIT_TARGET)

        shares = capital / entry_price

        exit_price = None
        exit_pos = None
        exit_reason = None

        for hold_index in range(MAX_HOLD):
            day_pos = entry_pos + hold_index

            if day_pos >= len(data):
                break

            day = data.iloc[day_pos]

            hit_stop = day["Low"] <= stop_price
            hit_target = day["High"] >= target_price

            if hit_stop and hit_target:
                exit_price = stop_price * (1 - SLIPPAGE)
                exit_pos = day_pos
                exit_reason = "stop_both_hit"
                break

            elif hit_stop:
                exit_price = stop_price * (1 - SLIPPAGE)
                exit_pos = day_pos
                exit_reason = "stop"
                break

            elif hit_target:
                exit_price = target_price * (1 - SLIPPAGE)
                exit_pos = day_pos
                exit_reason = "target"
                break

        if exit_price is None:
            exit_pos = min(entry_pos + MAX_HOLD - 1, len(data) - 1)
            raw_exit = data.iloc[exit_pos]["Close"]
            exit_price = raw_exit * (1 - SLIPPAGE)
            exit_reason = "time_exit"

        for j in range(entry_pos, exit_pos + 1):
            current_date = data.index[j]

            if j == exit_pos:
                current_equity = shares * exit_price
            else:
                current_equity = shares * data.iloc[j]["Close"]

            equity_records.append({
                "Date": current_date,
                "Equity": current_equity
            })

        trade_return = (exit_price / entry_price) - 1
        capital *= (1 + trade_return)

        trades.append({
            "signal_date": date,
            "entry_date": data.index[entry_pos],
            "exit_date": data.index[exit_pos],
            "return": trade_return,
            "exit_reason": exit_reason,
            "capital_after": capital,
        })

        i = exit_pos + 1

    trades_df = pd.DataFrame(trades)

    equity_df = (
        pd.DataFrame(equity_records)
        .drop_duplicates(subset="Date", keep="last")
        .set_index("Date")
        .sort_index()
        .reindex(data.index)
        .ffill()
    )

    return capital, trades_df, equity_df


rows = []
all_trades = []

for window_name, start_date in TEST_WINDOWS.items():

    if start_date is None:
        soxl = soxl_raw.copy()
        qqq = qqq_raw.copy()

    else:
        soxl = soxl_raw[soxl_raw.index >= start_date].copy()
        qqq = qqq_raw[qqq_raw.index >= start_date].copy()

    for ma_window in QQQ_MA_WINDOWS:

        qqq[f"ma_{ma_window}"] = qqq["Close"].rolling(ma_window).mean()

        qqq[f"trend_{ma_window}"] = (
            qqq["Close"] / qqq[f"ma_{ma_window}"]
        ) - 1

        soxl["qqq_trend"] = qqq[f"trend_{ma_window}"].reindex(soxl.index)

        oversold = soxl["z_score"] < SIGNAL_THRESHOLD

        base_episode_start = (
            oversold
            & ~oversold.shift(1, fill_value=False)
        )

        qqq_filter_signals = (
            base_episode_start
            & (soxl["qqq_trend"] > 0)
        )

        final_capital, trades, equity = run_backtest(
            data=soxl,
            signals=qqq_filter_signals
        )

        if len(trades) > 0:
            win_rate = (trades["return"] > 0).mean()
            avg_trade = trades["return"].mean()
            median_trade = trades["return"].median()
        else:
            win_rate = 0
            avg_trade = 0
            median_trade = 0

        rows.append({
            "window": window_name,
            "start_date": soxl.index.min(),
            "end_date": soxl.index.max(),
            "qqq_ma_window": ma_window,
            "signals": int(qqq_filter_signals.sum()),
            "trades": len(trades),
            "final_capital": final_capital,
            "total_return": (final_capital / STARTING_CAPITAL) - 1,
            "max_drawdown": max_drawdown(equity["Equity"]),
            "win_rate": win_rate,
            "avg_trade": avg_trade,
            "median_trade": median_trade,
        })

        if len(trades) > 0:
            trades = trades.copy()
            trades["window"] = window_name
            trades["qqq_ma_window"] = ma_window
            all_trades.append(trades)


summary = pd.DataFrame(rows)

if all_trades:
    trades_out = pd.concat(all_trades, ignore_index=True)
else:
    trades_out = pd.DataFrame()

summary.to_csv(
    "data/robustness_summary.csv",
    index=False
)

trades_out.to_csv(
    "data/robustness_trades.csv",
    index=False
)

print()
print("=" * 90)
print("ROBUSTNESS TEST RESULTS")
print("=" * 90)
print()

print(
    summary.to_string(
        index=False,
        formatters={
            "total_return": "{:.2%}".format,
            "max_drawdown": "{:.2%}".format,
            "win_rate": "{:.2%}".format,
            "avg_trade": "{:.2%}".format,
            "median_trade": "{:.2%}".format,
            "final_capital": "${:,.2f}".format,
        }
    )
)

print()
print("Files saved:")
print("data/robustness_summary.csv")
print("data/robustness_trades.csv")