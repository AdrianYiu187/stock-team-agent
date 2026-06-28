"""
v5.13 P36b — 4 信號（tech/fund/risk/sentiment）連續化 backtest 量化

比較 v5.11.3 (4 處 hard threshold) vs v5.13 P36b (sigmoid soft band)
- mock gauss 100 樣本，seed=42
- 量化 4 信號合計修正多少 hard cut 個案

v5.11.3 hard thresholds：
- tech/fund/risk: score > 0.6 → buy, < 0.4 → sell, else neutral
- sentiment: combined > 0.15 → positive, < -0.15 → negative, else neutral

v5.13 P36b soft bands：
- tech/fund/risk: market_signal_from_score(score) → sigmoid
- sentiment: sentiment_signal_from_combined(combined) → tanh
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random

import stock_analysis


def mock_scores_4signal(n=100, seed=42):
    """生成 mock scores 模擬 4 個信號"""
    random.seed(seed)
    out = {"tech": [], "fund": [], "risk": [], "sentiment": []}
    for _ in range(n):
        # 4 個信號都用 gauss(0.5, 0.15) 模擬（sentiment 改成 -1..1）
        out["tech"].append(max(0.0, min(1.0, random.gauss(0.5, 0.15))))
        out["fund"].append(max(0.0, min(1.0, random.gauss(0.5, 0.15))))
        out["risk"].append(max(0.0, min(1.0, random.gauss(0.5, 0.18))))  # risk 波動大
        out["sentiment"].append(max(-1.0, min(1.0, random.gauss(0.0, 0.3))))  # 雙極
    return out


def v511_classify_4signal(name, score):
    """v5.11.3 hard threshold"""
    if name == "sentiment":
        if score > 0.15:
            return "positive"
        elif score < -0.15:
            return "negative"
        else:
            return "neutral"
    else:  # tech/fund/risk
        if score > 0.6:
            return "buy"
        elif score < 0.4:
            return "sell"
        else:
            return "neutral"


def v513_classify_4signal(name, score):
    """v5.13 P36b soft band"""
    if name == "sentiment":
        sig, _, _ = stock_analysis.sentiment_signal_from_combined(score)
        return sig
    else:
        sig, _, _ = stock_analysis.market_signal_from_score(score)
        return sig


def quantify():
    n = 100
    scores = mock_scores_4signal(n=n, seed=42)

    # 統計
    total_diff = 0  # 4 信號合計信號變化個案
    per_signal_diff = {k: 0 for k in ["tech", "fund", "risk", "sentiment"]}
    per_signal_v511_dist = {k: {} for k in ["tech", "fund", "risk", "sentiment"]}
    per_signal_v513_dist = {k: {} for k in ["tech", "fund", "risk", "sentiment"]}

    for name in ["tech", "fund", "risk", "sentiment"]:
        for s in scores[name]:
            v511_sig = v511_classify_4signal(name, s)
            v513_sig = v513_classify_4signal(name, s)
            per_signal_v511_dist[name][v511_sig] = per_signal_v511_dist[name].get(v511_sig, 0) + 1
            per_signal_v513_dist[name][v513_sig] = per_signal_v513_dist[name].get(v513_sig, 0) + 1
            if v511_sig != v513_sig:
                per_signal_diff[name] += 1
                total_diff += 1

    print("=" * 70)
    print("v5.13 P36b — 4 信號連續化 backtest 量化")
    print("=" * 70)
    print(f"條件：n_tickers={n}, seed=42, mock gauss")
    print()
    print("【信號分布對比（v5.11.3 vs v5.13 P36b）】")
    print(f"{'信號':<10} {'v5.11.3':<35} {'v5.13 P36b':<35} {'差異個案':<8}")
    print("-" * 90)
    for name in ["tech", "fund", "risk", "sentiment"]:
        v511_d = per_signal_v511_dist[name]
        v513_d = per_signal_v513_dist[name]
        v511_str = ", ".join(f"{k}:{v}" for k, v in sorted(v511_d.items()))
        v513_str = ", ".join(f"{k}:{v}" for k, v in sorted(v513_d.items()))
        print(f"{name:<10} {v511_str:<35} {v513_str:<35} {per_signal_diff[name]:<8}")
    print()
    print(f"【合計】4 信號總修正 hard cut 個案：{total_diff}/400 ({(total_diff*100/400):.1f}%)")
    print()
    print("=" * 70)
    print("【範例：每個信號的第一個修正個案】")
    print("=" * 70)
    for name in ["tech", "fund", "risk", "sentiment"]:
        for s in scores[name]:
            v511_sig = v511_classify_4signal(name, s)
            v513_sig = v513_classify_4signal(name, s)
            if v511_sig != v513_sig:
                if name == "sentiment":
                    _, strength, conf = stock_analysis.sentiment_signal_from_combined(s)
                else:
                    _, strength, conf = stock_analysis.market_signal_from_score(s)
                print(f"  {name:<10}: score={s:+.4f}, v5.11.3={v511_sig:<8} → v5.13={v513_sig:<8} (strength={strength:.4f}, conf={conf:.4f})")
                break

    return {
        "total_diff": total_diff,
        "per_signal_diff": per_signal_diff,
    }


if __name__ == "__main__":
    result = quantify()
    print()
    print(f"量化結果：v5.13 P36b 修正 {result['total_diff']} 個 hard cut 個案（4 信號合計）")
    print(f"  tech={result['per_signal_diff']['tech']}, fund={result['per_signal_diff']['fund']}, risk={result['per_signal_diff']['risk']}, sentiment={result['per_signal_diff']['sentiment']}")