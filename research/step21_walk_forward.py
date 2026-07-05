import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# 1. SETTINGS
# ============================================================

DOWNLOAD_START = "2020-01-01"
RESEARCH_START = "2021-01-01"

QQQ_MA_WINDOW = 50

SLIPPAGE = 0.001

MIN_TRAIN_TRADES = 8


Z_WINDOWS = [
    4,
    5,
    6,
    7,
    8,
]


Z_THRESHOLDS = [
    -1.10,
    -1.20,
    -1.30,
    -1.40,
    -1.50,
    -1.60,
    -1.70,
    -1.80,
]


HOLD_DAYS_LIST = [
    3,
    4,
    5,
]


TEST_YEARS = [
    2023,
    2024,
    2025,
    2026,
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

    soxl[f"z_{window}"] = (
        (
            soxl["Close"]
            - rolling_mean
        )
        / rolling_std
    )


soxl = soxl[
    soxl.index >= RESEARCH_START
].copy()


# ============================================================
# 5. CREATE SIGNALS
# ============================================================

def create_signals(
    data,
    z_window,
    z_threshold,
):

    z_column = f"z_{z_window}"


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
        data["qqq_above_ma50"]
    )


    return signals


# ============================================================
# 6. GENERATE TRADES
#
# Important:
# signal is calculated from the full chronological series,
# but trades are filtered by SIGNAL DATE afterward.
#
# This preserves rolling-window context at year boundaries.
# ============================================================

def generate_trades(
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
        data.index[signals]
    )


    trades = []


    for signal_date in signal_dates:

        signal_pos = (
            data.index.get_loc(
                signal_date
            )
        )


        entry_pos = signal_pos + 1


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
            * (1 + SLIPPAGE)
        )


        exit_price = (
            raw_exit
            * (1 - SLIPPAGE)
        )


        trade_return = (
            exit_price
            / entry_price
        ) - 1


        trades.append({

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

            "z_window":
                z_window,

            "z_threshold":
                z_threshold,

            "hold_days":
                hold_days,

            "signal_z":
                data.loc[
                    signal_date,
                    f"z_{z_window}",
                ],

            "return":
                trade_return,
        })


    return pd.DataFrame(trades)


# ============================================================
# 7. SCORE TRAINING PERFORMANCE
#
# We do NOT simply pick highest average return.
#
# Score rewards:
# - positive average return
# - consistency
# - more observations
#
# Then applies a penalty if only a small fraction
# of training years were positive.
# ============================================================

def score_training_trades(
    trades,
):

    if len(trades) < MIN_TRAIN_TRADES:

        return None


    returns = trades["return"]


    return_std = returns.std()


    if (
        pd.isna(return_std)
        or return_std == 0
    ):
        return None


    base_quality = (
        returns.mean()
        / return_std
        * np.sqrt(len(returns))
    )


    temp = trades.copy()


    temp["year"] = (
        pd.to_datetime(
            temp["signal_date"]
        )
        .dt.year
    )


    yearly_avg = (
        temp
        .groupby("year")["return"]
        .mean()
    )


    positive_year_ratio = (
        yearly_avg > 0
    ).mean()


    # Penalize parameters that only worked
    # in a small part of training history.

    stability_multiplier = (
        0.5
        + 0.5
        * positive_year_ratio
    )


    score = (
        base_quality
        * stability_multiplier
    )


    return {

        "score":
            score,

        "trades":
            len(trades),

        "avg_return":
            returns.mean(),

        "median_return":
            returns.median(),

        "win_rate":
            (returns > 0).mean(),

        "return_std":
            return_std,

        "positive_year_ratio":
            positive_year_ratio,
    }


# ============================================================
# 8. PRECOMPUTE ALL PARAMETER TRADES
# ============================================================

parameter_trade_map = {}


total_combinations = (
    len(Z_WINDOWS)
    * len(Z_THRESHOLDS)
    * len(HOLD_DAYS_LIST)
)


counter = 0


for window in Z_WINDOWS:

    for threshold in Z_THRESHOLDS:

        for hold_days in HOLD_DAYS_LIST:

            counter += 1


            print(
                f"Building {counter}/"
                f"{total_combinations}: "
                f"W={window}, "
                f"Z={threshold}, "
                f"H={hold_days}"
            )


            key = (
                window,
                threshold,
                hold_days,
            )


            parameter_trade_map[key] = (
                generate_trades(
                    data=soxl,
                    z_window=window,
                    z_threshold=threshold,
                    hold_days=hold_days,
                )
            )


# ============================================================
# 9. WALK-FORWARD LOOP
# ============================================================

selection_rows = []

test_trade_frames = []

fold_summary_rows = []


for test_year in TEST_YEARS:

    print()

    print("=" * 100)

    print(
        f"WALK-FORWARD FOLD: "
        f"TEST YEAR {test_year}"
    )

    print("=" * 100)


    train_end = test_year - 1


    candidate_rows = []


    # --------------------------------------------------------
    # TRAINING SEARCH
    # --------------------------------------------------------

    for key, all_trades in (
        parameter_trade_map.items()
    ):

        window, threshold, hold_days = key


        if len(all_trades) == 0:
            continue


        trade_years = (
            pd.to_datetime(
                all_trades["signal_date"]
            )
            .dt.year
        )


        train_trades = all_trades[
            trade_years < test_year
        ].copy()


        score_result = (
            score_training_trades(
                train_trades
            )
        )


        if score_result is None:
            continue


        candidate_rows.append({

            "test_year":
                test_year,

            "train_end_year":
                train_end,

            "z_window":
                window,

            "z_threshold":
                threshold,

            "hold_days":
                hold_days,

            "train_score":
                score_result[
                    "score"
                ],

            "train_trades":
                score_result[
                    "trades"
                ],

            "train_avg_return":
                score_result[
                    "avg_return"
                ],

            "train_median_return":
                score_result[
                    "median_return"
                ],

            "train_win_rate":
                score_result[
                    "win_rate"
                ],

            "train_return_std":
                score_result[
                    "return_std"
                ],

            "train_positive_year_ratio":
                score_result[
                    "positive_year_ratio"
                ],
        })


    candidates = pd.DataFrame(
        candidate_rows
    )


    if len(candidates) == 0:

        print(
            "No eligible candidates."
        )

        continue


    candidates = (
        candidates
        .sort_values(
            "train_score",
            ascending=False,
        )
        .reset_index(drop=True)
    )


    best = candidates.iloc[0]


    selected_window = int(
        best["z_window"]
    )

    selected_threshold = float(
        best["z_threshold"]
    )

    selected_hold = int(
        best["hold_days"]
    )


    print()

    print("SELECTED FROM TRAINING ONLY:")

    print(
        f"Window: {selected_window}"
    )

    print(
        f"Threshold: "
        f"{selected_threshold}"
    )

    print(
        f"Hold: {selected_hold}"
    )

    print(
        f"Training trades: "
        f"{int(best['train_trades'])}"
    )

    print(
        f"Training avg return: "
        f"{best['train_avg_return']:.2%}"
    )

    print(
        f"Training score: "
        f"{best['train_score']:.3f}"
    )


    # --------------------------------------------------------
    # SAVE SELECTION
    # --------------------------------------------------------

    selection_rows.append(
        best.to_dict()
    )


    # --------------------------------------------------------
    # UNSEEN TEST YEAR
    # --------------------------------------------------------

    key = (
        selected_window,
        selected_threshold,
        selected_hold,
    )


    selected_all_trades = (
        parameter_trade_map[key]
    )


    selected_years = (
        pd.to_datetime(
            selected_all_trades[
                "signal_date"
            ]
        )
        .dt.year
    )


    test_trades = (
        selected_all_trades[
            selected_years
            == test_year
        ]
        .copy()
    )


    test_trades[
        "walk_forward_test_year"
    ] = test_year


    test_trades[
        "selected_window"
    ] = selected_window


    test_trades[
        "selected_threshold"
    ] = selected_threshold


    test_trades[
        "selected_hold"
    ] = selected_hold


    if len(test_trades) > 0:

        test_trade_frames.append(
            test_trades
        )


        test_returns = (
            test_trades["return"]
        )


        fold_summary_rows.append({

            "test_year":
                test_year,

            "selected_window":
                selected_window,

            "selected_threshold":
                selected_threshold,

            "selected_hold":
                selected_hold,

            "test_trades":
                len(test_trades),

            "test_avg_return":
                test_returns.mean(),

            "test_median_return":
                test_returns.median(),

            "test_win_rate":
                (
                    test_returns > 0
                ).mean(),

            "test_compounded_return":
                (
                    1 + test_returns
                ).prod() - 1,

            "test_best_trade":
                test_returns.max(),

            "test_worst_trade":
                test_returns.min(),
        })


    else:

        fold_summary_rows.append({

            "test_year":
                test_year,

            "selected_window":
                selected_window,

            "selected_threshold":
                selected_threshold,

            "selected_hold":
                selected_hold,

            "test_trades":
                0,

            "test_avg_return":
                np.nan,

            "test_median_return":
                np.nan,

            "test_win_rate":
                np.nan,

            "test_compounded_return":
                0.0,

            "test_best_trade":
                np.nan,

            "test_worst_trade":
                np.nan,
        })


# ============================================================
# 10. BUILD OUTPUTS
# ============================================================

selections = pd.DataFrame(
    selection_rows
)


fold_summary = pd.DataFrame(
    fold_summary_rows
)


if len(test_trade_frames) > 0:

    walk_forward_trades = pd.concat(
        test_trade_frames,
        ignore_index=True,
    )

else:

    walk_forward_trades = pd.DataFrame()


# ============================================================
# 11. COMBINED OUT-OF-SAMPLE SUMMARY
# ============================================================

if len(walk_forward_trades) > 0:

    oos_returns = (
        walk_forward_trades["return"]
    )


    overall_summary = pd.DataFrame(
        [
            {

                "oos_trades":
                    len(oos_returns),

                "oos_avg_return":
                    oos_returns.mean(),

                "oos_median_return":
                    oos_returns.median(),

                "oos_win_rate":
                    (
                        oos_returns > 0
                    ).mean(),

                "oos_compounded_trade_return":
                    (
                        1 + oos_returns
                    ).prod() - 1,

                "oos_best_trade":
                    oos_returns.max(),

                "oos_worst_trade":
                    oos_returns.min(),

                "positive_test_years":
                    (
                        fold_summary[
                            "test_avg_return"
                        ] > 0
                    ).sum(),

                "test_years_with_trades":
                    (
                        fold_summary[
                            "test_trades"
                        ] > 0
                    ).sum(),
            }
        ]
    )


else:

    overall_summary = pd.DataFrame()


# ============================================================
# 12. SAVE FILES
# ============================================================

selections.to_csv(
    DATA_DIR
    / "walk_forward_selections.csv",
    index=False,
)


fold_summary.to_csv(
    DATA_DIR
    / "walk_forward_fold_summary.csv",
    index=False,
)


walk_forward_trades.to_csv(
    DATA_DIR
    / "walk_forward_trades.csv",
    index=False,
)


overall_summary.to_csv(
    DATA_DIR
    / "walk_forward_overall.csv",
    index=False,
)


# ============================================================
# 13. PRINT SELECTIONS
# ============================================================

print()

print("=" * 120)

print("PARAMETERS SELECTED USING PAST DATA ONLY")

print("=" * 120)

print()


print(
    selections[
        [
            "test_year",
            "z_window",
            "z_threshold",
            "hold_days",
            "train_trades",
            "train_avg_return",
            "train_win_rate",
            "train_positive_year_ratio",
            "train_score",
        ]
    ]
    .to_string(

        index=False,

        formatters={

            "train_avg_return":
                "{:.2%}".format,

            "train_win_rate":
                "{:.2%}".format,

            "train_positive_year_ratio":
                "{:.2%}".format,

            "train_score":
                "{:.3f}".format,
        },
    )
)


# ============================================================
# 14. PRINT TEST RESULTS
# ============================================================

print()

print("=" * 120)

print("UNSEEN YEAR RESULTS")

print("=" * 120)

print()


print(
    fold_summary.to_string(

        index=False,

        formatters={

            "test_avg_return":
                "{:.2%}".format,

            "test_median_return":
                "{:.2%}".format,

            "test_win_rate":
                "{:.2%}".format,

            "test_compounded_return":
                "{:.2%}".format,

            "test_best_trade":
                "{:.2%}".format,

            "test_worst_trade":
                "{:.2%}".format,
        },
    )
)


# ============================================================
# 15. PRINT OVERALL OOS RESULT
# ============================================================

print()

print("=" * 120)

print("COMBINED OUT-OF-SAMPLE RESULTS")

print("=" * 120)

print()


if len(overall_summary) > 0:

    print(
        overall_summary.to_string(

            index=False,

            formatters={

                "oos_avg_return":
                    "{:.2%}".format,

                "oos_median_return":
                    "{:.2%}".format,

                "oos_win_rate":
                    "{:.2%}".format,

                "oos_compounded_trade_return":
                    "{:.2%}".format,

                "oos_best_trade":
                    "{:.2%}".format,

                "oos_worst_trade":
                    "{:.2%}".format,
            },
        )
    )


print()

print("Files saved:")

print(
    "data/walk_forward_selections.csv"
)

print(
    "data/walk_forward_fold_summary.csv"
)

print(
    "data/walk_forward_trades.csv"
)

print(
    "data/walk_forward_overall.csv"
)