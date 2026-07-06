from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from paper.paper_bot import PaperPaths, default_state, process_frame
from strategy.config import FAST_STRATEGY_CONFIG


def make_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=6)
    frame = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            "High": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0],
            "Close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            "Volume": [1_000_000] * 6,
            "soxl_mean_5": [100.0] * 6,
            "soxl_std_5": [1.0] * 6,
            "soxl_z_score": [0.0] * 6,
            "qqq_close": [500.0] * 6,
            "qqq_ma50": [450.0] * 6,
            "qqq_above_ma50": [True] * 6,
            "oversold": [False] * 6,
            "episode_start": [False] * 6,
            "buy_signal": [False] * 6,
        },
        index=dates,
    )
    return frame


class PaperBotTests(unittest.TestCase):
    def test_duplicate_market_date_is_not_logged_twice(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = PaperPaths(
                state_file=Path(tmpdir) / "state.json",
                daily_log_file=Path(tmpdir) / "daily.csv",
                trade_log_file=Path(tmpdir) / "trades.csv",
                local_data_dir=Path(tmpdir),
            )
            state = default_state(FAST_STRATEGY_CONFIG)
            frame = make_frame().iloc[:1]

            first = process_frame(frame, state, paths)
            second = process_frame(frame, state, paths)

            daily_log = pd.read_csv(paths.daily_log_file)
            self.assertTrue(first.processed)
            self.assertFalse(second.processed)
            self.assertEqual(len(daily_log), 1)

    def test_late_run_uses_next_open_and_scheduled_day_four_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = PaperPaths(
                state_file=Path(tmpdir) / "state.json",
                daily_log_file=Path(tmpdir) / "daily.csv",
                trade_log_file=Path(tmpdir) / "trades.csv",
                local_data_dir=Path(tmpdir),
            )
            frame = make_frame()
            state = default_state(FAST_STRATEGY_CONFIG)
            state["pending_entry"] = True
            state["signal_date"] = str(frame.index[0].date())

            result = process_frame(frame, state, paths, dry_run=True)

            self.assertEqual(result.trade_row["entry_date"], str(frame.index[1].date()))
            self.assertEqual(result.trade_row["exit_date"], str(frame.index[4].date()))
            expected_entry = frame.iloc[1]["Open"] * (1 + FAST_STRATEGY_CONFIG.slippage)
            expected_exit = frame.iloc[4]["Close"] * (1 - FAST_STRATEGY_CONFIG.slippage)
            self.assertAlmostEqual(result.trade_row["entry_price"], expected_entry)
            self.assertAlmostEqual(result.trade_row["exit_price"], expected_exit)

    def test_open_position_marks_equity_daily(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = PaperPaths(
                state_file=Path(tmpdir) / "state.json",
                daily_log_file=Path(tmpdir) / "daily.csv",
                trade_log_file=Path(tmpdir) / "trades.csv",
                local_data_dir=Path(tmpdir),
            )
            frame = make_frame().iloc[:3].copy()
            frame.iloc[-1, frame.columns.get_loc("Close")] = 90.0

            state = default_state(FAST_STRATEGY_CONFIG)
            state.update(
                {
                    "in_position": True,
                    "entry_date": str(frame.index[1].date()),
                    "entry_open": 100.0,
                    "entry_price": 100.0,
                    "shares": 50.0,
                    "invested_capital": 5000.0,
                    "cash": 5000.0,
                    "account_equity_before_entry": 10000.0,
                }
            )

            result = process_frame(frame, state, paths, dry_run=True)

            self.assertEqual(result.action, "HOLD")
            self.assertAlmostEqual(result.state["position_market_value"], 4500.0)
            self.assertAlmostEqual(result.state["marked_equity"], 9500.0)
            self.assertLess(result.state["current_drawdown"], 0.0)


if __name__ == "__main__":
    unittest.main()

