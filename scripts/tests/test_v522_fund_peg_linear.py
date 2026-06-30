"""
v5.22 P42 — fund_score_multifactor.peg_factor 真實 pitfall 修復

量化 (Stage B-0, N=50000 真實分布):
  - fund.peg cap=0.10 zone (>5): 8.19% 真實樣本落入
  - cap zone 內 std/max = 0.000 (完全 flat)
  - PEG > 5 在 biotech/distressed 股是常態 (例: TSLA, GROW)

Fix: 移除 cap,改 continuous exponential decay:
  peg > 5 → peg_factor = 0.10 * exp(-(peg-5)/10)  # 5→0.10, 15→0.037
  不再硬切 0.10 floor,但仍保證 PEG>5 始終低於 PEG=5
"""
import sys
sys.path.insert(0, 'scripts')
import stock_analysis as sa


def test_fund_peg_factor_strictly_decreasing_above_5():
    """v5.22 P42: PEG > 5 必須 strict decreasing, 不能 flat"""
    peg_values = [5, 6, 8, 10, 15, 20]
    scores = []
    for peg in peg_values:
        s = sa.fund_score_multifactor(pe=20.0, roe=0.15, peg_val=peg, revenue_growth=0.10)
        scores.append(s)
    for i in range(len(scores) - 1):
        assert scores[i] > scores[i+1], (
            f"PEG > 5 must strict decreasing. "
            f"PEG={peg_values[i]} score={scores[i]} → PEG={peg_values[i+1]} score={scores[i+1]} (flat!)"
        )


def test_fund_peg_factor_no_flat_zone():
    """v5.22 P42: PEG=6, 8, 10, 15 不能完全相同"""
    peg_values = [6, 8, 10, 15]
    scores = [sa.fund_score_multifactor(pe=20.0, roe=0.15, peg_val=p, revenue_growth=0.10)
              for p in peg_values]
    unique = len(set(scores))
    assert unique >= 4, f"Expected 4 distinct scores, got {unique}: {scores}"


def test_fund_peg_factor_continuous_at_boundary():
    """v5.22 P42: PEG=5 vs PEG=5.001 必須連續 (no jump)"""
    s5 = sa.fund_score_multifactor(pe=20.0, roe=0.15, peg_val=5.0, revenue_growth=0.10)
    s5_plus = sa.fund_score_multifactor(pe=20.0, roe=0.15, peg_val=5.5, revenue_growth=0.10)
    diff = abs(s5 - s5_plus)
    assert diff < 0.10, f"PEG=5→5.5 jump too large: {diff:.4f}"


def test_fund_peg_factor_lower_bound_strict():
    """v5.22 P42: PEG > 5 不能低於 PEG = 5 太多 (保留 '高 PEG = sell' 語義)"""
    s5 = sa.fund_score_multifactor(pe=20.0, roe=0.15, peg_val=5.0, revenue_growth=0.10)
    s20 = sa.fund_score_multifactor(pe=20.0, roe=0.15, peg_val=20.0, revenue_growth=0.10)
    assert s20 <= s5, f"PEG=20 score ({s20}) 應該 ≤ PEG=5 ({s5})"
