"""
Alpha Vantage Stock Data Module
Ported from TradingAgents dataflows/alpha_vantage_stock.py

Provides TIME_SERIES_DAILY_ADJUSTED endpoint for OHLCV data.
"""

from datetime import datetime
from io import StringIO
import pandas as pd
from .client import _make_api_request, AlphaVantageProvider


def get_stock(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """Get daily OHLCV data with adjusted close and split/dividend events.
    
    Uses TIME_SERIES_DAILY_ADJUSTED endpoint which returns:
    - Open, High, Low, Close prices (adjusted for splits/dividends)
    - Trading volume
    - Split/dividend events
    
    Args:
        symbol: Ticker symbol (e.g., "AAPL")
        start_date: Start date in YYYY-MM-DD format, or None for all available
        end_date: End date in YYYY-MM-DD format, or None for most recent
        
    Returns:
        CSV string with columns: date, 1. open, 2. high, 3. low, 4. close, 5. adjusted close,
                                6. volume, 7. dividend amount, 8. split coefficient
        
    Raises:
        AlphaVantageRateLimitError: When API rate limit is exceeded
    """
    # Use compact output for < 100 days, full for more
    outputsize = "compact"
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
            days = (end_dt - start_dt).days
            if days > 100:
                outputsize = "full"
        except (ValueError, TypeError):
            pass
    
    params = {
        "symbol": symbol,
        "outputsize": outputsize,
        "datatype": "csv",
    }
    
    csv_data = _make_api_request("TIME_SERIES_DAILY_ADJUSTED", params)
    
    # Filter by date range if specified
    if start_date or end_date:
        from .client import AlphaVantageProvider
        provider = AlphaVantageProvider()
        csv_data = provider._filter_csv_by_date(csv_data, start_date or "1900-01-01", end_date or "2100-01-01")
    
    return csv_data


def get_stock_json(symbol: str, start_date: str = None, end_date: str = None) -> dict:
    """Get stock data as JSON dict instead of CSV string.
    
    Returns:
        Dict with 'metadata' and 'data' keys
    """
    csv_data = get_stock(symbol, start_date, end_date)
    
    if not csv_data or csv_data.strip() == "":
        return {"metadata": {"symbol": symbol}, "data": []}
    
    df = pd.read_csv(StringIO(csv_data))
    date_col = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()][0]
    
    return {
        "metadata": {
            "symbol": symbol,
            "columns": list(df.columns),
        },
        "data": df.to_dict(orient="records")
    }
