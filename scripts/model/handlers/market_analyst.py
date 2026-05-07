#!/usr/bin/env python3
"""
市場分析師 (Market Analyst)
分析市場狀態、板塊輪動、資金流向、宏觀因素
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class MarketAnalyst:
    """市場狀態分析師"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.name = "market_analyst"
    
    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行市場分析"""
        try:
            # 獲取市場數據
            market_data = self._get_market_data(symbol)
            
            # 分析市場情緒
            sentiment = self._analyze_market_sentiment(market_data)
            
            # 計算評分
            score = self._calculate_score(sentiment)
            
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "market_data": market_data,
                "sentiment": sentiment,
                "score": score,
                "buy_score": sentiment.get("buy_score", 0),
                "hold_score": sentiment.get("hold_score", 0),
                "sell_score": sentiment.get("sell_score", 0),
                "signal": sentiment.get("signal", "neutral"),
                "confidence": sentiment.get("confidence", 0.5),
                "summary": sentiment.get("summary", ""),
            }
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    def _get_market_data(self, symbol: str) -> Dict:
        """獲取市場數據"""
        # 嘗試從數據提供者獲取
        try:
            kline = self.data_provider.get_kline(symbol, period="daily", limit=20)
            if kline and len(kline) > 0:
                return {"kline": kline, "source": "provider"}
            raise ValueError("Empty kline")
        except Exception as e:
            import logging
            logging.warning(f"[MarketAnalyst] get_kline({symbol}) failed: {e} — no data")
            return {"source": "no_data", "note": "無法獲取市場數據"}
    
    def _analyze_market_sentiment(self, market_data: Dict) -> Dict[str, Any]:
        """分析市場情緒 - 根據真實市場數據計算"""
        kline = market_data.get("kline", [])
        
        if not kline or len(kline) < 5:
            # 無K線數據時返回未知
            return {
                "buy_score": 0.30,
                "hold_score": 0.40,
                "sell_score": 0.30,
                "signal": "neutral",
                "confidence": 0.3,
                "summary": "市場數據不足，無法判斷趨勢"
            }
        
        # 根據近期價格變化計算市場情緒
        recent_closes = [k.get("close", 0) for k in kline[-5:] if k.get("close")]
        if len(recent_closes) < 2:
            return {
                "buy_score": 0.30,
                "hold_score": 0.40,
                "sell_score": 0.30,
                "signal": "neutral",
                "confidence": 0.3,
                "summary": "K線數據不足"
            }
        
        # 計算近期趨勢
        price_change = (recent_closes[-1] - recent_closes[0]) / recent_closes[0] if recent_closes[0] > 0 else 0
        
        # 計算成交量變化
        volumes = [k.get("volume", 0) for k in kline[-5:] if k.get("volume")]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        recent_volume = volumes[-1] if volumes else avg_volume
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # 根據價格變化和成交量判斷市場情緒
        if price_change > 0.02 and volume_ratio > 1.2:
            signal = "bullish"
            buy, hold, sell = 0.55, 0.30, 0.15
            confidence = 0.70
            summary = f"市場偏多：價格上漲{price_change:.1%}，成交量放大{volume_ratio:.1%}"
        elif price_change > 0.01:
            signal = "neutral_bullish"
            buy, hold, sell = 0.40, 0.40, 0.20
            confidence = 0.60
            summary = f"市場小幅上漲({price_change:.1%})，成交量穩定"
        elif price_change < -0.02 and volume_ratio > 1.2:
            signal = "bearish"
            buy, hold, sell = 0.15, 0.30, 0.55
            confidence = 0.70
            summary = f"市場偏空：價格下跌{abs(price_change):.1%}，成交量放大"
        elif price_change < -0.01:
            signal = "neutral_bearish"
            buy, hold, sell = 0.20, 0.40, 0.40
            confidence = 0.60
            summary = f"市場小幅下跌({price_change:.1%})"
        else:
            signal = "neutral"
            buy, hold, sell = 0.30, 0.45, 0.25
            confidence = 0.50
            summary = f"市場觀望：價格變化{price_change:+.1%}，成交量比率{volume_ratio:.2f}"
        
        return {
            "buy_score": round(buy, 3),
            "hold_score": round(hold, 3),
            "sell_score": round(sell, 3),
            "signal": signal,
            "confidence": confidence,
            "summary": summary
        }
    
    def _calculate_score(self, sentiment: Dict) -> float:
        """計算綜合評分"""
        buy = sentiment.get("buy_score", 0)
        sell = sentiment.get("sell_score", 0)
        return round((buy - sell) * 0.5 + 0.5, 2)
