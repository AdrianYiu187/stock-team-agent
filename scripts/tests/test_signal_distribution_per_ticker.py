"""v5.16 P50 — Signal distribution per ticker（cross-market 真實量化）。

設計：
    quantify_signal_distribution.py P48b 用 mock GBM 量化 buy/hold/sell，
    但無法驗證「99% hold → 26% buy」的改善在真實多 ticker 上也成立。

    本腳本從 cross_market fixtures（PE/ROE + sentiment/macro + 真實 yfinance），
    算每個 ticker 的 signal distribution + entropy，量化「cap 修復下游價值」。

成功標準（Rule 4）：
  1. 11/11 ticker 算 signal distribution
  2. 每 ticker 包含 buy/hold/sell ratio + signal_entropy
  3. signal_entropy ∈ [0, log2(3)] ≈ [0, 1.585]
  4. fixtures 加 signal_distribution_per_ticker 段
  5. fixtures 加完後 cross_market_real_yfinance_e2e pytest 不破壞既有
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from math import log2
from pathlib import Path
from typing import Optional

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

V514_PATH = SCRIPTS_DIR / "stock_analysis.py"
FIXTURES_PATH = SCRIPTS_DIR / "tests" / "fixtures" / "tickers_fundamentals.json"


def _load_module(label: str, path: Path):
    spec = importlib.util.spec_from_file_location(label, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 {label}（{path}）")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def v514():
    return _load_module("v514_stock_analysis", V514_PATH)


@pytest.fixture(scope="module")
def fixtures():
    if not FIXTURES_PATH.exists():
        pytest.skip(f"Fixtures {FIXTURES_PATH} 不存在")
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


# ============================================================
# 邊界測試 — 不需 fixtures
# ============================================================


class TestSignalDistributionFunctions:
    """compute_signal_distribution_per_ticker 邊界。"""

    def test_empty_inputs(self, v514):
        from cross_market_real_yfinance_e2e import compute_signal_distribution_per_ticker
        result = compute_signal_distribution_per_ticker(v514, {}, "AAPL")
        assert "error" in result or result.get("buy_ratio") == 0.0

    def test_missing_ticker(self, v514):
        from cross_market_real_yfinance_e2e import compute_signal_distribution_per_ticker
        fundamentals = {"AAPL": {"pe": 30, "roe": 0.5, "peg": 1.0, "growth": 0.1}}
        result = compute_signal_distribution_per_ticker(v514, fundamentals, "9999.HK")
        # 找不到 ticker → 回傳 error 或 fallback
        assert "error" in result or "buy_ratio" in result

    def test_valid_ticker_returns_signal(self, v514):
        from cross_market_real_yfinance_e2e import compute_signal_distribution_per_ticker
        fundamentals = {"AAPL": {"pe": 30, "roe": 0.5, "peg": 1.0, "growth": 0.1}}
        sentiment = {"AAPL": {"combined_score": 0.5, "confidence": 0.8, "news_count": 50}}
        macro = {"AAPL": {"index": "^GSPC", "macro_score": 0.55, "30d_return": 0.05, "annualized_vol": 0.15}}
        result = compute_signal_distribution_per_ticker(
            v514, fundamentals, "AAPL", sentiment=sentiment, macro=macro,
        )
        assert "buy_ratio" in result
        assert "hold_ratio" in result
        assert "sell_ratio" in result
        assert "signal_entropy" in result
        # ratio 總和 ≈ 1.0（容許 1e-4，因為 v514 加載可能含不同 import 路徑）
        total = result["buy_ratio"] + result["hold_ratio"] + result["sell_ratio"]
        assert abs(total - 1.0) < 1e-4
        # entropy ∈ [0, log2(3)]
        assert 0.0 <= result["signal_entropy"] <= log2(3) + 1e-6


# ============================================================
# Fixtures 整合測試
# ============================================================


class TestFixturesIntegration:
    """fixtures 含 sentiment + macro + signal 後的整合測試。"""

    def test_fixtures_has_sentiment_macro(self, fixtures):
        # 假設 task 2 已跑 derive_real_sentiment_macro.py
        assert "sentiment_per_ticker" in fixtures
        assert "macro_per_ticker" in fixtures

    def test_fixtures_has_signal_distribution_or_skip(self, fixtures):
        # task 3 整合後才會有
        if "signal_distribution_per_ticker" not in fixtures:
            pytest.skip("signal_distribution_per_ticker 尚未產生，請先跑 cross_market_real_yfinance_e2e.py")
        assert isinstance(fixtures["signal_distribution_per_ticker"], dict)

    def test_signal_distribution_keys(self, fixtures):
        if "signal_distribution_per_ticker" not in fixtures:
            pytest.skip("尚未整合")
        for t, sig in fixtures["signal_distribution_per_ticker"].items():
            assert "buy_ratio" in sig
            assert "hold_ratio" in sig
            assert "sell_ratio" in sig
            assert "signal_entropy" in sig
            assert "majority" in sig
            total = sig["buy_ratio"] + sig["hold_ratio"] + sig["sell_ratio"]
            assert abs(total - 1.0) < 1e-4, f"{t} ratios sum to {total}"
            assert 0.0 <= sig["signal_entropy"] <= log2(3) + 1e-6

    def test_all_11_tickers_have_signal(self, fixtures):
        if "signal_distribution_per_ticker" not in fixtures:
            pytest.skip("尚未整合")
        tickers = fixtures.get("tickers", [])
        assert len(tickers) == 11
        for t in tickers:
            assert t in fixtures["signal_distribution_per_ticker"], f"{t} 缺 signal distribution"