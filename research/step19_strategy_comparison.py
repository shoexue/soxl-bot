import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-01-01"
DOWNLOAD_START = "2020-01-01"

STARTING_CAPITAL = 10_000
POSITION_FRACTION = 0.50

QQQ_MA_WINDOW = 50
SLIPPAGE = 0.001

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# ============================================================
# 2. STRATEGIES
# ============================================================

STRATEGIES = {

    "Current 20D": {
        "z_window": 20,
        "z_threshold": -1.75,
        "exit_type": "stop_target",
        "stop_loss": -0.12,
        "profit_target": 0.20,
        "max_hold": 5,
    },

    "Fast 5D": {
        "z_window": 5,
        "z_threshold": -1.50,
        "exit_type": "fixed_hold",
        "hold_days": 5,
    },
}


# ============================================================
# 3. DOWNLOAD DATA
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


# ============================================================
# 4. BUILD QQQ FILTER
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
# 5. BUILD Z-SCORES
# ============================================================

windows = sorted(
    set(
        config["z_window"]
        for config in STRATEGIES.values()
    )
)


for window in windows:

    mean = (
        soxl["Close"]
        .rolling(window)
        .mean()
    )

    std = (
        soxl["Close"]
        .rolling(window)
        .std()
    )

    soxl[f"z_{window}"] = (
        (
            soxl["Close"]
            - mean
        )
        / std
    )


# ============================================================
# 6. MODERN PERIOD
# ============================================================

soxl = soxl[
    soxl.index >= START_DATE
].copy()


# ============================================================
# 7. CREATE SIGNALS
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
# 8. MAX DRAWDOWN
# ============================================================

def calculate_max_drawdown(equity):

    running_peak = equity.cummax()

    drawdown = (
        equity
        / running_peak
    ) - 1

    return drawdown.min()


# ============================================================
# 9. BACKTEST
# ============================================================

def run_backtest(
    data,
    strategy_name,
    config,
):

    signals = create_signals(

        data=data,

        z_window=
            config["z_window"],

        z_threshold=
            config["z_threshold"],
    )


    capital = STARTING_CAPITAL

    trades = []

    equity_records = []

    i = 0


    while i < len(data):

        current_date = data.index[i]


        equity_records.append({

            "Date":
                current_date,

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
        # ENTRY NEXT OPEN
        # ----------------------------------------------------

        signal_pos = i

        entry_pos = signal_pos + 1


        if entry_pos >= len(data):

            break


        signal_date = (
            data.index[signal_pos]
        )

        entry_date = (
            data.index[entry_pos]
        )


        raw_entry_price = (
            data.iloc[entry_pos]["Open"]
        )


        entry_price = (
            raw_entry_price
            * (1 + SLIPPAGE)
        )


        capital_before = capital


        invested_capital = (
            capital
            * POSITION_FRACTION
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
        # FIND EXIT
        # ----------------------------------------------------

        exit_price = None
        exit_pos = None
        exit_reason = None


        # ====================================================
        # CURRENT STRATEGY:
        # STOP / TARGET / MAX HOLD
        # ====================================================

        if (
            config["exit_type"]
            == "stop_target"
        ):

            stop_price = (
                entry_price
                * (
                    1
                    + config["stop_loss"]
                )
            )


            target_price = (
                entry_price
                * (
                    1
                    + config[
                        "profit_target"
                    ]
                )
            )


            max_hold = (
                config["max_hold"]
            )


            for hold_index in range(
                max_hold
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
                # stop first if both touched

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


            # Time exit

            if exit_price is None:

                exit_pos = min(

                    entry_pos
                    + max_hold
                    - 1,

                    len(data) - 1,
                )


                exit_price = (
                    data.iloc[
                        exit_pos
                    ]["Close"]

                    * (1 - SLIPPAGE)
                )


                exit_reason = "time_exit"


        # ====================================================
        # FAST STRATEGY:
        # FIXED HOLD
        # ====================================================

        elif (
            config["exit_type"]
            == "fixed_hold"
        ):

            hold_days = (
                config["hold_days"]
            )


            exit_pos = (
                entry_pos
                + hold_days
                - 1
            )


            if exit_pos >= len(data):
                break


            exit_price = (
                data.iloc[
                    exit_pos
                ]["Close"]

                * (1 - SLIPPAGE)
            )


            exit_reason = (
                "fixed_hold"
            )


        else:

            raise ValueError(
                "Unknown exit type"
            )


        exit_date = (
            data.index[exit_pos]
        )


        # ====================================================
        # EQUITY DURING POSITION
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


        account_return = (
            POSITION_FRACTION
            * position_return
        )


        capital = (
            capital
            * (
                1
                + account_return
            )
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

            "z_window":
                config[
                    "z_window"
                ],

            "z_threshold":
                config[
                    "z_threshold"
                ],

            "signal_z_score":
                data.iloc[
                    signal_pos
                ][
                    f"z_{config['z_window']}"
                ],

            "entry_price":
                entry_price,

            "exit_price":
                exit_price,

            "position_return":
                position_return,

            "account_return":
                account_return,

            "capital_before":
                capital_before,

            "capital_after":
                capital,

            "exit_reason":
                exit_reason,
        })


        # ----------------------------------------------------
        # NO OVERLAPPING POSITIONS
        # ----------------------------------------------------

        i = exit_pos + 1


    # ========================================================
    # OUTPUTS
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

        .reindex(data.index)

        .ffill()
    )


    return (
        capital,
        trades_df,
        equity_df,
        int(signals.sum()),
    )


# ============================================================
# 10. RUN BOTH STRATEGIES
# ============================================================

summary_rows = []

all_trades = []

equity_curves = pd.DataFrame(
    index=soxl.index
)


for strategy_name, config in (
    STRATEGIES.items()
):

    print()

    print(
        f"Running {strategy_name}..."
    )


    (
        final_capital,
        trades,
        equity,
        accepted_signals,

    ) = run_backtest(

        data=soxl,

        strategy_name=strategy_name,

        config=config,
    )


    returns = (
        trades["position_return"]
    )


    summary_rows.append({

        "strategy":
            strategy_name,

        "accepted_signals":
            accepted_signals,

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
            (
                returns > 0
            ).mean(),

        "avg_position_return":
            returns.mean(),

        "median_position_return":
            returns.median(),

        "best_trade":
            returns.max(),

        "worst_trade":
            returns.min(),
    })


    all_trades.append(
        trades
    )


    equity_curves[
        strategy_name
    ] = equity["Equity"]


# ============================================================
# 11. COMBINE RESULTS
# ============================================================

summary = pd.DataFrame(
    summary_rows
)


trades_output = pd.concat(
    all_trades,
    ignore_index=True,
)


# ============================================================
# 12. YEARLY RESULTS
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
            "strategy",
            "year",
        ]
    )

    .agg(

        trades=(
            "position_return",
            "count",
        ),

        avg_return=(
            "position_return",
            "mean",
        ),

        median_return=(
            "position_return",
            "median",
        ),

        win_rate=(
            "position_return",
            lambda x:
                (x > 0).mean(),
        ),

        compounded_position_return=(
            "position_return",
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
    / "strategy_comparison_summary.csv",
    index=False,
)


trades_output.to_csv(
    DATA_DIR
    / "strategy_comparison_trades.csv",
    index=False,
)


equity_curves.to_csv(
    DATA_DIR
    / "strategy_comparison_equity.csv",
)


yearly.to_csv(
    DATA_DIR
    / "strategy_comparison_yearly.csv",
    index=False,
)


# ============================================================
# 14. PRINT RESULTS
# ============================================================

print()

print("=" * 120)

print(
    "STRATEGY COMPARISON"
)

print("=" * 120)

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

            "avg_position_return":
                "{:.2%}".format,

            "median_position_return":
                "{:.2%}".format,

            "best_trade":
                "{:.2%}".format,

            "worst_trade":
                "{:.2%}".format,
        },
    )
)


print()

print("=" * 120)

print(
    "YEARLY RESULTS"
)

print("=" * 120)

print()


print(
    yearly.to_string(

        index=False,

        formatters={

            "avg_return":
                "{:.2%}".format,

            "median_return":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,

            "compounded_position_return":
                "{:.2%}".format,
        },
    )
)


print()

print("Files saved:")

print(
    "data/strategy_comparison_summary.csv"
)

print(
    "data/strategy_comparison_trades.csv"
)

print(
    "data/strategy_comparison_equity.csv"
)

print(
    "data/strategy_comparison_yearly.csv"
)