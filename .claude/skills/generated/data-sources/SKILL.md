---
name: data-sources
description: "Skill for the Data_sources area of stock-team-agent. 27 symbols across 3 files."
---

# Data_sources

27 symbols | 3 files | Cohesion: 98%

## When to Use

- Working with code in `scripts/`
- Understanding how fetch_all_working, analyze_stock_impact, get_market_sentiment work
- Modifying data_sources-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/data_sources/enhanced_news_feed_provider.py` | fetch_all_working, analyze_stock_impact, get_market_sentiment, analyze_with_price_context, _get_cache (+9) |
| `scripts/data_sources/stock_data_provider.py` | get_kline, get_financials, get_news, _get_cache, _set_cache (+2) |
| `scripts/data_sources/news_feed_provider.py` | fetch_feed, parse_rss, _parse_date, fetch_category, _get_cache (+1) |
| `scripts/data_sources/alpha_vantage/` | **Alpha Vantage data source (2026-05-11 port from TradingAgents)** |
| `scripts/data_sources/hybrid_provider.py` | **Hybrid Yahoo Finance + Alpha Vantage fallback provider** |

### Alpha Vantage Module (`scripts/data_sources/alpha_vantage/`)

Ported from TradingAgents (73.3k stars). Provides professional-grade stock data with 12 technical indicators.

**Modules:**
- `client.py` — Core API client with rate limit handling, `AlphaVantageProvider` class
- `stock.py` — TIME_SERIES_DAILY_ADJUSTED OHLCV data
- `fundamentals.py` — OVERVIEW, BALANCE_SHEET, INCOME_STATEMENT, CASHFLOW
- `indicators.py` — RSI, MACD, Bollinger Bands, ATR, SMA, EMA (12 indicators total)
- `news.py` — NEWS_SENTIMENT with parse_news_sentiment()
- `utils.py` — `safe_ticker_component()` **security validation** (blocks path traversal)
- `__init__.py` — Exports: `AlphaVantageProvider`, `AlphaVantageRateLimitError`, `safe_ticker_component`, `SUPPORTED_INDICATORS`, `INDICATOR_DESCRIPTIONS`

**Security:** `safe_ticker_component()` validates tickers against `^[A-Za-z0-9._\-\^]+$`. Blocks `../../../etc/passwd`, dots-only, and >32-char inputs. **Always use before filesystem interpolation.**

**Indicators supported:** `close_50_sma`, `close_200_sma`, `close_10_ema`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`

### Hybrid Provider (`scripts/data_sources/hybrid_provider.py`)

3-tier fallback provider: Yahoo Finance → Alpha Vantage → Mock.

```
HybridDataProvider()
  .get_kline(symbol)     # OHLCV
  .get_financials()     # Fundamentals
  .get_news()           # News
  .get_market_risk()    # VIX-based risk
  .get_indicator()      # Technical indicators (Alpha Vantage only)
```

**API key:** Set `ALPHA_VANTAGE_API_KEY` env var. Free tier: 25 req/day, 5 req/minute.

**Usage:**
```python
from scripts.data_sources.hybrid_provider import HybridDataProvider
provider = HybridDataProvider()
klines = provider.get_kline("AAPL")
```

## Entry Points

Start here when exploring this area:

- **`fetch_all_working`** (Function) — `scripts/data_sources/enhanced_news_feed_provider.py:212`
- **`analyze_stock_impact`** (Function) — `scripts/data_sources/enhanced_news_feed_provider.py:267`
- **`get_market_sentiment`** (Function) — `scripts/data_sources/enhanced_news_feed_provider.py:299`
- **`analyze_with_price_context`** (Function) — `scripts/data_sources/enhanced_news_feed_provider.py:336`
- **`analyze_sentiment_llm`** (Function) — `scripts/data_sources/enhanced_news_feed_provider.py:467`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetch_all_working` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 212 |
| `analyze_stock_impact` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 267 |
| `get_market_sentiment` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 299 |
| `analyze_with_price_context` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 336 |
| `analyze_sentiment_llm` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 467 |
| `analyze_stock_impact_llm` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 552 |
| `main` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 598 |
| `get_kline` | Function | `scripts/data_sources/stock_data_provider.py` | 33 |
| `get_financials` | Function | `scripts/data_sources/stock_data_provider.py` | 62 |
| `get_news` | Function | `scripts/data_sources/stock_data_provider.py` | 97 |
| `fetch_feed` | Function | `scripts/data_sources/news_feed_provider.py` | 115 |
| `parse_rss` | Function | `scripts/data_sources/news_feed_provider.py` | 134 |
| `fetch_category` | Function | `scripts/data_sources/news_feed_provider.py` | 212 |
| `fetch_feed` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 119 |
| `parse_rss` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 137 |
| `fetch_single` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 228 |
| `_get_cache` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 439 |
| `_set_cache` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 446 |
| `_keyword_sentiment` | Function | `scripts/data_sources/enhanced_news_feed_provider.py` | 488 |
| `_get_cache` | Function | `scripts/data_sources/stock_data_provider.py` | 142 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Analyze → _parse_date` | cross_community | 6 |
| `Analyze → _get_cache` | cross_community | 5 |
| `Analyze → Fetch_feed` | cross_community | 5 |
| `Analyze → _set_cache` | cross_community | 5 |
| `Main → _keyword_sentiment` | intra_community | 4 |
| `Fetch_single → _parse_date` | intra_community | 3 |
| `Main → _get_cache` | intra_community | 3 |
| `Main → _set_cache` | intra_community | 3 |
| `Main → Analyze_stock_impact` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "fetch_all_working"})` — see callers and callees
2. `gitnexus_query({query: "data_sources"})` — find related execution flows
3. Read key files listed above for implementation details
