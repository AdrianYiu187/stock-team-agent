"""v5.21 P3 — Three-tier fixture loader tests.

Mock fixture_cache 來避免 yfinance 網路依賴。

涵蓋:
1. mode='live' — tier 1 only
2. mode='frozen' — tier 2 only
3. mode='hybrid' — tier 1 + tier 2 fallback
4. Tier 1 fail + Tier 2 available → fallback to hardcoded
5. Tier 1 + Tier 2 都缺 → raise
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_sources import three_tier_loader  # noqa: E402


FIXTURES_PATH = SCRIPTS_DIR / "tests" / "fixtures" / "tickers_fundamentals.json"


@pytest.fixture
def hardcoded_data():
    return {
        "fundamentals": {
            "AAPL": {"pe": 30.0, "roe": 0.5, "peg": 1.5, "growth": 0.1},
            "MSFT": {"pe": 25.0, "roe": 0.3, "peg": 1.2, "growth": 0.15},
            "0700.HK": {"pe": 20.0, "roe": 0.2, "peg": 1.0, "growth": 0.08},
        },
        "tickers": ["AAPL", "MSFT", "0700.HK"],
    }


class TestThreeTierLoader:
    """v5.21 P3 three_tier_loader.py."""

    def test_frozen_mode_uses_hardcoded(self, hardcoded_data):
        """mode='frozen' 必用 hardcoded,不走 yfinance."""
        with patch.object(three_tier_loader, "_load_hardcoded_fixtures", return_value=hardcoded_data):
            result = three_tier_loader.load_fundamentals_three_tier(
                ["AAPL", "MSFT"], mode="frozen"
            )
        assert result["source"] == "hardcoded"
        assert result["fundamentals"]["AAPL"]["pe"] == 30.0
        assert result["source_per_ticker"]["AAPL"] == "hardcoded"
        assert result["missing"] == []

    def test_frozen_mode_missing_ticker_raises(self, hardcoded_data):
        """frozen mode 缺 ticker → raise."""
        with patch.object(three_tier_loader, "_load_hardcoded_fixtures", return_value=hardcoded_data):
            with pytest.raises(RuntimeError, match="hardcoded fixtures 缺 ticker"):
                three_tier_loader.load_fundamentals_three_tier(
                    ["AAPL", "UNKNOWN_TICKER"], mode="frozen"
                )

    def test_frozen_mode_no_hardcoded_file_raises(self):
        """frozen mode 但 hardcoded 不存在 → raise."""
        with patch.object(three_tier_loader, "_load_hardcoded_fixtures", return_value=None):
            with pytest.raises(RuntimeError, match="hardcoded fixtures"):
                three_tier_loader.load_fundamentals_three_tier(["AAPL"], mode="frozen")

    def test_live_mode_all_success(self):
        """mode='live' 全部 ticker live 成功."""
        def fake_get_all_fundamentals(tickers, force_refresh=False):
            return {
                t: {"pe": 25.0, "roe": 0.3, "peg": 1.5, "growth": 0.1,
                    "fetched_at": "2026-06-30T12:00:00+00:00", "source": "live"}
                for t in tickers
            }
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_get_all_fundamentals):
            result = three_tier_loader.load_fundamentals_three_tier(
                ["AAPL", "MSFT"], mode="live"
            )
        assert result["source"] == "live"
        assert result["fundamentals"]["AAPL"]["pe"] == 25.0
        # 內部欄位應被 strip
        assert "fetched_at" not in result["fundamentals"]["AAPL"]
        assert "source" not in result["fundamentals"]["AAPL"]

    def test_live_mode_partial_failure_raises(self):
        """live mode 部分 ticker 缺 → raise."""
        def fake_get_all_fundamentals(tickers, force_refresh=False):
            # 只回 AAPL,缺 MSFT
            return {
                "AAPL": {"pe": 25.0, "roe": 0.3, "peg": 1.5, "growth": 0.1,
                         "fetched_at": "2026-06-30T12:00:00+00:00", "source": "live"}
            }
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_get_all_fundamentals):
            with pytest.raises(RuntimeError, match="ticker 失敗且無可用 cache"):
                three_tier_loader.load_fundamentals_three_tier(
                    ["AAPL", "MSFT"], mode="live"
                )

    def test_hybrid_mode_fallback_to_hardcoded(self, hardcoded_data):
        """hybrid mode: live 缺 → fallback hardcoded."""
        def fake_get_all_fundamentals(tickers, force_refresh=False):
            # 只有 AAPL 從 live 來,MSFT 完全沒回 (yfinance 失敗)
            return {
                "AAPL": {"pe": 28.0, "roe": 0.4, "peg": 1.3, "growth": 0.12,
                         "fetched_at": "2026-06-30T12:00:00+00:00", "source": "live"}
            }
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_get_all_fundamentals), \
             patch.object(three_tier_loader, "_load_hardcoded_fixtures", return_value=hardcoded_data):
            result = three_tier_loader.load_fundamentals_three_tier(
                ["AAPL", "MSFT"], mode="hybrid"
            )
        assert result["source"] == "mixed"
        # AAPL 從 live 來
        assert result["source_per_ticker"]["AAPL"] == "live"
        assert result["fundamentals"]["AAPL"]["pe"] == 28.0
        # MSFT 從 hardcoded fallback
        assert result["source_per_ticker"]["MSFT"] == "hardcoded"
        assert result["fundamentals"]["MSFT"]["pe"] == 25.0
        assert result["partial"] == ["MSFT"]
        assert result["missing"] == []

    def test_hybrid_mode_both_layers_missing_raises(self, hardcoded_data):
        """hybrid mode: live + hardcoded 都缺 → raise."""
        def fake_get_all_fundamentals(tickers, force_refresh=False):
            return {}
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_get_all_fundamentals), \
             patch.object(three_tier_loader, "_load_hardcoded_fixtures", return_value=hardcoded_data):
            with pytest.raises(RuntimeError, match="連 hardcoded 也缺"):
                three_tier_loader.load_fundamentals_three_tier(
                    ["AAPL", "NEW_TICKER"], mode="hybrid"
                )

    def test_hybrid_mode_only_hardcoded(self, hardcoded_data):
        """hybrid mode: live 完全失敗,全部 fallback hardcoded."""
        def fake_get_all_fundamentals(tickers, force_refresh=False):
            return {}
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_get_all_fundamentals), \
             patch.object(three_tier_loader, "_load_hardcoded_fixtures", return_value=hardcoded_data):
            result = three_tier_loader.load_fundamentals_three_tier(
                ["AAPL", "MSFT"], mode="hybrid"
            )
        assert result["source"] == "hardcoded"
        assert result["partial"] == ["AAPL", "MSFT"]
        assert all(s == "hardcoded" for s in result["source_per_ticker"].values())

    def test_source_detection(self, hardcoded_data):
        """overall source 正確判定 (live / cache / mixed / hardcoded)."""
        def fake_live_only(tickers, force_refresh=False):
            return {
                t: {"pe": 20.0, "roe": 0.2, "peg": 1.0, "growth": 0.05,
                    "fetched_at": "2026-06-30T12:00:00+00:00", "source": "live"}
                for t in tickers
            }
        def fake_cache_only(tickers, force_refresh=False):
            return {
                t: {"pe": 20.0, "roe": 0.2, "peg": 1.0, "growth": 0.05,
                    "fetched_at": "2026-06-30T12:00:00+00:00", "source": "cache"}
                for t in tickers
            }
        # all live
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_live_only):
            r = three_tier_loader.load_fundamentals_three_tier(["AAPL"], mode="live")
        assert r["source"] == "live"
        # all cache
        with patch.object(three_tier_loader, "get_all_fundamentals", fake_cache_only):
            r = three_tier_loader.load_fundamentals_three_tier(["AAPL"], mode="live")
        assert r["source"] == "cache"
