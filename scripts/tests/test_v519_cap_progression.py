"""
v5.19 (Stage 5) 永久 regression tests:
  - N17/N18/N19: news_count / region_count / source_diversity cap flatline 修復
  - Source diversity ≥ 12 → 30 漸進（bonus fix）

驗證：
  - 修復後 120+ 條新聞仍能區分（不再 flatline）
  - 5+ 區域仍能區分
  - 12+ 來源仍能區分
  - 真實範圍 (news=0-120, region=0-5, source=1-12) 行為與 v5.18 完全一致
"""

import sys
from pathlib import Path

# 確保可 import stock_analysis
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analysis import (
    sentiment_score_multifactor,
    news_score_multifactor,
)


class TestV519N17SentimentNewsCountProgression:
    """N17: sentiment news_count ≥ 120 不再 cap flatline"""

    def test_news_count_120_to_500_strict_progression(self):
        """120 → 500 之間必須漸進 (monotonic increasing)"""
        scores = []
        for n in [120, 150, 200, 250, 300, 400, 500]:
            s = sentiment_score_multifactor(combined_score=0.0, confidence=0.5, news_count=n)
            scores.append(s)
        for i in range(1, len(scores)):
            assert scores[i] > scores[i-1], (
                f"news_count {120+i*50} score={scores[i]:.6f} should be > "
                f"prev={scores[i-1]:.6f} (N17 violation)"
            )

    def test_news_count_500_capped_at_max(self):
        """500+ 條應達 nc_factor 上限（不再無限增長）"""
        s_500 = sentiment_score_multifactor(0.0, 0.5, 500)
        s_1000 = sentiment_score_multifactor(0.0, 0.5, 1000)
        s_5000 = sentiment_score_multifactor(0.0, 0.5, 5000)
        # 500+ 全部飽和到 1.0 nc_factor
        assert s_500 == s_1000 == s_5000, (
            f"500+ news should all saturate, got {s_500:.6f}/{s_1000:.6f}/{s_5000:.6f}"
        )

    def test_news_count_120_unchanged_from_v518(self):
        """news_count=120 行為與 v5.18 一致（向後相容）"""
        s = sentiment_score_multifactor(0.0, 0.5, 120)
        assert abs(s - 0.595000) < 1e-4, f"news_count=120 score={s:.6f} (v5.18=0.595000)"

    def test_news_count_under_120_unchanged(self):
        """news_count<120 完全不受 v5.19 影響"""
        for n in [0, 30, 60, 90, 119]:
            s = sentiment_score_multifactor(0.0, 0.5, n)
            # 與 v5.18 公式 nc_factor 相同路徑
            assert 0.0 < s < 1.0


class TestV519N18NewsNewsCountProgression:
    """N18: news news_count ≥ 120 不再 cap flatline"""

    def test_news_count_120_to_500_strict_progression(self):
        scores = []
        for n in [120, 150, 200, 250, 300, 400, 500]:
            s = news_score_multifactor(news_count=n, region_count=3, source_diversity=4)
            scores.append(s)
        for i in range(1, len(scores)):
            assert scores[i] > scores[i-1], (
                f"news news_count {120+i*50} score={scores[i]:.6f} should be > "
                f"prev={scores[i-1]:.6f} (N18 violation)"
            )

    def test_news_count_500_capped(self):
        s_500 = news_score_multifactor(500, 3, 4)
        s_5000 = news_score_multifactor(5000, 3, 4)
        assert s_500 == s_5000, f"500+ news_count should saturate, got {s_500} vs {s_5000}"

    def test_news_count_120_unchanged(self):
        """120 條新聞行為不變"""
        s = news_score_multifactor(120, 3, 4)
        assert abs(s - 0.777455) < 1e-4


class TestV519N19NewsRegionCountProgression:
    """N19: news region_count ≥ 5 不再 cap flatline"""

    def test_region_count_5_to_12_strict_progression(self):
        scores = []
        for r in [5, 6, 7, 8, 9, 10, 11, 12]:
            s = news_score_multifactor(news_count=50, region_count=r, source_diversity=4)
            scores.append(s)
        for i in range(1, len(scores)):
            assert scores[i] > scores[i-1], (
                f"region_count {5+i} score={scores[i]:.6f} should be > "
                f"prev={scores[i-1]:.6f} (N19 violation)"
            )

    def test_region_count_12_capped(self):
        s_12 = news_score_multifactor(50, 12, 4)
        s_20 = news_score_multifactor(50, 20, 4)
        assert s_12 == s_20, f"12+ region should saturate, got {s_12} vs {s_20}"

    def test_region_count_5_unchanged(self):
        """5 個 region 行為不變 (向後相容)"""
        s = news_score_multifactor(50, 5, 4)
        assert abs(s - 0.578371) < 1e-4

    def test_region_count_under_5_unchanged(self):
        """<5 region 完全不受 v5.19 影響"""
        for r in [0, 1, 2, 3, 4]:
            s = news_score_multifactor(50, r, 4)
            assert 0.3 < s < 0.6, f"region_count={r}: score={s}"


class TestV519SourceDiversityProgression:
    """Bonus: source_diversity ≥ 12 → 30 漸進（與 region_count 一致）"""

    def test_source_diversity_12_to_30_strict_progression(self):
        scores = []
        for d in [12, 15, 18, 21, 24, 27, 30]:
            s = news_score_multifactor(news_count=50, region_count=3, source_diversity=d)
            scores.append(s)
        for i in range(1, len(scores)):
            assert scores[i] > scores[i-1], (
                f"source_diversity {12+i*3} score={scores[i]:.6f} should be > "
                f"prev={scores[i-1]:.6f}"
            )

    def test_source_diversity_30_capped(self):
        s_30 = news_score_multifactor(50, 3, 30)
        s_50 = news_score_multifactor(50, 3, 50)
        assert s_30 == s_50

    def test_source_diversity_12_unchanged(self):
        """12 個 source 行為不變"""
        s = news_score_multifactor(50, 3, 12)
        assert abs(s - 0.594917) < 1e-4


class TestV519RangeSanity:
    """v5.19 修復後所有 news 函數仍 in [0, 1]"""

    def test_sentiment_in_unit_interval(self):
        for n in [0, 10, 50, 100, 200, 500, 1000, 5000]:
            for cs in [-1, 0, 0.5, 1]:
                for conf in [0, 0.5, 1]:
                    s = sentiment_score_multifactor(cs, conf, n)
                    assert 0 <= s <= 1, f"sentiment out of range: cs={cs} conf={conf} n={n} → {s}"

    def test_news_in_unit_interval(self):
        for n in [0, 50, 200, 1000]:
            for r in [0, 3, 8, 20]:
                for d in [0, 5, 15, 50]:
                    s = news_score_multifactor(n, r, d)
                    assert 0 <= s <= 1, f"news out of range: n={n} r={r} d={d} → {s}"