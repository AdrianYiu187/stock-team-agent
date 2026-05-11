"""
Alpha Vantage Fundamentals Module
Ported from TradingAgents dataflows/alpha_vantage_fundamentals.py

Provides:
- Company OVERVIEW (key metrics and ratios)
- BALANCE_SHEET (quarterly/annual)
- INCOME_STATEMENT (quarterly/annual)
- CASHFLOW (quarterly/annual)
"""

import json
from .client import _make_api_request, AlphaVantageProvider


def _filter_reports_by_date(reports: list, curr_date: str, max_reports: int = 8) -> list:
    """Filter financial reports to prevent look-ahead bias.
    
    Only returns reports with fiscalDateEnding before curr_date.
    Limits to max_reports most recent periods.
    """
    if not curr_date:
        return reports[:max_reports]
    
    from datetime import datetime
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    
    filtered = []
    for report in reports:
        date_str = report.get("fiscalDateEnding", "")
        if date_str:
            try:
                from datetime import datetime
                report_dt = datetime.strptime(date_str, "%Y-%m-%d")
                if report_dt < curr_dt:
                    filtered.append(report)
            except ValueError:
                continue
    
    return filtered[:max_reports]


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamentals overview.
    
    API: OVERVIEW
    
    Returns company information including:
    - Identification: Symbol, Name, Type, Description
    - Financial Ratios: PERatio, PEGRatio, BookValue, PriceToBookRatio
    - Share Data: MarketCapitalization, SharesOutstanding, DividendYield
    - Performance: 52WeekHigh, 52WeekLow, 50DayMovingAverage
    - Fundamentals: RevenueTTM, EBITDA, EPS
    
    Args:
        ticker: Stock ticker symbol
        curr_date: Current trading date (YYYY-MM-DD) for backtesting
        
    Returns:
        JSON string with company overview data
    """
    params = {"symbol": ticker}
    return _make_api_request("OVERVIEW", params)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get balance sheet data.
    
    API: BALANCE_SHEET
    
    Returns:
        JSON string with quarterlyReports or annualReports
    """
    params = {"symbol": ticker}
    if freq == "annual":
        params["function"] = "BALANCE_SHEET"
    else:
        params["function"] = "BALANCE_SHEET"
    
    data = _make_api_request("BALANCE_SHEET", params)
    
    # Filter by date if specified
    if curr_date and isinstance(data, str):
        try:
            data_dict = json.loads(data)
            if "quarterlyReports" in data_dict:
                data_dict["quarterlyReports"] = _filter_reports_by_date(
                    data_dict["quarterlyReports"], curr_date
                )
            data = json.dumps(data_dict)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return data


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get cash flow statement data.
    
    API: CASH_FLOW
    
    Returns:
        JSON string with operating, investing, financing cash flows
    """
    params = {"symbol": ticker}
    params["function"] = "CASH_FLOW"
    
    data = _make_api_request("CASH_FLOW", params)
    
    # Filter by date if specified
    if curr_date and isinstance(data, str):
        try:
            data_dict = json.loads(data)
            if "quarterlyReports" in data_dict:
                data_dict["quarterlyReports"] = _filter_reports_by_date(
                    data_dict["quarterlyReports"], curr_date
                )
            data = json.dumps(data_dict)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return data


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get income statement data.
    
    API: INCOME_STATEMENT
    
    Returns:
        JSON string with revenues, expenses, earnings per share
    """
    params = {"symbol": ticker}
    params["function"] = "INCOME_STATEMENT"
    
    data = _make_api_request("INCOME_STATEMENT", params)
    
    # Filter by date if specified
    if curr_date and isinstance(data, str):
        try:
            data_dict = json.loads(data)
            if "quarterlyReports" in data_dict:
                data_dict["quarterlyReports"] = _filter_reports_by_date(
                    data_dict["quarterlyReports"], curr_date
                )
            data = json.dumps(data_dict)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return data
