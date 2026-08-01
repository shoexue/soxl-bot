from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.server import app
from reports.export_dashboard_json import build_static_dashboard_payload


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_dashboard_endpoint(self) -> None:
        response = self.client.get("/api/dashboard")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("state", payload)
        self.assertIn("performance", payload)
        self.assertIn("historical", payload)
        self.assertIn("intraday", payload)
        self.assertIn("data_health", payload)

    def test_historical_summary_endpoint(self) -> None:
        response = self.client.get("/api/historical-summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["frozen_strategy"]["z_window"], 5)
        self.assertEqual(payload["frozen_strategy"]["hold_days"], 4)
        self.assertFalse(payload["frozen_strategy"]["has_fixed_stop"])
        self.assertGreater(payload["signal_frequency"]["count"], 0)

    def test_daily_log_endpoint(self) -> None:
        response = self.client.get("/api/daily-log?limit=1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("count", payload)
        self.assertIn("rows", payload)
        self.assertLessEqual(len(payload["rows"]), 1)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("files", payload)

    def test_market_history_endpoint(self) -> None:
        response = self.client.get("/api/market-history?limit=120")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "SOXL")
        self.assertIn("latest", payload)
        self.assertIn("prices", payload)
        self.assertIn("markers", payload)
        self.assertLessEqual(len(payload["prices"]), 120)
        self.assertIn("signals", payload["markers"])

    def test_intraday_endpoint(self) -> None:
        response = self.client.get("/api/intraday")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "local_intraday_monitor")
        self.assertIn("latest", payload)
        self.assertIn("bars", payload)
        self.assertIn("snapshots", payload)
        self.assertIn("thirty_minute", payload)
        self.assertIn("overnight_rebound_paper", payload)
        self.assertIn("summary", payload["overnight_rebound_paper"])
        self.assertIn("disclosure", payload["overnight_rebound_paper"])
        self.assertIn("files", payload)
        self.assertEqual(payload["thirty_minute"]["mode"], "shadow_fast_30m")
        self.assertIn("backtest", payload["thirty_minute"])
        self.assertIn("adaptive_challenger", payload["thirty_minute"])
        self.assertEqual(
            payload["thirty_minute"]["adaptive_challenger"]["mode"],
            "shadow_research_only",
        )
        self.assertIn("summary", payload["thirty_minute"]["backtest"])
        self.assertIn("top_parameters", payload["thirty_minute"]["backtest"])
        self.assertIn("validated", payload["thirty_minute"]["backtest"])
        self.assertIn("validation", payload["thirty_minute"]["backtest"])
        self.assertIn("robustness", payload["thirty_minute"]["backtest"])
        self.assertIn("daily_shock_context", payload["thirty_minute"]["backtest"])
        self.assertIn("daily_shock_latest", payload["thirty_minute"]["backtest"])
        self.assertIn("challenger", payload["thirty_minute"]["backtest"])
        self.assertEqual(
            payload["thirty_minute"]["backtest"]["challenger"]["mode"],
            "research_only",
        )

    def test_overnight_paper_endpoint_discloses_backfill(self) -> None:
        response = self.client.get("/api/overnight-paper")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "live_paper_with_simulated_backfill")
        self.assertIn("reconstructed simulations", payload["disclosure"])
        self.assertIn("summary", payload)
        self.assertIn("decisions", payload)
        self.assertIn("trades", payload)

    def test_static_dashboard_export_payload(self) -> None:
        payload = build_static_dashboard_payload()

        self.assertIn("state", payload)
        self.assertIn("performance", payload)
        self.assertIn("intraday", payload)
        self.assertIn("static_export", payload)
        self.assertIn("generated_at_utc", payload["static_export"])
        self.assertIn("deploy_workflow", payload["static_export"])
        self.assertIn("paper_bot_workflow", payload["static_export"])


if __name__ == "__main__":
    unittest.main()
