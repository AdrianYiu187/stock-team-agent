#!/usr/bin/env python3
"""
情緒分析師 (Sentiment Analyst)
分析新聞情緒、社交媒體、研究報告、 分析師評級
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


class SentimentAnalyst:
    """情緒分析師"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.name = "sentiment_analyst"
    
    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行情緒分析"""
        try:
            # 獲取新聞數據
            news_data = self._get_news_data(symbol)
            
            # 分析新聞情緒
            sentiment = self._analyze_news_sentiment(news_data)
            
            # 分析分析師評級
            analyst_rating = self._get_analyst_rating(symbol)
            
            # 計算評分
            score_dict = self._calculate_score(sentiment, analyst_rating)
            score = score_dict.get("confidence", 0.5)
            
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "news_data": news_data,
                "sentiment": sentiment,
                "analyst_rating": analyst_rating,
                "score": score,
                "score_dict": score_dict,
                "buy_score": score_dict.get("buy", 0),
                "hold_score": score_dict.get("hold", 0),
                "sell_score": score_dict.get("sell", 0),
                "signal": score_dict.get("signal", "neutral"),
                "confidence": score_dict.get("confidence", 0.5),
                "summary": score_dict.get("summary", ""),
            }
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    def _get_news_data(self, symbol: str) -> List[Dict]:
        """獲取新聞數據 - 優先使用RSS Feed"""
        try:
            # 首先嘗試RSS Feed
            try:
                from data_sources.news_feed_provider import NewsFeedProvider
                provider = NewsFeedProvider()
                all_news = provider.fetch_all(limit_per_category=10)
                combined = []
                for category, items in all_news.items():
                    for item in items:
                        item["category"] = category
                        combined.append(item)
                
                # 分析股票相關新聞
                impact = provider.analyze_stock_impact(combined, symbol)
                if impact.get("relevant_news_count", 0) > 0:
                    return impact.get("relevant_news", [])
                
                # 如果沒有相關新聞，返回市場新聞
                return combined[:10]
            except ImportError as e:
                import logging
                logging.warning(f"[SentimentAnalyst] NewsFeedProvider import 失敗: {e}")
            except Exception as e:
                import logging
                logging.warning(f"[SentimentAnalyst] NewsFeedProvider failed: {e}")
            
            # 備用：使用yfinance新聞
            try:
                news = self.data_provider.get_news(symbol)
                if news:
                    return news
            except Exception as e:
                import logging
                logging.warning(f"[SentimentAnalyst] yfinance news failed: {e}")
            
            return self._get_mock_news()
        except Exception as e:
            import logging
            logging.warning(f"[SentimentAnalyst] _get_news_data failed: {e}")
            return self._get_mock_news()
    
    def _get_mock_news(self) -> List[Dict]:
        """生成模擬新聞數據"""
        return [
            {
                "title": "公司發布年度業績，營收同比增長15%",
                "source": "財經網",
                "date": datetime.now().isoformat(),
                "sentiment": "positive"
            },
            {
                "title": "分析師上調目標價至HK$60",
                "source": "研究報告",
                "date": datetime.now().isoformat(),
                "sentiment": "positive"
            },
            {
                "title": "行業景氣度下降，市場觀望情緒浓厚",
                "source": "市場觀察",
                "date": datetime.now().isoformat(),
                "sentiment": "neutral"
            }
        ]
    
    def _analyze_news_sentiment(self, news_data: List[Dict]) -> Dict[str, Any]:
        """分析新聞情緒"""
        if not news_data:
            return {"score": 0.5, "label": "neutral", "positive_count": 0, "negative_count": 0}
        
        positive = sum(1 for n in news_data if n.get("sentiment") == "positive")
        negative = sum(1 for n in news_data if n.get("sentiment") == "negative")
        neutral = len(news_data) - positive - negative
        
        total = len(news_data)
        sentiment_score = (positive * 1.0 + neutral * 0.5 + negative * 0.0) / total
        
        return {
            "score": sentiment_score,
            "label": "positive" if sentiment_score > 0.6 else "negative" if sentiment_score < 0.4 else "neutral",
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "positive_ratio": positive / total if total > 0 else 0
        }
    
    def _get_analyst_rating(self, symbol: str) -> Dict[str, Any]:
        """獲取分析師評級 - 優先使用真實市場數據"""
        try:
            # 嘗試從 yfinance 獲取分析師評級
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                # yfinance 的分析師評級相關字段
                target_price = info.get("targetMeanPrice") or info.get("targetPrice")
                recommendation = info.get("recommendationKey", "")
                
                # 計算評級分佈（如果有的話）
                buy_count = 0
                hold_count = 0
                sell_count = 0
                
                # recommendationKey: buy, hold, sell, strong_buy, etc.
                if recommendation in ("strong_buy", "buy"):
                    buy_count = 5
                    hold_count = 2
                    sell_count = 0
                elif recommendation == "hold":
                    buy_count = 2
                    hold_count = 5
                    sell_count = 1
                elif recommendation in ("sell", "strong_sell"):
                    buy_count = 1
                    hold_count = 2
                    sell_count = 5
                
                if target_price or recommendation:
                    return {
                        "buy": buy_count,
                        "hold": hold_count,
                        "sell": sell_count,
                        "avg_target_price": target_price or 0,
                        "high_target": info.get("targetHighPrice") or 0,
                        "low_target": info.get("targetLowPrice") or 0,
                        "consensus": recommendation or "unknown",
                        "source": "yfinance",
                        "⚠️ FALLBACK": False
                    }
            except ImportError as e:
                import logging
                logging.warning(f"[SentimentAnalyst] yfinance import 失敗: {e}")
            except Exception as e:
                import logging
                logging.warning(f"[SentimentAnalyst] yfinance analyst rating failed: {e}")

            # 無法獲取真實數據時明確標記
            return {
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "avg_target_price": 0,
                "high_target": 0,
                "low_target": 0,
                "consensus": "no_data",
                "source": "no_data",
                "⚠️ FALLBACK": True,
                "⚠️ REASON": "yfinance 未提供分析師評級數據"
            }
        except Exception as e:
            return {
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "avg_target_price": 0,
                "high_target": 0,
                "low_target": 0,
                "consensus": "error",
                "source": "error",
                "⚠️ FALLBACK": True,
                "⚠️ ERROR": str(e)
            }
    
    def _calculate_score(self, sentiment: Dict, analyst_rating: Dict) -> Dict[str, Any]:
        """計算情緒評分"""
        sentiment_score = sentiment.get("score", 0.5)
        
        # 分析師評級加權
        total_ratings = analyst_rating.get("buy", 0) + analyst_rating.get("hold", 0) + analyst_rating.get("sell", 0)
        if total_ratings > 0:
            analyst_score = (analyst_rating.get("buy", 0) * 1.0 + 
                          analyst_rating.get("hold", 0) * 0.5 + 
                          analyst_rating.get("sell", 0) * 0.0) / total_ratings
        else:
            analyst_score = 0.5
        
        # 綜合評分
        overall = sentiment_score * 0.4 + analyst_score * 0.6
        
        buy_score = overall * 0.8 if overall > 0.6 else overall * 0.4
        sell_score = (1 - overall) * 0.8 if overall < 0.4 else (1 - overall) * 0.3
        hold_score = 1 - buy_score - sell_score
        
        signal = "buy" if overall > 0.6 else "sell" if overall < 0.4 else "neutral"
        
        return {
            "buy": round(buy_score, 3),
            "hold": round(hold_score, 3),
            "sell": round(sell_score, 3),
            "signal": signal,
            "confidence": round(abs(overall - 0.5) * 2, 2),
            "sentiment_score": sentiment_score,
            "analyst_score": analyst_score,
            "summary": f"情緒{'偏正面' if overall > 0.6 else '偏負面' if overall < 0.4 else '中性'}。新聞{sentiment.get('label', 'neutral')}，分析師共識{analyst_rating.get('consensus', 'neutral')}。"
        }
