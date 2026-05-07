---
name: handlers
description: "Skill for the Handlers area of stock-team-agent. 44 symbols across 7 files."
---

# Handlers

44 symbols | 7 files | Cohesion: 92%

## When to Use

- Working with code in `scripts/`
- Understanding how analyze, analyze, analyze work
- Modifying handlers-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/handlers/technical_analyst.py` | _calculate_indicators, _sma, _ema, _rsi, _macd (+10) |
| `scripts/handlers/fundamental_analyst.py` | analyze, _get_financial_data, _analyze_profitability, _calculate_score, _calculate_valuation (+3) |
| `scripts/handlers/sentiment_analyst.py` | analyze, _analyze_news_sentiment, _get_analyst_rating, _calculate_score, _get_news_data (+1) |
| `scripts/handlers/risk_analyst.py` | analyze, _get_risk_data, _calculate_risk_metrics, _evaluate_risk_level, _calculate_score |
| `scripts/handlers/market_analyst.py` | analyze, _get_market_data, _analyze_market_sentiment, _calculate_score |
| `scripts/handlers/macro_analyst.py` | analyze, _get_macro_data, _analyze_macro_environment, _calculate_score |
| `scripts/data_sources/news_feed_provider.py` | fetch_all, analyze_stock_impact |

## Entry Points

Start here when exploring this area:

- **`analyze`** (Function) — `scripts/handlers/technical_analyst.py:29`
- **`analyze`** (Function) — `scripts/handlers/risk_analyst.py:17`
- **`analyze`** (Function) — `scripts/handlers/sentiment_analyst.py:17`
- **`fetch_all`** (Function) — `scripts/data_sources/news_feed_provider.py:242`
- **`analyze_stock_impact`** (Function) — `scripts/data_sources/news_feed_provider.py:301`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `analyze` | Function | `scripts/handlers/technical_analyst.py` | 29 |
| `analyze` | Function | `scripts/handlers/risk_analyst.py` | 17 |
| `analyze` | Function | `scripts/handlers/sentiment_analyst.py` | 17 |
| `fetch_all` | Function | `scripts/data_sources/news_feed_provider.py` | 242 |
| `analyze_stock_impact` | Function | `scripts/data_sources/news_feed_provider.py` | 301 |
| `analyze` | Function | `scripts/handlers/market_analyst.py` | 17 |
| `analyze` | Function | `scripts/handlers/macro_analyst.py` | 17 |
| `analyze` | Function | `scripts/handlers/fundamental_analyst.py` | 17 |
| `_calculate_indicators` | Function | `scripts/handlers/technical_analyst.py` | 102 |
| `_sma` | Function | `scripts/handlers/technical_analyst.py` | 124 |
| `_ema` | Function | `scripts/handlers/technical_analyst.py` | 129 |
| `_rsi` | Function | `scripts/handlers/technical_analyst.py` | 138 |
| `_macd` | Function | `scripts/handlers/technical_analyst.py` | 151 |
| `_bollinger_bands` | Function | `scripts/handlers/technical_analyst.py` | 162 |
| `_atr` | Function | `scripts/handlers/technical_analyst.py` | 173 |
| `_stochastic` | Function | `scripts/handlers/technical_analyst.py` | 185 |
| `_volume_profile` | Function | `scripts/handlers/technical_analyst.py` | 198 |
| `_get_kline_data` | Function | `scripts/handlers/technical_analyst.py` | 64 |
| `_recognize_patterns` | Function | `scripts/handlers/technical_analyst.py` | 207 |
| `_generate_signals` | Function | `scripts/handlers/technical_analyst.py` | 231 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Analyze → _parse_date` | cross_community | 6 |
| `Analyze → _get_cache` | cross_community | 5 |
| `Analyze → Fetch_feed` | cross_community | 5 |
| `Analyze → _set_cache` | cross_community | 5 |
| `Analyze → _sma` | cross_community | 3 |
| `Analyze → _ema` | cross_community | 3 |
| `Analyze → _generate_summary` | intra_community | 3 |
| `Analyze → _get_mock_news` | cross_community | 3 |
| `Analyze → Analyze_stock_impact` | cross_community | 3 |
| `Analyze → _evaluate_pe` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Data_sources | 1 calls |

## How to Explore

1. `gitnexus_context({name: "analyze"})` — see callers and callees
2. `gitnexus_query({query: "handlers"})` — find related execution flows
3. Read key files listed above for implementation details
