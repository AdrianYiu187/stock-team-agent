"""v5.27 P1 — TDD red light: 鎖定 MULTIFACTOR_WEIGHTS 從 baseline 改為 fund_heavy。

依據 v5.27 Step 2 weight sensitivity (`0429f6c`)：
fund_heavy_0.20_0.50_0.15_0.15 在真實 close prices 下
directional_accuracy Δ -19.49pp，比 baseline -22.13pp 改善 +2.64pp。

TDD 流程：
- Commit 1 (red): 此檔 5 個 guards 預期 FAIL（fund_heavy 數值未套用）
- Commit 2 (green): 修改 MULTIFACTOR_WEIGHTS baseline → fund_heavy
- Commit 3 (refactor): re-run quantify_v527 確認改善未衰減
"""

import json
import statistics
import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _TESTS_DIR.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from backtest_v511_multifactor import (  # noqa: E402
    MULTIFACTOR_WEIGHTS,
    run_cross_market_comparison,
)


# v5.27 fund_heavy 目標值（Step 2 量化勝出配置）
EXPECTED_FUND_HEAVY = {
    "tech": 0.20,
    "fund": 0.50,
    "market": 0.15,
    "risk": 0.15,
}

# v5.11.3 baseline（已存在模組常數，作為對照組）
BASELINE = {
    "tech": 0.35,
    "fund": 0.30,
    "market": 0.20,
    "risk": 0.15,
}


class TestFundHeavyWeightsApplied(unittest.TestCase):
    """v5.27 P1 — MULTIFACTOR_WEIGHTS 改為 fund_heavy 鎖定"""

    def test_fund_heavy_tech_is_0_20(self):
        """M-FH1: tech weight = 0.20（從 baseline 0.35 降至 0.20）"""
        self.assertAlmostEqual(MULTIFACTOR_WEIGHTS["tech"], 0.20, places=4)

    def test_fund_heavy_fund_is_0_50(self):
        """M-FH2: fund weight = 0.50（從 baseline 0.30 升至 0.50）"""
        self.assertAlmostEqual(MULTIFACTOR_WEIGHTS["fund"], 0.50, places=4)

    def test_fund_heavy_market_is_0_15(self):
        """M-FH3: market weight = 0.15（從 baseline 0.20 降至 0.15）"""
        self.assertAlmostEqual(MULTIFACTOR_WEIGHTS["market"], 0.15, places=4)

    def test_fund_heavy_risk_is_0_15(self):
        """M-FH4: risk weight = 0.15（與 baseline 0.15 一致）"""
        self.assertAlmostEqual(MULTIFACTOR_WEIGHTS["risk"], 0.15, places=4)

    def test_fund_heavy_differs_from_baseline(self):
        """M-FH5: fund_heavy ≠ baseline（至少 1 個 key 改變，確認套用生效）"""
        differs = any(
            MULTIFACTOR_WEIGHTS[k] != BASELINE[k] for k in BASELINE
        )
        self.assertTrue(
            differs,
            f"MULTIFACTOR_WEIGHTS 與 baseline 完全相同 — fund_heavy 未套用: {MULTIFACTOR_WEIGHTS}"
        )


class TestFundHeavyImprovementVsBaseline(unittest.TestCase):
    """v5.27 P1 — fund_heavy 在真實 close prices 下 directional_accuracy 改善"""

    @classmethod
    def setUpClass(cls):
        """跑一次 cross-market backtest 拿 fund_heavy 真實 metrics。"""
        cls.result = run_cross_market_comparison(close_source="real")
        cls.dir_acc_delta_pp = cls.result["improvement_v5.11.3_over_v5.10_pp"]["directional_accuracy"] * 100

    def test_dir_acc_delta_better_than_baseline(self):
        """M-FH6: fund_heavy Dir Acc Δ > baseline Dir Acc Δ (-22.13pp)"""
        # 量化發現 baseline = -22.13pp, fund_heavy 量化結果 = -19.49pp
        # 允許小數點容忍：fund_heavy 必須 ≥ -20pp（即比 baseline 好）
        self.assertGreaterEqual(
            self.dir_acc_delta_pp,
            -20.0,
            f"fund_heavy Dir Acc Δ {self.dir_acc_delta_pp:+.2f}pp 比 baseline (-22.13pp) 差 — regression!"
        )

    def test_overall_accuracy_delta_within_50pp(self):
        """M-FH7: Overall Accuracy Δ 在合理範圍 (>-50pp, 不會爆掉)"""
        overall_delta = self.result["improvement_v5.11.3_over_v5.10_pp"]["overall_accuracy"] * 100
        self.assertGreater(
            overall_delta,
            -50.0,
            f"Overall Δ {overall_delta:+.2f}pp 過差 — fund_heavy 套用可能破壞 backtest"
        )

    def test_11_tickers_have_per_ticker_scores(self):
        """M-FH8: per_ticker 字典有 11 ticker,每個有 4D 維度"""
        per_ticker = self.result["per_ticker"]
        self.assertEqual(len(per_ticker), 11, f"per_ticker 應有 11 個,實際 {len(per_ticker)}")
        for t, scores in per_ticker.items():
            for dim in ("tech", "fund", "market", "risk", "composite"):
                self.assertIn(dim, scores, f"{t} 缺 {dim}")
                self.assertGreaterEqual(scores[dim], 0.0)
                self.assertLessEqual(scores[dim], 1.0)


class TestFundHeavyConfigRecorded(unittest.TestCase):
    """v5.27 P1 — cross-market 結果 config 段記錄 fund_heavy weights"""

    def test_config_records_current_weights(self):
        """M-FH9: result.config.weights 反映當前 MULTIFACTOR_WEIGHTS（即 fund_heavy）"""
        result = run_cross_market_comparison(close_source="real")
        recorded = result["config"]["weights"]
        self.assertAlmostEqual(recorded["tech"], EXPECTED_FUND_HEAVY["tech"], places=4)
        self.assertAlmostEqual(recorded["fund"], EXPECTED_FUND_HEAVY["fund"], places=4)
        self.assertAlmostEqual(recorded["market"], EXPECTED_FUND_HEAVY["market"], places=4)
        self.assertAlmostEqual(recorded["risk"], EXPECTED_FUND_HEAVY["risk"], places=4)

    def test_config_close_source_real(self):
        """M-FH10: close_source=real 仍記錄（v5.26 P1 永久化）"""
        result = run_cross_market_comparison(close_source="real")
        self.assertEqual(result["config"]["close_source"], "real")


if __name__ == "__main__":
    unittest.main()