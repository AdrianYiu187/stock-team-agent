"""v5.21 — TTL-based fixture cache layer for yfinance fundamentals.

設計 (per docs/v5.21_live_fixtures_design.md §2.3):
- Cache key: ticker (e.g. "AAPL")
- Cache value: {pe, roe, peg, growth, fetched_at, source}
- TTL: 24h (default, overridable via FIXTURE_TTL_HOURS env var)
- Storage: scripts/tests/fixtures/.cache/fundamentals/<TICKER>.json
- Stale tolerance: 7 days (stale cache fallback if yfinance raises)

Backward compat:
- 既有 tickers_fundamentals.json 不刪除，繼續存在 repo（frozen mode 用）
- 新 .cache/ 加進 .gitignore
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# v5.21 design §3.3 — cache 路徑
CACHE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / ".cache" / "fundamentals"

# v5.21 A — 全批准預設
DEFAULT_TTL_HOURS = 24
# v5.23 P3 — 7 → 14 days (live mode weekend window yfinance 5% 失敗率 + cross-week cascade)
DEFAULT_STALE_TOLERANCE_DAYS = 14


def _get_ttl_hours() -> int:
    """Read TTL from env, fallback to default."""
    try:
        return int(os.environ.get("FIXTURE_TTL_HOURS", str(DEFAULT_TTL_HOURS)))
    except (ValueError, TypeError):
        return DEFAULT_TTL_HOURS


def _read_cache(ticker: str) -> dict | None:
    """Read cache file for ticker. Returns None if not exists or corrupted."""
    cache_path = CACHE_DIR / f"{ticker.replace('.', '_').replace('/', '_')}.json"
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  {ticker} cache corrupted: {e}", file=sys.stderr)
        return None


def _write_cache(ticker: str, data: dict) -> None:
    """Write cache file for ticker. Creates CACHE_DIR if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{ticker.replace('.', '_').replace('/', '_')}.json"
    cache_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _is_stale(data: dict, ttl_hours: int) -> bool:
    """Check if cache entry is older than TTL."""
    try:
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        age = datetime.now(timezone.utc) - fetched_at
        return age > timedelta(hours=ttl_hours)
    except (KeyError, ValueError, TypeError):
        return True  # 缺欄位或格式錯視為 stale


def _is_too_stale(data: dict, tolerance_days: int) -> bool:
    """Check if cache entry exceeds stale tolerance (fallback 不可用)."""
    try:
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        age = datetime.now(timezone.utc) - fetched_at
        return age > timedelta(days=tolerance_days)
    except (KeyError, ValueError, TypeError):
        return True


def get_fundamentals(
    ticker: str,
    *,
    force_refresh: bool = False,
    fetcher=None,
) -> dict:
    """Get fundamentals for ticker with TTL cache layer.

    Args:
        ticker: e.g. "AAPL", "0700.HK", "600519.SS"
        force_refresh: bypass TTL check, always re-fetch
        fetcher: callable(ticker) -> {pe, roe, peg, growth}
                 Defaults to yfinance_fundamentals.fetch_one()
                 (lazy import to avoid yfinance import cost in pytest)

    Returns:
        {pe, roe, peg, growth, fetched_at, source}
        source ∈ {"cache" | "live" | "stale_fallback"}

    Raises:
        RuntimeError: if yfinance fails AND no cache exists (or cache too old)
    """
    if fetcher is None:
        # Lazy import — pytest with --frozen-fixtures 不需 yfinance
        from scripts.data_sources.yfinance_fundamentals import fetch_one
        fetcher = fetch_one

    ttl_hours = _get_ttl_hours()
    cached = _read_cache(ticker)

    # Cache hit + fresh → use cache
    if cached and not _is_stale(cached, ttl_hours) and not force_refresh:
        return {**cached, "source": "cache"}

    # Try live fetch
    try:
        fresh = fetcher(ticker)
        enriched = {
            **fresh,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": "live",
        }
        _write_cache(ticker, enriched)
        return enriched
    except Exception as e:
        # Stale fallback per v5.21 §3.3
        if cached and not _is_too_stale(cached, DEFAULT_STALE_TOLERANCE_DAYS):
            print(
                f"⚠️  {ticker} yfinance 失敗，使用 {DEFAULT_STALE_TOLERANCE_DAYS} 天內 stale cache: {e}",
                file=sys.stderr,
            )
            return {**cached, "source": "stale_fallback"}
        # No usable cache → fail
        raise RuntimeError(
            f"❌ {ticker} yfinance 失敗且無可用 cache (>{DEFAULT_STALE_TOLERANCE_DAYS} 天): {e}"
        ) from e


def get_all_fundamentals(
    tickers: list[str],
    *,
    force_refresh: bool = False,
) -> dict[str, dict]:
    """Get fundamentals for multiple tickers. Per-ticker fail tolerance.

    Returns:
        {ticker: {pe, roe, peg, growth, fetched_at, source}, ...}
        Failed tickers are excluded. Caller should check len(result) vs len(tickers).
    """
    out: dict[str, dict] = {}
    failed: list[str] = []
    for t in tickers:
        try:
            out[t] = get_fundamentals(t, force_refresh=force_refresh)
        except Exception as e:
            print(f"⚠️  {t} fixture_cache failed: {e}", file=sys.stderr)
            failed.append(t)
    if failed:
        print(f"⚠️  {len(failed)}/{len(tickers)} ticker failed: {failed}", file=sys.stderr)
    return out


def clear_cache(ticker: str | None = None) -> int:
    """Clear cache file(s). Returns count of cleared files.

    Args:
        ticker: specific ticker, or None to clear all
    """
    if not CACHE_DIR.exists():
        return 0
    if ticker:
        path = CACHE_DIR / f"{ticker.replace('.', '_').replace('/', '_')}.json"
        if path.exists():
            path.unlink()
            return 1
        return 0
    count = 0
    for p in CACHE_DIR.glob("*.json"):
        p.unlink()
        count += 1
    return count
