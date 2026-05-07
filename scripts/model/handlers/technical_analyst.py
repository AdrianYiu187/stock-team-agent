#!/usr/bin/env python3
"""
技術分析師 (Technical Analyst)
分析K線形態、技術指標、趨勢、信號
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import math


class TechnicalAnalyst:
    """技術分析師"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.name = "technical_analyst"
        
        # 技術指標配置
        self.indicators_config = {
            "sma": {"periods": [20, 50, 200]},
            "ema": {"periods": [12, 26]},
            "rsi": {"period": 14, "overbought": 70, "oversold": 30},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "bollinger": {"period": 20, "std": 2},
            "atr": {"period": 14},
            "stoch": {"k_period": 14, "d_period": 3},
        }
    
    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行技術分析"""
        try:
            # 獲取K線數據
            kline = self._get_kline_data(symbol)
            
            # 計算技術指標
            indicators = self._calculate_indicators(kline)
            
            # 識別形態
            patterns = self._recognize_patterns(kline)
            
            # 生成信號
            signals = self._generate_signals(indicators, patterns)
            
            # 計算評分
            score = self._calculate_score(signals, indicators)
            
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "indicators": indicators,
                "patterns": patterns,
                "signals": signals,
                "score": score,
                "buy_score": signals.get("buy_score", 0),
                "hold_score": signals.get("hold_score", 0),
                "sell_score": signals.get("sell_score", 0),
                "signal": signals.get("signal", "neutral"),
                "confidence": signals.get("confidence", 0.5),
                "summary": signals.get("summary", ""),
            }
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    def _get_kline_data(self, symbol: str) -> List[Dict]:
        """獲取K線數據 - 優先使用真實市場數據"""
        try:
            kline = self.data_provider.get_kline(symbol, period="daily", limit=100)
            if kline and isinstance(kline, list) and len(kline) > 0:
                # 檢查數據是否有效（非全為Mock）
                has_real = any(not k.get("⚠️ MOCK_DATA") for k in kline if isinstance(k, dict))
                return kline
            raise ValueError("Empty or invalid kline")
        except Exception as e:
            import logging
            logging.warning(f"[TechnicalAnalyst] get_kline({symbol}) failed: {e} — no data")
            return []  # 不再自動生成mock，讓調用方處理空數據
    
    def _generate_mock_kline(self) -> List[Dict]:
        """生成模擬K線數據（⚠️ MOCK_DATA - 僅用於測試）"""
        import random
        base_price = 50.0
        kline = []
        for i in range(100):
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
                "date": f"2026-04-{30-i:02d}" if i < 30 else f"2026-03-{31-i:02d}",
                "⚠️ MOCK_DATA": True,
                "⚠️ MOCK_REASON": "技術分析師無法獲取真實K線，使用模擬數據"
            })
            base_price = close
        return kline
    
    def _calculate_indicators(self, kline: List[Dict]) -> Dict[str, Any]:
        """計算技術指標"""
        if not kline:
            return {}
        
        closes = [k["close"] for k in kline]
        volumes = [k["volume"] for k in kline]
        
        return {
            "sma20": self._sma(closes, 20),
            "sma50": self._sma(closes, 50),
            "sma200": self._sma(closes, 200) if len(closes) >= 200 else None,
            "ema12": self._ema(closes, 12),
            "ema26": self._ema(closes, 26),
            "rsi": self._rsi(closes, 14),
            "macd": self._macd(closes),
            "bollinger": self._bollinger_bands(closes, 20),
            "atr": self._atr(kline, 14),
            "stoch": self._stochastic(kline, 14, 3),
            "volume_profile": self._volume_profile(kline),
        }
    
    def _sma(self, data: List[float], period: int) -> Optional[float]:
        if len(data) < period:
            return None
        return sum(data[-period:]) / period
    
    def _ema(self, data: List[float], period: int) -> Optional[float]:
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def _rsi(self, data: List[float], period: int = 14) -> Optional[float]:
        if len(data) < period + 1:
            return None
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _macd(self, data: List[float]) -> Dict[str, float]:
        if len(data) < 26:
            return {"macd": None, "signal": None, "histogram": None}
        ema12 = self._ema(data, 12)
        ema26 = self._ema(data, 26)
        macd_line = ema12 - ema26
        # Signal line (9-period EMA of MACD) - simplified
        signal = macd_line * 0.9
        histogram = macd_line - signal
        return {"macd": macd_line, "signal": signal, "histogram": histogram}
    
    def _bollinger_bands(self, data: List[float], period: int = 20) -> Dict[str, float]:
        if len(data) < period:
            return {"upper": None, "middle": None, "lower": None}
        sma = self._sma(data, period)
        std = math.sqrt(sum((x - sma)**2 for x in data[-period:]) / period)
        return {
            "upper": sma + 2 * std,
            "middle": sma,
            "lower": sma - 2 * std
        }
    
    def _atr(self, kline: List[Dict], period: int = 14) -> Optional[float]:
        if len(kline) < period + 1:
            return None
        true_ranges = []
        for i in range(1, min(period + 1, len(kline))):
            high = kline[i]["high"]
            low = kline[i]["low"]
            prev_close = kline[i-1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        return sum(true_ranges) / len(true_ranges)
    
    def _stochastic(self, kline: List[Dict], k_period: int, d_period: int) -> Dict[str, float]:
        if len(kline) < k_period:
            return {"k": None, "d": None}
        recent = kline[-k_period:]
        lowest_low = min(k["low"] for k in recent)
        highest_high = max(k["high"] for k in recent)
        current_close = kline[-1]["close"]
        if highest_high == lowest_low:
            k = 50
        else:
            k = (current_close - lowest_low) / (highest_high - lowest_low) * 100
        return {"k": k, "d": k * 0.9}  # Simplified D
    
    def _volume_profile(self, kline: List[Dict]) -> Dict[str, float]:
        if not kline:
            return {"avg_volume": 0, "volume_change": 0}
        volumes = [k["volume"] for k in kline[-20:]]
        avg_volume = sum(volumes) / len(volumes)
        recent_volume = volumes[-1]
        volume_change = (recent_volume - avg_volume) / avg_volume if avg_volume > 0 else 0
        return {"avg_volume": avg_volume, "volume_change": volume_change}
    
    def _recognize_patterns(self, kline: List[Dict]) -> List[Dict[str, Any]]:
        """識別K線形態"""
        patterns = []
        if len(kline) < 20:
            return patterns
        
        # 檢測支撐/阻力位
        closes = [k["close"] for k in kline]
        highs = [k["high"] for k in kline]
        lows = [k["low"] for k in kline]
        
        # 簡單的支撐阻力檢測
        recent_lows = sorted(lows[-20:])[:5]
        recent_highs = sorted(highs[-20:], reverse=True)[:5]
        
        patterns.append({
            "type": "support_resistance",
            "support": sum(recent_lows) / len(recent_lows),
            "resistance": sum(recent_highs) / len(recent_highs),
            "strength": 0.6
        })
        
        return patterns
    
    def _generate_signals(self, indicators: Dict, patterns: List) -> Dict[str, Any]:
        """生成交易信號"""
        buy_score = 0.0
        hold_score = 0.0
        sell_score = 0.0
        
        # RSI 信號
        rsi = indicators.get("rsi")
        if rsi:
            if rsi < 30:
                buy_score += 0.25
            elif rsi > 70:
                sell_score += 0.25
            else:
                hold_score += 0.15
        
        # MACD 信號
        macd = indicators.get("macd", {})
        if macd.get("histogram", 0) > 0:
            buy_score += 0.2
        elif macd.get("histogram", 0) < 0:
            sell_score += 0.2
        
        # 布林帶信號
        bb = indicators.get("bollinger", {})
        current_price = indicators.get("sma20") or 50  # Fallback
        if bb.get("lower") and current_price < bb["lower"]:
            buy_score += 0.2
        elif bb.get("upper") and current_price > bb["upper"]:
            sell_score += 0.2
        
        # 標準化
        total = buy_score + hold_score + sell_score
        if total > 0:
            buy_score /= total
            hold_score /= total
            sell_score /= total
        
        # 信號判定
        if buy_score > 0.5:
            signal = "buy"
        elif sell_score > 0.5:
            signal = "sell"
        elif buy_score > hold_score:
            signal = "buy"
        elif sell_score > hold_score:
            signal = "sell"
        else:
            signal = "neutral"
        
        confidence = max(buy_score, hold_score, sell_score)
        
        return {
            "buy_score": round(buy_score, 3),
            "hold_score": round(hold_score, 3),
            "sell_score": round(sell_score, 3),
            "signal": signal,
            "confidence": round(confidence, 2),
            "summary": self._generate_summary(signal, indicators)
        }
    
    def _generate_summary(self, signal: str, indicators: Dict) -> str:
        """生成分析摘要"""
        rsi = indicators.get("rsi", 0)
        macd = indicators.get("macd", {})
        
        if signal == "buy":
            return f"技術指標顯示買入信號。RSI={rsi:.1f}，MACD histogram={'正' if macd.get('histogram', 0) > 0 else '負'}。"
        elif signal == "sell":
            return f"技術指標顯示賣出信號。RSI={rsi:.1f}，MACD histogram={'正' if macd.get('histogram', 0) > 0 else '負'}。"
        return f"技術指標顯示中性。RSI={rsi:.1f}，建議觀望。"
    
    def _calculate_score(self, signals: Dict, indicators: Dict) -> float:
        """計算技術分析綜合評分"""
        buy = signals.get("buy_score", 0)
        sell = signals.get("sell_score", 0)
        return round((buy - sell) * 0.5 + 0.5, 2)
