import pandas as pd
import numpy as np


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
# 2. POSITION-SIZING METHODS
# ============================================================

SIZING_METHODS = {

    "25% Allocation": {
        "type": "allocation",
        "value": 0.25,
    },

    "50% Allocation": {
        "type": "allocation",
        "value": 0.50,
    },

    "75% Allocation": {
        "type": "allocation",
        "value": 0.75,
    },

    "100% Allocation": {
        "type": "allocation",
        "value": 1.00,
    },

    "1% Account Risk": {
        "type": "risk",
        "value": 0.01,
    },

    "2% Account Risk": {
        "type": "risk",
        "value": 0.02,
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
print("=" * 100)
print("STEP 15 — POSITION SIZING")
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
# 4. BUILD QQQ MA50 FILTER
# ============================================================

qqq_raw["ma_50"] = (
    qqq_raw["Close"]
    .rolling(50)
    .mean()
)


qqq_raw["above_ma50"] = (
    qqq_raw["Close"]
    > qqq_raw["ma_50"]
)


# ============================================================
# 5. PREPARE SOXL DATA
# ============================================================

soxl = soxl_raw[
    soxl_raw.index >= START_DATE
].copy()


soxl["qqq_above_ma50"] = (

    qqq_raw["above_ma50"]

    .reindex(
        soxl.index
    )

    .fillna(False)

    .astype(bool)
)


# ============================================================
# 6. CREATE SIGNALS
# ============================================================

oversold = (
    soxl["z_score"]
    < SIGNAL_THRESHOLD
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

    soxl["qqq_above_ma50"]
)


print()

print(
    f"Accepted signals: "
    f"{int(signals.sum())}"
)


# ============================================================
# 7. POSITION FRACTION FUNCTION
# ============================================================

def get_position_fraction(
    sizing_type,
    sizing_value,
):

    # --------------------------------------------------------
    # FIXED ALLOCATION
    # --------------------------------------------------------

    if sizing_type == "allocation":

        return sizing_value


    # --------------------------------------------------------
    # ACCOUNT-RISK SIZING
    #
    # Example:
    #
    # 1% account risk / 12% stop
    # = 8.33% of account invested
    # --------------------------------------------------------

    elif sizing_type == "risk":

        position_fraction = (

            sizing_value

            / abs(STOP_LOSS)
        )


        # No leverage beyond account value

        return min(
            position_fraction,
            1.0,
        )


    else:

        raise ValueError(
            f"Unknown sizing type: "
            f"{sizing_type}"
        )


# ============================================================
# 8. MAX DRAWDOWN
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
# 9. BACKTEST FUNCTION
# ============================================================

def run_backtest(
    data,
    signal_series,
    strategy_name,
    position_fraction,
):

    capital = STARTING_CAPITAL

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        current_date = data.index[i]


        # Record full account value while in cash

        equity_records.append({

            "Date":
                current_date,

            "Equity":
                capital,
        })


        # ----------------------------------------------------
        # NO SIGNAL
        # ----------------------------------------------------

        if not signal_series.iloc[i]:

            i += 1

            continue


        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        entry_pos = i + 1


        if entry_pos >= len(data):

            break


        signal_date = data.index[i]


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
        # POSITION SIZE
        # ----------------------------------------------------

        capital_before = capital


        invested_capital = (

            capital

            * position_fraction
        )


        cash = (

            capital

            - invested_capital
        )


        shares = (

            invested_capital

            / entry_price
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


            # Conservative:
            # stop first if both touched same candle

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
        # RECORD DAILY ACCOUNT EQUITY
        # ====================================================

        for j in range(
            entry_pos,
            exit_pos + 1,
        ):

            date = data.index[j]


            if j == exit_pos:

                position_value = (

                    shares

                    * exit_price
                )


            else:

                position_value = (

                    shares

                    * data.iloc[j]["Close"]
                )


            total_equity = (

                cash

                + position_value
            )


            equity_records.append({

                "Date":
                    date,

                "Equity":
                    total_equity,
            })


        # ====================================================
        # UPDATE CAPITAL
        # ====================================================

        position_return = (

            exit_price

            / entry_price

        ) - 1


        position_profit = (

            invested_capital

            * position_return
        )


        capital = (

            capital

            + position_profit
        )


        account_return = (

            capital

            / capital_before

        ) - 1


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

            "position_fraction":
                position_fraction,

            "capital_before":
                capital_before,

            "invested_capital":
                invested_capital,

            "cash_held":
                cash,

            "position_return":
                position_return,

            "account_return":
                account_return,

            "capital_after":
                capital,

            "exit_reason":
                exit_reason,
        })


        # Prevent overlapping trades

        i = exit_pos + 1


    # ========================================================
    # BUILD OUTPUTS
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
# 10. RUN ALL SIZING METHODS
# ============================================================

summary_rows = []

all_trades = []

equity_curves = pd.DataFrame(
    index=soxl.index
)


for strategy_name, config in (
    SIZING_METHODS.items()
):

    position_fraction = (
        get_position_fraction(

            sizing_type=config["type"],

            sizing_value=config["value"],
        )
    )


    (
        final_capital,
        trades,
        equity,

    ) = run_backtest(

        data=soxl,

        signal_series=signals,

        strategy_name=strategy_name,

        position_fraction=position_fraction,
    )


    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    total_return = (

        final_capital

        / STARTING_CAPITAL

    ) - 1


    max_drawdown = (

        calculate_max_drawdown(
            equity["Equity"]
        )
    )


    daily_returns = (

        equity["Equity"]

        .pct_change()

        .fillna(0)
    )


    annualized_volatility = (

        daily_returns.std()

        * np.sqrt(252)
    )


    if len(trades) > 0:

        win_rate = (

            trades["position_return"]

            > 0

        ).mean()


        avg_account_return = (

            trades["account_return"]

            .mean()
        )


        worst_account_trade = (

            trades["account_return"]

            .min()
        )


        best_account_trade = (

            trades["account_return"]

            .max()
        )


    else:

        win_rate = 0
        avg_account_return = 0
        worst_account_trade = 0
        best_account_trade = 0


    summary_rows.append({

        "strategy":
            strategy_name,

        "position_fraction":
            position_fraction,

        "trades":
            len(trades),

        "starting_capital":
            STARTING_CAPITAL,

        "final_capital":
            final_capital,

        "total_return":
            total_return,

        "max_drawdown":
            max_drawdown,

        "annualized_volatility":
            annualized_volatility,

        "win_rate":
            win_rate,

        "avg_account_return_per_trade":
            avg_account_return,

        "best_account_trade":
            best_account_trade,

        "worst_account_trade":
            worst_account_trade,
    })


    if len(trades) > 0:

        all_trades.append(
            trades
        )


    column_name = (

        strategy_name

        .lower()

        .replace(" ", "_")

        .replace("%", "pct")
    )


    equity_curves[
        column_name
    ] = equity["Equity"]


# ============================================================
# 11. BUILD OUTPUT TABLES
# ============================================================

summary = pd.DataFrame(
    summary_rows
)


trades_output = pd.concat(
    all_trades,
    ignore_index=True,
)


# ============================================================
# 12. RETURN / DRAWDOWN EFFICIENCY
# ============================================================

summary[
    "return_to_drawdown"
] = (

    summary["total_return"]

    / summary[
        "max_drawdown"
    ].abs()
)


# ============================================================
# 13. SAVE FILES
# ============================================================

summary.to_csv(
    "data/position_sizing_summary.csv",
    index=False,
)


trades_output.to_csv(
    "data/position_sizing_trades.csv",
    index=False,
)


equity_curves.to_csv(
    "data/position_sizing_equity.csv",
)


# ============================================================
# 14. PRINT RESULTS
# ============================================================

print()
print("=" * 120)
print("POSITION SIZING RESULTS")
print("=" * 120)
print()


print(
    summary.to_string(

        index=False,

        formatters={

            "position_fraction":
                "{:.2%}".format,

            "starting_capital":
                "${:,.2f}".format,

            "final_capital":
                "${:,.2f}".format,

            "total_return":
                "{:.2%}".format,

            "max_drawdown":
                "{:.2%}".format,

            "annualized_volatility":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,

            "avg_account_return_per_trade":
                "{:.2%}".format,

            "best_account_trade":
                "{:.2%}".format,

            "worst_account_trade":
                "{:.2%}".format,

            "return_to_drawdown":
                "{:.2f}".format,
        }
    )
)


# ============================================================
# 15. PRINT RISK-SIZING EXPLANATION
# ============================================================

print()
print("=" * 120)
print("RISK-SIZING FRACTIONS")
print("=" * 120)
print()


for name, config in SIZING_METHODS.items():

    fraction = get_position_fraction(

        config["type"],

        config["value"],
    )


    print(

        f"{name}: "

        f"{fraction:.2%} of account invested"
    )


# ============================================================
# 16. FINAL MESSAGE
# ============================================================

print()
print("Files saved:")

print(
    "data/position_sizing_summary.csv"
)

print(
    "data/position_sizing_trades.csv"
)

print(
    "data/position_sizing_equity.csv"
)