"""
v5.22 P43 — market_score_multifactor.beta_factor 真實 pitfall 修復

量化 (Stage B-0, N=50000 真實分布):
  - market.beta cap=0.7 zone (>1.2): 30.92% 真實樣本落入
  - cap zone 內 std/max = 0.043 (輕微 flat,沒完全 cap 但有 floor 0.7)
  - 真實高 beta 股 (tech/growth) 常見 β=1.5-2.5

Fix: 移除 floor 0.7,改 continuous linear extrapolation:
  beta_factor = clip(1.0 - (beta - 1.0) * 0.4, 0.5, 1.0)
  # beta=1.0 → 1.0 (中性)
  # beta=1.5 → 0.8
  # beta=2.0 → 0.6
  # beta=2.5 → 0.5 (floor 保留避免過度 sell)
"""
import sys
sys.path.insert(0, 'scripts')
import stock_analysis as sa


def test_market_beta_factor_strictly_decreasing_above_1():
    """v5.22 P43: beta > 1 必須 strict decreasing"""
    betas = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5]
    scores = [sa.market_score_multifactor(ytd_return=0.10, pos_52wk=50, from_high_pct=-10, beta=b)
              for b in betas]
    for i in range(len(scores) - 1):
        assert scores[i] > scores[i+1], (
            f"beta 必須 strict decreasing > 1. "
            f"beta={betas[i]} score={scores[i]} → beta={betas[i+1]} score={scores[i+1]}"
        )


def test_market_beta_factor_no_floor_clamp():
    """v5.22 P43: beta=2.0 vs beta=2.5 不能完全相同 (不能 floor clamp)"""
    s2 = sa.market_score_multifactor(ytd_return=0.10, pos_52wk=50, from_high_pct=-10, beta=2.0)
    s25 = sa.market_score_multifactor(ytd_return=0.10, pos_52wk=50, from_high_pct=-10, beta=2.5)
    assert s2 != s25, f"beta=2.0 vs 2.5 same score ({s2}): floor clamp pitfall"


def test_market_beta_factor_continuous_at_1_2():
    """v5.22 P43: beta=1.0 vs 1.2 不能有跳階"""
    s1 = sa.market_score_multifactor(ytd_return=0.10, pos_52wk=50, from_high_pct=-10, beta=1.0)
    s12 = sa.market_score_multifactor(ytd_return=0.10, pos_52wk=50, from_high_pct=-10, beta=1.2)
    diff = abs(s1 - s12)
    assert diff < 0.05, f"beta=1.0→1.2 jump too large: {diff:.4f}"


def test_market_beta_factor_monotone_full_range():
    """v5.22 P43: beta ∈ [0.5, 2.5] 全範圍單調遞減"""
    scores = []
    betas = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5]
    for b in betas:
        s = sa.market_score_multifactor(ytd_return=0.10, pos_52wk=50, from_high_pct=-10, beta=b)
        scores.append(s)
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i+1], (
            f"beta must monotonically decrease. "
            f"beta={betas[i]} score={scores[i]} → beta={betas[i+1]} score={scores[i+1]}"
        )
