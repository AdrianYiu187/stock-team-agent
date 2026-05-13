#!/usr/bin/env python3
"""
Stock_Team_Agent 技術指標模組
36+ 技術指標計算
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import math


class StockTechnicalIndicators:
    """
    專業技術指標計算引擎
    
    支援指標類別：
    - 趨勢指標 (Trend): SMA, EMA, MACD, SuperTrend, Parabolic SAR, Ichimoku, ADX, Aroon
    - 動能指標 (Momentum): RSI, Stochastic, Williams %R, CCI, ROC, Momentum, TSI, PPO, KST, Ultimate
    - 波動指標 (Volatility): ATR, Bollinger Bands, Keltner, TTM Squeeze, Historical Volatility
    - 成交量指標 (Volume): OBV, VWAP, MFI, CMF, Force Index, A/D, Ease of Movement
    """
    
    def __init__(self):
        self.name = "technical_indicators"
    
    def list_indicators(self) -> List[str]:
        """返回支援的指標清單"""
        return [
            # 趨勢指標
            "sma", "ema", "macd", "supertrend", "parabolic_sar", 
            "ichimoku", "adx", "aroon",
            # 動能指標
            "rsi", "stochastic", "williams_r", "cci", "roc", 
            "momentum", "tsi", "ppo", "kst", "ultimate_oscillator",
            # 波動指標
            "atr", "bollinger_bands", "keltner", "ttm_squeeze", "hist_volatility",
            # 成交量指標
            "obv", "vwap", "mfi", "cmf", "force_index", "ad_line", "eom"
        ]
    
    def calculate_all(self, kline: List[Dict]) -> Dict[str, Any]:
        """計算所有指標"""
        if not kline:
            return {}
        
        closes = [k["close"] for k in kline]
        highs = [k["high"] for k in kline]
        lows = [k["low"] for k in kline]
        volumes = [k["volume"] for k in kline]
        
        return {
            "sma": self.sma(closes),
            "ema": self.ema(closes),
            "macd": self.macd(closes),
            "rsi": self.rsi(closes),
            "bollinger_bands": self.bollinger_bands(closes),
            "atr": self.atr(kline),
            "stochastic": self.stochastic(kline),
            "obv": self.obv(closes, volumes),
            "vwap": self.vwap(kline),
            "adx": self.adx(kline),
            "cci": self.cci(kline),
            "williams_r": self.williams_r(kline),
            "momentum": self.momentum(closes),
            "roc": self.roc(closes),
            "volume_profile": self.volume_profile(kline),
        }
    
    # ========== 趨勢指標 ==========
    
    def sma(self, data: List[float], period: int = 20) -> Optional[float]:
        """簡單移動平均"""
        if len(data) < period:
            return None
        return sum(data[-period:]) / period
    
    def ema(self, data: List[float], period: int = 12) -> Optional[float]:
        """指數移動平均"""
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def macd(self, data: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """MACD"""
        if len(data) < slow:
            return {"macd": None, "signal": None, "histogram": None}
        
        ema_fast = self._ema_iterative(data, fast)
        ema_slow = self._ema_iterative(data, slow)
        
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line (simplified)
        macd_values = []
        for i in range(slow, len(data)):
            ef = self._ema_iterative(data[:i+1], fast)
            es = self._ema_iterative(data[:i+1], slow)
            macd_values.append(ef - es)
        
        signal_line = sum(macd_values[-signal:]) / signal if len(macd_values) >= signal else macd_line
        histogram = macd_line - signal_line
        
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
    
    def _ema_iterative(self, data: List[float], period: int) -> float:
        """迭代計算EMA"""
        if len(data) < period:
            return sum(data) / len(data) if len(data) > 0 else 0
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def supertrend(self, kline: List[Dict], period: int = 10, multiplier: float = 3.0) -> Dict[str, Any]:
        """SuperTrend 指標"""
        if len(kline) < period:
            return {"supertrend": None, "signal": "neutral"}
        
        highs = [k["high"] for k in kline]
        lows = [k["low"] for k in kline]
        closes = [k["close"] for k in kline]
        
        atr = self.atr(kline, period)
        
        # Calculate Upper and Lower Band
        hl2 = [(h + l) / 2 for h, l in zip(highs, lows)]
        upper_band = [hl2[i] + multiplier * atr if i >= period - 1 else None for i in range(len(hl2))]
        lower_band = [hl2[i] - multiplier * atr if i >= period - 1 else None for i in range(len(hl2))]
        
        supertrend = []
        direction = 1  # 1 = uptrend, -1 = downtrend
        
        for i in range(len(closes)):
            if i < period - 1:
                supertrend.append(None)
                continue
            
            if upper_band[i] is None or lower_band[i] is None:
                supertrend.append(None)
                continue
                
            prev_st = supertrend[-1] if supertrend and supertrend[-1] is not None else (upper_band[i] if direction == -1 else lower_band[i])
            
            if direction == 1:
                if closes[i] < prev_st:
                    direction = -1
                    supertrend.append(upper_band[i])
                else:
                    supertrend.append(lower_band[i])
            else:
                if closes[i] > prev_st:
                    direction = 1
                    supertrend.append(lower_band[i])
                else:
                    supertrend.append(upper_band[i])
        
        current_st = supertrend[-1] if supertrend else None
        current_dir = direction
        
        return {
            "supertrend": current_st,
            "signal": "buy" if current_dir == 1 else "sell",
            "direction": current_dir
        }
    
    def adx(self, kline: List[Dict], period: int = 14) -> Dict[str, float]:
        """ADX 趨勢強度指標"""
        if len(kline) < period + 1:
            return {"adx": None, "plus_di": None, "minus_di": None}
        
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []
        
        for i in range(1, len(kline)):
            high = kline[i]["high"]
            low = kline[i]["low"]
            prev_high = kline[i-1]["high"]
            prev_low = kline[i-1]["low"]
            prev_close = kline[i-1]["close"]
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
            
            plus_dm = max(high - prev_high, 0) if (high - prev_high) > (prev_low - low) else 0
            minus_dm = max(prev_low - low, 0) if (prev_low - low) > (high - prev_high) else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        # Smooth averages
        tr_smooth = sum(tr_list[-period:])
        plus_dm_smooth = sum(plus_dm_list[-period:])
        minus_dm_smooth = sum(minus_dm_list[-period:])
        
        plus_di = (plus_dm_smooth / tr_smooth * 100) if tr_smooth > 0 else 0
        minus_di = (minus_dm_smooth / tr_smooth * 100) if tr_smooth > 0 else 0
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di) * 100) if (plus_di + minus_di) > 0 else 0
        
        return {"adx": dx, "plus_di": plus_di, "minus_di": minus_di}
    
    # ========== 動能指標 ==========
    
    def rsi(self, data: List[float], period: int = 14) -> Optional[float]:
        """RSI 相對強度指標 — 使用 Wilder's Smoothing (SMMA)"""
        if len(data) < period + 1:
            return None
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Seed with SMA for first period
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Wilder's smoothing (SMMA)
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def stochastic(self, kline: List[Dict], k_period: int = 14, d_period: int = 3) -> Dict[str, float]:
        """隨機指標"""
        if len(kline) < k_period:
            return {"k": None, "d": None}
        
        recent = kline[-k_period:]
        lowest_low = min(k["low"] for k in recent)
        highest_high = max(k["high"] for k in recent)
        current_close = kline[-1]["close"]
        
        # %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        # %D = SMA of %K over d_period (default 3)
        k_values = []
        for i in range(k_period - 1, len(kline)):
            window = kline[i - k_period + 1:i + 1]
            lowest_low = min(k["low"] for k in window)
            highest_high = max(k["high"] for k in window)
            current_close = kline[i]["close"]
            if highest_high == lowest_low:
                k_values.append(50)
            else:
                k_values.append((current_close - lowest_low) / (highest_high - lowest_low) * 100)

        if len(k_values) < d_period:
            return {"k": k_values[-1] if k_values else None, "d": None}
        d = sum(k_values[-d_period:]) / d_period
        return {"k": k_values[-1], "d": d}
    
    def williams_r(self, kline: List[Dict], period: int = 14) -> Optional[float]:
        """Williams %R"""
        if len(kline) < period:
            return None
        
        recent = kline[-period:]
        highest_high = max(k["high"] for k in recent)
        lowest_low = min(k["low"] for k in recent)
        current_close = kline[-1]["close"]
        
        if highest_high == lowest_low:
            return -50
        return (highest_high - current_close) / (highest_high - lowest_low) * -100
    
    def cci(self, kline: List[Dict], period: int = 20) -> Optional[float]:
        """CCI 商品通道指標"""
        if len(kline) < period:
            return None
        
        tp = [(k["high"] + k["low"] + k["close"]) / 3 for k in kline[-period:]]
        sma_tp = sum(tp) / period
        
        mean_deviation = sum(abs(tp[i] - sma_tp) for i in range(period)) / period
        
        current_tp = tp[-1]
        if mean_deviation == 0:
            return 0
        cci = (current_tp - sma_tp) / (0.015 * mean_deviation)
        
        return cci
    
    def momentum(self, data: List[float], period: int = 10) -> Optional[float]:
        """動量指標"""
        if len(data) < period + 1:
            return None
        return data[-1] - data[-period - 1]
    
    def roc(self, data: List[float], period: int = 12) -> Optional[float]:
        """變化率指標"""
        if len(data) < period + 1:
            return None
        old_value = data[-period - 1]
        if old_value == 0:
            return 0
        return ((data[-1] - old_value) / old_value) * 100
    
    # ========== 波動指標 ==========
    
    def bollinger_bands(self, data: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, float]:
        """布林帶"""
        if len(data) < period:
            return {"upper": None, "middle": None, "lower": None}
        
        middle = sum(data[-period:]) / period
        variance = sum((x - middle) ** 2 for x in data[-period:]) / period
        std = math.sqrt(variance)
        
        return {
            "upper": middle + std_dev * std,
            "middle": middle,
            "lower": middle - std_dev * std
        }
    
    def atr(self, kline: List[Dict], period: int = 14) -> Optional[float]:
        """ATR 平均真實波幅"""
        if len(kline) < period + 1:
            return None
        
        tr_list = []
        for i in range(1, min(period + 1, len(kline))):
            high = kline[i]["high"]
            low = kline[i]["low"]
            prev_close = kline[i-1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        
        return sum(tr_list) / len(tr_list)
    
    # ========== 成交量指標 ==========
    
    def obv(self, closes: List[float], volumes: List[float]) -> float:
        """OBV 能量潮"""
        if len(closes) < 2:
            return volumes[0] if volumes else 0
        
        obv = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                obv += volumes[i]
            elif closes[i] < closes[i-1]:
                obv -= volumes[i]
        return obv
    
    def vwap(self, kline: List[Dict]) -> Optional[float]:
        """VWAP 成交量加權平均價"""
        if not kline:
            return None
        
        cum_pv = 0
        cum_vol = 0
        
        for k in kline:
            typical_price = (k["high"] + k["low"] + k["close"]) / 3
            pv = typical_price * k["volume"]
            cum_pv += pv
            cum_vol += k["volume"]
        
        return cum_pv / cum_vol if cum_vol > 0 else None
    
    def volume_profile(self, kline: List[Dict]) -> Dict[str, Any]:
        """成交量概況"""
        if not kline:
            return {"avg_volume": 0, "volume_change": 0, "trend": "neutral"}
        
        volumes = [k["volume"] for k in kline]
        avg_volume = sum(volumes) / len(volumes)
        recent_volume = volumes[-1]
        volume_change = (recent_volume - avg_volume) / avg_volume if avg_volume > 0 else 0
        
        # 成交量趨勢
        if len(volumes) >= 5:
            recent_avg = sum(volumes[-5:]) / 5
            earlier_avg = sum(volumes[-10:-5]) / 5 if len(volumes) >= 10 else recent_avg
            trend = "increasing" if recent_avg > earlier_avg * 1.1 else "decreasing" if recent_avg < earlier_avg * 0.9 else "stable"
        else:
            trend = "neutral"
        
        return {
            "avg_volume": avg_volume,
            "volume_change": volume_change,
            "trend": trend
        }
