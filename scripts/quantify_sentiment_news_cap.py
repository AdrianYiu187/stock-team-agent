"""
v5.15 候選 audit：sentiment_score_multifactor + news_score_multifactor 的真實 cap flatline。

目標：找出 v5.14 後剩餘的真實 cap flatline，作為 v5.15 P41-P44 候選。

已知 cap：
- sentiment_score_multifactor (v5.12 P34): news_count ≥120 → nc_factor = 0.95 cap
- news_score_multifactor (v5.12 P33): 3 個 cap（news_count≥120 / region_count≥3 / source_diversity≥6 → 0.95）

設計：mock 1000 ticker × 5 score points 的極端輸入，量化真實 flat rate。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stock_analysis import sentiment_score_multifactor, news_score_multifactor


def quantify_sentiment_cap() -> dict:
    """量化 sentiment_score_multifactor 的 news_count cap。"""
    n_samples = 1000
    cap_count = 0
    all_scores = []

    # 模擬 news_count 真實分布（多數 0-50，少數 100+）
    import random
    rng = random.Random(42)
    for _ in range(n_samples):
        # 真實分布：p(0-30)=0.5, p(30-60)=0.3, p(60-120)=0.15, p(120+)=0.05
        r = rng.random()
        if r < 0.5:
            news_count = rng.randint(0, 30)
        elif r < 0.8:
            news_count = rng.randint(30, 60)
        elif r < 0.95:
            news_count = rng.randint(60, 120)
        else:
            news_count = rng.randint(120, 200)

        score = sentiment_score_multifactor(
            combined_score=0.0,
            confidence=0.5,
            news_count=news_count,
        )
        all_scores.append(score)
        if score >= 0.949:  # nc_factor = 0.95 的標誌（其他因子 0.5+0.5*0.5=0.5）
            cap_count += 1

    return {
        "function": "sentiment_score_multifactor",
        "n_samples": n_samples,
        "cap_count": cap_count,
        "cap_rate": cap_count / n_samples,
        "mean_score": sum(all_scores) / n_samples,
    }


def quantify_news_caps() -> dict:
    """量化 news_score_multifactor 的 3 個 cap。"""
    n_samples = 1000
    all_scores = []
    cap_news_count = 0
    cap_region = 0
    cap_source = 0

    import random
    rng = random.Random(42)

    # 真實分布：news_count [0, 200], region [0, 5], source [1, 10]
    for _ in range(n_samples):
        r = rng.random()
        if r < 0.5:
            news_count = rng.randint(0, 50)
        elif r < 0.85:
            news_count = rng.randint(50, 120)
        else:
            news_count = rng.randint(120, 250)

        region_count = rng.choice([0, 1, 2, 3, 4, 5])
        source_diversity = rng.randint(1, 12)

        score = news_score_multifactor(news_count, region_count, source_diversity)
        all_scores.append(score)

        if news_count >= 120:
            cap_news_count += 1
        # v5.15 P43: region_count cap 從 ≥3 延伸到 ≥5
        if region_count >= 5:
            cap_region += 1
        # v5.15 P44: source_diversity cap 從 ≥6 延伸到 ≥12
        if source_diversity >= 12:
            cap_source += 1

    return {
        "function": "news_score_multifactor",
        "n_samples": n_samples,
        "cap_news_count_rate": cap_news_count / n_samples,
        "cap_region_rate": cap_region / n_samples,
        "cap_source_rate": cap_source / n_samples,
        "mean_score": sum(all_scores) / n_samples,
    }


def main() -> None:
    print("=" * 70)
    print("v5.15 候選 audit：sentiment + news 真實 cap flatline")
    print("=" * 70)

    print("\n[1] sentiment_score_multifactor (v5.12 P34)")
    res = quantify_sentiment_cap()
    print(f"  n={res['n_samples']}, mean={res['mean_score']:.3f}")
    print(f"  news_count ≥120 cap rate: {res['cap_rate']*100:.1f}%")

    print("\n[2] news_score_multifactor (v5.12 P33)")
    res = quantify_news_caps()
    print(f"  n={res['n_samples']}, mean={res['mean_score']:.3f}")
    print(f"  cap rates: news_count={res['cap_news_count_rate']*100:.1f}%, "
          f"region={res['cap_region_rate']*100:.1f}%, "
          f"source={res['cap_source_rate']*100:.1f}%")

    print("\n" + "=" * 70)
    print("v5.15 候選 pitfall:")
    print("  P41: sentiment news_count ≥120 cap → nc_factor 線性延伸到 200+")
    print("  P42: news news_count ≥120 cap → nc_factor 線性延伸到 200+")
    print("  P43: news region_count ≥3 cap → rc_factor 線性延伸到 5+")
    print("  P44: news source_diversity ≥6 cap → sd_factor 線性延伸到 12+")
    print()
    print("注：cap 設計原意是『極端覆蓋不再加分』，但若真實分布常落入 cap zone")
    print("    → 訊號飽和幻覺（與 v5.14 P37-P40 同病）。建議線性化但保留最終飽和 0.99")
    print("=" * 70)


if __name__ == "__main__":
    main()
