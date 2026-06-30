"""v5.27 Step 2 — TDD guards: dashboard FastAPI endpoints。

啟動測試 (無需 uvicorn):
    pytest scripts/tests/test_dashboard_api.py -v
"""

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _TESTS_DIR.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from dashboard_api import app  # noqa: E402


client = TestClient(app)


class TestDashboardHealth(unittest.TestCase):
    """A1-A2: /api/health 健康檢查 + 當前 weights 反映 fund_heavy"""

    def test_health_status_ok(self):
        """A1: GET /api/health → status='ok'"""
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")

    def test_health_records_fund_heavy_weights(self):
        """A2: health.weights 是 fund_heavy (tech:0.20, fund:0.50, market:0.15, risk:0.15)"""
        r = client.get("/api/health")
        data = r.json()
        w = data["weights"]
        self.assertAlmostEqual(w["tech"], 0.20, places=4)
        self.assertAlmostEqual(w["fund"], 0.50, places=4)
        self.assertAlmostEqual(w["market"], 0.15, places=4)
        self.assertAlmostEqual(w["risk"], 0.15, places=4)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)


class TestDashboardConfig(unittest.TestCase):
    """A3-A4: /api/config 配置查詢"""

    def test_config_returns_close_source_default_real(self):
        """A3: close_source_default = 'real' (v5.26 P1 永久化)"""
        r = client.get("/api/config")
        data = r.json()
        self.assertEqual(data["close_source_default"], "real")
        self.assertIn("real", data["available_close_sources"])
        self.assertIn("mock", data["available_close_sources"])

    def test_config_weights_match_fund_heavy(self):
        """A4: config.weights_4d 與 /api/health.weights 一致 (v5.28 用 weights_4d key)"""
        h = client.get("/api/health").json()
        c = client.get("/api/config").json()
        self.assertEqual(h["weights"], c["weights_4d"])


class TestDashboardCrossMarket(unittest.TestCase):
    """A5-A10: /api/cross_market 真實 backtest 端點"""

    def test_cross_market_default_real(self):
        """A5: 預設 close_source='real',回傳 200 + close_source='real' echo"""
        r = client.get("/api/cross_market")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["close_source"], "real")

    def test_cross_market_explicit_real(self):
        """A6: ?close_source=real 明確指定"""
        r = client.get("/api/cross_market?close_source=real")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["close_source"], "real")
        self.assertEqual(data["config"]["close_source"], "real")

    def test_cross_market_explicit_mock(self):
        """A7: ?close_source=mock 切換為 mock GBM"""
        r = client.get("/api/cross_market?close_source=mock")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["close_source"], "mock")
        self.assertEqual(data["config"]["close_source"], "mock")

    def test_cross_market_response_has_top_keys(self):
        """A8: response 包含 config/v5.10/v5.11.3/per_ticker/cap_warnings/improvement"""
        r = client.get("/api/cross_market")
        data = r.json()
        for key in [
            "config", "v5.10", "v5.11.3", "per_ticker",
            "cap_warnings", "improvement_v5.11.3_over_v5.10_pp",
        ]:
            self.assertIn(key, data, f"missing top-level key: {key}")

    def test_cross_market_per_ticker_11_entries(self):
        """A9: per_ticker 字典含 11 ticker (fixture universe)"""
        r = client.get("/api/cross_market")
        data = r.json()
        self.assertEqual(len(data["per_ticker"]), 11)

    def test_cross_market_real_differs_from_mock(self):
        """A10: real 與 mock 在 v5.11.3 改善幅度上必須不同 (Lesson #54 守門)"""
        r_real = client.get("/api/cross_market?close_source=real").json()
        r_mock = client.get("/api/cross_market?close_source=mock").json()
        # Dir Acc Δ 真實 vs mock 必須不同（否則 fixture 未生效）
        real_imp = r_real["improvement_v5.11.3_over_v5.10_pp"]["directional_accuracy"]
        mock_imp = r_mock["improvement_v5.11.3_over_v5.10_pp"]["directional_accuracy"]
        self.assertNotAlmostEqual(
            real_imp, mock_imp, places=2,
            msg=f"real={real_imp} mock={mock_imp} 相同 — Lesson #54 fixture 未生效"
        )


class TestDashboardTickerFilter(unittest.TestCase):
    """A11-A12: ?tickers=... 子集過濾"""

    def test_tickers_filter_3_tickers(self):
        """A11: ?tickers=AAPL,MSFT,GOOGL 只回 3 ticker"""
        r = client.get("/api/cross_market?tickers=AAPL,MSFT,GOOGL")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(set(data["per_ticker"].keys()), {"AAPL", "MSFT", "GOOGL"})

    def test_tickers_filter_with_whitespace(self):
        """A12: ?tickers=' AAPL , MSFT ' 容許 whitespace"""
        r = client.get("/api/cross_market?tickers=%20AAPL%20,%20MSFT%20")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(set(data["per_ticker"].keys()), {"AAPL", "MSFT"})


class TestDashboardErrorHandling(unittest.TestCase):
    """A13: 錯誤處理 — 無效 close_source 應 422"""

    def test_invalid_close_source_rejected(self):
        """A13: ?close_source=invalid → 422 Unprocessable Entity (Pydantic Literal)"""
        r = client.get("/api/cross_market?close_source=invalid")
        self.assertEqual(r.status_code, 422)


class TestDashboard7DEndpoint(unittest.TestCase):
    """v5.28 P2 — /api/cross_market_7d + /api/config weights_7d 鎖定"""

    def test_config_exposes_weights_7d(self):
        """A14: GET /api/config 含 weights_7d = v5.30 預設 cn_macro_heavy
        + weights_7d_fallback = v5.28 預設 full_7d_balanced_0_15"""
        r = client.get("/api/config")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("weights_7d", data)
        w = data["weights_7d"]
        self.assertEqual(set(w.keys()), {"tech", "fund", "market", "risk", "sentiment", "news", "macro"})
        # v5.30 預設 cn_macro_heavy
        self.assertAlmostEqual(w["tech"], 0.10, places=4)
        self.assertAlmostEqual(w["fund"], 0.25, places=4)
        self.assertAlmostEqual(w["macro"], 0.25, places=4)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=4)
        # v5.30 新增 FALLBACK
        self.assertIn("weights_7d_fallback", data)
        wf = data["weights_7d_fallback"]
        self.assertAlmostEqual(wf["tech"], 0.18, places=4)
        self.assertAlmostEqual(wf["fund"], 0.37, places=4)
        self.assertAlmostEqual(sum(wf.values()), 1.0, places=4)
        # 預設與 FALLBACK 必須不同
        self.assertNotEqual(w, wf, "weights_7d == weights_7d_fallback, v5.30 升級無效")

    def test_config_exposes_weights_4d(self):
        """A15: GET /api/config 改用 weights_4d key (v5.27 向後相容 breaking)"""
        r = client.get("/api/config")
        data = r.json()
        self.assertIn("weights_4d", data)
        self.assertNotIn("weights", data, "v5.28 改成 weights_4d 取代 weights key")
        w = data["weights_4d"]
        self.assertAlmostEqual(w["fund"], 0.50, places=4)

    def test_7d_endpoint_returns_all_11_tickers(self):
        """A16: GET /api/cross_market_7d 不帶 ticker filter → 11 個 ticker"""
        r = client.get("/api/cross_market_7d")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["per_ticker"]), 11)

    def test_7d_endpoint_per_ticker_shape(self):
        """A17: per_ticker[AAPL] 必須含 7 維度 + composite_7d + signal + region + advice (v5.30 P3)"""
        r = client.get("/api/cross_market_7d")
        data = r.json()
        aapl = data["per_ticker"]["AAPL"]
        expected_keys = {
            "tech", "fund", "market", "risk",
            "sentiment", "news", "macro",
            "composite_7d", "signal",
            "majority", "buy_ratio", "hold_ratio", "sell_ratio",
            # v5.30 P3 NEW — per-region advice
            "region", "advice",
        }
        self.assertEqual(set(aapl.keys()), expected_keys)
        self.assertIn(aapl["signal"], {"BUY", "HOLD", "SELL"})
        # v5.30 P3 — region 必須 ∈ {US, HK, CN, global}
        self.assertIn(aapl["region"], {"US", "HK", "CN", "global"})
        # advice 是字串且包含 weight config 名稱
        self.assertIsInstance(aapl["advice"], str)
        self.assertGreater(len(aapl["advice"]), 0)

    def test_7d_endpoint_config_block(self):
        """A18: response.config 含 weights_7d + source + version (v5.30 升為 5.30.0)"""
        r = client.get("/api/cross_market_7d")
        data = r.json()
        cfg = data["config"]
        self.assertEqual(cfg["source"], "fixture_signal_distribution_per_ticker")
        self.assertEqual(cfg["version"], "5.30.0")  # v5.30 P1 升級
        self.assertIn("macro", cfg["weights_7d"])

    def test_7d_endpoint_ticker_filter(self):
        """A19: ?tickers=AAPL,MSFT → 只回這 2 個 ticker"""
        r = client.get("/api/cross_market_7d?tickers=AAPL,MSFT")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(set(data["per_ticker"].keys()), {"AAPL", "MSFT"})

    def test_7d_endpoint_invalid_ticker_ignored(self):
        """A20: ?tickers=AAPL,DOES_NOT_EXIST → 忽略無效 ticker (只回 AAPL)"""
        r = client.get("/api/cross_market_7d?tickers=AAPL,DOES_NOT_EXIST")
        data = r.json()
        self.assertEqual(set(data["per_ticker"].keys()), {"AAPL"})

    def test_7d_composite_in_valid_range(self):
        """A21: 所有 ticker 的 composite_7d 必須 ∈ [0.0, 1.0]"""
        r = client.get("/api/cross_market_7d")
        data = r.json()
        for ticker, info in data["per_ticker"].items():
            self.assertGreaterEqual(info["composite_7d"], 0.0, f"{ticker} composite_7d < 0")
            self.assertLessEqual(info["composite_7d"], 1.0, f"{ticker} composite_7d > 1")


if __name__ == "__main__":
    unittest.main()