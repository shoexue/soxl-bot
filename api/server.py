from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from intraday.monitor import (
    INTRADAY_30M_BACKTEST_BARS_FILE as DEFAULT_INTRADAY_30M_BACKTEST_BARS_FILE,
    INTRADAY_30M_BACKTEST_EQUITY_FILE as DEFAULT_INTRADAY_30M_BACKTEST_EQUITY_FILE,
    INTRADAY_30M_BACKTEST_SUMMARY_FILE as DEFAULT_INTRADAY_30M_BACKTEST_SUMMARY_FILE,
    INTRADAY_30M_BACKTEST_TRADES_FILE as DEFAULT_INTRADAY_30M_BACKTEST_TRADES_FILE,
    INTRADAY_30M_CHALLENGER_EQUITY_FILE as DEFAULT_INTRADAY_30M_CHALLENGER_EQUITY_FILE,
    INTRADAY_30M_CHALLENGER_FILE as DEFAULT_INTRADAY_30M_CHALLENGER_FILE,
    INTRADAY_30M_CHALLENGER_SUMMARY_FILE as DEFAULT_INTRADAY_30M_CHALLENGER_SUMMARY_FILE,
    INTRADAY_30M_CHALLENGER_TRADES_FILE as DEFAULT_INTRADAY_30M_CHALLENGER_TRADES_FILE,
    INTRADAY_30M_CHALLENGER_VALIDATION_FILE as DEFAULT_INTRADAY_30M_CHALLENGER_VALIDATION_FILE,
    INTRADAY_30M_FILE as DEFAULT_INTRADAY_30M_FILE,
    INTRADAY_30M_PARAMETER_COMPARISON_FILE as DEFAULT_INTRADAY_30M_PARAMETER_COMPARISON_FILE,
    INTRADAY_30M_ROBUSTNESS_FILE as DEFAULT_INTRADAY_30M_ROBUSTNESS_FILE,
    INTRADAY_30M_VALIDATION_FILE as DEFAULT_INTRADAY_30M_VALIDATION_FILE,
    INTRADAY_DAILY_SHOCK_CONTEXT_FILE as DEFAULT_INTRADAY_DAILY_SHOCK_CONTEXT_FILE,
    INTRADAY_DAILY_SHOCK_LATEST_FILE as DEFAULT_INTRADAY_DAILY_SHOCK_LATEST_FILE,
    INTRADAY_BARS_FILE as DEFAULT_INTRADAY_BARS_FILE,
    INTRADAY_SNAPSHOTS_FILE as DEFAULT_INTRADAY_SNAPSHOTS_FILE,
    OVERNIGHT_REBOUND_PAPER_LOG_FILE as DEFAULT_OVERNIGHT_REBOUND_PAPER_LOG_FILE,
    OVERNIGHT_REBOUND_PAPER_STATE_FILE as DEFAULT_OVERNIGHT_REBOUND_PAPER_STATE_FILE,
    OVERNIGHT_REBOUND_TRADE_LOG_FILE as DEFAULT_OVERNIGHT_REBOUND_TRADE_LOG_FILE,
)
from strategy.config import FAST_STRATEGY_CONFIG


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PAPER_DIR = DATA_DIR / "paper"

STATE_FILE = PAPER_DIR / "paper_state.json"
DAILY_LOG_FILE = PAPER_DIR / "paper_daily_log.csv"
TRADE_LOG_FILE = PAPER_DIR / "paper_trade_log.csv"
INTRADAY_BARS_FILE = ROOT / DEFAULT_INTRADAY_BARS_FILE
INTRADAY_SNAPSHOTS_FILE = ROOT / DEFAULT_INTRADAY_SNAPSHOTS_FILE
INTRADAY_30M_FILE = ROOT / DEFAULT_INTRADAY_30M_FILE
INTRADAY_30M_BACKTEST_BARS_FILE = ROOT / DEFAULT_INTRADAY_30M_BACKTEST_BARS_FILE
INTRADAY_30M_BACKTEST_SUMMARY_FILE = ROOT / DEFAULT_INTRADAY_30M_BACKTEST_SUMMARY_FILE
INTRADAY_30M_BACKTEST_TRADES_FILE = ROOT / DEFAULT_INTRADAY_30M_BACKTEST_TRADES_FILE
INTRADAY_30M_BACKTEST_EQUITY_FILE = ROOT / DEFAULT_INTRADAY_30M_BACKTEST_EQUITY_FILE
INTRADAY_30M_CHALLENGER_FILE = ROOT / DEFAULT_INTRADAY_30M_CHALLENGER_FILE
INTRADAY_30M_CHALLENGER_SUMMARY_FILE = (
    ROOT / DEFAULT_INTRADAY_30M_CHALLENGER_SUMMARY_FILE
)
INTRADAY_30M_CHALLENGER_TRADES_FILE = (
    ROOT / DEFAULT_INTRADAY_30M_CHALLENGER_TRADES_FILE
)
INTRADAY_30M_CHALLENGER_EQUITY_FILE = (
    ROOT / DEFAULT_INTRADAY_30M_CHALLENGER_EQUITY_FILE
)
INTRADAY_30M_CHALLENGER_VALIDATION_FILE = (
    ROOT / DEFAULT_INTRADAY_30M_CHALLENGER_VALIDATION_FILE
)
INTRADAY_30M_PARAMETER_COMPARISON_FILE = (
    ROOT / DEFAULT_INTRADAY_30M_PARAMETER_COMPARISON_FILE
)
INTRADAY_30M_VALIDATION_FILE = ROOT / DEFAULT_INTRADAY_30M_VALIDATION_FILE
INTRADAY_30M_ROBUSTNESS_FILE = ROOT / DEFAULT_INTRADAY_30M_ROBUSTNESS_FILE
INTRADAY_DAILY_SHOCK_CONTEXT_FILE = ROOT / DEFAULT_INTRADAY_DAILY_SHOCK_CONTEXT_FILE
INTRADAY_DAILY_SHOCK_LATEST_FILE = ROOT / DEFAULT_INTRADAY_DAILY_SHOCK_LATEST_FILE
OVERNIGHT_REBOUND_PAPER_STATE_FILE = ROOT / DEFAULT_OVERNIGHT_REBOUND_PAPER_STATE_FILE
OVERNIGHT_REBOUND_PAPER_LOG_FILE = ROOT / DEFAULT_OVERNIGHT_REBOUND_PAPER_LOG_FILE
OVERNIGHT_REBOUND_TRADE_LOG_FILE = ROOT / DEFAULT_OVERNIGHT_REBOUND_TRADE_LOG_FILE

HISTORICAL_SUMMARY_FILE = DATA_DIR / "execution_downside_summary.csv"
HISTORICAL_TRADES_FILE = DATA_DIR / "execution_downside_trades.csv"
RETURN_PATH_FILE = DATA_DIR / "fast_return_path_summary.csv"
WALK_FORWARD_OVERALL_FILE = DATA_DIR / "walk_forward_overall.csv"
SOXL_FILE = DATA_DIR / "SOXL.csv"
QQQ_FILE = DATA_DIR / "QQQ.csv"


app = FastAPI(
    title="SOXL Paper Bot API",
    version="0.1.0",
    description="Read-only API for paper-trading logs and historical context.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, Path):
        return str(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def records_safe(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    frame = frame.copy()
    for column in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = frame[column].dt.date.astype(str)

    records = []
    for row in frame.to_dict(orient="records"):
        records.append({key: json_safe(value) for key, value in row.items()})
    return records


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        with path.open("r") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {path}") from error


def read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def normalize_daily_log(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    normalized = frame.copy()

    rename_map = {
        "action": "next_action",
        "paper_equity": "paper_realized_equity",
    }
    normalized = normalized.rename(
        columns={old: new for old, new in rename_map.items() if old in normalized}
    )

    if "paper_marked_equity" not in normalized.columns:
        normalized["paper_marked_equity"] = normalized.get("paper_realized_equity")
    if "account_state" not in normalized.columns:
        normalized["account_state"] = normalized.apply(infer_account_state, axis=1)
    if "strategy_version" not in normalized.columns:
        normalized["strategy_version"] = FAST_STRATEGY_CONFIG.strategy_version
    if "data_warning" not in normalized.columns:
        normalized["data_warning"] = ""

    for column in ("run_timestamp", "market_date", "signal_date", "entry_date"):
        if column in normalized.columns:
            normalized[column] = normalized[column].astype(str)

    for column in (
        "qqq_above_ma50",
        "oversold",
        "episode_start",
        "buy_signal",
        "in_position",
        "pending_entry",
    ):
        if column in normalized.columns:
            normalized[column] = normalized[column].map(normalize_bool)

    return normalized


def infer_account_state(row: pd.Series) -> str:
    if normalize_bool(row.get("in_position")):
        return "in_position"
    if normalize_bool(row.get("pending_entry")):
        return "pending_entry"
    return "flat"


def latest_record(frame: pd.DataFrame) -> dict[str, Any] | None:
    records = records_safe(frame.tail(1))
    return records[0] if records else None


def latest_intraday_record(frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame.empty:
        return None
    records = []
    for row in frame.tail(1).to_dict(orient="records"):
        records.append({key: json_safe(value) for key, value in row.items()})
    return records[0] if records else None


def intraday_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [
        {key: json_safe(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def calculate_paper_performance(
    state: dict[str, Any],
    daily_log: pd.DataFrame,
    trade_log: pd.DataFrame,
) -> dict[str, Any]:
    marked_equity = state.get("marked_equity", state.get("paper_equity"))
    starting_capital = FAST_STRATEGY_CONFIG.starting_capital

    if marked_equity is None and not daily_log.empty:
        marked_equity = daily_log["paper_marked_equity"].dropna().iloc[-1]

    closed_trades = len(trade_log)
    win_rate = None
    avg_position_return = None
    total_account_return = None

    if not trade_log.empty:
        if "position_return" in trade_log.columns:
            returns = pd.to_numeric(trade_log["position_return"], errors="coerce").dropna()
            if not returns.empty:
                win_rate = float((returns > 0).mean())
                avg_position_return = float(returns.mean())
        if "equity_after_exit" in trade_log.columns:
            final_equity = pd.to_numeric(
                trade_log["equity_after_exit"], errors="coerce"
            ).dropna()
            if not final_equity.empty:
                total_account_return = float(final_equity.iloc[-1] / starting_capital - 1)

    if total_account_return is None and marked_equity is not None:
        total_account_return = float(marked_equity) / starting_capital - 1

    equity_curve = build_equity_curve(daily_log)

    return {
        "starting_capital": starting_capital,
        "current_marked_equity": json_safe(marked_equity),
        "cash": json_safe(state.get("cash")),
        "closed_trades": closed_trades,
        "win_rate": win_rate,
        "avg_position_return": avg_position_return,
        "total_account_return": total_account_return,
        "current_drawdown": json_safe(state.get("current_drawdown")),
        "max_mark_to_market_drawdown": json_safe(
            state.get("max_mark_to_market_drawdown")
        ),
        "equity_curve": equity_curve,
    }


def build_equity_curve(daily_log: pd.DataFrame) -> list[dict[str, Any]]:
    if daily_log.empty or "market_date" not in daily_log.columns:
        return []

    equity_column = (
        "paper_marked_equity"
        if "paper_marked_equity" in daily_log.columns
        else "paper_realized_equity"
    )
    if equity_column not in daily_log.columns:
        return []

    curve = daily_log[["market_date", equity_column]].copy()
    curve[equity_column] = pd.to_numeric(curve[equity_column], errors="coerce")
    curve = curve.dropna(subset=[equity_column])
    curve = curve.drop_duplicates(subset=["market_date"], keep="last")
    curve = curve.rename(columns={equity_column: "equity"})
    return records_safe(curve)


def get_frozen_historical_summary() -> dict[str, Any]:
    summary = read_csv(HISTORICAL_SUMMARY_FILE, keep_default_na=False)
    if summary.empty:
        return {}

    config = FAST_STRATEGY_CONFIG
    mask = (
        (summary["z_window"] == config.z_window)
        & (summary["z_threshold"] == config.z_threshold)
        & (summary["hold_days"] == config.hold_days)
        & (summary["stop_level"] == "None")
    )
    row = summary[mask]
    if row.empty:
        return {}

    return records_safe(row.head(1))[0]


def get_walk_forward_summary() -> dict[str, Any]:
    walk_forward = read_csv(WALK_FORWARD_OVERALL_FILE)
    if walk_forward.empty:
        return {}
    return records_safe(walk_forward.head(1))[0]


def get_return_path() -> list[dict[str, Any]]:
    path = read_csv(RETURN_PATH_FILE)
    if path.empty:
        return []
    return records_safe(path)


def get_historical_trades() -> pd.DataFrame:
    trades = read_csv(HISTORICAL_TRADES_FILE, keep_default_na=False)
    if trades.empty:
        return trades

    config = FAST_STRATEGY_CONFIG
    trades = trades[
        (trades["z_window"] == config.z_window)
        & (trades["z_threshold"] == config.z_threshold)
        & (trades["hold_days"] == config.hold_days)
        & (trades["stop_level"] == "None")
    ].copy()

    for column in ("signal_date", "entry_date", "exit_date"):
        if column in trades.columns:
            trades[column] = pd.to_datetime(trades[column], errors="coerce")

    return trades


def get_soxl_price_history(limit: int = 750) -> pd.DataFrame:
    prices = read_csv(SOXL_FILE)
    if prices.empty:
        return prices

    prices = prices.copy()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices = prices.dropna(subset=["Date", "Close"]).sort_values("Date")
    prices = prices.tail(limit)
    prices = prices.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return prices[["date", "open", "high", "low", "close", "volume"]]


def get_paper_soxl_price_history() -> pd.DataFrame:
    daily_log = normalize_daily_log(read_csv(DAILY_LOG_FILE))
    columns = ["date", "open", "high", "low", "close", "volume"]
    if daily_log.empty or "market_date" not in daily_log.columns:
        return pd.DataFrame(columns=columns)
    if "soxl_close" not in daily_log.columns:
        return pd.DataFrame(columns=columns)

    close = pd.to_numeric(daily_log["soxl_close"], errors="coerce")

    def numeric_column(column: str, fallback: pd.Series | None = None) -> pd.Series:
        if column in daily_log.columns:
            return pd.to_numeric(daily_log[column], errors="coerce")
        if fallback is not None:
            return fallback
        return pd.Series([None] * len(daily_log), index=daily_log.index, dtype="float64")

    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(daily_log["market_date"], errors="coerce"),
            "open": numeric_column("soxl_open", close),
            "high": numeric_column("soxl_high", close),
            "low": numeric_column("soxl_low", close),
            "close": close,
            "volume": numeric_column("soxl_volume"),
        }
    )
    prices = prices.dropna(subset=["date", "close"]).sort_values("date")
    return prices[columns]


def merge_soxl_price_history(
    local_prices: pd.DataFrame,
    paper_prices: pd.DataFrame,
    limit: int,
) -> pd.DataFrame:
    columns = ["date", "open", "high", "low", "close", "volume"]
    frames = [frame for frame in (local_prices, paper_prices) if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=columns)

    prices = pd.concat(frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["date", "close"]).sort_values("date")
    prices = prices.drop_duplicates(subset=["date"], keep="last")
    return prices.tail(limit)[columns]


def marker_price(
    prices_by_date: pd.DataFrame,
    date_value: Any,
    fallback: Any = None,
) -> float | None:
    date = pd.to_datetime(date_value, errors="coerce")
    if pd.isna(date):
        return json_safe(fallback)

    normalized_date = date.normalize()
    if normalized_date in prices_by_date.index:
        return json_safe(prices_by_date.loc[normalized_date, "close"])

    return json_safe(fallback)


def build_trade_markers(
    prices: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    if prices.empty or trades.empty:
        return {"signals": [], "entries": [], "exits": []}

    start_date = prices["date"].min()
    end_date = prices["date"].max()
    visible_trades = trades[
        (trades["signal_date"] >= start_date)
        & (trades["signal_date"] <= end_date)
    ].copy()

    prices_by_date = prices.set_index(prices["date"].dt.normalize())
    signals = []
    entries = []
    exits = []

    for _, trade in visible_trades.iterrows():
        signal_date = trade.get("signal_date")
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        position_return = json_safe(trade.get("position_return"))

        signals.append(
            {
                "date": json_safe(signal_date),
                "close": marker_price(prices_by_date, signal_date),
                "type": "signal",
                "signal_z": json_safe(trade.get("signal_z")),
                "entry_date": json_safe(entry_date),
                "exit_date": json_safe(exit_date),
                "position_return": position_return,
            }
        )
        entries.append(
            {
                "date": json_safe(entry_date),
                "close": marker_price(prices_by_date, entry_date, trade.get("entry_price")),
                "type": "entry",
                "signal_date": json_safe(signal_date),
                "exit_date": json_safe(exit_date),
                "position_return": position_return,
            }
        )
        exits.append(
            {
                "date": json_safe(exit_date),
                "close": marker_price(prices_by_date, exit_date, trade.get("exit_price")),
                "type": "exit",
                "signal_date": json_safe(signal_date),
                "entry_date": json_safe(entry_date),
                "position_return": position_return,
            }
        )

    return {"signals": signals, "entries": entries, "exits": exits}


def get_market_history_payload(limit: int = 750) -> dict[str, Any]:
    local_prices = get_soxl_price_history(limit=limit)
    paper_prices = get_paper_soxl_price_history()
    prices = merge_soxl_price_history(local_prices, paper_prices, limit)
    trades = get_historical_trades()
    markers = build_trade_markers(prices, trades)

    latest = latest_record(prices.rename(columns={"date": "market_date"}))
    if latest and "market_date" in latest:
        latest["date"] = latest.pop("market_date")

    return {
        "symbol": FAST_STRATEGY_CONFIG.symbol,
        "price_source": "local adjusted daily OHLCV plus paper Yahoo daily rows",
        "latest": latest,
        "prices": records_safe(prices),
        "markers": markers,
    }


def historical_signal_frequency(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty or "signal_date" not in trades.columns:
        return {"count": 0, "by_year": {}, "avg_per_year": 0.0}

    signal_dates = pd.to_datetime(trades["signal_date"], errors="coerce").dropna()
    if signal_dates.empty:
        return {"count": 0, "by_year": {}, "avg_per_year": 0.0}

    by_year = signal_dates.dt.year.value_counts().sort_index().to_dict()
    return {
        "count": int(len(signal_dates)),
        "by_year": {str(year): int(count) for year, count in by_year.items()},
        "avg_per_year": float(len(signal_dates) / len(by_year)) if by_year else 0.0,
    }


def paper_signals(daily_log: pd.DataFrame) -> list[dict[str, Any]]:
    if daily_log.empty or "buy_signal" not in daily_log.columns:
        return []

    signals = daily_log[daily_log["buy_signal"].map(bool)].copy()
    columns = [
        column
        for column in (
            "market_date",
            "soxl_close",
            "soxl_z_score",
            "qqq_close",
            "qqq_ma50",
            "qqq_above_ma50",
            "episode_start",
            "buy_signal",
            "next_action",
            "reason",
        )
        if column in signals.columns
    ]
    return records_safe(signals[columns])


def file_summary(path: Path, date_column: str = "Date") -> dict[str, Any]:
    exists = path.exists()
    if not exists:
        return {"exists": False, "rows": 0, "latest_date": None}

    frame = read_csv(path)
    latest_date = None
    if date_column in frame.columns:
        dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
        if not dates.empty:
            latest_date = dates.max().date().isoformat()
    elif "market_date" in frame.columns:
        dates = pd.to_datetime(frame["market_date"], errors="coerce").dropna()
        if not dates.empty:
            latest_date = dates.max().date().isoformat()

    return {
        "exists": True,
        "rows": int(len(frame)),
        "latest_date": latest_date,
    }


def intraday_file_summary(path: Path) -> dict[str, Any]:
    exists = path.exists()
    if not exists:
        return {"exists": False, "rows": 0, "latest_timestamp": None}

    frame = read_csv(path)
    latest_timestamp = None
    if "timestamp" in frame.columns:
        timestamps = pd.to_datetime(frame["timestamp"], errors="coerce").dropna()
        if not timestamps.empty:
            latest_timestamp = timestamps.max().isoformat()

    return {
        "exists": True,
        "rows": int(len(frame)),
        "latest_timestamp": latest_timestamp,
    }


def json_file_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "keys": 0}

    payload = read_json(path, default={})
    return {
        "exists": True,
        "keys": int(len(payload)),
        "last_processed_market_date": payload.get("last_processed_market_date"),
    }


def duplicate_market_dates(daily_log: pd.DataFrame) -> list[dict[str, Any]]:
    if daily_log.empty or "market_date" not in daily_log.columns:
        return []

    counts = daily_log["market_date"].value_counts()
    duplicates = counts[counts > 1]
    return [
        {"market_date": str(market_date), "rows": int(rows)}
        for market_date, rows in duplicates.items()
    ]


def load_runtime_data() -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    state = read_json(STATE_FILE, default={})
    daily_log = normalize_daily_log(read_csv(DAILY_LOG_FILE))
    trade_log = read_csv(TRADE_LOG_FILE)
    return state, daily_log, trade_log


def overnight_rebound_paper_payload() -> dict[str, Any]:
    state = read_json(OVERNIGHT_REBOUND_PAPER_STATE_FILE, default={})
    paper_log = read_csv(OVERNIGHT_REBOUND_PAPER_LOG_FILE)
    trade_log = read_csv(OVERNIGHT_REBOUND_TRADE_LOG_FILE)
    starting_equity = 10_000.0
    marked_equity = state.get("marked_equity", state.get("paper_equity"))
    marked_equity = float(marked_equity) if marked_equity is not None else None
    returns = (
        pd.to_numeric(trade_log["position_return"], errors="coerce").dropna()
        if "position_return" in trade_log.columns
        else pd.Series(dtype="float64")
    )
    provenance = (
        paper_log["provenance"].astype(str)
        if "provenance" in paper_log.columns
        else pd.Series(dtype="object")
    )
    return {
        "mode": "live_paper_with_simulated_backfill",
        "disclosure": (
            "Rows marked historical_backfill are reconstructed simulations, not "
            "trades observed by the live monitor."
        ),
        "state": state,
        "summary": {
            "strategy_version": state.get("strategy_version"),
            "starting_equity": starting_equity,
            "paper_equity": state.get("paper_equity"),
            "marked_equity": marked_equity,
            "total_return": (
                marked_equity / starting_equity - 1
                if marked_equity is not None
                else None
            ),
            "closed_trades": int(len(trade_log)),
            "win_rate": float((returns > 0).mean()) if not returns.empty else None,
            "in_position": bool(state.get("in_position")),
            "backfilled_events": int(provenance.eq("historical_backfill").sum()),
            "forward_events": int(provenance.eq("forward_live").sum()),
        },
        "decisions": intraday_records(paper_log.tail(20)),
        "trades": intraday_records(trade_log.tail(20)),
        "files": {
            "state": json_file_summary(OVERNIGHT_REBOUND_PAPER_STATE_FILE),
            "decisions": file_summary(
                OVERNIGHT_REBOUND_PAPER_LOG_FILE,
                date_column="market_date",
            ),
            "trades": file_summary(
                OVERNIGHT_REBOUND_TRADE_LOG_FILE,
                date_column="exit_market_date",
            ),
        },
    }


def get_intraday_payload(limit: int = 120) -> dict[str, Any]:
    bars = read_csv(INTRADAY_BARS_FILE)
    snapshots = read_csv(INTRADAY_SNAPSHOTS_FILE)
    thirty_minute_bars = read_csv(INTRADAY_30M_FILE)
    challenger_live_bars = read_csv(INTRADAY_30M_CHALLENGER_FILE)
    backtest_bars = read_csv(INTRADAY_30M_BACKTEST_BARS_FILE)
    backtest_summary = read_csv(INTRADAY_30M_BACKTEST_SUMMARY_FILE)
    backtest_trades = read_csv(INTRADAY_30M_BACKTEST_TRADES_FILE)
    backtest_equity = read_csv(INTRADAY_30M_BACKTEST_EQUITY_FILE)
    parameter_comparison = read_csv(INTRADAY_30M_PARAMETER_COMPARISON_FILE)
    validation = read_csv(INTRADAY_30M_VALIDATION_FILE)
    robustness = read_csv(INTRADAY_30M_ROBUSTNESS_FILE)
    daily_shock_context = read_csv(INTRADAY_DAILY_SHOCK_CONTEXT_FILE)
    daily_shock_latest = read_csv(INTRADAY_DAILY_SHOCK_LATEST_FILE)
    challenger_summary = read_csv(INTRADAY_30M_CHALLENGER_SUMMARY_FILE)
    challenger_trades = read_csv(INTRADAY_30M_CHALLENGER_TRADES_FILE)
    challenger_equity = read_csv(INTRADAY_30M_CHALLENGER_EQUITY_FILE)
    challenger_validation = read_csv(INTRADAY_30M_CHALLENGER_VALIDATION_FILE)
    thirty_minute_signals = pd.DataFrame()
    if not thirty_minute_bars.empty and "shadow_signal" in thirty_minute_bars.columns:
        thirty_minute_signals = thirty_minute_bars[
            thirty_minute_bars["shadow_signal"].map(normalize_bool).eq(True)
        ].copy()
    challenger_live_signals = pd.DataFrame()
    if not challenger_live_bars.empty and "shadow_signal" in challenger_live_bars.columns:
        challenger_live_signals = challenger_live_bars[
            challenger_live_bars["shadow_signal"].map(normalize_bool).eq(True)
        ].copy()
    latest = latest_intraday_record(snapshots)

    return {
        "mode": "local_intraday_monitor",
        "bar_file": str(INTRADAY_BARS_FILE),
        "snapshot_file": str(INTRADAY_SNAPSHOTS_FILE),
        "latest": latest,
        "bars": intraday_records(bars.tail(limit)),
        "snapshots": intraday_records(snapshots.tail(20)),
        "overnight_rebound_paper": overnight_rebound_paper_payload(),
        "thirty_minute": {
            "mode": "shadow_fast_30m",
            "bar_file": str(INTRADAY_30M_FILE),
            "latest": latest_intraday_record(thirty_minute_bars),
            "latest_signal": latest_intraday_record(thirty_minute_signals),
            "signal_count": int(len(thirty_minute_signals)),
            "bars": intraday_records(thirty_minute_bars.tail(limit)),
            "signals": intraday_records(thirty_minute_signals.tail(20)),
            "file": intraday_file_summary(INTRADAY_30M_FILE),
            "adaptive_challenger": {
                "mode": "shadow_research_only",
                "latest": latest_intraday_record(challenger_live_bars),
                "latest_signal": latest_intraday_record(challenger_live_signals),
                "signal_count": int(len(challenger_live_signals)),
                "bars": intraday_records(challenger_live_bars.tail(limit)),
                "signals": intraday_records(challenger_live_signals.tail(20)),
                "file": intraday_file_summary(INTRADAY_30M_CHALLENGER_FILE),
            },
            "backtest": {
                "summary": latest_intraday_record(backtest_summary),
                "best": latest_intraday_record(parameter_comparison.head(1)),
                "validated": latest_intraday_record(validation.head(1)),
                "recent_trades": intraday_records(backtest_trades.tail(20)),
                "equity_curve": intraday_records(backtest_equity.tail(limit)),
                "bars": intraday_records(backtest_bars.tail(limit)),
                "top_parameters": intraday_records(parameter_comparison.head(5)),
                "validation": intraday_records(validation.head(10)),
                "robustness": intraday_records(robustness),
                "daily_shock_context": intraday_records(daily_shock_context),
                "daily_shock_latest": latest_intraday_record(daily_shock_latest),
                "challenger": {
                    "mode": "research_only",
                    "summary": latest_intraday_record(challenger_summary),
                    "validation": latest_intraday_record(challenger_validation),
                    "recent_trades": intraday_records(challenger_trades.tail(20)),
                    "equity_curve": intraday_records(challenger_equity.tail(limit)),
                },
                "files": {
                    "bars": intraday_file_summary(INTRADAY_30M_BACKTEST_BARS_FILE),
                    "summary": file_summary(
                        INTRADAY_30M_BACKTEST_SUMMARY_FILE,
                        date_column="period_end",
                    ),
                    "trades": file_summary(
                        INTRADAY_30M_BACKTEST_TRADES_FILE,
                        date_column="exit_timestamp",
                    ),
                    "equity": intraday_file_summary(INTRADAY_30M_BACKTEST_EQUITY_FILE),
                    "parameters": file_summary(
                        INTRADAY_30M_PARAMETER_COMPARISON_FILE,
                        date_column="period_end",
                    ),
                    "validation": file_summary(
                        INTRADAY_30M_VALIDATION_FILE,
                        date_column="test_end",
                    ),
                    "robustness": file_summary(
                        INTRADAY_30M_ROBUSTNESS_FILE,
                        date_column="period_end",
                    ),
                    "daily_shock_context": file_summary(
                        INTRADAY_DAILY_SHOCK_CONTEXT_FILE,
                    ),
                    "challenger_summary": file_summary(
                        INTRADAY_30M_CHALLENGER_SUMMARY_FILE,
                        date_column="period_end",
                    ),
                    "challenger_trades": file_summary(
                        INTRADAY_30M_CHALLENGER_TRADES_FILE,
                        date_column="exit_timestamp",
                    ),
                    "challenger_validation": file_summary(
                        INTRADAY_30M_CHALLENGER_VALIDATION_FILE,
                        date_column="test_end",
                    ),
                },
            },
        },
        "files": {
            "bars": intraday_file_summary(INTRADAY_BARS_FILE),
            "snapshots": intraday_file_summary(INTRADAY_SNAPSHOTS_FILE),
            "thirty_minute": intraday_file_summary(INTRADAY_30M_FILE),
            "thirty_minute_backtest": file_summary(
                INTRADAY_30M_BACKTEST_SUMMARY_FILE,
                date_column="period_end",
            ),
            "thirty_minute_backtest_bars": intraday_file_summary(
                INTRADAY_30M_BACKTEST_BARS_FILE
            ),
            "thirty_minute_validation": file_summary(
                INTRADAY_30M_VALIDATION_FILE,
                date_column="test_end",
            ),
        },
    }


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "SOXL Paper Bot API",
        "docs": "/docs",
        "dashboard": "/api/dashboard",
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    state, daily_log, trade_log = load_runtime_data()
    return {
        "ok": True,
        "strategy_version": state.get(
            "strategy_version", FAST_STRATEGY_CONFIG.strategy_version
        ),
        "files": {
            "state": json_file_summary(STATE_FILE),
            "daily_log": file_summary(DAILY_LOG_FILE, date_column="market_date"),
            "trade_log": file_summary(TRADE_LOG_FILE, date_column="exit_date"),
            "soxl": file_summary(SOXL_FILE),
            "qqq": file_summary(QQQ_FILE),
            "intraday_bars": intraday_file_summary(INTRADAY_BARS_FILE),
            "intraday_snapshots": intraday_file_summary(INTRADAY_SNAPSHOTS_FILE),
            "intraday_30m": intraday_file_summary(INTRADAY_30M_FILE),
            "intraday_30m_backtest_bars": intraday_file_summary(
                INTRADAY_30M_BACKTEST_BARS_FILE
            ),
            "intraday_30m_backtest": file_summary(
                INTRADAY_30M_BACKTEST_SUMMARY_FILE,
                date_column="period_end",
            ),
            "intraday_30m_backtest_trades": file_summary(
                INTRADAY_30M_BACKTEST_TRADES_FILE,
                date_column="exit_timestamp",
            ),
            "intraday_30m_validation": file_summary(
                INTRADAY_30M_VALIDATION_FILE,
                date_column="test_end",
            ),
        },
        "duplicate_market_dates": duplicate_market_dates(daily_log),
        "closed_trades": int(len(trade_log)),
    }


@app.get("/api/state")
def state() -> dict[str, Any]:
    current_state, _, _ = load_runtime_data()
    return {
        "strategy_version": current_state.get(
            "strategy_version", FAST_STRATEGY_CONFIG.strategy_version
        ),
        "state": {key: json_safe(value) for key, value in current_state.items()},
    }


@app.get("/api/daily-log")
def daily_log(limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    _, log, _ = load_runtime_data()
    rows = log.tail(limit).copy()
    return {
        "count": int(len(log)),
        "latest": latest_record(log),
        "rows": records_safe(rows),
    }


@app.get("/api/trades")
def trades(limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    _, _, trade_log = load_runtime_data()
    rows = trade_log.tail(limit).copy()
    return {
        "count": int(len(trade_log)),
        "rows": records_safe(rows),
    }


@app.get("/api/signals")
def signals(limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    _, daily_log, _ = load_runtime_data()
    historical = get_historical_trades()
    historical_rows = historical.tail(limit).copy()
    historical_columns = [
        column
        for column in (
            "signal_date",
            "entry_date",
            "exit_date",
            "signal_z",
            "position_return",
            "mae",
            "mfe",
        )
        if column in historical_rows.columns
    ]
    return {
        "paper_signals": paper_signals(daily_log),
        "historical_signals": records_safe(historical_rows[historical_columns]),
        "historical_frequency": historical_signal_frequency(historical),
    }


@app.get("/api/market-history")
def market_history(limit: int = Query(750, ge=50, le=5000)) -> dict[str, Any]:
    return get_market_history_payload(limit=limit)


@app.get("/api/intraday")
def intraday(limit: int = Query(120, ge=1, le=1000)) -> dict[str, Any]:
    return get_intraday_payload(limit=limit)


@app.get("/api/overnight-paper")
def overnight_paper() -> dict[str, Any]:
    return overnight_rebound_paper_payload()


@app.get("/api/historical-summary")
def historical_summary() -> dict[str, Any]:
    historical_trades = get_historical_trades()
    return {
        "frozen_strategy": {
            "symbol": FAST_STRATEGY_CONFIG.symbol,
            "z_window": FAST_STRATEGY_CONFIG.z_window,
            "z_threshold": FAST_STRATEGY_CONFIG.z_threshold,
            "qqq_ma_window": FAST_STRATEGY_CONFIG.qqq_ma_window,
            "hold_days": FAST_STRATEGY_CONFIG.hold_days,
            "position_fraction": FAST_STRATEGY_CONFIG.position_fraction,
            "slippage": FAST_STRATEGY_CONFIG.slippage,
            "has_fixed_stop": False,
        },
        "historical_summary": get_frozen_historical_summary(),
        "walk_forward_summary": get_walk_forward_summary(),
        "return_path": get_return_path(),
        "signal_frequency": historical_signal_frequency(historical_trades),
    }


@app.get("/api/performance")
def performance() -> dict[str, Any]:
    state, daily_log, trade_log = load_runtime_data()
    return calculate_paper_performance(state, daily_log, trade_log)


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    state, daily_log, trade_log = load_runtime_data()
    historical_trades = get_historical_trades()
    return {
        "state": {key: json_safe(value) for key, value in state.items()},
        "latest_daily_log": latest_record(daily_log),
        "performance": calculate_paper_performance(state, daily_log, trade_log),
        "recent_daily_log": records_safe(daily_log.tail(20)),
        "recent_trades": records_safe(trade_log.tail(20)),
        "paper_signals": paper_signals(daily_log),
        "historical": {
            "summary": get_frozen_historical_summary(),
            "walk_forward": get_walk_forward_summary(),
            "return_path": get_return_path(),
            "signal_frequency": historical_signal_frequency(historical_trades),
        },
        "intraday": get_intraday_payload(),
        "market": get_market_history_payload(),
        "data_health": health(),
    }
