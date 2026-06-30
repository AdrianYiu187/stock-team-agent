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
