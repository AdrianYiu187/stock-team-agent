"""v5.30 P1 — cn_macro_heavy 升級為 7D 預設, 保留 fund_heavy-balanced 為 fallback。

業務動機 (v5.29 candidate 量化):
- v5.28 P1 預設 = full_7d_balanced_0_15, Pearson 改善 +8.6pp (淨)
- v5.29 candidate 評估 cn_macro_heavy 全域最佳 +0.7730 vs full_7d_balanced +0.6549
  → 改善 +11.81pp
- 但 per-region 反轉假設: CN region 內 global_4d_fund_heavy (+0.9452) > cn_macro_heavy (+0.4111)
  → CN 4 ticker 樣本中 4D 反而最穩定 → 必須保留 fallback 機制
- US/HK 樣本量過小 (4/3) → Pearson 全為 0, 暫不下結論

設計 (v5.30 P1):
1. MULTIFACTOR_WEIGHTS_7D → cn_macro_heavy (新預設)
2. MULTIFACTOR_WEIGHTS_7D_FALLBACK → full_7d_balanced_0_15 (舊預設, 保留供手動切換)
3. apply_7d_weights_v530(components, weights=None) — 接受可選 weights 參數
   預設 = MULTIFACTOR_WEIGHTS_7D (cn_macro_heavy)
   若傳入 weights=MULTIFACTOR_WEIGHTS_7D_FALLBACK → 退回 v5.28 行為
4. 向後相容: compute_7d_multifactor() 仍用模組級 MULTIFACTOR_WEIGHTS_7D
   (若改用 fallback 需明確呼叫 apply_7d_weights_v530(components, weights=fallback))

TDD: 5 guards
- M-V530-1: MULTIFACTOR_WEIGHTS_7D 值 == cn_macro_heavy
- M-V530-2: MULTIFACTOR_WEIGHTS_7D_FALLBACK 值 == full_7d_balanced_0_15 (舊預設)
- M-V530-3: 兩組 weights 必須 sum=1.0
- M-V530-4: apply_7d_weights_v530(components) 預設結果 = cn_macro_heavy composite
- M-V530-5: apply_7d_weights_v530(components, weights=FALLBACK) 結果 = full_7d_balanced composite
- (sanity): compute_7d_multifactor() 仍可用 (向後相容)
"""

import sys
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from backtest_v511_multifactor import (  # noqa: E402
    MULTIFACTOR_WEIGHTS_7D,
    apply_7d_weights,
    compute_7d_multifactor,
)


# v5.30 P1 預期常數值
EXPECTED_CN_MACRO_HEAVY = {
    "tech": 0.10,
    "fund": 0.25,
    "market": 0.10,
    "risk": 0.05,
    "sentiment": 0.15,
    "news": 0.10,
    "macro": 0.25,
}

# v5.28 P1 舊預設 (保留為 fallback)
EXPECTED_FULL_7D_BALANCED_FALLBACK = {
    "tech": 0.18,
    "fund": 0.37,
    "market": 0.13,
    "risk": 0.12,
    "sentiment": 0.10,
    "news": 0.05,
    "macro": 0.05,
}


class TestV530DefaultWeights(unittest.TestCase):
    """M-V530-1..3: 預設與 fallback 常數鎖定"""

    def test_default_weights_match_cn_macro_heavy(self):
        """M-V530-1: MULTIFACTOR_WEIGHTS_7D 必須等於 cn_macro_heavy 值"""
        self.assertEqual(
            set(MULTIFACTOR_WEIGHTS_7D.keys()),
            {"tech", "fund", "market", "risk", "sentiment", "news", "macro"},
        )
        for k, v in EXPECTED_CN_MACRO_HEAVY.items():
            self.assertAlmostEqual(
                MULTIFACTOR_WEIGHTS_7D[k], v, places=4,
                msg=f"MULTIFACTOR_WEIGHTS_7D[{k!r}]={MULTIFACTOR_WEIGHTS_7D[k]} expected {v}",
            )

    def test_fallback_constant_exists(self):
        """M-V530-2: MULTIFACTOR_WEIGHTS_7D_FALLBACK 必須等於 full_7d_balanced_0_15"""
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D_FALLBACK
        for k, v in EXPECTED_FULL_7D_BALANCED_FALLBACK.items():
            self.assertAlmostEqual(
                MULTIFACTOR_WEIGHTS_7D_FALLBACK[k], v, places=4,
                msg=f"FALLBACK[{k!r}]={MULTIFACTOR_WEIGHTS_7D_FALLBACK[k]} expected {v}",
            )
        # 與現有 v5.28 預設值不同 (確保真的是 fallback, 不是 alias)
        self.assertNotEqual(
            MULTIFACTOR_WEIGHTS_7D, MULTIFACTOR_WEIGHTS_7D_FALLBACK,
            "FALLBACK 與 DEFAULT 相同, 失去 fallback 意義",
        )

    def test_both_weight_sets_sum_to_one(self):
        """M-V530-3: default + fallback 兩組 weights 必須 sum=1.0"""
        from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS_7D_FALLBACK
        for name, w in [
            ("DEFAULT", MULTIFACTOR_WEIGHTS_7D),
            ("FALLBACK", MULTIFACTOR_WEIGHTS_7D_FALLBACK),
        ]:
            total = sum(w.values())
            self.assertAlmostEqual(
                total, 1.0, places=4,
                msg=f"{name} weights sum={total:.4f}, expected 1.0",
            )


class TestV530ApplyWeightsHelper(unittest.TestCase):
    """M-V530-4..5: apply_7d_weights_v530 helper"""

    def setUp(self):
        # 標準 7D components (fixture AAPL 真實數值附近)
        self.components = {
            "tech": 0.55, "fund": 0.65, "market": 0.48,
            "risk": 0.70, "sentiment": 0.55, "news": 0.50, "macro": 0.46,
        }

    def test_apply_7d_weights_v530_default(self):
        """M-V530-4: 預設 = cn_macro_heavy, 算出的 composite 必須等於套用新預設的結果"""
        from backtest_v511_multifactor import apply_7d_weights_v530
        result = apply_7d_weights_v530(self.components)
        # 用模組預設重算一次, 確認一致
        expected = round(
            sum(self.components[k] * MULTIFACTOR_WEIGHTS_7D[k] for k in MULTIFACTOR_WEIGHTS_7D),
            4,
        )
        self.assertAlmostEqual(result, expected, places=4)

    def test_apply_7d_weights_v530_fallback(self):
        """M-V530-5: 傳入 FALLBACK → 結果 = 套用 full_7d_balanced 的 composite (不同於預設)"""
        from backtest_v511_multifactor import (
            MULTIFACTOR_WEIGHTS_7D_FALLBACK,
            apply_7d_weights_v530,
        )
        result_default = apply_7d_weights_v530(self.components)
        result_fallback = apply_7d_weights_v530(
            self.components, weights=MULTIFACTOR_WEIGHTS_7D_FALLBACK,
        )
        # 兩個結果必須不同 (因為 weights 不同)
        self.assertNotAlmostEqual(
            result_default, result_fallback, places=4,
            msg="預設與 fallback 結果相同 — 兩組 weights 可能相同或 composite 巧合相同",
        )
        # fallback 結果必須等於手算的 full_7d_balanced
        expected_fallback = round(
            sum(
                self.components[k] * MULTIFACTOR_WEIGHTS_7D_FALLBACK[k]
                for k in MULTIFACTOR_WEIGHTS_7D_FALLBACK
            ),
            4,
        )
        self.assertAlmostEqual(result_fallback, expected_fallback, places=4)

    def test_compute_7d_multifactor_backward_compat(self):
        """Sanity: 舊函式 compute_7d_multifactor() 仍可用, 結果 = 預設 weights 的 composite"""
        result = compute_7d_multifactor(self.components)
        # compute_7d_multifactor 用模組預設, 結果應等於 apply_7d_weights_v530() 預設結果
        self.assertAlmostEqual(
            result["composite"],
            apply_7d_weights(self.components),
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
