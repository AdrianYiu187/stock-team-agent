"""v5.21 — yfinance fundamentals wrapper with per-ticker error tolerance.

設計 (per docs/v5.21_live_fixtures_design.md §2.1):
- 從 cross_market_real_yfinance_e2e.py:fetch_fundamentals() 抽取
- 抽出原因是 fixture_cache.py 需要 callable fetcher
- 保留原本的 per-ticker fail tolerance (P45)
"""

from __future__ import annotations

from typing import Optional


def fetch_one(ticker: str) -> dict:
    """從 yfinance 拉單 ticker 真實 fundamentals.

    Returns:
        {pe, roe, peg, growth} — 4 個核心欄位

    Raises:
        RuntimeError: if yfinance returns empty info or critical fields missing
    """
    import yfinance as yf  # lazy import

    info = yf.Ticker(ticker).info
    if not info:
        raise RuntimeError(f"yfinance returned empty info for {ticker}")

    pe = info.get("trailingPE") or 0
    roe = info.get("returnOnEquity") or 0
    peg = info.get("pegRatio")
    growth = info.get("revenueGrowth") or 0

    # Sanity check — AAPL yfinance 通常 4 個欄位都有值
    # 若全 0 或 None，可能是 ticker 錯誤或 yfinance rate limit
    if pe == 0 and roe == 0 and growth == 0 and peg is None:
        raise RuntimeError(
            f"{ticker} yfinance returned all-zero fundamentals "
            f"(可能 ticker 錯或 rate limit). Raw keys: {list(info.keys())[:10]}"
        )

    return {
        "pe": pe,
        "roe": roe,
        "peg": peg,
        "growth": growth,
    }


def fetch_all(tickers: list[str]) -> dict:
    """從 yfinance 拉多 ticker 真實 fundamentals（per-ticker fail tolerance）.

    Returns:
        {
            "fundamentals": {ticker: {pe, roe, peg, growth}, ...},
            "failed": [ticker, ...],
        }
    """
    out: dict[str, dict] = {}
    failed: list[str] = []
    for t in tickers:
        try:
            out[t] = fetch_one(t)
        except Exception as e:
            print(f"⚠️  {t} yfinance 拉取失敗：{e}")
            failed.append(t)
    if failed:
        print(f"⚠️  {len(failed)}/{len(tickers)} ticker 失敗：{failed}")
    return {"fundamentals": out, "failed": failed}
