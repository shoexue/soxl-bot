from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.server import app


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


if __name__ == "__main__":
    unittest.main()
