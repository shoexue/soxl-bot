from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from strategy.config import FAST_STRATEGY_CONFIG


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PAPER_DIR = DATA_DIR / "paper"

STATE_FILE = PAPER_DIR / "paper_state.json"
DAILY_LOG_FILE = PAPER_DIR / "paper_daily_log.csv"
TRADE_LOG_FILE = PAPER_DIR / "paper_trade_log.csv"

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
    prices = get_soxl_price_history(limit=limit)
    trades = get_historical_trades()
    markers = build_trade_markers(prices, trades)

    latest = latest_record(prices.rename(columns={"date": "market_date"}))
    if latest and "market_date" in latest:
        latest["date"] = latest.pop("market_date")

    return {
        "symbol": FAST_STRATEGY_CONFIG.symbol,
        "price_source": "local adjusted daily OHLCV",
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
        "market": get_market_history_payload(),
        "data_health": health(),
    }
