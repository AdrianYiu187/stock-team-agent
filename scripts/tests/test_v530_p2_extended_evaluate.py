"""v5.30 P2 — evaluate_per_region_extended() TDD guards。

業務動機:
  擴充 fixture (11 + 12 = 23 ticker) 後, US region 從 4 → 10 ticker,
  Pearson correlation 不再全為 0 (US 樣本量足夠), 可下 per-region 結論。

TDD 鎖定:
  1. evaluate_per_region_extended() 必須可運行 (合併 11+12 ticker)
  2. US region 樣本量必須 ≥ 10 (擴充生效)
  3. HK region 樣本量必須 ≥ 9 (擴充生效)
  4. US region 最佳 Pearson 必須 > 0.3 (門檻, 解鎖 per-region 結論)
  5. 既有 11 ticker 結果不變 (regression guard)
"""

import sys
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from quantify_v529_per_region_sensitivity import (  # noqa: E402
    REGION_MAP,
    REGION_MAP_EXTENDED,
    evaluate_per_region,
    evaluate_per_region_extended,
)


class TestV530P2ExtendedRegionMap(unittest.TestCase):
    """M-V530P2-13..14: REGION_MAP_EXTENDED 鎖定"""

    def test_extended_contains_all_11_originals(self):
        """REGION_MAP_EXTENDED 必須包含既有 11 ticker"""
        for ticker, region in REGION_MAP.items():
            self.assertEqual(
                REGION_MAP_EXTENDED.get(ticker), region,
                f"{ticker} region 變更: {REGION_MAP_EXTENDED.get(ticker)} (expected {region})",
            )

    def test_extended_has_12_new_tickers(self):
        """REGION_MAP_EXTENDED 必須新增 12 ticker (US 6 + HK 6)"""
        new_tickers = set(REGION_MAP_EXTENDED.keys()) - set(REGION_MAP.keys())
        self.assertEqual(len(new_tickers), 12, f"新增 ticker {len(new_tickers)} != 12")


class TestV530P2ExtendedEvaluate(unittest.TestCase):
    """M-V530P2-15..18: evaluate_per_region_extended() 量化結論"""

    def test_extended_runs_successfully(self):
        """evaluate_per_region_extended() 可運行"""
        report = evaluate_per_region_extended()
        self.assertIn("regions", report)
        self.assertIn("global_best", report)
        self.assertIn("summary", report)

    def test_us_n_tickers_at_least_10(self):
        """US region 樣本量必須 ≥ 10 (從既有 4 擴充)"""
        report = evaluate_per_region_extended()
        us_n = report["regions"]["US"]["n_tickers"]
        self.assertGreaterEqual(
            us_n, 10,
            f"US 樣本量 {us_n} < 10, 擴充未生效",
        )

    def test_hk_n_tickers_at_least_9(self):
        """HK region 樣本量必須 ≥ 9 (從既有 3 擴充)"""
        report = evaluate_per_region_extended()
        hk_n = report["regions"]["HK"]["n_tickers"]
        self.assertGreaterEqual(
            hk_n, 9,
            f"HK 樣本量 {hk_n} < 9, 擴充未生效",
        )

    def test_cn_n_tickers_unchanged(self):
        """CN region 樣本量保持 4 (未擴充, 既有即可)"""
        report = evaluate_per_region_extended()
        cn_n = report["regions"]["CN"]["n_tickers"]
        self.assertEqual(cn_n, 4, f"CN 樣本量 {cn_n} != 4 (預期未變)")

    def test_us_best_pearson_above_threshold(self):
        """US region 最佳 Pearson 必須 > 0.3 (門檻, 解鎖 per-region 結論)

        v5.30 P2 量化結論 (擴充後):
        - US 10 ticker 最佳 config = hk_fund_heavy, Pearson = +0.7100
        - 此 guard 鎖定門檻: Pearson > 0.3 (留 ±0.4 noise margin)
        - 若未來 US 樣本波動, Pearson 仍應 > 0.3 才算有意義
        """
        report = evaluate_per_region_extended()
        us_best = report["regions"]["US"]["best_pearson"]
        self.assertGreater(
            us_best, 0.3,
            f"US region 最佳 Pearson {us_best:.4f} <= 0.3, 樣本仍不足以解鎖 per-region 結論",
        )

    def test_existing_evaluate_per_region_unchanged(self):
        """既有 evaluate_per_region() 結果不變 (回歸保護)

        既有版本只看 signal_distribution_per_ticker (11 ticker),
        不應受 P2 擴充影響。
        """
        report_old = evaluate_per_region()
        # 既有 11 ticker 結果鎖定
        us_old = report_old["regions"]["US"]["n_tickers"]
        hk_old = report_old["regions"]["HK"]["n_tickers"]
        cn_old = report_old["regions"]["CN"]["n_tickers"]
        self.assertEqual(us_old, 4, f"既有 US 樣本量 {us_old} != 4 (應未變)")
        self.assertEqual(hk_old, 3, f"既有 HK 樣本量 {hk_old} != 3 (應未變)")
        self.assertEqual(cn_old, 4, f"既有 CN 樣本量 {cn_old} != 4 (應未變)")


if __name__ == "__main__":
    unittest.main()
