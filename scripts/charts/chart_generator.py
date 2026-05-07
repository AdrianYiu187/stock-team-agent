#!/usr/bin/env python3
"""
Stock_Team_Agent 圖表生成模組
生成專業技術分析圖表：K線、成交量、MACD、RSI、布林帶等
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class ChartGenerator:
    """
    圖表生成引擎
    
    支援圖表類型：
    - K線圖 (Candlestick)
    - 成交量圖 (Volume)
    - MACD
    - RSI
    - 布林帶
    - 支撐/阻力
    """
    
    def __init__(self):
        self.name = "chart_generator"
    
    def candlestick(self, kline: List[Dict], symbol: str) -> Dict[str, Any]:
        """生成K線圖數據"""
        if not kline:
            return {"error": "No data"}
        
        candles = []
        for k in kline[-60:]:  # 最近60根K線
            candles.append({
                "date": k.get("date", ""),
                "open": k.get("open", 0),
                "high": k.get("high", 0),
                "low": k.get("low", 0),
                "close": k.get("close", 0),
                "volume": k.get("volume", 0),
            })
        
        return {
            "type": "candlestick",
            "symbol": symbol,
            "data": candles,
            "count": len(candles),
            "description": f"{symbol} K線圖 - 最近{len(candles)}根K線"
        }
    
    def volume(self, kline: List[Dict]) -> Dict[str, Any]:
        """生成成交量圖數據"""
        if not kline:
            return {"error": "No data"}
        
        volumes = []
        for k in kline[-60:]:
            is_up = k.get("close", 0) >= k.get("open", 0)
            volumes.append({
                "date": k.get("date", ""),
                "volume": k.get("volume", 0),
                "color": "green" if is_up else "red"
            })
        
        return {
            "type": "volume",
            "data": volumes,
            "avg_volume": sum(v["volume"] for v in volumes) / len(volumes) if volumes else 0,
        }
    
    def macd(self, kline: List[Dict]) -> Dict[str, Any]:
        """生成MACD圖表數據"""
        if len(kline) < 26:
            return {"error": "Insufficient data"}
        
        closes = [k["close"] for k in kline]
        
        # Calculate EMA
        def calc_ema(data, period):
            multiplier = 2 / (period + 1)
            ema = sum(data[:period]) / period
            for price in data[period:]:
                ema = (price - ema) * multiplier + ema
            return ema
        
        ema12 = calc_ema(closes, 12)
        ema26 = calc_ema(closes, 26)
        macd_line = ema12 - ema26
        
        # Signal line (simplified)
        signal_line = macd_line * 0.9
        histogram = macd_line - signal_line
        
        return {
            "type": "macd",
            "macd_line": round(macd_line, 2),
            "signal_line": round(signal_line, 2),
            "histogram": round(histogram, 2),
            "signal": "bullish" if histogram > 0 else "bearish",
            "description": f"MACD={macd_line:.2f}, Signal={signal_line:.2f}"
        }
    
    def rsi(self, kline: List[Dict], period: int = 14) -> Dict[str, Any]:
        """生成RSI圖表數據"""
        if len(kline) < period + 1:
            return {"error": "Insufficient data"}
        
        closes = [k["close"] for k in kline]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Overbought/Oversold
        if rsi > 70:
            condition = "overbought"
        elif rsi < 30:
            condition = "oversold"
        else:
            condition = "neutral"
        
        return {
            "type": "rsi",
            "value": round(rsi, 2),
            "period": period,
            "condition": condition,
            "signal": "sell" if condition == "overbought" else "buy" if condition == "oversold" else "hold",
            "description": f"RSI({period})={rsi:.1f} ({condition})"
        }
    
    def bollinger_bands(self, kline: List[Dict], period: int = 20, std_dev: float = 2.0) -> Dict[str, Any]:
        """生成布林帶圖表數據"""
        if len(kline) < period:
            return {"error": "Insufficient data"}
        
        closes = [k["close"] for k in kline[-period:]]
        middle = sum(closes) / len(closes)
        
        variance = sum((x - middle) ** 2 for x in closes) / len(closes)
        std = variance ** 0.5
        
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        current_price = closes[-1]
        position = (current_price - lower) / (upper - lower) if upper != lower else 0.5
        
        return {
            "type": "bollinger_bands",
            "upper": round(upper, 2),
            "middle": round(middle, 2),
            "lower": round(lower, 2),
            "current_price": round(current_price, 2),
            "position": round(position, 2),
            "signal": "oversold" if position < 0.2 else "overbought" if position > 0.8 else "neutral",
            "description": f"Price at {position:.0%} of bands"
        }
    
    def support_resistance(self, kline: List[Dict], lookback: int = 20) -> Dict[str, Any]:
        """識別支撐和阻力位"""
        if len(kline) < lookback:
            return {"error": "Insufficient data"}
        
        highs = [k["high"] for k in kline[-lookback:]]
        lows = [k["low"] for k in kline[-lookback:]]
        
        # Find pivot highs/lows
        resistance = max(highs)
        support = min(lows)
        
        current = kline[-1]["close"]
        
        return {
            "type": "support_resistance",
            "resistance": round(resistance, 2),
            "support": round(support, 2),
            "current": round(current, 2),
            "distance_to_resistance": round((resistance - current) / current * 100, 2),
            "distance_to_support": round((current - support) / current * 100, 2),
            "description": f"阻力${resistance:.2f}, 支撐${support:.2f}"
        }


if __name__ == "__main__":
    import random
    
    cg = ChartGenerator()
    
    # Mock kline
    kline = []
    base = 50.0
    for i in range(100):
        o = base + random.uniform(-1, 1)
        h = o + random.uniform(0, 1)
        l = o - random.uniform(0, 1)
        c = (h + l) / 2 + random.uniform(-0.3, 0.3)
        kline.append({"date": f"2026-04-{i%30+1:02d}", "open": o, "high": h, "low": l, "close": c, "volume": random.randint(1e6, 1e7)})
        base = c
    
    print("=== 圖表生成測試 ===")
    print("\nCandlestick:", cg.candlestick(kline, "0700.HK"))
    print("\nRSI:", cg.rsi(kline))
    print("\nBollinger:", cg.bollinger_bands(kline))
