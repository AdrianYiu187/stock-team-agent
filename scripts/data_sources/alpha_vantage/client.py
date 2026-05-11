"""
Alpha Vantage API Client
Core client for making requests to Alpha Vantage API.

Ported from TradingAgents dataflows/alpha_vantage_common.py
"""

import os
import requests
import pandas as pd
import json
from datetime import datetime
from io import StringIO
from typing import Optional, Dict, Any

API_BASE_URL = "https://www.alphavantage.co/query"

# Free tier: 25 requests/day, 5 requests/minute
# Premium: higher limits


class AlphaVantageRateLimitError(Exception):
    """Exception raised when Alpha Vantage API rate limit is exceeded."""
    pass


# Module-level API request function (used by submodules)
def _make_api_request(function_name: str, params: dict) -> str:
    """Module-level API request wrapper.
    
    This function is used by stock.py, indicators.py, etc.
    For instance-level requests with caching, use AlphaVantageProvider._make_request().
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is not set.")
    
    api_params = params.copy()
    api_params.update({
        "function": function_name,
        "apikey": api_key,
        "source": "stock_team_agent",
    })
    
    response = requests.get(API_BASE_URL, params=api_params, timeout=10)
    response.raise_for_status()
    response_text = response.text
    
    # Check for rate limit error
    try:
        response_json = json.loads(response_text)
        if "Information" in response_json:
            info_message = response_json["Information"]
            if "rate limit" in info_message.lower() or "api key" in info_message.lower():
                raise AlphaVantageRateLimitError(f"Rate limit exceeded: {info_message}")
    except json.JSONDecodeError:
        pass
    
    return response_text


class AlphaVantageProvider:
    """Alpha Vantage data provider with caching and rate limit handling.
    
    This provider implements the same interface as StockDataProvider,
    allowing seamless fallback from yfinance to Alpha Vantage.
    
    Usage:
        provider = AlphaVantageProvider()
        klines = provider.get_kline("AAPL", period="daily", limit=100)
    """
    
    BASE_URL = API_BASE_URL
    
    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 300):
        """Initialize Alpha Vantage provider.
        
        Args:
            api_key: Alpha Vantage API key. If None, reads from ALPHA_VANTAGE_API_KEY env.
            cache_ttl: Cache time-to-live in seconds (default: 300 = 5 minutes)
        """
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Alpha Vantage API key required. "
                "Set ALPHA_VANTAGE_API_KEY environment variable or pass api_key parameter."
            )
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (data, timestamp)
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now().timestamp() - timestamp < self.cache_ttl:
                return data
            del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: Any):
        """Set cache with current timestamp."""
        self._cache[key] = (data, datetime.now().timestamp())
    
    def _make_request(self, function_name: str, params: dict) -> str:
        """Make API request and handle rate limiting."""
        api_params = params.copy()
        api_params.update({
            "function": function_name,
            "apikey": self.api_key,
            "source": "stock_team_agent",
        })
        
        response = requests.get(self.BASE_URL, params=api_params, timeout=10)
        response.raise_for_status()
        response_text = response.text
        
        # Check for rate limit error
        try:
            response_json = json.loads(response_text)
            if "Information" in response_json:
                info_message = response_json["Information"]
                if "rate limit" in info_message.lower() or "api key" in info_message.lower():
                    raise AlphaVantageRateLimitError(f"Rate limit exceeded: {info_message}")
        except json.JSONDecodeError:
            pass
        
        return response_text
    
    def _filter_csv_by_date(self, csv_data: str, start_date: str, end_date: str) -> str:
        """Filter CSV data to specified date range."""
        if not csv_data or csv_data.strip() == "":
            return csv_data
        
        try:
            df = pd.read_csv(StringIO(csv_data))
            date_col = df.columns[0]
            df[date_col] = pd.to_datetime(df[date_col])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            filtered_df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]
            return filtered_df.to_csv(index=False)
        except Exception:
            return csv_data
    
    # ===== High-level interface matching StockDataProvider =====
    
    def get_kline(self, symbol: str, period: str = "daily", limit: int = 100) -> list:
        """Get OHLCV candlestick data.
        
        Args:
            symbol: Ticker symbol (e.g., "AAPL", "0700.HK")
            period: "daily" or "weekly" (default: "daily")
            limit: Number of periods to fetch (default: 100)
            
        Returns:
            List of dicts with keys: date, open, high, low, close, volume
        """
        from .stock import get_stock
        from .utils import safe_ticker_component
        
        symbol = safe_ticker_component(symbol)
        cache_key = f"kline_{symbol}_{period}_{limit}"
        
        if cached := self._get_cache(cache_key):
            return cached
        
        try:
            csv_data = get_stock(symbol, None, None)
            if csv_data and "Error" not in csv_data[:50]:
                df = pd.read_csv(StringIO(csv_data))
                if len(df) > 0:
                    # Alpha Vantage returns newest first
                    df = df.iloc[::-1]  # Reverse to oldest first
                    df = df.tail(limit)
                    
                    klines = []
                    date_col = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()][0]
                    for _, row in df.iterrows():
                        klines.append({
                            "date": str(row[date_col])[:10],
                            "open": float(row.get("1. open", 0)),
                            "high": float(row.get("2. high", 0)),
                            "low": float(row.get("3. low", 0)),
                            "close": float(row.get("4. close", 0)),
                            "volume": int(row.get("6. volume", 0)),
                        })
                    self._set_cache(cache_key, klines)
                    return klines
        except Exception as e:
            print(f"[AlphaVantage] get_kline({symbol}) failed: {e}")
        
        return []
    
    def get_financials(self, symbol: str) -> dict:
        """Get financial metrics (simplified for compatibility)."""
        from .fundamentals import get_fundamentals
        from .utils import safe_ticker_component
        
        symbol = safe_ticker_component(symbol)
        cache_key = f"financials_{symbol}"
        
        if cached := self._get_cache(cache_key):
            return cached
        
        try:
            overview = get_fundamentals(symbol)
            if overview and "Error" not in overview[:50]:
                # Parse JSON overview into StockDataProvider format
                data = json.loads(overview) if isinstance(overview, str) else overview
                financials = {
                    "revenue": data.get("RevenueTTM", 0) or data.get("TotalRevenue", 0),
                    "net_income": data.get("NetIncome", 0),
                    "total_assets": data.get("TotalAssets", 0),
                    "roe": data.get("ReturnOnEquityTTM", 0) or data.get("ReturnOnEquity", 0),
                    "roa": data.get("ReturnOnAssetsTTM", 0) or data.get("ReturnOnAssets", 0),
                    "eps": data.get("EPSTTM", 0) or data.get("EPS", 0),
                    "pe_ratio": data.get("PERatio", 0),
                    "pb_ratio": data.get("PriceToBookRatio", 0),
                    "dividend_yield": data.get("DividendYield", 0),
                    "market_cap": data.get("MarketCapitalization", 0),
                    "52w_high": data.get("52WeekHigh", 0),
                    "52w_low": data.get("52WeekLow", 0),
                }
                self._set_cache(cache_key, financials)
                return financials
        except Exception as e:
            print(f"[AlphaVantage] get_financials({symbol}) failed: {e}")
        
        return {}
    
    def get_indicator(self, symbol: str, indicator: str, curr_date: str, look_back: int = 30) -> str:
        """Get technical indicator.
        
        Args:
            symbol: Ticker symbol
            indicator: Indicator name (rsi, macd, sma, ema, boll, atr)
            curr_date: Current date YYYY-MM-DD
            look_back: Days to look back (default: 30)
            
        Returns:
            String with indicator values and description
        """
        from .indicators import get_indicator as _get_indicator
        from .utils import safe_ticker_component
        
        symbol = safe_ticker_component(symbol)
        cache_key = f"indicator_{symbol}_{indicator}_{curr_date}_{look_back}"
        
        if cached := self._get_cache(cache_key):
            return cached
        
        try:
            result = _get_indicator(symbol, indicator, curr_date, look_back)
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[AlphaVantage] get_indicator({symbol}, {indicator}) failed: {e}")
            return f"Error: {str(e)}"
    
    def get_news(self, symbol: str, limit: int = 20) -> list:
        """Get news and sentiment for ticker."""
        from .news import get_news
        from .utils import safe_ticker_component
        
        symbol = safe_ticker_component(symbol)
        cache_key = f"news_{symbol}_{limit}"
        
        if cached := self._get_cache(cache_key):
            return cached
        
        try:
            news_data = get_news(symbol, None, None)
            if news_data and "Error" not in str(news_data)[:50]:
                if isinstance(news_data, dict):
                    articles = news_data.get("feed", [])[:limit]
                    news_list = []
                    for article in articles:
                        news_list.append({
                            "title": article.get("title", ""),
                            "source": article.get("source", ""),
                            "date": article.get("time_published", "")[:10],
                            "sentiment": article.get("overall_sentiment_label", "Neutral"),
                            "url": article.get("url", ""),
                        })
                    self._set_cache(cache_key, news_list)
                    return news_list
        except Exception as e:
            print(f"[AlphaVantage] get_news({symbol}) failed: {e}")
        
        return []


def get_api_key() -> str:
    """Retrieve API key from environment."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is not set.")
    return api_key


def format_datetime_for_api(date_input) -> str:
    """Convert date to YYYYMMDDTHHMM format for Alpha Vantage API."""
    if isinstance(date_input, str):
        if len(date_input) == 13 and 'T' in date_input:
            return date_input
        try:
            dt = datetime.strptime(date_input, "%Y-%m-%d")
            return dt.strftime("%Y%m%dT0000")
        except ValueError:
            try:
                dt = datetime.strptime(date_input, "%Y-%m-%d %H:%M")
                return dt.strftime("%Y%m%dT%H%M")
            except ValueError:
                raise ValueError(f"Unsupported date format: {date_input}")
    elif isinstance(date_input, datetime):
        return date_input.strftime("%Y%m%dT%H%M")
    else:
        raise ValueError(f"Date must be string or datetime object, got {type(date_input)}")
