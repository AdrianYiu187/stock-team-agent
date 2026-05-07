#!/usr/bin/env python3
"""
基本面分析師 (Fundamental Analyst)
分析財務報表、估值指標、盈利能力、增長潛力
"""

from typing import Dict, Any, Optional
from datetime import datetime


class FundamentalAnalyst:
    """基本面分析師"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.name = "fundamental_analyst"
    
    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行基本面分析"""
        try:
            # 獲取財務數據
            financials = self._get_financial_data(symbol)
            
            # 計算估值指標
            valuation = self._calculate_valuation(financials)
            
            # 分析盈利能力
            profitability = self._analyze_profitability(financials)
            
            # 計算評分
            score_dict = self._calculate_score(valuation, profitability)
            # 將 dict 評分轉為 float (使用 buy - sell 作為主要分數)
            score = score_dict.get("confidence", 0.5)
            
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "financials": financials,
                "valuation": valuation,
                "profitability": profitability,
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
    
    def _get_financial_data(self, symbol: str) -> Dict:
        """獲取財務數據 - 優先使用真實市場數據"""
        try:
            # 先嘗試從 data_provider 獲取
            financials = self.data_provider.get_financials(symbol)
            # revenue=0 會被視為無效數據（因為真實公司不會 revenue=0）
            if financials and financials.get("revenue", 0) != 0:
                return financials
            
            # 嘗試從 yfinance 直接獲取
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                # 檢查關鍵數據是否存在
                total_rev = info.get("totalRevenue")
                if total_rev and total_rev > 0:
                    return {
                        "revenue": total_rev,
                        "net_income": info.get("netIncomeToCommon", 0) or info.get("netIncome", 0) or 0,
                        "total_assets": info.get("totalAssets", 0) or 0,
                        "total_equity": info.get("totalStockholderEquity", 0) or 0,
                        "debt_to_equity": (info.get("debtToEquity", 0) or 0) / 100 if info.get("debtToEquity") else None,
                        "current_ratio": info.get("currentRatio", 0) or None,
                        "roe": info.get("returnOnEquity", 0) or 0,
                        "roa": info.get("returnOnAssets", 0) or 0,
                        "eps": info.get("trailingEps", 0) or info.get("forwardEps", 0) or 0,
                        "pe_ratio": info.get("trailingPE", 0) or info.get("forwardPE", 0) or None,
                        "pb_ratio": info.get("priceToBook", 0) or None,
                        "dividend_yield": info.get("dividendYield", 0) or 0,
                        "revenue_growth": info.get("revenueGrowth", 0) or 0,
                        "profit_growth": info.get("earningsGrowth", 0) or 0,
                        "source": "yfinance",
                        "⚠️ FALLBACK": False
                    }
            except ImportError:
                pass
            
            # 無法獲取真實數據時明確標記
            return {
                "revenue": None,
                "net_income": None,
                "total_assets": None,
                "total_equity": None,
                "debt_to_equity": None,
                "current_ratio": None,
                "roe": None,
                "roa": None,
                "eps": None,
                "pe_ratio": None,
                "pb_ratio": None,
                "dividend_yield": None,
                "revenue_growth": None,
                "profit_growth": None,
                "source": "no_data",
                "⚠️ FALLBACK": True,
                "⚠️ REASON": "無法從市場或yfinance獲取財務數據"
            }
        except Exception as e:
            return {
                "source": "error",
                "⚠️ FALLBACK": True,
                "⚠️ ERROR": str(e)
            }
    
    def _calculate_valuation(self, financials: Dict) -> Dict[str, Any]:
        """計算估值指標"""
        pe = financials.get("pe_ratio", 15)
        pb = financials.get("pb_ratio", 1)
        dividend = financials.get("dividend_yield", 0)
        
        # 估值評估
        pe_score = self._evaluate_pe(pe)
        pb_score = self._evaluate_pb(pb)
        dividend_score = self._evaluate_dividend(dividend)
        
        return {
            "pe_ratio": pe,
            "pb_ratio": pb,
            "dividend_yield": dividend,
            "pe_score": pe_score,
            "pb_score": pb_score,
            "dividend_score": dividend_score,
            "overall": (pe_score + pb_score + dividend_score) / 3
        }
    
    def _evaluate_pe(self, pe: float) -> float:
        """評估市盈率"""
        if pe < 10:
            return 0.8  # 便宜
        elif pe < 15:
            return 0.6
        elif pe < 25:
            return 0.4
        elif pe < 40:
            return 0.2
        return 0.1  # 昂貴
    
    def _evaluate_pb(self, pb: float) -> float:
        """評估市淨率"""
        if pb < 1:
            return 0.8
        elif pb < 1.5:
            return 0.6
        elif pb < 3:
            return 0.4
        elif pb < 5:
            return 0.2
        return 0.1
    
    def _evaluate_dividend(self, dividend: float) -> float:
        """評估股息率"""
        if dividend > 0.08:
            return 0.9
        elif dividend > 0.05:
            return 0.7
        elif dividend > 0.03:
            return 0.5
        elif dividend > 0.01:
            return 0.3
        return 0.1
    
    def _analyze_profitability(self, financials: Dict) -> Dict[str, Any]:
        """分析盈利能力"""
        roe = financials.get("roe", 0)
        roa = financials.get("roa", 0)
        profit_margin = financials.get("net_income", 0) / financials.get("revenue", 1)
        
        roe_score = 0.8 if roe > 0.15 else 0.6 if roe > 0.10 else 0.4 if roe > 0.05 else 0.2
        
        return {
            "roe": roe,
            "roa": roa,
            "profit_margin": profit_margin,
            "roe_score": roe_score,
            "overall": (roe_score + (profit_margin * 2)) / 2
        }
    
    def _calculate_score(self, valuation: Dict, profitability: Dict) -> Dict[str, Any]:
        """計算基本面綜合評分"""
        val_overall = valuation.get("overall", 0.5)
        prof_overall = profitability.get("overall", 0.5)
        
        # 權衡估值和盈利
        overall = val_overall * 0.4 + prof_overall * 0.6
        
        buy_score = overall * 0.9 if overall > 0.6 else overall * 0.5
        sell_score = (1 - overall) * 0.9 if overall < 0.4 else (1 - overall) * 0.5
        hold_score = 1 - buy_score - sell_score
        
        signal = "buy" if overall > 0.6 else "sell" if overall < 0.4 else "neutral"
        
        return {
            "buy": round(buy_score, 3),
            "hold": round(hold_score, 3),
            "sell": round(sell_score, 3),
            "signal": signal,
            "confidence": round(overall, 2),
            "summary": f"基本面{'良好' if overall > 0.6 else '一般' if overall > 0.4 else '較差'}。估值{valuation.get('overall', 0):.2f}，盈利能力{profitability.get('overall', 0):.2f}。"
        }
