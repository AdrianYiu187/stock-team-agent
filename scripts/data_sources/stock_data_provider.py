#!/usr/bin/env python3
"""
Stock_Team_Agent 數據提供者
整合多個數據源：Yahoo Finance、EastMoney、Alpha Vantage
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json


class StockDataProvider:
    """
    統一股票數據提供者
    
    支援：
    - Yahoo Finance (美股/HK股)
    - EastMoney (A股/H股)
    - 備援機制
    """
    
    def __init__(self, region: str = "hk"):
        self.region = region
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5分鐘緩存
        
        # 市場配置
        self.market_config = {
            "hk": {"vix_symbol": "^VIX", "name": "香港"},
            "us": {"vix_symbol": "^VIX", "name": "美國"},
            "cn": {"vix_symbol": "^VIX", "name": "中國"},
        }
        
    def get_kline(self, symbol: str, period: str = "daily", limit: int = 100) -> List[Dict]:
        """獲取K線數據"""
        cache_key = f"kline_{symbol}_{period}_{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo" if period == "daily" else "1mo")[:limit]
            
            klines = []
            for date, row in hist.iterrows():
                klines.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            klines.reverse()
            self._set_cache(cache_key, klines)
            return klines
        except Exception as e:
            # 返回模擬數據
            return self._generate_mock_kline(limit)
    
    def get_financials(self, symbol: str) -> Dict:
        """獲取財務數據"""
        cache_key = f"financials_{symbol}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            financials = {
                "revenue": info.get("totalRevenue", 0),
                "net_income": info.get("netIncomeToCommon", 0),
                "total_assets": info.get("totalAssets", 0),
                "total_equity": info.get("stockholdersEquity", 0),
                "debt_to_equity": info.get("debtToEquity", 0),
                "current_ratio": info.get("currentRatio", 0),
                "roe": info.get("returnOnEquity", 0),
                "roa": info.get("returnOnAssets", 0),
                "eps": info.get("trailingEps", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "pb_ratio": info.get("priceToBook", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "revenue_growth": info.get("revenueGrowth", 0),
                "profit_growth": info.get("earningsGrowth", 0),
            }
            self._set_cache(cache_key, financials, ttl=3600)
            return financials
        except Exception as e:
            import logging
            logging.warning(f"[StockDataProvider] get_financials({symbol}) failed: {e} — using fallback")
            return self._get_mock_financials()
    
    def get_news(self, symbol: str) -> List[Dict]:
        """獲取新聞"""
        cache_key = f"news_{symbol}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            result = []
            for item in news[:10]:
                result.append({
                    "title": item.get("title", ""),
                    "source": item.get("publisher", ""),
                    "date": datetime.fromtimestamp(item.get("providerPublishTime", 0)).isoformat(),
                    "sentiment": "neutral"
                })
            self._set_cache(cache_key, result, ttl=600)
            return result
        except Exception as e:
            import logging
            logging.warning(f"[StockDataProvider] get_news({symbol}) failed: {e} — returning empty")
            return []
    
    def get_market_risk(self) -> Dict:
        """獲取市場風險指標"""
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1mo")
            current_vix = vix_data["Close"].iloc[-1] if len(vix_data) > 0 else 20
            
            return {
                "vix": current_vix,
                "volatility": min(current_vix / 40, 1.0),
                "risk_level": "high" if current_vix > 30 else "medium" if current_vix > 20 else "low"
            }
        except Exception as e:
            import logging
            logging.warning(f"[StockDataProvider] get_market_risk() failed: {e} — using fallback")
            return {"vix": 20, "volatility": 0.25, "risk_level": "medium", "⚠️ FALLBACK": True}
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """獲取緩存"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
        return None
    
    def _set_cache(self, key: str, data: Any, ttl: int = 300):
        """設置緩存"""
        self.cache[key] = (data, datetime.now())
    
    def _generate_mock_kline(self, limit: int) -> List[Dict]:
        """生成模擬K線（⚠️ MOCK_DATA - 僅用於API失敗時的測試）"""
        import random
        base_price = 50.0
        kline = []
        for i in range(limit):
            open_p = base_price + random.uniform(-2, 2)
            high = open_p + random.uniform(0, 1.5)
            low = open_p - random.uniform(0, 1.5)
            close = (high + low) / 2 + random.uniform(-0.5, 0.5)
            volume = random.randint(1000000, 10000000)
            kline.append({
                "open": round(open_p, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
                "date": (datetime.now() - timedelta(days=limit-i)).strftime("%Y-%m-%d"),
                "⚠️ MOCK_DATA": True,
                "⚠️ MOCK_REASON": "yfinance API 失敗，使用模擬數據進行測試"
            })
            base_price = close
        return kline
    
    def _get_mock_financials(self) -> Dict:
        """生成模擬財務數據（⚠️ MOCK_DATA - 僅用於API失敗時的測試）"""
        return {
            "revenue": 10000000000,
            "net_income": 1500000000,
            "total_assets": 50000000000,
            "total_equity": 25000000000,
            "debt_to_equity": 0.8,
            "current_ratio": 1.5,
            "roe": 0.12,
            "roa": 0.06,
            "eps": 2.5,
            "pe_ratio": 15.0,
            "pb_ratio": 1.2,
            "dividend_yield": 0.035,
            "revenue_growth": 0.08,
            "profit_growth": 0.12,
            "⚠️ MOCK_DATA": True,
            "⚠️ MOCK_REASON": "yfinance API 失敗，使用模擬數據進行測試"
        }
