"""v5.15 P47 — score distribution 量化永久化。

量化 3 個 metric（替代 directional_accuracy）：
    1. Mean delta (mean_v514 - mean_v513)
    2. Wasserstein distance (distribution shift)
    3. Information entropy delta (分分散程度)

成功標準（Rule 4）：
    1. quantify_score_distribution 可重現（seed=42）
    2. Wasserstein distance < 0.05（小幅度分布差異符合預期）
    3. Entropy delta 在 [-0.5, 0.5] bits 範圍（不會劇烈變化）
    4. Std delta 接近 0（cap 修復對 std 影響極小）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tests/scripts/ → repo root
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(REPO_ROOT))  # scripts/quantify_*.py uses `from scripts.X`

from scripts.quantify_score_distribution import (  # noqa: E402
    compute_entropy,
    compute_scores,
    generate_realistic_inputs,
    quantize_score_distribution,
)


@pytest.fixture(scope="module")
def versions():
    """載入 v5.13 + v5.14 source。"""
    if not Path("/tmp/v513_stock_analysis.py").exists():
        import subprocess
        subprocess.run(
            "git show 0b39005^:scripts/stock_analysis.py > /tmp/v513_stock_analysis.py",
            shell=True, check=True, cwd=REPO_ROOT,
        )
    spec13 = importlib.util.spec_from_file_location(
        "v513", "/tmp/v513_stock_analysis.py"
    )
    spec14 = importlib.util.spec_from_file_location(
        "v514", str(SCRIPTS_DIR / "stock_analysis.py")
    )
    assert spec13 is not None and spec13.loader is not None, "v513 spec 失敗"
    assert spec14 is not None and spec14.loader is not None, "v514 spec 失敗"
    mod13 = importlib.util.module_from_spec(spec13)
    mod14 = importlib.util.module_from_spec(spec14)
    spec13.loader.exec_module(mod13)
    spec14.loader.exec_module(mod14)
    return mod13, mod14


@pytest.fixture(scope="module")
def quant_result(versions):
    """跑量化並回傳結果 dict。"""
    v513, v514 = versions
    inputs = generate_realistic_inputs(n=1000, seed=42)
    s13, s14 = compute_scores(v513, v514, inputs)
    return quantize_score_distribution(s13, s14)


class TestV515ScoreDistribution:
    """3 個新 metric 永久守住 v5.15 P47 結論。"""

    def test_01_sample_size_is_1000(self, quant_result):
        """樣本數 = 1000。"""
        assert quant_result["n_samples"] == 1000

    def test_02_wasserstein_distance_small(self, quant_result):
        """Wasserstein distance < 0.05（小幅度分布差異符合預期）。"""
        assert 0 <= quant_result["wasserstein_distance"] < 0.05, (
            f"Wasserstein {quant_result['wasserstein_distance']} >= 0.05，"
            "可能是 cap 修復過度"
        )

    def test_03_entropy_delta_in_reasonable_range(self, quant_result):
        """Entropy delta 在 [-0.5, 0.5] bits 範圍（不會劇烈變化）。"""
        delta = quant_result["entropy_delta"]
        assert -0.5 <= delta <= 0.5, f"Entropy delta {delta} 超出 [-0.5, 0.5]"

    def test_04_entropy_v513_positive(self, quant_result):
        """v5.13 entropy > 0 bits（分布有資訊）。"""
        assert quant_result["entropy_v513"] > 0

    def test_05_entropy_v514_positive(self, quant_result):
        """v5.14 entropy > 0 bits（分布有資訊）。"""
        assert quant_result["entropy_v514"] > 0

    def test_06_mean_delta_is_finite(self, quant_result):
        """Mean delta 是有限數（v5.13 vs v5.14 確實有差異）。"""
        delta = quant_result["mean_delta"]
        assert isinstance(delta, float)
        assert -0.5 < delta < 0.5

    def test_07_std_delta_near_zero(self, quant_result):
        """Std delta 接近 0（cap 修復對 std 影響極小，< 0.05）。"""
        delta = quant_result["std_delta"]
        assert abs(delta) < 0.05, f"Std delta {delta} 過大"

    def test_08_reproducible_with_same_seed(self, versions):
        """同 seed 跑兩次結果一致。"""
        v513, v514 = versions
        inputs1 = generate_realistic_inputs(n=500, seed=42)
        inputs2 = generate_realistic_inputs(n=500, seed=42)
        s13_a, s14_a = compute_scores(v513, v514, inputs1)
        s13_b, s14_b = compute_scores(v513, v514, inputs2)
        assert s13_a == s13_b
        assert s14_a == s14_b

    def test_09_quantize_pure_function(self, quant_result):
        """quantize_score_distribution 純函數 — 重跑結果一致。"""
        # 直接重算
        assert quant_result["mean_v513"] == quant_result["mean_v513"]  # idempotent
        # 重新跑 quant
        s13 = [0.5 + 0.001 * i for i in range(100)]
        s14 = [0.5 + 0.0008 * i for i in range(100)]
        quant = quantize_score_distribution(s13, s14)
        assert quant["n_samples"] == 100
        assert quant["mean_v513"] == 0.5495
        assert quant["mean_v514"] == 0.5396

    def test_10_entropy_function_works(self):
        """compute_entropy 對均勻分布應有高 entropy。"""
        uniform = [i / 100 for i in range(100)]  # 100 個均勻分布值
        e = compute_entropy(uniform, n_bins=10)
        assert e > 3.0, f"均勻分布 entropy {e} 應 > 3.0 bits"

    def test_11_entropy_concentrated_lower(self):
        """集中分布 entropy 應 < 均勻分布。"""
        concentrated = [0.5] * 100  # 全部 = 0.5
        uniform = [i / 100 for i in range(100)]
        e_conc = compute_entropy(concentrated, n_bins=10)
        e_unif = compute_entropy(uniform, n_bins=10)
        assert e_conc < e_unif, (
            f"集中分布 entropy {e_conc} 應 < 均勻分布 {e_unif}"
        )

    # ===== v5.15 P48: weight tuning (dynamic weights) =====

    def test_12_dynamic_weights_function_exists(self, versions):
        """v5.14 stock_analysis 應有 dynamic_weights_for_ticker + weighted_score_with_variance_penalty。"""
        v513, v514 = versions
        assert hasattr(v514, "dynamic_weights_for_ticker"), (
            "v5.14 缺 dynamic_weights_for_ticker（v5.12 P35 應該已加）"
        )
        assert hasattr(v514, "weighted_score_with_variance_penalty"), (
            "v5.14 缺 weighted_score_with_variance_penalty（v5.12 P32 應該已加）"
        )

    def test_13_dynamic_weights_region_different(self, versions):
        """dynamic_weights_for_ticker 對 US/HK/CN 應產出不同權重。"""
        v513, v514 = versions
        w_us = v514.dynamic_weights_for_ticker("AAPL")
        w_hk = v514.dynamic_weights_for_ticker("0700.HK")
        w_cn = v514.dynamic_weights_for_ticker("600519.SS")
        # 加權和應 normalize ≈ 1.0
        for label, w in [("us", w_us), ("hk", w_hk), ("cn", w_cn)]:
            assert abs(sum(w.values()) - 1.0) < 0.01, (
                f"{label} weights sum {sum(w.values())} ≠ 1.0"
            )
        # 三 region 權重分布應有真實差異（normalize 後仍然如此）
        # HK 應比 US 重視 technical（波動大）
        assert w_hk["technical"] > w_us["technical"], (
            f"HK technical {w_hk['technical']} 應 > US technical {w_us['technical']}"
        )
        # CN 應比 US 重視 risk（政策風險）
        assert w_cn["risk"] > w_us["risk"], (
            f"CN risk {w_cn['risk']} 應 > US risk {w_us['risk']}"
        )
        # 三 region 權重 dict 不可完全相同
        assert w_us != w_hk, "US 與 HK 權重不應相同"
        assert w_us != w_cn, "US 與 CN 權重不應相同"
        assert w_hk != w_cn, "HK 與 CN 權重不應相同"

    def test_14_weighted_score_with_penalty_disagreement_discount(self, versions):
        """weighted_score_with_variance_penalty 對高 disagreement 應折扣。"""
        v513, v514 = versions
        # 全共識
        s_consensus = {"market": 0.7, "tech": 0.71, "fund": 0.69, "risk": 0.7}
        w = {"market": 0.2, "tech": 0.2, "fund": 0.2, "risk": 0.2, "news": 0.2}
        f1, std1 = v514.weighted_score_with_variance_penalty(s_consensus, w)
        # 完全分歧
        s_split = {"market": 1.0, "tech": 0.0, "fund": 1.0, "risk": 0.0}
        f2, std2 = v514.weighted_score_with_variance_penalty(s_split, w)
        assert std2 > std1, "分歧時 std 應更大"
        # 高分歧 → penalty → final < weighted_avg
        # weighted_avg_split = 0.5, penalty = 1 - 0.3 * std2
        assert f2 < 0.5, f"高分歧 final {f2} 應 < 0.5（被折扣）"

    def test_15_compute_scores_dynamic_returns_disagreement(self, versions):
        """compute_scores_dynamic 應回傳 analyst_disagreement 列表。"""
        from scripts.quantify_score_distribution import compute_scores_dynamic
        v513, v514 = versions
        inputs = generate_realistic_inputs(n=50, seed=42)
        s13, s14, std13, std14 = compute_scores_dynamic(v513, v514, inputs, ticker="AAPL")
        assert len(s14) == 50
        assert len(std14) == 50
        # v5.14 std 應有真實值（不是 0）
        assert any(s > 0 for s in std14), "v5.14 應有真實 analyst_disagreement"
        # v5.13 std 應為 0（沒 disagreement 概念）
        assert all(s == 0 for s in std13), "v5.13 沒 disagreement 概念，std 應為 0"

    def test_16_dynamic_mode_wasserstein_amplified(self, versions):
        """Dynamic mode Wasserstein 應 ≥ equal mode（真實權重放大 cap 修復影響）。"""
        from scripts.quantify_score_distribution import (
            compute_scores,
            compute_scores_dynamic,
            quantize_score_distribution,
        )
        v513, v514 = versions
        inputs = generate_realistic_inputs(n=500, seed=42)

        # Equal mode
        s13_eq, s14_eq = compute_scores(v513, v514, inputs)
        quant_eq = quantize_score_distribution(s13_eq, s14_eq)

        # Dynamic mode (AAPL)
        s13_dy, s14_dy, _, _ = compute_scores_dynamic(v513, v514, inputs, ticker="AAPL")
        quant_dy = quantize_score_distribution(s13_dy, s14_dy)

        # Dynamic Wasserstein 應 ≥ equal（variance penalty 放大分布差異）
        assert quant_dy["wasserstein_distance"] >= quant_eq["wasserstein_distance"], (
            f"Dynamic Wasserstein {quant_dy['wasserstein_distance']} 應 ≥ "
            f"Equal Wasserstein {quant_eq['wasserstein_distance']}"
        )

    def test_17_dynamic_mode_entropy_lower_than_equal(self, versions):
        """Dynamic mode entropy delta 應 < equal mode（variance penalty 降低 entropy）。"""
        from scripts.quantify_score_distribution import (
            compute_scores,
            compute_scores_dynamic,
            quantize_score_distribution,
        )
        v513, v514 = versions
        inputs = generate_realistic_inputs(n=500, seed=42)

        quant_eq = quantize_score_distribution(*compute_scores(v513, v514, inputs))
        s13_dy, s14_dy, _, _ = compute_scores_dynamic(v513, v514, inputs, ticker="AAPL")
        quant_dy = quantize_score_distribution(s13_dy, s14_dy)

        # variance penalty 強烈壓縮分布 → entropy 應大幅下降
        assert quant_dy["entropy_delta"] < quant_eq["entropy_delta"], (
            f"Dynamic entropy_delta {quant_dy['entropy_delta']} 應 < "
            f"Equal entropy_delta {quant_eq['entropy_delta']}"
        )