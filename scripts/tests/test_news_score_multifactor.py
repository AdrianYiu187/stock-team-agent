"""v5.12 (Pitfall #33) news_score_multifactor — 12 條永久 pytest。

設計：
    - news_count (0.5): 線性 0 (0 條) → 0.95 (≥120 條)
    - region_count (0.3): 線性 0.3 (0 區) → 0.95 (3+ 區)
    - source_diversity (0.2): 線性 0.3 (1 源) → 0.95 (≥6 源)

成功標準（Rule 4）：
    1. score ∈ [0, 1]
    2. 單調性：news_count ↑ → score ↑
    3. 單調性：region_count ↑ → score ↑
    4. 單調性：source_diversity ↑ → score ↑
    5. 連續性：news_count=30 vs 60 vs 90 顯著不同
    6. 極端：news_count=0 → score 低
    7. 極端：3 區 + 6 源 + 120 條 → score 高
    8. news_count=60 在 v5.11 之前是 hard cap，現在是連續
    9. region_count=0 不崩潰
    10. source_diversity=0 不崩潰
    11. 修 v5.11 之前 `if-elif-elif` 分段跳躍
    12. 加權和 = 1.0（避免 RFactor 殘差）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import news_score_multifactor  # noqa: E402


class TestNewsScoreMultifactor:
    """12 條 pytest 永久化 v5.12 P33 news_score_multifactor。"""

    def test_01_score_in_unit_interval(self):
        """所有輸入下 score ∈ [0, 1]。"""
        for nc in [0, 30, 60, 120]:
            for rc in [0, 1, 3]:
                for sd in [1, 3, 6]:
                    s = news_score_multifactor(nc, rc, sd)
                    assert 0.0 <= s <= 1.0, f"nc={nc} rc={rc} sd={sd} → {s}"

    def test_02_monotonic_in_news_count(self):
        """news_count ↑ → score ↑（rc=2, sd=3 固定，cap 飽和後 =）。"""
        scores = [news_score_multifactor(nc, 2, 3) for nc in [0, 30, 60, 90, 120, 200]]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"news_count 非單調: {scores}"
            )

    def test_03_monotonic_in_region_count(self):
        """region_count ↑ → score ↑（nc=30, sd=3 固定，cap 飽和後 =）。"""
        scores = [news_score_multifactor(30, rc, 3) for rc in [0, 1, 2, 3, 5]]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"region_count 非單調: {scores}"
            )

    def test_04_monotonic_in_source_diversity(self):
        """source_diversity ↑ → score ↑（nc=30, rc=2 固定，cap 飽和後 =）。"""
        scores = [news_score_multifactor(30, 2, sd) for sd in [1, 2, 3, 4, 6, 10]]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"source_diversity 非單調: {scores}"
            )

    def test_05_continuity_at_thresholds(self):
        """news_count=30 vs 60 vs 90 顯著不同（修 v5.11 之前硬切）。"""
        s30 = news_score_multifactor(30, 2, 3)
        s60 = news_score_multifactor(60, 2, 3)
        s90 = news_score_multifactor(90, 2, 3)
        # 連續線性：差距應線性
        d_30_60 = s60 - s30
        d_60_90 = s90 - s60
        assert 0.05 < d_30_60 < 0.20, f"s30→s60 跳太大：{d_30_60}"
        assert abs(d_30_60 - d_60_90) < 0.01, (
            f"非線性: d_30_60={d_30_60} d_60_90={d_60_90}"
        )

    def test_06_zero_news_count(self):
        """news_count=0 → score 最低（但 region/來源仍有基本分）。"""
        s = news_score_multifactor(0, 0, 0)
        # nc=0, rc=0 (0.30), sd=1 (0.30)
        # score = 0*0.5 + 0.30*0.3 + 0.30*0.2 = 0.09 + 0.06 = 0.15
        assert 0.10 <= s <= 0.20, f"零新聞 score 應 ≈ 0.15，got {s}"

    def test_07_optimal_coverage(self):
        """v5.15 P43/P44: 3 區 + 6 源不再是 cap（線性延伸），但 120 條仍是 cap。"""
        s = news_score_multifactor(120, 3, 6)
        # v5.15 P43/P44: rc=3 (線性延伸, 0.30+0.65*3/5=0.69), sd=6 (線性延伸, 0.30+0.65*5/11=0.5955)
        # nc=120 cap=0.95 → score = 0.475 + 0.69*0.3 + 0.5955*0.2 = 0.475 + 0.207 + 0.119 = 0.801
        assert 0.79 <= s <= 0.81, f"v5.15 線性延伸後 score 應 ≈ 0.801，got {s}"

    def test_08_no_hard_cap_at_60(self):
        """news_count=60 不再是 hard cap（v5.11 之前 60 條一律 0.6）。"""
        s_50 = news_score_multifactor(50, 2, 3)
        s_60 = news_score_multifactor(60, 2, 3)
        s_70 = news_score_multifactor(70, 2, 3)
        # 連續：s_50 < s_60 < s_70（v5.11 之前 s_50=0.55, s_60=0.6, s_70=0.6 跳躍）
        assert s_50 < s_60 < s_70, (
            f"硬切殘留: s_50={s_50} s_60={s_60} s_70={s_70}"
        )
        assert s_60 - s_50 > 0.02 and s_70 - s_60 > 0.02, (
            f"60 條附近差距太小（v5.11 硬切 bug 殘留）"
        )

    def test_09_zero_region_no_crash(self):
        """region_count=0 不崩潰（沒 RSS 區域但有新聞）。"""
        s = news_score_multifactor(30, 0, 1)
        # nc=30→0.2375, rc=0→0.30, sd=1→0.30
        # score = 0.2375*0.5 + 0.30*0.3 + 0.30*0.2 = 0.119+0.09+0.06 = 0.269
        assert 0.20 <= s <= 0.35, f"0 區 score 應 ≈ 0.27，got {s}"

    def test_10_zero_source_diversity_no_crash(self):
        """source_diversity=0 不崩潰（單一來源）。"""
        s = news_score_multifactor(30, 1, 0)
        # sd=0 進 ≤ 1 branch → 0.30
        assert 0.0 <= s <= 1.0

    def test_11_v511_jump_removed(self):
        """v5.11 之前 30→60 跳躍從 0.55→0.6 修為連續線性。"""
        s_30 = news_score_multifactor(30, 2, 3)
        s_31 = news_score_multifactor(31, 2, 3)
        # 連續性：1 條差距應 < 0.01
        assert abs(s_31 - s_30) < 0.01, (
            f"v5.11 硬切殘留: s_30={s_30} s_31={s_31} 差 {abs(s_31 - s_30)}"
        )

    def test_12_weight_sum_equals_one(self):
        """加權和 = 1.0（避免 RFactor 殘差導致 score scale 漂移）。v5.15 P43/P44 後用 ≥5 區/≥12 源才能 cap。"""
        # 取極端值，檢查各因子獨立貢獻
        # nc=120 (0.95 cap) + rc=5 (0.95 cap, v5.15 P43) + sd=12 (0.95 cap, v5.15 P44) = 0.95
        s = news_score_multifactor(120, 5, 12)
        expected = 0.95 * (0.5 + 0.3 + 0.2)  # 0.95 * 1.0
        assert abs(s - expected) < 1e-6, (
            f"加權和 ≠ 1.0: s={s} expected={expected}"
        )
