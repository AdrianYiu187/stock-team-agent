"""v5.16 P49 — 真實 sentiment + macro 派生（從 cross-market yfinance）。

設計：
  quantify_score_distribution.py P48a 用 sentiment=0.5 / macro=0.5 中性基線，
  這是 fallback（沒 sentiment/macro 數據時），但會遮蔽真實 analyst disagreement。

  本腳本從 yfinance 拉真實 sentiment（news keyword count）+ macro（market index），
  把 fixtures 從 5 role 擴展到 7 role，enable 真實 dynamic weighted_score_with_variance_penalty。

派生策略：
  sentiment_per_ticker[t] = (combined_score, confidence, news_count)
    - combined_score ∈ [-1, 1]: 從 yf.Ticker(t).news 標題算 positive/negative 比例
    - confidence ∈ [0, 1]: news_count / 60 (≥60 = 滿分，< 5 = 低信心)
    - news_count: 原始新聞數

  macro_indexes[t] = macro_score (0-1)
    - 從 ticker 對應的 market index 算：
      AAPL/MSFT/GOOGL/NVDA → ^GSPC (S&P 500)
      0700.HK/9988.HK/3690.HK → ^HSI (Hang Seng)
      600519.SS/000858.SZ/601318.SS/000333.SZ → 000001.SS (SSE Composite)
    - macro_score = 0.5 + 0.3 * sign(30d_return) * log1p(abs(30d_return)/vol)
    - macro_score clipped to [0.0, 1.0]

成功標準（Rule 4）：
  1. 11/11 ticker 派生成功（per-ticker error tolerance）
  2. sentiment combined_score ∈ [-1, 1]
  3. macro_score ∈ [0, 1]
  4. fixtures 加 sentiment_macro 段（不破壞既有 PE/ROE 結構）
  5. quantify_score_distribution.py 用真實派生後 entropy_delta 不為 0
  6. fixtures freshness < 90 days

Usage:
  # CLI 一次性（會觸 yfinance 網路）
  python scripts/derive_real_sentiment_macro.py

  # pytest 模式（用 fixtures，無網路）
  pytest scripts/tests/test_derive_real_sentiment_macro.py -v
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# 確保 scripts/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

# v5.16 P49 — 重用既有 TICKER_UNIVERSE + FIXTURES_PATH
from cross_market_real_yfinance_e2e import (  # noqa: E402
    FIXTURES_PATH,
    TICKER_UNIVERSE,
)

# v5.16 P49 — ticker → macro index 映射
TICKER_TO_MACRO_INDEX: dict[str, str] = {
    # US 大盤
    "AAPL": "^GSPC", "MSFT": "^GSPC", "GOOGL": "^GSPC", "NVDA": "^GSPC",
    # HK 恒生
    "0700.HK": "^HSI", "9988.HK": "^HSI", "3690.HK": "^HSI",
    # CN 上證
    "600519.SS": "000001.SS", "000858.SZ": "399001.SZ",
    "601318.SS": "000001.SS", "000333.SZ": "399001.SZ",
}

# v5.16 P49 — 中英文情緒關鍵字（簡化版，與 social_sentiment_provider 一致）
POSITIVE_KEYWORDS = [
    "surge", "rally", "beat", "strong", "growth", "upgrade", "outperform",
    "high", "record", "buy", "bullish", "boom", "profit", "gain",
    "上漲", "突破", "強勁", "增長", "看好", "買入", "牛市", "利多", "獲利",
]
NEGATIVE_KEYWORDS = [
    "fall", "drop", "plunge", "miss", "weak", "decline", "downgrade",
    "underperform", "low", "loss", "sell", "bearish", "crash", "risk",
    "下跌", "暴跌", "疲弱", "下滑", "看淡", "賣出", "熊市", "利空", "虧損",
]


def compute_sentiment_from_news(news_items: list[dict]) -> tuple[float, float, int]:
    """從 yfinance news 算 sentiment (combined_score, confidence, news_count)。

    combined_score = (positive - negative) / max(positive + negative, 1) ∈ [-1, 1]
    confidence = min(news_count / 60, 1.0)
    """
    if not news_items:
        return 0.0, 0.0, 0

    positive, negative = 0, 0
    for item in news_items:
        title = (item.get("title") or "").lower()
        # 計算每個關鍵字出現次數（同一標題多次出現算多次）
        for kw in POSITIVE_KEYWORDS:
            if kw.lower() in title:
                positive += 1
        for kw in NEGATIVE_KEYWORDS:
            if kw.lower() in title:
                negative += 1

    total = positive + negative
    if total == 0:
        # 沒有任何情緒關鍵字 → 中性 0（confidence 低）
        return 0.0, min(len(news_items) / 60, 0.3), len(news_items)

    combined_score = (positive - negative) / total
    confidence = min(len(news_items) / 60, 1.0)
    return combined_score, confidence, len(news_items)


def compute_macro_from_history(close_history: list[float]) -> float:
    """從 macro index 30 天 close 算 macro_score ∈ [0, 1]。

    設計：macro_score 反映「市場整體環境」對個股的影響
      - 上升趨勢 → 高分（環境支持買入）
      - 高波動 → 中性（不確定性高）
      - 下降趨勢 → 低分（環境風險）

    公式：base = 0.5 + 0.3 * sign(30d_return) * log1p(abs(30d_return)/annualized_vol)
    """
    if not close_history or len(close_history) < 2:
        return 0.5  # 中性 fallback

    # 30 天回報率
    start, end = close_history[0], close_history[-1]
    if start <= 0:
        return 0.5
    period_return = (end - start) / start

    # 年化波動率（每日 return std × sqrt(252)）
    daily_returns = [
        (close_history[i] - close_history[i - 1]) / close_history[i - 1]
        for i in range(1, len(close_history))
        if close_history[i - 1] > 0
    ]
    if len(daily_returns) < 2:
        return 0.5
    vol = statistics.pstdev(daily_returns)
    annualized_vol = vol * math.sqrt(252)

    # sign + log1p 縮放
    direction = math.copysign(1, period_return)
    magnitude = math.log1p(abs(period_return) / max(annualized_vol, 0.01))

    macro_score = 0.5 + 0.3 * direction * min(magnitude, 1.0)
    return max(0.0, min(1.0, macro_score))


def fetch_sentiment_macro(
    tickers: list[str], period_days: int = 30
) -> dict[str, dict]:
    """從 yfinance 拉真實 sentiment + macro。

    Returns:
        dict with keys:
          - sentiment_per_ticker: dict[str, dict]  (combined_score / confidence / news_count)
          - macro_per_ticker: dict[str, dict]  (index / macro_score / 30d_return / annualized_vol)
          - failed_tickers: list[str]
    """
    import yfinance as yf

    sentiment_per_ticker: dict[str, dict] = {}
    macro_per_ticker: dict[str, dict] = {}
    failed: list[str] = []

    # 1. Pull sentiment per ticker
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            news_items = ticker_obj.news or []
            cs, conf, count = compute_sentiment_from_news(news_items)
            sentiment_per_ticker[t] = {
                "combined_score": round(cs, 4),
                "confidence": round(conf, 4),
                "news_count": count,
            }
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  {t} sentiment 拉取失敗：{e}")
            sentiment_per_ticker[t] = {
                "combined_score": 0.0,
                "confidence": 0.0,
                "news_count": 0,
            }
            failed.append(t)

    # 2. Pull macro per unique macro index
    unique_indexes = set(TICKER_TO_MACRO_INDEX[t] for t in tickers)
    index_data: dict[str, dict] = {}
    for idx in unique_indexes:
        try:
            ticker_obj = yf.Ticker(idx)
            hist = ticker_obj.history(period=f"{period_days}d")
            if hist is None or hist.empty:
                print(f"⚠️  {idx} 歷史資料為空")
                continue
            close_history = hist["Close"].tolist()
            macro_score = compute_macro_from_history(close_history)

            # 計算 30d_return + annualized_vol 用於報告
            start, end = close_history[0], close_history[-1]
            period_return = (end - start) / start if start > 0 else 0.0
            daily_returns = [
                (close_history[i] - close_history[i - 1]) / close_history[i - 1]
                for i in range(1, len(close_history))
                if close_history[i - 1] > 0
            ]
            annualized_vol = (
                statistics.pstdev(daily_returns) * math.sqrt(252)
                if len(daily_returns) >= 2
                else 0.0
            )

            index_data[idx] = {
                "macro_score": round(macro_score, 4),
                "30d_return": round(period_return, 4),
                "annualized_vol": round(annualized_vol, 4),
            }
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  {idx} macro 拉取失敗：{e}")

    # 3. Map ticker → macro index
    for t in tickers:
        idx = TICKER_TO_MACRO_INDEX.get(t)
        if idx and idx in index_data:
            macro_per_ticker[t] = {"index": idx, **index_data[idx]}
        else:
            macro_per_ticker[t] = {
                "index": idx or "UNKNOWN",
                "macro_score": 0.5,  # fallback
                "30d_return": 0.0,
                "annualized_vol": 0.0,
            }
            if t not in failed:
                failed.append(t)

    return {
        "sentiment_per_ticker": sentiment_per_ticker,
        "macro_per_ticker": macro_per_ticker,
        "failed_tickers": failed,
    }


def update_fixtures_with_sentiment_macro(fixtures: dict, derived: dict) -> dict:
    """把 sentiment/macro 寫進 fixtures（不破壞既有 PE/ROE/PEG/growth 結構）。"""
    fixtures["sentiment_per_ticker"] = derived["sentiment_per_ticker"]
    fixtures["macro_per_ticker"] = derived["macro_per_ticker"]
    fixtures["_meta"]["sentiment_macro_fetched_at"] = datetime.now(timezone.utc).isoformat()
    fixtures["_meta"]["sentiment_macro_failed"] = derived["failed_tickers"]
    fixtures["_meta"]["ticker_to_macro_index"] = TICKER_TO_MACRO_INDEX
    return fixtures


def main() -> int:
    parser = argparse.ArgumentParser(description="v5.16 P49 真實 sentiment + macro 派生")
    parser.add_argument(
        "--period-days", type=int, default=30,
        help="macro index 歷史天數（default 30）",
    )
    args = parser.parse_args()

    if not FIXTURES_PATH.exists():
        print(f"❌ Fixtures {FIXTURES_PATH} 不存在。請先跑：")
        print("   python scripts/cross_market_real_yfinance_e2e.py")
        return 1

    print(f"📡 從 yfinance 拉 sentiment + macro（{len(TICKER_UNIVERSE)} tickers）...")
    derived = fetch_sentiment_macro(TICKER_UNIVERSE, period_days=args.period_days)

    print(f"\n{'Ticker':<14} {'Sent':>7} {'Conf':>6} {'News':>5} {'MacroIdx':<12} {'MacroScore':>10}")
    for t in TICKER_UNIVERSE:
        s = derived["sentiment_per_ticker"].get(t, {})
        m = derived["macro_per_ticker"].get(t, {})
        print(
            f"{t:<14} {s.get('combined_score', 0):>+7.3f} {s.get('confidence', 0):>6.3f} "
            f"{s.get('news_count', 0):>5d} {m.get('index', '?'):<12} {m.get('macro_score', 0.5):>10.3f}"
        )

    # Update fixtures
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    fixtures = update_fixtures_with_sentiment_macro(fixtures, derived)
    FIXTURES_PATH.write_text(
        json.dumps(fixtures, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n💾 Fixtures 更新到 {FIXTURES_PATH}")
    print(
        f"✅ {len(TICKER_UNIVERSE) - len(derived['failed_tickers'])}/{len(TICKER_UNIVERSE)} ticker 成功"
        + (f"（失敗：{derived['failed_tickers']}）" if derived["failed_tickers"] else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())