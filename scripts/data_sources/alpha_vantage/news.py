"""
Alpha Vantage News Module
Ported from TradingAgents dataflows/alpha_vantage_news.py

Provides:
- NEWS_SENTIMENT: Market news & sentiment for specific ticker
- GLOBAL_NEWS: Market-wide news without ticker filter
- INSIDER_TRANSACTIONS: Insider trading activity
"""

import json
from .client import _make_api_request


def get_news(ticker: str, start_date: str = None, end_date: str = None) -> dict:
    """Get market news and sentiment for a specific ticker.
    
    API: NEWS_SENTIMENT
    
    Returns:
        Dict with feed array containing news articles
        Each article has: title, summary, source, url, time_published,
        authors, sentiment, topics, etc.
    """
    params = {
        "symbol": ticker,
        "topics": "technology,financial_markets,economy_macro",
        "sort": "LATEST",
        "limit": 50,
    }
    
    return _make_api_request("NEWS_SENTIMENT", params)


def get_global_news(curr_date: str = None, look_back_days: int = 7, limit: int = 50) -> dict:
    """Get global market news without ticker filter.
    
    API: NEWS_SENTIMENT with no ticker parameter
    
    Returns:
        Dict with feed array of market-wide news
    """
    params = {
        "topics": "financial_markets,economy_macro,technology",
        "sort": "LATEST",
        "limit": min(limit, 50),
    }
    
    if curr_date:
        params["time_from"] = curr_date.replace("-", "") + "T0000"
    
    return _make_api_request("NEWS_SENTIMENT", params)


def get_insider_transactions(symbol: str) -> dict:
    """Get insider transactions for a company.
    
    API: INSIDER_TRANSACTIONS
    
    Returns:
        Dict with transaction data including:
        - name: insider name
        - relation: relationship to company
        - transaction_date
        - transaction_price
        - transaction_shares
        - filing_date
    """
    params = {"symbol": symbol}
    return _make_api_request("INSIDER_TRANSACTIONS", params)


def parse_news_sentiment(news_data) -> dict:
    """Parse NEWS_SENTIMENT response into structured format.
    
    Args:
        news_data: Raw response from get_news() or get_global_news()
        
    Returns:
        Dict with summary statistics and article list
    """
    if isinstance(news_data, str):
        try:
            news_data = json.loads(news_data)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response", "articles": []}
    
    feed = news_data.get("feed", [])
    
    articles = []
    sentiment_scores = []
    
    for article in feed:
        articles.append({
            "title": article.get("title", ""),
            "summary": article.get("summary", "")[:200],
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "published": article.get("time_published", "")[:10],
            "sentiment_score": article.get("overall_sentiment_score", 0),
            "sentiment_label": article.get("overall_sentiment_label", "Neutral"),
            "tickers": [t.get("ticker") for t in article.get("ticker_sentiment", [])],
        })
        sentiment_scores.append(article.get("overall_sentiment_score", 0))
    
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
    
    return {
        "articles": articles,
        "count": len(articles),
        "avg_sentiment": round(avg_sentiment, 4),
        "sentiment_label": "Positive" if avg_sentiment > 0.05 else "Negative" if avg_sentiment < -0.05 else "Neutral",
    }
