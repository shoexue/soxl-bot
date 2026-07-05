import pandas as pd


# ============================================================
# 1. LOAD DATA
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


# Only use the recent 5-year regime
soxl = soxl[soxl.index >= "2021-07-05"].copy()


# ============================================================
# 2. CREATE SOXL FEATURES
# ============================================================

# Daily return
soxl["return_1d"] = soxl["Close"].pct_change(1)

# Previous 5 trading-day return
soxl["return_5d"] = soxl["Close"].pct_change(5)


# 20-day realized daily volatility
soxl["volatility_20d"] = (
    soxl["return_1d"]
    .rolling(20)
    .std()
)


# Average volume over previous 20 trading days
soxl["volume_avg_20d"] = (
    soxl["Volume"]
    .rolling(20)
    .mean()
)


# Today's volume relative to recent average
soxl["volume_ratio"] = (
    soxl["Volume"]
    / soxl["volume_avg_20d"]
)


# ============================================================
# 3. CREATE MARKET CONTEXT FEATURES
# ============================================================

# ------------------------
# QQQ trend
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
# SOXX trend
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
# VIX change
# ------------------------

vix["change_5d"] = (
    vix["Close"]
    .pct_change(5)
)


# ============================================================
# 4. FIND SIGNAL EPISODES
# ============================================================

threshold = -1.75

signal = (
    soxl["z_score"]
    < threshold
)


# Only count the first day of each consecutive signal cluster
episode_start = (
    signal
    & ~signal.shift(1, fill_value=False)
)


signal_dates = soxl.index[
    episode_start
]


print(
    f"Found {len(signal_dates)} signal episodes"
)


# ============================================================
# 5. CREATE ONE ROW PER TRADE
# ============================================================

trades = []


for signal_date in signal_dates:

    signal_pos = soxl.index.get_loc(
        signal_date
    )


    # Enter on next trading day
    entry_pos = signal_pos + 1


    # Need at least 10 future trading sessions
    if entry_pos + 9 >= len(soxl):
        continue


    entry_date = soxl.index[
        entry_pos
    ]


    entry_price = soxl.iloc[
        entry_pos
    ]["Open"]


    # ========================================================
    # CHECK CONTEXT DATA EXISTS
    # ========================================================

    if signal_date not in qqq.index:
        continue

    if signal_date not in soxx.index:
        continue

    if signal_date not in vix.index:
        continue


    # ========================================================
    # FUTURE 10-DAY PRICE PATH
    # ========================================================

    future_10d = soxl.iloc[
        entry_pos : entry_pos + 10
    ]


    # ------------------------
    # Maximum Adverse Excursion
    # ------------------------
    #
    # Worst intraday low during the next 10 sessions
    # relative to entry price.

    mae_10d = (
        future_10d["Low"].min()
        / entry_price
    ) - 1


    # ------------------------
    # Maximum Favorable Excursion
    # ------------------------
    #
    # Best intraday high during the next 10 sessions
    # relative to entry price.

    mfe_10d = (
        future_10d["High"].max()
        / entry_price
    ) - 1


    # ========================================================
    # DAILY PATH RETURNS
    # ========================================================

    path_returns = {}


    for day in range(1, 11):

        day_pos = (
            entry_pos
            + day
            - 1
        )


        close_price = soxl.iloc[
            day_pos
        ]["Close"]


        path_returns[
            f"return_day_{day}"
        ] = (
            close_price
            / entry_price
        ) - 1


    # ========================================================
    # FIXED-HOLD EXIT RETURNS
    # ========================================================

    exit_3d = soxl.iloc[
        entry_pos + 2
    ]["Close"]


    exit_5d = soxl.iloc[
        entry_pos + 4
    ]["Close"]


    exit_10d = soxl.iloc[
        entry_pos + 9
    ]["Close"]


    # ========================================================
    # BUILD TRADE ROW
    # ========================================================

    trade = {

        # ------------------------
        # Trade identification
        # ------------------------

        "signal_date":
            signal_date,

        "entry_date":
            entry_date,

        "entry_price":
            entry_price,


        # ------------------------
        # SOXL signal features
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

        "volume_ratio":
            soxl.loc[
                signal_date,
                "volume_ratio"
            ],

        "volatility_20d":
            soxl.loc[
                signal_date,
                "volatility_20d"
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


        # ------------------------
        # Fixed-hold outcomes
        # ------------------------

        "return_3d":
            (
                exit_3d
                / entry_price
            ) - 1,

        "return_5d":
            (
                exit_5d
                / entry_price
            ) - 1,

        "return_10d":
            (
                exit_10d
                / entry_price
            ) - 1,


        # ------------------------
        # Path outcomes
        # ------------------------

        "mae_10d":
            mae_10d,

        "mfe_10d":
            mfe_10d,
    }


    # Add return_day_1 through return_day_10
    trade.update(
        path_returns
    )


    trades.append(
        trade
    )


# ============================================================
# 6. CREATE DATAFRAME
# ============================================================

trades_df = pd.DataFrame(
    trades
)


# ============================================================
# 7. SAVE DATASET
# ============================================================

trades_df.to_csv(
    "data/trade_dataset.csv",
    index=False
)


# ============================================================
# 8. PRINT SUMMARY
# ============================================================

print()

print(
    f"Created {len(trades_df)} trades"
)

print()


# Display first few trades

print(
    trades_df.head()
)


print()


# ============================================================
# 9. RETURN SUMMARY
# ============================================================

return_columns = [
    "return_3d",
    "return_5d",
    "return_10d",
    "mae_10d",
    "mfe_10d"
]


print("Return summary:")

print(
    trades_df[
        return_columns
    ].describe()
)


print()


# ============================================================
# 10. WIN RATES
# ============================================================

print("Win rates:")

print(
    "3 day:",
    (
        trades_df["return_3d"] > 0
    ).mean()
)

print(
    "5 day:",
    (
        trades_df["return_5d"] > 0
    ).mean()
)

print(
    "10 day:",
    (
        trades_df["return_10d"] > 0
    ).mean()
)


print()


# ============================================================
# 11. AVERAGE DAILY TRADE PATH
# ============================================================

path_columns = [
    f"return_day_{day}"
    for day in range(1, 11)
]


average_path = (
    trades_df[
        path_columns
    ]
    .mean()
)


median_path = (
    trades_df[
        path_columns
    ]
    .median()
)


print(
    "Average trade path:"
)

print(
    average_path
)


print()


print(
    "Median trade path:"
)

print(
    median_path
)