import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# 1. SETTINGS
# ============================================================

START_DATE = "2021-01-01"
DOWNLOAD_START = "2020-01-01"

Z_WINDOW = 20
Z_THRESHOLD = -1.75

QQQ_MA_WINDOW = 50

HOLD_DAYS = 5
SLIPPAGE = 0.001


ASSETS = [
    "SOXL",
    "SOXX",
    "SMH",
    "NVDA",
    "AMD",
    "AVGO",
    "TSM",
]


Path("data").mkdir(exist_ok=True)


# ============================================================
# 2. DOWNLOAD DATA
# ============================================================

tickers_to_download = ASSETS + ["QQQ"]

market_data = {}


for ticker in tickers_to_download:

    print(f"Downloading {ticker}...")


    df = yf.download(
        ticker,
        start=DOWNLOAD_START,
        auto_adjust=True,
        progress=False,
    )


    # Fix yfinance MultiIndex columns

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = (
            df.columns
            .get_level_values(0)
        )


    df = df[
        [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    ].copy()


    market_data[ticker] = df


    print(
        f"{ticker}: "
        f"{df.index.min()} → "
        f"{df.index.max()}"
    )


# ============================================================
# 3. BUILD QQQ REGIME FILTER
# ============================================================

qqq = market_data["QQQ"].copy()


qqq["ma_50"] = (
    qqq["Close"]
    .rolling(QQQ_MA_WINDOW)
    .mean()
)


qqq["healthy"] = (
    qqq["Close"]
    > qqq["ma_50"]
)


# ============================================================
# 4. BACKTEST ONE ASSET
# ============================================================

def test_asset(
    ticker,
    data,
    qqq_data,
):

    df = data.copy()


    # --------------------------------------------------------
    # CREATE 20-DAY Z-SCORE
    # --------------------------------------------------------

    df["ma_20"] = (
        df["Close"]
        .rolling(Z_WINDOW)
        .mean()
    )


    df["std_20"] = (
        df["Close"]
        .rolling(Z_WINDOW)
        .std()
    )


    df["z_score"] = (

        (
            df["Close"]
            - df["ma_20"]
        )

        / df["std_20"]
    )


    # --------------------------------------------------------
    # ATTACH QQQ REGIME
    # --------------------------------------------------------

    df["qqq_healthy"] = (

        qqq_data["healthy"]

        .reindex(
            df.index
        )
    )


    # Keep modern test period

    df = df[
        df.index >= START_DATE
    ].copy()


    # --------------------------------------------------------
    # ORIGINAL OVERSOLD EPISODES
    # --------------------------------------------------------

    oversold = (
        df["z_score"]
        < Z_THRESHOLD
    )


    episode_start = (

        oversold

        &

        ~oversold.shift(
            1,
            fill_value=False,
        )
    )


    # --------------------------------------------------------
    # APPLY QQQ FILTER ONLY ON EPISODE START
    # --------------------------------------------------------

    signals = (

        episode_start

        &

        df["qqq_healthy"]
        .fillna(False)
    )


    signal_dates = df.index[
        signals
    ]


    trades = []


    # ========================================================
    # CREATE TRADES
    # ========================================================

    for signal_date in signal_dates:

        signal_pos = (
            df.index.get_loc(
                signal_date
            )
        )


        entry_pos = (
            signal_pos + 1
        )


        exit_pos = (

            entry_pos

            + HOLD_DAYS

            - 1
        )


        if exit_pos >= len(df):

            continue


        entry_date = df.index[
            entry_pos
        ]


        exit_date = df.index[
            exit_pos
        ]


        raw_entry = df.iloc[
            entry_pos
        ]["Open"]


        raw_exit = df.iloc[
            exit_pos
        ]["Close"]


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

            "asset":
                ticker,

            "signal_date":
                signal_date,

            "entry_date":
                entry_date,

            "exit_date":
                exit_date,

            "z_score":
                df.loc[
                    signal_date,
                    "z_score"
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


    return pd.DataFrame(
        trades
    )


# ============================================================
# 5. RUN ALL ASSETS
# ============================================================

all_trades = []


for ticker in ASSETS:

    print()

    print(
        f"Testing {ticker}..."
    )


    trades = test_asset(

        ticker=ticker,

        data=market_data[ticker],

        qqq_data=qqq,
    )


    print(
        f"{ticker}: "
        f"{len(trades)} trades"
    )


    if len(trades) > 0:

        all_trades.append(
            trades
        )


# ============================================================
# 6. COMBINE TRADES
# ============================================================

trades_output = pd.concat(

    all_trades,

    ignore_index=True,
)


# ============================================================
# 7. ASSET-BY-ASSET SUMMARY
# ============================================================

asset_summary = (

    trades_output

    .groupby("asset")

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

        best_trade=(
            "return",
            "max",
        ),

        worst_trade=(
            "return",
            "min",
        ),
    )

    .reset_index()
)


# ============================================================
# 8. COMPOUNDED RETURN PER ASSET
# ============================================================

compounded = (

    trades_output

    .groupby("asset")["return"]

    .apply(
        lambda x:
            (1 + x).prod() - 1
    )

    .rename(
        "compounded_trade_return"
    )

    .reset_index()
)


asset_summary = asset_summary.merge(

    compounded,

    on="asset",

    how="left",
)


# ============================================================
# 9. POOLED SUMMARY
# ============================================================

pooled_summary = pd.DataFrame([{

    "assets":
        trades_output[
            "asset"
        ].nunique(),

    "trades":
        len(trades_output),

    "avg_return":
        trades_output[
            "return"
        ].mean(),

    "median_return":
        trades_output[
            "return"
        ].median(),

    "win_rate":
        trades_output[
            "winner"
        ].mean(),

    "best_trade":
        trades_output[
            "return"
        ].max(),

    "worst_trade":
        trades_output[
            "return"
        ].min(),
}])


# ============================================================
# 10. YEAR-BY-YEAR SUMMARY
# ============================================================

trades_output["year"] = (

    pd.to_datetime(

        trades_output[
            "signal_date"
        ]
    )

    .dt.year
)


yearly_summary = (

    trades_output

    .groupby("year")

    .agg(

        trades=(
            "return",
            "count",
        ),

        assets=(
            "asset",
            "nunique",
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
    )

    .reset_index()
)


# ============================================================
# 11. SAVE FILES
# ============================================================

trades_output.to_csv(

    "data/cross_asset_trades.csv",

    index=False,
)


asset_summary.to_csv(

    "data/cross_asset_summary.csv",

    index=False,
)


pooled_summary.to_csv(

    "data/cross_asset_pooled.csv",

    index=False,
)


yearly_summary.to_csv(

    "data/cross_asset_yearly.csv",

    index=False,
)


# ============================================================
# 12. PRINT RESULTS
# ============================================================

print()

print("=" * 100)

print(
    "CROSS-ASSET TEST RESULTS"
)

print("=" * 100)

print()


print(
    asset_summary.to_string(

        index=False,

        formatters={

            "avg_return":
                "{:.2%}".format,

            "median_return":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,

            "best_trade":
                "{:.2%}".format,

            "worst_trade":
                "{:.2%}".format,

            "compounded_trade_return":
                "{:.2%}".format,
        }
    )
)


print()

print("=" * 100)

print(
    "POOLED RESULTS"
)

print("=" * 100)

print()


print(
    pooled_summary.to_string(

        index=False,

        formatters={

            "avg_return":
                "{:.2%}".format,

            "median_return":
                "{:.2%}".format,

            "win_rate":
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


print(
    yearly_summary.to_string(

        index=False,

        formatters={

            "avg_return":
                "{:.2%}".format,

            "median_return":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,
        }
    )
)


print()

print("Files saved:")

print(
    "data/cross_asset_trades.csv"
)

print(
    "data/cross_asset_summary.csv"
)

print(
    "data/cross_asset_pooled.csv"
)

print(
    "data/cross_asset_yearly.csv"
)