"""v5.23 P5 — live_score_engine cap-zone warning API (Lesson #49).

Per docs/v5.23_roadmap.md §P5:
設計動機: live mode operator dashboard 在 live recompute 時,需要一個 API
自動提示「哪些 ticker 在 cap-zone 上撞牆」,而不是每次手動掃 cap_coverage_report。

API spec — recompute_all_scores_with_cap_warnings():
  Input:  fundamentals = {ticker: {pe, roe, peg, growth}, ...}
  Output: {
    'scores': {v5_10_scores, v5_11_3_scores, std_quant},  # 同 recompute_all_scores
    'cap_warnings': [                                      # Lesson #49 永久 API
      {
        'metric': 'fund.peg' | 'fund.pe' | 'fund.roe' | 'fund.growth',
        'n_in_cap_zone': int,
        'coverage': float,
        'is_by_design': bool,
        'tickers': [ticker, ...],   # 實際撞 cap 的 ticker (新)
      },
      ...
    ],
    'summary': {                              # v5.23 operator dashboard 友善
      'total_warnings': int,
      'warning_by_metric': {metric: count},
      'live_unavailable_metrics': [metric],   # 預留 (實作 v5.24)
    },
  }

只有 _cap_zone_ 已經過 v5.22 量化驗證為「真實 pitfall」會出 warning:
- fund.peg (>5): v5.22 P42 fix 後應 < 0.5% (regression guard)
- fund.pe (>500): by_design 邊界保護,保留 cap (is_by_design=True 但仍上榜以便 audit)
- fund.roe (>3.0): by_design 邊界保護
- fund.growth (>5.0): by_design 邊界保護

TDD 紅→綠:
1. test_returns_scores_and_warnings_keys
2. test_warning_includes_fund_peg_when_peg_in_cap_range
3. test_no_warnings_when_all_fundamentals_normal (正常範圍 fully healthy)
4. test_summary_total_warnings_matches_warning_list_length
5. test_warning_tickers_are_substring_of_input (新欄位結構 sanity)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.data_sources import live_score_engine  # noqa: E402


def _normal_fundamentals() -> dict[str, dict]:
    """5 個全部在合理範圍的 fixture。"""
    return {
        "AAPL":       {"pe": 28.0, "roe": 0.45, "peg": 2.5, "growth": 0.08},
        "MSFT":       {"pe": 32.0, "roe": 0.40, "peg": 2.0, "growth": 0.12},
        "GOOGL":      {"pe": 24.0, "roe": 0.30, "peg": 1.5, "growth": 0.15},
        "0700.HK":    {"pe": 18.0, "roe": 0.22, "peg": 1.8, "growth": 0.10},
        "600519.SS":  {"pe": 35.0, "roe": 0.32, "peg": 2.8, "growth": 0.18},
    }


def _edge_case_fundamentals() -> dict[str, dict]:
    """4 個正常 + 1 個故意把 peg 推到 cap (>5) 觸發 warning。"""
    return {
        "AAPL":       {"pe": 28.0, "roe": 0.45, "peg": 2.5, "growth": 0.08},
        "MSFT":       {"pe": 32.0, "roe": 0.40, "peg": 2.0, "growth": 0.12},
        "GOOGL":      {"pe": 24.0, "roe": 0.30, "peg": 1.5, "growth": 0.15},
        "0700.HK":    {"pe": 18.0, "roe": 0.22, "peg": 1.8, "growth": 0.10},
        "3690.HK":    {"pe": 22.0, "roe": 0.15, "peg": 28.72, "growth": 0.06},  # PEG>5 cap
    }


def test_returns_scores_and_warnings_keys():
    """P5: API 必須回傳 'scores' + 'cap_warnings' + 'summary' 三層。"""
    result = live_score_engine.recompute_all_scores_with_cap_warnings(
        _normal_fundamentals()
    )
    assert "scores" in result
    assert "cap_warnings" in result
    assert "summary" in result
    # scores 子結構同 recompute_all_scores
    assert "v5_10_scores" in result["scores"]
    assert "v5_11_3_scores" in result["scores"]
    assert "std_quant" in result["scores"]


def test_warning_includes_fund_peg_when_peg_in_cap_range():
    """P5+核心: 故意推 PEG=28.72 (v5.22 真實值) → warning 必須上榜。"""
    result = live_score_engine.recompute_all_scores_with_cap_warnings(
        _edge_case_fundamentals()
    )
    warnings = result["cap_warnings"]
    peg_warnings = [w for w in warnings if w["metric"] == "fund.peg"]
    assert len(peg_warnings) >= 1, (
        f"預期有 fund.peg warning,實際 warnings: {[w['metric'] for w in warnings]}"
    )
    assert "3690.HK" in peg_warnings[0]["tickers"]


def test_no_warnings_when_all_fundamentals_normal():
    """P5+正向: 5 個都正常時, PEG/pe/roe/growth 都不該有 warn (健康 dashboard)。"""
    result = live_score_engine.recompute_all_scores_with_cap_warnings(
        _normal_fundamentals()
    )
    peg_warnings = [w for w in result["cap_warnings"] if w["metric"] == "fund.peg"]
    # v5.22 P42 fix 後 PEG>5 應為 0%; 完全正常 fixtures 應該沒有 PEG cap warning
    assert len(peg_warnings) == 0, (
        f"全正常 fixtures 不該有 fund.peg warning,實際: {peg_warnings}"
    )


def test_summary_total_warnings_matches_warning_list_length():
    """P5+dashboard: summary.total_warnings 必須 = len(cap_warnings)。"""
    result = live_score_engine.recompute_all_scores_with_cap_warnings(
        _edge_case_fundamentals()
    )
    assert result["summary"]["total_warnings"] == len(result["cap_warnings"])
    # warning_by_metric 必須涵蓋所有 warning metric
    summary_metrics = set(result["summary"]["warning_by_metric"].keys())
    warning_metrics = {w["metric"] for w in result["cap_warnings"]}
    assert summary_metrics == warning_metrics


def test_warning_tickers_are_substring_of_input():
    """P5+sanity: warning.tickers 都必須在 input fundamentals keys 內。"""
    input_keys = set(_edge_case_fundamentals().keys())
    result = live_score_engine.recompute_all_scores_with_cap_warnings(
        _edge_case_fundamentals()
    )
    for w in result["cap_warnings"]:
        for t in w["tickers"]:
            assert t in input_keys, f"warning ticker {t} 不在 input 中"
