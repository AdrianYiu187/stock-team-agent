"""v5.15 P43 + P44: news_score_multifactor cap 線性延伸 pytest。

P43: region_count ≥3 cap 0.95 → 線性延伸到 ≥5
  - region_count=3,4 → 連續（舊版 cap 0.95）
  - region_count=5+ → 0.95 cap（保留保護）
P44: source_diversity ≥6 cap 0.95 → 線性延伸到 ≥12
  - source_diversity=6..11 → 連續（舊版 cap 0.95）
  - source_diversity=12+ → 0.95 cap（保留保護）

成功標準（Rule 4）：
  1. P43: region_count=4 > region_count=3（線性延伸）
  2. P43: region_count=5 ≥ region_count=4（繼續線性）
  3. P43: region_count=10 = 0.95 cap
  4. P44: source_diversity=8 > source_diversity=6（線性延伸）
  5. P44: source_diversity=12 = 0.95 cap
  6. P44: source_diversity=20 = 0.95 cap
  7. 3 個因子都增加時 score 同步上升
  8. news_count≥120 cap 保留（v5.15 P41 不動）
  9. region_count=0/1 邊界不崩潰
 10. source_diversity=0/1 邊界不崩潰
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import news_score_multifactor  # noqa: E402


class TestNewsScoreV515Linear:
    """v5.15 P43 + P44: region_count / source_diversity cap 線性延伸。"""

    def test_01_p43_region4_greater_than_region3(self):
        """P43: region_count=4 > region_count=3（v5.14 兩者都 =0.95 cap）。"""
        s3 = news_score_multifactor(news_count=60, region_count=3, source_diversity=3)
        s4 = news_score_multifactor(news_count=60, region_count=4, source_diversity=3)
        assert s4 > s3, f"region=4 ({s4}) 應 > region=3 ({s3})"

    def test_02_p43_region5_greater_than_region4(self):
        """P43: region_count=5 > region_count=4（繼續線性延伸）。"""
        s4 = news_score_multifactor(news_count=60, region_count=4, source_diversity=3)
        s5 = news_score_multifactor(news_count=60, region_count=5, source_diversity=3)
        assert s5 > s4, f"region=5 ({s5}) 應 > region=4 ({s4})"

    def test_03_p43_region10_cap_at_095(self):
        """P43: region_count≥10 達到 0.95 cap（保留保護）。"""
        s10 = news_score_multifactor(news_count=60, region_count=10, source_diversity=3)
        # v5.15 P43: rc=10 cap=0.95; nc=60 → 0.95*60/120=0.475; sd=3 → 0.30+0.65*2/11=0.418
        # score = 0.475*0.5 + 0.95*0.3 + 0.418*0.2 = 0.2375 + 0.285 + 0.0836 = 0.6061
        assert 0.60 <= s10 <= 0.61, f"region=10 預期 ~0.606, got {s10}"

    def test_04_p44_source8_greater_than_source6(self):
        """P44: source_diversity=8 > source_diversity=6（v5.14 兩者都 =0.95 cap）。"""
        s6 = news_score_multifactor(news_count=60, region_count=2, source_diversity=6)
        s8 = news_score_multifactor(news_count=60, region_count=2, source_diversity=8)
        assert s8 > s6, f"sd=8 ({s8}) 應 > sd=6 ({s6})"

    def test_05_p44_source12_cap_at_095(self):
        """P44: source_diversity≥12 達到 0.95 cap（保留保護）。"""
        s12 = news_score_multifactor(news_count=60, region_count=2, source_diversity=12)
        # v5.15 P44: sd=12 cap=0.95; nc=60 → 0.475; rc=2 → 0.30+0.65*2/5=0.56
        # score = 0.475*0.5 + 0.56*0.3 + 0.95*0.2 = 0.2375 + 0.168 + 0.19 = 0.5955
        assert 0.59 <= s12 <= 0.60, f"sd=12 預期 ~0.5955, got {s12}"

    def test_06_p44_source20_still_cap(self):
        """P44: source_diversity=20 仍 = cap（保護極端輸入）。"""
        s12 = news_score_multifactor(news_count=60, region_count=2, source_diversity=12)
        s20 = news_score_multifactor(news_count=60, region_count=2, source_diversity=20)
        assert abs(s20 - s12) < 1e-9, f"sd=20 ({s20}) 應 = sd=12 ({s12})"

    def test_07_all_three_factors_monotonic(self):
        """3 個因子同時增加 → score 上升。"""
        s_low = news_score_multifactor(news_count=10, region_count=1, source_diversity=2)
        s_high = news_score_multifactor(news_count=80, region_count=4, source_diversity=9)
        assert s_high > s_low, f"low ({s_low}) 應 < high ({s_high})"

    def test_08_news_count_cap_preserved(self):
        """P41 不動：news_count≥120 仍 cap 0.95。"""
        s120 = news_score_multifactor(news_count=120, region_count=1, source_diversity=2)
        s500 = news_score_multifactor(news_count=500, region_count=1, source_diversity=2)
        # nc≥120 cap=0.95; rc=1 → 0.30+0.65/3 = 0.517; sd=2 → 0.30+0.65/5 = 0.43
        # score = 0.95*0.5 + 0.517*0.3 + 0.43*0.2 = 0.475 + 0.155 + 0.086 = 0.716
        assert abs(s120 - s500) < 1e-9, f"nc=120 ({s120}) 應 = nc=500 ({s500})"

    def test_09_region_zero_safe(self):
        """region_count=0 邊界不崩潰（v5.14 已經處理，v5.15 保留）。"""
        s = news_score_multifactor(news_count=60, region_count=0, source_diversity=3)
        assert 0.0 <= s <= 1.0, f"region=0 應在 [0,1], got {s}"

    def test_10_source_zero_safe(self):
        """source_diversity=0 邊界不崩潰（v5.14 已經處理，v5.15 保留）。"""
        s = news_score_multifactor(news_count=60, region_count=2, source_diversity=0)
        assert 0.0 <= s <= 1.0, f"sd=0 應在 [0,1], got {s}"
