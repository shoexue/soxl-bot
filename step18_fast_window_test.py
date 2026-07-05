import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-01-01"
DOWNLOAD_START = "2020-01-01"

Z_WINDOWS = [
    3,
    5,
    10,
    20,
]

Z_THRESHOLDS = [
    -1.25,
    -1.50,
    -1.75,
    -2.00,
]

HOLD_DAYS_LIST = [
    1,
    2,
    3,
    5,
]

QQQ_MA_WINDOW = 50

SLIPPAGE = 0.001

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

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):
        df.columns = (
            df.columns
            .get_level_values(0)
        )

    return df[
        [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    ].copy()


soxl = download_data("SOXL")
qqq = download_data("QQQ")


print()

print(
    f"SOXL: {soxl.index.min()} "
    f"→ {soxl.index.max()}"
)

print(
    f"QQQ: {qqq.index.min()} "
    f"→ {qqq.index.max()}"
)


# ============================================================
# 3. QQQ REGIME FILTER
# ============================================================

qqq["ma_50"] = (
    qqq["Close"]
    .rolling(QQQ_MA_WINDOW)
    .mean()
)

qqq["above_ma50"] = (
    qqq["Close"]
    > qqq["ma_50"]
)


soxl["qqq_above_ma50"] = (
    qqq["above_ma50"]
    .reindex(soxl.index)
    .fillna(False)
    .astype(bool)
)


# ============================================================
# 4. BUILD ALL Z-SCORES
# ============================================================

for window in Z_WINDOWS:

    mean_column = f"mean_{window}"
    std_column = f"std_{window}"
    z_column = f"z_{window}"

    soxl[mean_column] = (
        soxl["Close"]
        .rolling(window)
        .mean()
    )

    soxl[std_column] = (
        soxl["Close"]
        .rolling(window)
        .std()
    )

    soxl[z_column] = (
        (
            soxl["Close"]
            - soxl[mean_column]
        )
        /
        soxl[std_column]
    )


# ============================================================
# 5. MODERN PERIOD ONLY
# ============================================================

soxl = soxl[
    soxl.index >= START_DATE
].copy()


# ============================================================
# 6. TEST ONE PARAMETER COMBINATION
# ============================================================

def test_combination(
    data,
    z_window,
    z_threshold,
    hold_days,
):

    z_column = f"z_{z_window}"

    oversold = (
        data[z_column]
        < z_threshold
    )


    # Only first day of a new oversold episode

    episode_start = (
        oversold
        &
        ~oversold.shift(
            1,
            fill_value=False,
        )
    )


    signals = (
        episode_start
        &
        data["qqq_above_ma50"]
    )


    signal_dates = (
        data.index[signals]
    )


    trades = []


    for signal_date in signal_dates:

        signal_pos = (
            data.index.get_loc(
                signal_date
            )
        )


        # Buy next open

        entry_pos = (
            signal_pos + 1
        )


        # Hold N complete trading sessions:
        #
        # hold 1 = exit entry-day close
        # hold 2 = exit next day's close
        # etc.

        exit_pos = (
            entry_pos
            + hold_days
            - 1
        )


        if exit_pos >= len(data):
            continue


        entry_date = (
            data.index[entry_pos]
        )

        exit_date = (
            data.index[exit_pos]
        )


        raw_entry_price = (
            data.iloc[entry_pos][
                "Open"
            ]
        )


        raw_exit_price = (
            data.iloc[exit_pos][
                "Close"
            ]
        )


        entry_price = (
            raw_entry_price
            * (1 + SLIPPAGE)
        )


        exit_price = (
            raw_exit_price
            * (1 - SLIPPAGE)
        )


        trade_return = (
            exit_price
            / entry_price
        ) - 1


        trades.append({

            "z_window":
                z_window,

            "z_threshold":
                z_threshold,

            "hold_days":
                hold_days,

            "signal_date":
                signal_date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

            "signal_z_score":
                data.loc[
                    signal_date,
                    z_column,
                ],

            "entry_price":
                entry_price,

            "exit_price":
                exit_price,

            "return":
                trade_return,

            "winner":
                trade_return > 0,
        })


    return pd.DataFrame(trades)


# ============================================================
# 7. RUN FULL GRID
# ============================================================

all_trades = []
summary_rows = []


total_tests = (
    len(Z_WINDOWS)
    * len(Z_THRESHOLDS)
    * len(HOLD_DAYS_LIST)
)


test_number = 0


for z_window in Z_WINDOWS:

    for z_threshold in Z_THRESHOLDS:

        for hold_days in HOLD_DAYS_LIST:

            test_number += 1

            print(
                f"Test {test_number}/{total_tests}: "
                f"window={z_window}, "
                f"threshold={z_threshold}, "
                f"hold={hold_days}"
            )


            trades = test_combination(
                data=soxl,
                z_window=z_window,
                z_threshold=z_threshold,
                hold_days=hold_days,
            )


            if len(trades) == 0:
                continue


            all_trades.append(trades)


            returns = trades["return"]


            compounded_return = (
                (1 + returns).prod()
                - 1
            )


            downside_returns = (
                returns[
                    returns < 0
                ]
            )


            summary_rows.append({

                "z_window":
                    z_window,

                "z_threshold":
                    z_threshold,

                "hold_days":
                    hold_days,

                "trades":
                    len(trades),

                "avg_return":
                    returns.mean(),

                "median_return":
                    returns.median(),

                "win_rate":
                    trades["winner"].mean(),

                "compounded_trade_return":
                    compounded_return,

                "best_trade":
                    returns.max(),

                "worst_trade":
                    returns.min(),

                "return_std":
                    returns.std(),

                "avg_loss":
                    (
                        downside_returns.mean()
                        if len(downside_returns) > 0
                        else 0
                    ),
            })


# ============================================================
# 8. COMBINE RESULTS
# ============================================================

trades_output = pd.concat(
    all_trades,
    ignore_index=True,
)


summary = pd.DataFrame(
    summary_rows
)


# ============================================================
# 9. SIMPLE QUALITY SCORE
#
# This is only for sorting candidates.
# Do NOT treat it as a final optimization objective.
# ============================================================

summary["quality_score"] = (

    summary["avg_return"]
    /
    summary["return_std"]
    .replace(0, np.nan)

    *

    np.sqrt(
        summary["trades"]
    )
)


# ============================================================
# 10. RANK RESULTS
# ============================================================

summary_by_avg = (
    summary
    .sort_values(
        [
            "avg_return",
            "trades",
        ],
        ascending=[
            False,
            False,
        ],
    )
)


summary_by_quality = (
    summary
    .sort_values(
        "quality_score",
        ascending=False,
    )
)


# ============================================================
# 11. ROBUSTNESS TABLE
#
# Average across thresholds for each
# window + holding period combination.
#
# This is important:
# we prefer broad stable regions over one lucky parameter.
# ============================================================

robustness = (

    summary

    .groupby(
        [
            "z_window",
            "hold_days",
        ]
    )

    .agg(

        parameter_tests=(
            "z_threshold",
            "count",
        ),

        avg_trades=(
            "trades",
            "mean",
        ),

        avg_trade_return=(
            "avg_return",
            "mean",
        ),

        median_of_median_returns=(
            "median_return",
            "median",
        ),

        avg_win_rate=(
            "win_rate",
            "mean",
        ),

        avg_quality_score=(
            "quality_score",
            "mean",
        ),
    )

    .reset_index()

    .sort_values(
        "avg_quality_score",
        ascending=False,
    )
)


# ============================================================
# 12. YEARLY RESULTS
# ============================================================

trades_output["year"] = (

    pd.to_datetime(
        trades_output["signal_date"]
    )

    .dt.year
)


yearly = (

    trades_output

    .groupby(
        [
            "z_window",
            "z_threshold",
            "hold_days",
            "year",
        ]
    )

    .agg(

        trades=(
            "return",
            "count",
        ),

        avg_return=(
            "return",
            "mean",
        ),

        median_return=(
            "return",
            "median",
        ),

        win_rate=(
            "winner",
            "mean",
        ),

        compounded_return=(
            "return",
            lambda x:
                (1 + x).prod() - 1,
        ),
    )

    .reset_index()
)


# ============================================================
# 13. SAVE FILES
# ============================================================

summary.to_csv(
    DATA_DIR
    / "fast_window_summary.csv",
    index=False,
)


trades_output.to_csv(
    DATA_DIR
    / "fast_window_trades.csv",
    index=False,
)


robustness.to_csv(
    DATA_DIR
    / "fast_window_robustness.csv",
    index=False,
)


yearly.to_csv(
    DATA_DIR
    / "fast_window_yearly.csv",
    index=False,
)


# ============================================================
# 14. PRINT TOP RESULTS
# ============================================================

percent_columns = {

    "avg_return":
        "{:.2%}".format,

    "median_return":
        "{:.2%}".format,

    "win_rate":
        "{:.2%}".format,

    "compounded_trade_return":
        "{:.2%}".format,

    "best_trade":
        "{:.2%}".format,

    "worst_trade":
        "{:.2%}".format,

    "return_std":
        "{:.2%}".format,

    "avg_loss":
        "{:.2%}".format,
}


print()

print("=" * 120)

print(
    "TOP 15 BY AVERAGE TRADE RETURN"
)

print("=" * 120)

print()


print(
    summary_by_avg
    .head(15)
    .to_string(
        index=False,
        formatters=percent_columns,
    )
)


print()

print("=" * 120)

print(
    "TOP 15 BY QUALITY SCORE"
)

print("=" * 120)

print()


print(
    summary_by_quality
    .head(15)
    .to_string(
        index=False,
        formatters=percent_columns,
    )
)


print()

print("=" * 120)

print(
    "WINDOW / HOLD ROBUSTNESS"
)

print("=" * 120)

print()


print(
    robustness.to_string(
        index=False,
        formatters={

            "avg_trade_return":
                "{:.2%}".format,

            "median_of_median_returns":
                "{:.2%}".format,

            "avg_win_rate":
                "{:.2%}".format,

            "avg_quality_score":
                "{:.3f}".format,
        },
    )
)


print()

print("Files saved:")

print(
    "data/fast_window_summary.csv"
)

print(
    "data/fast_window_trades.csv"
)

print(
    "data/fast_window_robustness.csv"
)

print(
    "data/fast_window_yearly.csv"
)