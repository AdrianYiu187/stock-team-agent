"""v5.21 — Three-tier fixture loader (live + cache + hardcoded fallback).

設計 (per docs/v5.21_live_fixtures_design.md §2.5 + 用戶批准 C 選項):
Tier 1: yfinance live fetch with 24h TTL cache (fixture_cache.get_all_fundamentals)
Tier 2: Hardcoded scripts/tests/fixtures/tickers_fundamentals.json (v5.20 snapshot)
Tier 3: Per-ticker error (ticker 完全無法取得)

使用:
    from data_sources.three_tier_loader import load_fundamentals_three_tier

    # Default: live + cache + hardcoded fallback
    fx = load_fundamentals_three_tier(['AAPL', '0700.HK'])
    # fx['fundamentals'] = {ticker: {pe, roe, peg, growth}, ...}
    # fx['source'] = 'live' | 'cache' | 'hardcoded'
    # fx['missing'] = [ticker 完全沒資料的]
    # fx['partial'] = [ticker 只有 hardcoded]

    # Frozen mode (CI / 完全離線)
    fx = load_fundamentals_three_tier(['AAPL'], mode='frozen')
    # 必用 hardcoded,失敗就 fail

Backward compat:
- test_cross_market_real_yfinance_e2e.py 仍可 load_fixtures() (純 hardcoded)
- test_signal_distribution_per_ticker.py 仍可 load_fixtures() (純 hardcoded)
- 新增 load_fundamentals_three_tier() 給 P3 caller 整合用
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

# 確保 fixture_cache 可 import
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from data_sources.fixture_cache import get_all_fundamentals  # noqa: E402

FIXTURES_PATH = _SCRIPTS_DIR / "tests" / "fixtures" / "tickers_fundamentals.json"

# v5.21 — 三層載入模式
LoadMode = Literal["live", "frozen", "hybrid"]


def _load_hardcoded_fixtures() -> dict | None:
    """Tier 2: 讀 v5.20 hardcoded snapshot。"""
    if not FIXTURES_PATH.exists():
        return None
    try:
        return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Hardcoded fixtures corrupted: {e}", file=sys.stderr)
        return None


def load_fundamentals_three_tier(
    tickers: list[str],
    *,
    mode: LoadMode = "live",
    force_refresh: bool = False,
) -> dict:
    """三層 fallback 載入 fundamentals.

    Args:
        tickers: ticker list
        mode:
            "live" — Tier 1 only,失敗 ticker raise
            "frozen" — Tier 2 only (CI 離線用)
            "hybrid" — Tier 1 → 缺的部分自動 fallback 到 Tier 2
        force_refresh: 強制重抓 (bypass TTL cache)

    Returns:
        {
            'fundamentals': {ticker: {pe, roe, peg, growth}, ...},
            'source_per_ticker': {ticker: 'live'|'cache'|'hardcoded', ...},
            'source': 'live'|'cache'|'hardcoded'|'mixed',  # overall
            'missing': [完全沒資料的 ticker],
            'partial': [只有 hardcoded 的 ticker],
        }

    Raises:
        RuntimeError: mode='live' 時 ticker 失敗
        RuntimeError: mode='frozen' 時 hardcoded 缺 ticker
        RuntimeError: mode='hybrid' 時 ticker 連 hardcoded 也缺
    """
    if mode == "frozen":
        # Tier 2 only
        fx = _load_hardcoded_fixtures()
        if fx is None:
            raise RuntimeError(f"❌ Frozen mode: hardcoded fixtures {FIXTURES_PATH} 不存在或損壞")
        missing = [t for t in tickers if t not in fx.get("fundamentals", {})]
        if missing:
            raise RuntimeError(
                f"❌ Frozen mode: hardcoded fixtures 缺 ticker: {missing}"
            )
        return {
            "fundamentals": {t: fx["fundamentals"][t] for t in tickers},
            "source_per_ticker": {t: "hardcoded" for t in tickers},
            "source": "hardcoded",
            "missing": [],
            "partial": [],
        }

    if mode == "live":
        # Tier 1 only (24h TTL cache + live yfinance)
        result = get_all_fundamentals(tickers, force_refresh=force_refresh)
        if not result:
            raise RuntimeError("❌ Live mode: 全部 ticker 失敗")
        missing = [t for t in tickers if t not in result]
        if missing:
            raise RuntimeError(
                f"❌ Live mode: ticker 失敗且無可用 cache: {missing}"
            )
        # Determine overall source
        sources = {data.get("source", "unknown") for data in result.values()}
        if sources == {"live"}:
            overall = "live"
        elif sources == {"cache"}:
            overall = "cache"
        elif sources == {"stale_fallback"}:
            overall = "stale_fallback"
        else:
            overall = "mixed"
        # Strip internal metadata, return pure fundamentals
        fundamentals = {
            t: {k: v for k, v in data.items() if k not in ("fetched_at", "source")}
            for t, data in result.items()
        }
        return {
            "fundamentals": fundamentals,
            "source_per_ticker": {t: data.get("source", "unknown") for t, data in result.items()},
            "source": overall,
            "missing": missing,
            "partial": [],
        }

    # mode == "hybrid" — Tier 1 + Tier 2 fallback
    result = get_all_fundamentals(tickers, force_refresh=force_refresh)

    hardcoded_fx = _load_hardcoded_fixtures()
    hardcoded_fundamentals = hardcoded_fx.get("fundamentals", {}) if hardcoded_fx else {}

    fundamentals = {}
    source_per_ticker = {}
    partial = []
    final_missing = []

    for t in tickers:
        if t in result:
            data = result[t]
            fundamentals[t] = {k: v for k, v in data.items() if k not in ("fetched_at", "source")}
            source_per_ticker[t] = data.get("source", "unknown")
        elif t in hardcoded_fundamentals:
            fundamentals[t] = hardcoded_fundamentals[t]
            source_per_ticker[t] = "hardcoded"
            partial.append(t)
        else:
            final_missing.append(t)

    # Determine overall source
    sources = set(source_per_ticker.values())
    if not sources:
        overall = "empty"
    elif sources == {"live"}:
        overall = "live"
    elif sources == {"cache"}:
        overall = "cache"
    elif sources == {"stale_fallback"}:
        overall = "stale_fallback"
    elif sources == {"hardcoded"}:
        overall = "hardcoded"
    else:
        overall = "mixed"

    if final_missing:
        raise RuntimeError(
            f"❌ Hybrid mode: ticker 連 hardcoded 也缺: {final_missing}"
        )

    return {
        "fundamentals": fundamentals,
        "source_per_ticker": source_per_ticker,
        "source": overall,
        "missing": [],
        "partial": partial,
    }
