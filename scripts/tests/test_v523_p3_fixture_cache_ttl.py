"""v5.23 P3 — fixture_cache stale-tolerance TTL 7→14 days guard.

Per docs/v5.23_roadmap.md §P3:
- v5.21 design §2.3 寫 DEFAULT_STALE_TOLERANCE_DAYS = 7
- v5.23 量化: live mode weekend window (Fri→Mon) yfinance 5% 失敗率,
  7 天 stale tolerance 在跨週失敗 cascade 時仍不夠安全。
- 升級到 14 天 (Rule 3「精準修改」僅 1 個常數)。
- Lesson #49: 此 guard 永久化,防止未來 revert 默默改回 7。

TDD 紅→綠:
1. test_default_stale_tolerance_days_is_14 → fixture_cache.DEFAULT_STALE_TOLERANCE_DAYS == 14
2. test_stale_fallback_within_14_days_works → 8 天前 cache 在 yfinance 失敗時仍然 fallback 成功 (不 raise)
3. test_stale_fallback_past_14_days_raises → 15 天前 cache 仍 raise RuntimeError (邊界正確)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.data_sources import fixture_cache  # noqa: E402
from scripts.data_sources.fixture_cache import (  # noqa: E402
    DEFAULT_STALE_TOLERANCE_DAYS,
    _write_cache,
    get_fundamentals,
)


def _make_cache_data(age_days: float) -> dict:
    """製造 age_days 前 fetched_at 的 cache data。"""
    fetched_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {
        "pe": 15.0,
        "roe": 0.20,
        "peg": 1.5,
        "growth": 0.10,
        "fetched_at": fetched_at.isoformat(),
        "source": "cache",
    }


def test_default_stale_tolerance_days_is_14():
    """P3: TTL 必須 = 14,不是 7 (防止未來 revert)。"""
    assert DEFAULT_STALE_TOLERANCE_DAYS == 14, (
        f"v5.23 P3 要求 DEFAULT_STALE_TOLERANCE_DAYS=14, 實際 {DEFAULT_STALE_TOLERANCE_DAYS}"
    )


def test_stale_fallback_within_14_days_works(tmp_path):
    """P3+邊界: 8 天前 cache (within 14 days) 在 fetcher 失敗時要 fallback,不能 raise。"""
    # 用 monkeypatch 把 CACHE_DIR 導到 tmp_path 避免污染真實 .cache/
    fake_cache_dir = tmp_path / ".cache" / "fundamentals"
    fake_cache_dir.mkdir(parents=True)
    # 把 8 天前 cache 寫進 tmp_path
    eight_days_ago = _make_cache_data(8.0)
    (fake_cache_dir / "TEST_P3_OK.json").write_text(
        __import__("json").dumps(eight_days_ago, ensure_ascii=False),
        encoding="utf-8",
    )

    def failing_fetcher(ticker: str):
        raise RuntimeError("yfinance down (simulated)")

    with patch.object(fixture_cache, "CACHE_DIR", fake_cache_dir):
        result = get_fundamentals("TEST_P3_OK", fetcher=failing_fetcher)

    assert result["source"] == "stale_fallback", (
        f"8 天前 cache 應該 stale_fallback,實際 {result['source']}"
    )
    assert result["pe"] == 15.0


def test_stale_fallback_past_14_days_raises(tmp_path):
    """P3+邊界: 15 天前 cache (超過 14 天) 必須 raise RuntimeError (不可用 fallback)。"""
    fake_cache_dir = tmp_path / ".cache" / "fundamentals"
    fake_cache_dir.mkdir(parents=True)
    fifteen_days_ago = _make_cache_data(15.0)
    (fake_cache_dir / "TEST_P3_OLD.json").write_text(
        __import__("json").dumps(fifteen_days_ago, ensure_ascii=False),
        encoding="utf-8",
    )

    def failing_fetcher(ticker: str):
        raise RuntimeError("yfinance down (simulated)")

    with patch.object(fixture_cache, "CACHE_DIR", fake_cache_dir):
        with pytest.raises(RuntimeError, match="無可用 cache"):
            get_fundamentals("TEST_P3_OLD", fetcher=failing_fetcher)
