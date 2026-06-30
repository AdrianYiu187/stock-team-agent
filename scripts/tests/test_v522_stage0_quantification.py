"""
v5.22 Stage 0 pytest guard: 鎖定 tech_score_multifactor 的 ma50 flat pitfall

這個 test 在 v5.22 量化時**應該 FAIL** (regression guard):
  tech.ma50_factor ratio-based 設計導致 ma50=50,100,150 → 完全相同 score

Stage 0 fix (Pitfall P41) 後改成 PASS:
  ma50_score_50 != ma50_score_100 != ma50_score_150

這個 test 是 baseline guard — protect from future regression
"""
import sys
sys.path.insert(0, 'scripts')
import stock_analysis as sa


def test_tech_ma50_factor_not_flat_at_50_100_150():
    """v5.22 P41 regression guard: ma50=50/100/150 必須連續 (不平坦)"""
    score_50 = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=50.0, momentum_20d=0.05)
    score_100 = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=100.0, momentum_20d=0.05)
    score_150 = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=150.0, momentum_20d=0.05)
    # 三值必須 distinct
    assert score_50 != score_100, f"ma50=50 ({score_50}) == ma50=100 ({score_100}) flat!"
    assert score_100 != score_150, f"ma50=100 ({score_100}) == ma50=150 ({score_150}) flat!"
    assert score_50 != score_150, f"ma50=50 ({score_50}) == ma50=150 ({score_150}) flat!"


def test_tech_ma50_factor_strictly_monotone_when_below_price():
    """v5.22 P41: ma50 < price 時, ma50 越大 → score 越低 (sell-side trend)"""
    scores = []
    for ma50 in [50, 100, 150, 180, 195]:
        s = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=ma50, momentum_20d=0.05)
        scores.append(s)
    # 嚴格遞減
    for i in range(len(scores) - 1):
        assert scores[i] > scores[i+1], (
            f"ma50 increasing at fixed price should decrease score. "
            f"Got {scores[i]} → {scores[i+1]} (non-monotone)"
        )


def test_tech_ma50_factor_non_zero_sensitivity():
    """v5.22 P41: ma50 變化 ±20% → score 變化 > 0.001 (sensitivity check)"""
    base = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=200.0, momentum_20d=0.05)
    lower = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=160.0, momentum_20d=0.05)
    upper = sa.tech_score_multifactor(rsi=50, macd_val=0, price=200.0, ma50=240.0, momentum_20d=0.05)
    delta_lower = abs(base - lower)
    delta_upper = abs(base - upper)
    assert delta_lower > 0.001, f"ma50 -20% sensitivity too low: {delta_lower:.6f}"
    assert delta_upper > 0.001, f"ma50 +20% sensitivity too low: {delta_upper:.6f}"
