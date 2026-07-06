from __future__ import annotations

from pathlib import Path

import pandas as pd

from strategy.config import FAST_STRATEGY_CONFIG, FastStrategyConfig


REQUIRED_OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


class MarketDataError(RuntimeError):
    """Raised when market data is missing or malformed."""


def normalize_ohlcv(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    df = data.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")

    missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in df.columns]
    if missing:
        raise MarketDataError(
            f"{ticker} data is missing required columns: {', '.join(missing)}"
        )

    df = df.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    for column in REQUIRED_OHLCV_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    if df.empty:
        raise MarketDataError(f"{ticker} data has no usable OHLC rows.")

    return df


def read_ohlcv_csv(path: Path, ticker: str) -> pd.DataFrame:
    if not path.exists():
        raise MarketDataError(f"Missing local {ticker} data file: {path}")

    return normalize_ohlcv(pd.read_csv(path), ticker=ticker)


def build_signal_frame(
    soxl: pd.DataFrame,
    qqq: pd.DataFrame,
    config: FastStrategyConfig = FAST_STRATEGY_CONFIG,
) -> pd.DataFrame:
    soxl_data = normalize_ohlcv(soxl, ticker=config.symbol)
    qqq_data = normalize_ohlcv(qqq, ticker=config.regime_symbol)

    frame = soxl_data.copy()

    qqq_ma = qqq_data["Close"].rolling(config.qqq_ma_window).mean()
    qqq_features = pd.DataFrame(
        {
            "qqq_close": qqq_data["Close"],
            "qqq_ma50": qqq_ma,
            "qqq_above_ma50": qqq_data["Close"] > qqq_ma,
        }
    )

    frame["soxl_mean_5"] = frame["Close"].rolling(config.z_window).mean()
    frame["soxl_std_5"] = frame["Close"].rolling(config.z_window).std()
    frame["soxl_z_score"] = (
        (frame["Close"] - frame["soxl_mean_5"]) / frame["soxl_std_5"]
    )

    aligned_qqq = qqq_features.reindex(frame.index)
    frame["qqq_close"] = aligned_qqq["qqq_close"]
    frame["qqq_ma50"] = aligned_qqq["qqq_ma50"]
    frame["qqq_above_ma50"] = aligned_qqq["qqq_above_ma50"].eq(True)

    frame["oversold"] = (frame["soxl_z_score"] < config.z_threshold).fillna(False)
    frame["episode_start"] = (
        frame["oversold"]
        & ~frame["oversold"].shift(1, fill_value=False)
    )
    frame["buy_signal"] = frame["episode_start"] & frame["qqq_above_ma50"]

    return frame


def signal_dates(frame: pd.DataFrame) -> pd.DatetimeIndex:
    return frame.index[frame["buy_signal"]]
