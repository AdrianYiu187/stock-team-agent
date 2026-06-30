"""v5.21 P2 — Live score engine regression tests.

驗證 (per docs/v5.21_live_fixtures_design.md §3.1):
1. recompute_v510_scores 與 v5.20 hardcoded fixture Δ < 1e-6 (數學一致)
2. recompute_v5113_scores 與 v5.20 hardcoded fixture Δ < 1e-6
3. recompute_all_scores 3 個 sections 都有
4. 空 fundamentals → 空 result
5. 部分 ticker 缺失 → 跳過該 ticker
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_sources.live_score_engine import (  # noqa: E402
    recompute_v510_scores,
    recompute_v5113_scores,
    recompute_all_scores,
    recompute_std_quant,
)


FIXTURES_PATH = SCRIPTS_DIR / "tests" / "fixtures" / "tickers_fundamentals.json"


@pytest.fixture(scope="module")
def hardcoded_fixtures():
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


class TestLiveScoreEngine:
    """v5.21 P2 live_score_engine.py regression guard."""

    def test_v510_scores_match_hardcoded(self, hardcoded_fixtures):
        """v5.10 recomputed Δ vs hardcoded < 1e-6 — 證明 scoring math 一致."""
        fundamentals = hardcoded_fixtures["fundamentals"]
        hardcoded = hardcoded_fixtures["v5_10_scores"]
        result = recompute_v510_scores(fundamentals)
        assert len(result) == len(hardcoded), (
            f"Ticker count mismatch: {len(result)} vs {len(hardcoded)}"
        )
        for t in hardcoded:
            assert t in result, f"Missing ticker {t}"
            delta = abs(result[t] - hardcoded[t])
            assert delta < 1e-6, (
                f"v5.10 {t} Δ={delta:.2e} exceeds tolerance (recomputed={result[t]}, hardcoded={hardcoded[t]})"
            )

    def test_v5113_scores_match_hardcoded(self, hardcoded_fixtures):
        """v5.11.3 recomputed Δ vs hardcoded < 1e-6."""
        fundamentals = hardcoded_fixtures["fundamentals"]
        hardcoded = hardcoded_fixtures["v5_11_3_scores"]
        result = recompute_v5113_scores(fundamentals)
        assert len(result) == len(hardcoded)
        for t in hardcoded:
            assert t in result, f"Missing ticker {t}"
            delta = abs(result[t] - hardcoded[t])
            assert delta < 1e-6, (
                f"v5.11.3 {t} Δ={delta:.2e} exceeds tolerance"
            )

    def test_recompute_all_returns_3_sections(self, hardcoded_fixtures):
        """recompute_all_scores 必含 v5_10_scores / v5_11_3_scores / std_quant."""
        fundamentals = hardcoded_fixtures["fundamentals"]
        result = recompute_all_scores(fundamentals)
        assert "v5_10_scores" in result
        assert "v5_11_3_scores" in result
        assert "std_quant" in result
        # std_quant 結構 per quantize_cross_market
        assert "v5_10_std" in result["std_quant"]
        assert "v5_11_3_std" in result["std_quant"]
        assert "std_delta" in result["std_quant"]
        assert "sample_size" in result["std_quant"]
        assert result["std_quant"]["sample_size"] == len(hardcoded_fixtures["tickers"])

    def test_empty_fundamentals(self):
        """空 fundamentals → 空 result (no crash)."""
        result = recompute_all_scores({})
        assert result["v5_10_scores"] == {}
        assert result["v5_11_3_scores"] == {}
        assert result["std_quant"]["sample_size"] == 0

    def test_partial_fundamentals(self, hardcoded_fixtures):
        """部分 ticker 缺失 → 只算有的,missing 不報錯."""
        fundamentals = {
            "AAPL": hardcoded_fixtures["fundamentals"]["AAPL"],
            "MSFT": hardcoded_fixtures["fundamentals"]["MSFT"],
        }
        result = recompute_all_scores(fundamentals)
        assert "AAPL" in result["v5_10_scores"]
        assert "MSFT" in result["v5_10_scores"]
        assert len(result["v5_10_scores"]) == 2
        assert result["std_quant"]["sample_size"] == 2

    def test_scores_in_valid_range(self, hardcoded_fixtures):
        """所有 score 必在 [0, 1] 範圍."""
        fundamentals = hardcoded_fixtures["fundamentals"]
        result = recompute_all_scores(fundamentals)
        for t, s in result["v5_10_scores"].items():
            assert 0 <= s <= 1, f"v5.10 {t} score {s} out of [0,1]"
        for t, s in result["v5_11_3_scores"].items():
            assert 0 <= s <= 1, f"v5.11.3 {t} score {s} out of [0,1]"

    def test_std_quant_delta_sign(self, hardcoded_fixtures):
        """v5.11.3 std 應 ≤ v5.10 std (cap 飽和效果 — per Lesson 25 / 26)."""
        fundamentals = hardcoded_fixtures["fundamentals"]
        result = recompute_std_quant(fundamentals)
        # v5.11.3 設計目標 = 降低 std (cap 飽和 → 集中)
        assert result["v5_11_3_std"] <= result["v5_10_std"], (
            f"v5.11.3 std {result['v5_11_3_std']} > v5.10 std {result['v5_10_std']} — "
            f"cap saturation 失效!"
        )
