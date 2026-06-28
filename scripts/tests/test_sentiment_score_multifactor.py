"""v5.12 (Pitfall #34) sentiment_score_multifactor — 8 條永久 pytest。

設計：
    - combined_score 因子 (0.7): tanh 平滑，保留正負號
    - confidence 因子 (0.2): 0.5 中性，1.0 滿分
    - news_count 因子 (0.1): 0→0.4, 30→0.7, 60→0.9, ≥120→0.95

成功標準（Rule 4）：
    1. score ∈ [0, 1]（所有輸入）
    2. 單調性：combined_score ↑ → score ↑（confidence/news_count 固定）
    3. 中性點：combined_score=0 → score ≈ 0.5
    4. 正負分離：positive (>0) > neutral (0) > negative (<0)
    5. confidence ↑ → score ↑
    6. news_count ↑ → score ↑
    7. 邊界連續：combined_score=±1 不爆掉
    8. 0 news_count 不崩
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import sentiment_score_multifactor  # noqa: E402


class TestSentimentScoreMultifactor:
    """8 條 pytest 永久化 v5.12 P34 sentiment_score_multifactor。"""

    def test_01_score_in_unit_interval(self):
        """所有輸入下 score ∈ [0, 1]。"""
        for cs in [-1, -0.5, 0, 0.5, 1]:
            for conf in [0.3, 0.5, 0.8, 1.0]:
                for nc in [0, 30, 60, 120]:
                    s = sentiment_score_multifactor(cs, conf, nc)
                    assert 0.0 <= s <= 1.0, f"cs={cs} conf={conf} nc={nc} → {s}"

    def test_02_monotonic_in_combined_score(self):
        """combined_score ↑ → score ↑（confidence=0.5, nc=30 固定）。"""
        scores = [
            sentiment_score_multifactor(cs, 0.5, 30)
            for cs in [-1, -0.5, 0, 0.5, 1]
        ]
        for i in range(1, len(scores)):
            assert scores[i] > scores[i - 1], (
                f"非單調: cs=-1→{scores[0]}, cs=+1→{scores[-1]}, "
                f"序列={scores}"
            )

    def test_03_neutral_point_approximately_half(self):
        """combined_score=0 → score ≈ 0.5（中性點）。"""
        s = sentiment_score_multifactor(0, 0.5, 30)
        # cs_factor = 0.5; conf_factor = 0.75; nc_factor = 0.7
        # score = 0.5*0.7 + 0.75*0.2 + 0.7*0.1 = 0.35+0.15+0.07 = 0.57
        assert 0.5 <= s <= 0.65, f"中性 score 預期 ≈ 0.57，got {s}"

    def test_04_positive_negative_separation(self):
        """positive (>0) > neutral (0) > negative (<0)。"""
        s_neg = sentiment_score_multifactor(-0.5, 0.5, 30)
        s_neu = sentiment_score_multifactor(0.0, 0.5, 30)
        s_pos = sentiment_score_multifactor(+0.5, 0.5, 30)
        assert s_pos > s_neu > s_neg, (
            f"分離失敗: pos={s_pos} neu={s_neu} neg={s_neg}"
        )

    def test_05_monotonic_in_confidence(self):
        """confidence ↑ → score ↑（cs=0.3, nc=30 固定）。"""
        scores = [
            sentiment_score_multifactor(0.3, conf, 30)
            for conf in [0.3, 0.5, 0.7, 0.9, 1.0]
        ]
        for i in range(1, len(scores)):
            assert scores[i] > scores[i - 1], (
                f"confidence 非單調: {scores}"
            )

    def test_06_monotonic_in_news_count(self):
        """news_count ↑ → score ↑（cs=0.2, conf=0.5 固定）。"""
        scores = [
            sentiment_score_multifactor(0.2, 0.5, nc)
            for nc in [0, 10, 30, 60, 90, 120]
        ]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"news_count 非單調: {scores}"
            )

    def test_07_extreme_combined_score_no_explode(self):
        """combined_score=±1 不爆掉（tanh 飽和安全）。"""
        s_pos = sentiment_score_multifactor(1.0, 0.5, 30)
        s_neg = sentiment_score_multifactor(-1.0, 0.5, 30)
        # 對稱性：pos + neg ≈ 1.0（tanh 對稱 + conf/nc 相同）
        assert 0.85 <= s_pos <= 0.95, f"cs=+1 score 應 ≈ 0.90，got {s_pos}"
        # cs=-1 強負面 + conf=0.5 中性 + nc=30 中等 → score 偏中下 ≈ 0.27
        assert 0.20 <= s_neg <= 0.35, f"cs=-1 score 應 ≈ 0.27，got {s_neg}"
        # 對稱性檢查：cs_factor 對稱，但 conf/nc 推上去使 s_neg 不會很低
        # 真實對稱需 cs_factor*0.7 = 0.5*0.7=0.35 (cs=0) — 不同 cs 才看
        assert s_pos > 0.5 and s_neg < 0.5, (
            f"分離失敗: pos={s_pos} neg={s_neg} 應 pos>0.5 且 neg<0.5"
        )

    def test_08_zero_news_count_no_crash(self):
        """0 news_count 不崩潰（覆蓋偏少，low coverage）。"""
        s = sentiment_score_multifactor(0.3, 0.5, 0)
        assert 0.0 <= s <= 1.0
        # nc_factor = 0.40（最低）
        # cs_factor = 0.5 + 0.45 * tanh(0.6) = 0.5 + 0.45*0.537 = 0.7417
        # conf_factor = 0.75
        # score = 0.7417*0.7 + 0.75*0.2 + 0.40*0.1 = 0.5192+0.15+0.04 = 0.7092
        assert 0.65 <= s <= 0.75, f"0 news_count score 應 ≈ 0.71，got {s}"
