#!/usr/bin/env python3
"""
Hybrid Data Provider - Stock_Team_Agent
整合 Yahoo Finance + Alpha Vantage + Mock Fallback

策略：
1. Yahoo Finance (主要) - 速度快，覆蓋廣
2. Alpha Vantage (備援) - 當 yfinance 失敗時使用
3. Mock Data (最終) - 僅當前兩者都失敗時用於測試

使用方式：
    from hybrid_provider import HybridDataProvider
    provider = HybridDataProvider()
    klines = provider.get_kline("AAPL")
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HybridDataProvider:
    """混合數據提供者 - Yahoo Finance + Alpha Vantage + Mock Fallback
    
    層級fallback策略：
    1. Yahoo Finance (主要)
    2. Alpha Vantage (備援)
    3. Mock Data (最終備援，⚠️ 僅測試用)
    
    Usage:
        provider = HybridDataProvider()
        klines = provider.get_kline("0700.HK")  # 港股
        klines = provider.get_kline("AAPL")       # 美股
        financials = provider.get_financials("0999.HK")
        indicator = provider.get_indicator("AAPL", "rsi", "2024-01-01", 30)
    """
    
    def __init__(self, region: str = "hk", use_alpha_vantage: bool = True):
        """初始化混合提供者。
        
        Args:
            region: 市場區域 "hk", "us", "cn"
            use_alpha_vantage: 是否啟用 Alpha Vantage 備援 (default: True)
        """
        self.region = region
        self.use_alpha_vantage = use_alpha_vantage
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.cache_ttl = 300  # 5分鐘
        
        # Alpha Vantage provider (lazy loaded)
        self._av_provider = None
        
        # 市場配置
        self.market_config = {
            "hk": {"vix_symbol": "^VIX", "name": "香港"},
            "us": {"vix_symbol": "^VIX", "name": "美國"},
            "cn": {"vix_symbol": "^VIX", "name": "中國"},
        }
    
    @property
    def av_provider(self):
        """Lazy load Alpha Vantage provider."""
        if self._av_provider is None and self.use_alpha_vantage:
            try:
                from alpha_vantage import AlphaVantageProvider
                self._av_provider = AlphaVantageProvider()
                logger.info("[HybridDataProvider] Alpha Vantage provider initialized")
            except ValueError as e:
                logger.warning(f"[HybridDataProvider] Alpha Vantage not available: {e}")
                self._av_provider = None
        return self._av_provider
    
    # ===== Core Data Methods =====
    
    def get_kline(self, symbol: str, period: str = "daily", limit: int = 100) -> List[Dict]:
        """獲取K線數據，自動fallback。
        
        順序：Yahoo Finance → Alpha Vantage → Mock Data
        """
        cache_key = f"kline_{symbol}_{period}_{limit}"
        if cached := self._get_cache(cache_key):
            return cached
        
        # 嘗試 Yahoo Finance
        try:
            result = self._get_yfinance_kline(symbol, period, limit)
            if result:
                self._set_cache(cache_key, result)
                logger.info(f"[HybridDataProvider] {symbol} kline from Yahoo Finance")
                return result
        except Exception as e:
            logger.warning(f"[HybridDataProvider] Yahoo Finance failed for {symbol}: {e}")
        
        # 嘗試 Alpha Vantage
        if self.av_provider:
            try:
                result = self.av_provider.get_kline(symbol, period, limit)
                if result:
                    self._set_cache(cache_key, result)
                    logger.info(f"[HybridDataProvider] {symbol} kline from Alpha Vantage")
                    return result
            except Exception as e:
                logger.warning(f"[HybridDataProvider] Alpha Vantage failed for {symbol}: {e}")
        
        # 最終 Mock (⚠️ 測試用)
        logger.warning(f"[HybridDataProvider] All providers failed for {symbol}, using mock data")
        return self._generate_mock_kline(limit, symbol)
    
    def get_financials(self, symbol: str) -> Dict:
        """獲取財務數據，自動fallback。"""
        cache_key = f"financials_{symbol}"
        if cached := self._get_cache(cache_key):
            return cached
        
        # 嘗試 Yahoo Finance
        try:
            result = self._get_yfinance_financials(symbol)
            if result:
                self._set_cache(cache_key, result, ttl=3600)
                logger.info(f"[HybridDataProvider] {symbol} financials from Yahoo Finance")
                return result
        except Exception as e:
            logger.warning(f"[HybridDataProvider] Yahoo Finance failed for {symbol} financials: {e}")
        
        # 嘗試 Alpha Vantage
        if self.av_provider:
            try:
                result = self.av_provider.get_financials(symbol)
                if result:
                    self._set_cache(cache_key, result, ttl=3600)
                    logger.info(f"[HybridDataProvider] {symbol} financials from Alpha Vantage")
                    return result
            except Exception as e:
                logger.warning(f"[HybridDataProvider] Alpha Vantage failed for {symbol} financials: {e}")
        
        # Mock
        logger.warning(f"[HybridDataProvider] All providers failed for {symbol} financials, using mock")
        return self._get_mock_financials()
    
    def get_news(self, symbol: str, limit: int = 20) -> List[Dict]:
        """獲取新聞，自動fallback。"""
        cache_key = f"news_{symbol}_{limit}"
        if cached := self._get_cache(cache_key):
            return cached
        
        # Yahoo Finance news
        try:
            result = self._get_yfinance_news(symbol, limit)
            if result:
                self._set_cache(cache_key, result, ttl=600)
                return result
        except Exception as e:
            logger.warning(f"[HybridDataProvider] Yahoo Finance news failed: {e}")
        
        # Alpha Vantage news
        if self.av_provider:
            try:
                result = self.av_provider.get_news(symbol, limit)
                if result:
                    self._set_cache(cache_key, result, ttl=600)
                    return result
            except Exception as e:
                logger.warning(f"[HybridDataProvider] Alpha Vantage news failed: {e}")
        
        return []
    
    def get_market_risk(self) -> Dict:
        """獲取市場風險指標。"""
        cache_key = "market_risk"
        if cached := self._get_cache(cache_key):
            return cached
        
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1mo")
            current_vix = vix_data["Close"].iloc[-1] if len(vix_data) > 0 else 20
            
            result = {
                "vix": current_vix,
                "volatility": min(current_vix / 40, 1.0),
                "risk_level": "high" if current_vix > 30 else "medium" if current_vix > 20 else "low"
            }
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"[HybridDataProvider] VIX fetch failed: {e}")
            return {"vix": 20, "volatility": 0.25, "risk_level": "medium"}
    
    def get_indicator(self, symbol: str, indicator: str, curr_date: str, look_back: int = 30) -> str:
        """獲取技術指標（僅支援 Alpha Vantage）。
        
        Args:
            symbol: 股票代碼
            indicator: 指標名稱 (rsi, macd, sma, ema, boll, atr)
            curr_date: 當前日期 YYYY-MM-DD
            look_back: 回看天數 (default: 30)
            
        Returns:
            指標數值字串，格式為 "YYYY-MM-DD: value" 列表
        """
        cache_key = f"indicator_{symbol}_{indicator}_{curr_date}_{look_back}"
        if cached := self._get_cache(cache_key):
            return cached
        
        # 主要使用 Alpha Vantage
        if self.av_provider:
            try:
                result = self.av_provider.get_indicator(symbol, indicator, curr_date, look_back)
                self._set_cache(cache_key, result)
                return result
            except Exception as e:
                logger.warning(f"[HybridDataProvider] Alpha Vantage indicator failed: {e}")
        
        # 如果沒有 Alpha Vantage，回退到本地計算
        logger.warning(f"[HybridDataProvider] Falling back to local indicator calculation")
        return self._calculate_local_indicator(symbol, indicator, curr_date, look_back)
    
    # ===== Yahoo Finance Private Methods =====
    
    def _get_yfinance_kline(self, symbol: str, period: str, limit: int) -> List[Dict]:
        """從 Yahoo Finance 獲取K線。"""
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo" if period == "daily" else "1mo")
        
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
        return klines[-limit:] if len(klines) > limit else klines
    
    def _get_yfinance_financials(self, symbol: str) -> Dict:
        """從 Yahoo Finance 獲取財務數據。"""
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
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
    
    def _get_yfinance_news(self, symbol: str, limit: int) -> List[Dict]:
        """從 Yahoo Finance 獲取新聞。"""
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        result = []
        for item in news[:limit]:
            result.append({
                "title": item.get("title", ""),
                "source": item.get("publisher", ""),
                "date": datetime.fromtimestamp(item.get("providerPublishTime", 0)).isoformat(),
                "sentiment": "neutral"
            })
        return result
    
    # ===== Local Indicator Calculation =====
    
    def _calculate_local_indicator(self, symbol: str, indicator: str, curr_date: str, look_back: int) -> str:
        """當 Alpha Vantage 不可用時，使用本地計算指標。"""
        # 先獲取K線數據
        klines = self.get_kline(symbol, limit=look_back + 50)
        if not klines or len(klines) < 20:
            return f"Error: Insufficient data for {indicator} calculation"
        
        import pandas as pd
        df = pd.DataFrame(klines)
        
        if indicator == "sma":
            df["sma"] = df["close"].rolling(window=20).mean()
            result = df[["date", "close", "sma"]].dropna().tail(look_back)
            return "\n".join([f"{row['date']}: {row['sma']:.2f}" for _, row in result.iterrows()])
        elif indicator == "ema":
            df["ema"] = df["close"].ewm(span=12, adjust=False).mean()
            result = df[["date", "close", "ema"]].dropna().tail(look_back)
            return "\n".join([f"{row['date']}: {row['ema']:.2f}" for _, row in result.iterrows()])
        elif indicator == "rsi":
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df["rsi"] = 100 - (100 / (1 + rs))
            result = df[["date", "rsi"]].dropna().tail(look_back)
            return "\n".join([f"{row['date']}: {row['rsi']:.2f}" for _, row in result.iterrows()])
        else:
            return f"Error: Local calculation for '{indicator}' not implemented. Use Alpha Vantage."
    
    # ===== Cache Methods =====
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """獲取緩存。"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
        return None
    
    def _set_cache(self, key: str, data: Any, ttl: int = 300):
        """設置緩存。"""
        self.cache[key] = (data, datetime.now())
    
    # ===== Mock Data (⚠️ 測試用) =====
    
    def _generate_mock_kline(self, limit: int, symbol: str = "UNKNOWN") -> List[Dict]:
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
                "⚠️ SOURCE": f"Mock (all providers failed for {symbol})"
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
            "⚠️ SOURCE": "Mock (all providers failed)"
        }
