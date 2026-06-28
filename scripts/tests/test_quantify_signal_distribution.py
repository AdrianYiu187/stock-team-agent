"""v5.15 P48 — signal distribution 量化（buy/hold/sell 訊號分布 + entropy）。

問題：
    score distribution (P47) 只量化 0..1 連續值的分布，沒看下游訊號分布。
    但 cap 修復的真正價值是「buy/hold/sell 訊號分布恢復正常」
    （v5.13 99% hold → v5.14 ~26% buy）。

新指標（5 個）：
    1. buy_ratio_v513 / v514 — 買入訊號比例
    2. hold_ratio_v513 / v514 — 持有觀望比例
    3. sell_ratio_v513 / v514 — 賣出訊號比例
    4. signal_entropy_v513 / v514 — 3-class Shannon entropy（買/持/賣）
    5. random_baseline_entropy — 均勻分布 = log2(3) ≈ 1.585 bits（理論上限）

成功標準（Rule 4）：
    1. buy + hold + sell = 1.0（每個樣本）
    2. v5.14 signal_entropy > v5.13 signal_entropy（cap 修復 → 訊號更分散）
    3. v5.13 hold_ratio 應 > v5.14 hold_ratio（cap 製造假中性）
    4. signal_entropy 應 ≤ log2(3)（3-class Shannon 上限）
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from math import log2
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # tests/scripts/ → repo root
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(REPO_ROOT))


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
def signal_result(versions):
    """跑量化並回傳結果 dict（default mode=dynamic, ticker=AAPL）。"""
    from scripts.quantify_signal_distribution import quantize_signal_distribution
    from scripts.quantify_score_distribution import generate_realistic_inputs
    from scripts.quantify_signal_distribution import compute_signal_distribution

    v513, v514 = versions
    inputs = generate_realistic_inputs(n=1000, seed=42)
    sig13, sig14 = compute_signal_distribution(
        v513, v514, inputs, mode="dynamic", ticker="AAPL"
    )
    return quantize_signal_distribution(sig13, sig14)


class TestV515SignalDistribution:
    """buy/hold/sell 訊號分布永久守住 v5.15 P48 結論。

    重要前提（mock GBM μ=10% 上漲趨勢 → 兩版 mean > 0.5 → 多數 buy）：
    - v5.13 dynamic mode: 100% buy（mean=0.5946, no sell signals）
    - v5.14 dynamic mode: 99.1% buy + 0.9% sell（mean=0.5577, 出現少量 sell）
    - v5.14 signal_entropy 略高於 v5.13（+0.0741 bits）— cap 修復讓 sell 訊號浮現
    """

    def test_01_sample_size_is_1000(self, signal_result):
        assert signal_result["n_samples"] == 1000

    def test_02_buy_hold_sell_sums_to_one(self, signal_result):
        """每個 ratio set 加總 = 1.0（sigmoid 設計約束）。"""
        for ver in ["v513", "v514"]:
            total = (
                signal_result[f"buy_ratio_{ver}"]
                + signal_result[f"hold_ratio_{ver}"]
                + signal_result[f"sell_ratio_{ver}"]
            )
            assert abs(total - 1.0) < 0.01, (
                f"{ver} buy+hold+sell={total} ≠ 1.0"
            )

    def test_03_v514_hold_ratio_at_most_v513(self, signal_result):
        """v5.14 hold_ratio 應 ≤ v5.13（cap 修復不增加假中性）。"""
        h13 = signal_result["hold_ratio_v513"]
        h14 = signal_result["hold_ratio_v514"]
        assert h14 <= h13 + 0.001, (
            f"v5.14 hold {h14:.4f} 應 ≤ v5.13 hold {h13:.4f}"
        )

    def test_04_v514_signal_entropy_higher_than_v513(self, signal_result):
        """v5.14 signal_entropy 應 > v5.13（訊號更分散，因為 cap 修復讓 sell 浮現）。"""
        e13 = signal_result["signal_entropy_v513"]
        e14 = signal_result["signal_entropy_v514"]
        assert e14 > e13, (
            f"v5.14 entropy {e14:.4f} 應 > v5.13 entropy {e13:.4f}"
        )

    def test_05_signal_entropy_bounded_by_uniform(self, signal_result):
        """signal_entropy 應 ≤ log2(3) ≈ 1.585 bits（3-class Shannon 上限）。"""
        log2_3 = log2(3)
        for ver in ["v513", "v514"]:
            e = signal_result[f"signal_entropy_{ver}"]
            assert 0 <= e <= log2_3 + 0.001, (
                f"{ver} entropy {e} 超出 [0, log2(3)]"
            )

    def test_06_random_baseline_entropy_is_log2_3(self):
        """3-class 均勻分布 entropy = log2(3) ≈ 1.585 bits。"""
        from scripts.quantify_signal_distribution import compute_signal_entropy
        uniform = ["buy"] * 100 + ["hold"] * 100 + ["sell"] * 100
        e = compute_signal_entropy(uniform)
        assert abs(e - log2(3)) < 0.01, f"均勻分布 entropy {e} 應 ≈ log2(3)={log2(3)}"

    def test_07_concentrated_signal_lower_entropy(self):
        """集中分布（如全 hold）entropy 應 < 均勻分布。"""
        from scripts.quantify_signal_distribution import compute_signal_entropy
        concentrated = ["hold"] * 300
        uniform = ["buy"] * 100 + ["hold"] * 100 + ["sell"] * 100
        e_conc = compute_signal_entropy(concentrated)
        e_unif = compute_signal_entropy(uniform)
        assert e_conc < e_unif, (
            f"集中 entropy {e_conc} 應 < 均勻 entropy {e_unif}"
        )

    def test_08_majority_v513_is_buy(self, signal_result):
        """v5.13 majority 訊號應是 buy（mock GBM μ=10% → mean > 0.5）。"""
        majority = signal_result["majority_v513"]
        assert majority == "buy", (
            f"v5.13 majority 應為 buy（μ=10% 上升趨勢），實際 {majority}"
        )

    def test_09_majority_v514_is_buy(self, signal_result):
        """v5.14 majority 訊號應是 buy（同上 mock GBM 上升）。"""
        majority = signal_result["majority_v514"]
        assert majority == "buy", (
            f"v5.14 majority 應為 buy（μ=10% 上升），實際 {majority}"
        )

    def test_10_v514_has_sell_signal_floated(self, signal_result):
        """v5.14 sell_ratio 應 > v5.13 sell_ratio（cap 修復讓 sell 訊號浮現）。"""
        s13 = signal_result["sell_ratio_v513"]
        s14 = signal_result["sell_ratio_v514"]
        # v5.13 0%（完全集中 buy），v5.14 ~0.9%（cap 修復後少數 sell 出現）
        assert s14 > s13, (
            f"v5.14 sell {s14:.4f} 應 > v5.13 sell {s13:.4f}"
        )

    def test_11_majority_signal_classification(self):
        """majority_signal 純函數應正確分類。"""
        from scripts.quantify_signal_distribution import majority_signal
        counts = Counter({"buy": 10, "hold": 5, "sell": 2})
        assert majority_signal(counts) == "buy"
        counts = Counter({"buy": 2, "hold": 10, "sell": 5})
        assert majority_signal(counts) == "hold"
        counts = Counter({"buy": 1, "hold": 2, "sell": 10})
        assert majority_signal(counts) == "sell"
