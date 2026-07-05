import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-01-01"
DOWNLOAD_START = "2020-01-01"

QQQ_MA_WINDOW = 50

SLIPPAGE = 0.001

MIN_SIGNALS = 5


# Short-window neighborhood around our 5D candidate

Z_WINDOWS = [
    3,
    4,
    5,
    6,
    7,
    8,
    10,
]


Z_THRESHOLDS = [
    -1.00,
    -1.10,
    -1.20,
    -1.30,
    -1.40,
    -1.50,
    -1.60,
    -1.70,
    -1.80,
    -1.90,
    -2.00,
]


HOLD_DAYS_LIST = [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
]


DATA_DIR = Path("data")

DATA_DIR.mkdir(
    exist_ok=True
)


# ============================================================
# 2. DOWNLOAD DATA
# ============================================================

def download_data(
    ticker,
):

    print(
        f"Downloading {ticker}..."
    )


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


soxl = download_data(
    "SOXL"
)


qqq = download_data(
    "QQQ"
)


print()

print(
    f"SOXL: "
    f"{soxl.index.min()} "
    f"→ "
    f"{soxl.index.max()}"
)


# ============================================================
# 3. QQQ REGIME FILTER
# ============================================================

qqq["ma_50"] = (

    qqq["Close"]

    .rolling(
        QQQ_MA_WINDOW
    )

    .mean()
)


qqq["above_ma50"] = (

    qqq["Close"]

    > qqq["ma_50"]
)


soxl["qqq_above_ma50"] = (

    qqq["above_ma50"]

    .reindex(
        soxl.index
    )

    .fillna(False)

    .astype(bool)
)


# ============================================================
# 4. BUILD Z-SCORES
# ============================================================

for window in Z_WINDOWS:

    rolling_mean = (

        soxl["Close"]

        .rolling(window)

        .mean()
    )


    rolling_std = (

        soxl["Close"]

        .rolling(window)

        .std()
    )


    soxl[
        f"z_{window}"
    ] = (

        (
            soxl["Close"]
            - rolling_mean
        )

        / rolling_std
    )


# ============================================================
# 5. MODERN PERIOD
# ============================================================

soxl = soxl[
    soxl.index >= START_DATE
].copy()


# ============================================================
# 6. SIGNAL CREATION
# ============================================================

def create_signals(
    data,
    z_window,
    z_threshold,
):

    z_column = (
        f"z_{z_window}"
    )


    oversold = (

        data[z_column]

        < z_threshold
    )


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

        data[
            "qqq_above_ma50"
        ]
    )


    return signals


# ============================================================
# 7. TEST ONE COMBINATION
# ============================================================

def test_combination(
    data,
    z_window,
    z_threshold,
    hold_days,
):

    signals = create_signals(

        data=data,

        z_window=z_window,

        z_threshold=z_threshold,
    )


    signal_dates = (
        data.index[
            signals
        ]
    )


    trades = []


    for signal_date in signal_dates:

        signal_pos = (

            data.index.get_loc(
                signal_date
            )
        )


        entry_pos = (
            signal_pos + 1
        )


        exit_pos = (

            entry_pos

            + hold_days

            - 1
        )


        if exit_pos >= len(data):

            continue


        raw_entry = (

            data.iloc[
                entry_pos
            ]["Open"]
        )


        raw_exit = (

            data.iloc[
                exit_pos
            ]["Close"]
        )


        entry_price = (

            raw_entry

            * (
                1 + SLIPPAGE
            )
        )


        exit_price = (

            raw_exit

            * (
                1 - SLIPPAGE
            )
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
                data.index[
                    entry_pos
                ],

            "exit_date":
                data.index[
                    exit_pos
                ],

            "signal_z":
                data.loc[
                    signal_date,
                    f"z_{z_window}",
                ],

            "return":
                trade_return,
        })


    return pd.DataFrame(
        trades
    )


# ============================================================
# 8. FULL LOCAL ROBUSTNESS GRID
# ============================================================

summary_rows = []

all_trades = []


total_tests = (

    len(Z_WINDOWS)

    * len(Z_THRESHOLDS)

    * len(HOLD_DAYS_LIST)
)


test_number = 0


for window in Z_WINDOWS:

    for threshold in Z_THRESHOLDS:

        for hold_days in HOLD_DAYS_LIST:

            test_number += 1


            print(

                f"Test "
                f"{test_number}/"
                f"{total_tests}: "

                f"window={window}, "

                f"threshold="
                f"{threshold}, "

                f"hold="
                f"{hold_days}"
            )


            trades = test_combination(

                data=soxl,

                z_window=window,

                z_threshold=threshold,

                hold_days=hold_days,
            )


            # Ignore combinations with
            # almost no observations

            if len(trades) < MIN_SIGNALS:

                continue


            returns = (
                trades["return"]
            )


            all_trades.append(
                trades
            )


            summary_rows.append({

                "z_window":
                    window,

                "z_threshold":
                    threshold,

                "hold_days":
                    hold_days,

                "trades":
                    len(trades),

                "avg_return":
                    returns.mean(),

                "median_return":
                    returns.median(),

                "win_rate":
                    (
                        returns > 0
                    ).mean(),

                "return_std":
                    returns.std(),

                "best_trade":
                    returns.max(),

                "worst_trade":
                    returns.min(),

                "positive_years":
                    None,

                "quality_score":

                    (
                        returns.mean()

                        / returns.std()
                    )

                    * np.sqrt(
                        len(returns)
                    )

                    if returns.std() > 0

                    else np.nan,
            })


summary = pd.DataFrame(
    summary_rows
)


trades_output = pd.concat(

    all_trades,

    ignore_index=True,
)


# ============================================================
# 9. YEARLY STABILITY
# ============================================================

trades_output["year"] = (

    pd.to_datetime(

        trades_output[
            "signal_date"
        ]
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
            "return",
            lambda x:
                (x > 0).mean(),
        ),
    )

    .reset_index()
)


# ============================================================
# 10. ADD POSITIVE YEAR COUNT
# ============================================================

positive_year_counts = (

    yearly

    .groupby(
        [
            "z_window",
            "z_threshold",
            "hold_days",
        ]
    )

    .agg(

        years_tested=(
            "year",
            "count",
        ),

        positive_years=(
            "avg_return",
            lambda x:
                (x > 0).sum(),
        ),
    )

    .reset_index()
)


summary = summary.drop(
    columns=[
        "positive_years"
    ]
)


summary = summary.merge(

    positive_year_counts,

    on=[
        "z_window",
        "z_threshold",
        "hold_days",
    ],

    how="left",
)


# ============================================================
# 11. WINDOW / HOLD ROBUSTNESS
#
# Average across thresholds.
# ============================================================

window_hold_robustness = (

    summary

    .groupby(
        [
            "z_window",
            "hold_days",
        ]
    )

    .agg(

        threshold_tests=(
            "z_threshold",
            "count",
        ),

        avg_trades=(
            "trades",
            "mean",
        ),

        avg_return_across_thresholds=(
            "avg_return",
            "mean",
        ),

        median_return_across_thresholds=(
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

        avg_positive_year_ratio=(
            "positive_years",
            lambda x:

                (
                    x
                    /
                    summary.loc[
                        x.index,
                        "years_tested"
                    ]
                ).mean()
        ),
    )

    .reset_index()

    .sort_values(

        "avg_quality_score",

        ascending=False,
    )
)


# ============================================================
# 12. POST-ENTRY RETURN PATH
#
# Use our current fast candidate:
#
# 5-day z < -1.50
# QQQ > MA50
#
# Measure cumulative return from next open
# through each later close.
# ============================================================

PATH_WINDOW = 5

PATH_THRESHOLD = -1.50

PATH_MAX_DAY = 10


path_signals = create_signals(

    data=soxl,

    z_window=PATH_WINDOW,

    z_threshold=PATH_THRESHOLD,
)


path_signal_dates = (

    soxl.index[
        path_signals
    ]
)


path_rows = []


for signal_date in path_signal_dates:

    signal_pos = (

        soxl.index.get_loc(
            signal_date
        )
    )


    entry_pos = (
        signal_pos + 1
    )


    if entry_pos >= len(soxl):

        continue


    raw_entry = (

        soxl.iloc[
            entry_pos
        ]["Open"]
    )


    entry_price = (

        raw_entry

        * (
            1 + SLIPPAGE
        )
    )


    for day_number in range(
        1,
        PATH_MAX_DAY + 1,
    ):

        exit_pos = (

            entry_pos

            + day_number

            - 1
        )


        if exit_pos >= len(soxl):

            continue


        exit_price = (

            soxl.iloc[
                exit_pos
            ]["Close"]

            * (
                1 - SLIPPAGE
            )
        )


        cumulative_return = (

            exit_price

            / entry_price

        ) - 1


        path_rows.append({

            "signal_date":
                signal_date,

            "entry_date":
                soxl.index[
                    entry_pos
                ],

            "day":
                day_number,

            "cumulative_return":
                cumulative_return,
        })


path_trades = pd.DataFrame(
    path_rows
)


# ============================================================
# 13. SUMMARIZE RETURN PATH
# ============================================================

path_summary = (

    path_trades

    .groupby("day")

    .agg(

        observations=(
            "cumulative_return",
            "count",
        ),

        avg_cumulative_return=(
            "cumulative_return",
            "mean",
        ),

        median_cumulative_return=(
            "cumulative_return",
            "median",
        ),

        win_rate=(
            "cumulative_return",
            lambda x:
                (x > 0).mean(),
        ),

        p25_return=(
            "cumulative_return",
            lambda x:
                x.quantile(0.25),
        ),

        p75_return=(
            "cumulative_return",
            lambda x:
                x.quantile(0.75),
        ),

        worst_return=(
            "cumulative_return",
            "min",
        ),

        best_return=(
            "cumulative_return",
            "max",
        ),
    )

    .reset_index()
)


# ============================================================
# 14. MARGINAL DAILY CONTRIBUTION
#
# Difference between average cumulative
# return on consecutive days.
#
# Helps answer:
# when are gains actually accumulating?
# ============================================================

path_summary[
    "avg_incremental_gain"
] = (

    path_summary[
        "avg_cumulative_return"
    ]

    .diff()
)


path_summary.loc[

    path_summary.index[0],

    "avg_incremental_gain"

] = (

    path_summary.loc[
        path_summary.index[0],
        "avg_cumulative_return"
    ]
)


# ============================================================
# 15. SAVE FILES
# ============================================================

summary.to_csv(

    DATA_DIR
    / "fast_local_robustness_summary.csv",

    index=False,
)


window_hold_robustness.to_csv(

    DATA_DIR
    / "fast_window_hold_robustness.csv",

    index=False,
)


yearly.to_csv(

    DATA_DIR
    / "fast_local_yearly.csv",

    index=False,
)


path_summary.to_csv(

    DATA_DIR
    / "fast_return_path_summary.csv",

    index=False,
)


path_trades.to_csv(

    DATA_DIR
    / "fast_return_path_events.csv",

    index=False,
)


# ============================================================
# 16. PRINT TOP ROBUSTNESS RESULTS
# ============================================================

print()

print("=" * 120)

print(
    "TOP WINDOW / HOLD ROBUSTNESS"
)

print("=" * 120)

print()


print(

    window_hold_robustness

    .head(25)

    .to_string(

        index=False,

        formatters={

            "avg_return_across_thresholds":
                "{:.2%}".format,

            "median_return_across_thresholds":
                "{:.2%}".format,

            "avg_win_rate":
                "{:.2%}".format,

            "avg_quality_score":
                "{:.3f}".format,

            "avg_positive_year_ratio":
                "{:.2%}".format,
        },
    )
)


# ============================================================
# 17. PRINT RETURN PATH
# ============================================================

print()

print("=" * 120)

print(
    "5D Z < -1.50 POST-ENTRY RETURN PATH"
)

print("=" * 120)

print()


print(

    path_summary

    .to_string(

        index=False,

        formatters={

            "avg_cumulative_return":
                "{:.2%}".format,

            "median_cumulative_return":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,

            "p25_return":
                "{:.2%}".format,

            "p75_return":
                "{:.2%}".format,

            "worst_return":
                "{:.2%}".format,

            "best_return":
                "{:.2%}".format,

            "avg_incremental_gain":
                "{:.2%}".format,
        },
    )
)


# ============================================================
# 18. FINAL MESSAGE
# ============================================================

print()

print("Files saved:")

print(
    "data/fast_local_robustness_summary.csv"
)

print(
    "data/fast_window_hold_robustness.csv"
)

print(
    "data/fast_local_yearly.csv"
)

print(
    "data/fast_return_path_summary.csv"
)

print(
    "data/fast_return_path_events.csv"
)