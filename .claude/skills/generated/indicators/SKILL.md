---
name: indicators
description: "Skill for the Indicators area of stock-team-agent. 18 symbols across 1 files."
---

# Indicators

18 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `scripts/`
- Understanding how calculate_all, sma, ema work
- Modifying indicators-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/indicators/technical_indicators.py` | calculate_all, sma, ema, macd, _ema_iterative (+13) |
| `scripts/data_sources/alpha_vantage/indicators.py` | **Alpha Vantage indicators (12 types: RSI, MACD, Bollinger, ATR, SMA, EMA…)** |

## Dual Indicator Sources

Stock_Team_Agent has **two** indicator implementations — different sources, different use cases:

| Source | Location | Provider | Indicators |
|---------|----------|----------|-------------|
| **Native** | `scripts/indicators/technical_indicators.py` | yfinance (calculated) | SMA, EMA, MACD, RSI, Bollinger, ATR, ADX, Stochastic, CCI, OBV, VWAP… |
| **Alpha Vantage** | `scripts/data_sources/alpha_vantage/indicators.py` | Alpha Vantage API | RSI, MACD, Bollinger, ATR, SMA, EMA + 8 more |

**Use Alpha Vantage indicators when**: You want API-verified indicator values with built-in rate limit handling and `safe_ticker_component` security.

**Use native indicators when**: You need indicators not in Alpha Vantage (ADX, Stochastic, CCI, OBV, VWAP) or prefer local calculation.

**Supported Alpha Vantage functions**: `close_50_sma`, `close_200_sma`, `close_10_ema`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`

## Entry Points

Start here when exploring this area:

- **`calculate_all`** (Function) — `scripts/indicators/technical_indicators.py:40`
- **`sma`** (Function) — `scripts/indicators/technical_indicators.py:70`
- **`ema`** (Function) — `scripts/indicators/technical_indicators.py:76`
- **`macd`** (Function) — `scripts/indicators/technical_indicators.py:86`
- **`supertrend`** (Function) — `scripts/indicators/technical_indicators.py:118`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `calculate_all` | Function | `scripts/indicators/technical_indicators.py` | 40 |
| `sma` | Function | `scripts/indicators/technical_indicators.py` | 70 |
| `ema` | Function | `scripts/indicators/technical_indicators.py` | 76 |
| `macd` | Function | `scripts/indicators/technical_indicators.py` | 86 |
| `supertrend` | Function | `scripts/indicators/technical_indicators.py` | 118 |
| `adx` | Function | `scripts/indicators/technical_indicators.py` | 170 |
| `rsi` | Function | `scripts/indicators/technical_indicators.py` | 209 |
| `stochastic` | Function | `scripts/indicators/technical_indicators.py` | 225 |
| `williams_r` | Function | `scripts/indicators/technical_indicators.py` | 242 |
| `cci` | Function | `scripts/indicators/technical_indicators.py` | 256 |
| `momentum` | Function | `scripts/indicators/technical_indicators.py` | 273 |
| `roc` | Function | `scripts/indicators/technical_indicators.py` | 279 |
| `bollinger_bands` | Function | `scripts/indicators/technical_indicators.py` | 290 |
| `atr` | Function | `scripts/indicators/technical_indicators.py` | 305 |
| `obv` | Function | `scripts/indicators/technical_indicators.py` | 322 |
| `vwap` | Function | `scripts/indicators/technical_indicators.py` | 335 |
| `volume_profile` | Function | `scripts/indicators/technical_indicators.py` | 351 |
| `_ema_iterative` | Function | `scripts/indicators/technical_indicators.py` | 108 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Calculate_all → _ema_iterative` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "calculate_all"})` — see callers and callees
2. `gitnexus_query({query: "indicators"})` — find related execution flows
3. Read key files listed above for implementation details
