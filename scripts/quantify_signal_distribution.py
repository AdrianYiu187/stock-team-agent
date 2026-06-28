"""v5.15 P48 — Signal distribution quantification (buy/hold/sell entropy)。

問題：
    P47 score distribution 只量化 0..1 連續值的分布（Wasserstein/entropy），
    但 cap 修復的真正下游價值是「buy/hold/sell 訊號分布恢復正常」。
    v5.13 由於 cap 飽和，99% 樣本落在 score=0.5 附近 → score_to_bhs 全部歸類 hold。
    v5.14 cap 修復後，buy 訊號比例恢復到 ~25-30%（AAPL mock GBM μ=10% 上升趨勢）。

新指標（5 個）：
    1. buy/hold/sell ratio (per version)
    2. signal_entropy = Shannon entropy over 3-class labels
    3. random_baseline_entropy = log2(3) ≈ 1.585 bits（3-class 均勻上限）
    4. majority label（cap 修復前=hold，後=buy）
    5. buy_ratio_delta（v5.13 → v5.14 buy 訊號恢復量）

Usage:
    python -m scripts.quantify_signal_distribution --tickers AAPL,MSFT
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from math import log2
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
V513_PATH = Path("/tmp/v513_stock_analysis.py")
V514_PATH = REPO_ROOT / "scripts" / "stock_analysis.py"


def _load_module(label: str, path: Path):
    if not path.exists():
        raise RuntimeError(f"{label} source not found at {path}")
    spec = importlib.util.spec_from_file_location(label, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 {label} ({path})")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_versions() -> tuple:
    """Load v5.13 and v5.14 stock_analysis modules."""
    if not V513_PATH.exists():
        import subprocess
        subprocess.run(
            "git show 0b39005^:scripts/stock_analysis.py > /tmp/v513_stock_analysis.py",
            shell=True, check=True, cwd=REPO_ROOT,
        )
    v513 = _load_module("v513_stock_analysis", V513_PATH)
    v514 = _load_module("v514_stock_analysis", V514_PATH)
    return v513, v514


def score_to_label(
    v_mod, score: float
) -> str:
    """用 v_mod.score_to_bhs 將 score 映射到 dominant label (buy/hold/sell)。

    score_to_bhs 回傳 Dict[str, float]，取最大值對應的 label。
    """
    bhs = v_mod.score_to_bhs(score)
    # Tie-break: buy > hold > sell（保守）
    return max(bhs, key=bhs.get)


def compute_signal_distribution(
    v513_mod, v514_mod, inputs: list[dict], mode: str = "equal", ticker: str = "AAPL"
) -> tuple[list[str], list[str]]:
    """對每個 sample 算 v5.13 與 v5.14 的 dominant signal label。

    mode='equal'：5 role 算術平均（向後相容，P47 預設）
    mode='dynamic'：真實 weighted_score_with_variance_penalty（v5.15 P48）
    """
    from scripts.quantify_score_distribution import (
        compute_scores,
        compute_scores_dynamic,
    )
    if mode == "dynamic":
        s13, s14, _, _ = compute_scores_dynamic(v513_mod, v514_mod, inputs, ticker=ticker)
    else:
        s13, s14 = compute_scores(v513_mod, v514_mod, inputs)
    sig13 = [score_to_label(v513_mod, s) for s in s13]
    sig14 = [score_to_label(v514_mod, s) for s in s14]
    return sig13, sig14


def compute_signal_entropy(labels: list[str]) -> float:
    """Shannon entropy over 3-class labels (buy/hold/sell)。"""
    if not labels:
        return 0.0
    counts = Counter(labels)
    total = sum(counts.values())
    probs = [c / total for c in counts.values() if c > 0]
    return float(-sum(p * log2(p) for p in probs))


def majority_signal(counts: Counter) -> str:
    """回傳最高頻 label（buy > hold > sell tie-break）。"""
    if not counts:
        return "hold"
    # 計算最高頻
    max_count = max(counts.values())
    candidates = [k for k, v in counts.items() if v == max_count]
    # Tie-break 順序：buy > hold > sell
    for label in ["buy", "hold", "sell"]:
        if label in candidates:
            return label
    return candidates[0]


def quantize_signal_distribution(
    sig13: list[str], sig14: list[str]
) -> dict:
    """5 個 metric + 結論。"""
    c13, c14 = Counter(sig13), Counter(sig14)
    n = len(sig13)
    buy13 = c13.get("buy", 0) / n
    hold13 = c13.get("hold", 0) / n
    sell13 = c13.get("sell", 0) / n
    buy14 = c14.get("buy", 0) / n
    hold14 = c14.get("hold", 0) / n
    sell14 = c14.get("sell", 0) / n
    e13 = compute_signal_entropy(sig13)
    e14 = compute_signal_entropy(sig14)
    return {
        "n_samples": n,
        # 訊號分布
        "buy_ratio_v513": round(buy13, 4),
        "hold_ratio_v513": round(hold13, 4),
        "sell_ratio_v513": round(sell13, 4),
        "buy_ratio_v514": round(buy14, 4),
        "hold_ratio_v514": round(hold14, 4),
        "sell_ratio_v514": round(sell14, 4),
        # Entropy
        "signal_entropy_v513": round(e13, 4),
        "signal_entropy_v514": round(e14, 4),
        "signal_entropy_delta": round(e14 - e13, 4),
        # Random baseline
        "random_baseline_entropy": round(log2(3), 4),
        # Majority
        "majority_v513": majority_signal(c13),
        "majority_v514": majority_signal(c14),
        # Delta
        "buy_ratio_delta": round(buy14 - buy13, 4),
        "hold_ratio_delta": round(hold14 - hold13, 4),
        "sell_ratio_delta": round(sell14 - sell13, 4),
        # 結論
        "interpretation": (
            "v5.14 entropy 上升 + buy_ratio 恢復 = cap 修復下游價值。\n"
            "若 entropy 下降則表示 cap 修復反而加劇訊號集中。\n"
            "若 majority 從 hold 變 buy = 真實訊號恢復（AAPL μ=10%）。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Signal distribution quantification")
    parser.add_argument(
        "--n", type=int, default=1000,
        help="樣本數（default 1000，seed=42 控制）",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed（default 42）",
    )
    parser.add_argument(
        "--mode", choices=["equal", "dynamic"], default="dynamic",
        help="權重模式：equal=等權重 1/5（向後相容），dynamic=真實 dynamic_weights_for_ticker + variance penalty（v5.15 P48，default）",
    )
    parser.add_argument(
        "--ticker", default="AAPL",
        help="ticker（決定 region 用於 dynamic weights，default AAPL）",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only",
    )
    args = parser.parse_args()

    print(f"📊 v5.15 P48 signal distribution (N={args.n}, seed={args.seed}, mode={args.mode}, ticker={args.ticker})")
    v513, v514 = _load_versions()

    print("⚙️  生成 realistic inputs...")
    from scripts.quantify_score_distribution import generate_realistic_inputs
    inputs = generate_realistic_inputs(n=args.n, seed=args.seed)

    print("🔬 跑 v5.13 vs v5.14 算 buy/hold/sell 訊號...")
    sig13, sig14 = compute_signal_distribution(
        v513, v514, inputs, mode=args.mode, ticker=args.ticker
    )
    quant = quantize_signal_distribution(sig13, sig14)

    if args.json:
        print(json.dumps(quant, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*60}")
        print(f"訊號分布:")
        print(f"  v5.13: buy={quant['buy_ratio_v513']:.2%}, "
              f"hold={quant['hold_ratio_v513']:.2%}, "
              f"sell={quant['sell_ratio_v513']:.2%}")
        print(f"  v5.14: buy={quant['buy_ratio_v514']:.2%}, "
              f"hold={quant['hold_ratio_v514']:.2%}, "
              f"sell={quant['sell_ratio_v514']:.2%}")
        print(f"\n訊號 entropy:")
        print(f"  v5.13 entropy: {quant['signal_entropy_v513']:.4f} bits")
        print(f"  v5.14 entropy: {quant['signal_entropy_v514']:.4f} bits")
        print(f"  Δ entropy:    {quant['signal_entropy_delta']:+.4f} bits")
        print(f"  Random baseline (uniform 3-class): {quant['random_baseline_entropy']:.4f} bits")
        print(f"\n多數訊號 (majority):")
        print(f"  v5.13: {quant['majority_v513']}")
        print(f"  v5.14: {quant['majority_v514']}")
        print(f"\nDelta (v5.14 - v5.13):")
        print(f"  Δ buy_ratio:  {quant['buy_ratio_delta']:+.4f}")
        print(f"  Δ hold_ratio: {quant['hold_ratio_delta']:+.4f}")
        print(f"  Δ sell_ratio: {quant['sell_ratio_delta']:+.4f}")
        print(f"\n💡 {quant['interpretation']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
