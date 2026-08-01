from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


DATA_DIR = Path("data")
INTRADAY_DIR = DATA_DIR / "intraday"
INTRADAY_BARS_FILE = INTRADAY_DIR / "soxl_intraday_bars.csv"
INTRADAY_SNAPSHOTS_FILE = INTRADAY_DIR / "soxl_intraday_snapshots.csv"
INTRADAY_30M_FILE = INTRADAY_DIR / "soxl_30m_shadow_signals.csv"
INTRADAY_30M_PAPER_STATE_FILE = INTRADAY_DIR / "soxl_30m_paper_state.json"
INTRADAY_30M_PAPER_LOG_FILE = INTRADAY_DIR / "soxl_30m_paper_log.csv"
INTRADAY_30M_TRADE_LOG_FILE = INTRADAY_DIR / "soxl_30m_trade_log.csv"
INTRADAY_30M_BACKTEST_BARS_FILE = INTRADAY_DIR / "soxl_30m_backtest_bars.csv"
INTRADAY_30M_BACKTEST_SUMMARY_FILE = INTRADAY_DIR / "soxl_30m_backtest_summary.csv"
INTRADAY_30M_BACKTEST_TRADES_FILE = INTRADAY_DIR / "soxl_30m_backtest_trades.csv"
INTRADAY_30M_BACKTEST_EQUITY_FILE = INTRADAY_DIR / "soxl_30m_backtest_equity.csv"
INTRADAY_30M_PARAMETER_COMPARISON_FILE = (
    INTRADAY_DIR / "soxl_30m_parameter_comparison.csv"
)
INTRADAY_30M_VALIDATION_FILE = INTRADAY_DIR / "soxl_30m_validation.csv"
INTRADAY_30M_ROBUSTNESS_FILE = INTRADAY_DIR / "soxl_30m_robustness.csv"
INTRADAY_DAILY_SHOCK_CONTEXT_FILE = (
    INTRADAY_DIR / "soxl_daily_shock_context.csv"
)
INTRADAY_DAILY_SHOCK_LATEST_FILE = (
    INTRADAY_DIR / "soxl_daily_shock_latest.csv"
)
INTRADAY_30M_CHALLENGER_FILE = (
    INTRADAY_DIR / "soxl_30m_adaptive_challenger_signals.csv"
)
INTRADAY_30M_CHALLENGER_BACKTEST_BARS_FILE = (
    INTRADAY_DIR / "soxl_30m_adaptive_challenger_backtest_bars.csv"
)
INTRADAY_30M_CHALLENGER_SUMMARY_FILE = (
    INTRADAY_DIR / "soxl_30m_adaptive_challenger_summary.csv"
)
INTRADAY_30M_CHALLENGER_TRADES_FILE = (
    INTRADAY_DIR / "soxl_30m_adaptive_challenger_trades.csv"
)
INTRADAY_30M_CHALLENGER_EQUITY_FILE = (
    INTRADAY_DIR / "soxl_30m_adaptive_challenger_equity.csv"
)
INTRADAY_30M_CHALLENGER_VALIDATION_FILE = (
    INTRADAY_DIR / "soxl_30m_adaptive_challenger_validation.csv"
)
OVERNIGHT_REBOUND_PAPER_STATE_FILE = (
    INTRADAY_DIR / "soxl_overnight_rebound_paper_state.json"
)
OVERNIGHT_REBOUND_PAPER_LOG_FILE = (
    INTRADAY_DIR / "soxl_overnight_rebound_paper_log.csv"
)
OVERNIGHT_REBOUND_TRADE_LOG_FILE = (
    INTRADAY_DIR / "soxl_overnight_rebound_trade_log.csv"
)

MARKET_TIMEZONE = ZoneInfo("America/New_York")
REGULAR_SESSION_START = "09:30"
REGULAR_SESSION_END = "16:00"
THIRTY_MINUTE_SESSION_BARS = 13

BAR_COLUMNS = [
    "timestamp",
    "market_date",
    "interval",
    "soxl_open",
    "soxl_high",
    "soxl_low",
    "soxl_close",
    "soxl_volume",
    "soxl_vwap",
    "soxl_from_open_pct",
    "soxl_from_high_pct",
    "soxl_from_low_pct",
    "soxl_range_pct",
    "qqq_close",
    "qqq_from_open_pct",
]

THIRTY_MINUTE_COLUMNS = [
    "timestamp",
    "market_date",
    "interval",
    "strategy_version",
    "soxl_open",
    "soxl_high",
    "soxl_low",
    "soxl_close",
    "soxl_volume",
    "soxl_vwap",
    "soxl_return_30m_pct",
    "soxl_z_5bar",
    "soxl_vs_vwap_pct",
    "soxl_from_open_pct",
    "soxl_from_high_pct",
    "soxl_from_low_pct",
    "soxl_session_range_pct",
    "bar_number",
    "qqq_close",
    "qqq_return_30m_pct",
    "qqq_from_open_pct",
    "bars_in_window",
    "oversold_30m",
    "episode_start_30m",
    "bars_since_episode_start_30m",
    "bounce_confirmed_30m",
    "regime_ok_30m",
    "entry_window_ok_30m",
    "shadow_signal",
    "shadow_action",
    "shadow_reason",
]

THIRTY_MINUTE_PAPER_LOG_COLUMNS = [
    "run_timestamp",
    "timestamp",
    "market_date",
    "strategy_version",
    "action",
    "reason",
    "shadow_signal",
    "shadow_action",
    "soxl_close",
    "soxl_z_5bar",
    "qqq_from_open_pct",
    "account_state",
    "in_position",
    "entry_timestamp",
    "entry_price",
    "shares",
    "bars_held",
    "position_market_value",
    "paper_cash",
    "paper_realized_equity",
    "paper_marked_equity",
    "current_position_return",
]

THIRTY_MINUTE_TRADE_LOG_COLUMNS = [
    "strategy_version",
    "entry_timestamp",
    "exit_timestamp",
    "entry_price",
    "exit_price",
    "shares",
    "bars_held",
    "position_return",
    "account_return",
    "equity_before_entry",
    "equity_after_exit",
    "entry_z",
    "exit_reason",
]

OVERNIGHT_REBOUND_PAPER_LOG_COLUMNS = [
    "event_id",
    "run_timestamp",
    "event_timestamp",
    "market_date",
    "strategy_version",
    "provenance",
    "is_backfill",
    "action",
    "reason",
    "signal_from_open_pct",
    "signal_price",
    "fill_price",
    "account_state",
    "paper_cash",
    "paper_realized_equity",
    "paper_marked_equity",
]

OVERNIGHT_REBOUND_TRADE_LOG_COLUMNS = [
    "trade_id",
    "strategy_version",
    "provenance",
    "is_backfill",
    "entry_timestamp",
    "exit_timestamp",
    "entry_market_date",
    "exit_market_date",
    "signal_from_open_pct",
    "entry_price",
    "exit_price",
    "shares",
    "position_return",
    "account_return",
    "equity_before_entry",
    "equity_after_exit",
    "exit_reason",
]

SNAPSHOT_COLUMNS = [
    "run_timestamp",
    "timestamp",
    "market_date",
    "interval",
    "watch_state",
    "reason",
    "soxl_open",
    "soxl_last",
    "soxl_session_high",
    "soxl_session_low",
    "soxl_vwap",
    "soxl_from_open_pct",
    "soxl_from_high_pct",
    "soxl_from_low_pct",
    "soxl_range_pct",
    "soxl_vs_vwap_pct",
    "qqq_last",
    "qqq_from_open_pct",
    "bars_observed",
    "data_warning",
]


class IntradayDataError(RuntimeError):
    """Raised when intraday data is unavailable or malformed."""


@dataclass(frozen=True)
class IntradayConfig:
    symbol: str = "SOXL"
    regime_symbol: str = "QQQ"
    interval: str = "5m"
    period: str = "5d"
    signal_interval: str = "30min"
    signal_z_window: int = 5
    signal_z_threshold: float = -1.25
    regime_floor_pct: float = -0.01
    strategy_version: str = "fast_30m_validated_v4"
    challenger_strategy_version: str = "adaptive_30m_research_v1"
    stress_strategy_version: str = "fast_30m_stress_guard_v5_research"
    challenger_min_pullback_from_high_pct: float = -0.01
    challenger_trend_from_open_pct: float = 0.02
    challenger_trend_qqq_floor_pct: float = 0.0
    challenger_prior_pullback_pct: float = -0.005
    overnight_strategy_version: str = "overnight_rebound_paper_v1"
    overnight_signal_from_open_pct: float = -0.05
    overnight_signal_bar_number: int = 12
    starting_capital: float = 10_000.0
    position_fraction: float = 0.50
    slippage: float = 0.001
    hold_bars: int = 3
    entry_style: str = "bounce_confirmation"
    bounce_wait_bars: int = 2
    require_vwap_reclaim: bool = False
    allow_overnight: bool = False
    session_signal_bars: int = THIRTY_MINUTE_SESSION_BARS
    max_history_years: int = 3
    backtest_period: str = "90d"
    extreme_range_pct: float = 0.10
    pullback_from_high_pct: float = -0.07
    bounce_from_low_pct: float = 0.07
    trend_move_pct: float = 0.06


@dataclass(frozen=True)
class IntradayPaths:
    bars_file: Path = INTRADAY_BARS_FILE
    snapshots_file: Path = INTRADAY_SNAPSHOTS_FILE
    thirty_minute_file: Path = INTRADAY_30M_FILE
    thirty_minute_challenger_file: Path = INTRADAY_30M_CHALLENGER_FILE
    thirty_minute_state_file: Path = INTRADAY_30M_PAPER_STATE_FILE
    thirty_minute_paper_log_file: Path = INTRADAY_30M_PAPER_LOG_FILE
    thirty_minute_trade_log_file: Path = INTRADAY_30M_TRADE_LOG_FILE
    overnight_state_file: Path = OVERNIGHT_REBOUND_PAPER_STATE_FILE
    overnight_paper_log_file: Path = OVERNIGHT_REBOUND_PAPER_LOG_FILE
    overnight_trade_log_file: Path = OVERNIGHT_REBOUND_TRADE_LOG_FILE


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return float(value)


def pct_change(current: Any, base: Any) -> float | None:
    current_number = to_float(current)
    base_number = to_float(base)
    if current_number is None or base_number in (None, 0):
        return None
    return current_number / base_number - 1


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def is_valid_number(value: Any) -> bool:
    number = to_float(value)
    return number is not None and math.isfinite(number)


def parse_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default.copy()
    try:
        with path.open("r") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        return default.copy()
    state = default.copy()
    state.update(payload)
    return state


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=4, sort_keys=True) + "\n")
    temp_path.replace(path)


def normalize_intraday_ohlcv(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    frame = data.copy()
    if frame.empty:
        raise IntradayDataError(f"{ticker} intraday data is empty.")

    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    for datetime_column in ("Datetime", "Date"):
        if datetime_column in frame.columns:
            frame[datetime_column] = pd.to_datetime(frame[datetime_column])
            frame = frame.set_index(datetime_column)
            break

    missing = [
        column
        for column in ("Open", "High", "Low", "Close", "Volume")
        if column not in frame.columns
    ]
    if missing:
        raise IntradayDataError(
            f"{ticker} intraday data is missing: {', '.join(missing)}"
        )

    frame = frame[["Open", "High", "Low", "Close", "Volume"]].copy()
    frame.index = pd.to_datetime(frame.index)
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize(MARKET_TIMEZONE)
    else:
        frame.index = frame.index.tz_convert(MARKET_TIMEZONE)

    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["Open", "High", "Low", "Close"])

    if frame.empty:
        raise IntradayDataError(f"{ticker} intraday data has no usable rows.")
    return frame


def download_yahoo_intraday(
    ticker: str,
    period: str,
    interval: str,
) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as error:
        raise IntradayDataError("Install yfinance to download intraday data.") from error

    data = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
    )
    return normalize_intraday_ohlcv(data, ticker=ticker)


def regular_session(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.between_time(
        REGULAR_SESSION_START,
        REGULAR_SESSION_END,
        inclusive="left",
    )


def latest_market_date(frame: pd.DataFrame) -> pd.Timestamp:
    if frame.empty:
        raise IntradayDataError("No intraday rows available.")
    latest_date = frame.index.max().date()
    return pd.Timestamp(latest_date)


def build_intraday_bars(
    soxl: pd.DataFrame,
    qqq: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> pd.DataFrame:
    soxl_session = regular_session(soxl)
    qqq_session = regular_session(qqq)
    session_date = latest_market_date(soxl_session)

    soxl_day = soxl_session[soxl_session.index.date == session_date.date()].copy()
    qqq_day = qqq_session[qqq_session.index.date == session_date.date()].copy()
    if soxl_day.empty:
        raise IntradayDataError("No SOXL rows for the latest regular session.")

    qqq_close = pd.Series(index=soxl_day.index, dtype="float64")
    qqq_from_open = pd.Series(index=soxl_day.index, dtype="float64")
    if not qqq_day.empty:
        aligned_qqq_close = qqq_day["Close"].reindex(soxl_day.index, method="ffill")
        qqq_open = qqq_day["Open"].iloc[0]
        qqq_close = aligned_qqq_close
        qqq_from_open = aligned_qqq_close.map(lambda value: pct_change(value, qqq_open))

    soxl_open = soxl_day["Open"].iloc[0]
    running_high = soxl_day["High"].cummax()
    running_low = soxl_day["Low"].cummin()
    cumulative_volume = soxl_day["Volume"].fillna(0).cumsum()
    cumulative_value = (soxl_day["Close"] * soxl_day["Volume"].fillna(0)).cumsum()
    vwap = cumulative_value.divide(cumulative_volume.where(cumulative_volume != 0))

    bars = pd.DataFrame(
        {
            "timestamp": [timestamp.isoformat() for timestamp in soxl_day.index],
            "market_date": str(session_date.date()),
            "interval": config.interval,
            "soxl_open": soxl_day["Open"],
            "soxl_high": soxl_day["High"],
            "soxl_low": soxl_day["Low"],
            "soxl_close": soxl_day["Close"],
            "soxl_volume": soxl_day["Volume"],
            "soxl_vwap": vwap,
            "soxl_from_open_pct": soxl_day["Close"].map(
                lambda value: pct_change(value, soxl_open)
            ),
            "soxl_from_high_pct": [
                pct_change(close, high)
                for close, high in zip(soxl_day["Close"], running_high, strict=False)
            ],
            "soxl_from_low_pct": [
                pct_change(close, low)
                for close, low in zip(soxl_day["Close"], running_low, strict=False)
            ],
            "soxl_range_pct": [
                pct_change(high, low)
                for high, low in zip(running_high, running_low, strict=False)
            ],
            "qqq_close": qqq_close,
            "qqq_from_open_pct": qqq_from_open,
        }
    )
    return bars[BAR_COLUMNS].reset_index(drop=True)


def expected_rows_per_signal_bar(config: IntradayConfig) -> int:
    if config.interval == "5m" and config.signal_interval in {"30m", "30min"}:
        return 6
    return 1


def apply_thirty_minute_signal_rules(
    frame: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=THIRTY_MINUTE_COLUMNS)

    signals = frame.copy()
    signals["strategy_version"] = config.strategy_version
    signals["soxl_z_5bar"] = (
        (
            signals["soxl_close"]
            - signals["soxl_close"].rolling(config.signal_z_window).mean()
        )
        / signals["soxl_close"].rolling(config.signal_z_window).std()
    )
    signals["oversold_30m"] = (
        signals["soxl_z_5bar"] <= config.signal_z_threshold
    ).fillna(False)
    signals["episode_start_30m"] = (
        signals["oversold_30m"]
        & ~signals["oversold_30m"].shift(1, fill_value=False)
    )
    if "market_date" in signals.columns:
        new_session = signals["market_date"] != signals["market_date"].shift(1)
        signals["episode_start_30m"] = signals["episode_start_30m"] | (
            signals["oversold_30m"] & new_session
        )
    signals["regime_ok_30m"] = (
        signals["qqq_from_open_pct"] >= config.regime_floor_pct
    ).fillna(False)
    if config.allow_overnight or "bar_number" not in signals.columns:
        signals["entry_window_ok_30m"] = True
    else:
        signals["entry_window_ok_30m"] = (
            pd.to_numeric(signals["bar_number"], errors="coerce") + config.hold_bars
            <= config.session_signal_bars
        ).fillna(False)
    signals["bars_since_episode_start_30m"] = pd.NA
    signals["bounce_confirmed_30m"] = False
    signals["shadow_signal"] = False
    actions = []
    reasons = []

    active_episode = False
    active_market_date = None
    bars_since_episode = 0
    previous_close = None

    for index, row in signals.iterrows():
        market_date = row.get("market_date")
        if active_episode and market_date != active_market_date:
            active_episode = False
            bars_since_episode = 0

        oversold = bool(row["oversold_30m"])
        episode_start = bool(row["episode_start_30m"])
        regime_ok = bool(row["regime_ok_30m"])
        entry_window_ok = bool(row["entry_window_ok_30m"])
        shadow_signal = False
        bounce_confirmed = False
        bars_since_value = pd.NA

        if episode_start:
            active_episode = True
            active_market_date = market_date
            bars_since_episode = 0
            bars_since_value = 0

        elif active_episode:
            bars_since_episode += 1
            bars_since_value = bars_since_episode

        if config.entry_style == "episode_start":
            shadow_signal = episode_start and regime_ok and entry_window_ok
        elif config.entry_style == "bounce_confirmation":
            if active_episode and not episode_start:
                close = to_float(row.get("soxl_close"))
                positive_bar = (to_float(row.get("soxl_return_30m_pct")) or 0.0) > 0
                higher_close = (
                    close is not None
                    and previous_close is not None
                    and close > previous_close
                )
                vwap_ok = (
                    not config.require_vwap_reclaim
                    or (to_float(row.get("soxl_vs_vwap_pct")) or 0.0) >= 0
                )
                bounce_confirmed = (
                    bars_since_episode <= config.bounce_wait_bars
                    and positive_bar
                    and higher_close
                    and vwap_ok
                )
                shadow_signal = bounce_confirmed and regime_ok
                shadow_signal = shadow_signal and entry_window_ok
        else:
            raise IntradayDataError(f"Unsupported 30-minute entry style: {config.entry_style}")

        if shadow_signal:
            active_episode = False
            actions.append("SHADOW_LONG_WATCH")
            if config.entry_style == "bounce_confirmation":
                reasons.append(
                    "30-minute SOXL bounce confirmed after an oversold reset while QQQ held up."
                )
            else:
                reasons.append(
                    "30-minute SOXL z-score reset while QQQ stayed above the intraday floor."
                )
        elif episode_start and not regime_ok:
            actions.append("REGIME_BLOCKED")
            reasons.append("30-minute SOXL reset fired, but QQQ intraday regime failed.")
        elif episode_start and not entry_window_ok:
            actions.append("TOO_LATE")
            reasons.append("30-minute reset fired too late to complete the same-day hold.")
        elif episode_start and config.entry_style == "bounce_confirmation":
            actions.append("OVERSOLD_WATCH")
            reasons.append("30-minute SOXL reset started; waiting for a bounce bar.")
        elif bounce_confirmed and not regime_ok:
            actions.append("REGIME_BLOCKED")
            reasons.append("SOXL bounced after the reset, but QQQ intraday regime failed.")
        elif bounce_confirmed and not entry_window_ok:
            actions.append("TOO_LATE")
            reasons.append("SOXL bounced, but there are not enough same-day bars left.")
        elif oversold:
            actions.append("OVERSOLD_WATCH")
            reasons.append("30-minute SOXL z-score is stretched lower.")
        else:
            actions.append("WAIT")
            reasons.append("No completed 30-minute shadow setup.")

        signals.at[index, "bars_since_episode_start_30m"] = bars_since_value
        signals.at[index, "bounce_confirmed_30m"] = bounce_confirmed
        signals.at[index, "shadow_signal"] = shadow_signal
        if active_episode and bars_since_episode >= config.bounce_wait_bars:
            active_episode = False
        previous_close = to_float(row.get("soxl_close"))

    signals["shadow_action"] = actions
    signals["shadow_reason"] = reasons
    return signals[THIRTY_MINUTE_COLUMNS].reset_index(drop=True)


def apply_adaptive_thirty_minute_challenger_rules(
    frame: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> pd.DataFrame:
    """Build a research-only two-lane challenger without changing live v4 signals."""
    signals = apply_thirty_minute_signal_rules(frame, config=config)
    if signals.empty:
        return signals

    baseline_reversion = signals["shadow_signal"].map(is_true)
    deep_reversion = baseline_reversion & (
        pd.to_numeric(signals["soxl_from_high_pct"], errors="coerce")
        <= config.challenger_min_pullback_from_high_pct
    ).fillna(False)

    previous_return = signals.groupby("market_date")["soxl_return_30m_pct"].shift(1)
    trend_pullback = (
        (
            pd.to_numeric(signals["soxl_from_open_pct"], errors="coerce")
            >= config.challenger_trend_from_open_pct
        )
        & (pd.to_numeric(signals["soxl_vs_vwap_pct"], errors="coerce") >= 0)
        & (
            pd.to_numeric(signals["qqq_from_open_pct"], errors="coerce")
            >= config.challenger_trend_qqq_floor_pct
        )
        & (pd.to_numeric(signals["soxl_return_30m_pct"], errors="coerce") > 0)
        & (previous_return <= config.challenger_prior_pullback_pct)
        & signals["entry_window_ok_30m"].map(is_true)
    ).fillna(False)

    signals["strategy_version"] = config.challenger_strategy_version
    signals["shadow_signal"] = deep_reversion | trend_pullback

    shallow_reversion = baseline_reversion & ~deep_reversion
    signals.loc[shallow_reversion, "shadow_action"] = "SHALLOW_REVERSION_BLOCKED"
    signals.loc[shallow_reversion, "shadow_reason"] = (
        "The v4 bounce was too close to the session high for the adaptive research lane."
    )
    signals.loc[deep_reversion, "shadow_action"] = "DEEP_REVERSION_LONG_WATCH"
    signals.loc[deep_reversion, "shadow_reason"] = (
        "A completed v4 bounce followed a meaningful pullback from the session high."
    )
    signals.loc[trend_pullback, "shadow_action"] = "TREND_PULLBACK_LONG_WATCH"
    signals.loc[trend_pullback, "shadow_reason"] = (
        "SOXL resumed higher above VWAP after a completed pullback in a positive QQQ regime."
    )
    return signals[THIRTY_MINUTE_COLUMNS].reset_index(drop=True)


def build_thirty_minute_bars(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(columns=THIRTY_MINUTE_COLUMNS)

    frame = bars.copy()
    frame["timestamp_dt"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp_dt", "soxl_close"])
    if frame.empty:
        return pd.DataFrame(columns=THIRTY_MINUTE_COLUMNS)

    frame = frame.set_index("timestamp_dt").sort_index()
    grouped = frame.groupby(pd.Grouper(freq=config.signal_interval))
    aggregated = grouped.agg(
        market_date=("market_date", "last"),
        soxl_open=("soxl_open", "first"),
        soxl_high=("soxl_high", "max"),
        soxl_low=("soxl_low", "min"),
        soxl_close=("soxl_close", "last"),
        soxl_volume=("soxl_volume", "sum"),
        soxl_vwap=("soxl_vwap", "last"),
        soxl_from_open_pct=("soxl_from_open_pct", "last"),
        soxl_from_high_pct=("soxl_from_high_pct", "last"),
        soxl_from_low_pct=("soxl_from_low_pct", "last"),
        soxl_session_range_pct=("soxl_range_pct", "last"),
        qqq_open=("qqq_close", "first"),
        qqq_close=("qqq_close", "last"),
        qqq_from_open_pct=("qqq_from_open_pct", "last"),
        bars_in_window=("soxl_close", "count"),
    )

    aggregated = aggregated[
        aggregated["bars_in_window"] >= expected_rows_per_signal_bar(config)
    ].copy()
    if aggregated.empty:
        return pd.DataFrame(columns=THIRTY_MINUTE_COLUMNS)

    aggregated["timestamp"] = [timestamp.isoformat() for timestamp in aggregated.index]
    aggregated["interval"] = config.signal_interval
    aggregated["bar_number"] = (
        aggregated.groupby("market_date").cumcount() + 1
    ).astype(int)
    aggregated["soxl_return_30m_pct"] = [
        pct_change(close, open_)
        for close, open_ in zip(
            aggregated["soxl_close"],
            aggregated["soxl_open"],
            strict=False,
        )
    ]
    aggregated["soxl_vs_vwap_pct"] = [
        pct_change(close, vwap)
        for close, vwap in zip(
            aggregated["soxl_close"],
            aggregated["soxl_vwap"],
            strict=False,
        )
    ]
    aggregated["qqq_return_30m_pct"] = [
        pct_change(close, open_)
        for close, open_ in zip(
            aggregated["qqq_close"],
            aggregated["qqq_open"],
            strict=False,
        )
    ]
    return apply_thirty_minute_signal_rules(aggregated, config=config)


def build_historical_thirty_minute_bars(
    soxl: pd.DataFrame,
    qqq: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> pd.DataFrame:
    soxl_session = regular_session(soxl)
    qqq_session = regular_session(qqq)
    if soxl_session.empty:
        return pd.DataFrame(columns=THIRTY_MINUTE_COLUMNS)

    soxl_day = pd.Series(soxl_session.index.date, index=soxl_session.index)
    soxl_day_open = soxl_session.groupby(soxl_day)["Open"].transform("first")
    soxl_running_high = soxl_session.groupby(soxl_day)["High"].cummax()
    soxl_running_low = soxl_session.groupby(soxl_day)["Low"].cummin()
    soxl_volume = soxl_session["Volume"].fillna(0)
    soxl_cumulative_volume = soxl_volume.groupby(soxl_day).cumsum()
    soxl_cumulative_value = (soxl_session["Close"] * soxl_volume).groupby(soxl_day).cumsum()
    soxl_vwap = soxl_cumulative_value.divide(
        soxl_cumulative_volume.where(soxl_cumulative_volume != 0)
    )
    soxl_bar_number = soxl_session.groupby(soxl_day).cumcount() + 1

    aligned_qqq_close = qqq_session["Close"].reindex(soxl_session.index, method="ffill")
    qqq_open_by_day = qqq_session.groupby(qqq_session.index.date)["Open"].transform("first")
    qqq_open = qqq_open_by_day.reindex(soxl_session.index, method="ffill")

    base = pd.DataFrame(
        {
            "timestamp": [timestamp.isoformat() for timestamp in soxl_session.index],
            "market_date": [str(timestamp.date()) for timestamp in soxl_session.index],
            "interval": config.signal_interval,
            "soxl_open": soxl_session["Open"],
            "soxl_high": soxl_session["High"],
            "soxl_low": soxl_session["Low"],
            "soxl_close": soxl_session["Close"],
            "soxl_volume": soxl_session["Volume"],
            "soxl_vwap": soxl_vwap,
            "soxl_return_30m_pct": [
                pct_change(close, open_)
                for close, open_ in zip(
                    soxl_session["Close"],
                    soxl_session["Open"],
                    strict=False,
                )
            ],
            "soxl_vs_vwap_pct": [
                pct_change(close, vwap)
                for close, vwap in zip(soxl_session["Close"], soxl_vwap, strict=False)
            ],
            "soxl_from_open_pct": [
                pct_change(close, open_)
                for close, open_ in zip(
                    soxl_session["Close"],
                    soxl_day_open,
                    strict=False,
                )
            ],
            "soxl_from_high_pct": [
                pct_change(close, high)
                for close, high in zip(
                    soxl_session["Close"],
                    soxl_running_high,
                    strict=False,
                )
            ],
            "soxl_from_low_pct": [
                pct_change(close, low)
                for close, low in zip(
                    soxl_session["Close"],
                    soxl_running_low,
                    strict=False,
                )
            ],
            "soxl_session_range_pct": [
                pct_change(high, low)
                for high, low in zip(
                    soxl_running_high,
                    soxl_running_low,
                    strict=False,
                )
            ],
            "bar_number": soxl_bar_number,
            "qqq_close": aligned_qqq_close,
            "qqq_return_30m_pct": [
                pct_change(close, open_)
                for close, open_ in zip(
                    aligned_qqq_close,
                    qqq_session["Open"].reindex(soxl_session.index, method="ffill"),
                    strict=False,
                )
            ],
            "qqq_from_open_pct": [
                pct_change(close, open_)
                for close, open_ in zip(aligned_qqq_close, qqq_open, strict=False)
            ],
            "bars_in_window": 1,
        }
    )
    base = base.dropna(subset=["soxl_close", "qqq_close"])
    return apply_thirty_minute_signal_rules(base, config=config)


def classify_watch_state(
    latest_bar: pd.Series,
    config: IntradayConfig = IntradayConfig(),
) -> tuple[str, str]:
    from_open = to_float(latest_bar.get("soxl_from_open_pct")) or 0.0
    from_high = to_float(latest_bar.get("soxl_from_high_pct")) or 0.0
    from_low = to_float(latest_bar.get("soxl_from_low_pct")) or 0.0
    range_pct = to_float(latest_bar.get("soxl_range_pct")) or 0.0

    if range_pct >= config.extreme_range_pct:
        return "EXTREME_RANGE", "Session range is already unusually wide."
    if from_high <= config.pullback_from_high_pct:
        return "PULLBACK_WATCH", "SOXL has sold off sharply from the session high."
    if from_low >= config.bounce_from_low_pct and from_open < 0:
        return "BOUNCE_WATCH", "SOXL has bounced hard from the session low while still red."
    if abs(from_open) >= config.trend_move_pct:
        return "TREND_DAY", "SOXL has made a large move from the session open."
    return "OBSERVE", "No intraday watch threshold has fired."


def build_snapshot(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
    now: datetime | None = None,
) -> dict[str, Any]:
    if bars.empty:
        raise IntradayDataError("Cannot build an intraday snapshot without bars.")

    latest = bars.iloc[-1]
    watch_state, reason = classify_watch_state(latest, config=config)
    now = now or datetime.now(MARKET_TIMEZONE)
    soxl_vwap = to_float(latest.get("soxl_vwap"))
    soxl_last = to_float(latest.get("soxl_close"))

    data_warning = ""
    if latest.get("qqq_close") is None or pd.isna(latest.get("qqq_close")):
        data_warning = "QQQ intraday row was unavailable for the latest SOXL bar."

    return {
        "run_timestamp": now.isoformat(),
        "timestamp": latest.get("timestamp"),
        "market_date": latest.get("market_date"),
        "interval": config.interval,
        "watch_state": watch_state,
        "reason": reason,
        "soxl_open": to_float(bars.iloc[0].get("soxl_open")),
        "soxl_last": soxl_last,
        "soxl_session_high": to_float(bars["soxl_high"].max()),
        "soxl_session_low": to_float(bars["soxl_low"].min()),
        "soxl_vwap": soxl_vwap,
        "soxl_from_open_pct": to_float(latest.get("soxl_from_open_pct")),
        "soxl_from_high_pct": to_float(latest.get("soxl_from_high_pct")),
        "soxl_from_low_pct": to_float(latest.get("soxl_from_low_pct")),
        "soxl_range_pct": to_float(latest.get("soxl_range_pct")),
        "soxl_vs_vwap_pct": pct_change(soxl_last, soxl_vwap),
        "qqq_last": to_float(latest.get("qqq_close")),
        "qqq_from_open_pct": to_float(latest.get("qqq_from_open_pct")),
        "bars_observed": int(len(bars)),
        "data_warning": data_warning,
    }


def merge_csv_rows(path: Path, rows: pd.DataFrame, unique_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        if existing.empty:
            merged = rows.copy()
        else:
            columns = list(dict.fromkeys([*existing.columns, *rows.columns]))
            populated = [
                frame.dropna(axis=1, how="all") for frame in (existing, rows)
            ]
            merged = pd.concat(populated, ignore_index=True).reindex(columns=columns)
    else:
        merged = rows.copy()

    merged = merged.drop_duplicates(subset=[unique_key], keep="last")
    merged = merged.sort_values(unique_key)
    merged.to_csv(path, index=False)


def append_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    row = pd.DataFrame([{column: snapshot.get(column) for column in SNAPSHOT_COLUMNS}])
    merge_csv_rows(path, row, unique_key="timestamp")


def save_bars(path: Path, bars: pd.DataFrame) -> None:
    merge_csv_rows(path, bars[BAR_COLUMNS], unique_key="timestamp")


def save_thirty_minute_bars(path: Path, bars: pd.DataFrame) -> None:
    if not bars.empty:
        if path.exists():
            existing = pd.read_csv(path, nrows=1)
            has_current_schema = set(THIRTY_MINUTE_COLUMNS).issubset(existing.columns)
            if not has_current_schema:
                path.parent.mkdir(parents=True, exist_ok=True)
                bars[THIRTY_MINUTE_COLUMNS].to_csv(path, index=False)
                return
        merge_csv_rows(path, bars[THIRTY_MINUTE_COLUMNS], unique_key="timestamp")


def default_thirty_minute_state(config: IntradayConfig) -> dict[str, Any]:
    return {
        "strategy_version": config.strategy_version,
        "paper_equity": config.starting_capital,
        "cash": config.starting_capital,
        "marked_equity": config.starting_capital,
        "in_position": False,
        "entry_timestamp": None,
        "entry_price": None,
        "entry_z": None,
        "shares": 0.0,
        "invested_capital": 0.0,
        "equity_before_entry": None,
        "last_processed_timestamp": None,
        "last_action": None,
        "last_reason": None,
    }


def sort_thirty_minute_bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    sorted_frame = frame.copy()
    sorted_frame["timestamp_dt"] = pd.to_datetime(
        sorted_frame["timestamp"],
        errors="coerce",
    )
    sorted_frame = sorted_frame.dropna(subset=["timestamp_dt"])
    return sorted_frame.sort_values("timestamp_dt").reset_index(drop=True)


def mark_thirty_minute_position(
    state: dict[str, Any],
    latest_close: float,
) -> None:
    shares = float(state.get("shares", 0.0))
    cash = float(state.get("cash", 0.0))
    entry_price = float(state.get("entry_price") or 0.0)
    position_market_value = shares * latest_close
    marked_equity = cash + position_market_value
    state["marked_equity"] = float(marked_equity)
    state["position_market_value"] = float(position_market_value)
    state["current_position_return"] = (
        float(latest_close / entry_price - 1) if entry_price > 0 else 0.0
    )


def bars_held_since_entry(frame: pd.DataFrame, entry_timestamp: Any, latest_timestamp: Any) -> int:
    entry = parse_timestamp(entry_timestamp)
    latest = parse_timestamp(latest_timestamp)
    if entry is None or latest is None:
        return 0
    mask = (frame["timestamp_dt"] > entry) & (frame["timestamp_dt"] <= latest)
    return int(mask.sum())


def append_thirty_minute_paper_log(
    path: Path,
    row: dict[str, Any],
) -> None:
    data = pd.DataFrame(
        [{column: row.get(column) for column in THIRTY_MINUTE_PAPER_LOG_COLUMNS}]
    )
    merge_csv_rows(path, data, unique_key="timestamp")


def append_thirty_minute_trade_log(
    path: Path,
    row: dict[str, Any],
) -> None:
    data = pd.DataFrame(
        [{column: row.get(column) for column in THIRTY_MINUTE_TRADE_LOG_COLUMNS}]
    )
    merge_csv_rows(path, data, unique_key="exit_timestamp")


def process_thirty_minute_paper(
    bars: pd.DataFrame,
    paths: IntradayPaths = IntradayPaths(),
    config: IntradayConfig = IntradayConfig(),
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    frame = sort_thirty_minute_bars(bars)
    if frame.empty:
        raise IntradayDataError("No 30-minute bars available for paper processing.")

    state = load_json(
        paths.thirty_minute_state_file,
        default_thirty_minute_state(config),
    )
    latest = frame.iloc[-1]
    latest_timestamp = latest["timestamp"]
    latest_close = to_float(latest.get("soxl_close"))
    if latest_close is None:
        raise IntradayDataError("Latest 30-minute SOXL close is unavailable.")

    last_processed = parse_timestamp(state.get("last_processed_timestamp"))
    latest_dt = parse_timestamp(latest_timestamp)
    if last_processed is not None and latest_dt is not None and latest_dt <= last_processed:
        return {
            "processed": False,
            "action": "NO NEW 30M BAR",
            "reason": f"Already processed {latest_timestamp}.",
            "state": state,
        }

    now = now or datetime.now(MARKET_TIMEZONE)
    action = "WAIT"
    reason = "No 30-minute paper action."
    trade_row = None

    if bool(state.get("in_position")):
        held_bars = bars_held_since_entry(
            frame,
            state.get("entry_timestamp"),
            latest_timestamp,
        )
        mark_thirty_minute_position(state, latest_close)
        if held_bars >= config.hold_bars:
            exit_price = latest_close * (1 - config.slippage)
            shares = float(state.get("shares", 0.0))
            final_equity = float(state.get("cash", 0.0)) + shares * exit_price
            equity_before_entry = float(
                state.get("equity_before_entry") or state.get("paper_equity")
            )
            entry_price = float(state.get("entry_price") or 0.0)
            position_return = exit_price / entry_price - 1 if entry_price else 0.0
            account_return = final_equity / equity_before_entry - 1
            trade_row = {
                "strategy_version": config.strategy_version,
                "entry_timestamp": state.get("entry_timestamp"),
                "exit_timestamp": latest_timestamp,
                "entry_price": entry_price,
                "exit_price": float(exit_price),
                "shares": shares,
                "bars_held": held_bars,
                "position_return": float(position_return),
                "account_return": float(account_return),
                "equity_before_entry": equity_before_entry,
                "equity_after_exit": float(final_equity),
                "entry_z": state.get("entry_z"),
                "exit_reason": f"fixed_hold_{config.hold_bars}_30m_bars",
            }
            state.update(
                {
                    "paper_equity": float(final_equity),
                    "cash": float(final_equity),
                    "marked_equity": float(final_equity),
                    "in_position": False,
                    "entry_timestamp": None,
                    "entry_price": None,
                    "entry_z": None,
                    "shares": 0.0,
                    "invested_capital": 0.0,
                    "equity_before_entry": None,
                    "position_market_value": 0.0,
                    "current_position_return": 0.0,
                }
            )
            action = "SELL"
            reason = f"Exited after {held_bars} completed 30-minute bars."
        else:
            action = "HOLD"
            reason = (
                f"Position open. Holding bar {held_bars} of {config.hold_bars}."
            )

    if not bool(state.get("in_position")) and trade_row is None and is_true(
        latest.get("shadow_signal")
    ):
        account_equity = float(state.get("marked_equity") or state["paper_equity"])
        invested_capital = account_equity * config.position_fraction
        entry_price = latest_close * (1 + config.slippage)
        shares = invested_capital / entry_price
        state.update(
            {
                "cash": float(account_equity - invested_capital),
                "marked_equity": float(account_equity),
                "in_position": True,
                "entry_timestamp": latest_timestamp,
                "entry_price": float(entry_price),
                "entry_z": to_float(latest.get("soxl_z_5bar")),
                "shares": float(shares),
                "invested_capital": float(invested_capital),
                "equity_before_entry": float(account_equity),
                "position_market_value": float(shares * latest_close),
                "current_position_return": float(latest_close / entry_price - 1),
            }
        )
        action = "BUY"
        reason = "Entered 30-minute paper trade on the completed signal bar."

    state["last_processed_timestamp"] = latest_timestamp
    state["last_action"] = action
    state["last_reason"] = reason

    log_row = {
        "run_timestamp": now.isoformat(),
        "timestamp": latest_timestamp,
        "market_date": latest.get("market_date"),
        "strategy_version": config.strategy_version,
        "action": action,
        "reason": reason,
        "shadow_signal": bool(is_true(latest.get("shadow_signal"))),
        "shadow_action": latest.get("shadow_action"),
        "soxl_close": latest_close,
        "soxl_z_5bar": to_float(latest.get("soxl_z_5bar")),
        "qqq_from_open_pct": to_float(latest.get("qqq_from_open_pct")),
        "account_state": "in_position" if state.get("in_position") else "flat",
        "in_position": bool(state.get("in_position")),
        "entry_timestamp": state.get("entry_timestamp"),
        "entry_price": state.get("entry_price"),
        "shares": state.get("shares"),
        "bars_held": bars_held_since_entry(frame, state.get("entry_timestamp"), latest_timestamp)
        if state.get("in_position")
        else 0,
        "position_market_value": state.get("position_market_value", 0.0),
        "paper_cash": state.get("cash"),
        "paper_realized_equity": state.get("paper_equity"),
        "paper_marked_equity": state.get("marked_equity"),
        "current_position_return": state.get("current_position_return", 0.0),
    }

    if not dry_run:
        save_json(paths.thirty_minute_state_file, state)
        append_thirty_minute_paper_log(paths.thirty_minute_paper_log_file, log_row)
        if trade_row:
            append_thirty_minute_trade_log(paths.thirty_minute_trade_log_file, trade_row)

    return {
        "processed": True,
        "action": action,
        "reason": reason,
        "state": state,
        "log_row": log_row,
        "trade_row": trade_row,
    }


def default_overnight_rebound_state(config: IntradayConfig) -> dict[str, Any]:
    return {
        "strategy_version": config.overnight_strategy_version,
        "paper_equity": config.starting_capital,
        "cash": config.starting_capital,
        "marked_equity": config.starting_capital,
        "in_position": False,
        "entry_timestamp": None,
        "entry_market_date": None,
        "entry_price": None,
        "entry_signal_from_open_pct": None,
        "entry_provenance": None,
        "shares": 0.0,
        "invested_capital": 0.0,
        "equity_before_entry": None,
        "last_signal_market_date": None,
        "last_action": None,
        "last_reason": None,
    }


def append_overnight_rebound_paper_log(path: Path, row: dict[str, Any]) -> None:
    data = pd.DataFrame(
        [{column: row.get(column) for column in OVERNIGHT_REBOUND_PAPER_LOG_COLUMNS}]
    )
    merge_csv_rows(path, data, unique_key="event_id")


def append_overnight_rebound_trade_log(path: Path, row: dict[str, Any]) -> None:
    data = pd.DataFrame(
        [{column: row.get(column) for column in OVERNIGHT_REBOUND_TRADE_LOG_COLUMNS}]
    )
    merge_csv_rows(path, data, unique_key="trade_id")


def overnight_rebound_event_row(
    *,
    state: dict[str, Any],
    config: IntradayConfig,
    now: datetime,
    provenance: str,
    is_backfill: bool,
    event_id: str,
    event_timestamp: Any,
    market_date: str,
    action: str,
    reason: str,
    signal_from_open_pct: float | None = None,
    signal_price: float | None = None,
    fill_price: float | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "run_timestamp": now.isoformat(),
        "event_timestamp": event_timestamp,
        "market_date": market_date,
        "strategy_version": config.overnight_strategy_version,
        "provenance": provenance,
        "is_backfill": is_backfill,
        "action": action,
        "reason": reason,
        "signal_from_open_pct": signal_from_open_pct,
        "signal_price": signal_price,
        "fill_price": fill_price,
        "account_state": "in_position" if state.get("in_position") else "flat",
        "paper_cash": state.get("cash"),
        "paper_realized_equity": state.get("paper_equity"),
        "paper_marked_equity": state.get("marked_equity"),
    }


def process_overnight_rebound_paper(
    bars: pd.DataFrame,
    paths: IntradayPaths = IntradayPaths(),
    config: IntradayConfig = IntradayConfig(),
    now: datetime | None = None,
    provenance: str = "forward_live",
    is_backfill: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    frame = sort_thirty_minute_bars(bars)
    if frame.empty:
        raise IntradayDataError("No 30-minute bars available for overnight paper processing.")

    now = now or datetime.now(MARKET_TIMEZONE)
    state = load_json(
        paths.overnight_state_file,
        default_overnight_rebound_state(config),
    )
    market_date = str(frame.iloc[-1].get("market_date"))
    events: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []

    if bool(state.get("in_position")) and market_date > str(
        state.get("entry_market_date") or market_date
    ):
        opening_bar = frame.iloc[0]
        opening_price = to_float(opening_bar.get("soxl_open"))
        if opening_price is None:
            raise IntradayDataError("SOXL session open is unavailable for overnight exit.")
        exit_price = opening_price * (1 - config.slippage)
        shares = float(state.get("shares") or 0.0)
        final_equity = float(state.get("cash") or 0.0) + shares * exit_price
        equity_before_entry = float(
            state.get("equity_before_entry") or state.get("paper_equity")
        )
        entry_price = float(state.get("entry_price") or 0.0)
        position_return = exit_price / entry_price - 1 if entry_price else 0.0
        account_return = final_equity / equity_before_entry - 1
        entry_timestamp = state.get("entry_timestamp")
        trade_provenance = state.get("entry_provenance") or provenance
        trade_id = f"{entry_timestamp}->{opening_bar.get('timestamp')}"
        trade_row = {
            "trade_id": trade_id,
            "strategy_version": config.overnight_strategy_version,
            "provenance": trade_provenance,
            "is_backfill": trade_provenance == "historical_backfill",
            "entry_timestamp": entry_timestamp,
            "exit_timestamp": opening_bar.get("timestamp"),
            "entry_market_date": state.get("entry_market_date"),
            "exit_market_date": market_date,
            "signal_from_open_pct": state.get("entry_signal_from_open_pct"),
            "entry_price": entry_price,
            "exit_price": float(exit_price),
            "shares": shares,
            "position_return": float(position_return),
            "account_return": float(account_return),
            "equity_before_entry": equity_before_entry,
            "equity_after_exit": float(final_equity),
            "exit_reason": "next_session_market_open",
        }
        trades.append(trade_row)
        state.update(
            {
                "paper_equity": float(final_equity),
                "cash": float(final_equity),
                "marked_equity": float(final_equity),
                "in_position": False,
                "entry_timestamp": None,
                "entry_market_date": None,
                "entry_price": None,
                "entry_signal_from_open_pct": None,
                "entry_provenance": None,
                "shares": 0.0,
                "invested_capital": 0.0,
                "equity_before_entry": None,
            }
        )
        events.append(
            overnight_rebound_event_row(
                state=state,
                config=config,
                now=now,
                provenance=provenance,
                is_backfill=is_backfill,
                event_id=(
                    f"{opening_bar.get('timestamp')}:{provenance}:OPEN_EXIT"
                ),
                event_timestamp=opening_bar.get("timestamp"),
                market_date=market_date,
                action="SELL_OPEN",
                reason="Exited the overnight paper position at the next session open.",
                fill_price=float(exit_price),
            )
        )

    signal_rows = frame[
        pd.to_numeric(frame.get("bar_number"), errors="coerce")
        == config.overnight_signal_bar_number
    ]
    already_processed = str(state.get("last_signal_market_date")) == market_date
    if not signal_rows.empty and not already_processed:
        signal_bar = signal_rows.iloc[-1]
        signal_timestamp = signal_bar.get("timestamp")
        signal_price = to_float(signal_bar.get("soxl_close"))
        signal_from_open = to_float(signal_bar.get("soxl_from_open_pct"))
        if signal_price is None or signal_from_open is None:
            raise IntradayDataError("Overnight rebound signal inputs are unavailable.")

        action = "NO_SIGNAL"
        reason = "SOXL had not fallen enough by 3:30 p.m. ET."
        fill_price = None
        if (
            not bool(state.get("in_position"))
            and signal_from_open <= config.overnight_signal_from_open_pct
        ):
            account_equity = float(
                state.get("marked_equity") or state.get("paper_equity")
            )
            invested_capital = account_equity * config.position_fraction
            fill_price = signal_price * (1 + config.slippage)
            shares = invested_capital / fill_price
            state.update(
                {
                    "cash": float(account_equity - invested_capital),
                    "marked_equity": float(account_equity - invested_capital + shares * signal_price),
                    "in_position": True,
                    "entry_timestamp": signal_timestamp,
                    "entry_market_date": market_date,
                    "entry_price": float(fill_price),
                    "entry_signal_from_open_pct": signal_from_open,
                    "entry_provenance": provenance,
                    "shares": float(shares),
                    "invested_capital": float(invested_capital),
                    "equity_before_entry": float(account_equity),
                }
            )
            action = "BUY_CLOSE"
            reason = "SOXL was down at least 5% at 3:30 p.m.; entered for the next open."

        state["last_signal_market_date"] = market_date
        events.append(
            overnight_rebound_event_row(
                state=state,
                config=config,
                now=now,
                provenance=provenance,
                is_backfill=is_backfill,
                event_id=f"{signal_timestamp}:{provenance}:1530_DECISION",
                event_timestamp=signal_timestamp,
                market_date=market_date,
                action=action,
                reason=reason,
                signal_from_open_pct=signal_from_open,
                signal_price=signal_price,
                fill_price=fill_price,
            )
        )

    if bool(state.get("in_position")):
        latest_close = to_float(frame.iloc[-1].get("soxl_close"))
        if latest_close is not None:
            state["marked_equity"] = float(
                float(state.get("cash") or 0.0)
                + float(state.get("shares") or 0.0) * latest_close
            )
    if events:
        state["last_action"] = events[-1]["action"]
        state["last_reason"] = events[-1]["reason"]

    if not dry_run:
        save_json(paths.overnight_state_file, state)
        for event in events:
            append_overnight_rebound_paper_log(paths.overnight_paper_log_file, event)
        for trade in trades:
            append_overnight_rebound_trade_log(paths.overnight_trade_log_file, trade)

    return {
        "processed": bool(events),
        "events": events,
        "trades": trades,
        "state": state,
        "action": events[-1]["action"] if events else "NO NEW OVERNIGHT EVENT",
    }


def backfill_overnight_rebound_paper(
    bars: pd.DataFrame,
    sessions: int = 5,
    paths: IntradayPaths = IntradayPaths(),
    config: IntradayConfig = IntradayConfig(),
    now: datetime | None = None,
) -> dict[str, Any]:
    frame = sort_thirty_minute_bars(bars)
    market_dates = sorted(frame["market_date"].dropna().astype(str).unique())[-sessions:]
    if not market_dates:
        raise IntradayDataError("No market sessions were available for overnight backfill.")

    paths.overnight_state_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=OVERNIGHT_REBOUND_PAPER_LOG_COLUMNS).to_csv(
        paths.overnight_paper_log_file,
        index=False,
    )
    pd.DataFrame(columns=OVERNIGHT_REBOUND_TRADE_LOG_COLUMNS).to_csv(
        paths.overnight_trade_log_file,
        index=False,
    )
    state = default_overnight_rebound_state(config)
    state.update(
        {
            "backfill_sessions": len(market_dates),
            "backfill_start": market_dates[0],
            "backfill_end": market_dates[-1],
            "backfill_is_simulated": True,
        }
    )
    save_json(paths.overnight_state_file, state)

    all_events: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []
    for market_date in market_dates:
        day = frame[frame["market_date"].astype(str) == market_date].copy()
        result = process_overnight_rebound_paper(
            day,
            paths=paths,
            config=config,
            now=now,
            provenance="historical_backfill",
            is_backfill=True,
        )
        all_events.extend(result["events"])
        all_trades.extend(result["trades"])

    state = load_json(
        paths.overnight_state_file,
        default_overnight_rebound_state(config),
    )
    state["forward_live_started_at"] = (now or datetime.now(MARKET_TIMEZONE)).isoformat()
    save_json(paths.overnight_state_file, state)
    return {
        "sessions": market_dates,
        "events": all_events,
        "trades": all_trades,
        "state": state,
    }


def max_drawdown(equity_values: list[float]) -> float:
    peak = None
    worst = 0.0
    for value in equity_values:
        peak = value if peak is None else max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1)
    return worst


def backtest_thirty_minute_strategy(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
    entry_execution: str = "signal_close",
    max_entries_per_session: int | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    if entry_execution not in {"signal_close", "next_bar_open"}:
        raise IntradayDataError(
            f"Unsupported 30-minute entry execution: {entry_execution}"
        )

    frame = sort_thirty_minute_bars(bars)
    cash = config.starting_capital
    marked_equity = config.starting_capital
    shares = 0.0
    entry_price = None
    entry_timestamp = None
    entry_z = None
    equity_before_entry = None
    pending_signal: dict[str, Any] | None = None
    entries_by_session: dict[str, int] = {}
    trades = []
    equity_rows = []

    for _, row in frame.iterrows():
        close = to_float(row.get("soxl_close"))
        if close is None:
            continue

        timestamp = row.get("timestamp")
        market_date = str(row.get("market_date"))
        if shares > 0 and entry_timestamp is not None:
            bars_held = bars_held_since_entry(frame, entry_timestamp, timestamp)
            marked_equity = cash + shares * close
            if bars_held >= config.hold_bars:
                exit_price = close * (1 - config.slippage)
                final_equity = cash + shares * exit_price
                position_return = (
                    exit_price / entry_price - 1 if entry_price else 0.0
                )
                account_return = (
                    final_equity / equity_before_entry - 1
                    if equity_before_entry
                    else 0.0
                )
                trades.append(
                    {
                        "strategy_version": config.strategy_version,
                        "entry_timestamp": entry_timestamp,
                        "exit_timestamp": timestamp,
                        "entry_price": entry_price,
                        "exit_price": float(exit_price),
                        "shares": shares,
                        "bars_held": bars_held,
                        "position_return": float(position_return),
                        "account_return": float(account_return),
                        "equity_before_entry": equity_before_entry,
                        "equity_after_exit": float(final_equity),
                        "entry_z": entry_z,
                        "exit_reason": f"fixed_hold_{config.hold_bars}_30m_bars",
                    }
                )
                cash = float(final_equity)
                marked_equity = float(final_equity)
                shares = 0.0
                entry_price = None
                entry_timestamp = None
                entry_z = None
                equity_before_entry = None

        if shares == 0 and pending_signal is not None:
            same_session = (
                str(row.get("market_date"))
                == str(pending_signal.get("market_date"))
            )
            bar_open = to_float(row.get("soxl_open"))
            if same_session and bar_open is not None:
                equity_before_entry = marked_equity
                invested_capital = marked_equity * config.position_fraction
                entry_price = bar_open * (1 + config.slippage)
                shares = invested_capital / entry_price
                cash = marked_equity - invested_capital
                entry_timestamp = timestamp
                entry_z = pending_signal.get("entry_z")
                marked_equity = cash + shares * close
                entries_by_session[market_date] = (
                    entries_by_session.get(market_date, 0) + 1
                )
            pending_signal = None

        entry_limit_available = (
            max_entries_per_session is None
            or entries_by_session.get(market_date, 0) < max_entries_per_session
        )
        if (
            shares == 0
            and pending_signal is None
            and entry_limit_available
            and is_true(row.get("shadow_signal"))
            and entry_execution == "signal_close"
        ):
            equity_before_entry = marked_equity
            invested_capital = marked_equity * config.position_fraction
            entry_price = close * (1 + config.slippage)
            shares = invested_capital / entry_price
            cash = marked_equity - invested_capital
            entry_timestamp = timestamp
            entry_z = to_float(row.get("soxl_z_5bar"))
            marked_equity = cash + shares * close
            entries_by_session[market_date] = (
                entries_by_session.get(market_date, 0) + 1
            )

        if (
            shares == 0
            and pending_signal is None
            and entry_limit_available
            and is_true(row.get("shadow_signal"))
            and entry_execution == "next_bar_open"
        ):
            bar_number = to_float(row.get("bar_number"))
            can_finish_same_session = (
                config.allow_overnight
                or bar_number is None
                or bar_number + 1 + config.hold_bars
                <= config.session_signal_bars
            )
            if can_finish_same_session:
                pending_signal = {
                    "timestamp": timestamp,
                    "market_date": row.get("market_date"),
                    "entry_z": to_float(row.get("soxl_z_5bar")),
                }

        equity_rows.append(
            {
                "timestamp": timestamp,
                "market_date": row.get("market_date"),
                "equity": float(marked_equity),
                "in_position": shares > 0,
            }
        )

    trade_frame = pd.DataFrame(trades, columns=THIRTY_MINUTE_TRADE_LOG_COLUMNS)
    equity_frame = pd.DataFrame(equity_rows)
    returns = (
        pd.to_numeric(trade_frame["position_return"], errors="coerce")
        if not trade_frame.empty
        else pd.Series(dtype="float64")
    )
    final_equity = (
        float(equity_frame["equity"].iloc[-1])
        if not equity_frame.empty
        else config.starting_capital
    )
    summary = {
        "strategy_version": config.strategy_version,
        "period_start": equity_frame["timestamp"].iloc[0] if not equity_frame.empty else None,
        "period_end": equity_frame["timestamp"].iloc[-1] if not equity_frame.empty else None,
        "bars": int(len(frame)),
        "trades": int(len(trade_frame)),
        "final_equity": final_equity,
        "total_return": float(final_equity / config.starting_capital - 1),
        "win_rate": float((returns > 0).mean()) if not returns.empty else None,
        "avg_position_return": float(returns.mean()) if not returns.empty else None,
        "best_trade": float(returns.max()) if not returns.empty else None,
        "worst_trade": float(returns.min()) if not returns.empty else None,
        "max_drawdown": max_drawdown(equity_frame["equity"].tolist())
        if not equity_frame.empty
        else 0.0,
        "z_threshold": config.signal_z_threshold,
        "hold_bars": config.hold_bars,
        "regime_floor_pct": config.regime_floor_pct,
        "entry_style": config.entry_style,
        "bounce_wait_bars": config.bounce_wait_bars,
        "require_vwap_reclaim": config.require_vwap_reclaim,
        "allow_overnight": config.allow_overnight,
        "entry_execution": entry_execution,
        "slippage": config.slippage,
        "max_entries_per_session": max_entries_per_session,
    }
    return summary, trade_frame, equity_frame


def config_with(
    config: IntradayConfig,
    *,
    strategy_version: str | None = None,
    z_threshold: float | None = None,
    hold_bars: int | None = None,
    regime_floor_pct: float | None = None,
    entry_style: str | None = None,
    bounce_wait_bars: int | None = None,
    require_vwap_reclaim: bool | None = None,
    allow_overnight: bool | None = None,
    slippage: float | None = None,
) -> IntradayConfig:
    return IntradayConfig(
        symbol=config.symbol,
        regime_symbol=config.regime_symbol,
        interval=config.interval,
        period=config.period,
        signal_interval=config.signal_interval,
        signal_z_window=config.signal_z_window,
        signal_z_threshold=(
            config.signal_z_threshold if z_threshold is None else z_threshold
        ),
        regime_floor_pct=(
            config.regime_floor_pct
            if regime_floor_pct is None
            else regime_floor_pct
        ),
        strategy_version=strategy_version or config.strategy_version,
        challenger_strategy_version=config.challenger_strategy_version,
        stress_strategy_version=config.stress_strategy_version,
        challenger_min_pullback_from_high_pct=(
            config.challenger_min_pullback_from_high_pct
        ),
        challenger_trend_from_open_pct=config.challenger_trend_from_open_pct,
        challenger_trend_qqq_floor_pct=config.challenger_trend_qqq_floor_pct,
        challenger_prior_pullback_pct=config.challenger_prior_pullback_pct,
        overnight_strategy_version=config.overnight_strategy_version,
        overnight_signal_from_open_pct=config.overnight_signal_from_open_pct,
        overnight_signal_bar_number=config.overnight_signal_bar_number,
        starting_capital=config.starting_capital,
        position_fraction=config.position_fraction,
        slippage=config.slippage if slippage is None else slippage,
        hold_bars=config.hold_bars if hold_bars is None else hold_bars,
        entry_style=config.entry_style if entry_style is None else entry_style,
        bounce_wait_bars=(
            config.bounce_wait_bars
            if bounce_wait_bars is None
            else bounce_wait_bars
        ),
        require_vwap_reclaim=(
            config.require_vwap_reclaim
            if require_vwap_reclaim is None
            else require_vwap_reclaim
        ),
        allow_overnight=(
            config.allow_overnight if allow_overnight is None else allow_overnight
        ),
        session_signal_bars=config.session_signal_bars,
        max_history_years=config.max_history_years,
        backtest_period=config.backtest_period,
        extreme_range_pct=config.extreme_range_pct,
        pullback_from_high_pct=config.pullback_from_high_pct,
        bounce_from_low_pct=config.bounce_from_low_pct,
        trend_move_pct=config.trend_move_pct,
    )


def candidate_configs(config: IntradayConfig) -> list[IntradayConfig]:
    candidates = []
    entry_styles = ("episode_start", "bounce_confirmation")
    for entry_style in entry_styles:
        wait_values = (0,) if entry_style == "episode_start" else (1, 2, 3)
        vwap_values = (False,) if entry_style == "episode_start" else (False, True)
        for z_threshold in (-1.0, -1.25, -1.5, -1.75, -2.0):
            for hold_bars in (1, 2, 3, 4):
                for regime_floor in (-0.015, -0.01, -0.005, 0.0):
                    for bounce_wait in wait_values:
                        for require_vwap in vwap_values:
                            candidates.append(
                                config_with(
                                    config,
                                    z_threshold=z_threshold,
                                    hold_bars=hold_bars,
                                    regime_floor_pct=regime_floor,
                                    entry_style=entry_style,
                                    bounce_wait_bars=bounce_wait,
                                    require_vwap_reclaim=require_vwap,
                                    allow_overnight=False,
                                )
                            )
    return candidates


def score_summary(summary: dict[str, Any], min_trades: int = 5) -> float:
    total_return = float(summary.get("total_return") or 0.0)
    drawdown = abs(float(summary.get("max_drawdown") or 0.0))
    trades = int(summary.get("trades") or 0)
    score = total_return / max(drawdown, 0.01)

    if total_return <= 0:
        score -= 1.0
    if trades < min_trades:
        score -= (min_trades - trades) * 0.5
    if drawdown > 0.10:
        score -= drawdown * 5
    return float(score)


def evaluate_candidate(
    bars: pd.DataFrame,
    config: IntradayConfig,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    candidate_bars = apply_thirty_minute_signal_rules(bars, config=config)
    return backtest_thirty_minute_strategy(candidate_bars, config=config)


def compare_thirty_minute_parameters(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
    candidates: list[IntradayConfig] | None = None,
) -> pd.DataFrame:
    rows = []
    for candidate_config in candidates or candidate_configs(config):
        summary, _, _ = evaluate_candidate(bars, candidate_config)
        summary["score"] = score_summary(summary)
        rows.append(summary)
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


def split_train_test_bars(
    bars: pd.DataFrame,
    train_fraction: float = 0.67,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = sort_thirty_minute_bars(bars)
    if frame.empty or "market_date" not in frame.columns:
        return frame, frame.iloc[0:0].copy()

    market_dates = pd.Series(frame["market_date"].dropna().unique()).sort_values()
    if len(market_dates) < 3:
        return frame, frame.iloc[0:0].copy()

    split_index = int(len(market_dates) * train_fraction)
    split_index = max(1, min(split_index, len(market_dates) - 1))
    train_dates = set(market_dates.iloc[:split_index].astype(str))
    test_dates = set(market_dates.iloc[split_index:].astype(str))
    train = frame[frame["market_date"].astype(str).isin(train_dates)].copy()
    test = frame[frame["market_date"].astype(str).isin(test_dates)].copy()
    return train.reset_index(drop=True), test.reset_index(drop=True)


def adaptive_challenger_config(
    config: IntradayConfig = IntradayConfig(),
) -> IntradayConfig:
    return config_with(
        config,
        strategy_version=config.challenger_strategy_version,
    )


def evaluate_adaptive_challenger(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    challenger_bars = apply_adaptive_thirty_minute_challenger_rules(
        bars,
        config=config,
    )
    challenger_config = adaptive_challenger_config(config)
    summary, trades, equity = backtest_thirty_minute_strategy(
        challenger_bars,
        config=challenger_config,
    )
    return summary, trades, equity, challenger_bars


def validate_adaptive_challenger(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
) -> dict[str, Any]:
    """Check the fixed challenger across chronological 60/20/20 date blocks."""
    challenger_bars = apply_adaptive_thirty_minute_challenger_rules(
        bars,
        config=config,
    )
    market_dates = pd.Series(
        challenger_bars["market_date"].dropna().astype(str).unique()
    ).sort_values()
    if len(market_dates) < 5:
        return {}

    train_end = max(1, int(len(market_dates) * 0.60))
    validation_end = max(train_end + 1, int(len(market_dates) * 0.80))
    validation_end = min(validation_end, len(market_dates) - 1)
    date_blocks = {
        "train": set(market_dates.iloc[:train_end]),
        "validation": set(market_dates.iloc[train_end:validation_end]),
        "test": set(market_dates.iloc[validation_end:]),
    }
    challenger_config = adaptive_challenger_config(config)
    summaries: dict[str, dict[str, Any]] = {}
    for name, dates in date_blocks.items():
        segment = challenger_bars[
            challenger_bars["market_date"].astype(str).isin(dates)
        ].copy()
        summaries[name], _, _ = backtest_thirty_minute_strategy(
            segment,
            config=challenger_config,
        )

    passed = (
        float(summaries["train"].get("total_return") or 0.0) > 0
        and float(summaries["validation"].get("total_return") or 0.0) > 0
        and float(summaries["test"].get("total_return") or 0.0) > 0
        and int(summaries["train"].get("trades") or 0) >= 10
        and int(summaries["validation"].get("trades") or 0) >= 2
        and int(summaries["test"].get("trades") or 0) >= 2
        and all(
            abs(float(summary.get("max_drawdown") or 0.0)) <= 0.05
            for summary in summaries.values()
        )
    )
    result: dict[str, Any] = {
        "strategy_version": config.challenger_strategy_version,
        "passes_chronological_check": passed,
        "min_pullback_from_high_pct": config.challenger_min_pullback_from_high_pct,
        "trend_from_open_pct": config.challenger_trend_from_open_pct,
        "trend_qqq_floor_pct": config.challenger_trend_qqq_floor_pct,
        "prior_pullback_pct": config.challenger_prior_pullback_pct,
    }
    for name, summary in summaries.items():
        result[f"{name}_start"] = summary.get("period_start")
        result[f"{name}_end"] = summary.get("period_end")
        result[f"{name}_trades"] = int(summary.get("trades") or 0)
        result[f"{name}_return"] = float(summary.get("total_return") or 0.0)
        result[f"{name}_win_rate"] = summary.get("win_rate")
        result[f"{name}_max_drawdown"] = float(
            summary.get("max_drawdown") or 0.0
        )
    return result


def recent_regime_segments(
    bars: pd.DataFrame,
    recent_sessions: int = 20,
) -> dict[str, pd.DataFrame]:
    """Return full, prior, and recent blocks without using future signal inputs."""
    frame = sort_thirty_minute_bars(bars)
    market_dates = pd.Series(
        frame["market_date"].dropna().astype(str).unique()
    ).sort_values()
    if market_dates.empty:
        return {"full": frame}

    recent_count = min(recent_sessions, len(market_dates))
    recent_dates = set(market_dates.iloc[-recent_count:])
    prior_dates = set(market_dates.iloc[:-recent_count])
    segments = {"full": frame}
    if prior_dates:
        segments["prior"] = frame[
            frame["market_date"].astype(str).isin(prior_dates)
        ].copy()
    segments[f"recent_{recent_count}_sessions"] = frame[
        frame["market_date"].astype(str).isin(recent_dates)
    ].copy()
    return segments


def evaluate_thirty_minute_robustness(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
    slippage_values: tuple[float, ...] = (0.001, 0.002, 0.003, 0.005),
    recent_sessions: int = 20,
) -> pd.DataFrame:
    """Stress both research lanes across execution, costs, and recent regimes."""
    baseline_bars = apply_thirty_minute_signal_rules(bars, config=config)
    strategy_specs = {
        config.strategy_version: (baseline_bars, None),
        config.challenger_strategy_version: (
            apply_adaptive_thirty_minute_challenger_rules(
                bars,
                config=config,
            ),
            None,
        ),
        config.stress_strategy_version: (baseline_bars, 1),
    }
    rows: list[dict[str, Any]] = []
    for strategy_version, (
        signal_bars,
        max_entries_per_session,
    ) in strategy_specs.items():
        strategy_config = config_with(
            config,
            strategy_version=strategy_version,
        )
        for segment_name, segment in recent_regime_segments(
            signal_bars,
            recent_sessions=recent_sessions,
        ).items():
            for entry_execution in ("signal_close", "next_bar_open"):
                for slippage in slippage_values:
                    test_config = config_with(
                        strategy_config,
                        slippage=slippage,
                    )
                    summary, _, _ = backtest_thirty_minute_strategy(
                        segment,
                        config=test_config,
                        entry_execution=entry_execution,
                        max_entries_per_session=max_entries_per_session,
                    )
                    summary["segment"] = segment_name
                    rows.append(summary)
    return pd.DataFrame(rows)


def evaluate_daily_shock_context(
    daily_prices: pd.DataFrame,
    paper_log: pd.DataFrame | None = None,
    modern_start: str = "2021-01-01",
    thresholds: tuple[float, ...] = (-0.20, -0.25, -0.30),
    forward_horizons: tuple[int, ...] = (1, 3, 5),
    cooldown_sessions: int = 10,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Summarize non-overlapping modern SOXL shocks and forward returns."""
    prices = daily_prices.copy()
    if "Date" not in prices.columns or "Close" not in prices.columns:
        raise IntradayDataError("Daily SOXL context requires Date and Close columns.")
    prices = prices[["Date", "Close"]].copy()

    if paper_log is not None and not paper_log.empty:
        required = {"market_date", "soxl_close"}
        if required.issubset(paper_log.columns):
            updates = paper_log[["market_date", "soxl_close"]].rename(
                columns={"market_date": "Date", "soxl_close": "Close"}
            )
            prices = pd.concat([prices, updates], ignore_index=True)

    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = (
        prices.dropna(subset=["Date", "Close"])
        .drop_duplicates(subset=["Date"], keep="last")
        .sort_values("Date")
    )
    prices = prices[prices["Date"] >= pd.Timestamp(modern_start)].reset_index(
        drop=True
    )
    if len(prices) < 21:
        return pd.DataFrame(), {}

    prices["return_5d"] = prices["Close"].pct_change(5)
    prices["drawdown_20d"] = (
        prices["Close"] / prices["Close"].rolling(20).max() - 1
    )
    latest = prices.iloc[-1]
    latest_summary = {
        "market_date": latest["Date"].date().isoformat(),
        "soxl_close": float(latest["Close"]),
        "return_5d": to_float(latest["return_5d"]),
        "drawdown_20d": to_float(latest["drawdown_20d"]),
        "modern_start": modern_start,
    }

    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        candidate_indices = prices.index[prices["return_5d"] <= threshold].tolist()
        event_indices: list[int] = []
        last_event = -cooldown_sessions
        for index in candidate_indices:
            if index - last_event < cooldown_sessions:
                continue
            event_indices.append(index)
            last_event = index

        for horizon in forward_horizons:
            forward_returns = [
                prices.iloc[index + horizon]["Close"] / prices.iloc[index]["Close"] - 1
                for index in event_indices
                if index + horizon < len(prices)
            ]
            values = pd.Series(forward_returns, dtype="float64")
            rows.append(
                {
                    "modern_start": modern_start,
                    "shock_threshold_5d": threshold,
                    "cooldown_sessions": cooldown_sessions,
                    "forward_sessions": horizon,
                    "events": int(len(values)),
                    "mean_forward_return": to_float(values.mean()),
                    "median_forward_return": to_float(values.median()),
                    "positive_rate": to_float((values > 0).mean()),
                    "worst_forward_return": to_float(values.min()),
                    "best_forward_return": to_float(values.max()),
                }
            )
    return pd.DataFrame(rows), latest_summary


def validation_row(
    candidate_config: IntradayConfig,
    train_summary: dict[str, Any],
    test_summary: dict[str, Any],
    full_summary: dict[str, Any],
    rank: int,
) -> dict[str, Any]:
    train_score = score_summary(train_summary)
    test_score = score_summary(test_summary, min_trades=2)
    train_return = float(train_summary.get("total_return") or 0.0)
    test_return = float(test_summary.get("total_return") or 0.0)
    train_trades = int(train_summary.get("trades") or 0)
    test_trades = int(test_summary.get("trades") or 0)
    test_drawdown = abs(float(test_summary.get("max_drawdown") or 0.0))
    decay_ratio = test_return / train_return if train_return > 0 else None
    passes_validation = (
        train_return > 0
        and test_return > 0
        and train_trades >= 5
        and test_trades >= 2
        and test_drawdown <= 0.05
    )
    validation_score = test_score + min(train_score, 3.0) * 0.25

    if not passes_validation:
        validation_score -= 100.0
    if decay_ratio is not None and decay_ratio < 0.25:
        validation_score -= 0.5

    return {
        "rank": rank,
        "strategy_version": candidate_config.strategy_version,
        "entry_style": candidate_config.entry_style,
        "z_threshold": candidate_config.signal_z_threshold,
        "hold_bars": candidate_config.hold_bars,
        "regime_floor_pct": candidate_config.regime_floor_pct,
        "bounce_wait_bars": candidate_config.bounce_wait_bars,
        "require_vwap_reclaim": candidate_config.require_vwap_reclaim,
        "allow_overnight": candidate_config.allow_overnight,
        "train_start": train_summary.get("period_start"),
        "train_end": train_summary.get("period_end"),
        "train_trades": train_trades,
        "train_return": train_return,
        "train_win_rate": train_summary.get("win_rate"),
        "train_max_drawdown": train_summary.get("max_drawdown"),
        "train_score": train_score,
        "test_start": test_summary.get("period_start"),
        "test_end": test_summary.get("period_end"),
        "test_trades": test_trades,
        "test_return": test_return,
        "test_win_rate": test_summary.get("win_rate"),
        "test_max_drawdown": test_summary.get("max_drawdown"),
        "test_score": test_score,
        "full_trades": int(full_summary.get("trades") or 0),
        "full_return": float(full_summary.get("total_return") or 0.0),
        "full_win_rate": full_summary.get("win_rate"),
        "full_max_drawdown": full_summary.get("max_drawdown"),
        "decay_ratio": decay_ratio,
        "passes_validation": passes_validation,
        "validation_score": float(validation_score),
    }


def validate_thirty_minute_candidates(
    bars: pd.DataFrame,
    config: IntradayConfig = IntradayConfig(),
    train_fraction: float = 0.67,
    candidates: list[IntradayConfig] | None = None,
) -> pd.DataFrame:
    train_bars, test_bars = split_train_test_bars(bars, train_fraction=train_fraction)
    if train_bars.empty or test_bars.empty:
        return pd.DataFrame()

    rows = []
    ranked_train = compare_thirty_minute_parameters(
        train_bars,
        config=config,
        candidates=candidates,
    )
    for rank, candidate in enumerate(ranked_train.to_dict(orient="records"), start=1):
        candidate_config = config_with(
            config,
            z_threshold=float(candidate["z_threshold"]),
            hold_bars=int(candidate["hold_bars"]),
            regime_floor_pct=float(candidate["regime_floor_pct"]),
            entry_style=str(candidate["entry_style"]),
            bounce_wait_bars=int(candidate["bounce_wait_bars"]),
            require_vwap_reclaim=is_true(candidate["require_vwap_reclaim"]),
            allow_overnight=is_true(candidate["allow_overnight"]),
        )
        train_summary, _, _ = evaluate_candidate(train_bars, candidate_config)
        test_summary, _, _ = evaluate_candidate(test_bars, candidate_config)
        full_summary, _, _ = evaluate_candidate(bars, candidate_config)
        rows.append(
            validation_row(
                candidate_config,
                train_summary,
                test_summary,
                full_summary,
                rank=rank,
            )
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            ["passes_validation", "validation_score"],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )


def run_backtest(
    paths: IntradayPaths = IntradayPaths(),
    config: IntradayConfig = IntradayConfig(),
    period: str | None = None,
) -> dict[str, Any]:
    requested_period = period or config.backtest_period
    try:
        soxl = download_yahoo_intraday(config.symbol, requested_period, "30m")
        qqq = download_yahoo_intraday(config.regime_symbol, requested_period, "30m")
    except IntradayDataError:
        if requested_period == "60d":
            raise
        requested_period = "60d"
        soxl = download_yahoo_intraday(config.symbol, requested_period, "30m")
        qqq = download_yahoo_intraday(config.regime_symbol, requested_period, "30m")

    bars = build_historical_thirty_minute_bars(soxl, qqq, config=config)
    if bars.empty:
        raise IntradayDataError("No 30-minute historical bars were available.")

    summary, trades, equity = backtest_thirty_minute_strategy(bars, config=config)
    comparison = compare_thirty_minute_parameters(bars, config=config)
    validation = validate_thirty_minute_candidates(bars, config=config)
    (
        challenger_summary,
        challenger_trades,
        challenger_equity,
        challenger_bars,
    ) = evaluate_adaptive_challenger(bars, config=config)
    challenger_validation = validate_adaptive_challenger(bars, config=config)
    robustness = evaluate_thirty_minute_robustness(bars, config=config)

    daily_shock_context = pd.DataFrame()
    daily_shock_latest: dict[str, Any] = {}
    daily_price_file = DATA_DIR / "SOXL.csv"
    paper_log_file = DATA_DIR / "paper" / "paper_daily_log.csv"
    if daily_price_file.exists():
        daily_prices = pd.read_csv(daily_price_file)
        paper_log = read_csv_or_empty(paper_log_file)
        daily_shock_context, daily_shock_latest = evaluate_daily_shock_context(
            daily_prices,
            paper_log=paper_log,
        )

    paths.thirty_minute_file.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(INTRADAY_30M_BACKTEST_BARS_FILE, index=False)
    pd.DataFrame([summary]).to_csv(INTRADAY_30M_BACKTEST_SUMMARY_FILE, index=False)
    trades.to_csv(INTRADAY_30M_BACKTEST_TRADES_FILE, index=False)
    equity.to_csv(INTRADAY_30M_BACKTEST_EQUITY_FILE, index=False)
    comparison.to_csv(INTRADAY_30M_PARAMETER_COMPARISON_FILE, index=False)
    validation.to_csv(INTRADAY_30M_VALIDATION_FILE, index=False)
    challenger_bars.to_csv(
        INTRADAY_30M_CHALLENGER_BACKTEST_BARS_FILE,
        index=False,
    )
    pd.DataFrame([challenger_summary]).to_csv(
        INTRADAY_30M_CHALLENGER_SUMMARY_FILE,
        index=False,
    )
    challenger_trades.to_csv(INTRADAY_30M_CHALLENGER_TRADES_FILE, index=False)
    challenger_equity.to_csv(INTRADAY_30M_CHALLENGER_EQUITY_FILE, index=False)
    pd.DataFrame([challenger_validation] if challenger_validation else []).to_csv(
        INTRADAY_30M_CHALLENGER_VALIDATION_FILE,
        index=False,
    )
    robustness.to_csv(INTRADAY_30M_ROBUSTNESS_FILE, index=False)
    daily_shock_context.to_csv(INTRADAY_DAILY_SHOCK_CONTEXT_FILE, index=False)
    pd.DataFrame([daily_shock_latest] if daily_shock_latest else []).to_csv(
        INTRADAY_DAILY_SHOCK_LATEST_FILE,
        index=False,
    )

    best = comparison.head(1).to_dict(orient="records")
    validated = validation.head(1).to_dict(orient="records")
    return {
        "requested_period": period or config.backtest_period,
        "used_period": requested_period,
        "summary": summary,
        "best": best[0] if best else None,
        "validated": validated[0] if validated else None,
        "trades": trades,
        "equity": equity,
        "comparison": comparison,
        "validation": validation,
        "robustness": robustness,
        "daily_shock_context": daily_shock_context,
        "daily_shock_latest": daily_shock_latest,
        "challenger": {
            "summary": challenger_summary,
            "trades": challenger_trades,
            "equity": challenger_equity,
            "bars": challenger_bars,
            "validation": challenger_validation,
        },
    }


def run_once(
    paths: IntradayPaths = IntradayPaths(),
    config: IntradayConfig = IntradayConfig(),
    paper_trade_30m: bool = False,
    paper_trade_overnight: bool = False,
) -> dict[str, Any]:
    soxl = download_yahoo_intraday(config.symbol, config.period, config.interval)
    qqq = download_yahoo_intraday(config.regime_symbol, config.period, config.interval)
    bars = build_intraday_bars(soxl, qqq, config=config)
    thirty_minute_bars = build_thirty_minute_bars(bars, config=config)
    challenger_bars = apply_adaptive_thirty_minute_challenger_rules(
        thirty_minute_bars,
        config=config,
    )
    snapshot = build_snapshot(bars, config=config)

    save_bars(paths.bars_file, bars)
    save_thirty_minute_bars(paths.thirty_minute_file, thirty_minute_bars)
    save_thirty_minute_bars(paths.thirty_minute_challenger_file, challenger_bars)
    paper_result = None
    if paper_trade_30m and not thirty_minute_bars.empty:
        paper_result = process_thirty_minute_paper(
            thirty_minute_bars,
            paths=paths,
            config=config,
        )
    overnight_result = None
    if paper_trade_overnight and not thirty_minute_bars.empty:
        overnight_result = process_overnight_rebound_paper(
            thirty_minute_bars,
            paths=paths,
            config=config,
        )
    append_snapshot(paths.snapshots_file, snapshot)
    if not thirty_minute_bars.empty:
        latest_30m = thirty_minute_bars.iloc[-1]
        snapshot["thirty_minute_action"] = latest_30m.get("shadow_action")
        snapshot["thirty_minute_z"] = to_float(latest_30m.get("soxl_z_5bar"))
    if not challenger_bars.empty:
        snapshot["challenger_action"] = challenger_bars.iloc[-1].get("shadow_action")
    if paper_result:
        snapshot["thirty_minute_paper_action"] = paper_result.get("action")
    if overnight_result:
        snapshot["overnight_paper_action"] = overnight_result.get("action")
    return snapshot


def print_snapshot(snapshot: dict[str, Any]) -> None:
    print("=" * 80)
    print("SOXL LOCAL INTRADAY MONITOR")
    print("=" * 80)
    print(f"Market date: {snapshot.get('market_date')}")
    print(f"Timestamp: {snapshot.get('timestamp')}")
    print(f"Watch state: {snapshot.get('watch_state')}")
    print(f"Reason: {snapshot.get('reason')}")
    print(f"SOXL last: {snapshot.get('soxl_last')}")
    print(f"SOXL from open: {snapshot.get('soxl_from_open_pct')}")
    print(f"SOXL session range: {snapshot.get('soxl_range_pct')}")
    if snapshot.get("thirty_minute_action"):
        print(f"30m shadow action: {snapshot.get('thirty_minute_action')}")
        print(f"30m z-score: {snapshot.get('thirty_minute_z')}")
    if snapshot.get("thirty_minute_paper_action"):
        print(f"30m paper action: {snapshot.get('thirty_minute_paper_action')}")
    if snapshot.get("challenger_action"):
        print(f"Adaptive research action: {snapshot.get('challenger_action')}")
    if snapshot.get("overnight_paper_action"):
        print(f"Overnight paper action: {snapshot.get('overnight_paper_action')}")
    if snapshot.get("data_warning"):
        print(f"Data warning: {snapshot.get('data_warning')}")


def print_backtest_result(result: dict[str, Any]) -> None:
    summary = result["summary"]
    best = result.get("best") or {}
    validated = result.get("validated") or {}
    challenger = result.get("challenger") or {}
    challenger_summary = challenger.get("summary") or {}
    challenger_validation = challenger.get("validation") or {}
    print("=" * 80)
    print("SOXL 30M RESEARCH STRATEGY BACKTEST")
    print("=" * 80)
    print(f"Requested period: {result.get('requested_period')}")
    print(f"Used period: {result.get('used_period')}")
    print(f"Bars: {summary.get('bars')}")
    print(f"Trades: {summary.get('trades')}")
    print(f"Total return: {summary.get('total_return')}")
    print(f"Win rate: {summary.get('win_rate')}")
    print(f"Max drawdown: {summary.get('max_drawdown')}")
    if best:
        print("-" * 80)
        print("Best parameter row in this small sample:")
        print(
            "entry={entry_style}, z={z_threshold}, hold={hold_bars}, "
            "regime={regime_floor_pct}, wait={bounce_wait_bars}, "
            "vwap={require_vwap_reclaim}, overnight={allow_overnight}, "
            "return={total_return}, trades={trades}, score={score}".format(**best)
        )
    if validated:
        print("-" * 80)
        print("Best train/test validated row:")
        print(
            "entry={entry_style}, z={z_threshold}, hold={hold_bars}, "
            "regime={regime_floor_pct}, wait={bounce_wait_bars}, "
            "vwap={require_vwap_reclaim}, train_return={train_return}, "
            "test_return={test_return}, test_trades={test_trades}, "
            "passes={passes_validation}, validation_score={validation_score}".format(
                **validated
            )
        )
    if challenger_summary:
        print("-" * 80)
        print("Research-only adaptive challenger (live v4 remains unchanged):")
        print(
            "version={strategy_version}, return={total_return}, trades={trades}, "
            "win_rate={win_rate}, max_drawdown={max_drawdown}".format(
                **challenger_summary
            )
        )
        if challenger_validation:
            print(
                "chronological_check={passes_chronological_check}, "
                "train={train_return}, validation={validation_return}, "
                "test={test_return}".format(**challenger_validation)
            )

    robustness = result.get("robustness")
    if isinstance(robustness, pd.DataFrame) and not robustness.empty:
        print("-" * 80)
        print("Execution and cost robustness (causal next-bar-open rows):")
        full = robustness[
            (robustness["segment"] == "full")
            & (robustness["entry_execution"] == "next_bar_open")
            & (
                pd.to_numeric(robustness["slippage"], errors="coerce").isin(
                    [0.001, 0.003]
                )
            )
        ]
        for row in full.to_dict(orient="records"):
            print(
                f"version={row.get('strategy_version')}, "
                f"slippage={row.get('slippage')}, "
                f"return={row.get('total_return')}, "
                f"trades={row.get('trades')}, "
                f"win_rate={row.get('win_rate')}, "
                f"max_drawdown={row.get('max_drawdown')}"
            )

    daily_shock_latest = result.get("daily_shock_latest") or {}
    daily_shock_context = result.get("daily_shock_context")
    if daily_shock_latest:
        print("-" * 80)
        print(
            "Latest completed daily shock context: "
            f"date={daily_shock_latest.get('market_date')}, "
            f"5d_return={daily_shock_latest.get('return_5d')}, "
            f"20d_drawdown={daily_shock_latest.get('drawdown_20d')}"
        )
    if isinstance(daily_shock_context, pd.DataFrame) and not daily_shock_context.empty:
        severe_five_day = daily_shock_context[
            (daily_shock_context["shock_threshold_5d"] == -0.30)
            & (daily_shock_context["forward_sessions"] == 5)
        ]
        if not severe_five_day.empty:
            row = severe_five_day.iloc[0]
            print(
                "Modern non-overlapping 5d shocks <= -30%, next 5 sessions: "
                f"events={int(row['events'])}, "
                f"median={row['median_forward_return']}, "
                f"positive_rate={row['positive_rate']}, "
                f"worst={row['worst_forward_return']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local SOXL intraday monitor.")
    parser.add_argument("--interval", default=IntradayConfig.interval)
    parser.add_argument("--period", default=IntradayConfig.period)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--backtest-period", default=IntradayConfig.backtest_period)
    parser.add_argument(
        "--paper-trade-30m",
        action="store_true",
        help="Also run local 30-minute paper accounting. Default is research/log only.",
    )
    parser.add_argument(
        "--paper-trade-overnight",
        action="store_true",
        help="Run the separate close-to-next-open rebound paper account.",
    )
    parser.add_argument(
        "--backfill-overnight-paper",
        action="store_true",
        help="Rebuild the overnight paper account from labeled historical simulation.",
    )
    parser.add_argument("--backfill-sessions", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=int, default=300)
    parser.add_argument("--bars-file", type=Path, default=INTRADAY_BARS_FILE)
    parser.add_argument("--snapshots-file", type=Path, default=INTRADAY_SNAPSHOTS_FILE)
    parser.add_argument("--thirty-minute-file", type=Path, default=INTRADAY_30M_FILE)
    parser.add_argument(
        "--challenger-file",
        type=Path,
        default=INTRADAY_30M_CHALLENGER_FILE,
    )
    args = parser.parse_args()

    config = IntradayConfig(
        interval=args.interval,
        period=args.period,
        backtest_period=args.backtest_period,
    )
    paths = IntradayPaths(
        bars_file=args.bars_file,
        snapshots_file=args.snapshots_file,
        thirty_minute_file=args.thirty_minute_file,
        thirty_minute_challenger_file=args.challenger_file,
    )

    if args.backtest:
        result = run_backtest(paths=paths, config=config, period=args.backtest_period)
        print_backtest_result(result)
        return

    if args.backfill_overnight_paper:
        historical_bars = read_csv_or_empty(INTRADAY_30M_BACKTEST_BARS_FILE)
        live_bars = read_csv_or_empty(INTRADAY_30M_FILE)
        if not live_bars.empty:
            historical_bars = pd.concat(
                [historical_bars, live_bars],
                ignore_index=True,
            ).drop_duplicates(subset=["timestamp"], keep="last")
        if historical_bars.empty:
            raise SystemExit(
                "Run the 60-day backtest before rebuilding the overnight paper backfill."
            )
        result = backfill_overnight_rebound_paper(
            historical_bars,
            sessions=args.backfill_sessions,
            paths=paths,
            config=config,
        )
        print("=" * 80)
        print("SOXL OVERNIGHT REBOUND PAPER BACKFILL (SIMULATED)")
        print("=" * 80)
        print(f"Sessions: {result['sessions']}")
        print(f"Events: {len(result['events'])}")
        print(f"Trades: {len(result['trades'])}")
        print(f"Paper equity: {result['state'].get('paper_equity')}")
        return

    while True:
        try:
            snapshot = run_once(
                paths=paths,
                config=config,
                paper_trade_30m=args.paper_trade_30m,
                paper_trade_overnight=args.paper_trade_overnight,
            )
            print_snapshot(snapshot)
        except IntradayDataError as error:
            print(f"Intraday data unavailable: {error}", file=sys.stderr)
            if not args.loop:
                raise SystemExit(1) from error
        except Exception as error:
            print(f"Unexpected intraday monitor error: {error}", file=sys.stderr)
            if not args.loop:
                raise

        if not args.loop:
            break
        time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
