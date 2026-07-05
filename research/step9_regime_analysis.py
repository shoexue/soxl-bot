import pandas as pd


# ============================================================
# 1. LOAD DATA
# ============================================================

trades = pd.read_csv(
    "data/exit_strategy_trades.csv",
    parse_dates=["signal_date", "entry_date", "exit_date"]
)

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

soxx = pd.read_csv(
    "data/SOXX.csv",
    parse_dates=["Date"],
    index_col="Date"
)

vix = pd.read_csv(
    "data/VIX.csv",
    parse_dates=["Date"],
    index_col="Date"
)


# ============================================================
# 2. BUILD FEATURES
# ============================================================

# ------------------------
# SOXL
# ------------------------

soxl["return_1d"] = (
    soxl["Close"]
    .pct_change(1)
)

soxl["return_5d"] = (
    soxl["Close"]
    .pct_change(5)
)

soxl["return_10d"] = (
    soxl["Close"]
    .pct_change(10)
)

soxl["volatility_20d"] = (
    soxl["return_1d"]
    .rolling(20)
    .std()
)

soxl["volume_avg_20d"] = (
    soxl["Volume"]
    .rolling(20)
    .mean()
)

soxl["volume_ratio"] = (
    soxl["Volume"]
    / soxl["volume_avg_20d"]
)


# ------------------------
# QQQ
# ------------------------

qqq["ma_50"] = (
    qqq["Close"]
    .rolling(50)
    .mean()
)

qqq["trend"] = (
    qqq["Close"]
    / qqq["ma_50"]
) - 1


# ------------------------
# SOXX
# ------------------------

soxx["ma_50"] = (
    soxx["Close"]
    .rolling(50)
    .mean()
)

soxx["trend"] = (
    soxx["Close"]
    / soxx["ma_50"]
) - 1


# ------------------------
# VIX
# ------------------------

vix["change_5d"] = (
    vix["Close"]
    .pct_change(5)
)


# ============================================================
# 3. ATTACH FEATURES TO EXECUTED TRADES
# ============================================================

rows = []


for _, trade in trades.iterrows():

    signal_date = trade["signal_date"]


    # Make sure all datasets contain the date
    if signal_date not in soxl.index:
        continue

    if signal_date not in qqq.index:
        continue

    if signal_date not in soxx.index:
        continue

    if signal_date not in vix.index:
        continue


    row = {

        # ------------------------
        # Trade information
        # ------------------------

        "signal_date":
            signal_date,

        "entry_date":
            trade["entry_date"],

        "exit_date":
            trade["exit_date"],

        "trade_return":
            trade["return"],

        "exit_reason":
            trade["exit_reason"],


        # Winner = trade made money
        "winner":
            trade["return"] > 0,


        # ------------------------
        # SOXL features
        # ------------------------

        "z_score":
            soxl.loc[
                signal_date,
                "z_score"
            ],

        "soxl_return_1d":
            soxl.loc[
                signal_date,
                "return_1d"
            ],

        "soxl_return_5d":
            soxl.loc[
                signal_date,
                "return_5d"
            ],

        "soxl_return_10d":
            soxl.loc[
                signal_date,
                "return_10d"
            ],

        "volatility_20d":
            soxl.loc[
                signal_date,
                "volatility_20d"
            ],

        "volume_ratio":
            soxl.loc[
                signal_date,
                "volume_ratio"
            ],


        # ------------------------
        # Market context
        # ------------------------

        "qqq_trend":
            qqq.loc[
                signal_date,
                "trend"
            ],

        "soxx_trend":
            soxx.loc[
                signal_date,
                "trend"
            ],

        "vix_level":
            vix.loc[
                signal_date,
                "Close"
            ],

        "vix_change_5d":
            vix.loc[
                signal_date,
                "change_5d"
            ],
    }


    rows.append(row)


analysis = pd.DataFrame(rows)


# ============================================================
# 4. FEATURE LIST
# ============================================================

features = [

    "z_score",

    "soxl_return_1d",
    "soxl_return_5d",
    "soxl_return_10d",

    "volatility_20d",
    "volume_ratio",

    "qqq_trend",
    "soxx_trend",

    "vix_level",
    "vix_change_5d",
]


# ============================================================
# 5. WINNER VS LOSER COMPARISON
# ============================================================

winner_comparison = (
    analysis
    .groupby("winner")[features]
    .mean()
    .T
)


winner_comparison.columns = [
    "losers_avg",
    "winners_avg"
]


winner_comparison[
    "difference"
] = (

    winner_comparison[
        "winners_avg"
    ]

    -

    winner_comparison[
        "losers_avg"
    ]
)


# ============================================================
# 6. MEDIAN COMPARISON
# ============================================================

median_comparison = (
    analysis
    .groupby("winner")[features]
    .median()
    .T
)


median_comparison.columns = [
    "losers_median",
    "winners_median"
]


median_comparison[
    "difference"
] = (

    median_comparison[
        "winners_median"
    ]

    -

    median_comparison[
        "losers_median"
    ]
)


# ============================================================
# 7. CORRELATION WITH TRADE RETURN
# ============================================================

correlations = (

    analysis[
        features
        + ["trade_return"]
    ]

    .corr()["trade_return"]

    .drop("trade_return")

    .sort_values(
        ascending=False
    )
)


correlation_df = (
    correlations
    .rename(
        "correlation_with_return"
    )
    .to_frame()
)


# ============================================================
# 8. SIMPLE MEDIAN-SPLIT ANALYSIS
# ============================================================

split_results = []


for feature in features:

    median_value = analysis[
        feature
    ].median()


    low_group = analysis[
        analysis[feature]
        <= median_value
    ]


    high_group = analysis[
        analysis[feature]
        > median_value
    ]


    split_results.append({

        "feature":
            feature,

        "median_split":
            median_value,


        # Low feature group

        "low_trades":
            len(low_group),

        "low_avg_return":
            low_group[
                "trade_return"
            ].mean(),

        "low_win_rate":
            low_group[
                "winner"
            ].mean(),


        # High feature group

        "high_trades":
            len(high_group),

        "high_avg_return":
            high_group[
                "trade_return"
            ].mean(),

        "high_win_rate":
            high_group[
                "winner"
            ].mean(),
    })


split_df = pd.DataFrame(
    split_results
)


# ============================================================
# 9. EXIT REASON ANALYSIS
# ============================================================

exit_summary = (

    analysis
    .groupby(
        "exit_reason"
    )

    .agg(

        trades=(
            "trade_return",
            "count"
        ),

        avg_return=(
            "trade_return",
            "mean"
        ),

        median_return=(
            "trade_return",
            "median"
        ),

        win_rate=(
            "winner",
            "mean"
        ),
    )

    .sort_values(
        "avg_return",
        ascending=False
    )
)


# ============================================================
# 10. SAVE RESULTS
# ============================================================

analysis.to_csv(
    "data/regime_trade_analysis.csv",
    index=False
)


winner_comparison.to_csv(
    "data/winner_loser_means.csv"
)


median_comparison.to_csv(
    "data/winner_loser_medians.csv"
)


correlation_df.to_csv(
    "data/feature_correlations.csv"
)


split_df.to_csv(
    "data/feature_median_splits.csv",
    index=False
)


exit_summary.to_csv(
    "data/exit_reason_summary.csv"
)


# ============================================================
# 11. PRINT RESULTS
# ============================================================

print()
print("=" * 70)
print("REGIME ANALYSIS")
print("=" * 70)

print()
print(f"Trades analyzed: {len(analysis)}")

print(
    f"Winners: {analysis['winner'].sum()}"
)

print(
    f"Losers: {(~analysis['winner']).sum()}"
)


print()
print("=" * 70)
print("WINNER VS LOSER MEANS")
print("=" * 70)
print()

print(
    winner_comparison
)


print()
print("=" * 70)
print("CORRELATION WITH TRADE RETURN")
print("=" * 70)
print()

print(
    correlation_df
)


print()
print("=" * 70)
print("MEDIAN SPLIT ANALYSIS")
print("=" * 70)
print()

print(
    split_df.to_string(
        index=False,
        formatters={

            "low_avg_return":
                "{:.2%}".format,

            "low_win_rate":
                "{:.2%}".format,

            "high_avg_return":
                "{:.2%}".format,

            "high_win_rate":
                "{:.2%}".format,
        }
    )
)


print()
print("=" * 70)
print("EXIT REASONS")
print("=" * 70)
print()

print(
    exit_summary
)


print()
print("Files saved:")

print(
    "data/regime_trade_analysis.csv"
)

print(
    "data/winner_loser_means.csv"
)

print(
    "data/winner_loser_medians.csv"
)

print(
    "data/feature_correlations.csv"
)

print(
    "data/feature_median_splits.csv"
)

print(
    "data/exit_reason_summary.csv"
)