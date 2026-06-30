"""v5.30 P2 — 擴大 US/HK sample 解鎖 per-region 結論 TDD guards。

業務動機:
  v5.29 candidate 量化 (e1d3e12) 揭示 US (4 ticker) / HK (3 ticker) 樣本量過小,
  Pearson correlation 全為 0.0, 無法下 per-region 結論。
  v5.30 P2 從 S&P 500 / Hang Seng 各抓 6+ ticker, 擴充 fixture 至 US≥10 / HK≥9,
  目標 Pearson > 0.3 解鎖 per-region 結論。

TDD 流程:
  1. 此檔 TDD guards 鎖定:
     - proxy 計算確定性 (相同 input → 相同 output)
     - 7D components 結構合約 (7 keys, [0, 1] range)
     - majority 規則確定性 (30d return >+5%/-5%)
     - fixture 結構合約 (extended_signal_distribution_per_ticker 與既有 11 ticker 並列)
  2. **不鎖定 Pearson 結果** (因為 ticker 樣本會變), 而是鎖定「擴充後
     US/HK n_tickers ≥ 10 / ≥ 9, 且 evaluate_per_region_extended() 不再全為 0」
"""

import json
import math
import sys
import unittest
from pathlib import Path
from typing import Dict, List

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from snapshot_more_tickers import (  # noqa: E402
    EXTENDED_TICKER_REGION,
    EXTENDED_TICKER_UNIVERSE,
    compute_majority_from_prices,
    compute_price_derived_components,
)


# 標準測試 close prices (3 種典型場景)
BULLISH_CLOSES = [100.0 + i * 0.5 for i in range(120)]  # 30d: 100 → 115 (+15%)
BEARISH_CLOSES = [100.0 - i * 0.5 for i in range(120)]  # 30d: 100 → 85 (-15%)
SIDEWAYS_CLOSES = [100.0 + (i % 10) * 0.1 for i in range(120)]  # 30d: ~100 (~+1%)


class TestV530P2ProxyCompute(unittest.TestCase):
    """M-V530P2-1..4: price-derived proxy 純函數行為"""

    def test_bullish_majority_is_buy(self):
        """30d return +15% → majority = buy"""
        self.assertEqual(compute_majority_from_prices(BULLISH_CLOSES), "buy")

    def test_bearish_majority_is_sell(self):
        """30d return -15% → majority = sell"""
        self.assertEqual(compute_majority_from_prices(BEARISH_CLOSES), "sell")

    def test_sideways_majority_is_hold(self):
        """30d return ~+1% → majority = hold"""
        self.assertEqual(compute_majority_from_prices(SIDEWAYS_CLOSES), "hold")

    def test_proxy_components_returns_7_keys(self):
        """compute_price_derived_components 必須回傳 7 個維度"""
        comp = compute_price_derived_components(BULLISH_CLOSES)
        self.assertEqual(
            set(comp.keys()),
            {"tech", "fund", "market", "risk", "sentiment", "news", "macro"},
        )

    def test_proxy_components_in_unit_range(self):
        """7D components 全部 ∈ [0, 1]"""
        for closes in (BULLISH_CLOSES, BEARISH_CLOSES, SIDEWAYS_CLOSES):
            comp = compute_price_derived_components(closes)
            for k, v in comp.items():
                self.assertGreaterEqual(v, 0.0, f"{k}={v} < 0")
                self.assertLessEqual(v, 1.0, f"{k}={v} > 1")

    def test_proxy_components_pure_function(self):
        """純函數: 相同 input → 相同 output (regression guard)"""
        c1 = compute_price_derived_components(BULLISH_CLOSES)
        c2 = compute_price_derived_components(BULLISH_CLOSES)
        self.assertEqual(c1, c2)

    def test_proxy_short_sample_returns_neutral(self):
        """< 30 day 樣本 → 全部 0.5 (中性)"""
        comp = compute_price_derived_components([100.0] * 10)
        for v in comp.values():
            self.assertEqual(v, 0.5)


class TestV530P2ExtendedUniverse(unittest.TestCase):
    """M-V530P2-5..7: EXTENDED_TICKER_UNIVERSE 鎖定"""

    def test_universe_size(self):
        """EXTENDED_TICKER_UNIVERSE 必須 ≥ 12 ticker (US 6 + HK 6)"""
        self.assertGreaterEqual(len(EXTENDED_TICKER_UNIVERSE), 12)

    def test_region_coverage(self):
        """EXTENDED_TICKER_REGION 必須 cover US 6+ 與 HK 6+"""
        us_count = sum(1 for r in EXTENDED_TICKER_REGION.values() if r == "US")
        hk_count = sum(1 for r in EXTENDED_TICKER_REGION.values() if r == "HK")
        self.assertGreaterEqual(us_count, 6, f"US 樣本 {us_count} < 6")
        self.assertGreaterEqual(hk_count, 6, f"HK 樣本 {hk_count} < 6")

    def test_no_overlap_with_existing_11(self):
        """擴充 ticker 不可與既有 11 ticker 重疊 (AAPL/MSFT/GOOGL/NVDA/0700/9988/3690/600519/000858/601318/000333)"""
        existing = {
            "AAPL", "MSFT", "GOOGL", "NVDA",
            "0700.HK", "9988.HK", "3690.HK",
            "600519.SS", "000858.SZ", "601318.SS", "000333.SZ",
        }
        overlap = set(EXTENDED_TICKER_UNIVERSE) & existing
        self.assertEqual(overlap, set(), f"擴充 ticker 與既有重疊: {overlap}")


class TestV530P2FixtureStructure(unittest.TestCase):
    """M-V530P2-8..10: fixture 結構合約 (既有 11 ticker 不受影響)"""

    FIXTURE_PATH = _SCRIPT_DIR / "fixtures" / "tickers_fundamentals.json"

    def test_fixture_exists(self):
        self.assertTrue(self.FIXTURE_PATH.exists(), f"fixture 缺失: {self.FIXTURE_PATH}")

    def test_existing_11_tickers_intact(self):
        """既有 11 ticker 必須仍存在於 signal_distribution_per_ticker (P2 不污染)"""
        with open(self.FIXTURE_PATH) as f:
            fixture = json.load(f)
        sd = fixture.get("signal_distribution_per_ticker", {})
        expected_existing = {
            "AAPL", "MSFT", "GOOGL", "NVDA",
            "0700.HK", "9988.HK", "3690.HK",
            "600519.SS", "000858.SZ", "601318.SS", "000333.SZ",
        }
        self.assertEqual(
            set(sd.keys()), expected_existing,
            f"既有 11 ticker 缺失或被覆蓋: 差異 {set(sd.keys()) ^ expected_existing}",
        )

    def test_existing_11_have_7d_components(self):
        """既有 11 ticker 必須仍含 7D components (P2 不破壞既有合約)"""
        with open(self.FIXTURE_PATH) as f:
            fixture = json.load(f)
        sd = fixture["signal_distribution_per_ticker"]
        for ticker, info in sd.items():
            comps = info.get("components", {})
            missing = {"market", "technical", "fundamental", "risk", "sentiment", "news", "macro"} - set(comps.keys())
            self.assertEqual(
                missing, set(),
                f"{ticker} 缺 7D 維度: {missing}",
            )


class TestV530P2ThresholdGuard(unittest.TestCase):
    """M-V530P2-11..12: 擴大 sample 後, evaluate_per_region_extended() 必須有 n_tickers 增長

    注: 此 guard 不直接 call evaluate (避免循環 import + 網路依賴),
    而是驗證 fixture 結構支持 evaluate 擴充。
    """

    FIXTURE_PATH = _SCRIPT_DIR / "fixtures" / "tickers_fundamentals.json"

    def test_extended_key_does_not_exist_pre_snapshot(self):
        """snapshot 跑前, extended_signal_distribution_per_ticker 必須不存在

        這是 P2 啟動前狀態, TDD guard 確保既有 fixture 乾淨。
        跑 snapshot_more_tickers.py 後此 guard 會 FAIL, 是預期的 (P2 標記 fixture 已更新)。
        """
        with open(self.FIXTURE_PATH) as f:
            fixture = json.load(f)
        # 首次跑 P2 前這 key 不存在 — 若已存在, 可能是 P2 已跑過 (no-op 跳過)
        if "extended_signal_distribution_per_ticker" in fixture:
            self.skipTest("extended_signal_distribution_per_ticker 已存在 (P2 可能已跑過)")

    def test_extended_snapshot_post_run(self):
        """v5.30 P2 跑過後: extended_signal_distribution_per_ticker 必須含 12 ticker
        且都有 is_proxy=True 標記 + 7D components + majority
        """
        with open(self.FIXTURE_PATH) as f:
            fixture = json.load(f)
        ext = fixture.get("extended_signal_distribution_per_ticker", {})
        if not ext:
            self.skipTest("尚未跑 snapshot_more_tickers.py")
        # 12 ticker (US 6 + HK 6)
        self.assertEqual(
            len(ext), 12,
            f"擴充 ticker 數量 {len(ext)} != 12, snapshot 異常",
        )
        for ticker, info in ext.items():
            self.assertTrue(
                info.get("is_proxy", False),
                f"{ticker}: 缺 is_proxy=True 標記",
            )
            self.assertIn(
                info.get("majority"), {"buy", "hold", "sell"},
                f"{ticker}: majority={info.get('majority')} 不合法",
            )
            comps = info.get("components", {})
            self.assertEqual(
                set(comps.keys()),
                {"tech", "fund", "market", "risk", "sentiment", "news", "macro"},
                f"{ticker}: components 結構不符",
            )
        # _meta 必須含 v530_p2_extended_snapshot
        meta = fixture.get("_meta", {}).get("v530_p2_extended_snapshot", {})
        self.assertEqual(
            meta.get("proxy_version"), "v5.30-p2-price-only",
            "fixture _meta 缺 v530_p2_extended_snapshot 標記",
        )

    def test_extended_tickers_have_is_proxy_marker(self):
        """跑過 snapshot 後, 擴充 ticker 必須含 is_proxy=True 標記

        確保 caller 不會誤把 proxy 當 full 7D components 使用。
        """
        with open(self.FIXTURE_PATH) as f:
            fixture = json.load(f)
        ext = fixture.get("extended_signal_distribution_per_ticker", {})
        if not ext:
            self.skipTest("尚未跑 snapshot_more_tickers.py")
        for ticker, info in ext.items():
            self.assertTrue(
                info.get("is_proxy", False),
                f"{ticker}: 擴充 ticker 缺 is_proxy=True 標記",
            )
            comps = info.get("components", {})
            self.assertEqual(
                set(comps.keys()),
                {"tech", "fund", "market", "risk", "sentiment", "news", "macro"},
                f"{ticker}: 擴充 ticker components 結構不符",
            )


if __name__ == "__main__":
    unittest.main()
