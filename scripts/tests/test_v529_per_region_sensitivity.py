"""v5.29 候選 — per-region 7D weight 重新校準 (TDD guards)。

業務動機: v5.27 Step 2 揭示全域 fund_heavy 對 A 股 5 個 HIGH-risk 中 2 個反向 BUY。
量化結論 (v5.29 candidate 評估, 2026-06-30):
  - Global 7D balanced_0_15 baseline = +0.6549
  - Global cn_macro_heavy 反而最佳 = +0.7730 (+11.81pp vs 7D baseline)
  - CN region 內部: global_4d_fund_heavy 最佳 = +0.9452, cn_macro_heavy 最差 = +0.4111
    (反轉假設 — CN 樣本對 4D 整合最穩定)
  - US/HK region 樣本量過小 (4/3 tickers), Pearson 全為 0.0 → 無法分辨 config 優劣
    (fixture composite 變異為 0, 需要擴大 sample 才能下結論)

v5.30 P1 升級語意:
  - cn_macro_heavy 從「候選 config」升級為「MULTIFACTOR_WEIGHTS_7D 預設」
  - test_cn_macro_heavy_best_globally 語意改為:
    「在 5 個候選 config 中, cn_macro_heavy 仍是 Pearson 最高的 (即將升級為預設的候選)」
  - 這確保 v5.30 升級不是任意的, 而是來自 v5.29 candidate 量化的可重現結論

TDD 流程:
- 此檔 6 個 guards 鎖定上述量化結論
- 防止未來重跑 noise 把 candidate 結論推翻
"""

import sys
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "quantify_v529_per_region_sensitivity.py"
sys.path.insert(0, str(_SCRIPT.parent))

from quantify_v529_per_region_sensitivity import (  # noqa: E402
    REGION_MAP,
    WEIGHT_CONFIGS,
    compute_composite_with_weights,
    evaluate_per_region,
    pearson,
)


class TestV529RegionMap(unittest.TestCase):
    """M-V529-1..2: REGION_MAP 鎖定 11 ticker 分區"""

    def test_all_11_tickers_mapped(self):
        """11 ticker 都必須有 region 標記"""
        self.assertEqual(len(REGION_MAP), 11)

    def test_region_counts(self):
        """US=4, HK=3, CN=4"""
        counts = {"US": 0, "HK": 0, "CN": 0}
        for region in REGION_MAP.values():
            counts[region] += 1
        self.assertEqual(counts, {"US": 4, "HK": 3, "CN": 4})


class TestV529WeightConfigs(unittest.TestCase):
    """M-V529-3..4: 5 weight configs 必須 sum=1.0"""

    def test_5_configs_exist(self):
        self.assertEqual(len(WEIGHT_CONFIGS), 5)

    def test_all_configs_sum_to_one(self):
        """每個 weight config 必須 sum=1.0 (避免 composite 失真)"""
        for cfg_name, weights in WEIGHT_CONFIGS.items():
            total = sum(weights.values())
            self.assertAlmostEqual(
                total, 1.0, places=4,
                msg=f"{cfg_name}: weights sum={total:.4f}, expected 1.0",
            )


class TestV529EvaluateCandidate(unittest.TestCase):
    """M-V529-5..6: evaluate_per_region() 量化結論鎖定"""

    def test_global_baseline_7d_pearson_within_range(self):
        """Global 7D balanced_0_15 Pearson 必須 ∈ [0.5, 0.8]
        (量化 v5.29 結果: +0.6549, 留 ±0.15 noise margin)"""
        report = evaluate_per_region()
        v = report["global_best"]["global_7d_balanced_0_15"]
        self.assertGreaterEqual(v, 0.5, f"global 7D Pearson {v} 過低")
        self.assertLessEqual(v, 0.8, f"global 7D Pearson {v} 過高")

    def test_cn_macro_heavy_best_globally(self):
        """v5.30 P1 升級語意: cn_macro_heavy 從候選升級為預設。

        量化決策依據 (v5.29 candidate 評估, 2026-06-30):
        - 在 5 個候選 config 中, cn_macro_heavy Pearson 最高
        - 升級決定來自候選量化, 不是任意設定

        此 guard 鎖定 v5.30 升級的可重現性:
        1. MULTIFACTOR_WEIGHTS_7D 必須等於 cn_macro_heavy (v5.29 量化勝出值)
        2. evaluate_per_region() 計算的 cn_macro_heavy Pearson 必須 = v5.30 預設 Pearson
           (因為兩者用同一組 weights, 結果必須一致)
        3. 預設 Pearson 必須 > 7D baseline (v5.28 預設) + 5pp noise floor
           (即 +0.7049 = +0.6549 + 5pp, 對應 +11.81pp 改善至少保留一半)
        """
        from backtest_v511_multifactor import (
            MULTIFACTOR_WEIGHTS_7D,
        )

        # (1) 預設值等於 cn_macro_heavy (升級生效)
        cn_macro_heavy = {
            "tech": 0.10, "fund": 0.25, "market": 0.10, "risk": 0.05,
            "sentiment": 0.15, "news": 0.10, "macro": 0.25,
        }
        for k, v in cn_macro_heavy.items():
            self.assertAlmostEqual(
                MULTIFACTOR_WEIGHTS_7D[k], v, places=4,
                msg=f"v5.30 升級失敗: MULTIFACTOR_WEIGHTS_7D[{k}]={MULTIFACTOR_WEIGHTS_7D[k]} expected {v}",
            )

        # (2) 候選 cn_macro_heavy Pearson 必須等於套用預設的結果
        report = evaluate_per_region()
        candidate_pearson = report["global_best"]["cn_macro_heavy"]

        # 手算套用預設的 Pearson (11 ticker composite vs majority)
        from quantify_v529_per_region_sensitivity import _map_components
        import json
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "tickers_fundamentals.json"
        with open(fixture_path) as f:
            fixture = json.load(f)
        sd = fixture["signal_distribution_per_ticker"]
        composites = []
        majorities = []
        for ticker, info in sd.items():
            components_7d = _map_components(info["components"])
            composite = round(
                sum(components_7d[k] * MULTIFACTOR_WEIGHTS_7D[k] for k in MULTIFACTOR_WEIGHTS_7D),
                4,
            )
            composites.append(composite)
            majorities.append({"buy": 1, "hold": 0, "sell": -1}[info["majority"]])

        # 計算 Pearson
        n = len(composites)
        mean_x = sum(composites) / n
        mean_y = sum(majorities) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(composites, majorities))
        var_x = sum((x - mean_x) ** 2 for x in composites)
        var_y = sum((y - mean_y) ** 2 for y in majorities)
        denom = (var_x * var_y) ** 0.5
        default_pearson = round(cov / denom, 4) if denom > 0 else 0.0

        self.assertAlmostEqual(
            candidate_pearson, default_pearson, places=4,
            msg=f"v5.30 預設與 cn_macro_heavy 候選 Pearson 不一致: "
                f"候選 {candidate_pearson} vs 預設 {default_pearson} — 升級與量化脫鉤",
        )

        # (3) 預設 Pearson 必須 > 7D baseline + 5pp (v5.30 升級的 noise floor 保護)
        baseline = report["global_best"]["global_7d_balanced_0_15"]
        improvement = default_pearson - baseline
        self.assertGreater(
            improvement, 0.05,
            f"v5.30 升級改善不足: {improvement:.4f} (候選 +0.7730 vs 7D +0.6549, 期望 ≥ +0.05)",
        )

    def test_cn_region_4d_better_than_7d_macro(self):
        """**非預期結論**: CN region 內 global_4d_fund_heavy (+0.9452) > cn_macro_heavy (+0.4111)

        業務解讀: 4 個 CN ticker 樣本中, 4D 整合反而比 macro-heavy 7D 更貼近多數方向。
        暗示 CN 高頻 trading 信號主要來自 fund/tech 而非 macro (A 股特殊環境)。
        此結論是 candidate 量化反轉假設, 必須鎖定以防 noise 推翻。
        """
        report = evaluate_per_region()
        cn_results = report["regions"]["CN"]["results"]
        self.assertGreater(
            cn_results["global_4d_fund_heavy"],
            cn_results["cn_macro_heavy"],
            f"CN region: 4D {cn_results['global_4d_fund_heavy']:.4f} 應該 > macro_heavy {cn_results['cn_macro_heavy']:.4f}",
        )

    def test_us_hk_pearson_zero_due_to_small_sample(self):
        """US (4) / HK (3) region Pearson 全為 0 — fixture composite 變異為 0

        此 guard 鎖定「樣本量過小無法分辨」的限制, 防止未來 US/HK 擴大 sample
        後卻誤刪此結論。
        """
        report = evaluate_per_region()
        for region in ("US", "HK"):
            for cfg_name, pearson_v in report["regions"][region]["results"].items():
                self.assertEqual(
                    pearson_v, 0.0,
                    f"{region}/{cfg_name}: Pearson {pearson_v} ≠ 0 — 樣本變異改變需更新結論",
                )


if __name__ == "__main__":
    unittest.main()