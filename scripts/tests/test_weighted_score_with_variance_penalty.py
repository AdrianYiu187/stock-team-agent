"""v5.12 (Pitfall #32) weighted_score_with_variance_penalty — 8 條永久 pytest。

設計：
    - weighted_avg = Σ (score * weight) / Σ weight
    - analyst_std = stdev(analyst_scores)
    - penalty = 1 - 0.3 * min(std, 1.0)  [0.7, 1.0]
    - final_score = weighted_avg * penalty

成功標準（Rule 4）：
    1. score ∈ [0, 1]
    2. 完全共識 (std=0) → penalty=1.0 → final=weighted_avg
    3. 最大分歧 (std=1) → penalty=0.7 → final=weighted_avg*0.7
    4. penalty 區間 ∈ [0.7, 1.0]
    5. analyst_std 正確反映 disagreement
    6. 空 scores/weights 不崩
    7. 單一 analyst → std=0（無分歧）
    8. final_score 永遠 < weighted_avg 若 std > 0（信心折扣）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import (  # noqa: E402
    weighted_score_with_variance_penalty,
)


class TestWeightedScoreWithVariancePenalty:
    """8 條 pytest 永久化 v5.12 P32 consensus variance penalty。"""

    def test_01_score_in_unit_interval(self):
        """所有輸入下 final_score ∈ [0, 1]。"""
        scores_cases = [
            {"a": 0.5, "b": 0.5, "c": 0.5},  # 完全共識
            {"a": 0.0, "b": 1.0},              # 完全相反
            {"a": 0.3, "b": 0.5, "c": 0.7, "d": 0.9},  # 4 analyst 分歧
            {"a": 0.0}, {"a": 1.0},
        ]
        weights = {"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.1}
        for s in scores_cases:
            final, std = weighted_score_with_variance_penalty(s, weights)
            assert 0.0 <= final <= 1.0, f"scores={s} → final={final}"

    def test_02_perfect_consensus_no_penalty(self):
        """完全共識 (std=0) → final = weighted_avg。"""
        scores = {"a": 0.6, "b": 0.6, "c": 0.6}
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        final, std = weighted_score_with_variance_penalty(scores, weights)
        assert std < 1e-6, f"完全共識 std 應 ≈ 0，got {std}"
        # weighted_avg = 0.6 * 1.0 = 0.6, penalty = 1.0
        assert abs(final - 0.6) < 1e-6, f"完全共識 final 應 = 0.6，got {final}"

    def test_03_max_disagreement_30pct_penalty(self):
        """最大分歧 (std=1) → penalty=0.7 → final = weighted_avg * 0.7。"""
        scores = {"a": 0.0, "b": 1.0}
        weights = {"a": 0.5, "b": 0.5}
        final, std = weighted_score_with_variance_penalty(scores, weights)
        # weighted_avg = 0.5, std = 0.5, penalty = 1 - 0.3*0.5 = 0.85
        # final = 0.5 * 0.85 = 0.425
        assert 0.40 <= final <= 0.45, f"分歧 final 應 ≈ 0.425，got {final}"
        # std 應 ≈ 0.5
        assert 0.4 <= std <= 0.6, f"std 應 ≈ 0.5，got {std}"

    def test_04_penalty_range_0_7_to_1_0(self):
        """penalty 永遠 ∈ [0.7, 1.0]。"""
        test_cases = [
            ({"a": 0.0, "b": 0.0}, {"a": 0.5, "b": 0.5}),  # std=0
            ({"a": 0.0, "b": 1.0}, {"a": 0.5, "b": 0.5}),  # std=0.5
            ({"a": 0.0, "b": 0.5, "c": 1.0}, {"a": 0.3, "b": 0.3, "c": 0.4}),  # std≈0.4
        ]
        for s, w in test_cases:
            _, std = weighted_score_with_variance_penalty(s, w)
            penalty = max(0.7, 1.0 - 0.3 * min(std, 1.0))
            assert 0.7 <= penalty <= 1.0, f"penalty {penalty} 超出 [0.7, 1.0]"

    def test_05_analyst_std_reflects_disagreement(self):
        """analyst_std 正確反映 disagreement。"""
        # 共識
        s_consensus = {"a": 0.5, "b": 0.5, "c": 0.5}
        # 中度分歧
        s_medium = {"a": 0.3, "b": 0.5, "c": 0.7}
        # 高度分歧
        s_high = {"a": 0.0, "b": 0.5, "c": 1.0}
        weights = {"a": 0.33, "b": 0.34, "c": 0.33}
        _, std_c = weighted_score_with_variance_penalty(s_consensus, weights)
        _, std_m = weighted_score_with_variance_penalty(s_medium, weights)
        _, std_h = weighted_score_with_variance_penalty(s_high, weights)
        assert std_c < 1e-6, f"共識 std 應 = 0，got {std_c}"
        assert std_m > std_c, f"中度 {std_m} 應 > 共識 {std_c}"
        assert std_h > std_m, f"高度 {std_h} 應 > 中度 {std_m}"

    def test_06_empty_inputs_no_crash(self):
        """空 scores/weights 不崩。"""
        # 空 dict
        f1, s1 = weighted_score_with_variance_penalty({}, {"a": 0.5})
        assert f1 == 0.5 and s1 == 0.0
        # 全空
        f2, s2 = weighted_score_with_variance_penalty({}, {})
        assert f2 == 0.5 and s2 == 0.0
        # scores 有但 weights 沒對應 role
        f3, s3 = weighted_score_with_variance_penalty({"a": 0.5}, {"b": 0.5})
        assert f3 == 0.5 and s3 == 0.0

    def test_07_single_analyst_no_disagreement(self):
        """單一 analyst → std=0（無分歧可比）。"""
        scores = {"a": 0.7}
        weights = {"a": 1.0}
        final, std = weighted_score_with_variance_penalty(scores, weights)
        assert std == 0.0, f"單一 analyst std 應 = 0，got {std}"
        # penalty = 1.0, final = weighted_avg = 0.7
        assert abs(final - 0.7) < 1e-6, f"final 應 = 0.7，got {final}"

    def test_08_final_below_weighted_avg_when_disagreement(self):
        """disagreement > 0 → final < weighted_avg（信心折扣證明）。"""
        scores = {"a": 0.3, "b": 0.7, "c": 0.5}
        weights = {"a": 0.4, "b": 0.4, "c": 0.2}
        # weighted_avg = 0.3*0.4 + 0.7*0.4 + 0.5*0.2 = 0.12+0.28+0.10 = 0.5
        # std ≈ 0.163
        # penalty = 1 - 0.3*0.163 = 0.951
        # final = 0.5 * 0.951 = 0.4755
        final, std = weighted_score_with_variance_penalty(scores, weights)
        # 計算 weighted_avg
        total_w = sum(weights[r] for r in weights if r in scores)
        weighted_avg = sum(scores[r] * weights[r] for r in weights if r in scores) / total_w
        assert std > 0, "disagreement > 0 應有 std"
        assert final < weighted_avg, (
            f"信心折扣: final={final} 應 < weighted_avg={weighted_avg}"
        )
        # 但 final 接近 weighted_avg（penalty 折扣 < 5%）
        assert (weighted_avg - final) / weighted_avg < 0.10, (
            f"penalty 過大: final={final} weighted_avg={weighted_avg}"
        )
