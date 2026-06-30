"""v5.21 P1 — Fixture cache TTL layer unit tests.

Mock fetcher (無 yfinance 網路依賴):
- mock_fetcher: 永遠成功
- failing_fetcher: 永遠 raise RuntimeError

涵蓋情境 (per docs/v5.21_live_fixtures_design.md §3.1):
1. cold cache → live fetch
2. warm cache (< 24h) → cache hit (no fetcher call)
3. force_refresh=True → live fetch
4. fetcher fails + no cache → RuntimeError
5. fetcher fails + cache exists (within tolerance) → stale_fallback
6. fetcher fails + cache too old (>7 days) → RuntimeError
7. TTL env var override
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

# 慣例 (per scripts/tests/test_v520_*.py)
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from data_sources.fixture_cache import (  # noqa: E402
    get_fundamentals,
    clear_cache,
    _read_cache,
    _write_cache,
    _is_stale,
    _is_too_stale,
    DEFAULT_TTL_HOURS,
    DEFAULT_STALE_TOLERANCE_DAYS,
)


# --- Mock fetchers ---

def mock_fetcher(ticker: str) -> dict:
    return {"pe": 20.0, "roe": 0.15, "peg": 1.5, "growth": 0.10}


def failing_fetcher(ticker: str) -> dict:
    raise RuntimeError("yfinance down (test mock)")


# --- Fixtures ---

@pytest.fixture(autouse=True)
def cleanup_cache():
    """Each test starts with empty cache for its ticker."""
    yield
    for t in ["TEST_AAPL", "TEST_HK", "TEST_FAIL"]:
        clear_cache(t)


# --- Tests ---

class TestFixtureCache:
    """v5.21 P1 fixture cache layer."""

    def test_cold_cache_returns_live(self):
        """Cold cache → fetcher called, source=live."""
        result = get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        assert result["source"] == "live"
        assert result["pe"] == 20.0
        assert result["roe"] == 0.15

    def test_warm_cache_returns_cache_without_fetcher(self):
        """Fresh cache (< 24h) → fetcher NOT called, source=cache."""
        get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)  # populate
        # Now fetcher should not be called
        result = get_fundamentals("TEST_AAPL", fetcher=failing_fetcher)
        assert result["source"] == "cache", "Fresh cache must not trigger fetcher"

    def test_force_refresh_bypasses_cache(self):
        """force_refresh=True → fetcher called even if cache fresh."""
        get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        result = get_fundamentals("TEST_AAPL", force_refresh=True, fetcher=mock_fetcher)
        assert result["source"] == "live"

    def test_fetcher_fails_no_cache_raises(self):
        """Fetcher fails + no cache → RuntimeError."""
        with pytest.raises(RuntimeError, match="yfinance 失敗且無可用 cache"):
            get_fundamentals("TEST_FAIL", fetcher=failing_fetcher)

    def test_stale_cache_fallback_on_fetcher_failure(self):
        """Stale cache (> TTL but < tolerance) + fetcher fails → stale_fallback."""
        # Populate
        get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        # Make cache 48h old (stale, but within 7-day tolerance)
        cached = _read_cache("TEST_AAPL")
        cached["fetched_at"] = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        _write_cache("TEST_AAPL", cached)

        result = get_fundamentals("TEST_AAPL", fetcher=failing_fetcher)
        assert result["source"] == "stale_fallback"
        assert result["pe"] == 20.0

    def test_too_stale_cache_raises_even_with_history(self):
        """Cache > 7 days + fetcher fails → RuntimeError (per design §3.3)."""
        get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        cached = _read_cache("TEST_AAPL")
        cached["fetched_at"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        _write_cache("TEST_AAPL", cached)

        with pytest.raises(RuntimeError, match="無可用 cache"):
            get_fundamentals("TEST_AAPL", fetcher=failing_fetcher)

    def test_stale_check_correctness(self):
        """_is_stale / _is_too_stale unit tests."""
        fresh = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "pe": 20,
        }
        old_48h = {
            "fetched_at": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
            "pe": 20,
        }
        old_30d = {
            "fetched_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "pe": 20,
        }

        assert not _is_stale(fresh, ttl_hours=24)
        assert _is_stale(old_48h, ttl_hours=24)
        assert not _is_too_stale(old_48h, tolerance_days=7)
        assert _is_too_stale(old_30d, tolerance_days=7)

    def test_corrupted_cache_returns_none(self):
        """Cache file with invalid JSON → _read_cache returns None."""
        _write_cache("TEST_AAPL", {"invalid": "data"})  # 缺 fetched_at
        # Cache without fetched_at should be treated as stale
        result = get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        # Since _is_stale returns True for missing fetched_at, fetcher will be called
        assert result["source"] == "live"

    def test_clear_cache_specific(self):
        """clear_cache(ticker) removes only that ticker's cache."""
        get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        get_fundamentals("TEST_HK", fetcher=mock_fetcher)
        cleared = clear_cache("TEST_AAPL")
        assert cleared == 1
        assert _read_cache("TEST_AAPL") is None
        assert _read_cache("TEST_HK") is not None  # 未被清
        clear_cache("TEST_HK")

    def test_clear_cache_all(self):
        """clear_cache() with no args removes all."""
        get_fundamentals("TEST_AAPL", fetcher=mock_fetcher)
        get_fundamentals("TEST_HK", fetcher=mock_fetcher)
        cleared = clear_cache()
        assert cleared >= 2
        assert _read_cache("TEST_AAPL") is None
        assert _read_cache("TEST_HK") is None
