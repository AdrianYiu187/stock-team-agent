"""
Alpha Vantage Data Source for Stock_Team_Agent
Ported from TradingAgents dataflows/alpha_vantage/

Provides:
- Stock OHLCV data (TIME_SERIES_DAILY_ADJUSTED)
- Fundamentals (balance sheet, cashflow, income statement)
- Technical indicators (SMA, EMA, MACD, RSI, Bollinger Bands, ATR)
- News sentiment and insider transactions

Usage:
    from alpha_vantage import AlphaVantageProvider
    provider = AlphaVantageProvider()
    klines = provider.get_kline("AAPL")
    rsi = provider.get_indicator("AAPL", "rsi", "2024-01-01", 30)
"""

from .client import AlphaVantageProvider, AlphaVantageRateLimitError, get_api_key
from .stock import get_stock
from .fundamentals import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
from .indicators import get_indicator, SUPPORTED_INDICATORS, INDICATOR_DESCRIPTIONS
from .news import get_news, get_global_news, get_insider_transactions
from .utils import safe_ticker_component

__all__ = [
    "AlphaVantageProvider",
    "AlphaVantageRateLimitError", 
    "get_api_key",
    "get_stock",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_indicator",
    "SUPPORTED_INDICATORS",
    "INDICATOR_DESCRIPTIONS",
    "get_news",
    "get_global_news",
    "get_insider_transactions",
    "safe_ticker_component",
]
