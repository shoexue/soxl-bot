from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategy.config import FAST_STRATEGY_CONFIG, FastStrategyConfig
from strategy.signals import build_signal_frame, read_ohlcv_csv, signal_dates


DATA_DIR = ROOT / "data"
REFERENCE_TRADES_FILE = DATA_DIR / "execution_downside_trades.csv"


def generate_fixed_hold_trades(
    frame: pd.DataFrame,
    config: FastStrategyConfig,
) -> pd.DataFrame:
    trades = []

    for signal_date in signal_dates(frame):
        signal_pos = frame.index.get_loc(signal_date)
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + config.hold_days - 1

        if exit_pos >= len(frame):
            continue

        entry_date = frame.index[entry_pos]
        exit_date = frame.index[exit_pos]
        raw_entry = frame.iloc[entry_pos]["Open"]
        raw_exit = frame.iloc[exit_pos]["Close"]
        entry_price = raw_entry * (1 + config.slippage)
        exit_price = raw_exit * (1 - config.slippage)

        trades.append(
            {
                "signal_date": signal_date,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "signal_z": frame.loc[signal_date, "soxl_z_score"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "position_return": exit_price / entry_price - 1,
                "entry_timing_ok": entry_pos == signal_pos + 1,
                "exit_timing_ok": (exit_pos - entry_pos + 1) == config.hold_days,
            }
        )

    return pd.DataFrame(trades)


def load_reference_trades(config: FastStrategyConfig) -> pd.DataFrame:
    if not REFERENCE_TRADES_FILE.exists():
        return pd.DataFrame()

    reference = pd.read_csv(REFERENCE_TRADES_FILE, keep_default_na=False)
    reference = reference[
        (reference["z_window"] == config.z_window)
        & (reference["z_threshold"] == config.z_threshold)
        & (reference["hold_days"] == config.hold_days)
        & (reference["stop_level"] == "None")
    ].copy()

    for column in ("signal_date", "entry_date", "exit_date"):
        reference[column] = pd.to_datetime(reference[column]).dt.normalize()

    return reference


def compare_to_reference(
    production: pd.DataFrame,
    reference: pd.DataFrame,
) -> tuple[bool, list[str]]:
    issues = []

    if reference.empty:
        return True, ["Reference trade file was not available; skipped parity check."]

    shared = production.merge(
        reference,
        on=["signal_date", "entry_date", "exit_date"],
        how="outer",
        suffixes=("_production", "_reference"),
        indicator=True,
    )

    missing_from_production = shared[shared["_merge"] == "right_only"]
    missing_from_reference = shared[shared["_merge"] == "left_only"]

    if not missing_from_production.empty:
        issues.append(
            f"{len(missing_from_production)} reference trades were missing from production."
        )
    if not missing_from_reference.empty:
        issues.append(
            f"{len(missing_from_reference)} production trades were missing from reference."
        )

    matched = shared[shared["_merge"] == "both"].copy()
    if not matched.empty:
        for column in ("entry_price", "exit_price", "position_return"):
            left = matched[f"{column}_production"].astype(float)
            right = matched[f"{column}_reference"].astype(float)
            if not np.allclose(left, right, rtol=1e-6, atol=1e-4):
                issues.append(f"{column} did not match the reference backtest.")

    if issues:
        return False, issues

    return True, [
        "Signal dates, entry dates, exit dates, and trade math matched the "
        "reference backtest within adjusted-price tolerance."
    ]


def signal_frequency(signal_index: pd.DatetimeIndex, frame: pd.DataFrame) -> dict[str, object]:
    if signal_index.empty:
        return {
            "count": 0,
            "avg_per_year": 0.0,
            "median_trading_day_gap": None,
            "by_year": {},
        }

    signal_positions = pd.Series(
        [frame.index.get_loc(date) for date in signal_index],
        index=signal_index,
    )
    gaps = signal_positions.diff().dropna()
    years = signal_index.year
    by_year = pd.Series(1, index=years).groupby(level=0).sum().to_dict()
    year_count = max(1, len(set(years)))

    return {
        "count": int(len(signal_index)),
        "avg_per_year": len(signal_index) / year_count,
        "median_trading_day_gap": float(gaps.median()) if not gaps.empty else None,
        "by_year": by_year,
    }


def main() -> int:
    config = FAST_STRATEGY_CONFIG

    soxl = read_ohlcv_csv(DATA_DIR / "SOXL.csv", config.symbol)
    qqq = read_ohlcv_csv(DATA_DIR / "QQQ.csv", config.regime_symbol)
    frame = build_signal_frame(soxl, qqq, config=config)

    modern = frame[frame.index >= pd.Timestamp("2021-01-01")].copy()
    first_valid_regime = modern.index[modern["qqq_ma50"].notna()][0]
    validation_frame = modern[modern.index >= first_valid_regime].copy()

    production_trades = generate_fixed_hold_trades(validation_frame, config)
    production_signals = signal_dates(validation_frame)

    reference = load_reference_trades(config)
    if not reference.empty:
        reference = reference[reference["signal_date"] >= first_valid_regime].copy()

    parity_ok, parity_messages = compare_to_reference(production_trades, reference)
    frequency = signal_frequency(production_signals, validation_frame)

    entry_violations = 0
    exit_violations = 0
    if not production_trades.empty:
        entry_violations = int((~production_trades["entry_timing_ok"]).sum())
        exit_violations = int((~production_trades["exit_timing_ok"]).sum())

    latest = frame.iloc[-1]
    raw_data_warning = []
    if soxl.index.max() != qqq.index.max():
        raw_data_warning.append(
            f"SOXL latest date {soxl.index.max().date()} differs from "
            f"QQQ latest date {qqq.index.max().date()}."
        )
    if pd.isna(latest["qqq_ma50"]):
        raw_data_warning.append("Latest QQQ MA50 is unavailable.")
    if pd.isna(latest["soxl_z_score"]):
        raw_data_warning.append("Latest SOXL 5-day z-score is unavailable.")

    print()
    print("=" * 80)
    print("PAPER BOT VALIDATION")
    print("=" * 80)
    print()
    print(f"Strategy: {config.strategy_version}")
    print(f"Local data through: {frame.index.max().date()}")
    print(f"Validation starts: {first_valid_regime.date()}")
    print()
    print("Backtest parity:")
    print(f"  OK: {parity_ok}")
    for message in parity_messages:
        print(f"  - {message}")
    print()
    print("Signal frequency:")
    print(f"  Signals checked: {frequency['count']}")
    print(f"  Average per active year: {frequency['avg_per_year']:.2f}")
    if frequency["median_trading_day_gap"] is not None:
        print(f"  Median trading-day gap: {frequency['median_trading_day_gap']:.1f}")
    print(f"  By year: {frequency['by_year']}")
    print()
    print("Entry/exit timing:")
    print(f"  Completed trades checked: {len(production_trades)}")
    print(f"  Entry timing violations: {entry_violations}")
    print(f"  Exit timing violations: {exit_violations}")
    print()
    print("Latest signal snapshot:")
    print(f"  SOXL close: {latest['Close']:.2f}")
    print(f"  SOXL 5D z-score: {latest['soxl_z_score']:.3f}")
    print(f"  QQQ above MA50: {bool(latest['qqq_above_ma50'])}")
    print(f"  Episode start: {bool(latest['episode_start'])}")
    print(f"  Buy signal: {bool(latest['buy_signal'])}")
    print()
    print("Real-time data quirks:")
    if raw_data_warning:
        for warning in raw_data_warning:
            print(f"  - {warning}")
    else:
        print("  No local SOXL/QQQ alignment issue detected on the latest bar.")
    print()
    print(
        "Note: local QQQ data starts in 2021, so this validation begins only after "
        "the local QQQ 50-day MA is available. The original research used earlier "
        "downloaded data for warm-up."
    )

    if not parity_ok or entry_violations or exit_violations:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
