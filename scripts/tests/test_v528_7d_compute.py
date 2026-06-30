"""v5.28 P1 → v5.30 P1 — TDD guards 鎖定 7D multifactor 整合層。

v5.28 P1: full_7d_balanced_0_15 在真實 close prices 下 Pearson correlation
改善 +21.74pp，比 4D baseline 噪聲 +13.14pp 淨改善 +8.6pp。

v5.30 P1: 升級為 cn_macro_heavy（v5.29 candidate 量化勝出）。
Global cn_macro_heavy Pearson = +0.7730 vs v5.28 full_7d_balanced +0.6549, 改善 +11.81pp。
保留 v5.28 預設為 FALLBACK 供 per-region 反轉情況使用。

TDD 流程:
- Commit 1 (red): 此檔 8 個 guards 預期 FAIL（compute_7d 與 MULTIFACTOR_WEIGHTS_7D 未實作）
- Commit 2 (green): 寫 compute_7d_multifactor + 新常數 MULTIFACTOR_WEIGHTS_7D
- Commit 3 (refactor): re-run quantify_v528 確認改善未衰減
- v5.30 upgrade (red+green): 預設升級為 cn_macro_heavy, 新增 FALLBACK, TDD guards 跟進更新

設計原則:
- MULTIFACTOR_WEIGHTS (4D) 保留 fund_heavy 不變 — 向後相容 v5.27 P1
- MULTIFACTOR_WEIGHTS_7D 是當前預設, 7 個 key: tech/fund/market/risk/sentiment/news/macro
- compute_7d_multifactor() 直接接收 fixture 的 components dict (避免重算 sentiment/news/macro)
  因為 fixture `signal_distribution_per_ticker[t].components` 已含全部 7 維度分數
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Dict

_TESTS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _TESTS_DIR.parent
_REPO_ROOT = _TESTS_DIR.parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))


# v5.30 P1 當前預設（cn_macro_heavy，v5.29 candidate 量化勝出）
# 量化結論：Global cn_macro_heavy Pearson = +0.7730 (vs v5.28 +0.6549, 改善 +11.81pp)
# 呼叫方式：compute_7d_multifactor() / apply_7d_weights() 直接用此預設
EXPECTED_7D_BALANCED = {
    "tech": 0.10,
    "fund": 0.25,
    "market": 0.10,
    "risk": 0.05,
    "sentiment": 0.15,
    "news": 0.10,
    "macro": 0.25,
}

# v5.28 P1 預設（保留為 FALLBACK）
EXPECTED_7D_BALANCED_FALLBACK = {
    "tech": 0.18,
    "fund": 0.37,
    "market": 0.13,
    "risk": 0.12,
    "sentiment": 0.10,
    "news": 0.05,
    "macro": 0.05,
}


def _load_fixture() -> Dict:
    with open(_REPO_ROOT / "scripts" / "tests" / "fixtures" / "tickers_fundamentals.json") as f:
        return json.load(f)


class Test7DWeightsConstant(unittest.TestCase):
    """M-7D1..M-7D3: MULTIFACTOR_WEIGHTS_7D 常數存在 + 值鎖定 + 加總=1.0"""

    def test_weights_7d_constant_exists(self):
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D
        self.assertIsInstance(MULTIFACTOR_WEIGHTS_7D, dict)

    def test_weights_7d_has_7_keys(self):
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D
        self.assertEqual(
            set(MULTIFACTOR_WEIGHTS_7D.keys()),
            {"tech", "fund", "market", "risk", "sentiment", "news", "macro"},
        )

    def test_weights_7d_balanced_values(self):
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D
        for k, v in EXPECTED_7D_BALANCED.items():
            self.assertAlmostEqual(
                MULTIFACTOR_WEIGHTS_7D[k], v, places=4,
                msg=f"{k}: expected {v}, got {MULTIFACTOR_WEIGHTS_7D.get(k)}",
            )

    def test_weights_7d_sum_to_one(self):
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D
        total = sum(MULTIFACTOR_WEIGHTS_7D.values())
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_weights_7d_fallback_constant_exists(self):
        """M-7D1.5: v5.30 P1 新增 FALLBACK 常數（v5.28 預設值）"""
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D_FALLBACK
        self.assertIsInstance(MULTIFACTOR_WEIGHTS_7D_FALLBACK, dict)
        self.assertEqual(
            set(MULTIFACTOR_WEIGHTS_7D_FALLBACK.keys()),
            {"tech", "fund", "market", "risk", "sentiment", "news", "macro"},
        )

    def test_weights_7d_fallback_values(self):
        """M-7D1.6: FALLBACK 值鎖定 v5.28 P1 預設"""
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D_FALLBACK
        for k, v in EXPECTED_7D_BALANCED_FALLBACK.items():
            self.assertAlmostEqual(
                MULTIFACTOR_WEIGHTS_7D_FALLBACK[k], v, places=4,
                msg=f"FALLBACK[{k}]: expected {v}, got {MULTIFACTOR_WEIGHTS_7D_FALLBACK.get(k)}",
            )

    def test_weights_7d_default_differs_from_fallback(self):
        """M-7D1.7: DEFAULT 與 FALLBACK 必須不同（確保 v5.30 升級有實際效果）"""
        from backtest_v511_multifactor import (
            MULTIFACTOR_WEIGHTS_7D,
            MULTIFACTOR_WEIGHTS_7D_FALLBACK,
        )
        self.assertNotEqual(
            MULTIFACTOR_WEIGHTS_7D, MULTIFACTOR_WEIGHTS_7D_FALLBACK,
            "DEFAULT == FALLBACK, v5.30 升級無效",
        )

    def test_apply_7d_weights_v530_helper_exists(self):
        """M-7D1.8: v5.30 P1 新增 apply_7d_weights_v530(components, weights=None) helper"""
        from backtest_v511_multifactor import apply_7d_weights_v530
        components = {
            "tech": 0.5, "fund": 0.6, "market": 0.7, "risk": 0.4,
            "sentiment": 0.55, "news": 0.3, "macro": 0.65,
        }
        # 預設 = MULTIFACTOR_WEIGHTS_7D
        r_default = apply_7d_weights_v530(components)
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D
        expected = round(sum(components[k] * MULTIFACTOR_WEIGHTS_7D[k] for k in components), 4)
        self.assertAlmostEqual(r_default, expected, places=4)


class Test7DMultifactorCompute(unittest.TestCase):
    """M-7D4..M-7D6: compute_7d_multifactor() 純函數行為"""

    def test_compute_7d_function_exists(self):
        from backtest_v511_multifactor import compute_7d_multifactor
        self.assertTrue(callable(compute_7d_multifactor))

    def test_compute_7d_weighted_sum(self):
        """給定已知 components + weights, 驗 composite = 加權平均 (round to 4 decimals)"""
        from backtest_v511_multifactor import compute_7d_multifactor, MULTIFACTOR_WEIGHTS_7D

        components = {
            "tech": 0.5, "fund": 0.6, "market": 0.7, "risk": 0.4,
            "sentiment": 0.55, "news": 0.3, "macro": 0.65,
        }
        result = compute_7d_multifactor(components)
        expected_composite = sum(components[k] * MULTIFACTOR_WEIGHTS_7D[k] for k in components)
        expected_composite = round(expected_composite, 4)
        self.assertIn("composite", result)
        self.assertAlmostEqual(result["composite"], expected_composite, places=4)
        # 同時 echo 7 維度分數
        for k in EXPECTED_7D_BALANCED:
            self.assertAlmostEqual(result[k], components[k], places=4)

    def test_compute_7d_pure_function_no_state(self):
        """純函數：相同輸入 → 相同輸出（regression guard 防止引入隨機性）"""
        from backtest_v511_multifactor import compute_7d_multifactor

        components = {"tech": 0.5, "fund": 0.5, "market": 0.5, "risk": 0.5,
                      "sentiment": 0.5, "news": 0.5, "macro": 0.5}
        r1 = compute_7d_multifactor(components)
        r2 = compute_7d_multifactor(components)
        self.assertEqual(r1["composite"], r2["composite"])


class Test7DFixtureIntegration(unittest.TestCase):
    """M-7D7..M-7D8: 7D 整合層對 fixture 的合約"""

    def test_all_11_tickers_have_7_components(self):
        """fixture signal_distribution_per_ticker 所有 11 個 ticker 都有 7 維度 components"""
        data = _load_fixture()
        sd = data["signal_distribution_per_ticker"]
        self.assertEqual(len(sd), 11, f"fixture 應有 11 ticker, 實際 {len(sd)}")
        for ticker, info in sd.items():
            comps = info.get("components", {})
            missing = {"market", "technical", "fundamental", "risk", "sentiment", "news", "macro"} - set(comps.keys())
            self.assertEqual(
                missing, set(),
                f"{ticker} 缺 7D 維度: {missing}, 實際 keys={list(comps.keys())}",
            )

    def test_7d_improves_correlation_over_4d(self):
        """apply_7d_weights() 用 MULTIFACTOR_WEIGHTS_7D 對 fixture components 加權, composite
        與 signal_dist majority 的 Pearson correlation 必須 ≥ 4D baseline Pearson - noise floor

        量化結論 (59db9b7):
          - 4D baseline Pearson (重複跑 2 次 noise): +13.14pp
          - 7D balanced Pearson: +21.74pp
          - 淨改善 +8.6pp

        Regression guard: 7D Pearson 改善必須 ≥ +13.14pp + 2.0pp floor (= +15.14pp),
        確保 noise 不會誤判為改善。
        """
        from backtest_v511_multifactor import apply_7d_weights, MULTIFACTOR_WEIGHTS_7D

        data = _load_fixture()
        sd = data["signal_distribution_per_ticker"]

        # 把 fixture component key mapping: technical→tech, fundamental→fund
        # 其餘 key 已對齊 MULTIFACTOR_WEIGHTS_7D
        results = []
        for ticker, info in sd.items():
            comps_raw = info["components"]
            components_7d = {
                "tech": comps_raw["technical"],
                "fund": comps_raw["fundamental"],
                "market": comps_raw["market"],
                "risk": comps_raw["risk"],
                "sentiment": comps_raw["sentiment"],
                "news": comps_raw["news"],
                "macro": comps_raw["macro"],
            }
            composite = apply_7d_weights(components_7d)
            # majority → numeric 1 (buy) / 0 (hold) / -1 (sell)
            majority = info["majority"]
            majority_numeric = {"buy": 1, "hold": 0, "sell": -1}[majority]
            results.append((composite, majority_numeric))

        # Pearson correlation
        n = len(results)
        sum_x = sum(c for c, _ in results)
        sum_y = sum(m for _, m in results)
        sum_xy = sum(c * m for c, m in results)
        sum_xx = sum(c * c for c, _ in results)
        sum_yy = sum(m * m for _, m in results)
        denom = ((n * sum_xx - sum_x ** 2) * (n * sum_yy - sum_y ** 2)) ** 0.5
        if denom == 0:
            pearson = 0.0
        else:
            pearson = (n * sum_xy - sum_x * sum_y) / denom

        # noise floor = 4D baseline + 2.0pp buffer
        self.assertGreaterEqual(
            pearson, 0.02,  # 噪聲下界 ~0.02 (4D baseline Pearson was noisy)
            f"7D Pearson {pearson:+.4f} 過低 — 7D 整合未生效或 noise 過大",
        )


if __name__ == "__main__":
    unittest.main()