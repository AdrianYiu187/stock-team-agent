#!/usr/bin/env python3
"""
新聞分析師 (News Analyst)
分析新聞覆蓋、情緒、影響力
"""

from typing import Dict, Any, Optional
from datetime import datetime


class NewsAnalyst:
    """新聞分析師"""

    def __init__(self, data_provider=None):
        self.data_provider = data_provider
        self.name = "news_analyst"

    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行新聞分析"""
        try:
            news_data = self._get_news_data(symbol)
            sentiment = self._analyze_news_sentiment(news_data)
            score = self._calculate_score(sentiment)

            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "news_data": news_data,
                "sentiment": sentiment,
                "score": score,
                "buy_score": sentiment.get("buy_score", 0),
                "hold_score": sentiment.get("hold_score", 0),
                "sell_score": sentiment.get("sell_score", 0),
                "signal": "buy" if score > 0.6 else "sell" if score < 0.4 else "neutral",
                "confidence": sentiment.get("confidence", 0.5),
                "summary": sentiment.get("summary", "新聞情緒分析"),
                "raw_findings": news_data,
            }
        except Exception as e:
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "score": 0.5,
                "signal": "neutral",
            }

    def _get_news_data(self, symbol: str) -> Dict[str, Any]:
        """獲取新聞數據"""
        if self.data_provider is None:
            return {"news_count": 0, "headlines": []}

        try:
            from data_sources.enhanced_news_feed_provider import EnhancedNewsFeedProvider

            provider = EnhancedNewsFeedProvider()
            all_feeds = provider.fetch_all_working(limit_per_source=15)
            combined = all_feeds.get("all", [])
            return {
                "news_count": len(combined),
                "headlines": [f.get("title", "") for f in combined[:10]],
                "sources": list(all_feeds.keys()),
            }
        except Exception:
            return {"news_count": 0, "headlines": []}

    def _analyze_news_sentiment(self, news_data: Dict) -> Dict[str, float]:
        """分析新聞情緒"""
        news_count = news_data.get("news_count", 0)
        if news_count == 0:
            return {
                "buy_score": 0.33,
                "hold_score": 0.34,
                "sell_score": 0.33,
                "confidence": 0.0,
                "summary": "無新聞數據",
            }

        # 基於新聞數量評分
        coverage_score = min(news_count / 20, 1.0)
        return {
            "buy_score": 0.33 + coverage_score * 0.1,
            "hold_score": 0.34 - coverage_score * 0.05,
            "sell_score": 0.33 - coverage_score * 0.05,
            "confidence": min(news_count / 10, 0.8),
            "summary": f"新聞覆蓋{news_count}條",
        }

    def _calculate_score(self, sentiment: Dict) -> float:
        """計算評分"""
        buy = sentiment.get("buy_score", 0.33)
        hold = sentiment.get("hold_score", 0.34)
        return buy + 0.5 * hold
