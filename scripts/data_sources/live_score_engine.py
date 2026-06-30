"""v5.21 — Live score recompute engine.

設計 (per docs/v5.21_live_fixtures_design.md §2.4):
- 從 cached/realtime fundamentals 重算 v5_10_scores / v5_11_3_scores / std_quant
- 不重寫 scoring 邏輯 (Rule 2「最小代碼」),直接 import cross_market_real_yfinance_e2e.score_tickers
- live_score_engine.py 是 wrapper,所有 scoring math 仍在原處

使用:
    from data_sources.live_score_engine import recompute_all_scores

    scores = recompute_all_scores(['AAPL', '0700.HK'])
    # {
    #   'v5_10_scores': {'AAPL': 0.72, '0700.HK': 0.55, ...},
    #   'v5_11_3_scores': {'AAPL': 0.68, ...},
    #   'std_quant': {...}
    # }
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

# 確保 cross_market_real_yfinance_e2e 可 import
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from cross_market_real_yfinance_e2e import (  # noqa: E402
    score_ticker,
    score_tickers,
    quantize_cross_market,
    _load_module,
    V510_PATH,
    V511_PATH,
)


def _ensure_v510_baseline() -> None:
    """v5.10 baseline 必須先存在 (per cross_market_real_yfinance_e2e.py:_ensure_v510_baseline)."""
    if not V510_PATH.exists():
        raise RuntimeError(
            f"❌ {V510_PATH} 不存在。請先跑：\n"
            f"   git show 0f30069:scripts/stock_analysis.py > {V510_PATH}"
        )


def _load_v510_v511_modules():
    """載入 v5.10 (baseline) + v5.11.3 (current) modules."""
    _ensure_v510_baseline()
    v510_mod = _load_module("v510_baseline", V510_PATH)
    v511_mod = _load_module("v511_current", V511_PATH)
    return v510_mod, v511_mod


def recompute_v510_scores(fundamentals: dict[str, dict]) -> dict[str, float]:
    """v5.10 fund_score_multifactor() 重算所有 tickers.

    Args:
        fundamentals: {ticker: {pe, roe, peg, growth}, ...}
    Returns:
        {ticker: score (0..1), ...}
    """
    _ensure_v510_baseline()
    v510_mod = _load_module("v510_baseline", V510_PATH)
    return score_tickers(v510_mod.fund_score_multifactor, fundamentals)


def recompute_v5113_scores(fundamentals: dict[str, dict]) -> dict[str, float]:
    """v5.11.3 fund_score_multifactor() 重算所有 tickers (current)."""
    v511_mod = _load_module("v511_current", V511_PATH)
    return score_tickers(v511_mod.fund_score_multifactor, fundamentals)


def recompute_std_quant(fundamentals: dict[str, dict]) -> dict:
    """std_quant = quantize_cross_market(v5.10, v5.11.3) per ticker.

    原始 quantize_cross_market 比較 v510 vs v511 std 差異。
    std_quant 結構 per cross_market_real_yfinance_e2e.py:quantize_cross_market 返回。
    """
    v510_scores = recompute_v510_scores(fundamentals)
    v511_scores = recompute_v5113_scores(fundamentals)
    return quantize_cross_market(v510_scores, v511_scores)


def recompute_all_scores(fundamentals: dict[str, dict]) -> dict:
    """一次重算 3 個 sections (v5_10_scores / v5_11_3_scores / std_quant).

    Args:
        fundamentals: {ticker: {pe, roe, peg, growth}, ...}
    Returns:
        {
            'v5_10_scores': {ticker: float, ...},
            'v5_11_3_scores': {ticker: float, ...},
            'std_quant': {...},  # 來自 quantize_cross_market
        }
    """
    v510_scores = recompute_v510_scores(fundamentals)
    v511_scores = recompute_v5113_scores(fundamentals)
    return {
        "v5_10_scores": v510_scores,
        "v5_11_3_scores": v511_scores,
        "std_quant": quantize_cross_market(v510_scores, v511_scores),
    }


# v5.23 P5 — cap-zone warning API (Lesson #49 永久化)
# Per docs/v5.23_roadmap.md §P5: live mode operator dashboard 需要
# 「哪些 ticker 在 cap-zone 上撞牆」的自動 warning,不必每次手動跑 cap_coverage_report。

# Cap-zone 判定規則 (per v5.22 P42 B-0 量化 + v5.22 Stage 5 保留):
# 規則對應 stock_analysis.fund_score_multifactor 各 factor 的邊界
_FUND_CAP_RULES = (
    # (metric, rule_key, predicate(ticker_fund_dict) -> bool, threshold_value, is_by_design)
    ("fund.pe",      "pe",      lambda f: f.get("pe", 0) > 500,     500, True),   # by-design clip
    ("fund.roe",     "roe",     lambda f: f.get("roe", 0) > 3.0,    3.0, True),   # by-design clip
    ("fund.peg",     "peg",     lambda f: (f.get("peg") or 0) > 25, 25.0, True),   # by-design clip (v5.22 P42 後)
    ("fund.growth",  "growth",  lambda f: f.get("growth", 0) > 5.0, 5.0, True),   # by-design clip
)


def _detect_cap_zone_collisions(
    fundamentals: dict[str, dict],
    threshold: float = 0.005,
) -> list[dict]:
    """對每個 fund.* cap-zone 規則掃所有 ticker,回傳 colliding warnings。

    Args:
        fundamentals: {ticker: {pe, roe, peg, growth}, ...}
        threshold: cap-zone 覆蓋率上限 (< threshold 視為 by-design,
                    預設 0.5% per v5.22 Stage B-0)

    Returns:
        [{
            'metric': 'fund.peg',
            'n_in_cap_zone': int,
            'coverage': float,
            'is_by_design': bool,
            'threshold_value': float,
            'tickers': [ticker, ...],   # 實際撞 cap 的 ticker
        }, ...]
    """
    total = max(len(fundamentals), 1)
    warnings: list[dict] = []
    for metric, _, predicate, threshold_value, is_by_design in _FUND_CAP_RULES:
        tickers = sorted(t for t, f in fundamentals.items() if predicate(f))
        if not tickers:
            continue
        coverage = len(tickers) / total
        warnings.append({
            "metric": metric,
            "n_in_cap_zone": len(tickers),
            "coverage": round(coverage, 4),
            "is_by_design": is_by_design,
            "threshold_value": threshold_value,
            "tickers": tickers,
        })
    return warnings


def recompute_all_scores_with_cap_warnings(
    fundamentals: dict[str, dict],
) -> dict:
    """v5.23 P5 — Live mode operator dashboard cap-zone warning。

    等同 recompute_all_scores() 但附加 cap-zone warning 結構。

    Args:
        fundamentals: {ticker: {pe, roe, peg, growth}, ...}

    Returns:
        {
            'scores': <same as recompute_all_scores()>,
            'cap_warnings': [
                {
                    'metric': 'fund.peg',
                    'n_in_cap_zone': int,
                    'coverage': float,
                    'is_by_design': bool,
                    'threshold_value': float,
                    'tickers': [str, ...],
                },
                ...
            ],
            'summary': {
                'total_warnings': int,
                'warning_by_metric': {metric: int},
                'live_unavailable_metrics': [],   # 預留 v5.24
            },
        }
    """
    scores = recompute_all_scores(fundamentals)
    cap_warnings = _detect_cap_zone_collisions(fundamentals)
    warning_by_metric = {w["metric"]: w["n_in_cap_zone"] for w in cap_warnings}
    return {
        "scores": scores,
        "cap_warnings": cap_warnings,
        "summary": {
            "total_warnings": len(cap_warnings),
            "warning_by_metric": warning_by_metric,
            "live_unavailable_metrics": [],
        },
    }


# v5.24 P1 — Cross-market E2E helper (Lesson #49 整合驗證)
# Per docs/v5.24_roadmap.md §P1: 串接 recompute_all_scores_with_cap_warnings()
# + quantize_cross_market + 提供 cross-market signal distribution 觸發點。
# 主流程整合點在 cross_market_real_yfinance_e2e.main() (P2)。


def recompute_cross_market_with_cap_warnings(
    fundamentals: dict[str, dict],
) -> dict:
    """v5.24 P1 — Cross-market E2E 整合 cap-zone warning。

    等同 recompute_all_scores_with_cap_warnings() 但結構對齊 cross-market
    E2E 流程,回傳額外 v5_11_3 std_quant + cross-market signal distribution key
    (預留 operator dashboard 整合)。

    Args:
        fundamentals: {ticker: {pe, roe, peg, growth}, ...}

    Returns:
        {
            'scores': {
                'v5_10_scores': {ticker: float, ...},
                'v5_11_3_scores': {ticker: float, ...},
                'std_quant': {...},   # 來自 quantize_cross_market
            },
            'cap_warnings': [...],    # 同 recompute_all_scores_with_cap_warnings
            'summary': {
                'total_warnings': int,
                'warning_by_metric': {metric: int},
                'live_unavailable_metrics': [],   # 預留
                'cross_market_signal_distribution': {},  # 預留 operator dashboard
            },
        }
    """
    base = recompute_all_scores_with_cap_warnings(fundamentals)
    return {
        "scores": base["scores"],
        "cap_warnings": base["cap_warnings"],
        "summary": {
            **base["summary"],
            "cross_market_signal_distribution": {},  # 預留 operator dashboard
        },
    }
