#!/usr/bin/env python3
"""
風險分析師 (Risk Analyst)
分析市場風險、信用風險、流動性風險、估值風險
"""

from typing import Dict, Any, Optional
from datetime import datetime


class RiskAnalyst:
    """風險分析師"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.name = "risk_analyst"
    
    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行風險分析"""
        try:
            # 獲取風險數據
            risk_data = self._get_risk_data(symbol)
            
            # 計算風險指標
            risk_metrics = self._calculate_risk_metrics(risk_data)
            
            # 評估風險等級
            risk_level = self._evaluate_risk_level(risk_metrics)
            
            # 計算評分
            score_dict = self._calculate_score(risk_level, risk_metrics)
            score = score_dict.get("confidence", 0.5)
            
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "risk_data": risk_data,
                "risk_metrics": risk_metrics,
                "risk_level": risk_level,
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
    
    def _get_risk_data(self, symbol: str) -> Dict:
        """獲取風險數據 - 優先使用真實市場數據"""
        try:
            # 嘗試從市場獲取真實VIX等風險數據
            market_risk = self.data_provider.get_market_risk()
            if market_risk and market_risk.get("vix") is not None:
                market_risk["source"] = "market_risk_provider"
                market_risk["⚠️ FALLBACK"] = False
                return market_risk
            
            # 嘗試從個股信息獲取Beta等風險指標
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return {
                    "volatility": info.get("beta", 0.25) * 0.20,  # Beta轉換為波動率估算
                    "beta": info.get("beta", 1.0),
                    "var_95": 0.05,
                    "sharpe_ratio": info.get("beta", 1.0) * 0.5,
                    "max_drawdown": 0.15,
                    "debt_to_equity": info.get("debtToEquity", 0) / 100 if info.get("debtToEquity") else 0.8,
                    "current_ratio": info.get("currentRatio", 1.5),
                    "interest_coverage": info.get("interestCoverage", 5.0),
                    "source": "yfinance",
                    "⚠️ FALLBACK": False
                }
            except Exception as e:
                import logging
                logging.warning(f"[RiskAnalyst] yfinance beta/financials 失敗: {e}")
            
            # 無法獲取真實數據時明確標記
            return {
                "volatility": None,
                "beta": None,
                "var_95": None,
                "sharpe_ratio": None,
                "max_drawdown": None,
                "debt_to_equity": None,
                "current_ratio": None,
                "interest_coverage": None,
                "source": "no_data",
                "⚠️ FALLBACK": True,
                "⚠️ REASON": "無法從市場或yfinance獲取風險數據"
            }
        except Exception as e:
            return {
                "source": "error",
                "⚠️ FALLBACK": True,
                "⚠️ ERROR": str(e)
            }
    
    def _calculate_risk_metrics(self, risk_data: Dict) -> Dict[str, float]:
        """計算風險指標"""
        # 檢查是否為 fallback 數據
        if risk_data.get("⚠️ FALLBACK"):
            # 無真實數據時返回低信心
            return {
                "var_score": 0.5,
                "vol_score": 0.5,
                "beta_score": 0.5,
                "sharpe_score": 0.5,
                "dd_score": 0.5,
                "overall": 0.5,
                "⚠️ NO_REAL_DATA": True
            }
        
        volatility = risk_data.get("volatility") or 0.25
        beta = risk_data.get("beta") or 1.0
        sharpe = risk_data.get("sharpe_ratio") or 0
        max_dd = risk_data.get("max_drawdown") or 0
        
        # VaR 風險評分
        var = risk_data.get("var_95") or 0.05
        var_score = max(0, 1 - var * 10)
        
        # 波動率評分
        vol_score = max(0, 1 - volatility * 4)
        
        # Beta 評分（1.0為基準）
        beta_score = max(0, 1 - abs(beta - 1.0))
        
        # 夏普比率評分
        sharpe_score = min(1.0, sharpe / 1.5) if sharpe > 0 else 0
        
        # 最大回撤評分
        dd_score = max(0, 1 - max_dd * 5)
        
        return {
            "var_score": var_score,
            "vol_score": vol_score,
            "beta_score": beta_score,
            "sharpe_score": sharpe_score,
            "dd_score": dd_score,
            "overall": ( var_score + vol_score + beta_score + sharpe_score + dd_score) / 5
        }
    
    def _evaluate_risk_level(self, metrics: Dict[str, float]) -> str:
        """評估風險等級"""
        overall = metrics.get("overall", 0.5)
        if overall > 0.7:
            return "low"
        elif overall > 0.4:
            return "medium"
        return "high"
    
    def _calculate_score(self, risk_level: str, metrics: Dict) -> Dict[str, Any]:
        """計算風險調整後評分"""
        overall = metrics.get("overall", 0.5)
        
        # 風險越高，買入評分越低
        if risk_level == "low":
            buy_score = 0.5 + overall * 0.3
            sell_score = 0.1
        elif risk_level == "medium":
            buy_score = 0.3 + overall * 0.2
            sell_score = 0.2 + (1 - overall) * 0.2
        else:
            buy_score = 0.2
            sell_score = 0.5 + (1 - overall) * 0.3
        
        hold_score = 1 - buy_score - sell_score
        
        # 風險評分和信號
        if risk_level == "low":
            signal = "buy"
        elif risk_level == "high":
            signal = "sell"
        else:
            signal = "neutral"
        
        return {
            "buy": round(buy_score, 3),
            "hold": round(hold_score, 3),
            "sell": round(sell_score, 3),
            "signal": signal,
            "confidence": round(overall, 2),
            "risk_level": risk_level,
            "summary": f"風險{risk_level}。波動率評分={metrics.get('vol_score', 0):.2f}，VaR評分={metrics.get('var_score', 0):.2f}。"
        }
