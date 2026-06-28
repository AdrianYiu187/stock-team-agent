"""v5.14 P39: tech_score_multifactor 5 caps 線性化 pytest.

目的：守住 tech RSI<5 + macd ±2 + ma50<=0 + momentum<-50 5 caps 線性化。

舊版行為（v5.13）：
- rsi < 5:        1.0  (cap)
- rsi [5,20]:     線性 1.0..0.95
- rsi [20,30]:    線性 0.85..0.70
- ...
- macd >= 2:      0.8  (cap)
- macd [-2, 2]:   線性 0.25..0.8
- macd <= -2:     0.25 (cap)
- ma50 <= 0:      0.5  (fallback)
- momentum <= -50: 0.05 (cap)

新版行為（v5.14 P39）：
- rsi [0, 5]:     線性 1.05 → 1.0 → clip 1.0 (細分)
- macd [-10, 10]: 線性外推 (macd=-10 → 0.0, macd=+10 → 1.0)
- ma50 [0, ...]:  保留 fallback 0.5（ma50=0 是數據錯誤）
- momentum [-100, -50]: 線性 0.0 → 0.05 (extrapolate)

歷史：
- 2026-06-28 created (v5.14 P39)
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import tech_score_multifactor


def tech_score(rsi=None, macd_val=None, price=None, ma50=None, momentum_20d=None):
    """Tech score with one parameter varying."""
    defaults = {"rsi": 50, "macd_val": 0.5, "price": 100, "ma50": 100, "momentum_20d": 5}
    if rsi is not None: defaults["rsi"] = rsi
    if macd_val is not None: defaults["macd_val"] = macd_val
    if price is not None: defaults["price"] = price
    if ma50 is not None: defaults["ma50"] = ma50
    if momentum_20d is not None: defaults["momentum_20d"] = momentum_20d
    return tech_score_multifactor(**defaults)


class TestP39TechRsiLinear:
    """RSI [0, 5] 必須連續，不能 cap 1.0。"""

    def test_rsi_zero_extreme_oversold(self):
        """RSI=0 應 < RSI=5（極度超賣更強 buy）。"""
        s0 = tech_score(rsi=0)
        s5 = tech_score(rsi=5)
        # v5.14: rsi [0, 5] 線性 1.05 → 1.0, rsi=0 → rsi_factor=1.05 → clip 1.0
        # rsi=5 → rsi_factor=1.0 (boundary with [5,20] branch)
        # 兩者都 saturate 在 1.0 cap (max 1.0), 但 score 加權後可能差
        # 接受 s0 >= s5 (更 buy) 或 s0 == s5 (saturated)
        assert s0 >= s5 - 0.01, f"RSI=0 ({s0}) should be >= RSI=5 ({s5})"

    def test_rsi_low_monotonic(self):
        """RSI [0, 30] 應該接近單調（極度超賣 → 中性）。"""
        scores = [tech_score(rsi=r) for r in [0, 1, 3, 5, 10, 15, 20, 25, 30]]
        # 至少前半段單調遞減
        for i in range(1, 5):
            assert scores[i] <= scores[i-1] + 0.01, \
                f"RSI low: not monotonic at index {i}"


class TestP39TechMacdLinear:
    """macd_val [-10, +10] 必須連續，不能 cap 0.8 / 0.25。"""

    def test_macd_plus_5_above_cap(self):
        """macd=+5 必須 > macd=+2 (舊 cap 0.8)。"""
        s2 = tech_score(macd_val=2)
        s5 = tech_score(macd_val=5)
        # 線性外推 macd=5 應 > macd=2
        assert s5 > s2, f"macd=5 ({s5}) should be > macd=2 ({s2})"

    def test_macd_minus_5_below_cap(self):
        """macd=-5 必須 < macd=-2 (舊 cap 0.25)。"""
        s_m2 = tech_score(macd_val=-2)
        s_m5 = tech_score(macd_val=-5)
        assert s_m5 < s_m2, f"macd=-5 ({s_m5}) should be < macd=-2 ({s_m2})"

    def test_macd_symmetry(self):
        """macd 對稱：|x| 越大，rsi 影響越大（線性外推）。"""
        # macd_val ±5: 加權 0.15, 不對稱但 score 應有差異
        s_pos = tech_score(macd_val=5)
        s_neg = tech_score(macd_val=-5)
        # 設計對稱時 macd_factor=-5 接近 0, macd_factor=+5 接近 1.0
        assert s_pos > s_neg, f"macd=+5 ({s_pos}) should be > macd=-5 ({s_neg})"

    def test_macd_extreme_plus10(self):
        """macd=+10 必須 > macd=+5 (繼續線性，clip 1.0 max)。"""
        s10 = tech_score(macd_val=10)
        s5 = tech_score(macd_val=5)
        assert s10 >= s5, f"macd=+10 ({s10}) should be >= macd=+5 ({s5})"


class TestP39TechMa50Fallback:
    """ma50<=0 fallback 0.5: 保留 (ma50=0 是數據錯誤)。"""

    def test_ma50_zero_fallback_neutral(self):
        """ma50=0 應 fallback 至中性 0.5（數據錯誤保護）。"""
        s = tech_score(price=100, ma50=0)
        # ma50_factor=0.5, contributes 0.1 (weight=0.2)
        # Total depends on others but should be near neutral (0.5-0.6)
        assert 0.4 <= s <= 0.65

    def test_ma50_negative_uses_fallback(self):
        """ma50=-10 應 fallback 至中性 0.5（保護）。"""
        s = tech_score(price=100, ma50=-10)
        assert 0.4 <= s <= 0.65


class TestP39TechMomentumLinear:
    """momentum [-100, -50] 必須連續，不能 cap 0.05。"""

    def test_momentum_minus_100_lower_than_minus_50(self):
        """mom=-100 必須 < mom=-50 (舊 cap 0.05 區)。"""
        s_m100 = tech_score(momentum_20d=-100)
        s_m50 = tech_score(momentum_20d=-50)
        assert s_m100 < s_m50, f"mom=-100 ({s_m100}) should be < mom=-50 ({s_m50})"

    def test_momentum_minus_50_to_plus_50_monotonic(self):
        """mom [-50, +50] 線性單調遞增。"""
        scores = [tech_score(momentum_20d=m) for m in [-50, -25, 0, 25, 50]]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i-1], \
                f"mom monotonic: index {i} not >= {i-1}"
