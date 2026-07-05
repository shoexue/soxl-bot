import pandas as pd


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-01-01"
STARTING_CAPITAL = 10_000

SIGNAL_THRESHOLD = -1.75

STOP_LOSS = -0.12
PROFIT_TARGET = 0.20
MAX_HOLD = 5

SLIPPAGE = 0.001


# ============================================================
# 2. LOAD DATA
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
print("=" * 100)
print("STEP 14 — SHORT-TERM QQQ FILTER TEST")
print("=" * 100)

print()
print(
    f"SOXL: {soxl_raw.index.min()} → "
    f"{soxl_raw.index.max()}"
)

print(
    f"QQQ: {qqq_raw.index.min()} → "
    f"{qqq_raw.index.max()}"
)


# ============================================================
# 3. BUILD QQQ FEATURES BEFORE SLICING
# ============================================================

qqq_raw["ma_20"] = (
    qqq_raw["Close"]
    .rolling(20)
    .mean()
)


qqq_raw["ma_50"] = (
    qqq_raw["Close"]
    .rolling(50)
    .mean()
)


qqq_raw["return_5d"] = (
    qqq_raw["Close"]
    .pct_change(5)
)


qqq_raw["above_ma20"] = (
    qqq_raw["Close"]
    > qqq_raw["ma_20"]
)


qqq_raw["above_ma50"] = (
    qqq_raw["Close"]
    > qqq_raw["ma_50"]
)


# ============================================================
# 4. PREPARE SOXL DATA
# ============================================================

soxl = soxl_raw[
    soxl_raw.index >= START_DATE
].copy()


soxl["qqq_above_ma20"] = (
    qqq_raw["above_ma20"]
    .reindex(soxl.index)
    .fillna(False)
    .astype(bool)
)


soxl["qqq_above_ma50"] = (
    qqq_raw["above_ma50"]
    .reindex(soxl.index)
    .fillna(False)
    .astype(bool)
)


soxl["qqq_return_5d"] = (
    qqq_raw["return_5d"]
    .reindex(soxl.index)
)


# ============================================================
# 5. CREATE ORIGINAL SOXL EPISODES
# ============================================================

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


print()
print(
    f"Original SOXL oversold episodes: "
    f"{base_episode_start.sum()}"
)


# ============================================================
# 6. DEFINE THE THREE STRATEGIES
# ============================================================

# ------------------------------------------------------------
# CURRENT STRATEGY
#
# SOXL oversold episode
# +
# QQQ above MA50
# ------------------------------------------------------------

current_signals = (
    base_episode_start
    &
    soxl["qqq_above_ma50"]
)


# ------------------------------------------------------------
# MA20 + MA50
#
# Current strategy
# +
# QQQ must also be above MA20
# ------------------------------------------------------------

ma20_ma50_signals = (
    base_episode_start
    &
    soxl["qqq_above_ma50"]
    &
    soxl["qqq_above_ma20"]
)


# ------------------------------------------------------------
# POSITIVE 5-DAY MOMENTUM
#
# Current strategy
# +
# QQQ 5-day return must be positive
# ------------------------------------------------------------

momentum_5d_signals = (
    base_episode_start
    &
    soxl["qqq_above_ma50"]
    &
    (
        soxl["qqq_return_5d"]
        > 0
    )
)


signal_sets = {

    "Current MA50":
        current_signals,

    "MA20 + MA50":
        ma20_ma50_signals,

    "MA50 + Positive 5D":
        momentum_5d_signals,
}


print()
print("Accepted signal counts:")

for name, signals in signal_sets.items():

    print(
        f"{name}: {int(signals.sum())}"
    )


# ============================================================
# 7. MAX DRAWDOWN
# ============================================================

def calculate_max_drawdown(
    equity,
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
# 8. BACKTEST FUNCTION
# ============================================================

def run_backtest(
    data,
    signals,
    strategy_name,
):

    capital = STARTING_CAPITAL

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        signal_date = data.index[i]


        # Record cash while not invested

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
        # EXIT LEVELS
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
        # CHECK EXIT CONDITIONS
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


            # Conservative assumption:
            # if both are touched in the same daily candle,
            # assume the stop happened first.

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


            elif hit_stop:

                exit_price = (
                    stop_price
                    * (1 - SLIPPAGE)
                )

                exit_pos = day_pos

                exit_reason = "stop"

                break


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
        # RECORD EQUITY DURING POSITION
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
        # UPDATE CAPITAL
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

            "strategy":
                strategy_name,

            "signal_date":
                signal_date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

            "z_score":
                data.iloc[i][
                    "z_score"
                ],

            "qqq_above_ma20":
                data.iloc[i][
                    "qqq_above_ma20"
                ],

            "qqq_above_ma50":
                data.iloc[i][
                    "qqq_above_ma50"
                ],

            "qqq_return_5d":
                data.iloc[i][
                    "qqq_return_5d"
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
                exit_reason,
        })


        # Prevent overlapping positions

        i = exit_pos + 1


    # ========================================================
    # BUILD OUTPUT DATAFRAMES
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
# 9. RUN ALL STRATEGIES
# ============================================================

summary_rows = []

all_trades = []

equity_curves = pd.DataFrame(
    index=soxl.index
)


for strategy_name, signals in signal_sets.items():

    (
        final_capital,
        trades,
        equity,

    ) = run_backtest(

        data=soxl,

        signals=signals,

        strategy_name=strategy_name,
    )


    if len(trades) > 0:

        win_rate = (
            trades["return"] > 0
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


    summary_rows.append({

        "strategy":
            strategy_name,

        "accepted_signals":
            int(signals.sum()),

        "executed_trades":
            len(trades),

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


    if len(trades) > 0:

        all_trades.append(
            trades
        )


    column_name = (

        strategy_name

        .lower()

        .replace(" ", "_")

        .replace("+", "plus")
    )


    equity_curves[
        column_name
    ] = equity["Equity"]


# ============================================================
# 10. BUILD OUTPUT TABLES
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
# 11. YEAR-BY-YEAR RESULTS
# ============================================================

yearly_rows = []


for strategy_name in signal_sets.keys():

    strategy_trades = trades_output[

        trades_output["strategy"]

        == strategy_name

    ].copy()


    if len(strategy_trades) == 0:

        continue


    strategy_trades["year"] = (

        pd.to_datetime(
            strategy_trades[
                "signal_date"
            ]
        )

        .dt.year
    )


    for year, group in strategy_trades.groupby(
        "year"
    ):

        yearly_rows.append({

            "strategy":
                strategy_name,

            "year":
                year,

            "trades":
                len(group),

            "avg_trade":
                group["return"].mean(),

            "median_trade":
                group["return"].median(),

            "win_rate":
                (
                    group["return"] > 0
                ).mean(),

            "compounded_trade_return":
                (
                    1 + group["return"]
                ).prod() - 1,
        })


yearly_summary = pd.DataFrame(
    yearly_rows
)


# ============================================================
# 12. SAVE FILES
# ============================================================

summary.to_csv(
    "data/short_term_filter_summary.csv",
    index=False,
)


trades_output.to_csv(
    "data/short_term_filter_trades.csv",
    index=False,
)


equity_curves.to_csv(
    "data/short_term_filter_equity.csv",
)


yearly_summary.to_csv(
    "data/short_term_filter_yearly.csv",
    index=False,
)


# ============================================================
# 13. PRINT SUMMARY
# ============================================================

print()
print("=" * 110)
print("SHORT-TERM FILTER TEST RESULTS")
print("=" * 110)
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

            "best_trade":
                "{:.2%}".format,

            "worst_trade":
                "{:.2%}".format,
        }
    )
)


# ============================================================
# 14. PRINT YEARLY RESULTS
# ============================================================

print()
print("=" * 110)
print("YEAR-BY-YEAR RESULTS")
print("=" * 110)
print()


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

            "compounded_trade_return":
                "{:.2%}".format,
        }
    )
)


# ============================================================
# 15. FINAL MESSAGE
# ============================================================

print()
print("Files saved:")

print(
    "data/short_term_filter_summary.csv"
)

print(
    "data/short_term_filter_trades.csv"
)

print(
    "data/short_term_filter_equity.csv"
)

print(
    "data/short_term_filter_yearly.csv"
)