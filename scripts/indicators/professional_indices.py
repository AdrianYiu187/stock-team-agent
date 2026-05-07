#!/usr/bin/env python3
"""
Stock_Team_Agent 專業指數模組
計算專業投資指標：巴菲特指標、席勒市盈率、黃金切割率、風險評分等
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import math


class ProfessionalIndices:
    """
    專業投資指數引擎
    
    支援指數：
    - 巴菲特指標 (Market Cap / GDP)
    - 席勒市盈率 (CAPE)
    - 格雷厄姆數字
    - 風險評分 (VaR, CVaR, Sharpe, Sortino)
    - 板塊輪動指標
    - 恐慌指標 (VIX)
    """
    
    def __init__(self):
        self.name = "professional_indices"
    
    def list_indices(self) -> List[str]:
        """返回支援的指數清單"""
        return [
            "buffett_indicator",
            "shiller_pe",
            "graham_number",
            "risk_score",
            "var_cvar",
            "sharpe_ratio",
            "sortino_ratio",
            "omega_ratio",
            "calmar_ratio",
            "sector_momentum",
            "market_breadth",
            "put_call_ratio",
            "gold_cross_signal",
            "death_cross_signal",
        ]
    
    def buffett_indicator(self, market_cap: float, gdp: float) -> Dict[str, Any]:
        if gdp == 0:
            return {"error": "GDP cannot be zero"}
        
        ratio = market_cap / gdp
        
        if ratio < 0.5:
            verdict = "嚴重低估"
            signal = "buy"
        elif ratio < 0.75:
            verdict = "相對低估"
            signal = "buy"
        elif ratio < 0.90:
            verdict = "相對合理"
            signal = "hold"
        elif ratio < 1.15:
            verdict = "輕微高估"
            signal = "sell"
        else:
            verdict = "嚴重高估"
            signal = "sell"
        
        return {
            "name": "巴菲特指標",
            "value": round(ratio, 4),
            "percentage": round(ratio * 100, 2),
            "verdict": verdict,
            "signal": signal,
            "description": f"股市總市值/GDP = {ratio:.2%}"
        }
    
    def shiller_pe(self, price: float, avg_earnings: float, periods: int = 10) -> Dict[str, Any]:
        if avg_earnings <= 0:
            return {"error": "Invalid earnings data"}
        
        cape = price / avg_earnings
        
        if cape < 10:
            verdict = "嚴重低估"
            signal = "buy"
        elif cape < 15:
            verdict = "相對低估"
            signal = "buy"
        elif cape < 20:
            verdict = "合理"
            signal = "hold"
        elif cape < 25:
            verdict = "輕微高估"
            signal = "sell"
        else:
            verdict = "嚴重高估"
            signal = "sell"
        
        return {
            "name": "席勒市盈率",
            "value": round(cape, 2),
            "avg_earnings": avg_earnings,
            "verdict": verdict,
            "signal": signal,
            "description": f"CAPE = {cape:.2f}"
        }
    
    def graham_number(self, eps: float, book_value_per_share: float) -> Dict[str, Any]:
        if eps <= 0 or book_value_per_share <= 0:
            return {"error": "EPS and BVPS must be positive"}
        
        graham_num = math.sqrt(22.5 * eps * book_value_per_share)
        
        return {
            "name": "格雷厄姆數字",
            "value": round(graham_num, 2),
            "eps": eps,
            "book_value_per_share": book_value_per_share,
            "formula": "sqrt(22.5 * EPS * BVPS)",
            "description": f"內在價值上限 = ${graham_num:.2f}"
        }
    
    def risk_score(self, returns: List[float], volatility: float, beta: float = 1.0) -> Dict[str, Any]:
        if not returns:
            return {"error": "No returns data"}
        
        vol_score = min(volatility * 200, 40)
        beta_score = min(abs(beta - 1) * 30, 30) if beta > 0 else 15
        negative_returns = [r for r in returns if r < 0]
        tail_risk = len(negative_returns) / len(returns) * 30 if returns else 15
        
        total_score = vol_score + beta_score + tail_risk
        
        risk_level = "low" if total_score < 30 else "medium" if total_score < 50 else "high"
        
        return {
            "name": "綜合風險評分",
            "value": round(total_score, 1),
            "risk_level": risk_level,
            "components": {
                "volatility_risk": round(vol_score, 1),
                "beta_risk": round(beta_score, 1),
                "tail_risk": round(tail_risk, 1)
            },
            "signal": "buy" if risk_level == "low" else "sell" if risk_level == "high" else "hold"
        }
    
    def sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> Dict[str, Any]:
        if len(returns) < 2:
            return {"error": "Insufficient data"}
        
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0
        
        if std_dev == 0:
            return {"error": "Zero standard deviation"}
        
        sharpe = (avg_return - risk_free_rate) / std_dev
        
        if sharpe < 0:
            verdict = "差"
        elif sharpe < 0.5:
            verdict = "尚可"
        elif sharpe < 1.0:
            verdict = "良好"
        elif sharpe < 2.0:
            verdict = "優秀"
        else:
            verdict = "極佳"
        
        return {
            "name": "夏普比率",
            "value": round(sharpe, 3),
            "verdict": verdict,
            "avg_return": round(avg_return, 4),
            "std_dev": round(std_dev, 4),
            "signal": "buy" if sharpe > 1.0 else "hold"
        }
    
    def var_cvar(self, returns: List[float], confidence: float = 0.95) -> Dict[str, Any]:
        if not returns:
            return {"error": "No returns data"}
        
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        var = -sorted_returns[index] if index < len(sorted_returns) else 0
        
        tail_losses = [r for r in returns if r <= -var]
        cvar = -sum(tail_losses) / len(tail_losses) if tail_losses else var
        
        return {
            "name": "風險價值",
            "var_95": round(var * 100, 2),
            "cvar_95": round(cvar * 100, 2),
            "description": f"95%信心下，單日最大損失 VaR={var:.2%}, CVaR={cvar:.2%}",
            "signal": "sell" if var > 0.05 else "hold"
        }
    
    def gold_cross_death_cross(self, sma_50: float, sma_200: float, prev_sma_50: float, prev_sma_200: float) -> Dict[str, Any]:
        current_golden = sma_50 > sma_200
        previous_golden = prev_sma_50 > prev_sma_200
        
        if current_golden and not previous_golden:
            signal = "golden_cross"
            verdict = "金叉形成 - 買入信號"
        elif not current_golden and previous_golden:
            signal = "death_cross"
            verdict = "死叉形成 - 賣出信號"
        elif current_golden:
            signal = "bullish"
            verdict = "多頭排列 - 持續看好"
        else:
            signal = "bearish"
            verdict = "空頭排列 - 謹慎觀望"
        
        return {
            "name": "交叉信號",
            "signal": signal,
            "verdict": verdict,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "description": verdict
        }
    
    def sector_momentum(self, sector_etf_returns: List[float], market_return: float = 0) -> Dict[str, Any]:
        """
        計算板塊動量指標
        
        參數:
            sector_etf_returns: 該板塊ETF的日/週收益率列表
            market_return: 大盤收益率（可選）
        
        返回:
            {
                "name": "板塊動量",
                "momentum_score": float,  # 正數=強於大盤，負數=弱於大盤
                "signal": "sector_rotation_signal",
                "verdict": str,
                "relative_strength": float
            }
        """
        if not sector_etf_returns:
            return {"error": "No sector ETF returns data", "⚠️ MOCK_DATA": True}
        
        # 計算該板塊的平均收益率
        avg_sector_return = sum(sector_etf_returns) / len(sector_etf_returns)
        
        # 計算動量（相對大盤）
        relative_strength = avg_sector_return - market_return if market_return else avg_sector_return
        
        # 計算動量得分（標準化）
        if len(sector_etf_returns) >= 2:
            variance = sum((r - avg_sector_return) ** 2 for r in sector_etf_returns) / len(sector_etf_returns)
            std_dev = variance ** 0.5
            if std_dev > 0:
                momentum_score = relative_strength / std_dev
            else:
                momentum_score = 0
        else:
            momentum_score = relative_strength * 10
        
        # 判斷信號
        if momentum_score > 1.0:
            verdict = "強勢板塊，積極配置"
            signal = "overweight"
        elif momentum_score > 0.5:
            verdict = "穩健板塊，適度配置"
            signal = "neutral"
        elif momentum_score > -0.5:
            verdict = "落後大盤，減持"
            signal = "underweight"
        else:
            verdict = "弱勢明顯，規避"
            signal = "avoid"
        
        return {
            "name": "板塊動量",
            "momentum_score": round(momentum_score, 3),
            "avg_sector_return": round(avg_sector_return, 4),
            "market_return": round(market_return, 4),
            "relative_strength": round(relative_strength, 4),
            "verdict": verdict,
            "signal": signal,
            "description": f"板塊相對大盤動量: {relative_strength:+.2%}"
        }
    
    def market_breadth(self, advancing_stocks: int, declining_stocks: int, 
                       advancing_volume: float = 0, declining_volume: float = 0) -> Dict[str, Any]:
        """
        計算市場廣度指標
        
        參數:
            advancing_stocks: 上涨股票数量
            declining_stocks: 下跌股票数量
            advancing_volume: 上涨股票成交量（可選）
            declining_volume: 下跌股票成交量（可選）
        
        返回:
            {
                "name": "市場廣度",
                "breadth_ratio": float,  # (advance-decline) / total
                "signal": str,
                "verdict": str,
                "volume_ratio": float  # 如果有成交量數據
            }
        """
        total_stocks = advancing_stocks + declining_stocks
        if total_stocks == 0:
            return {"error": "No stock data", "⚠️ MOCK_DATA": True}
        
        # A/D 指標
        ad_ratio = (advancing_stocks - declining_stocks) / total_stocks
        
        # 廣度比率
        breadth_ratio = ad_ratio  # -1 到 1
        
        # 成交量比率（如果提供）
        volume_ratio = None
        if advancing_volume > 0 and declining_volume > 0:
            total_volume = advancing_volume + declining_volume
            volume_ratio = (advancing_volume - declining_volume) / total_volume
        
        # 判斷信號
        if breadth_ratio > 0.3:
            verdict = "市場廣度強勁，上漲趨勢健康"
            signal = "bullish"
        elif breadth_ratio > 0.1:
            verdict = "市場廣度正面，偏多"
            signal = "neutral_bullish"
        elif breadth_ratio > -0.1:
            verdict = "市場分化，觀望"
            signal = "neutral"
        elif breadth_ratio > -0.3:
            verdict = "市場廣度負面，偏空"
            signal = "neutral_bearish"
        else:
            verdict = "市場廣度惡劣，下跌趨勢蔓延"
            signal = "bearish"
        
        result = {
            "name": "市場廣度",
            "breadth_ratio": round(breadth_ratio, 4),
            "advancing_stocks": advancing_stocks,
            "declining_stocks": declining_stocks,
            "total_stocks": total_stocks,
            "verdict": verdict,
            "signal": signal,
            "description": f"A/D比率: {breadth_ratio:+.2%} ({advancing_stocks}漲/{declining_stocks}跌)"
        }
        
        if volume_ratio is not None:
            result["volume_ratio"] = round(volume_ratio, 4)
            result["description"] += f", 成交量A/D: {volume_ratio:+.2%}"
        
        return result
    
    def put_call_ratio(self, put_volume: float, call_volume: float) -> Dict[str, Any]:
        """
        計算看跌/看漲比率 (Put/Call Ratio)
        
        參數:
            put_volume: 看跌期權成交量
            call_volume: 看漲期權成交量
        
        返回:
            {
                "name": "沽購比率",
                "pcr": float,  # put/call ratio
                "signal": str,
                "verdict": str,
                "interpretation": str
            }
        """
        if call_volume == 0:
            return {"error": "Call volume is zero", "⚠️ MOCK_DATA": True}
        
        pcr = put_volume / call_volume
        
        # 判斷信號
        if pcr > 1.2:
            verdict = "過度悲觀，可能見底信號"
            signal = "contrarian_bullish"
            interpretation = "PCR高於1.2通常暗示市場過度恐慌，可能出現反向買入機會"
        elif pcr > 0.9:
            verdict = "謹慎情緒，可能調整"
            signal = "cautious"
            interpretation = "PCR高於0.9顯示投資者對沖需求增加，需關注風險"
        elif pcr > 0.7:
            verdict = "情緒中性"
            signal = "neutral"
            interpretation = "PCR在正常區間，市場情緒平穩"
        elif pcr > 0.5:
            verdict = "情緒偏多"
            signal = "neutral_bullish"
            interpretation = "PCR低於0.7顯示市場信心較強，但需防範過度樂觀"
        else:
            verdict = "過度樂觀，可能見頂信號"
            signal = "contrarian_bearish"
            interpretation = "PCR低於0.5通常暗示市場過度樂觀，可能出現調整"
        
        return {
            "name": "沽購比率",
            "pcr": round(pcr, 4),
            "put_volume": put_volume,
            "call_volume": call_volume,
            "verdict": verdict,
            "signal": signal,
            "interpretation": interpretation,
            "description": f"PCR = {pcr:.2f}"
        }


if __name__ == "__main__":
    pi = ProfessionalIndices()
    
    # Test
    print("=== 專業指數測試 ===")
    print("\n巴菲特指標:")
    result = pi.buffett_indicator(market_cap=50e12, gdp=25e12)
    print(result)
    
    print("\n格雷厄姆數字:")
    result = pi.graham_number(eps=2.5, book_value_per_share=20.0)
    print(result)
    
    print("\n風險評分:")
    import random
    returns = [random.uniform(-0.05, 0.05) for _ in range(100)]
    result = pi.risk_score(returns=returns, volatility=0.2, beta=1.1)
    print(result)
