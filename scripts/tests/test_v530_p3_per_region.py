"""v5.30 P3 — dashboard per-region weight 預覽 TDD guards。

業務動機:
  v5.30 P2 量化揭示 per-region 最佳 config 不同:
  - US: hk_fund_heavy (Pearson +0.7100)
  - HK/CN: global_4d_fund_heavy (反轉/樣本限制)
  - Global: cn_macro_heavy (v5.30 預設)

  v5.30 P3 在 dashboard 加 per-region toggle:
  - API: /api/cross_market_7d?region=US|HK|CN|global 自動套用該區最佳 config
  - UI: 每 ticker card 加 region badge (e.g. "此 ticker 屬 US，建議用 us_fund_heavy")

TDD 鎖定:
  1. /api/config 暴露 per_region_weights_7d (4 regions)
  2. /api/cross_market_7d?region=US 套用 us_fund_heavy weights
  3. /api/cross_market_7d?region=CN 套用 4d_fund_heavy weights
  4. 每個 ticker 都有 region + advice badge
  5. 無效 region → 422
  6. 不傳 region → 預設 global (向後相容)
"""

import sys
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from fastapi.testclient import TestClient  # noqa: E402

from dashboard_api import app  # noqa: E402

client = TestClient(app)


class TestV530P3PerRegionConfig(unittest.TestCase):
    """M-V530P3-1..2: /api/config 暴露 per_region_weights_7d"""

    def test_config_exposes_per_region_weights(self):
        """/api/config 必須含 per_region_weights_7d (4 regions)"""
        r = client.get("/api/config")
        data = r.json()
        self.assertIn("per_region_weights_7d", data)
        regions = data["per_region_weights_7d"]
        self.assertEqual(set(regions.keys()), {"US", "HK", "CN", "global"})

    def test_config_exposes_ticker_region_map(self):
        """/api/config 必須含 ticker_region_map (11 ticker)"""
        r = client.get("/api/config")
        data = r.json()
        self.assertIn("ticker_region_map", data)
        rm = data["ticker_region_map"]
        # 11 ticker 必須有 region 標記
        self.assertEqual(len(rm), 11, f"ticker_region_map 應有 11 ticker, 實際 {len(rm)}")
        # 驗證關鍵 ticker region
        self.assertEqual(rm["AAPL"], "US")
        self.assertEqual(rm["0700.HK"], "HK")
        self.assertEqual(rm["600519.SS"], "CN")

    def test_config_exposes_available_regions(self):
        """/api/config 必須含 available_regions"""
        r = client.get("/api/config")
        data = r.json()
        self.assertIn("available_regions", data)
        self.assertEqual(
            set(data["available_regions"]),
            {"US", "HK", "CN", "global"},
        )


class TestV530P3RegionQuery(unittest.TestCase):
    """M-V530P3-3..6: /api/cross_market_7d?region= 套用 per-region weights"""

    def test_default_region_is_global(self):
        """不傳 region → 預設 global (向後相容 v5.28 behavior)"""
        r = client.get("/api/cross_market_7d")
        data = r.json()
        self.assertEqual(data["config"]["region"], "global")
        # global weights = v5.30 預設 cn_macro_heavy
        self.assertAlmostEqual(
            data["config"]["weights_7d"]["macro"], 0.25, places=4,
            msg="global region 預設 macro 應 = 0.25 (cn_macro_heavy)",
        )

    def test_region_us_applies_us_fund_heavy(self):
        """?region=US 套用 us_fund_heavy weights (tech 0.15 / fund 0.45)"""
        r = client.get("/api/cross_market_7d?region=US")
        data = r.json()
        self.assertEqual(data["config"]["region"], "US")
        w = data["config"]["weights_7d"]
        self.assertAlmostEqual(w["fund"], 0.45, places=4)
        self.assertAlmostEqual(w["tech"], 0.15, places=4)

    def test_region_cn_applies_4d_fund_heavy(self):
        """?region=CN 套用 4d_fund_heavy (tech 0.20 / fund 0.50, sentiment/news/macro = 0)"""
        r = client.get("/api/cross_market_7d?region=CN")
        data = r.json()
        self.assertEqual(data["config"]["region"], "CN")
        w = data["config"]["weights_7d"]
        self.assertAlmostEqual(w["fund"], 0.50, places=4)
        self.assertAlmostEqual(w["sentiment"], 0.0, places=4)
        self.assertAlmostEqual(w["macro"], 0.0, places=4)

    def test_per_ticker_has_region_and_advice(self):
        """每個 ticker 必須含 region + advice badge"""
        r = client.get("/api/cross_market_7d?region=US")
        data = r.json()
        aapl = data["per_ticker"]["AAPL"]
        self.assertIn("region", aapl)
        self.assertEqual(aapl["region"], "US")
        self.assertIn("advice", aapl)
        # US region 建議 = us_fund_heavy
        self.assertIn("us_fund_heavy", aapl["advice"])

    def test_invalid_region_rejected(self):
        """無效 region 值 → 422 (Pydantic Literal)"""
        r = client.get("/api/cross_market_7d?region=invalid")
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
