import pandas as pd
import numpy as np


# ============================================================
# 1. SETTINGS
# ============================================================

# Signals within this many CALENDAR days of the previous
# signal are grouped into the same market event.
#
# We use calendar days here because the trade file contains
# dates, and this keeps the clustering logic easy to inspect.

EVENT_GAP_DAYS = 5


# ============================================================
# 2. LOAD DATA
# ============================================================

trades = pd.read_csv(
    "data/cross_asset_trades.csv",
    parse_dates=[
        "signal_date",
        "entry_date",
        "exit_date",
    ],
)


qqq = pd.read_csv(
    "data/QQQ.csv",
    parse_dates=["Date"],
    index_col="Date",
)


soxx = pd.read_csv(
    "data/SOXX.csv",
    parse_dates=["Date"],
    index_col="Date",
)


vix = pd.read_csv(
    "data/VIX.csv",
    parse_dates=["Date"],
    index_col="Date",
)


# Sort trades chronologically

trades = trades.sort_values(
    "signal_date"
).reset_index(drop=True)


print()
print("=" * 100)
print("STEP 13 — EVENT CLUSTERING")
print("=" * 100)

print()
print(f"Trade observations: {len(trades)}")

print(
    f"Trade dates: "
    f"{trades['signal_date'].min()} → "
    f"{trades['signal_date'].max()}"
)


# ============================================================
# 3. BUILD MARKET CONTEXT FEATURES
# ============================================================


# ------------------------------------------------------------
# QQQ FEATURES
# ------------------------------------------------------------

qqq["return_1d"] = (
    qqq["Close"]
    .pct_change(1)
)


qqq["return_5d"] = (
    qqq["Close"]
    .pct_change(5)
)


qqq["return_20d"] = (
    qqq["Close"]
    .pct_change(20)
)


qqq["ma_20"] = (
    qqq["Close"]
    .rolling(20)
    .mean()
)


qqq["ma_50"] = (
    qqq["Close"]
    .rolling(50)
    .mean()
)


qqq["ma_200"] = (
    qqq["Close"]
    .rolling(200)
    .mean()
)


# Distance above/below moving averages

qqq["trend_20"] = (
    qqq["Close"]
    / qqq["ma_20"]
) - 1


qqq["trend_50"] = (
    qqq["Close"]
    / qqq["ma_50"]
) - 1


qqq["trend_200"] = (
    qqq["Close"]
    / qqq["ma_200"]
) - 1


# 50-day MA slope:
# how much the MA itself changed over the last 10 days

qqq["ma50_slope_10d"] = (
    qqq["ma_50"]
    .pct_change(10)
)


# 200-day MA slope

qqq["ma200_slope_20d"] = (
    qqq["ma_200"]
    .pct_change(20)
)


# Recent realized volatility

qqq["volatility_20d"] = (
    qqq["return_1d"]
    .rolling(20)
    .std()
)


# ------------------------------------------------------------
# SOXX FEATURES
# ------------------------------------------------------------

soxx["return_1d"] = (
    soxx["Close"]
    .pct_change(1)
)


soxx["return_5d"] = (
    soxx["Close"]
    .pct_change(5)
)


soxx["return_20d"] = (
    soxx["Close"]
    .pct_change(20)
)


soxx["ma_20"] = (
    soxx["Close"]
    .rolling(20)
    .mean()
)


soxx["ma_50"] = (
    soxx["Close"]
    .rolling(50)
    .mean()
)


soxx["ma_200"] = (
    soxx["Close"]
    .rolling(200)
    .mean()
)


soxx["trend_20"] = (
    soxx["Close"]
    / soxx["ma_20"]
) - 1


soxx["trend_50"] = (
    soxx["Close"]
    / soxx["ma_50"]
) - 1


soxx["trend_200"] = (
    soxx["Close"]
    / soxx["ma_200"]
) - 1


soxx["ma50_slope_10d"] = (
    soxx["ma_50"]
    .pct_change(10)
)


# ------------------------------------------------------------
# VIX FEATURES
# ------------------------------------------------------------

vix["change_1d"] = (
    vix["Close"]
    .pct_change(1)
)


vix["change_5d"] = (
    vix["Close"]
    .pct_change(5)
)


vix["change_20d"] = (
    vix["Close"]
    .pct_change(20)
)


vix["ma_20"] = (
    vix["Close"]
    .rolling(20)
    .mean()
)


vix["vs_ma20"] = (
    vix["Close"]
    / vix["ma_20"]
) - 1


# ============================================================
# 4. CLUSTER TRADES INTO EVENTS
# ============================================================

event_ids = []

current_event_id = 0

previous_signal_date = None


for signal_date in trades["signal_date"]:

    # First trade starts Event 1

    if previous_signal_date is None:

        current_event_id = 1


    else:

        gap_days = (
            signal_date
            - previous_signal_date
        ).days


        # If gap is larger than threshold,
        # begin a new event

        if gap_days > EVENT_GAP_DAYS:

            current_event_id += 1


    event_ids.append(
        current_event_id
    )


    previous_signal_date = (
        signal_date
    )


trades["event_id"] = event_ids


print()
print(
    f"Distinct clustered events: "
    f"{trades['event_id'].nunique()}"
)


# ============================================================
# 5. BUILD EVENT-LEVEL SUMMARY
# ============================================================

event_rows = []


for event_id, group in trades.groupby(
    "event_id"
):

    group = group.sort_values(
        "signal_date"
    )


    event_start = (
        group["signal_date"]
        .min()
    )


    event_end = (
        group["signal_date"]
        .max()
    )


    # --------------------------------------------------------
    # EVENT OUTCOMES
    # --------------------------------------------------------

    avg_return = (
        group["return"]
        .mean()
    )


    median_return = (
        group["return"]
        .median()
    )


    win_rate = (
        group["winner"]
        .mean()
    )


    # Define event success using median return.
    #
    # This avoids one extreme asset dominating the event label.

    event_winner = (
        median_return > 0
    )


    assets = sorted(
        group["asset"]
        .unique()
        .tolist()
    )


    assets_string = ",".join(
        assets
    )


    # --------------------------------------------------------
    # GET MARKET CONTEXT ON EVENT START DATE
    # --------------------------------------------------------

    if event_start not in qqq.index:
        continue

    if event_start not in soxx.index:
        continue

    if event_start not in vix.index:
        continue


    row = {

        # Event identity

        "event_id":
            event_id,

        "event_start":
            event_start,

        "event_end":
            event_end,

        "event_duration_days":
            (
                event_end
                - event_start
            ).days,


        # Breadth

        "trade_observations":
            len(group),

        "unique_assets":
            group[
                "asset"
            ].nunique(),

        "assets":
            assets_string,


        # Outcomes

        "avg_return":
            avg_return,

        "median_return":
            median_return,

        "win_rate":
            win_rate,

        "best_return":
            group[
                "return"
            ].max(),

        "worst_return":
            group[
                "return"
            ].min(),

        "event_winner":
            event_winner,


        # ====================================================
        # QQQ CONTEXT
        # ====================================================

        "qqq_return_1d":
            qqq.loc[
                event_start,
                "return_1d"
            ],

        "qqq_return_5d":
            qqq.loc[
                event_start,
                "return_5d"
            ],

        "qqq_return_20d":
            qqq.loc[
                event_start,
                "return_20d"
            ],

        "qqq_trend_20":
            qqq.loc[
                event_start,
                "trend_20"
            ],

        "qqq_trend_50":
            qqq.loc[
                event_start,
                "trend_50"
            ],

        "qqq_trend_200":
            qqq.loc[
                event_start,
                "trend_200"
            ],

        "qqq_ma50_slope_10d":
            qqq.loc[
                event_start,
                "ma50_slope_10d"
            ],

        "qqq_ma200_slope_20d":
            qqq.loc[
                event_start,
                "ma200_slope_20d"
            ],

        "qqq_volatility_20d":
            qqq.loc[
                event_start,
                "volatility_20d"
            ],


        # ====================================================
        # SOXX CONTEXT
        # ====================================================

        "soxx_return_1d":
            soxx.loc[
                event_start,
                "return_1d"
            ],

        "soxx_return_5d":
            soxx.loc[
                event_start,
                "return_5d"
            ],

        "soxx_return_20d":
            soxx.loc[
                event_start,
                "return_20d"
            ],

        "soxx_trend_20":
            soxx.loc[
                event_start,
                "trend_20"
            ],

        "soxx_trend_50":
            soxx.loc[
                event_start,
                "trend_50"
            ],

        "soxx_trend_200":
            soxx.loc[
                event_start,
                "trend_200"
            ],

        "soxx_ma50_slope_10d":
            soxx.loc[
                event_start,
                "ma50_slope_10d"
            ],


        # ====================================================
        # VIX CONTEXT
        # ====================================================

        "vix_level":
            vix.loc[
                event_start,
                "Close"
            ],

        "vix_change_1d":
            vix.loc[
                event_start,
                "change_1d"
            ],

        "vix_change_5d":
            vix.loc[
                event_start,
                "change_5d"
            ],

        "vix_change_20d":
            vix.loc[
                event_start,
                "change_20d"
            ],

        "vix_vs_ma20":
            vix.loc[
                event_start,
                "vs_ma20"
            ],
    }


    event_rows.append(
        row
    )


events = pd.DataFrame(
    event_rows
)


# ============================================================
# 6. WINNING VS LOSING EVENT COMPARISON
# ============================================================

feature_columns = [

    # Breadth
    "trade_observations",
    "unique_assets",

    # QQQ
    "qqq_return_1d",
    "qqq_return_5d",
    "qqq_return_20d",
    "qqq_trend_20",
    "qqq_trend_50",
    "qqq_trend_200",
    "qqq_ma50_slope_10d",
    "qqq_ma200_slope_20d",
    "qqq_volatility_20d",

    # SOXX
    "soxx_return_1d",
    "soxx_return_5d",
    "soxx_return_20d",
    "soxx_trend_20",
    "soxx_trend_50",
    "soxx_trend_200",
    "soxx_ma50_slope_10d",

    # VIX
    "vix_level",
    "vix_change_1d",
    "vix_change_5d",
    "vix_change_20d",
    "vix_vs_ma20",
]


means = (

    events

    .groupby(
        "event_winner"
    )[feature_columns]

    .mean()

    .T
)


# Safely rename columns

rename_map = {}

if False in means.columns:
    rename_map[False] = "losing_events_avg"

if True in means.columns:
    rename_map[True] = "winning_events_avg"


means = means.rename(
    columns=rename_map
)


if (
    "losing_events_avg"
    in means.columns
    and
    "winning_events_avg"
    in means.columns
):

    means["difference"] = (

        means[
            "winning_events_avg"
        ]

        -

        means[
            "losing_events_avg"
        ]
    )


# ============================================================
# 7. MEDIAN COMPARISON
# ============================================================

medians = (

    events

    .groupby(
        "event_winner"
    )[feature_columns]

    .median()

    .T
)


rename_map = {}

if False in medians.columns:
    rename_map[False] = "losing_events_median"

if True in medians.columns:
    rename_map[True] = "winning_events_median"


medians = medians.rename(
    columns=rename_map
)


if (
    "losing_events_median"
    in medians.columns
    and
    "winning_events_median"
    in medians.columns
):

    medians["difference"] = (

        medians[
            "winning_events_median"
        ]

        -

        medians[
            "losing_events_median"
        ]
    )


# ============================================================
# 8. FEATURE CORRELATIONS WITH EVENT RETURN
# ============================================================

correlation_data = events[
    feature_columns
    + ["median_return"]
].copy()


correlations = (

    correlation_data

    .corr(
        numeric_only=True
    )["median_return"]

    .drop(
        "median_return"
    )

    .sort_values(
        ascending=False
    )

    .rename(
        "correlation_with_event_return"
    )

    .to_frame()
)


# ============================================================
# 9. MEDIAN-SPLIT ANALYSIS
# ============================================================

split_rows = []


for feature in feature_columns:

    valid = events[
        [
            feature,
            "median_return",
            "event_winner",
        ]
    ].dropna()


    if len(valid) == 0:
        continue


    split_value = (
        valid[feature]
        .median()
    )


    low_group = valid[
        valid[feature]
        <= split_value
    ]


    high_group = valid[
        valid[feature]
        > split_value
    ]


    split_rows.append({

        "feature":
            feature,

        "split_value":
            split_value,


        # Low group

        "low_events":
            len(low_group),

        "low_avg_event_return":
            low_group[
                "median_return"
            ].mean(),

        "low_win_rate":
            low_group[
                "event_winner"
            ].mean(),


        # High group

        "high_events":
            len(high_group),

        "high_avg_event_return":
            high_group[
                "median_return"
            ].mean(),

        "high_win_rate":
            high_group[
                "event_winner"
            ].mean(),
    })


split_analysis = pd.DataFrame(
    split_rows
)


# ============================================================
# 10. YEAR-BY-YEAR EVENT SUMMARY
# ============================================================

events["year"] = (

    pd.to_datetime(
        events["event_start"]
    )

    .dt.year
)


yearly_events = (

    events

    .groupby("year")

    .agg(

        events=(
            "event_id",
            "count"
        ),

        winning_events=(
            "event_winner",
            "sum"
        ),

        event_win_rate=(
            "event_winner",
            "mean"
        ),

        avg_event_return=(
            "median_return",
            "mean"
        ),

        median_event_return=(
            "median_return",
            "median"
        ),

        avg_assets_triggered=(
            "unique_assets",
            "mean"
        ),
    )

    .reset_index()
)


# ============================================================
# 11. EVENT DETAIL TABLE
# ============================================================

event_detail_columns = [

    "event_id",
    "event_start",
    "event_end",

    "trade_observations",
    "unique_assets",
    "assets",

    "avg_return",
    "median_return",
    "win_rate",
    "event_winner",

    "qqq_trend_20",
    "qqq_trend_50",
    "qqq_trend_200",

    "qqq_ma50_slope_10d",

    "soxx_trend_20",
    "soxx_trend_50",
    "soxx_trend_200",

    "vix_level",
    "vix_change_5d",
]


event_details = events[
    event_detail_columns
].copy()


# Sort worst events first

event_details = (
    event_details
    .sort_values(
        "median_return",
        ascending=True
    )
)


# ============================================================
# 12. SAVE OUTPUT FILES
# ============================================================

trades.to_csv(
    "data/event_clustered_trades.csv",
    index=False,
)


events.to_csv(
    "data/event_summary.csv",
    index=False,
)


event_details.to_csv(
    "data/event_details.csv",
    index=False,
)


means.to_csv(
    "data/event_winner_loser_means.csv"
)


medians.to_csv(
    "data/event_winner_loser_medians.csv"
)


correlations.to_csv(
    "data/event_feature_correlations.csv"
)


split_analysis.to_csv(
    "data/event_feature_splits.csv",
    index=False,
)


yearly_events.to_csv(
    "data/event_yearly_summary.csv",
    index=False,
)


# ============================================================
# 13. PRINT MAIN RESULTS
# ============================================================

print()
print("=" * 100)
print("EVENT SUMMARY")
print("=" * 100)
print()


print(
    f"Original trade observations: "
    f"{len(trades)}"
)


print(
    f"Distinct market events: "
    f"{len(events)}"
)


print(
    f"Winning events: "
    f"{events['event_winner'].sum()}"
)


print(
    f"Losing events: "
    f"{(~events['event_winner']).sum()}"
)


print(
    f"Event win rate: "
    f"{events['event_winner'].mean():.2%}"
)


print(
    f"Average event median return: "
    f"{events['median_return'].mean():.2%}"
)


print(
    f"Median event return: "
    f"{events['median_return'].median():.2%}"
)


# ============================================================
# 14. PRINT WORST EVENTS
# ============================================================

print()
print("=" * 100)
print("WORST EVENTS")
print("=" * 100)
print()


worst_events = (

    event_details

    .head(10)
)


print(
    worst_events.to_string(

        index=False,

        formatters={

            "avg_return":
                "{:.2%}".format,

            "median_return":
                "{:.2%}".format,

            "win_rate":
                "{:.2%}".format,

            "qqq_trend_20":
                "{:.2%}".format,

            "qqq_trend_50":
                "{:.2%}".format,

            "qqq_trend_200":
                "{:.2%}".format,

            "qqq_ma50_slope_10d":
                "{:.2%}".format,

            "soxx_trend_20":
                "{:.2%}".format,

            "soxx_trend_50":
                "{:.2%}".format,

            "soxx_trend_200":
                "{:.2%}".format,

            "vix_change_5d":
                "{:.2%}".format,
        }
    )
)


# ============================================================
# 15. PRINT CORRELATIONS
# ============================================================

print()
print("=" * 100)
print("FEATURE CORRELATIONS WITH EVENT RETURN")
print("=" * 100)
print()


print(
    correlations.to_string()
)


# ============================================================
# 16. PRINT YEARLY EVENT RESULTS
# ============================================================

print()
print("=" * 100)
print("YEAR-BY-YEAR EVENT RESULTS")
print("=" * 100)
print()


print(
    yearly_events.to_string(

        index=False,

        formatters={

            "event_win_rate":
                "{:.2%}".format,

            "avg_event_return":
                "{:.2%}".format,

            "median_event_return":
                "{:.2%}".format,

            "avg_assets_triggered":
                "{:.2f}".format,
        }
    )
)


# ============================================================
# 17. FINAL MESSAGE
# ============================================================

print()
print("Files saved:")

print(
    "data/event_clustered_trades.csv"
)

print(
    "data/event_summary.csv"
)

print(
    "data/event_details.csv"
)

print(
    "data/event_winner_loser_means.csv"
)

print(
    "data/event_winner_loser_medians.csv"
)

print(
    "data/event_feature_correlations.csv"
)

print(
    "data/event_feature_splits.csv"
)

print(
    "data/event_yearly_summary.csv"
)