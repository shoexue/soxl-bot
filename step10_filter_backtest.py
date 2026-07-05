import pandas as pd


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-07-05"
STARTING_CAPITAL = 10_000

STOP_LOSS = -0.12
PROFIT_TARGET = 0.20
MAX_HOLD = 5

# 0.10% cost on entry and exit
SLIPPAGE = 0.001


# ============================================================
# 2. LOAD DATA
# ============================================================

soxl = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date"
)

qqq = pd.read_csv(
    "data/QQQ.csv",
    parse_dates=["Date"],
    index_col="Date"
)


# Keep recent research period

soxl = soxl[
    soxl.index >= START_DATE
].copy()

qqq = qqq[
    qqq.index >= START_DATE
].copy()


print()
print(
    f"Data from {soxl.index.min()} "
    f"to {soxl.index.max()}"
)

print(
    f"Trading days: {len(soxl)}"
)


# ============================================================
# 3. CREATE QQQ TREND
# ============================================================

qqq["ma_50"] = (
    qqq["Close"]
    .rolling(50)
    .mean()
)


qqq["trend"] = (
    qqq["Close"]
    / qqq["ma_50"]
) - 1


# Attach QQQ trend to SOXL dates

soxl["qqq_trend"] = (
    qqq["trend"]
    .reindex(soxl.index)
)


# ============================================================
# 4. CREATE ORIGINAL SOXL EPISODES FIRST
# ============================================================

# Base SOXL oversold condition

oversold = (
    soxl["z_score"] < -1.75
)


# Episode starts are determined ONLY by SOXL.
#
# Example:
#
# Day 1: z = -1.4   no signal
# Day 2: z = -1.8   EPISODE START
# Day 3: z = -2.1   same episode
# Day 4: z = -1.9   same episode
# Day 5: z = -1.3   episode ends
#
# Only Day 2 can create a trade.

base_episode_start = (
    oversold
    &
    ~oversold.shift(
        1,
        fill_value=False
    )
)


print(
    f"Original SOXL episodes: "
    f"{base_episode_start.sum()}"
)


# ============================================================
# 5. APPLY FILTERS ONLY AT ORIGINAL EPISODE START
# ============================================================

# ------------------------------------------------------------
# BASELINE
#
# Take every original SOXL oversold episode.
# ------------------------------------------------------------

baseline_signals = (
    base_episode_start
)


# ------------------------------------------------------------
# QQQ FILTER
#
# Only accept an original SOXL episode if QQQ is above
# its 50-day moving average ON THE ORIGINAL SIGNAL DATE.
# ------------------------------------------------------------

qqq_signals = (
    base_episode_start
    &
    (soxl["qqq_trend"] > 0)
)


# ------------------------------------------------------------
# Z-SCORE BAND
#
# Only accept original episodes whose starting z-score is:
#
#     -2.0 < z < -1.75
#
# This avoids the most extreme selloffs.
# ------------------------------------------------------------

z_band_signals = (
    base_episode_start
    &
    (soxl["z_score"] > -2.0)
)


# ------------------------------------------------------------
# COMBINED FILTER
#
# Original SOXL episode must:
#
# 1. Start between z = -2.0 and z = -1.75
# 2. Have QQQ above its 50-day MA
# ------------------------------------------------------------

combined_signals = (
    base_episode_start
    &
    (soxl["z_score"] > -2.0)
    &
    (soxl["qqq_trend"] > 0)
)


# Store all strategies

signal_sets = {

    "Baseline":
        baseline_signals,

    "QQQ Filter":
        qqq_signals,

    "Z Band":
        z_band_signals,

    "Combined":
        combined_signals,
}


# Print accepted signal counts

print()
print("Accepted signal episodes:")

for name, signals in signal_sets.items():

    print(
        f"{name}: {signals.sum()}"
    )


# ============================================================
# 6. BACKTEST FUNCTION
# ============================================================

def run_backtest(
    data,
    signal_series,
    strategy_name
):

    capital = STARTING_CAPITAL

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        current_date = data.index[i]


        # Record current cash value while not invested

        equity_records.append({

            "Date":
                current_date,

            "Equity":
                capital
        })


        # ----------------------------------------------------
        # NO SIGNAL
        # ----------------------------------------------------

        if not signal_series.iloc[i]:

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


        # Apply entry slippage

        entry_price = (
            raw_entry_price
            * (1 + SLIPPAGE)
        )


        # ----------------------------------------------------
        # CALCULATE EXIT LEVELS
        # ----------------------------------------------------

        stop_price = (
            entry_price
            * (1 + STOP_LOSS)
        )


        target_price = (
            entry_price
            * (1 + PROFIT_TARGET)
        )


        # Invest all available capital

        shares = (
            capital
            / entry_price
        )


        capital_before = capital


        exit_price = None
        exit_pos = None
        exit_reason = None


        # ====================================================
        # CHECK EXIT CONDITIONS DAY BY DAY
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
            # BOTH STOP AND TARGET HIT ON SAME DAILY CANDLE
            #
            # Since daily data cannot tell us which happened
            # first, use the conservative assumption:
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
            # PROFIT TARGET HIT
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

        # If neither stop nor target was hit,
        # exit at the Close of the final allowed day.

        if exit_price is None:

            exit_pos = min(

                entry_pos
                + MAX_HOLD
                - 1,

                len(data)
                - 1
            )


            raw_exit_price = data.iloc[
                exit_pos
            ]["Close"]


            exit_price = (
                raw_exit_price
                * (1 - SLIPPAGE)
            )


            exit_reason = "time_exit"


        # ----------------------------------------------------
        # EXIT DATE
        # ----------------------------------------------------

        exit_date = data.index[
            exit_pos
        ]


        # ====================================================
        # RECORD EQUITY DURING OPEN POSITION
        # ====================================================

        for j in range(
            entry_pos,
            exit_pos + 1
        ):

            date = data.index[j]


            # On the actual exit day, use actual exit price

            if j == exit_pos:

                current_equity = (
                    shares
                    * exit_price
                )


            # Otherwise mark position at daily Close

            else:

                current_equity = (
                    shares
                    * data.iloc[j]["Close"]
                )


            equity_records.append({

                "Date":
                    date,

                "Equity":
                    current_equity
            })


        # ====================================================
        # CALCULATE TRADE RETURN
        # ====================================================

        trade_return = (
            exit_price
            / entry_price
        ) - 1


        # Compound capital

        capital = (
            capital
            * (1 + trade_return)
        )


        # ====================================================
        # SAVE TRADE
        # ====================================================

        trades.append({

            "strategy":
                strategy_name,

            "signal_date":
                current_date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

            "z_score":
                data.iloc[i][
                    "z_score"
                ],

            "qqq_trend":
                data.iloc[i][
                    "qqq_trend"
                ],

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
                exit_reason
        })


        # ----------------------------------------------------
        # PREVENT OVERLAPPING POSITIONS
        #
        # Continue scanning from the day AFTER the exit.
        # ----------------------------------------------------

        i = exit_pos + 1


    # ========================================================
    # BUILD TRADE DATAFRAME
    # ========================================================

    trades_df = pd.DataFrame(
        trades
    )


    # ========================================================
    # BUILD EQUITY CURVE
    # ========================================================

    equity_df = pd.DataFrame(
        equity_records
    )


    equity_df = (

        equity_df

        .drop_duplicates(
            subset="Date",
            keep="last"
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
        equity_df
    )


# ============================================================
# 7. MAX DRAWDOWN FUNCTION
# ============================================================

def calculate_max_drawdown(
    equity
):

    running_peak = (
        equity.cummax()
    )


    drawdown = (
        equity
        / running_peak
    ) - 1


    return drawdown.min()


# ============================================================
# 8. RUN ALL FOUR STRATEGIES
# ============================================================

summary_rows = []

all_trades = []

equity_curves = pd.DataFrame(
    index=soxl.index
)


for strategy_name, signals in signal_sets.items():

    final_capital, trades, equity = (
        run_backtest(

            data=soxl,

            signal_series=signals,

            strategy_name=strategy_name
        )
    )


    max_drawdown = (
        calculate_max_drawdown(
            equity["Equity"]
        )
    )


    # --------------------------------------------------------
    # TRADE METRICS
    # --------------------------------------------------------

    if len(trades) > 0:

        win_rate = (
            trades["return"] > 0
        ).mean()


        avg_trade = (
            trades["return"]
        ).mean()


        median_trade = (
            trades["return"]
        ).median()


    else:

        win_rate = 0

        avg_trade = 0

        median_trade = 0


    # --------------------------------------------------------
    # SUMMARY ROW
    # --------------------------------------------------------

    summary_rows.append({

        "strategy":
            strategy_name,

        "starting_capital":
            STARTING_CAPITAL,

        "final_capital":
            final_capital,

        "total_return":
            (
                final_capital
                / STARTING_CAPITAL
            ) - 1,

        "max_drawdown":
            max_drawdown,

        "trades":
            len(trades),

        "win_rate":
            win_rate,

        "avg_trade":
            avg_trade,

        "median_trade":
            median_trade
    })


    # Save trade records

    all_trades.append(
        trades
    )


    # Save equity curve

    column_name = (

        strategy_name

        .lower()

        .replace(
            " ",
            "_"
        )
    )


    equity_curves[
        column_name
    ] = equity["Equity"]


# ============================================================
# 9. CREATE OUTPUT DATAFRAMES
# ============================================================

summary = pd.DataFrame(
    summary_rows
)


trades_output = pd.concat(
    all_trades,
    ignore_index=True
)


# ============================================================
# 10. SAVE RESULTS
# ============================================================

summary.to_csv(
    "data/filter_backtest_summary.csv",
    index=False
)


trades_output.to_csv(
    "data/filter_backtest_trades.csv",
    index=False
)


equity_curves.to_csv(
    "data/filter_equity_curves.csv"
)


# ============================================================
# 11. PRINT RESULTS
# ============================================================

print()
print("=" * 90)
print("CORRECTED FILTER BACKTEST RESULTS")
print("=" * 90)
print()


print(
    summary.to_string(

        index=False,

        formatters={

            "starting_capital":
                "${:,.2f}".format,

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
        }
    )
)


# ============================================================
# 12. PRINT SIGNAL COUNTS VS EXECUTED TRADES
# ============================================================

print()
print("=" * 90)
print("SIGNALS VS EXECUTED TRADES")
print("=" * 90)
print()


for strategy_name, signals in signal_sets.items():

    accepted_signals = int(
        signals.sum()
    )


    executed_trades = len(

        trades_output[
            trades_output[
                "strategy"
            ]
            == strategy_name
        ]
    )


    print(
        f"{strategy_name}: "
        f"{accepted_signals} accepted signals, "
        f"{executed_trades} executed trades"
    )


# ============================================================
# 13. PRINT EXIT REASONS BY STRATEGY
# ============================================================

print()
print("=" * 90)
print("EXIT REASONS BY STRATEGY")
print("=" * 90)
print()


exit_reason_table = pd.crosstab(

    trades_output[
        "strategy"
    ],

    trades_output[
        "exit_reason"
    ]
)


print(
    exit_reason_table
)


# ============================================================
# 14. FINAL MESSAGE
# ============================================================

print()
print("Files saved:")
print("data/filter_backtest_summary.csv")
print("data/filter_backtest_trades.csv")
print("data/filter_equity_curves.csv")