"""
v5.13 P36c-5tier: score_to_5tier_with_confidence - dual return (tier, confidence)

Pitfall P36c-5tier Rule 6: v5.11 N14 already fixed ±15/±5 boundaries — 5 tiers
distribute healthily (15-27% each), no hard-cap saturation. User chose B:
add score_to_5tier_with_confidence (dual return), preserve score_to_5tier
behavior unchanged (backward compat + Check 2 verifier).

Design:
- score_to_5tier(overall) -> tier  (UNCHANGED, integer 1-5)
- score_to_5tier_with_confidence(overall) -> (tier, confidence in [0.5, 1.0])
  - Boundary (just crossed): confidence = 0.5
  - Tier center: confidence = 1.0
  - Saturated (>30 or <-30): confidence = 1.0
"""
import sys
import os
import pytest

# Path setup: scripts/ subdir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.stock_analysis import (
    score_to_5tier,
    score_to_5tier_with_confidence,
)


class TestScoreTo5TierWithConfidenceBackwardCompat:
    """Verify score_to_5tier unchanged — Check 2 verifier still PASS."""

    def test_original_function_unchanged_strong_buy(self):
        """overall=15 still returns 5."""
        assert score_to_5tier(15) == 5

    def test_original_function_unchanged_strong_sell(self):
        """overall=-20 still returns 1."""
        assert score_to_5tier(-20) == 1

    def test_original_function_unchanged_hold(self):
        """overall=0 still returns 3 (HOLD center)."""
        assert score_to_5tier(0) == 3

    def test_original_function_unchanged_buy(self):
        """overall=10 still returns 4 (BUY)."""
        assert score_to_5tier(10) == 4


class TestScoreTo5TierWithConfidenceBoundaryConfidence:
    """At tier boundaries, confidence = 0.5 (just crossed)."""

    def test_boundary_strong_buy(self):
        """overall=15: tier=5, confidence=0.5 (just entered STRONG_BUY)."""
        tier, conf = score_to_5tier_with_confidence(15)
        assert tier == 5
        assert conf == 0.5

    def test_boundary_strong_sell(self):
        """overall=-15: tier=2 (SELL, just crossed SELL boundary), confidence=0.5.

        Note: STRONG_SELL (tier=1) boundary is < -15 (not == -15).
        score_to_5tier(-15) returns 2 because -15 still >= -15 (v5.11 N14 logic).
        """
        tier, conf = score_to_5tier_with_confidence(-15)
        assert tier == 2
        assert conf == 0.5

    def test_boundary_buy(self):
        """overall=5: tier=4, confidence=0.5 (just entered BUY)."""
        tier, conf = score_to_5tier_with_confidence(5)
        assert tier == 4
        assert conf == 0.5

    def test_boundary_hold_upper(self):
        """overall=-5: tier=3, confidence=0.5 (HOLD upper edge)."""
        tier, conf = score_to_5tier_with_confidence(-5)
        assert tier == 3
        assert conf == 0.5


class TestScoreTo5TierWithConfidenceCenterConfidence:
    """At tier centers, confidence = 1.0 (most stable)."""

    def test_center_hold(self):
        """overall=0: tier=3, confidence=1.0 (HOLD center)."""
        tier, conf = score_to_5tier_with_confidence(0)
        assert tier == 3
        assert conf == 1.0

    def test_center_buy(self):
        """overall=10: tier=4, confidence=1.0 (BUY center)."""
        tier, conf = score_to_5tier_with_confidence(10)
        assert tier == 4
        assert conf == 1.0

    def test_center_sell(self):
        """overall=-10: tier=2, confidence=1.0 (SELL center)."""
        tier, conf = score_to_5tier_with_confidence(-10)
        assert tier == 2
        assert conf == 1.0


class TestScoreTo5TierWithConfidenceSaturation:
    """Far from center, confidence saturates at 1.0."""

    def test_saturation_strong_buy(self):
        """overall=30: tier=5, confidence=1.0."""
        tier, conf = score_to_5tier_with_confidence(30)
        assert tier == 5
        assert conf == 1.0

    def test_saturation_strong_sell(self):
        """overall=-30: tier=1, confidence=1.0."""
        tier, conf = score_to_5tier_with_confidence(-30)
        assert tier == 1
        assert conf == 1.0


class TestScoreTo5TierWithConfidenceSymmetry:
    """±overall should produce symmetric (tier, conf) — score sign symmetry."""

    def test_symmetric_strong(self):
        """overall=25 vs overall=-25: tier symmetric, conf same."""
        t1, c1 = score_to_5tier_with_confidence(25)
        t2, c2 = score_to_5tier_with_confidence(-25)
        assert t1 == 5
        assert t2 == 1
        assert c1 == c2  # symmetric confidence

    def test_symmetric_buy_sell(self):
        """overall=8 vs overall=-8: tier 4 vs 2, conf same."""
        t1, c1 = score_to_5tier_with_confidence(8)
        t2, c2 = score_to_5tier_with_confidence(-8)
        assert t1 == 4
        assert t2 == 2
        assert c1 == c2


class TestScoreTo5TierWithConfidenceMonotonic:
    """Within a tier, confidence should monotonically increase from boundary to center."""

    def test_monotonic_in_buy_tier(self):
        """overall=5 (boundary), 7, 10 (center): conf 0.5 < x < 1.0 < y."""
        _, c5 = score_to_5tier_with_confidence(5)
        _, c7 = score_to_5tier_with_confidence(7)
        _, c10 = score_to_5tier_with_confidence(10)
        assert c5 < c7 < c10
        assert c5 == 0.5
        assert c10 == 1.0

    def test_monotonic_in_hold_tier(self):
        """overall=-5 (boundary), -2.5, 0 (center): conf 0.5 < x < 1.0."""
        _, c_neg5 = score_to_5tier_with_confidence(-5)
        _, c_neg25 = score_to_5tier_with_confidence(-2.5)
        _, c0 = score_to_5tier_with_confidence(0)
        assert c_neg5 < c_neg25 < c0
        assert c_neg5 == 0.5
        assert c0 == 1.0