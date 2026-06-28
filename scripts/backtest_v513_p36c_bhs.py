"""
v5.13 P36c-bhs 量化腳本：score_to_bhs 連續化改善

對比：
- v5.11.3: score_to_bhs 線性硬切，score=0.5 完美中性 (0, 1, 0)
- v5.13 P36c-bhs: sigmoid soft band，score=0.5 三等分 (1/3, 1/3, 1/3)

設計：mock 100 ticker × 21 score points (0.0..1.0 step 0.05)
統計 v5.11.3 vs v5.13 P36c-bhs 在 hold 比例 / buy/sell 分布的差異
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import random
from stock_analysis import score_to_bhs


def v513_score_to_bhs(score: float) -> dict:
    """v5.11.3 舊版：score_to_bhs 線性硬切（mock 用）。"""
    score = max(0.0, min(1.0, float(score)))
    if score >= 0.5:
        buy = (score - 0.5) * 2
        hold = 1.0 - buy
        sell = 0.0
    else:
        sell = (0.5 - score) * 2
        hold = 1.0 - sell
        buy = 0.0
    return {"buy": buy, "hold": hold, "sell": sell}


def main() -> None:
    random.seed(42)
    n_tickers = 100
    n_scores = 21  # 0.0, 0.05, ..., 1.0

    # 為每個 ticker 隨機選一個 score（模擬真實場景）
    v513_total_hold = 0.0
    v513_total_buy = 0.0
    v513_total_sell = 0.0
    v513_n_hold_dominant = 0  # hold > 0.5

    v513_total_hold = 0.0
    v513_p36c_total_hold = 0.0
    v513_p36c_n_hold_dominant = 0

    print(f"=== v5.13 P36c-bhs 量化（mock {n_tickers} ticker × {n_scores} score）===\n")

    for ticker_id in range(n_tickers):
        # 每個 ticker 用固定分布（mock 實際 score 在 [0.3, 0.7] 中段）
        # 這樣可看出硬切的影響（中段 0.3-0.7 大部分被舊版歸類為 hold）
        score = random.uniform(0.0, 1.0)
        r_v513 = v513_score_to_bhs(score)
        r_p36c = score_to_bhs(score)
        v513_total_hold += r_v513["hold"]
        v513_total_buy += r_v513["buy"]
        v513_total_sell += r_v513["sell"]
        v513_p36c_total_hold += r_p36c["hold"]
        if r_v513["hold"] > 0.5:
            v513_n_hold_dominant += 1
        if r_p36c["hold"] > 0.5:
            v513_p36c_n_hold_dominant += 1

    print(f"=== v5.11.3 (硬切) ===")
    print(f"avg hold={v513_total_hold/n_tickers:.3f}, buy={v513_total_buy/n_tickers:.3f}, sell={v513_total_sell/n_tickers:.3f}")
    print(f"hold-dominant (>0.5): {v513_n_hold_dominant}/{n_tickers} ({100*v513_n_hold_dominant/n_tickers:.1f}%)")
    print()
    print(f"=== v5.13 P36c-bhs (sigmoid) ===")
    print(f"avg hold={v513_p36c_total_hold/n_tickers:.3f}")
    print(f"hold-dominant (>0.5): {v513_p36c_n_hold_dominant}/{n_tickers} ({100*v513_p36c_n_hold_dominant/n_tickers:.1f}%)")
    print()
    print(f"=== 改善 ===")
    delta_hold_dominant = v513_n_hold_dominant - v513_p36c_n_hold_dominant
    print(f"hold-dominant 個案: {v513_n_hold_dominant} → {v513_p36c_n_hold_dominant} (修正 {delta_hold_dominant}/{n_tickers}, {100*delta_hold_dominant/n_tickers:.1f}%)")
    print(f"avg hold 下降: {v513_total_hold/n_tickers - v513_p36c_total_hold/n_tickers:+.3f}")


if __name__ == "__main__":
    main()
