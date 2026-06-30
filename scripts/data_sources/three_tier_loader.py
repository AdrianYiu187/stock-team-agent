"""v5.21 — Three-tier fixture loader (live + cache + hardcoded fallback).

設計 (per docs/v5.21_live_fixtures_design.md §2.5 + 用戶批准 C 選項):
Tier 1: yfinance live fetch with 24h TTL cache (fixture_cache.get_all_fundamentals)
Tier 2: Hardcoded scripts/tests/fixtures/tickers_fundamentals.json (v5.20 snapshot)
Tier 3: Per-ticker error (ticker 完全無法取得)

v5.23 P1 — cap_coverage_report() API (per docs/v5.23_roadmap.md §P1 + Lesson #50):
量化 score function 在 param_range 內的 cap-zone coverage。
從 v5.22 Stage B-0 N=50000 standalone 腳本 → reusable API。
讓任何 score_fn + param_range → {coverage, is_by_design, threshold_value}
都能量化 cap-zone 比例,避免每次重新 audit 都重跑整個 sweep。

使用:
    from data_sources.three_tier_loader import cap_coverage_report

    # 量化 PEG>5 真實 cap-zone 比例
    result = cap_coverage_report(
        score_fn=lambda peg: fund_score_multifactor(20.0, 0.15, peg, 0.10),
        param_name="peg_val",
        param_range=(0.0, 50.0),
        cap_threshold=0.10,  # PEG>5 cap-zone 定義: peg_factor<=0.10
        n_samples=10000,
    )
    # result = {"coverage": 0.91, "is_by_design": False,
    #            "threshold_value": 5.0, "param_name": "peg_val",
    #            "score_min": 0.05, "score_max": 0.95}

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
from typing import Callable, Literal

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


# v5.23 P1 — cap_coverage_report() API (per docs/v5.23_roadmap.md §P1 + Lesson #50)

# By-design cap-zone coverage 閾值 (per v5.22 Stage B-0 N=50000 結論)
# 真實樣本 cap-zone > 0.5% → 真實 pitfall 需修
# 真實樣本 cap-zone ≤ 0.5% → by-design 保留
DEFAULT_BY_DESIGN_THRESHOLD = 0.005  # 0.5%


def cap_coverage_report(
    score_fn: Callable[[float], float],
    param_name: str,
    param_range: tuple[float, float],
    cap_threshold: float,
    n_samples: int = 10000,
    by_design_threshold: float = DEFAULT_BY_DESIGN_THRESHOLD,
) -> dict:
    """量化 score_fn 在 param_range 內的 cap-zone coverage。

    Args:
        score_fn: 接收 1 個 float param value, 回傳 score (float 0..1)
                  Important: 應該傳 *_factor 函數(如 peg_factor), 不是 fund_score_multifactor
                  weighted composite。否則 cap-zone 會被其他因子稀釋看不到。
        param_name: param 名稱 (e.g. "peg_val", "roe", "beta")
        param_range: (min, max) uniform sweep range
        cap_threshold: cap-zone 定義 (e.g. 0.10 = score<=0.10 視為 cap-zone)
        n_samples: sample count (default 10000,Stage B-0 用 50000 需顯式調高)
        by_design_threshold: ≤ 此比例視為 by-design 保留 (default 0.005 = 0.5%)

    Returns:
        {
            "coverage": float,           # cap-zone 比例 (0..1)
            "is_by_design": bool,        # coverage ≤ by_design_threshold → True
            "threshold_value": float,    # param_range[0] + coverage*range (cap 起點推測)
            "param_name": str,           # 傳入的 param_name
            "score_min": float,          # 最小 score
            "score_max": float,          # 最大 score
            "n_samples": int,            # 實際 sample count
            "cap_zone_samples": int,     # 落在 cap-zone 的樣本數
        }

    Design (per v5.22 Stage B-0 + Lesson #48 + #50):
    - Uniform sweep in param_range
    - score <= cap_threshold 視為 cap-zone (cap 通常是 floor)
    - by_design 判斷:coverage ≤ by_design_threshold (default 0.5%)

    IMPORTANT (per Lesson #48):
    - 必須傳 *_factor helper, 非 fund_score_multifactor weighted composite
    - 否則 cap-zone 被其他因子稀釋看起來像 0%, 誤判 by-design

    Lesson #48 lesson: 不要只看「單調遞減」就判定 pitfall,要量化真實分布 cap-zone
                     coverage 是否 > 0.5%。Stage B-0 N=50000 排除 5 false-positive。
    """
    if param_range[0] >= param_range[1]:
        raise ValueError(
            f"❌ param_range[0] ({param_range[0]}) 必須 < param_range[1] ({param_range[1]})"
        )
    if n_samples < 10:
        raise ValueError(f"❌ n_samples ({n_samples}) 太少,最少 10")

    lo, hi = param_range
    step = (hi - lo) / (n_samples - 1)
    samples = [lo + i * step for i in range(n_samples)]

    scores = [score_fn(x) for x in samples]
    cap_zone_count = sum(1 for s in scores if s <= cap_threshold)
    coverage = cap_zone_count / n_samples

    score_min = min(scores)
    score_max = max(scores)

    # threshold_value: cap-zone 第一個 sample 的 param value (推測 cap 起點)
    threshold_value = samples[0]
    for x, s in zip(samples, scores):
        if s <= cap_threshold:
            threshold_value = x
            break

    return {
        "coverage": coverage,
        "is_by_design": coverage <= by_design_threshold,
        "threshold_value": threshold_value,
        "param_name": param_name,
        "score_min": score_min,
        "score_max": score_max,
        "n_samples": n_samples,
        "cap_zone_samples": cap_zone_count,
    }
