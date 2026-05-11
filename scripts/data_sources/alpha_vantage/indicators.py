"""
Alpha Vantage Technical Indicators Module
Ported from TradingAgents dataflows/alpha_vantage_indicator.py

Supported indicators:
    - close_50_sma: 50-day Simple Moving Average
    - close_200_sma: 200-day Simple Moving Average
    - close_10_ema: 10-day Exponential Moving Average
    - macd: Moving Average Convergence/Divergence
    - macds: MACD Signal line
    - macdh: MACD Histogram
    - rsi: Relative Strength Index (14-period)
    - boll: Bollinger Middle Band (20-period, 2 std dev)
    - boll_ub: Bollinger Upper Band
    - boll_lb: Bollinger Lower Band
    - atr: Average True Range (14-period)
    - vwma: Volume Weighted Moving Average (calculated client-side)
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta
from .client import _make_api_request

SUPPORTED_INDICATORS = {
    "close_50_sma": ("SMA", "50", "close"),
    "close_200_sma": ("SMA", "200", "close"),
    "close_10_ema": ("EMA", "10", "close"),
    "macd": ("MACD", None, "close"),
    "macds": ("MACD", None, "close"),
    "macdh": ("MACD", None, "close"),
    "rsi": ("RSI", "14", "close"),
    "boll": ("BBANDS", "20", "close"),
    "boll_ub": ("BBANDS", "20", "close"),
    "boll_lb": ("BBANDS", "20", "close"),
    "atr": ("ATR", "14", None),
    "vwma": (None, None, None),  # Not available via API
}

INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: Medium-term trend indicator. Identifies trend direction and dynamic support/resistance. Use with faster indicators for timely signals.",
    "close_200_sma": "200 SMA: Long-term trend benchmark. Confirms overall market trend, identifies golden/death cross setups. Slow-reacting, best for strategic confirmation.",
    "close_10_ema": "10 EMA: Responsive short-term average. Captures quick momentum shifts and potential entries. Prone to noise in choppy markets.",
    "macd": "MACD: Momentum via differences of EMAs. Look for crossovers and divergence as trend change signals. Confirm with other indicators.",
    "macds": "MACD Signal: EMA smoothing of MACD line. Crossovers with MACD line trigger trades. Best as part of broader strategy.",
    "macdh": "MACD Histogram: Gap between MACD and signal line. Visualizes momentum strength and spots divergence early. Can be volatile.",
    "rsi": "RSI: Momentum measuring overbought/oversold (70/30 thresholds). Watch for divergence to signal reversals. In strong trends, RSI may remain extreme.",
    "boll": "Bollinger Middle: 20 SMA basis for bands. Dynamic benchmark for price movement. Combine with upper/lower bands for breakouts or reversals.",
    "boll_ub": "Bollinger Upper: 2 standard deviations above middle. Potential overbought and breakout zones. Prices may ride the band in strong trends.",
    "boll_lb": "Bollinger Lower: 2 standard deviations below middle. Potential oversold conditions. Use additional analysis to avoid false reversals.",
    "atr": "ATR: Measures volatility for stop-loss levels and position sizing. Reactive measure; use as part of broader risk management.",
    "vwma": "VWMA: Volume-weighted price average. Confirms trends by integrating volume. Watch for skewed results from volume spikes.",
}


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
    interval: str = "daily",
    time_period: int = 14,
    series_type: str = "close"
) -> str:
    """Get technical indicator values over a time window.
    
    Args:
        symbol: Ticker symbol (e.g., "AAPL")
        indicator: Name - close_50_sma, close_200_sma, close_10_ema, macd,
                   macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma
        curr_date: Current trading date YYYY-MM-DD
        look_back_days: Days to look back from curr_date
        interval: Time interval - daily, weekly, monthly (default: daily)
        time_period: Data points for calculation (default: 14)
        series_type: Price type - close, open, high, low (default: close)
        
    Returns:
        String with indicator values (YYYY-MM-DD: value) and description
        
    Raises:
        ValueError: If indicator not supported
    """
    if indicator not in SUPPORTED_INDICATORS:
        raise ValueError(
            f"Indicator '{indicator}' not supported. "
            f"Choose from: {list(SUPPORTED_INDICATORS.keys())}"
        )

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    api_func, param_period, required_series_type = SUPPORTED_INDICATORS[indicator]

    # VWMA not available via API
    if api_func is None:
        return (
            f"## VWMA for {symbol}:\n\n"
            f"VWMA requires OHLCV data and cannot be fetched directly.\n"
            f"Calculate from: sum(close * volume) / sum(volume) over period.\n\n"
            f"{INDICATOR_DESCRIPTIONS.get('vwma', '')}"
        )

    # Override series_type if required by indicator
    if required_series_type:
        series_type = required_series_type

    try:
        # Build API params based on indicator type
        if indicator in ["close_50_sma", "close_200_sma"]:
            data = _make_api_request("SMA", {
                "symbol": symbol,
                "interval": interval,
                "time_period": param_period,
                "series_type": series_type,
                "datatype": "csv"
            })
        elif indicator == "close_10_ema":
            data = _make_api_request("EMA", {
                "symbol": symbol,
                "interval": interval,
                "time_period": param_period,
                "series_type": series_type,
                "datatype": "csv"
            })
        elif indicator in ["macd", "macds", "macdh"]:
            data = _make_api_request("MACD", {
                "symbol": symbol,
                "interval": interval,
                "series_type": series_type,
                "datatype": "csv"
            })
        elif indicator == "rsi":
            data = _make_api_request("RSI", {
                "symbol": symbol,
                "interval": interval,
                "time_period": str(time_period),
                "series_type": series_type,
                "datatype": "csv"
            })
        elif indicator in ["boll", "boll_ub", "boll_lb"]:
            data = _make_api_request("BBANDS", {
                "symbol": symbol,
                "interval": interval,
                "time_period": param_period,
                "series_type": series_type,
                "datatype": "csv"
            })
        elif indicator == "atr":
            data = _make_api_request("ATR", {
                "symbol": symbol,
                "interval": interval,
                "time_period": str(time_period),
                "datatype": "csv"
            })
        else:
            return f"Error: Indicator {indicator} not implemented."

        # Parse CSV and extract values in date range
        lines = data.strip().split('\n')
        if len(lines) < 2:
            return f"Error: No data returned for {indicator}"

        header = [col.strip() for col in lines[0].split(',')]
        try:
            date_col_idx = header.index('time')
        except ValueError:
            return f"Error: 'time' column not found. Available: {header}"

        col_name_map = {
            "macd": "MACD",
            "macds": "MACD_Signal",
            "macdh": "MACD_Hist",
            "boll": "Real Middle Band",
            "boll_ub": "Real Upper Band",
            "boll_lb": "Real Lower Band",
            "rsi": "RSI",
            "atr": "ATR",
            "close_10_ema": "EMA",
            "close_50_sma": "SMA",
            "close_200_sma": "SMA"
        }

        target_col_name = col_name_map.get(indicator)
        if target_col_name:
            try:
                value_col_idx = header.index(target_col_name)
            except ValueError:
                return f"Error: Column '{target_col_name}' not found. Available: {header}"
        else:
            value_col_idx = 1

        # Extract data within date range
        result_data = []
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split(',')
            if len(values) > max(date_col_idx, value_col_idx):
                try:
                    date_str = values[date_col_idx].strip()
                    date_dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if before <= date_dt <= curr_date_dt:
                        value = values[value_col_idx].strip()
                        result_data.append((date_dt, value))
                except (ValueError, IndexError):
                    continue

        result_data.sort(key=lambda x: x[0])

        ind_string = ""
        for date_dt, value in result_data:
            ind_string += f"{date_dt.strftime('%Y-%m-%d')}: {value}\n"

        if not ind_string:
            ind_string = "No data available for the specified date range.\n"

        return (
            f"## {indicator.upper()} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + ind_string
            + "\n"
            + INDICATOR_DESCRIPTIONS.get(indicator, "No description available.")
        )

    except Exception as e:
        return f"Error retrieving {indicator} data: {str(e)}"
