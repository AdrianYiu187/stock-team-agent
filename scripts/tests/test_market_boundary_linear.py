"""v5.14 P38: market_score_multifactor from_high_pct + ytd_return 邊界線性化 pytest.

目的：守住 market from_high_pct（<-60 邊界）+ ytd_return（<-100 邊界）線性化。

舊版行為（v5.13）：
- from_high <= -60: 1.0  (cap)
- from_high [-60, 0]: 線性 0.5..1.0
- from_high [0, +30]: 線性 0.55..0.65
- from_high > +30: 線性至 0.85 (v5.10 C22 fix)

- ytd <= -100: 0.0  (cap)
- ytd [-100, +200]: 線性 0.0..1.0

新版行為（v5.14 P38）：
- from_high <= -60: 線性 1.0 (fhigh=-60) → 0.5 (fhigh=-200) → clip 0.0
- ytd <= -100: 線性 0.0 (ytd=-100) → clip 0.0 (ytd=-200)

歷史：
- 2026-06-28 created (v5.14 P38)
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import market_score_multifactor


def fh_score(fh):
    """market_score with from_high varying (ytd=20, pos=50, beta=1)."""
    return market_score_multifactor(
        ytd_return=20.0, pos_52wk=50.0,
        from_high_pct=float(fh), beta=1.0,
    )


def ytd_score(ytd):
    """market_score with ytd varying (pos=50, fhigh=-10, beta=1)."""
    return market_score_multifactor(
        ytd_return=float(ytd), pos_52wk=50.0,
        from_high_pct=-10.0, beta=1.0,
    )


class TestP38MarketFromHighContinuous:
    """from_high_pct: [-200, -60] 必須連續線性，不能 cap 1.0。"""

    def test_fh_minus_60_continuous(self):
        """from_high=-60 → dd_factor=1.0 (peak buy, no cap discontinuity)。"""
        s = fh_score(-60)
        # dd_factor=1.0, contributes 0.5
        # pos_factor=0.75 (pos=50), contributes 0.225
        # ytd_factor=0.55 (ytd=20 = (20+200)/400), contributes 0.0825
        # beta_factor=1.0, contributes 0.05
        # Total: 0.5 + 0.225 + 0.0825 + 0.05 = 0.8575
        assert abs(s - 0.8575) < 0.02, f"fhigh=-60 score={s}, expected≈0.8575"

    def test_fh_minus_120_no_cap(self):
        """from_high=-120 (舊 cap 1.0) 不能 flatline，必須繼續線性下降。"""
        s = fh_score(-120)
        # Linear extrapolation: 1.0 - 0.5*(60/140) = 1.0 - 0.214 = 0.786
        # dd_factor contributes 0.393
        s_m60 = fh_score(-60)
        assert s < s_m60, f"fhigh=-120 ({s}) should be < fhigh=-60 ({s_m60})"

    def test_fh_minus_200_floor(self):
        """from_high=-200 應 clip 至合理下限（不能 < 0）。"""
        s = fh_score(-200)
        assert 0.0 <= s <= 1.0
        # Should be lower than fhigh=-60 (severe drawdown)
        s_m60 = fh_score(-60)
        assert s < s_m60

    def test_fh_no_flatline_minus_200_to_minus_60(self):
        """from_high [-200, -60] 不能 flatline。"""
        flat_count = 0
        prev = fh_score(-200)
        for fh in range(-199, -59):
            curr = fh_score(fh)
            if abs(curr - prev) < 1e-9:
                flat_count += 1
            prev = curr
        assert flat_count < 5, f"Too many flat segments in [-200, -60]: {flat_count}"


class TestP38MarketYtdContinuous:
    """ytd_return: [-200, -100] 必須連續線性，不能 cap 0.0。"""

    def test_ytd_minus_100_continuous(self):
        """ytd=-100 → ytd_factor=0.25 (continuous with [-100, +200] branch)。"""
        s = ytd_score(-100)
        # pos=50 → pos_factor=0.75 → 0.225
        # fhigh=-10 → dd_factor=0.583 → 0.292
        # ytd=-100 → ytd_factor=(−100+200)/400=0.25 → 0.0375
        # beta=1.0 → 0.05
        # Total: 0.225 + 0.292 + 0.0375 + 0.05 = 0.6045
        assert abs(s - 0.6045) < 0.02, f"ytd=-100 score={s}, expected≈0.6045"

    def test_ytd_minus_150_no_cap(self):
        """ytd=-150 必須 < ytd=-100（不能 saturate 0.0）。"""
        s = ytd_score(-150)
        s_m100 = ytd_score(-100)
        # At ytd=-150: ytd_factor should clip 0 (or be lower than ytd=-100)
        # score must be < ytd=-100 (lower ytd = worse)
        assert s < s_m100, f"ytd=-150 ({s}) should be < ytd=-100 ({s_m100})"

    def test_ytd_minus_200_floor(self):
        """ytd=-200 應 clip 至 0（嚴重崩盤 = 最低分）。"""
        s = ytd_score(-200)
        assert 0.0 <= s <= 1.0
        assert s <= ytd_score(-100) + 0.01  # 不高於 ytd=-100

    def test_ytd_no_flatline_minus_200_to_minus_100(self):
        """ytd [-200, -100] 不能 flatline。"""
        flat_count = 0
        prev = ytd_score(-200)
        for ytd in range(-199, -99):
            curr = ytd_score(ytd)
            if abs(curr - prev) < 1e-9:
                flat_count += 1
            prev = curr
        assert flat_count < 10, f"Too many flat segments in [-200, -100]: {flat_count}"
