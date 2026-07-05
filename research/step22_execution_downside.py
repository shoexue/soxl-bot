import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# 1. SETTINGS
# ============================================================

DOWNLOAD_START = "2020-01-01"
RESEARCH_START = "2021-01-01"

STARTING_CAPITAL = 10_000
POSITION_FRACTION = 0.50

QQQ_MA_WINDOW = 50
SLIPPAGE = 0.001

# Fixed fast strategy family from walk-forward evidence
Z_WINDOWS = [5, 6]
Z_THRESHOLDS = [-1.50, -1.70]
HOLD_DAYS_LIST = [4, 5]

# Stops to test
STOP_LEVELS = [
    None,      # no stop
    -0.08,
    -0.10,
    -0.12,
    -0.15,
]

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# ============================================================
# 2. DOWNLOAD DATA
# ============================================================

def download_data(ticker):
    print(f"Downloading {ticker}...")

    df = yf.download(
        ticker,
        start=DOWNLOAD_START,
        auto_adjust=True,
        progress=False,
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df[["Open", "High", "Low", "Close", "Volume"]].copy()


soxl = download_data("SOXL")
qqq = download_data("QQQ")


# ============================================================
# 3. BUILD QQQ FILTER
# ============================================================

qqq["ma_50"] = qqq["Close"].rolling(QQQ_MA_WINDOW).mean()
qqq["above_ma50"] = qqq["Close"] > qqq["ma_50"]

soxl["qqq_above_ma50"] = (
    qqq["above_ma50"]
    .reindex(soxl.index)
    .fillna(False)
    .astype(bool)
)


# ============================================================
# 4. BUILD Z-SCORES
# ============================================================

for window in Z_WINDOWS:
    mean = soxl["Close"].rolling(window).mean()
    std = soxl["Close"].rolling(window).std()

    soxl[f"z_{window}"] = (soxl["Close"] - mean) / std


soxl = soxl[soxl.index >= RESEARCH_START].copy()


# ============================================================
# 5. SIGNAL FUNCTION
# ============================================================

def create_signals(data, z_window, z_threshold):
    z_col = f"z_{z_window}"

    oversold = data[z_col] < z_threshold

    episode_start = (
        oversold
        &
        ~oversold.shift(1, fill_value=False)
    )

    signals = (
        episode_start
        &
        data["qqq_above_ma50"]
    )

    return signals


# ============================================================
# 6. GENERATE TRADES WITH PATH DATA
# ============================================================

def generate_trades(data, z_window, z_threshold, hold_days, stop_level):
    signals = create_signals(
        data=data,
        z_window=z_window,
        z_threshold=z_threshold,
    )

    signal_dates = data.index[signals]
    trades = []

    for signal_date in signal_dates:
        signal_pos = data.index.get_loc(signal_date)
        entry_pos = signal_pos + 1

        if entry_pos >= len(data):
            continue

        max_exit_pos = entry_pos + hold_days - 1

        if max_exit_pos >= len(data):
            continue

        entry_date = data.index[entry_pos]

        raw_entry_price = data.iloc[entry_pos]["Open"]
        entry_price = raw_entry_price * (1 + SLIPPAGE)

        future = data.iloc[entry_pos : max_exit_pos + 1].copy()

        # Path diagnostics
        mae = (future["Low"].min() / entry_price) - 1
        mfe = (future["High"].max() / entry_price) - 1

        worst_day_pos = future["Low"].idxmin()
        best_day_pos = future["High"].idxmax()

        # Default fixed-hold exit
        exit_pos = max_exit_pos
        exit_reason = "fixed_hold"
        raw_exit_price = data.iloc[exit_pos]["Close"]
        exit_price = raw_exit_price * (1 - SLIPPAGE)

        # Optional stop
        if stop_level is not None:
            stop_price = entry_price * (1 + stop_level)

            for pos in range(entry_pos, max_exit_pos + 1):
                day = data.iloc[pos]

                if day["Low"] <= stop_price:
                    exit_pos = pos
                    exit_reason = "stop"
                    exit_price = stop_price * (1 - SLIPPAGE)
                    break

        exit_date = data.index[exit_pos]

        position_return = (exit_price / entry_price) - 1
        account_return = POSITION_FRACTION * position_return

        trades.append({
            "z_window": z_window,
            "z_threshold": z_threshold,
            "hold_days": hold_days,
            "stop_level": stop_level if stop_level is not None else "None",

            "signal_date": signal_date,
            "entry_date": entry_date,
            "exit_date": exit_date,

            "signal_z": data.loc[signal_date, f"z_{z_window}"],

            "entry_price": entry_price,
            "exit_price": exit_price,

            "position_return": position_return,
            "account_return": account_return,

            "mae": mae,
            "mfe": mfe,
            "worst_day_date": worst_day_pos,
            "best_day_date": best_day_pos,

            "exit_reason": exit_reason,
        })

    return pd.DataFrame(trades)


# ============================================================
# 7. MAX DRAWDOWN FROM TRADE SEQUENCE
# ============================================================

def trade_sequence_max_drawdown(account_returns):
    equity = [STARTING_CAPITAL]

    for r in account_returns:
        equity.append(equity[-1] * (1 + r))

    equity = pd.Series(equity)
    peak = equity.cummax()
    dd = equity / peak - 1

    return dd.min(), equity.iloc[-1]


# ============================================================
# 8. RUN GRID
# ============================================================

all_trades = []
summary_rows = []

for z_window in Z_WINDOWS:
    for z_threshold in Z_THRESHOLDS:
        for hold_days in HOLD_DAYS_LIST:
            for stop_level in STOP_LEVELS:

                trades = generate_trades(
                    data=soxl,
                    z_window=z_window,
                    z_threshold=z_threshold,
                    hold_days=hold_days,
                    stop_level=stop_level,
                )

                if len(trades) == 0:
                    continue

                all_trades.append(trades)

                returns = trades["position_return"]
                account_returns = trades["account_return"]

                max_dd, final_capital = trade_sequence_max_drawdown(
                    account_returns
                )

                stop_label = stop_level if stop_level is not None else "None"

                summary_rows.append({
                    "z_window": z_window,
                    "z_threshold": z_threshold,
                    "hold_days": hold_days,
                    "stop_level": stop_label,

                    "trades": len(trades),

                    "avg_position_return": returns.mean(),
                    "median_position_return": returns.median(),
                    "win_rate": (returns > 0).mean(),

                    "best_trade": returns.max(),
                    "worst_trade": returns.min(),

                    "avg_mae": trades["mae"].mean(),
                    "median_mae": trades["mae"].median(),
                    "worst_mae": trades["mae"].min(),

                    "avg_mfe": trades["mfe"].mean(),
                    "median_mfe": trades["mfe"].median(),
                    "best_mfe": trades["mfe"].max(),

                    "stop_exits": (trades["exit_reason"] == "stop").sum(),
                    "fixed_exits": (trades["exit_reason"] == "fixed_hold").sum(),

                    "final_capital_50pct": final_capital,
                    "total_return_50pct": (final_capital / STARTING_CAPITAL) - 1,
                    "trade_sequence_max_drawdown_50pct": max_dd,
                })


trades_output = pd.concat(all_trades, ignore_index=True)
summary = pd.DataFrame(summary_rows)


# ============================================================
# 9. RANK RESULTS
# ============================================================

summary["return_to_drawdown"] = (
    summary["total_return_50pct"]
    / summary["trade_sequence_max_drawdown_50pct"].abs()
)

summary = summary.sort_values(
    ["return_to_drawdown", "total_return_50pct"],
    ascending=False,
)


# ============================================================
# 10. SAVE OUTPUTS
# ============================================================

summary.to_csv(
    DATA_DIR / "execution_downside_summary.csv",
    index=False,
)

trades_output.to_csv(
    DATA_DIR / "execution_downside_trades.csv",
    index=False,
)


# ============================================================
# 11. PRINT RESULTS
# ============================================================

print()
print("=" * 120)
print("EXECUTION / DOWNSIDE SUMMARY")
print("=" * 120)
print()

print(
    summary.to_string(
        index=False,
        formatters={
            "avg_position_return": "{:.2%}".format,
            "median_position_return": "{:.2%}".format,
            "win_rate": "{:.2%}".format,
            "best_trade": "{:.2%}".format,
            "worst_trade": "{:.2%}".format,
            "avg_mae": "{:.2%}".format,
            "median_mae": "{:.2%}".format,
            "worst_mae": "{:.2%}".format,
            "avg_mfe": "{:.2%}".format,
            "median_mfe": "{:.2%}".format,
            "best_mfe": "{:.2%}".format,
            "final_capital_50pct": "${:,.2f}".format,
            "total_return_50pct": "{:.2%}".format,
            "trade_sequence_max_drawdown_50pct": "{:.2%}".format,
            "return_to_drawdown": "{:.2f}".format,
        },
    )
)

print()
print("Files saved:")
print("data/execution_downside_summary.csv")
print("data/execution_downside_trades.csv")