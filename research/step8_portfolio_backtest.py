import pandas as pd


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-07-05"
STARTING_CAPITAL = 10_000

SIGNAL_THRESHOLD = -1.75

STOP_LOSS = -0.12
PROFIT_TARGET = 0.20
MAX_HOLD = 5

# 0.10% cost on entry and exit
SLIPPAGE = 0.001


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(
    "data/SOXL_features.csv",
    parse_dates=["Date"],
    index_col="Date"
)

df = df[
    df.index >= START_DATE
].copy()


print()
print(f"Data from {df.index.min()} to {df.index.max()}")
print(f"Trading days: {len(df)}")


# ============================================================
# 3. CREATE SIGNAL EPISODES
# ============================================================

signal = (
    df["z_score"]
    < SIGNAL_THRESHOLD
)

episode_start = (
    signal
    & ~signal.shift(1, fill_value=False)
)

df["episode_start"] = episode_start


print(
    f"Signal episodes: {episode_start.sum()}"
)


# ============================================================
# 4. BUY AND HOLD
# ============================================================

buy_hold_entry_price = (
    df.iloc[0]["Open"]
    * (1 + SLIPPAGE)
)

buy_hold_exit_price = (
    df.iloc[-1]["Close"]
    * (1 - SLIPPAGE)
)

buy_hold_return = (
    buy_hold_exit_price
    / buy_hold_entry_price
) - 1

buy_hold_final = (
    STARTING_CAPITAL
    * (1 + buy_hold_return)
)


# Daily buy-and-hold equity curve

buy_hold_equity = (
    STARTING_CAPITAL
    * df["Close"]
    / buy_hold_entry_price
)

buy_hold_equity.iloc[-1] = buy_hold_final


# ============================================================
# 5. FIXED 5-DAY HOLD STRATEGY
# ============================================================

def run_fixed_hold_backtest(
    data,
    starting_capital,
    hold_days
):

    capital = starting_capital

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        date = data.index[i]


        # Record cash value while not invested
        equity_records.append({
            "Date": date,
            "Equity": capital
        })


        # Check whether today is a signal day
        if not data.iloc[i]["episode_start"]:
            i += 1
            continue


        # Enter next trading day
        entry_pos = i + 1


        if entry_pos >= len(data):
            break


        exit_pos = (
            entry_pos
            + hold_days
            - 1
        )


        if exit_pos >= len(data):
            break


        entry_date = data.index[entry_pos]
        exit_date = data.index[exit_pos]


        raw_entry_price = data.iloc[
            entry_pos
        ]["Open"]


        entry_price = (
            raw_entry_price
            * (1 + SLIPPAGE)
        )


        raw_exit_price = data.iloc[
            exit_pos
        ]["Close"]


        exit_price = (
            raw_exit_price
            * (1 - SLIPPAGE)
        )


        capital_before = capital


        shares = (
            capital
            / entry_price
        )


        # Record mark-to-market equity during trade
        for j in range(
            entry_pos,
            exit_pos + 1
        ):

            current_date = data.index[j]

            current_close = data.iloc[
                j
            ]["Close"]

            current_equity = (
                shares
                * current_close
            )

            equity_records.append({
                "Date": current_date,
                "Equity": current_equity
            })


        trade_return = (
            exit_price
            / entry_price
        ) - 1


        capital = (
            capital
            * (1 + trade_return)
        )


        trades.append({

            "signal_date":
                date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

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
                f"{hold_days}_day_hold"
        })


        # Skip to day after exit
        i = exit_pos + 1


    trades_df = pd.DataFrame(trades)


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
    )


    # Fill missing trading days
    equity_df = (
        equity_df
        .reindex(data.index)
        .ffill()
    )


    return (
        capital,
        trades_df,
        equity_df
    )


# ============================================================
# 6. STOP / TARGET / TIME EXIT STRATEGY
# ============================================================

def run_exit_strategy_backtest(
    data,
    starting_capital,
    stop_loss,
    profit_target,
    max_hold
):

    capital = starting_capital

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        date = data.index[i]


        equity_records.append({
            "Date": date,
            "Equity": capital
        })


        if not data.iloc[i]["episode_start"]:
            i += 1
            continue


        entry_pos = i + 1


        if entry_pos >= len(data):
            break


        raw_entry_price = data.iloc[
            entry_pos
        ]["Open"]


        entry_price = (
            raw_entry_price
            * (1 + SLIPPAGE)
        )


        stop_price = (
            entry_price
            * (1 + stop_loss)
        )


        target_price = (
            entry_price
            * (1 + profit_target)
        )


        capital_before = capital


        shares = (
            capital
            / entry_price
        )


        exit_price = None
        exit_pos = None
        exit_reason = None


        # Check each day chronologically
        for hold_index in range(max_hold):

            day_pos = (
                entry_pos
                + hold_index
            )


            if day_pos >= len(data):
                break


            day = data.iloc[day_pos]


            hit_stop = (
                day["Low"]
                <= stop_price
            )


            hit_target = (
                day["High"]
                >= target_price
            )


            # Conservative assumption:
            # if both happen on same daily candle,
            # assume stop was hit first.

            if hit_stop and hit_target:

                exit_price = (
                    stop_price
                    * (1 - SLIPPAGE)
                )

                exit_pos = day_pos

                exit_reason = "stop_both_hit"

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


        # No stop or target hit:
        # exit at Close on final allowed day

        if exit_price is None:

            exit_pos = min(
                entry_pos + max_hold - 1,
                len(data) - 1
            )


            raw_exit_price = data.iloc[
                exit_pos
            ]["Close"]


            exit_price = (
                raw_exit_price
                * (1 - SLIPPAGE)
            )


            exit_reason = "time_exit"


        entry_date = data.index[
            entry_pos
        ]


        exit_date = data.index[
            exit_pos
        ]


        # Record equity during the trade

        for j in range(
            entry_pos,
            exit_pos + 1
        ):

            current_date = data.index[j]


            # On exit day, use actual exit price
            if j == exit_pos:

                current_equity = (
                    shares
                    * exit_price
                )

            else:

                current_close = data.iloc[
                    j
                ]["Close"]

                current_equity = (
                    shares
                    * current_close
                )


            equity_records.append({

                "Date":
                    current_date,

                "Equity":
                    current_equity
            })


        trade_return = (
            exit_price
            / entry_price
        ) - 1


        capital = (
            capital
            * (1 + trade_return)
        )


        trades.append({

            "signal_date":
                date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

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


        # Move to day after exit
        i = exit_pos + 1


    trades_df = pd.DataFrame(
        trades
    )


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
    )


    equity_df = (
        equity_df
        .reindex(data.index)
        .ffill()
    )


    return (
        capital,
        trades_df,
        equity_df
    )


# ============================================================
# 7. RUN STRATEGIES
# ============================================================

fixed_final, fixed_trades, fixed_equity = (
    run_fixed_hold_backtest(
        data=df,
        starting_capital=STARTING_CAPITAL,
        hold_days=5
    )
)


exit_final, exit_trades, exit_equity = (
    run_exit_strategy_backtest(
        data=df,
        starting_capital=STARTING_CAPITAL,
        stop_loss=STOP_LOSS,
        profit_target=PROFIT_TARGET,
        max_hold=MAX_HOLD
    )
)


# ============================================================
# 8. MAX DRAWDOWN FUNCTION
# ============================================================

def calculate_max_drawdown(
    equity_series
):

    running_peak = (
        equity_series
        .cummax()
    )


    drawdown = (
        equity_series
        / running_peak
    ) - 1


    return drawdown.min()


# ============================================================
# 9. CALCULATE METRICS
# ============================================================

fixed_max_dd = calculate_max_drawdown(
    fixed_equity["Equity"]
)


exit_max_dd = calculate_max_drawdown(
    exit_equity["Equity"]
)


buy_hold_max_dd = calculate_max_drawdown(
    buy_hold_equity
)


fixed_win_rate = (
    fixed_trades["return"] > 0
).mean()


exit_win_rate = (
    exit_trades["return"] > 0
).mean()


# ============================================================
# 10. BUILD SUMMARY TABLE
# ============================================================

summary = pd.DataFrame([

    {
        "strategy":
            "Buy and Hold",

        "starting_capital":
            STARTING_CAPITAL,

        "final_capital":
            buy_hold_final,

        "total_return":
            (
                buy_hold_final
                / STARTING_CAPITAL
            ) - 1,

        "max_drawdown":
            buy_hold_max_dd,

        "trades":
            1,

        "win_rate":
            None
    },


    {
        "strategy":
            "Fixed 5-Day Hold",

        "starting_capital":
            STARTING_CAPITAL,

        "final_capital":
            fixed_final,

        "total_return":
            (
                fixed_final
                / STARTING_CAPITAL
            ) - 1,

        "max_drawdown":
            fixed_max_dd,

        "trades":
            len(fixed_trades),

        "win_rate":
            fixed_win_rate
    },


    {
        "strategy":
            "Stop Target 5-Day",

        "starting_capital":
            STARTING_CAPITAL,

        "final_capital":
            exit_final,

        "total_return":
            (
                exit_final
                / STARTING_CAPITAL
            ) - 1,

        "max_drawdown":
            exit_max_dd,

        "trades":
            len(exit_trades),

        "win_rate":
            exit_win_rate
    }

])


# ============================================================
# 11. SAVE RESULTS
# ============================================================

summary.to_csv(
    "data/portfolio_summary.csv",
    index=False
)


fixed_trades.to_csv(
    "data/fixed_hold_trades.csv",
    index=False
)


exit_trades.to_csv(
    "data/exit_strategy_trades.csv",
    index=False
)


# Combined equity curve

equity_curve = pd.DataFrame(
    index=df.index
)


equity_curve[
    "buy_hold"
] = buy_hold_equity


equity_curve[
    "fixed_5d"
] = fixed_equity["Equity"]


equity_curve[
    "stop_target_5d"
] = exit_equity["Equity"]


equity_curve.to_csv(
    "data/equity_curve.csv"
)


# ============================================================
# 12. PRINT RESULTS
# ============================================================

print()
print("=" * 70)
print("PORTFOLIO BACKTEST RESULTS")
print("=" * 70)
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
                lambda x:
                    ""
                    if pd.isna(x)
                    else f"{x:.2%}"
        }
    )
)


print()
print("=" * 70)
print("EXIT REASONS")
print("=" * 70)
print()


print(
    exit_trades[
        "exit_reason"
    ].value_counts()
)


print()
print("Files saved:")
print("data/portfolio_summary.csv")
print("data/fixed_hold_trades.csv")
print("data/exit_strategy_trades.csv")
print("data/equity_curve.csv")