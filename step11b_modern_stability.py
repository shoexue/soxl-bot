import pandas as pd


# ============================================================
# 1. SETTINGS — KEEP THESE FIXED
# ============================================================

STARTING_CAPITAL = 10_000

SIGNAL_THRESHOLD = -1.75

QQQ_MA_WINDOW = 50

STOP_LOSS = -0.12
PROFIT_TARGET = 0.20
MAX_HOLD = 5

SLIPPAGE = 0.001


# ============================================================
# 2. MODERN ERA PERIODS
# ============================================================

TEST_PERIODS = {

    "2021-2022": {
        "start": "2021-01-01",
        "end": "2022-12-31",
    },

    "2023-2024": {
        "start": "2023-01-01",
        "end": "2024-12-31",
    },

    "2025-2026": {
        "start": "2025-01-01",
        "end": None,
    },

    "Full Modern Era": {
        "start": "2021-01-01",
        "end": None,
    },
}


# ============================================================
# 3. LOAD DATA
# ============================================================

soxl_raw = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date",
)


qqq_raw = pd.read_csv(
    "data/QQQ.csv",
    parse_dates=["Date"],
    index_col="Date",
)


print()

print(
    f"SOXL data: "
    f"{soxl_raw.index.min()} → "
    f"{soxl_raw.index.max()}"
)

print(
    f"QQQ data: "
    f"{qqq_raw.index.min()} → "
    f"{qqq_raw.index.max()}"
)


# ============================================================
# 4. CALCULATE QQQ 50-DAY TREND
#
# IMPORTANT:
# Calculate before slicing periods so the beginning of each
# period already has moving-average history.
# ============================================================

qqq_raw["ma_50"] = (
    qqq_raw["Close"]
    .rolling(QQQ_MA_WINDOW)
    .mean()
)


qqq_raw["trend_50"] = (

    qqq_raw["Close"]

    / qqq_raw["ma_50"]

) - 1


# ============================================================
# 5. MAX DRAWDOWN FUNCTION
# ============================================================

def calculate_max_drawdown(equity):

    running_peak = equity.cummax()

    drawdown = (
        equity / running_peak
    ) - 1

    return drawdown.min()


# ============================================================
# 6. BACKTEST FUNCTION
# ============================================================

def run_backtest(
    data,
    signals,
):

    capital = STARTING_CAPITAL

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        signal_date = data.index[i]


        # Record cash equity while not invested

        equity_records.append({

            "Date":
                signal_date,

            "Equity":
                capital,
        })


        # ----------------------------------------------------
        # NO SIGNAL
        # ----------------------------------------------------

        if not signals.iloc[i]:

            i += 1

            continue


        # ----------------------------------------------------
        # ENTER NEXT TRADING DAY
        # ----------------------------------------------------

        entry_pos = i + 1


        if entry_pos >= len(data):

            break


        entry_date = data.index[
            entry_pos
        ]


        raw_entry_price = data.iloc[
            entry_pos
        ]["Open"]


        entry_price = (

            raw_entry_price

            * (1 + SLIPPAGE)
        )


        # ----------------------------------------------------
        # STOP AND TARGET LEVELS
        # ----------------------------------------------------

        stop_price = (

            entry_price

            * (1 + STOP_LOSS)
        )


        target_price = (

            entry_price

            * (1 + PROFIT_TARGET)
        )


        capital_before = capital


        shares = (

            capital

            / entry_price
        )


        exit_price = None
        exit_pos = None
        exit_reason = None


        # ====================================================
        # CHECK EACH HOLDING DAY
        # ====================================================

        for hold_index in range(
            MAX_HOLD
        ):

            day_pos = (

                entry_pos

                + hold_index
            )


            if day_pos >= len(data):

                break


            day = data.iloc[
                day_pos
            ]


            hit_stop = (

                day["Low"]

                <= stop_price
            )


            hit_target = (

                day["High"]

                >= target_price
            )


            # ------------------------------------------------
            # BOTH HIT ON SAME DAILY CANDLE
            #
            # Conservative assumption:
            # stop happened first.
            # ------------------------------------------------

            if hit_stop and hit_target:

                exit_price = (

                    stop_price

                    * (1 - SLIPPAGE)
                )


                exit_pos = day_pos

                exit_reason = (
                    "stop_both_hit"
                )

                break


            # ------------------------------------------------
            # STOP HIT
            # ------------------------------------------------

            elif hit_stop:

                exit_price = (

                    stop_price

                    * (1 - SLIPPAGE)
                )


                exit_pos = day_pos

                exit_reason = "stop"

                break


            # ------------------------------------------------
            # TARGET HIT
            # ------------------------------------------------

            elif hit_target:

                exit_price = (

                    target_price

                    * (1 - SLIPPAGE)
                )


                exit_pos = day_pos

                exit_reason = "target"

                break


        # ====================================================
        # TIME EXIT
        # ====================================================

        if exit_price is None:

            exit_pos = min(

                entry_pos
                + MAX_HOLD
                - 1,

                len(data)
                - 1,
            )


            raw_exit_price = data.iloc[
                exit_pos
            ]["Close"]


            exit_price = (

                raw_exit_price

                * (1 - SLIPPAGE)
            )


            exit_reason = "time_exit"


        exit_date = data.index[
            exit_pos
        ]


        # ====================================================
        # RECORD EQUITY DURING TRADE
        # ====================================================

        for j in range(
            entry_pos,
            exit_pos + 1,
        ):

            current_date = data.index[j]


            if j == exit_pos:

                current_equity = (

                    shares

                    * exit_price
                )


            else:

                current_equity = (

                    shares

                    * data.iloc[j]["Close"]
                )


            equity_records.append({

                "Date":
                    current_date,

                "Equity":
                    current_equity,
            })


        # ====================================================
        # CALCULATE TRADE RETURN
        # ====================================================

        trade_return = (

            exit_price

            / entry_price

        ) - 1


        capital = (

            capital

            * (1 + trade_return)
        )


        # ====================================================
        # SAVE TRADE
        # ====================================================

        trades.append({

            "signal_date":
                signal_date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

            "z_score":
                data.iloc[i]["z_score"],

            "qqq_trend":
                data.iloc[i]["qqq_trend"],

            "entry_price":
                entry_price,

            "exit_price":
                exit_price,

            "return":
                trade_return,

            "capital_before":
                capital_before,

            "capital_after":
                capital,

            "exit_reason":
                exit_reason,
        })


        # Prevent overlapping trades

        i = exit_pos + 1


    # ========================================================
    # BUILD DATAFRAMES
    # ========================================================

    trades_df = pd.DataFrame(
        trades
    )


    equity_df = (

        pd.DataFrame(
            equity_records
        )

        .drop_duplicates(
            subset="Date",
            keep="last",
        )

        .set_index("Date")

        .sort_index()

        .reindex(
            data.index
        )

        .ffill()
    )


    return (
        capital,
        trades_df,
        equity_df,
    )


# ============================================================
# 7. RUN EACH MODERN PERIOD
# ============================================================

summary_rows = []

all_trades = []

all_equity = {}


for period_name, dates in TEST_PERIODS.items():

    start_date = dates["start"]

    end_date = dates["end"]


    # --------------------------------------------------------
    # SLICE SOXL PERIOD
    # --------------------------------------------------------

    if end_date is None:

        soxl = soxl_raw[
            soxl_raw.index >= start_date
        ].copy()


    else:

        soxl = soxl_raw[

            (
                soxl_raw.index
                >= start_date
            )

            &

            (
                soxl_raw.index
                <= end_date
            )

        ].copy()


    # --------------------------------------------------------
    # ATTACH QQQ TREND
    # --------------------------------------------------------

    soxl["qqq_trend"] = (

        qqq_raw["trend_50"]

        .reindex(
            soxl.index
        )
    )


    # ========================================================
    # CREATE ORIGINAL SOXL EPISODES
    # ========================================================

    oversold = (

        soxl["z_score"]

        < SIGNAL_THRESHOLD
    )


    base_episode_start = (

        oversold

        &

        ~oversold.shift(
            1,
            fill_value=False,
        )
    )


    # ========================================================
    # APPLY QQQ FILTER AT ORIGINAL EPISODE START
    # ========================================================

    signals = (

        base_episode_start

        &

        (
            soxl["qqq_trend"]
            > 0
        )
    )


    # ========================================================
    # RUN BACKTEST
    # ========================================================

    (
        final_capital,
        trades,
        equity,

    ) = run_backtest(

        data=soxl,

        signals=signals,
    )


    # ========================================================
    # METRICS
    # ========================================================

    if len(trades) > 0:

        win_rate = (

            trades["return"]

            > 0

        ).mean()


        avg_trade = (

            trades["return"]

            .mean()
        )


        median_trade = (

            trades["return"]

            .median()
        )


        best_trade = (

            trades["return"]

            .max()
        )


        worst_trade = (

            trades["return"]

            .min()
        )


    else:

        win_rate = 0

        avg_trade = 0

        median_trade = 0

        best_trade = 0

        worst_trade = 0


    # ========================================================
    # SUMMARY
    # ========================================================

    summary_rows.append({

        "period":
            period_name,

        "start_date":
            soxl.index.min(),

        "end_date":
            soxl.index.max(),

        "accepted_signals":
            int(signals.sum()),

        "executed_trades":
            len(trades),

        "final_capital":
            final_capital,

        "total_return":
            (
                final_capital
                / STARTING_CAPITAL
            ) - 1,

        "max_drawdown":
            calculate_max_drawdown(
                equity["Equity"]
            ),

        "win_rate":
            win_rate,

        "avg_trade":
            avg_trade,

        "median_trade":
            median_trade,

        "best_trade":
            best_trade,

        "worst_trade":
            worst_trade,
    })


    # ========================================================
    # SAVE TRADE DETAILS
    # ========================================================

    if len(trades) > 0:

        trades = trades.copy()

        trades["period"] = (
            period_name
        )

        all_trades.append(
            trades
        )


    all_equity[
        period_name
    ] = equity["Equity"]


# ============================================================
# 8. BUILD OUTPUT TABLES
# ============================================================

summary = pd.DataFrame(
    summary_rows
)


if all_trades:

    trades_output = pd.concat(
        all_trades,
        ignore_index=True,
    )

else:

    trades_output = pd.DataFrame()


# ============================================================
# 9. YEAR-BY-YEAR ANALYSIS
# ============================================================

full_modern_trades = trades_output[

    trades_output["period"]

    == "Full Modern Era"

].copy()


if len(full_modern_trades) > 0:

    full_modern_trades[
        "year"
    ] = (

        pd.to_datetime(
            full_modern_trades[
                "signal_date"
            ]
        )

        .dt.year
    )


    yearly_summary = (

        full_modern_trades

        .groupby("year")

        .agg(

            trades=(
                "return",
                "count",
            ),

            avg_trade=(
                "return",
                "mean",
            ),

            median_trade=(
                "return",
                "median",
            ),

            win_rate=(
                "return",
                lambda x:
                    (x > 0).mean(),
            ),

            compounded_return=(
                "return",
                lambda x:
                    (1 + x).prod() - 1,
            ),
        )

        .reset_index()
    )


else:

    yearly_summary = pd.DataFrame()


# ============================================================
# 10. SAVE FILES
# ============================================================

summary.to_csv(
    "data/modern_stability_summary.csv",
    index=False,
)


trades_output.to_csv(
    "data/modern_stability_trades.csv",
    index=False,
)


yearly_summary.to_csv(
    "data/modern_yearly_summary.csv",
    index=False,
)


# ============================================================
# 11. PRINT RESULTS
# ============================================================

print()

print("=" * 100)

print(
    "MODERN ERA STABILITY TEST"
)

print("=" * 100)

print()


print(
    summary.to_string(

        index=False,

        formatters={

            "final_capital":
                "${:,.2f}".format,

            "total_return":
                "{:.2%}".format,

            "max_drawdown":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,

            "avg_trade":
                "{:.2%}".format,

            "median_trade":
                "{:.2%}".format,

            "best_trade":
                "{:.2%}".format,

            "worst_trade":
                "{:.2%}".format,
        }
    )
)


print()

print("=" * 100)

print(
    "YEAR-BY-YEAR RESULTS"
)

print("=" * 100)

print()


if len(yearly_summary) > 0:

    print(

        yearly_summary.to_string(

            index=False,

            formatters={

                "avg_trade":
                    "{:.2%}".format,

                "median_trade":
                    "{:.2%}".format,

                "win_rate":
                    "{:.2%}".format,

                "compounded_return":
                    "{:.2%}".format,
            }
        )
    )


print()

print("Files saved:")

print(
    "data/modern_stability_summary.csv"
)

print(
    "data/modern_stability_trades.csv"
)

print(
    "data/modern_yearly_summary.csv"
)