"""v5.15 P47 — Score distribution quantification（directional_accuracy 替代指標）。

問題：
    directional_accuracy = sign(score - 0.5) ≈ buy-only baseline（bias 市場無鑑別度）

新指標（3 個，全部從 score 分布推導）：
    1. Mean delta — v5.14 mean - v5.13 mean（cap 修復應讓 mean 反映真實分布）
    2. Distribution shift — Wasserstein distance（量化分布整體位移量）
    3. Information entropy — H = -Σ p*log(p) on binned scores
        cap 修復應讓 entropy 上升（更多資訊 = 更分散）

成功標準（Rule 4）：
    1. v5.14 entropy ≥ v5.13 entropy（cap 修復 → 更分散）
    2. mean delta 不為 0（v5.14 ≠ v5.13）
    3. Wasserstein distance > 0（分布有真實位移）

Usage:
    python -m scripts.quantify_score_distribution --tickers AAPL,MSFT
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev
from typing import Callable, Optional

import numpy as np
from scipy.stats import wasserstein_distance

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
        # 自動從 git 拉
        import subprocess
        subprocess.run(
            "git show 0b39005^:scripts/stock_analysis.py > /tmp/v513_stock_analysis.py",
            shell=True, check=True, cwd=REPO_ROOT,
        )
    v513 = _load_module("v513_stock_analysis", V513_PATH)
    v514 = _load_module("v514_stock_analysis", V514_PATH)
    return v513, v514


def generate_realistic_inputs(n: int = 1000, seed: int = 42) -> list[dict]:
    """生成 N 個 realistic market/tech/risk/fund/news 輸入樣本（seed 控制）。"""
    rng = np.random.default_rng(seed)
    return [
        {
            # market
            "ytd_return": rng.normal(5, 30),
            "pos_52wk": rng.uniform(0, 100),
            "from_high_pct": rng.normal(-15, 25),
            "beta": rng.uniform(0.5, 1.8),
            # tech
            "rsi": rng.uniform(20, 85),
            "macd_val": rng.normal(0, 2.5),
            "price": rng.uniform(50, 300),
            "ma50": rng.uniform(50, 300),
            "momentum_20d": rng.normal(0, 30),
            # risk
            "volatility": rng.uniform(0.1, 0.6),
            "var_95": rng.uniform(-0.15, 0.05),
            "max_dd": rng.uniform(-0.5, 0.0),
            "sharpe": rng.uniform(-1, 3),
            # fund
            "pe": rng.uniform(5, 50),
            "roe": rng.uniform(0.05, 0.4),
            "peg_val": rng.uniform(0.5, 3.0),
            "revenue_growth": rng.uniform(-0.1, 0.4),
            # news
            "news_count": int(rng.integers(10, 200)),
            "region_count": int(rng.integers(1, 6)),
            "source_diversity": int(rng.integers(2, 14)),
        }
        for _ in range(n)
    ]


def compute_scores(
    v513_mod, v514_mod, inputs: list[dict]
) -> tuple[list[float], list[float]]:
    """跑 v5.13 vs v5.14 五函數算 total score。

    等權重模式（向後相容）：5 role 算術平均
    Dynamic 模式（v5.15 P48）：weighted_score_with_variance_penalty（7 role + region-aware）
    """
    scores_v513, scores_v514 = [], []
    for inp in inputs:
        # 五函數加權 → total score
        market_v513 = v513_mod.market_score_multifactor(
            ytd_return=inp["ytd_return"],
            pos_52wk=inp["pos_52wk"],
            from_high_pct=inp["from_high_pct"],
            beta=inp["beta"],
        )
        market_v514 = v514_mod.market_score_multifactor(
            ytd_return=inp["ytd_return"],
            pos_52wk=inp["pos_52wk"],
            from_high_pct=inp["from_high_pct"],
            beta=inp["beta"],
        )

        tech_v513 = v513_mod.tech_score_multifactor(
            rsi=inp["rsi"],
            macd_val=inp["macd_val"],
            price=inp["price"],
            ma50=inp["ma50"],
            momentum_20d=inp["momentum_20d"],
        )
        tech_v514 = v514_mod.tech_score_multifactor(
            rsi=inp["rsi"],
            macd_val=inp["macd_val"],
            price=inp["price"],
            ma50=inp["ma50"],
            momentum_20d=inp["momentum_20d"],
        )

        risk_v513 = v513_mod.risk_score_multifactor(
            volatility=inp["volatility"],
            var_95=inp["var_95"],
            max_dd=inp["max_dd"],
            sharpe=inp["sharpe"],
        )
        risk_v514 = v514_mod.risk_score_multifactor(
            volatility=inp["volatility"],
            var_95=inp["var_95"],
            max_dd=inp["max_dd"],
            sharpe=inp["sharpe"],
        )

        fund_v513 = v513_mod.fund_score_multifactor(
            pe=inp["pe"],
            roe=inp["roe"],
            peg_val=inp["peg_val"],
            revenue_growth=inp["revenue_growth"],
        )
        fund_v514 = v514_mod.fund_score_multifactor(
            pe=inp["pe"],
            roe=inp["roe"],
            peg_val=inp["peg_val"],
            revenue_growth=inp["revenue_growth"],
        )

        news_v513 = v513_mod.news_score_multifactor(
            news_count=inp["news_count"],
            region_count=inp["region_count"],
            source_diversity=inp["source_diversity"],
        )
        news_v514 = v514_mod.news_score_multifactor(
            news_count=inp["news_count"],
            region_count=inp["region_count"],
            source_diversity=inp["source_diversity"],
        )

        # 等權重加總（簡化：實際權重由 weighted_score_with_variance_penalty 決定）
        scores_v513.append(
            (market_v513 + tech_v513 + risk_v513 + fund_v513 + news_v513) / 5
        )
        scores_v514.append(
            (market_v514 + tech_v514 + risk_v514 + fund_v514 + news_v514) / 5
        )
    return scores_v513, scores_v514


def compute_scores_dynamic(
    v513_mod, v514_mod, inputs: list[dict], ticker: str = "AAPL"
) -> tuple[list[float], list[float], list[float], list[float]]:
    """v5.15 P48: 用真實 weighted_score_with_variance_penalty + dynamic_weights_for_ticker。

    回傳：
        scores_v513, scores_v514: final score（含 variance penalty）
        std_v513, std_v514: analyst_disagreement（量化分歧度）
    """
    scores_v513, scores_v514 = [], []
    std_v513, std_v514 = [], []

    # 一次算 weights（ticker 不變）
    weights = v514_mod.dynamic_weights_for_ticker(ticker)

    for inp in inputs:
        # v5.14 算各 role score
        m14 = v514_mod.market_score_multifactor(
            ytd_return=inp["ytd_return"],
            pos_52wk=inp["pos_52wk"],
            from_high_pct=inp["from_high_pct"],
            beta=inp["beta"],
        )
        t14 = v514_mod.tech_score_multifactor(
            rsi=inp["rsi"],
            macd_val=inp["macd_val"],
            price=inp["price"],
            ma50=inp["ma50"],
            momentum_20d=inp["momentum_20d"],
        )
        r14 = v514_mod.risk_score_multifactor(
            volatility=inp["volatility"],
            var_95=inp["var_95"],
            max_dd=inp["max_dd"],
            sharpe=inp["sharpe"],
        )
        f14 = v514_mod.fund_score_multifactor(
            pe=inp["pe"],
            roe=inp["roe"],
            peg_val=inp["peg_val"],
            revenue_growth=inp["revenue_growth"],
        )
        n14 = v514_mod.news_score_multifactor(
            news_count=inp["news_count"],
            region_count=inp["region_count"],
            source_diversity=inp["source_diversity"],
        )

        # v5.13 算各 role score
        m13 = v513_mod.market_score_multifactor(
            ytd_return=inp["ytd_return"],
            pos_52wk=inp["pos_52wk"],
            from_high_pct=inp["from_high_pct"],
            beta=inp["beta"],
        )
        t13 = v513_mod.tech_score_multifactor(
            rsi=inp["rsi"],
            macd_val=inp["macd_val"],
            price=inp["price"],
            ma50=inp["ma50"],
            momentum_20d=inp["momentum_20d"],
        )
        r13 = v513_mod.risk_score_multifactor(
            volatility=inp["volatility"],
            var_95=inp["var_95"],
            max_dd=inp["max_dd"],
            sharpe=inp["sharpe"],
        )
        f13 = v513_mod.fund_score_multifactor(
            pe=inp["pe"],
            roe=inp["roe"],
            peg_val=inp["peg_val"],
            revenue_growth=inp["revenue_growth"],
        )
        n13 = v513_mod.news_score_multifactor(
            news_count=inp["news_count"],
            region_count=inp["region_count"],
            source_diversity=inp["source_diversity"],
        )

        # weighted_score_with_variance_penalty 需要 7 role dict
        # sentiment 與 macro 用各 0.5（中性基線，因為 realistic_inputs 沒造 sentiment/macro）
        scores14 = {
            "market": m14, "technical": t14, "fundamental": f14,
            "risk": r14, "sentiment": 0.5, "news": n14, "macro": 0.5,
        }
        scores13 = {
            "market": m13, "technical": t13, "fundamental": f13,
            "risk": r13, "sentiment": 0.5, "news": n13, "macro": 0.5,
        }

        # v5.14 與 v5.13 都用 v5.14 的 weights（因為 v5.12 P35 已引入 weights）
        # v5.13 沒 weights 概念，視為等權重 1/5
        weights13 = {k: 0.2 for k in scores13}
        # 為 v5.13 模擬一個「簡化 weighted」：等權重算術平均
        scores_v513.append(sum(scores13.values()) / len(scores13))
        std_v513.append(0.0)  # v5.13 沒 disagreement 概念

        # v5.14 用真實 weighted_score_with_variance_penalty
        f14_final, std14 = v514_mod.weighted_score_with_variance_penalty(scores14, weights)
        scores_v514.append(f14_final)
        std_v514.append(std14)

    return scores_v513, scores_v514, std_v513, std_v514


def compute_entropy(scores: list[float], n_bins: int = 10) -> float:
    """計算 score 分布的 Shannon entropy（binning to n_bins）。"""
    if not scores:
        return 0.0
    bins = np.linspace(0, 1, n_bins + 1)
    digitized = np.digitize(scores, bins) - 1
    digitized = np.clip(digitized, 0, n_bins - 1)
    counts = Counter(digitized.tolist())
    total = sum(counts.values())
    probs = np.array([c / total for c in counts.values()])
    probs = probs[probs > 0]  # 避免 log(0)
    return float(-np.sum(probs * np.log2(probs)))


def quantize_score_distribution(
    scores_v513: list[float],
    scores_v514: list[float],
    std_v514: list[float] | None = None,
) -> dict:
    """3 個新指標 + 傳統 std 對比 + analyst_disagreement（dynamic mode）。"""
    result = {
        "n_samples": len(scores_v513),
        # 指標 1: mean delta
        "mean_v513": round(mean(scores_v513), 4),
        "mean_v514": round(mean(scores_v514), 4),
        "mean_delta": round(mean(scores_v514) - mean(scores_v513), 4),
        # 指標 2: distribution shift (Wasserstein distance)
        "wasserstein_distance": round(
            wasserstein_distance(scores_v513, scores_v514), 4
        ),
        # 指標 3: information entropy
        "entropy_v513": round(compute_entropy(scores_v513), 4),
        "entropy_v514": round(compute_entropy(scores_v514), 4),
        "entropy_delta": round(
            compute_entropy(scores_v514) - compute_entropy(scores_v513), 4
        ),
        # 傳統 std（向後相容）
        "std_v513": round(pstdev(scores_v513), 4),
        "std_v514": round(pstdev(scores_v514), 4),
        "std_delta": round(pstdev(scores_v514) - pstdev(scores_v513), 4),
    }
    if std_v514:
        result["analyst_disagreement_v514"] = round(mean(std_v514), 4)
        result["penalty_discount_mean"] = round(
            1.0 - mean(std_v514) * 0.3, 4  # weighted_score_with_variance_penalty 公式
        )
    # 結論
    result["interpretation"] = (
        "v5.14 entropy 上升 + Wasserstein > 0 = score 分布真有變化。"
        "若 entropy 下降則表示 v5.14 cap 修復反而讓分布更集中（cap 製造假分散）。"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Score distribution quantification")
    parser.add_argument(
        "--n", type=int, default=1000,
        help="樣本數（default 1000，seed=42 控制）",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed（default 42）",
    )
    parser.add_argument(
        "--weights", choices=["equal", "dynamic"], default="equal",
        help="權重模式：equal=等權重 1/5（向後相容），dynamic=真實 dynamic_weights_for_ticker + variance penalty（v5.15 P48）",
    )
    parser.add_argument(
        "--ticker", default="AAPL",
        help="ticker（決定 region 用於 dynamic weights：US/HK/CN，default AAPL）",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON only",
    )
    args = parser.parse_args()

    mode_label = "dynamic (weighted_score_with_variance_penalty)" if args.weights == "dynamic" else "equal (1/5 算術平均)"
    print(f"📊 v5.15 P47/P48 score distribution quantification (N={args.n}, seed={args.seed}, weights={mode_label}, ticker={args.ticker})")
    v513, v514 = _load_versions()

    print("⚙️  生成 realistic inputs...")
    inputs = generate_realistic_inputs(n=args.n, seed=args.seed)

    print(f"🔬 跑 v5.13 vs v5.14 算 total score...")
    if args.weights == "dynamic":
        s13, s14, _, std14 = compute_scores_dynamic(v513, v514, inputs, ticker=args.ticker)
        quant = quantize_score_distribution(s13, s14, std_v514=std14)
    else:
        s13, s14 = compute_scores(v513, v514, inputs)
        quant = quantize_score_distribution(s13, s14)

    if args.json:
        print(json.dumps(quant, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*60}")
        print(f"指標 1 — Mean delta")
        print(f"  v5.13 mean: {quant['mean_v513']:.4f}")
        print(f"  v5.14 mean: {quant['mean_v514']:.4f}")
        print(f"  Δ mean:    {quant['mean_delta']:+.4f}")
        print(f"\n指標 2 — Distribution shift (Wasserstein distance)")
        print(f"  Wasserstein: {quant['wasserstein_distance']:.4f}")
        print(f"  (>0 表示 v5.14 分布與 v5.13 有真實位移)")
        print(f"\n指標 3 — Information entropy")
        print(f"  v5.13 entropy: {quant['entropy_v513']:.4f} bits")
        print(f"  v5.14 entropy: {quant['entropy_v514']:.4f} bits")
        print(f"  Δ entropy:    {quant['entropy_delta']:+.4f} bits")
        print(f"  (上升 = v5.14 更分散 = 真實 cap 修復有效)")
        print(f"\n傳統 std 對比:")
        print(f"  v5.13 std: {quant['std_v513']:.4f}")
        print(f"  v5.14 std: {quant['std_v514']:.4f}")
        print(f"  Δ std:    {quant['std_delta']:+.4f}")
        if "analyst_disagreement_v514" in quant:
            print(f"\n[P48 dynamic weights 專屬]")
            print(f"  analyst_disagreement (v5.14): {quant['analyst_disagreement_v514']:.4f}")
            print(f"  penalty_discount_mean:         {quant['penalty_discount_mean']:.4f}")
            print(f"  (penalty < 1.0 表示多樣本觸發 disagreement 折扣)")
        print(f"\n💡 {quant['interpretation']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())