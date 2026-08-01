from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from intraday.monitor import (
    IntradayConfig,
    IntradayPaths,
    apply_adaptive_thirty_minute_challenger_rules,
    apply_thirty_minute_signal_rules,
    append_snapshot,
    backtest_thirty_minute_strategy,
    backfill_overnight_rebound_paper,
    build_intraday_bars,
    build_snapshot,
    build_thirty_minute_bars,
    evaluate_daily_shock_context,
    evaluate_thirty_minute_robustness,
    save_bars,
    validate_thirty_minute_candidates,
)


def make_intraday_frame(
    close_values: list[float],
    high_values: list[float],
    low_values: list[float],
    open_value: float = 100.0,
) -> pd.DataFrame:
    index = pd.date_range(
        "2026-07-08 09:30",
        periods=len(close_values),
        freq="5min",
        tz="America/New_York",
    )
    return pd.DataFrame(
        {
            "Open": [open_value] * len(close_values),
            "High": high_values,
            "Low": low_values,
            "Close": close_values,
            "Volume": [1_000_000] * len(close_values),
        },
        index=index,
    )


class IntradayMonitorTests(unittest.TestCase):
    def make_thirty_minute_base(
        self,
        opens: list[float],
        closes: list[float],
        from_high: list[float] | None = None,
    ) -> pd.DataFrame:
        index = pd.date_range(
            "2026-07-08 09:30",
            periods=len(closes),
            freq="30min",
            tz="America/New_York",
        )
        session_open = opens[0]
        highs = [max(open_, close) + 0.5 for open_, close in zip(opens, closes)]
        lows = [min(open_, close) - 0.5 for open_, close in zip(opens, closes)]
        running_high = pd.Series(highs).cummax()
        running_low = pd.Series(lows).cummin()
        return pd.DataFrame(
            {
                "timestamp": [timestamp.isoformat() for timestamp in index],
                "market_date": ["2026-07-08"] * len(index),
                "interval": "30min",
                "soxl_open": opens,
                "soxl_high": highs,
                "soxl_low": lows,
                "soxl_close": closes,
                "soxl_volume": [1_000_000] * len(index),
                "soxl_vwap": [session_open + 1.0] * len(index),
                "soxl_return_30m_pct": [
                    close / open_ - 1
                    for open_, close in zip(opens, closes, strict=False)
                ],
                "soxl_vs_vwap_pct": [
                    close / (session_open + 1.0) - 1 for close in closes
                ],
                "soxl_from_open_pct": [
                    close / session_open - 1 for close in closes
                ],
                "soxl_from_high_pct": from_high
                or [
                    close / high - 1
                    for close, high in zip(closes, running_high, strict=False)
                ],
                "soxl_from_low_pct": [
                    close / low - 1
                    for close, low in zip(closes, running_low, strict=False)
                ],
                "soxl_session_range_pct": [
                    high / low - 1
                    for high, low in zip(running_high, running_low, strict=False)
                ],
                "bar_number": list(range(1, len(index) + 1)),
                "qqq_close": [500.0] * len(index),
                "qqq_return_30m_pct": [0.0] * len(index),
                "qqq_from_open_pct": [0.0] * len(index),
                "bars_in_window": [1] * len(index),
            }
        )

    def test_build_intraday_bars_tracks_latest_session_metrics(self) -> None:
        soxl = make_intraday_frame(
            close_values=[100.0, 104.0, 109.0, 110.0],
            high_values=[101.0, 105.0, 111.0, 112.0],
            low_values=[99.0, 98.0, 97.0, 96.0],
        )
        qqq = make_intraday_frame(
            close_values=[500.0, 501.0, 502.0, 503.0],
            high_values=[501.0, 502.0, 503.0, 504.0],
            low_values=[499.0, 500.0, 501.0, 502.0],
            open_value=500.0,
        )

        bars = build_intraday_bars(soxl, qqq)
        latest = bars.iloc[-1]

        self.assertEqual(len(bars), 4)
        self.assertEqual(latest["market_date"], "2026-07-08")
        self.assertEqual(latest["soxl_close"], 110.0)
        self.assertAlmostEqual(latest["soxl_from_open_pct"], 0.10)
        self.assertAlmostEqual(latest["soxl_range_pct"], 112.0 / 96.0 - 1)
        self.assertAlmostEqual(latest["qqq_from_open_pct"], 503.0 / 500.0 - 1)

    def test_build_snapshot_classifies_extreme_intraday_range(self) -> None:
        config = IntradayConfig(extreme_range_pct=0.10)
        soxl = make_intraday_frame(
            close_values=[100.0, 104.0, 109.0, 110.0],
            high_values=[101.0, 105.0, 111.0, 112.0],
            low_values=[99.0, 98.0, 97.0, 96.0],
        )
        qqq = make_intraday_frame(
            close_values=[500.0, 501.0, 502.0, 503.0],
            high_values=[501.0, 502.0, 503.0, 504.0],
            low_values=[499.0, 500.0, 501.0, 502.0],
            open_value=500.0,
        )
        bars = build_intraday_bars(soxl, qqq, config=config)

        snapshot = build_snapshot(
            bars,
            config=config,
            now=datetime(2026, 7, 8, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        )

        self.assertEqual(snapshot["watch_state"], "EXTREME_RANGE")
        self.assertEqual(snapshot["bars_observed"], 4)
        self.assertEqual(snapshot["soxl_last"], 110.0)
        self.assertEqual(snapshot["data_warning"], "")

    def test_intraday_csv_writes_dedupe_by_timestamp(self) -> None:
        soxl = make_intraday_frame(
            close_values=[100.0, 104.0],
            high_values=[101.0, 105.0],
            low_values=[99.0, 98.0],
        )
        qqq = make_intraday_frame(
            close_values=[500.0, 501.0],
            high_values=[501.0, 502.0],
            low_values=[499.0, 500.0],
            open_value=500.0,
        )
        bars = build_intraday_bars(soxl, qqq)
        snapshot = build_snapshot(bars)

        with tempfile.TemporaryDirectory() as tmpdir:
            bars_file = Path(tmpdir) / "bars.csv"
            snapshots_file = Path(tmpdir) / "snapshots.csv"

            save_bars(bars_file, bars)
            save_bars(bars_file, bars)
            append_snapshot(snapshots_file, snapshot)
            append_snapshot(snapshots_file, snapshot)

            saved_bars = pd.read_csv(bars_file)
            saved_snapshots = pd.read_csv(snapshots_file)

            self.assertEqual(len(saved_bars), len(bars))
            self.assertEqual(len(saved_snapshots), 1)

    def test_build_thirty_minute_bars_flags_shadow_long_watch(self) -> None:
        soxl_closes = (
            [100.0] * 6
            + [101.0] * 6
            + [102.0] * 6
            + [101.0] * 6
            + [95.0] * 6
        )
        qqq_closes = [500.0] * len(soxl_closes)
        soxl = make_intraday_frame(
            close_values=soxl_closes,
            high_values=[value + 1.0 for value in soxl_closes],
            low_values=[value - 1.0 for value in soxl_closes],
            open_value=94.0,
        )
        qqq = make_intraday_frame(
            close_values=qqq_closes,
            high_values=[501.0] * len(qqq_closes),
            low_values=[499.0] * len(qqq_closes),
            open_value=500.0,
        )
        config = IntradayConfig(
            signal_z_threshold=-1.25,
            entry_style="episode_start",
        )

        bars = build_intraday_bars(soxl, qqq, config=config)
        thirty_minute_bars = build_thirty_minute_bars(bars, config=config)
        latest = thirty_minute_bars.iloc[-1]

        self.assertEqual(len(thirty_minute_bars), 5)
        self.assertEqual(latest["interval"], "30min")
        self.assertTrue(latest["oversold_30m"])
        self.assertTrue(latest["episode_start_30m"])
        self.assertTrue(latest["regime_ok_30m"])
        self.assertTrue(latest["shadow_signal"])
        self.assertEqual(latest["shadow_action"], "SHADOW_LONG_WATCH")

    def test_thirty_minute_bounce_confirmation_waits_for_reversal(self) -> None:
        soxl_closes = (
            [100.0] * 6
            + [101.0] * 6
            + [102.0] * 6
            + [101.0] * 6
            + [95.0] * 6
            + [97.0] * 6
        )
        qqq_closes = [500.0] * len(soxl_closes)
        soxl = make_intraday_frame(
            close_values=soxl_closes,
            high_values=[value + 1.0 for value in soxl_closes],
            low_values=[value - 1.0 for value in soxl_closes],
            open_value=94.0,
        )
        qqq = make_intraday_frame(
            close_values=qqq_closes,
            high_values=[501.0] * len(qqq_closes),
            low_values=[499.0] * len(qqq_closes),
            open_value=500.0,
        )
        config = IntradayConfig(
            signal_z_threshold=-1.25,
            entry_style="bounce_confirmation",
            bounce_wait_bars=2,
            require_vwap_reclaim=False,
        )

        bars = build_intraday_bars(soxl, qqq, config=config)
        thirty_minute_bars = build_thirty_minute_bars(bars, config=config)
        oversold_start = thirty_minute_bars.iloc[-2]
        bounce = thirty_minute_bars.iloc[-1]

        self.assertTrue(oversold_start["episode_start_30m"])
        self.assertFalse(oversold_start["shadow_signal"])
        self.assertEqual(oversold_start["shadow_action"], "OVERSOLD_WATCH")
        self.assertTrue(bounce["bounce_confirmed_30m"])
        self.assertTrue(bounce["shadow_signal"])
        self.assertEqual(bounce["bars_since_episode_start_30m"], 1)

    def test_backtest_thirty_minute_strategy_enters_and_exits_signal(self) -> None:
        soxl_closes = (
            [100.0] * 6
            + [101.0] * 6
            + [102.0] * 6
            + [101.0] * 6
            + [95.0] * 6
            + [97.0] * 6
            + [98.0] * 6
        )
        qqq_closes = [500.0] * len(soxl_closes)
        soxl = make_intraday_frame(
            close_values=soxl_closes,
            high_values=[value + 1.0 for value in soxl_closes],
            low_values=[value - 1.0 for value in soxl_closes],
            open_value=94.0,
        )
        qqq = make_intraday_frame(
            close_values=qqq_closes,
            high_values=[501.0] * len(qqq_closes),
            low_values=[499.0] * len(qqq_closes),
            open_value=500.0,
        )
        config = IntradayConfig(
            signal_z_threshold=-1.25,
            hold_bars=1,
            entry_style="bounce_confirmation",
            bounce_wait_bars=2,
            require_vwap_reclaim=False,
        )

        bars = build_intraday_bars(soxl, qqq, config=config)
        thirty_minute_bars = build_thirty_minute_bars(bars, config=config)
        summary, trades, equity = backtest_thirty_minute_strategy(
            thirty_minute_bars,
            config=config,
        )

        self.assertEqual(summary["trades"], 1)
        self.assertGreater(summary["total_return"], 0)
        self.assertEqual(len(equity), len(thirty_minute_bars))
        self.assertEqual(trades.iloc[0]["exit_reason"], "fixed_hold_1_30m_bars")
        self.assertEqual(trades.iloc[0]["bars_held"], 1)

    def test_next_bar_execution_waits_for_the_following_open(self) -> None:
        base = self.make_thirty_minute_base(
            opens=[100.0, 100.0, 101.0, 102.0, 101.0, 95.0, 97.0, 98.0],
            closes=[100.0, 101.0, 102.0, 101.0, 95.0, 97.0, 98.0, 99.0],
        )
        config = IntradayConfig(hold_bars=1)
        signals = apply_thirty_minute_signal_rules(base, config=config)
        signal_timestamp = signals.loc[
            signals["shadow_signal"].map(bool),
            "timestamp",
        ].iloc[0]

        summary, trades, _ = backtest_thirty_minute_strategy(
            signals,
            config=config,
            entry_execution="next_bar_open",
        )

        self.assertEqual(summary["entry_execution"], "next_bar_open")
        self.assertEqual(summary["trades"], 1)
        self.assertGreater(trades.iloc[0]["entry_timestamp"], signal_timestamp)
        self.assertAlmostEqual(
            trades.iloc[0]["entry_price"],
            97.0 * (1 + config.slippage),
        )

    def test_robustness_grid_includes_causal_cost_stress(self) -> None:
        base = self.make_thirty_minute_base(
            opens=[100.0, 100.0, 101.0, 102.0, 101.0, 95.0, 97.0, 98.0],
            closes=[100.0, 101.0, 102.0, 101.0, 95.0, 97.0, 98.0, 99.0],
        )

        robustness = evaluate_thirty_minute_robustness(
            base,
            slippage_values=(0.001, 0.003),
            recent_sessions=1,
        )

        self.assertEqual(
            set(robustness["entry_execution"]),
            {"signal_close", "next_bar_open"},
        )
        self.assertEqual(set(robustness["slippage"]), {0.001, 0.003})
        self.assertEqual(
            set(robustness["strategy_version"]),
            {
                "fast_30m_validated_v4",
                "adaptive_30m_research_v1",
                "fast_30m_stress_guard_v5_research",
            },
        )

    def test_session_entry_cap_blocks_repeated_falling_knife_attempts(self) -> None:
        base = self.make_thirty_minute_base(
            opens=[100.0] * 8,
            closes=[100.0, 101.0, 100.0, 101.0, 100.0, 101.0, 100.0, 101.0],
        )
        signals = apply_thirty_minute_signal_rules(base)
        signals["shadow_signal"] = False
        signals.loc[[0, 3, 6], "shadow_signal"] = True
        config = IntradayConfig(hold_bars=1)

        uncapped, _, _ = backtest_thirty_minute_strategy(
            signals,
            config=config,
        )
        capped, _, _ = backtest_thirty_minute_strategy(
            signals,
            config=config,
            max_entries_per_session=1,
        )

        self.assertGreater(uncapped["trades"], capped["trades"])
        self.assertEqual(capped["trades"], 1)

    def test_daily_shock_context_summarizes_modern_forward_returns(self) -> None:
        dates = pd.bdate_range("2025-01-02", periods=40)
        closes = [100.0] * 40
        closes[10:16] = [95.0, 90.0, 82.0, 74.0, 68.0, 65.0]
        closes[16:22] = [70.0, 73.0, 76.0, 78.0, 80.0, 82.0]
        daily = pd.DataFrame({"Date": dates, "Close": closes})

        context, latest = evaluate_daily_shock_context(
            daily,
            thresholds=(-0.30,),
            forward_horizons=(5,),
        )

        self.assertEqual(latest["market_date"], dates[-1].date().isoformat())
        self.assertEqual(len(context), 1)
        self.assertGreaterEqual(context.iloc[0]["events"], 1)
        self.assertIn("median_forward_return", context.columns)

    def test_adaptive_challenger_adds_causal_trend_pullback_signal(self) -> None:
        base = self.make_thirty_minute_base(
            opens=[100.0, 103.0, 101.0],
            closes=[103.0, 101.0, 103.0],
        )

        signals = apply_adaptive_thirty_minute_challenger_rules(base)
        latest = signals.iloc[-1]

        self.assertTrue(latest["shadow_signal"])
        self.assertEqual(latest["strategy_version"], "adaptive_30m_research_v1")
        self.assertEqual(latest["shadow_action"], "TREND_PULLBACK_LONG_WATCH")

    def test_adaptive_challenger_blocks_shallow_reversion_bounce(self) -> None:
        base = self.make_thirty_minute_base(
            opens=[100.0, 100.0, 100.0, 100.0, 100.0, 95.0],
            closes=[100.0, 101.0, 102.0, 101.0, 95.0, 97.0],
            from_high=[-0.005] * 6,
        )
        baseline = apply_thirty_minute_signal_rules(base)
        challenger = apply_adaptive_thirty_minute_challenger_rules(base)

        self.assertTrue(baseline.iloc[-1]["shadow_signal"])
        self.assertFalse(challenger.iloc[-1]["shadow_signal"])
        self.assertEqual(
            challenger.iloc[-1]["shadow_action"],
            "SHALLOW_REVERSION_BLOCKED",
        )

    def test_overnight_backfill_labels_simulation_and_exits_next_open(self) -> None:
        frames = []
        dates = ["2026-07-08", "2026-07-09", "2026-07-10", "2026-07-13", "2026-07-14"]
        for market_date in dates:
            index = pd.date_range(
                f"{market_date} 09:30",
                periods=13,
                freq="30min",
                tz="America/New_York",
            )
            session_open = 110.0 if market_date == "2026-07-14" else 100.0
            closes = [session_open] * 13
            if market_date == "2026-07-13":
                closes[11] = 90.0
                closes[12] = 89.0
            frames.append(
                pd.DataFrame(
                    {
                        "timestamp": [timestamp.isoformat() for timestamp in index],
                        "market_date": market_date,
                        "bar_number": list(range(1, 14)),
                        "soxl_open": [session_open] * 13,
                        "soxl_close": closes,
                        "soxl_from_open_pct": [
                            close / session_open - 1 for close in closes
                        ],
                    }
                )
            )
        bars = pd.concat(frames, ignore_index=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = IntradayPaths(
                overnight_state_file=root / "state.json",
                overnight_paper_log_file=root / "paper.csv",
                overnight_trade_log_file=root / "trades.csv",
            )
            result = backfill_overnight_rebound_paper(
                bars,
                sessions=5,
                paths=paths,
            )

            decisions = pd.read_csv(paths.overnight_paper_log_file)
            trades = pd.read_csv(paths.overnight_trade_log_file)
            self.assertEqual(len(result["trades"]), 1)
            self.assertGreater(result["state"]["paper_equity"], 10_000.0)
            self.assertTrue(decisions["is_backfill"].map(bool).all())
            self.assertTrue(trades["is_backfill"].map(bool).all())
            self.assertEqual(set(decisions["provenance"]), {"historical_backfill"})
            self.assertEqual(trades.iloc[0]["exit_market_date"], "2026-07-14")

    def test_validate_thirty_minute_candidates_returns_ranked_rows(self) -> None:
        frames = []
        for day_offset in range(6):
            index = pd.date_range(
                pd.Timestamp("2026-07-01 09:30", tz="America/New_York")
                + pd.Timedelta(days=day_offset),
                periods=7,
                freq="30min",
            )
            closes = [100.0, 101.0, 102.0, 101.0, 95.0, 98.0, 100.0]
            frames.append(
                pd.DataFrame(
                    {
                        "timestamp": [timestamp.isoformat() for timestamp in index],
                        "market_date": [str(timestamp.date()) for timestamp in index],
                        "interval": "30min",
                        "strategy_version": "test",
                        "soxl_open": [94.0] * len(index),
                        "soxl_high": [value + 1.0 for value in closes],
                        "soxl_low": [value - 1.0 for value in closes],
                        "soxl_close": closes,
                        "soxl_volume": [1_000_000] * len(index),
                        "soxl_vwap": [96.0] * len(index),
                        "soxl_return_30m_pct": [
                            close / 94.0 - 1 for close in closes
                        ],
                        "soxl_z_5bar": [None] * len(index),
                        "soxl_vs_vwap_pct": [close / 96.0 - 1 for close in closes],
                        "soxl_from_open_pct": [close / 94.0 - 1 for close in closes],
                        "soxl_from_high_pct": [0.0] * len(index),
                        "soxl_from_low_pct": [0.0] * len(index),
                        "soxl_session_range_pct": [0.05] * len(index),
                        "bar_number": list(range(1, len(index) + 1)),
                        "qqq_close": [500.0] * len(index),
                        "qqq_return_30m_pct": [0.0] * len(index),
                        "qqq_from_open_pct": [0.01] * len(index),
                        "bars_in_window": [1] * len(index),
                        "oversold_30m": [False] * len(index),
                        "episode_start_30m": [False] * len(index),
                        "bars_since_episode_start_30m": [None] * len(index),
                        "bounce_confirmed_30m": [False] * len(index),
                        "regime_ok_30m": [True] * len(index),
                        "entry_window_ok_30m": [True] * len(index),
                        "shadow_signal": [False] * len(index),
                        "shadow_action": ["WAIT"] * len(index),
                        "shadow_reason": [""] * len(index),
                    }
                )
            )
        bars = pd.concat(frames, ignore_index=True)
        config = IntradayConfig(
            signal_z_threshold=-1.25,
            entry_style="bounce_confirmation",
            require_vwap_reclaim=False,
            hold_bars=1,
        )

        validation = validate_thirty_minute_candidates(
            bars,
            config=config,
            train_fraction=0.5,
            candidates=[config],
        )

        self.assertFalse(validation.empty)
        self.assertIn("validation_score", validation.columns)
        self.assertIn("test_return", validation.columns)


if __name__ == "__main__":
    unittest.main()
