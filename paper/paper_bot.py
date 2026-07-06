from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from strategy.config import FAST_STRATEGY_CONFIG, FastStrategyConfig
from strategy.signals import MarketDataError, build_signal_frame, read_ohlcv_csv


STATE_SCHEMA_VERSION = 2

DATA_DIR = Path("data")
PAPER_DIR = DATA_DIR / "paper"
STATE_FILE = PAPER_DIR / "paper_state.json"
DAILY_LOG_FILE = PAPER_DIR / "paper_daily_log.csv"
TRADE_LOG_FILE = PAPER_DIR / "paper_trade_log.csv"

DAILY_LOG_COLUMNS = [
    "run_timestamp",
    "strategy_version",
    "market_date",
    "soxl_open",
    "soxl_high",
    "soxl_low",
    "soxl_close",
    "soxl_mean_5",
    "soxl_std_5",
    "soxl_z_score",
    "qqq_close",
    "qqq_ma50",
    "qqq_above_ma50",
    "oversold",
    "episode_start",
    "buy_signal",
    "account_state",
    "in_position",
    "pending_entry",
    "signal_date",
    "entry_date",
    "entry_price",
    "shares",
    "days_held",
    "position_market_value",
    "current_position_return",
    "current_marked_pl",
    "paper_cash",
    "paper_realized_equity",
    "paper_marked_equity",
    "equity_peak",
    "current_drawdown",
    "max_mark_to_market_drawdown",
    "next_action",
    "reason",
    "data_warning",
]

TRADE_LOG_COLUMNS = [
    "strategy_version",
    "signal_date",
    "entry_date",
    "exit_date",
    "hold_days",
    "entry_open",
    "entry_price",
    "exit_close",
    "exit_price",
    "shares",
    "invested_capital",
    "cash_after_entry",
    "equity_before_entry",
    "equity_after_exit",
    "position_return",
    "account_return",
    "exit_reason",
]

MARKET_TIMEZONE = ZoneInfo("America/New_York")
CURRENT_DAY_COMPLETE_HOUR_ET = 17


class PaperStateError(RuntimeError):
    """Raised when the persisted paper state is internally inconsistent."""


@dataclass(frozen=True)
class PaperPaths:
    state_file: Path = STATE_FILE
    daily_log_file: Path = DAILY_LOG_FILE
    trade_log_file: Path = TRADE_LOG_FILE
    local_data_dir: Path = DATA_DIR


@dataclass
class RunResult:
    processed: bool
    market_date: str | None
    action: str
    reason: str
    state: dict[str, Any]
    daily_row: dict[str, Any] | None = None
    trade_row: dict[str, Any] | None = None
    data_warning: str = ""


def default_state(config: FastStrategyConfig) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "strategy_version": config.strategy_version,
        "paper_equity": config.starting_capital,
        "cash": config.starting_capital,
        "marked_equity": config.starting_capital,
        "equity_peak": config.starting_capital,
        "current_drawdown": 0.0,
        "max_mark_to_market_drawdown": 0.0,
        "position_market_value": 0.0,
        "current_position_return": 0.0,
        "current_marked_pl": 0.0,
        "in_position": False,
        "pending_entry": False,
        "signal_date": None,
        "entry_date": None,
        "entry_open": None,
        "entry_price": None,
        "shares": 0.0,
        "invested_capital": 0.0,
        "account_equity_before_entry": None,
        "days_held": 0,
        "last_processed_market_date": None,
        "last_run_timestamp": None,
        "last_action": None,
        "last_reason": None,
    }


def parse_market_date(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    return pd.Timestamp(value).normalize()


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return float(value)


def is_valid_price(value: Any) -> bool:
    number = to_float(value)
    return number is not None and math.isfinite(number) and number > 0


def account_state_name(state: dict[str, Any]) -> str:
    if state.get("in_position"):
        return "in_position"
    if state.get("pending_entry"):
        return "pending_entry"
    return "flat"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r") as file:
        return json.load(file)


def save_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=4, sort_keys=True) + "\n")
    temp_path.replace(path)


def infer_last_logged_market_date(path: Path) -> str | None:
    if not path.exists():
        return None

    try:
        log = pd.read_csv(path, usecols=["market_date"])
    except (ValueError, pd.errors.EmptyDataError):
        return None

    if log.empty:
        return None

    dates = pd.to_datetime(log["market_date"], errors="coerce").dropna()
    if dates.empty:
        return None

    return str(dates.max().date())


def migrate_state(
    raw_state: dict[str, Any],
    config: FastStrategyConfig,
    daily_log_file: Path,
) -> dict[str, Any]:
    state = default_state(config)
    state.update(raw_state)

    state_version = state.get("strategy_version")
    has_live_exposure = bool(state.get("in_position") or state.get("pending_entry"))

    if state_version not in (None, config.strategy_version) and has_live_exposure:
        raise PaperStateError(
            "Paper state has live exposure for a different strategy version: "
            f"{state_version}. Close or migrate that state manually before running "
            f"{config.strategy_version}."
        )

    if state_version is None and has_live_exposure:
        raise PaperStateError(
            "Paper state has live exposure but no strategy_version. This looks like "
            "legacy 20-day state, so it must be migrated manually."
        )

    state["schema_version"] = STATE_SCHEMA_VERSION
    state["strategy_version"] = config.strategy_version

    if state.get("marked_equity") is None:
        state["marked_equity"] = state.get("paper_equity", config.starting_capital)
    if state.get("equity_peak") is None:
        state["equity_peak"] = state["marked_equity"]

    if state.get("last_processed_market_date") is None:
        state["last_processed_market_date"] = infer_last_logged_market_date(
            daily_log_file
        )

    for legacy_key in ("stop_price", "target_price"):
        state.pop(legacy_key, None)

    return state


def load_state(paths: PaperPaths, config: FastStrategyConfig) -> dict[str, Any]:
    if not paths.state_file.exists():
        return default_state(config)

    return migrate_state(load_json(paths.state_file), config, paths.daily_log_file)


def next_legacy_path(path: Path) -> Path:
    candidate = path.with_name(f"{path.stem}_legacy{path.suffix}")
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}_legacy_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def ensure_log_schema(path: Path, columns: list[str]) -> str:
    if not path.exists():
        return ""

    try:
        existing_columns = list(pd.read_csv(path, nrows=0).columns)
    except pd.errors.EmptyDataError:
        path.unlink()
        return "Removed empty log file before writing a new schema."

    if existing_columns == columns:
        return ""

    legacy_path = next_legacy_path(path)
    path.replace(legacy_path)
    return f"Moved incompatible existing log to {legacy_path}."


def append_row_once(
    path: Path,
    row: dict[str, Any],
    columns: list[str],
    unique_keys: list[str],
) -> tuple[bool, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_message = ensure_log_schema(path, columns)

    ordered_row = {column: row.get(column) for column in columns}

    if path.exists():
        existing = pd.read_csv(path, dtype=str)
        if all(key in existing.columns for key in unique_keys):
            duplicate_mask = pd.Series(True, index=existing.index)
            for key in unique_keys:
                duplicate_mask &= existing[key].astype(str) == str(ordered_row[key])
            if bool(duplicate_mask.any()):
                return False, schema_message

        pd.DataFrame([ordered_row], columns=columns).to_csv(
            path,
            mode="a",
            header=False,
            index=False,
        )
        return True, schema_message

    pd.DataFrame([ordered_row], columns=columns).to_csv(path, index=False)
    return True, schema_message


def download_yahoo_ohlcv(ticker: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as error:
        raise MarketDataError(
            "yfinance is required for --source yahoo. Use --source local for "
            "offline testing."
        ) from error

    data = yf.download(
        ticker,
        period="18mo",
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if data.empty:
        raise MarketDataError(f"Yahoo returned no data for {ticker}.")

    return data


def load_market_frame(
    source: str,
    paths: PaperPaths,
    config: FastStrategyConfig,
    as_of: str | None = None,
) -> pd.DataFrame:
    if source == "local":
        soxl = read_ohlcv_csv(paths.local_data_dir / f"{config.symbol}.csv", config.symbol)
        qqq = read_ohlcv_csv(
            paths.local_data_dir / f"{config.regime_symbol}.csv",
            config.regime_symbol,
        )
    elif source == "yahoo":
        soxl = download_yahoo_ohlcv(config.symbol)
        qqq = download_yahoo_ohlcv(config.regime_symbol)
    else:
        raise MarketDataError(f"Unknown data source: {source}")

    frame = build_signal_frame(soxl, qqq, config=config)

    if as_of is not None:
        as_of_date = pd.Timestamp(as_of).normalize()
        frame = frame[frame.index <= as_of_date].copy()

    if frame.empty:
        raise MarketDataError("No market data is available for the requested date.")

    if source == "yahoo" and as_of is None:
        frame = remove_incomplete_current_day_bar(frame)

    if frame.empty:
        raise MarketDataError(
            "No completed market data is available yet. This can happen before "
            "the first completed daily bar or if the latest Yahoo row was an "
            "incomplete same-day bar."
        )

    return frame


def remove_incomplete_current_day_bar(
    frame: pd.DataFrame,
    now_et: datetime | None = None,
) -> pd.DataFrame:
    now_et = now_et or datetime.now(MARKET_TIMEZONE)
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=MARKET_TIMEZONE)
    else:
        now_et = now_et.astimezone(MARKET_TIMEZONE)

    latest_date = frame.index[-1].date()
    current_date = now_et.date()

    if (
        latest_date >= current_date
        and now_et.hour < CURRENT_DAY_COMPLETE_HOUR_ET
    ):
        return frame.iloc[:-1].copy()

    return frame


def latest_data_warning(latest: pd.Series) -> str:
    warnings = []

    if to_float(latest.get("qqq_close")) is None:
        warnings.append("QQQ close missing for latest SOXL date")
    if to_float(latest.get("qqq_ma50")) is None:
        warnings.append("QQQ MA50 unavailable")
    if to_float(latest.get("soxl_mean_5")) is None:
        warnings.append("SOXL 5-day mean unavailable")
    if to_float(latest.get("soxl_std_5")) in (None, 0.0):
        warnings.append("SOXL 5-day standard deviation unavailable")

    return "; ".join(warnings)


def mark_position(
    state: dict[str, Any],
    latest_close: float,
    config: FastStrategyConfig,
) -> None:
    shares = float(state.get("shares", 0.0))
    cash = float(state.get("cash", 0.0))
    entry_price = float(state.get("entry_price", 0.0))

    position_value = shares * latest_close
    marked_equity = cash + position_value
    current_marked_pl = marked_equity - float(
        state.get("account_equity_before_entry") or state.get("paper_equity")
    )

    if entry_price > 0:
        current_position_return = latest_close / entry_price - 1
    else:
        current_position_return = 0.0

    equity_peak = max(float(state.get("equity_peak", marked_equity)), marked_equity)
    current_drawdown = marked_equity / equity_peak - 1 if equity_peak else 0.0
    max_drawdown = min(
        float(state.get("max_mark_to_market_drawdown", 0.0)),
        current_drawdown,
    )

    state["position_market_value"] = float(position_value)
    state["marked_equity"] = float(marked_equity)
    state["current_marked_pl"] = float(current_marked_pl)
    state["current_position_return"] = float(current_position_return)
    state["equity_peak"] = float(equity_peak)
    state["current_drawdown"] = float(current_drawdown)
    state["max_mark_to_market_drawdown"] = float(max_drawdown)


def reset_flat_state_after_exit(
    state: dict[str, Any],
    final_equity: float,
) -> None:
    state.update(
        {
            "paper_equity": float(final_equity),
            "cash": float(final_equity),
            "marked_equity": float(final_equity),
            "position_market_value": 0.0,
            "current_position_return": 0.0,
            "current_marked_pl": 0.0,
            "in_position": False,
            "pending_entry": False,
            "signal_date": None,
            "entry_date": None,
            "entry_open": None,
            "entry_price": None,
            "shares": 0.0,
            "invested_capital": 0.0,
            "account_equity_before_entry": None,
            "days_held": 0,
        }
    )
    state["equity_peak"] = float(max(state.get("equity_peak", final_equity), final_equity))
    state["current_drawdown"] = float(final_equity / state["equity_peak"] - 1)


def fill_pending_entry(
    frame: pd.DataFrame,
    state: dict[str, Any],
    latest_date: pd.Timestamp,
    config: FastStrategyConfig,
) -> tuple[bool, str]:
    signal_date = parse_market_date(state.get("signal_date"))
    if signal_date is None:
        raise PaperStateError("pending_entry is true but signal_date is missing.")

    if latest_date <= signal_date:
        return False, "Waiting for the first completed bar after the signal date."

    future_rows = frame[frame.index > signal_date]
    if future_rows.empty:
        return False, "Waiting for the next SOXL trading session after the signal."

    entry_date = future_rows.index[0]
    entry_row = future_rows.iloc[0]

    if not is_valid_price(entry_row["Open"]):
        raise MarketDataError(f"SOXL open is missing for entry date {entry_date.date()}.")

    raw_entry_open = float(entry_row["Open"])
    entry_price = raw_entry_open * (1 + config.slippage)

    account_equity = float(state.get("marked_equity") or state["paper_equity"])
    invested_capital = account_equity * config.position_fraction
    shares = invested_capital / entry_price
    cash = account_equity - invested_capital

    state.update(
        {
            "cash": float(cash),
            "in_position": True,
            "pending_entry": False,
            "entry_date": str(entry_date.date()),
            "entry_open": float(raw_entry_open),
            "entry_price": float(entry_price),
            "shares": float(shares),
            "invested_capital": float(invested_capital),
            "account_equity_before_entry": float(account_equity),
            "days_held": 0,
        }
    )

    return True, (
        f"Pending entry filled at next open on {entry_date.date()} "
        f"for ${entry_price:.2f} including slippage."
    )


def maybe_exit_position(
    frame: pd.DataFrame,
    state: dict[str, Any],
    latest_date: pd.Timestamp,
    config: FastStrategyConfig,
) -> tuple[bool, dict[str, Any] | None, str]:
    entry_date = parse_market_date(state.get("entry_date"))
    if entry_date is None:
        raise PaperStateError("in_position is true but entry_date is missing.")

    position_rows = frame[(frame.index >= entry_date) & (frame.index <= latest_date)]
    if position_rows.empty:
        raise MarketDataError(
            f"No SOXL bars found from entry date {entry_date.date()} through "
            f"{latest_date.date()}."
        )

    observed_days = len(position_rows)
    state["days_held"] = int(observed_days)

    latest_row = frame.loc[latest_date]
    if not is_valid_price(latest_row["Close"]):
        raise MarketDataError(f"SOXL close is missing for {latest_date.date()}.")

    if observed_days < config.hold_days:
        mark_position(state, float(latest_row["Close"]), config)
        return False, None, (
            f"Position open. Holding day {observed_days} of {config.hold_days}; "
            f"marked equity is ${state['marked_equity']:,.2f}."
        )

    scheduled_exit_date = position_rows.index[config.hold_days - 1]
    scheduled_exit_row = position_rows.iloc[config.hold_days - 1]

    if not is_valid_price(scheduled_exit_row["Close"]):
        raise MarketDataError(
            f"SOXL close is missing for scheduled exit date "
            f"{scheduled_exit_date.date()}."
        )

    exit_close = float(scheduled_exit_row["Close"])
    mark_position(state, exit_close, config)

    exit_price = exit_close * (1 - config.slippage)
    shares = float(state["shares"])
    final_equity = float(state["cash"]) + shares * exit_price
    equity_before_entry = float(
        state.get("account_equity_before_entry") or state["paper_equity"]
    )

    position_return = exit_price / float(state["entry_price"]) - 1
    account_return = final_equity / equity_before_entry - 1

    trade_row = {
        "strategy_version": config.strategy_version,
        "signal_date": state.get("signal_date"),
        "entry_date": state.get("entry_date"),
        "exit_date": str(scheduled_exit_date.date()),
        "hold_days": int(config.hold_days),
        "entry_open": state.get("entry_open"),
        "entry_price": state.get("entry_price"),
        "exit_close": float(exit_close),
        "exit_price": float(exit_price),
        "shares": shares,
        "invested_capital": state.get("invested_capital"),
        "cash_after_entry": state.get("cash"),
        "equity_before_entry": equity_before_entry,
        "equity_after_exit": float(final_equity),
        "position_return": float(position_return),
        "account_return": float(account_return),
        "exit_reason": f"fixed_hold_day_{config.hold_days}",
    }

    reset_flat_state_after_exit(state, final_equity)

    if scheduled_exit_date < latest_date:
        return True, trade_row, (
            f"Exited at the scheduled day-{config.hold_days} close on "
            f"{scheduled_exit_date.date()} for ${exit_price:.2f} including "
            f"slippage. Latest available data was {latest_date.date()}."
        )

    return True, trade_row, (
        f"Exited at day-{config.hold_days} close on {scheduled_exit_date.date()} "
        f"for ${exit_price:.2f} including slippage."
    )


def schedule_new_entry(
    state: dict[str, Any],
    signal_date: pd.Timestamp,
) -> None:
    state["pending_entry"] = True
    state["signal_date"] = str(signal_date.date())


def build_daily_row(
    now: datetime,
    latest_date: pd.Timestamp,
    latest: pd.Series,
    state: dict[str, Any],
    action: str,
    reason: str,
    data_warning: str,
    config: FastStrategyConfig,
) -> dict[str, Any]:
    return {
        "run_timestamp": now.isoformat(),
        "strategy_version": config.strategy_version,
        "market_date": str(latest_date.date()),
        "soxl_open": to_float(latest.get("Open")),
        "soxl_high": to_float(latest.get("High")),
        "soxl_low": to_float(latest.get("Low")),
        "soxl_close": to_float(latest.get("Close")),
        "soxl_mean_5": to_float(latest.get("soxl_mean_5")),
        "soxl_std_5": to_float(latest.get("soxl_std_5")),
        "soxl_z_score": to_float(latest.get("soxl_z_score")),
        "qqq_close": to_float(latest.get("qqq_close")),
        "qqq_ma50": to_float(latest.get("qqq_ma50")),
        "qqq_above_ma50": bool(latest.get("qqq_above_ma50", False)),
        "oversold": bool(latest.get("oversold", False)),
        "episode_start": bool(latest.get("episode_start", False)),
        "buy_signal": bool(latest.get("buy_signal", False)),
        "account_state": account_state_name(state),
        "in_position": bool(state.get("in_position")),
        "pending_entry": bool(state.get("pending_entry")),
        "signal_date": state.get("signal_date"),
        "entry_date": state.get("entry_date"),
        "entry_price": state.get("entry_price"),
        "shares": state.get("shares"),
        "days_held": state.get("days_held"),
        "position_market_value": state.get("position_market_value"),
        "current_position_return": state.get("current_position_return"),
        "current_marked_pl": state.get("current_marked_pl"),
        "paper_cash": state.get("cash"),
        "paper_realized_equity": state.get("paper_equity"),
        "paper_marked_equity": state.get("marked_equity"),
        "equity_peak": state.get("equity_peak"),
        "current_drawdown": state.get("current_drawdown"),
        "max_mark_to_market_drawdown": state.get("max_mark_to_market_drawdown"),
        "next_action": action,
        "reason": reason,
        "data_warning": data_warning,
    }


def process_frame(
    frame: pd.DataFrame,
    state: dict[str, Any],
    paths: PaperPaths,
    config: FastStrategyConfig = FAST_STRATEGY_CONFIG,
    now: datetime | None = None,
    dry_run: bool = False,
) -> RunResult:
    if frame.empty:
        raise MarketDataError("No market data available to process.")

    now = now or datetime.now()
    latest_date = frame.index[-1]
    latest = frame.iloc[-1]

    last_processed = parse_market_date(state.get("last_processed_market_date"))
    if last_processed is not None and latest_date <= last_processed:
        return RunResult(
            processed=False,
            market_date=str(latest_date.date()),
            action="NO NEW DATA",
            reason=(
                f"Latest completed market date {latest_date.date()} was already "
                f"processed on or before {last_processed.date()}."
            ),
            state=state,
        )

    data_warning = latest_data_warning(latest)
    action = "NO TRADE"
    reason = "No valid entry signal."
    trade_row = None

    if bool(state.get("pending_entry")) and not bool(state.get("in_position")):
        filled, fill_reason = fill_pending_entry(frame, state, latest_date, config)
        if filled:
            action = "BUY"
            reason = fill_reason
        else:
            action = "WAITING FOR ENTRY"
            reason = fill_reason

    if bool(state.get("in_position")):
        exited, candidate_trade_row, exit_reason = maybe_exit_position(
            frame,
            state,
            latest_date,
            config,
        )
        if exited:
            trade_row = candidate_trade_row
            action = "SELL" if action != "BUY" else "BUY AND SELL"
            reason = exit_reason
        elif action == "BUY":
            action = "BUY AND HOLD"
            reason = f"{reason} {exit_reason}"
        else:
            action = "HOLD"
            reason = exit_reason

    if not bool(state.get("in_position")) and not bool(state.get("pending_entry")):
        if bool(latest["buy_signal"]):
            schedule_new_entry(state, latest_date)
            if action == "SELL":
                action = "SELL AND BUY NEXT OPEN"
                reason = (
                    f"{reason} New fast-strategy signal also occurred after the "
                    "close, so a next-open entry is pending."
                )
            else:
                action = "BUY NEXT OPEN"
                reason = (
                    f"SOXL 5-day z-score is {latest['soxl_z_score']:.3f}, this "
                    "is a new oversold episode, and QQQ is above its 50-day MA."
                )
        elif data_warning and action == "NO TRADE":
            reason = f"No valid entry signal. Data warning: {data_warning}."

    if not bool(state.get("in_position")):
        state["marked_equity"] = float(state["paper_equity"])
        state["position_market_value"] = 0.0
        state["current_position_return"] = 0.0
        state["current_marked_pl"] = 0.0
        state["equity_peak"] = float(max(state["equity_peak"], state["marked_equity"]))
        state["current_drawdown"] = float(state["marked_equity"] / state["equity_peak"] - 1)

    state["last_processed_market_date"] = str(latest_date.date())
    state["last_run_timestamp"] = now.isoformat()
    state["last_action"] = action
    state["last_reason"] = reason

    daily_row = build_daily_row(
        now=now,
        latest_date=latest_date,
        latest=latest,
        state=state,
        action=action,
        reason=reason,
        data_warning=data_warning,
        config=config,
    )

    if not dry_run:
        log_messages = []
        if trade_row is not None:
            _, message = append_row_once(
                paths.trade_log_file,
                trade_row,
                TRADE_LOG_COLUMNS,
                ["strategy_version", "entry_date", "exit_date"],
            )
            if message:
                log_messages.append(message)

        _, message = append_row_once(
            paths.daily_log_file,
            daily_row,
            DAILY_LOG_COLUMNS,
            ["strategy_version", "market_date"],
        )
        if message:
            log_messages.append(message)

        if log_messages:
            daily_row["data_warning"] = "; ".join(
                filter(None, [daily_row["data_warning"], *log_messages])
            )

        save_json_atomic(paths.state_file, state)

    return RunResult(
        processed=True,
        market_date=str(latest_date.date()),
        action=action,
        reason=reason,
        state=state,
        daily_row=daily_row,
        trade_row=trade_row,
        data_warning=data_warning,
    )


def run_once(
    source: str,
    paths: PaperPaths,
    config: FastStrategyConfig = FAST_STRATEGY_CONFIG,
    as_of: str | None = None,
    dry_run: bool = False,
) -> RunResult:
    state = load_state(paths, config)
    frame = load_market_frame(source=source, paths=paths, config=config, as_of=as_of)
    result = process_frame(
        frame=frame,
        state=state,
        paths=paths,
        config=config,
        dry_run=dry_run,
    )

    if not result.processed and state != load_state(paths, config):
        save_json_atomic(paths.state_file, state)

    return result


def print_result(result: RunResult, paths: PaperPaths) -> None:
    print()
    print("=" * 80)
    print("SOXL FAST PAPER BOT")
    print("=" * 80)
    print()
    print(f"Market date: {result.market_date}")
    print(f"Action: {result.action}")
    print(f"Reason: {result.reason}")
    print()
    print(f"Account state: {account_state_name(result.state)}")
    print(f"Cash: ${float(result.state['cash']):,.2f}")
    print(f"Marked equity: ${float(result.state['marked_equity']):,.2f}")
    print(f"Max mark-to-market drawdown: {float(result.state['max_mark_to_market_drawdown']):.2%}")

    if result.state.get("in_position"):
        print(f"Entry date: {result.state.get('entry_date')}")
        print(f"Entry price: ${float(result.state['entry_price']):.2f}")
        print(f"Shares: {float(result.state['shares']):.4f}")
        print(f"Days held: {int(result.state['days_held'])}")

    if result.state.get("pending_entry"):
        print(f"Pending signal date: {result.state.get('signal_date')}")

    print()
    print(f"State file: {paths.state_file}")
    print(f"Daily log: {paths.daily_log_file}")
    print(f"Trade log: {paths.trade_log_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen SOXL fast-strategy daily paper bot."
    )
    parser.add_argument(
        "--source",
        choices=["yahoo", "local"],
        default="yahoo",
        help="Use Yahoo data for daily operation or local CSVs for offline testing.",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Only process data up through this YYYY-MM-DD date.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate the action without writing state or logs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = PaperPaths()

    try:
        result = run_once(
            source=args.source,
            paths=paths,
            config=FAST_STRATEGY_CONFIG,
            as_of=args.as_of,
            dry_run=args.dry_run,
        )
    except (MarketDataError, PaperStateError) as error:
        print()
        print("=" * 80)
        print("SOXL FAST PAPER BOT ERROR")
        print("=" * 80)
        print()
        print(str(error))
        return 1

    print_result(result, paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
