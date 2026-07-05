import yfinance as yf
import pandas as pd
import json
from pathlib import Path
from datetime import datetime


# ============================================================
# 1. SETTINGS
# ============================================================

PAPER_STARTING_CAPITAL = 10_000.0

POSITION_FRACTION = 0.50

Z_WINDOW = 20
Z_THRESHOLD = -1.75

QQQ_MA_WINDOW = 50

STOP_LOSS = -0.12
PROFIT_TARGET = 0.20
MAX_HOLD_DAYS = 5

SLIPPAGE = 0.001


DATA_DIR = Path("data") / "paper"

STATE_FILE = DATA_DIR / "paper_state.json"

LOG_FILE = DATA_DIR / "paper_trade_log.csv"

DAILY_LOG_FILE = DATA_DIR / "paper_daily_log.csv"


DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 2. DEFAULT STATE
# ============================================================

DEFAULT_STATE = {

    "paper_equity":
        PAPER_STARTING_CAPITAL,

    "cash":
        PAPER_STARTING_CAPITAL,

    "in_position":
        False,

    "pending_entry":
        False,

    "signal_date":
        None,

    "entry_date":
        None,

    "entry_price":
        None,

    "shares":
        0.0,

    "invested_capital":
        0.0,

    "stop_price":
        None,

    "target_price":
        None,

    "days_held":
        0,
}


# ============================================================
# 3. LOAD / SAVE STATE
# ============================================================

def load_state():

    if not STATE_FILE.exists():

        save_state(
            DEFAULT_STATE.copy()
        )

        return DEFAULT_STATE.copy()


    with open(
        STATE_FILE,
        "r",
    ) as file:

        return json.load(file)


def save_state(
    state,
):

    with open(
        STATE_FILE,
        "w",
    ) as file:

        json.dump(
            state,
            file,
            indent=4,
        )


# ============================================================
# 4. DOWNLOAD LATEST MARKET DATA
# ============================================================

def download_data(
    ticker,
):

    print(
        f"Downloading {ticker}..."
    )


    df = yf.download(
        ticker,
        period="1y",
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


    df.index = pd.to_datetime(
        df.index
    )


    return df


soxl = download_data(
    "SOXL"
)

qqq = download_data(
    "QQQ"
)


# ============================================================
# 5. BUILD FEATURES
# ============================================================

soxl["ma_20"] = (

    soxl["Close"]

    .rolling(
        Z_WINDOW
    )

    .mean()
)


soxl["std_20"] = (

    soxl["Close"]

    .rolling(
        Z_WINDOW
    )

    .std()
)


soxl["z_score"] = (

    (
        soxl["Close"]
        - soxl["ma_20"]
    )

    / soxl["std_20"]
)


qqq["ma_50"] = (

    qqq["Close"]

    .rolling(
        QQQ_MA_WINDOW
    )

    .mean()
)


qqq["above_ma50"] = (

    qqq["Close"]

    > qqq["ma_50"]
)


# ============================================================
# 6. ALIGN DATA
# ============================================================

soxl["qqq_close"] = (

    qqq["Close"]

    .reindex(
        soxl.index
    )
)


soxl["qqq_ma50"] = (

    qqq["ma_50"]

    .reindex(
        soxl.index
    )
)


soxl["qqq_above_ma50"] = (

    qqq["above_ma50"]

    .reindex(
        soxl.index
    )

    .fillna(False)
)


# ============================================================
# 7. CREATE SIGNAL
# ============================================================

soxl["oversold"] = (

    soxl["z_score"]

    < Z_THRESHOLD
)


soxl["episode_start"] = (

    soxl["oversold"]

    &

    ~soxl["oversold"].shift(
        1,
        fill_value=False,
    )
)


soxl["buy_signal"] = (

    soxl["episode_start"]

    &

    soxl["qqq_above_ma50"]
)


# ============================================================
# 8. GET LATEST COMPLETED BAR
# ============================================================

latest_date = (
    soxl.index[-1]
)


latest = (
    soxl.iloc[-1]
)


previous_date = (

    soxl.index[-2]

    if len(soxl) >= 2

    else None
)


print()

print("=" * 90)

print(
    "SOXL PAPER BOT"
)

print("=" * 90)

print()

print(
    f"Latest market date: "
    f"{latest_date.date()}"
)

print(
    f"SOXL close: "
    f"${latest['Close']:.2f}"
)

print(
    f"SOXL z-score: "
    f"{latest['z_score']:.3f}"
)

print(
    f"QQQ close: "
    f"${latest['qqq_close']:.2f}"
)

print(
    f"QQQ MA50: "
    f"${latest['qqq_ma50']:.2f}"
)

print(
    f"QQQ above MA50: "
    f"{bool(latest['qqq_above_ma50'])}"
)

print(
    f"Oversold episode start: "
    f"{bool(latest['episode_start'])}"
)

print(
    f"Buy signal: "
    f"{bool(latest['buy_signal'])}"
)


# ============================================================
# 9. LOAD PAPER ACCOUNT
# ============================================================

state = load_state()


print()

print("-" * 90)

print("PAPER ACCOUNT")

print("-" * 90)

print()

print(
    f"Paper equity: "
    f"${state['paper_equity']:,.2f}"
)

print(
    f"Cash: "
    f"${state['cash']:,.2f}"
)

print(
    f"In position: "
    f"{state['in_position']}"
)

print(
    f"Pending entry: "
    f"{state['pending_entry']}"
)


# ============================================================
# 10. HELPER: APPEND CSV ROW
# ============================================================

def append_csv(
    filepath,
    row,
):

    row_df = pd.DataFrame(
        [row]
    )


    if filepath.exists():

        row_df.to_csv(
            filepath,
            mode="a",
            header=False,
            index=False,
        )


    else:

        row_df.to_csv(
            filepath,
            index=False,
        )


# ============================================================
# 11. DETERMINE ACTION
# ============================================================

action = "NO TRADE"

reason = "No valid entry signal."


# ============================================================
# 12. HANDLE PENDING ENTRY
#
# A signal happens after market close.
#
# We cannot know tomorrow's opening price yet.
#
# Therefore:
# Day 1 close -> BUY NEXT OPEN
# Next run after that open/day -> simulate entry
# ============================================================

if (
    state["pending_entry"]
    and
    not state["in_position"]
):

    signal_date = pd.Timestamp(
        state["signal_date"]
    )


    newer_rows = soxl[
        soxl.index
        > signal_date
    ]


    if len(newer_rows) > 0:

        entry_date = (
            newer_rows.index[0]
        )


        raw_entry_price = (

            newer_rows.iloc[0][
                "Open"
            ]
        )


        entry_price = (

            raw_entry_price

            * (
                1 + SLIPPAGE
            )
        )


        capital_before = (

            state[
                "paper_equity"
            ]
        )


        invested_capital = (

            capital_before

            * POSITION_FRACTION
        )


        cash = (

            capital_before

            - invested_capital
        )


        shares = (

            invested_capital

            / entry_price
        )


        stop_price = (

            entry_price

            * (
                1 + STOP_LOSS
            )
        )


        target_price = (

            entry_price

            * (
                1 + PROFIT_TARGET
            )
        )


        state.update({

            "cash":
                cash,

            "in_position":
                True,

            "pending_entry":
                False,

            "entry_date":
                str(
                    entry_date.date()
                ),

            "entry_price":
                float(
                    entry_price
                ),

            "shares":
                float(
                    shares
                ),

            "invested_capital":
                float(
                    invested_capital
                ),

            "stop_price":
                float(
                    stop_price
                ),

            "target_price":
                float(
                    target_price
                ),

            "days_held":
                0,
        })


        save_state(
            state
        )


        action = "HOLD"


        reason = (

            f"Paper entry filled at "
            f"${entry_price:.2f} on "
            f"{entry_date.date()}."
        )


# ============================================================
# 13. HANDLE EXISTING POSITION
# ============================================================

if state["in_position"]:

    entry_date = pd.Timestamp(
        state["entry_date"]
    )


    position_rows = soxl[
        soxl.index
        >= entry_date
    ]


    if len(position_rows) > 0:

        latest_position_bar = (
            position_rows.iloc[-1]
        )


        current_date = (
            position_rows.index[-1]
        )


        days_held = len(
            position_rows
        )


        state[
            "days_held"
        ] = days_held


        stop_price = (
            state["stop_price"]
        )


        target_price = (
            state["target_price"]
        )


        hit_stop = (

            latest_position_bar[
                "Low"
            ]

            <= stop_price
        )


        hit_target = (

            latest_position_bar[
                "High"
            ]

            >= target_price
        )


        exit_price = None

        exit_reason = None


        # Conservative:
        # if both hit on same candle,
        # assume stop first.

        if hit_stop and hit_target:

            exit_price = (

                stop_price

                * (
                    1 - SLIPPAGE
                )
            )


            exit_reason = (
                "STOP — both stop and target "
                "touched; assuming stop first"
            )


        elif hit_stop:

            exit_price = (

                stop_price

                * (
                    1 - SLIPPAGE
                )
            )


            exit_reason = "STOP LOSS"


        elif hit_target:

            exit_price = (

                target_price

                * (
                    1 - SLIPPAGE
                )
            )


            exit_reason = (
                "PROFIT TARGET"
            )


        elif days_held >= MAX_HOLD_DAYS:

            exit_price = (

                latest_position_bar[
                    "Close"
                ]

                * (
                    1 - SLIPPAGE
                )
            )


            exit_reason = (
                "MAX HOLD TIME"
            )


        # ----------------------------------------------------
        # EXIT POSITION
        # ----------------------------------------------------

        if exit_price is not None:

            position_value = (

                state["shares"]

                * exit_price
            )


            final_equity = (

                state["cash"]

                + position_value
            )


            position_return = (

                exit_price

                / state["entry_price"]

            ) - 1


            account_return = (

                final_equity

                / state[
                    "paper_equity"
                ]

            ) - 1


            trade_row = {

                "signal_date":
                    state[
                        "signal_date"
                    ],

                "entry_date":
                    state[
                        "entry_date"
                    ],

                "exit_date":
                    str(
                        current_date.date()
                    ),

                "entry_price":
                    state[
                        "entry_price"
                    ],

                "exit_price":
                    exit_price,

                "shares":
                    state[
                        "shares"
                    ],

                "position_return":
                    position_return,

                "account_return":
                    account_return,

                "equity_after":
                    final_equity,

                "exit_reason":
                    exit_reason,
            }


            append_csv(

                LOG_FILE,

                trade_row,
            )


            state = {

                "paper_equity":
                    float(
                        final_equity
                    ),

                "cash":
                    float(
                        final_equity
                    ),

                "in_position":
                    False,

                "pending_entry":
                    False,

                "signal_date":
                    None,

                "entry_date":
                    None,

                "entry_price":
                    None,

                "shares":
                    0.0,

                "invested_capital":
                    0.0,

                "stop_price":
                    None,

                "target_price":
                    None,

                "days_held":
                    0,
            }


            save_state(
                state
            )


            action = "SELL"


            reason = (

                f"{exit_reason}. "
                f"Paper exit at "
                f"${exit_price:.2f}."
            )


        else:

            current_position_value = (

                state["shares"]

                * latest_position_bar[
                    "Close"
                ]
            )


            mark_to_market_equity = (

                state["cash"]

                + current_position_value
            )


            action = "HOLD"


            reason = (

                f"Position open. "
                f"Day {days_held} of "
                f"{MAX_HOLD_DAYS}. "
                f"Marked equity: "
                f"${mark_to_market_equity:,.2f}."
            )


            save_state(
                state
            )


# ============================================================
# 14. CHECK FOR NEW ENTRY SIGNAL
# ============================================================

elif (
    not state["pending_entry"]
    and
    bool(latest["buy_signal"])
):

    state[
        "pending_entry"
    ] = True


    state[
        "signal_date"
    ] = str(
        latest_date.date()
    )


    save_state(
        state
    )


    action = "BUY NEXT OPEN"


    reason = (

        f"SOXL z-score is "
        f"{latest['z_score']:.3f}, "
        f"this is a new oversold episode, "
        f"and QQQ is above MA50."
    )


# ============================================================
# 15. DAILY LOG
# ============================================================

daily_row = {

    "run_timestamp":
        datetime.now().isoformat(),

    "market_date":
        str(
            latest_date.date()
        ),

    "soxl_close":
        float(
            latest["Close"]
        ),

    "soxl_z_score":
        float(
            latest["z_score"]
        ),

    "qqq_close":
        float(
            latest["qqq_close"]
        ),

    "qqq_ma50":
        float(
            latest["qqq_ma50"]
        ),

    "qqq_above_ma50":
        bool(
            latest[
                "qqq_above_ma50"
            ]
        ),

    "episode_start":
        bool(
            latest[
                "episode_start"
            ]
        ),

    "buy_signal":
        bool(
            latest[
                "buy_signal"
            ]
        ),

    "action":
        action,

    "reason":
        reason,

    "paper_equity":
        state[
            "paper_equity"
        ],

    "in_position":
        state[
            "in_position"
        ],

    "pending_entry":
        state[
            "pending_entry"
        ],
}


append_csv(

    DAILY_LOG_FILE,

    daily_row,
)


# ============================================================
# 16. FINAL OUTPUT
# ============================================================

print()

print("=" * 90)

print("TODAY'S PAPER ACTION")

print("=" * 90)

print()

print(
    f"ACTION: {action}"
)

print()

print(
    f"REASON: {reason}"
)

print()


if state["in_position"]:

    print(
        f"Entry price: "
        f"${state['entry_price']:.2f}"
    )

    print(
        f"Stop price: "
        f"${state['stop_price']:.2f}"
    )

    print(
        f"Target price: "
        f"${state['target_price']:.2f}"
    )

    print(
        f"Shares: "
        f"{state['shares']:.4f}"
    )

    print(
        f"Days held: "
        f"{state['days_held']}"
    )


print()

print("State file:")

print(
    STATE_FILE
)

print()

print("Daily log:")

print(
    DAILY_LOG_FILE
)

print()

print("Completed trades:")

print(
    LOG_FILE
)
