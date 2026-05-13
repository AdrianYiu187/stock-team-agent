#!/usr/bin/env python3
"""
Stock_Team_Agent 估值模型模組
DCF、DDM、Dividend Discount、PEG等專業估值方法
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import math


class ValuationModels:
    """
    專業估值模型引擎
    
    支援模型：
    - DCF (現金流折現)
    - DDM (股息折現)
    - PEG (市盈率相對增長)
    - Graham Formula (格雷厄姆公式)
    - Reverse DCF
    """
    
    def __init__(self):
        self.name = "valuation_models"
    
    def list_models(self) -> List[str]:
        return [
            "dcf",
            "ddm",
            "peg",
            "graham_formula",
            "reverse_dcf",
            "dividend_yield_model",
        ]
    
    def dcf(self, cash_flows: List[float], discount_rate: float, terminal_growth: float = 0.02, shares_outstanding: float = 1.0) -> Dict[str, Any]:
        """
        DCF 現金流折現模型
        
        公式：EV = sum(CF_t / (1+r)^t) + TV / (1+r)^n
        """
        if not cash_flows or discount_rate <= 0:
            return {"error": "Invalid inputs"}
        
        pv_sum = 0
        year = 1
        for cf in cash_flows:
            pv_sum += cf / ((1 + discount_rate) ** year)
            year += 1
        
        # Terminal Value
        if len(cash_flows) > 0:
            last_cf = cash_flows[-1]
            if discount_rate <= terminal_growth:
                pv_terminal = 0  # 避免除零，terminal_growth >= discount_rate 無意義
            else:
                terminal_value = last_cf * (1 + terminal_growth) / (discount_rate - terminal_growth)
                pv_terminal = terminal_value / ((1 + discount_rate) ** len(cash_flows))
        else:
            pv_terminal = 0
        
        total_ev = pv_sum + pv_terminal
        # 修復：假設 cash_flows 單位是百萬，shares_outstanding 單位是百萬股
        # intrinsic_value = total_ev (百萬) / shares (百萬) = 每股價格
        intrinsic_value = total_ev / shares_outstanding
        
        return {
            "model": "DCF",
            "enterprise_value": round(total_ev, 2),
            "intrinsic_value": round(intrinsic_value, 2) if intrinsic_value > 0.01 else round(intrinsic_value, 6),
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "pv_sum": round(pv_sum, 2),
            "terminal_value": round(pv_terminal, 2),
            "shares_outstanding": shares_outstanding,
            "description": f"DCF估值：每股內在價值 ${intrinsic_value:.2f}"
        }
    
    def ddm(self, dividend_per_share: float, discount_rate: float, growth_rate: float, years: int = 5) -> Dict[str, Any]:
        """
        DDM 股息折現模型
        
        公式：V = sum(D_t / (1+r)^t) + D_(n+1) / (r-g)
        """
        if discount_rate <= growth_rate:
            return {"error": "Growth rate must be less than discount rate"}
        
        pv_sum = 0
        for year in range(1, years + 1):
            dividend = dividend_per_share * ((1 + growth_rate) ** year)
            pv_sum += dividend / ((1 + discount_rate) ** year)
        
        # Terminal value
        d_n1 = dividend_per_share * ((1 + growth_rate) ** (years + 1))
        terminal_value = d_n1 / (discount_rate - growth_rate)
        pv_terminal = terminal_value / ((1 + discount_rate) ** years)
        
        intrinsic_value = pv_sum + pv_terminal
        
        return {
            "model": "DDM",
            "intrinsic_value": round(intrinsic_value, 2),
            "discount_rate": discount_rate,
            "growth_rate": growth_rate,
            "initial_dividend": dividend_per_share,
            "description": f"DDM估值：每股內在價值 ${intrinsic_value:.2f}"
        }
    
    def peg(self, pe_ratio: float, earnings_growth_rate: float) -> Dict[str, Any]:
        """
        PEG 市盈率相對增長
        
        公式：PEG = PE / G
        - PEG < 1: 被低估
        - PEG = 1: 合理
        - PEG > 1: 被高估
        """
        if earnings_growth_rate <= 0:
            return {"error": "Growth rate must be positive"}
        
        peg = pe_ratio / (earnings_growth_rate * 100)
        
        if peg < 0.7:
            verdict = "嚴重低估"
            signal = "buy"
        elif peg < 1.0:
            verdict = "輕微低估"
            signal = "buy"
        elif peg < 1.3:
            verdict = "合理"
            signal = "hold"
        elif peg < 2.0:
            verdict = "輕微高估"
            signal = "sell"
        else:
            verdict = "嚴重高估"
            signal = "sell"
        
        return {
            "model": "PEG",
            "peg": round(peg, 2),
            "pe_ratio": pe_ratio,
            "growth_rate": earnings_growth_rate,
            "verdict": verdict,
            "signal": signal,
            "description": f"PEG = {peg:.2f} ({verdict})"
        }
    
    def graham_formula(self, eps: float, growth_rate: float, bond_yield: float = 0.04) -> Dict[str, Any]:
        """
        格雷厄姆估值公式
        
        公式：V = sqrt(22.5 * EPS * (8.5 + 2G))
        G = 預期增長率 (%)
        """
        if eps <= 0 or growth_rate < 0:
            return {"error": "Invalid inputs"}
        
        g = growth_rate * 100  # Convert to percentage
        intrinsic = math.sqrt(22.5 * eps * (8.5 + 2 * g))
        
        # Fair PE based on bond yield
        fair_pe = 8.5 / bond_yield if bond_yield > 0 else 20
        fair_price = eps * fair_pe
        
        return {
            "model": "Graham Formula",
            "intrinsic_value": round(intrinsic, 2),
            "fair_pe": round(fair_pe, 1),
            "fair_price": round(fair_price, 2),
            "eps": eps,
            "growth_rate": growth_rate,
            "bond_yield": bond_yield,
            "description": f"格雷厄姆估值：${intrinsic:.2f}"
        }
    
    def reverse_dcf(self, current_price: float, shares_outstanding: float, discount_rate: float = 0.08, terminal_growth: float = 0.02) -> Dict[str, Any]:
        """
        Reverse DCF - 反推市場隱含增長率
        """
        market_cap = current_price * shares_outstanding
        
        # Assume 5 years of cash flows
        # This is a simplified reverse calculation
        implied_cf = market_cap * (discount_rate - terminal_growth) / (1 + terminal_growth)
        
        # Calculate implied growth from typical margins
        # This is a simplification
        
        return {
            "model": "Reverse DCF",
            "current_price": current_price,
            "market_cap": round(market_cap, 2),
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "description": "反推市場隱含的未來現金流增長預期",
            "note": "需結合其他估值方法綜合判斷"
        }


if __name__ == "__main__":
    vm = ValuationModels()
    
    print("=== 估值模型測試 ===")
    
    # DCF
    cfs = [10, 12, 14, 15, 16]
    result = vm.dcf(cash_flows=cfs, discount_rate=0.08, terminal_growth=0.02, shares_outstanding=1.0)
    print("\nDCF:", result)
    
    # PEG
    result = vm.peg(pe_ratio=20, earnings_growth_rate=0.15)
    print("\nPEG:", result)
    
    # Graham
    result = vm.graham_formula(eps=2.5, growth_rate=0.12)
    print("\nGraham:", result)
