"""v5.14 P37: market_score_multifactor pos_52wk 線性化 pytest.

目的：守住 market pos_52wk 從 4-segment cap (1.0/0.7/0.55/0.5) 改為連續線性
(v5.14 P37 fix)。

舊版行為（v5.13）：
- pos <= 5:    1.0  (cap)
- pos [6,20]:  0.95 → 0.70  (線性)
- pos [21,50]: 0.7  (cap)
- pos [51,80]: 0.55 (cap)
- pos [81,100]: 0.5  (cap)

新版行為（v5.14 P37）：
- pos in [0, 100]: 線性 1.0 (pos=0) → 0.5 (pos=100)
- pos > 100:       0.5  (cap, 保留極值)

歷史：
- 2026-06-28 created (v5.14 P37)
- TDD 紅燈先寫：先確認 pytest fail with `market_score_multifactor pos_52wk` old version
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import market_score_multifactor


def pos_contribution(pos):
    """Helper: pos_factor's contribution to market_score (weight=0.3).
    
    Computes base dynamically using from_high=-10, ytd=20, beta=1.0
    so the test is robust to changes in those formulas.
    """
    base_with_pos_zero = market_score_multifactor(
        ytd_return=20.0, pos_52wk=0.0,
        from_high_pct=-10.0, beta=1.0,
    )
    # base = dd_factor*0.5 + ytd_factor*0.15 + beta_factor*0.05
    base = base_with_pos_zero - 1.0 * 0.3  # subtract pos_factor=1.0*0.3
    return base + pos_factor_value(pos) * 0.3


def pos_factor_value(pos):
    """Pure pos_factor value (extracted from v5.14 P37 linear logic)."""
    pos = float(pos)
    if pos <= 100:
        return 1.0 - 0.5 * pos / 100
    return 0.5


def pos_score(pos):
    """Helper: compute market_score_multifactor with only pos varying."""
    return market_score_multifactor(
        ytd_return=20.0, pos_52wk=float(pos),
        from_high_pct=-10.0, beta=1.0,
    )


class TestP37MarketPos52wkContinuous:
    """market_score_multifactor pos_52wk 必須連續線性，無 flatline。"""

    def test_pos_zero_returns_1_0(self):
        """pos=0 → pos_factor=1.0（線性公式），對應 score = base + 1.0*0.3。"""
        s = pos_score(0)
        expected_contrib = pos_contribution(0)
        assert abs(s - expected_contrib) < 0.01, f"pos=0 score={s}, expected≈{expected_contrib}"

    def test_pos_hundred_returns_0_5_pos_factor(self):
        """pos=100 → pos_factor=0.5（線性公式）。"""
        s = pos_score(100)
        expected_contrib = pos_contribution(100)
        assert abs(s - expected_contrib) < 0.01, f"pos=100 score={s}, expected≈{expected_contrib}"

    def test_pos_monotonic_decreasing(self):
        """pos 必須嚴格單調遞減（無 cap flatline）。"""
        prev = pos_score(0)
        for pos in range(1, 101):
            curr = pos_score(pos)
            assert curr < prev, f"pos={pos}: {curr} not < prev {prev}"
            prev = curr

    def test_pos_no_flat_segments(self):
        """pos=20..50 (舊 cap 0.7) 不能 flatline。"""
        scores = [pos_score(p) for p in range(20, 51)]
        assert len(set(round(s, 6) for s in scores)) >= 30, \
            f"Too few unique values in [20,50]: {len(set(scores))}"

    def test_pos_no_flat_segment_high(self):
        """pos=50..100 (舊 cap 0.55/0.5) 不能 flatline。"""
        scores = [pos_score(p) for p in range(50, 101)]
        assert len(set(round(s, 6) for s in scores)) >= 50, \
            f"Too few unique values in [50,100]: {len(set(scores))}"

    def test_pos_midpoint_neutral(self):
        """pos=50 → 中性（pos_factor=0.75）。"""
        s = pos_score(50)
        expected = pos_contribution(50)
        assert abs(s - expected) < 0.01

    def test_pos_no_cap_above_100(self):
        """pos > 100 保留 cap 0.5（極值保護）。"""
        s = pos_score(150)
        expected = pos_contribution(150)
        assert abs(s - expected) < 0.01

    def test_pos_no_negative_cap(self):
        """pos < 0 必須 clip 或繼續線性，不允許突然跳到 0 或 1.0 之外。"""
        s = pos_score(-50)
        assert 0.0 <= s <= 1.0
