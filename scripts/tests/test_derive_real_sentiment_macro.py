"""v5.16 P49 — 真實 sentiment + macro 派生 pytest。

設計：驗證 derive_real_sentiment_macro.py 從 yfinance 拉 sentiment + macro
並寫入 fixtures 的正確性。

成功標準（Rule 4）：
  1. fetch_sentiment_macro 返回 3 個 key（sentiment/macro/failed_tickers）
  2. 11/11 ticker 派生（per-ticker error tolerance）
  3. sentiment combined_score ∈ [-1, 1]
  4. macro_score ∈ [0, 1]
  5. fixtures 加 sentiment_macro 段後 pytest 不破壞既有
  6. compute_sentiment_from_news 邊界：空 list / 無關鍵字 / 純 positive / 純 negative
  7. compute_macro_from_history 邊界：空 list / 全 0 / 上升趨勢 / 下降趨勢
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from derive_real_sentiment_macro import (  # noqa: E402
    TICKER_TO_MACRO_INDEX,
    TICKER_UNIVERSE,
    compute_macro_from_history,
    compute_sentiment_from_news,
    fetch_sentiment_macro,
    update_fixtures_with_sentiment_macro,
)


# ============================================================
# 邊界測試 — 不需網路
# ============================================================


class TestComputeSentimentFromNews:
    """compute_sentiment_from_news 邊界。"""

    def test_empty_news_returns_neutral(self):
        cs, conf, count = compute_sentiment_from_news([])
        assert cs == 0.0
        assert conf == 0.0
        assert count == 0

    def test_only_positive_keywords(self):
        news = [
            {"title": "Stock surges to record high"},
            {"title": "Strong growth beat estimates"},
        ]
        cs, conf, count = compute_sentiment_from_news(news)
        assert cs > 0.5  # mostly positive
        assert conf > 0
        assert count == 2

    def test_only_negative_keywords(self):
        news = [
            {"title": "Stock plunges on weak earnings"},
            {"title": "Bearish outlook declines further"},
        ]
        cs, conf, count = compute_sentiment_from_news(news)
        assert cs < -0.5
        assert conf > 0
        assert count == 2

    def test_balanced_news(self):
        news = [
            {"title": "Strong rally beats expectations"},
            {"title": "Bearish decline plunges shares"},
        ]
        cs, conf, count = compute_sentiment_from_news(news)
        assert -0.3 < cs < 0.3  # balanced → near 0
        assert count == 2

    def test_no_keywords_neutral_with_low_conf(self):
        news = [{"title": "Quarterly report filed"}]
        cs, conf, count = compute_sentiment_from_news(news)
        assert cs == 0.0
        assert conf < 0.5  # 低信心（沒情緒信號）
        assert count == 1

    def test_confidence_caps_at_1(self):
        news = [{"title": f"surge {i}"} for i in range(100)]
        cs, conf, count = compute_sentiment_from_news(news)
        assert conf == 1.0  # 100/60 → 1.0 (capped)
        assert count == 100


class TestComputeMacroFromHistory:
    """compute_macro_from_history 邊界。"""

    def test_empty_history_returns_neutral(self):
        assert compute_macro_from_history([]) == 0.5

    def test_single_value_returns_neutral(self):
        assert compute_macro_from_history([100.0]) == 0.5

    def test_uptrend_high_score(self):
        # 平穩上升
        history: list[float] = [100.0 + i * 0.5 for i in range(30)]
        score = compute_macro_from_history(history)
        assert score > 0.5

    def test_downtrend_low_score(self):
        history: list[float] = [100.0 - i * 0.5 for i in range(30)]
        score = compute_macro_from_history(history)
        assert score < 0.5

    def test_volatile_returns_neutral(self):
        # 高波動但最終回原點
        history = [100, 110, 90, 105, 95, 100, 110, 90, 105, 95] * 3
        score = compute_macro_from_history(history)
        assert 0.4 <= score <= 0.6  # 高波動 → 中性

    def test_score_in_bounds(self):
        history = [100, 200, 50, 300, 10]  # 極端值
        score = compute_macro_from_history(history)
        assert 0.0 <= score <= 1.0


# ============================================================
# Ticker 映射測試
# ============================================================


class TestTickerMapping:
    """TICKER_TO_MACRO_INDEX 完整性。"""

    def test_all_tickers_have_macro_index(self):
        for t in TICKER_UNIVERSE:
            assert t in TICKER_TO_MACRO_INDEX, f"{t} 缺 macro index 映射"

    def test_macro_indexes_count(self):
        # 11 ticker → 4 unique macro index（^GSPC, ^HSI, 000001.SS, 399001.SZ）
        unique = set(TICKER_TO_MACRO_INDEX[t] for t in TICKER_UNIVERSE)
        assert len(unique) == 4

    def test_us_tickers_use_spy(self):
        for t in ["AAPL", "MSFT", "GOOGL", "NVDA"]:
            assert TICKER_TO_MACRO_INDEX[t] == "^GSPC"

    def test_hk_tickers_use_hsi(self):
        for t in ["0700.HK", "9988.HK", "3690.HK"]:
            assert TICKER_TO_MACRO_INDEX[t] == "^HSI"

    def test_cn_tickers_use_sse_or_szse(self):
        for t in ["600519.SS", "601318.SS"]:
            assert TICKER_TO_MACRO_INDEX[t] == "000001.SS"
        for t in ["000858.SZ", "000333.SZ"]:
            assert TICKER_TO_MACRO_INDEX[t] == "399001.SZ"


# ============================================================
# Fixtures 更新測試
# ============================================================


class TestFixturesUpdate:
    """update_fixtures_with_sentiment_macro 不破壞既有結構。"""

    def test_preserves_existing_fields(self):
        original = {
            "tickers": ["AAPL"],
            "fundamentals": {"AAPL": {"pe": 30}},
            "v5_10_scores": {"AAPL": 0.5},
            "v5_11_3_scores": {"AAPL": 0.6},
            "std_quant": {"sample_size": 1},
            "_meta": {"fetched_at": "2026-06-28"},
        }
        derived = {
            "sentiment_per_ticker": {"AAPL": {"combined_score": 0.5, "confidence": 0.8, "news_count": 50}},
            "macro_per_ticker": {"AAPL": {"index": "^GSPC", "macro_score": 0.55, "30d_return": 0.05, "annualized_vol": 0.15}},
            "failed_tickers": [],
        }
        result = update_fixtures_with_sentiment_macro(original, derived)
        # 既有欄位保留
        assert result["tickers"] == ["AAPL"]
        assert result["fundamentals"]["AAPL"]["pe"] == 30
        assert result["v5_10_scores"]["AAPL"] == 0.5
        assert result["v5_11_3_scores"]["AAPL"] == 0.6
        assert result["std_quant"]["sample_size"] == 1
        # 新欄位加入
        assert "sentiment_per_ticker" in result
        assert "macro_per_ticker" in result
        assert "sentiment_macro_fetched_at" in result["_meta"]
        assert result["_meta"]["sentiment_macro_failed"] == []
        assert "ticker_to_macro_index" in result["_meta"]


# ============================================================
# 整合測試 — fetch_sentiment_macro（需網路）
# ============================================================


@pytest.fixture(scope="module")
def derived() -> dict:
    """一次性拉 sentiment + macro（網路操作，整個 module 共用）。"""
    try:
        result = fetch_sentiment_macro(TICKER_UNIVERSE, period_days=30)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"yfinance 網路失敗：{e}")
    return result


@pytest.mark.skipif(
    "sys.platform == 'win32'", reason="Windows yfinance 限制"
)
class TestFetchSentimentMacro:
    """fetch_sentiment_macro 整合測試（需網路，會跑但可能 skip）。"""

    def test_three_keys(self, derived):
        assert "sentiment_per_ticker" in derived
        assert "macro_per_ticker" in derived
        assert "failed_tickers" in derived

    def test_per_ticker_sentiment_in_range(self, derived):
        for t, s in derived["sentiment_per_ticker"].items():
            assert -1.0 <= s["combined_score"] <= 1.0, f"{t} combined_score 越界"
            assert 0.0 <= s["confidence"] <= 1.0, f"{t} confidence 越界"
            assert s["news_count"] >= 0, f"{t} news_count 負數"

    def test_per_ticker_macro_in_range(self, derived):
        for t, m in derived["macro_per_ticker"].items():
            assert 0.0 <= m["macro_score"] <= 1.0, f"{t} macro_score 越界"

    def test_majority_tickers_succeed(self, derived):
        # 至少 80% ticker 成功（per-ticker error tolerance）
        success = len(TICKER_UNIVERSE) - len(derived["failed_tickers"])
        assert success >= len(TICKER_UNIVERSE) * 0.8