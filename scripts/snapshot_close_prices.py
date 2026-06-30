"""v5.26 P1 — Snapshot 11 ticker close prices 從 yfinance 一次性寫入 fixture。

Purpose:
    Per Lesson #53 (mock ≠ 真實) + Lesson #54 候選 (mock GBM 適用範圍):
    從 yfinance 拉 11 ticker × 120 day close prices, 寫入
    tests/fixtures/tickers_fundamentals.json 的 close_prices key。

Why one-shot CLI:
    - 凍結 yfinance snapshot 到 fixture 後, pytest/CI 無網路依賴
    - 確保 audit chain 重跑結果一致 (git-committed fixture)

Usage:
    python scripts/snapshot_close_prices.py [--period 6mo] [--output tests/fixtures/tickers_fundamentals.json]

Risks:
    - yfinance network failure → fallback 寫 _meta.snapshot_failed=True
    - Ticker 退市 → 該 ticker 跳過, log warning
    - 輸出 fixture 變大 (~11KB) → round(4 decimals) 壓縮
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union  # noqa: F401
# 確保 scripts/ 在 path 中 (用 cross_market_real_yfinance_e2e 既有 TICKER_UNIVERSE)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cross_market_real_yfinance_e2e import TICKER_UNIVERSE  # noqa: E402

FIXTURES_PATH_DEFAULT = (
    Path(__file__).resolve().parent / "tests" / "fixtures" / "tickers_fundamentals.json"
)


def fetch_one_close_series(ticker: str, period: str = "6mo") -> list[float]:
    """從 yfinance 拉單 ticker close prices (length ≈ 120 day)。"""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance 未安裝; pip install yfinance")
    t = yf.Ticker(ticker)
    hist = t.history(period=period, auto_adjust=False)
    if hist is None or len(hist) == 0:
        return []
    closes = hist["Close"].dropna().tolist()
    # Round to 4 decimals (compress fixture)
    return [round(float(c), 4) for c in closes]


def snapshot_close_prices(
    tickers: list[str] | None = None,
    period: str = "6mo",
    fixtures_path: Path = FIXTURES_PATH_DEFAULT,
    target_length: int = 120,
) -> dict:
    """從 yfinance 拉所有 ticker close prices, 寫入 fixture。

    Args:
        tickers: 自訂 ticker list (default = TICKER_UNIVERSE 11 ticker)
        period: yfinance period (default "6mo" ≈ 126 trading day > 120)
        fixtures_path: 輸出 fixture path
        target_length: 對齊 backtest n_days=120

    Returns:
        dict 含 per-ticker close_prices + snapshot metadata
    """
    if tickers is None:
        tickers = list(TICKER_UNIVERSE)

    close_prices: dict[str, list[float]] = {}
    failed: list[str] = []
    snapshot_date = datetime.now(timezone.utc).isoformat()

    for ticker in tickers:
        try:
            prices = fetch_one_close_series(ticker, period=period)
            if not prices:
                print(f"⚠️  {ticker}: yfinance 無數據, 跳過")
                failed.append(ticker)
                continue
            # 對齊 target_length: 取最後 target_length days
            if len(prices) >= target_length:
                prices = prices[-target_length:]
            else:
                print(f"⚠️  {ticker}: 只有 {len(prices)} 天 (< {target_length}), 仍寫入")
            close_prices[ticker] = prices
            print(f"✅ {ticker}: {len(prices)} days, "
                  f"min={min(prices):.2f} max={max(prices):.2f}")
        except Exception as e:
            print(f"❌ {ticker}: {e}")
            failed.append(ticker)

    # 寫入 fixture (merge to existing close_prices key)
    if fixtures_path.exists():
        with open(fixtures_path, "r", encoding="utf-8") as f:
            fixture = json.load(f)
    else:
        fixture = {}

    fixture["close_prices"] = close_prices
    meta = fixture.setdefault("_meta", {})
    meta["close_prices_snapshot"] = {
        "snapshot_date": snapshot_date,
        "period": period,
        "target_length": target_length,
        "source": "yfinance real fetch (v5.26 P1)",
        "n_tickers": len(close_prices),
        "failed_tickers": failed,
    }

    fixtures_path.parent.mkdir(parents=True, exist_ok=True)
    with open(fixtures_path, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)

    print(f"\n[完成] close_prices 寫入 {fixtures_path}")
    print(f"  成功: {len(close_prices)}/{len(tickers)} tickers")
    print(f"  失敗: {len(failed)} tickers {failed if failed else ''}")

    return {
        "close_prices": close_prices,
        "failed_tickers": failed,
        "snapshot_date": snapshot_date,
    }


def main():
    parser = argparse.ArgumentParser(description="v5.26 P1: Snapshot close prices from yfinance")
    parser.add_argument("--period", default="6mo",
                        help="yfinance period (default 6mo ≈ 126 trading day)")
    parser.add_argument("--output", type=Path, default=FIXTURES_PATH_DEFAULT,
                        help="輸出 fixture path")
    parser.add_argument("--target-length", type=int, default=120,
                        help="對齊 backtest n_days (default 120)")
    args = parser.parse_args()

    snapshot_close_prices(
        period=args.period,
        fixtures_path=args.output,
        target_length=args.target_length,
    )


if __name__ == "__main__":
    main()