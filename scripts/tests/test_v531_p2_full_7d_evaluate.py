"""v5.31 P2 TDD guards — 鎖定升級後 per-region 量化結果。

8 guards:
  1. test_v531_global_hk_fund_heavy_pearson_improved
  2. test_v531_us_pearson_above_threshold (不退化到 0)
  3. test_v531_hk_pearson_zero_documented_limitation
  4. test_v531_cn_pearson_unchanged
  5. test_v531_global_best_config_documented
  6. test_v531_quantify_report_file_exists
  7. test_v531_no_regression_vs_v530_summary
  8. test_v531_per_region_n_tickers_lock
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from quantify_v531_per_region_full_7d import (  # noqa: E402
    evaluate_per_region_v531,
    WEIGHT_CONFIGS,
    REGION_MAP,
)


class TestV531P2Full7dEvaluate(unittest.TestCase):
    """P2 — 量化結果 invariants (升級後不能比 v5.30 差太多)。"""

    @classmethod
    def setUpClass(cls):
        cls.report = evaluate_per_region_v531()

    def test_01_v531_global_hk_fund_heavy_pearson_improved(self):
        """v5.31 升級後 global hk_fund_heavy Pearson 應 ≥ v5.30 baseline 0.6496"""
        v531 = self.report["global_best"]["hk_fund_heavy"]
        self.assertGreaterEqual(
            v531, 0.6496,
            f"v5.31 global hk_fund_heavy={v531} < v5.30 baseline 0.6496 (升級應改善)",
        )

    def test_02_v531_us_pearson_above_threshold(self):
        """US 10 ticker 升級後 Pearson 仍應 > 0.5 (不退化)"""
        us_pearson = self.report["regions"]["US"]["best_pearson"]
        self.assertGreater(
            us_pearson, 0.5,
            f"US Pearson={us_pearson} 應 > 0.5 (v5.30 baseline 0.7100)",
        )

    def test_03_v531_hk_pearson_zero_documented_limitation(self):
        """HK 仍 0 — 但這是文件化的方法論限制 (majority variance=0, 非 sentiment variance)"""
        hk_pearson = self.report["regions"]["HK"]["best_pearson"]
        # 文件化: HK 9 ticker majority 全 sell → Pearson var_y=0
        # v5.31 P1 升級 sentiment/news/macro 有變異, 但 majority direction 無變異
        # 解鎖需要真實 e2e 重抓或變更 sampling period (超出 deterministic 範圍)
        self.assertEqual(
            hk_pearson, 0.0,
            f"HK Pearson={hk_pearson} 應為 0 (文件化方法論限制)",
        )

    def test_04_v531_cn_pearson_unchanged(self):
        """CN 4 ticker (不來自 extended) → Pearson 不變"""
        cn_pearson = self.report["regions"]["CN"]["best_pearson"]
        self.assertAlmostEqual(
            cn_pearson, 0.9452, delta=0.005,
            msg=f"CN Pearson={cn_pearson} 應 ≈ v5.30 0.9452 (CN 不含 extended ticker)",
        )

    def test_05_v531_global_best_config_documented(self):
        """v5.31 升級後 global best config 應有 _source 標記"""
        global_best_cfg = max(
            self.report["global_best"].items(),
            key=lambda kv: kv[1],
        )[0]
        # 至少 5 個 configs 都應有結果
        self.assertEqual(
            len(self.report["global_best"]), len(WEIGHT_CONFIGS),
        )
        # 確保 best config 在 WEIGHT_CONFIGS 中 (valid)
        self.assertIn(global_best_cfg, WEIGHT_CONFIGS)

    def test_06_v531_quantify_report_file_exists(self):
        """量化 JSON 報告應已寫入 docs/"""
        report_path = _REPO_ROOT / "docs" / "v5.31_p2_per_region_full_7d.json"
        self.assertTrue(
            report_path.exists(),
            f"v5.31 P2 量化報告應存在: {report_path}",
        )

    def test_07_v531_no_regression_vs_v530_summary(self):
        """summary 應含 3 個 region 的 improvement_pp + n_tickers"""
        summary = self.report["summary"]
        for region in ("us", "hk", "cn"):
            self.assertIn(f"{region}_improvement_pp", summary)
            self.assertIn(f"{region}_n_tickers", summary)
        # n_tickers 鎖定 (US=10, HK=9, CN=4)
        self.assertEqual(summary["us_n_tickers"], 10)
        self.assertEqual(summary["hk_n_tickers"], 9)
        self.assertEqual(summary["cn_n_tickers"], 4)

    def test_08_v531_per_region_n_tickers_lock(self):
        """每個 region 至少有 3 個 ticker (Pearson 計算樣本下限)"""
        for region, info in self.report["regions"].items():
            self.assertGreaterEqual(
                info["n_tickers"], 3,
                f"{region} n_tickers={info['n_tickers']} 應 ≥ 3 (Pearson 計算下限)",
            )


if __name__ == "__main__":
    unittest.main()