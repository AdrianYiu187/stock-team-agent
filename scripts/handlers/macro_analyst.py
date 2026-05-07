#!/usr/bin/env python3
"""
宏觀策略分析師 (Macro Analyst)
分析利率環境、經濟周期、地緣政治、宏觀政策對投資的影響
"""

from typing import Dict, Any, Optional
from datetime import datetime


class MacroAnalyst:
    """宏觀策略分析師"""
    
    def __init__(self, data_provider):
        self.data_provider = data_provider
        self.name = "macro_analyst"
    
    def analyze(self, symbol: str, task_type: str, user_request: str, **kwargs) -> Dict[str, Any]:
        """執行宏觀分析"""
        try:
            # 獲取宏觀數據
            macro_data = self._get_macro_data(symbol)
            
            # 分析宏觀環境
            environment = self._analyze_macro_environment(macro_data)
            
            # 計算評分
            score_dict = self._calculate_score(environment)
            score = score_dict.get("confidence", 0.5)
            
            return {
                "analyst": self.name,
                "timestamp": datetime.now().isoformat(),
                "macro_data": macro_data,
                "environment": environment,
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
    
    def _get_macro_data(self, symbol: str) -> Dict:
        """獲取宏觀數據"""
        try:
            import yfinance as yf
            
            macro_data = {
                "source": "yfinance",
                "⚠️ FALLBACK": False
            }
            
            # 嘗試獲取主要宏觀指標
            try:
                # 美國國債收益率（10年期）- 經濟健康度指標
                treasury = yf.Ticker("^TNX")
                treasury_data = treasury.history(period="1mo")
                if len(treasury_data) > 0:
                    macro_data["us_10y_yield"] = float(treasury_data["Close"].iloc[-1])
                    macro_data["yield_change_1m"] = float(treasury_data["Close"].iloc[-1] - treasury_data["Close"].iloc[0]) if len(treasury_data) > 1 else 0
            except Exception as e:
                import logging
                logging.warning(f"[MacroAnalyst] treasury data failed: {e}")
            
            try:
                # VIX 波動率指數 - 市場恐慌度
                vix = yf.Ticker("^VIX")
                vix_data = vix.history(period="1mo")
                if len(vix_data) > 0:
                    macro_data["vix"] = float(vix_data["Close"].iloc[-1])
            except Exception as e:
                import logging
                logging.warning(f"[MacroAnalyst] vix data failed: {e}")
            
            try:
                # 黃金 - 避險需求
                gold = yf.Ticker("GC=F")
                gold_data = gold.history(period="1mo")
                if len(gold_data) > 0:
                    gold_val = float(gold_data["Close"].iloc[-1])
                    macro_data["gold"] = gold_val
                    macro_data["gold_price"] = gold_val
                    macro_data["gold_change_1m"] = float(gold_data["Close"].iloc[-1] - gold_data["Close"].iloc[0]) / float(gold_data["Close"].iloc[0]) if len(gold_data) > 1 and gold_data["Close"].iloc[0] > 0 else 0
            except Exception as e:
                import logging
                logging.warning(f"[MacroAnalyst] gold data failed: {e}")
            
            try:
                # 美元指數 - 資金流向
                dxy = yf.Ticker("DX-Y.NYB")
                dxy_data = dxy.history(period="1mo")
                if len(dxy_data) > 0:
                    macro_data["dxy"] = float(dxy_data["Close"].iloc[-1])
            except Exception as e:
                import logging
                logging.warning(f"[MacroAnalyst] dxy data failed: {e}")
            
            # 嘗試從個股信息獲取相關宏觀敏感度
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                macro_data["beta"] = info.get("beta", 1.0)
                macro_data["earnings_quarterly_growth"] = info.get("earningsQuarterlyGrowth", 0)
            except Exception as e:
                import logging
                logging.warning(f"[MacroAnalyst] beta/earnings data failed: {e}")
            
            # 檢查是否有任何數據
            if len(macro_data) <= 2:  # 只有 source 和 ⚠️ FALLBACK
                raise ValueError("No macro data retrieved")
            
            return macro_data
            
        except Exception as e:
            import logging
            logging.warning(f"[MacroAnalyst] _get_macro_data({symbol}) failed: {e} — using fallback")
            return {
                "source": "error",
                "⚠️ FALLBACK": True,
                "⚠️ ERROR": str(e)
            }
    
    def _analyze_macro_environment(self, macro_data: Dict) -> Dict[str, Any]:
        """分析宏觀環境"""
        # 如果是 fallback 數據，返回中性分析
        if macro_data.get("⚠️ FALLBACK"):
            return {
                "rate_environment": "unknown",
                "risk_sentiment": "unknown",
                "dollar_strength": "unknown",
                "gold_trend": "unknown",
                "overall": "neutral",
                "confidence": 0.3
            }
        
        analysis = {}
        signals = []
        
        # 分析利率環境
        yield_val = macro_data.get("us_10y_yield")
        if yield_val:
            if yield_val > 4.5:
                analysis["rate_environment"] = "high_rates"
                signals.append(("bearish", 0.3))
            elif yield_val > 3.5:
                analysis["rate_environment"] = "moderate_rates"
                signals.append(("neutral", 0.2))
            else:
                analysis["rate_environment"] = "low_rates"
                signals.append(("bullish", 0.3))
        
        # 分析市場恐慌度 (VIX)
        vix = macro_data.get("vix")
        if vix:
            if vix > 30:
                analysis["risk_sentiment"] = "fear"
                signals.append(("bearish", 0.25))
            elif vix > 20:
                analysis["risk_sentiment"] = "caution"
                signals.append(("neutral", 0.15))
            else:
                analysis["risk_sentiment"] = "complacency"
                signals.append(("bullish", 0.15))
        
        # 分析黃金走勢（避險需求）
        gold_change = macro_data.get("gold_change_1m")
        if gold_change:
            if gold_change > 0.05:
                analysis["gold_trend"] = "strong_bid"
                signals.append(("neutral", 0.1))  # 避險需求高，但不等於壞事
            elif gold_change > 0:
                analysis["gold_trend"] = "mild_bid"
                signals.append(("neutral", 0.05))
            else:
                analysis["gold_trend"] = "off_bid"
        
        # 分析美元走勢
        dxy = macro_data.get("dxy")
        if dxy:
            if dxy > 105:
                analysis["dollar_strength"] = "strong"
                signals.append(("bearish", 0.2))  # 強美元對新興市場不利
            elif dxy > 100:
                analysis["dollar_strength"] = "moderate"
                signals.append(("neutral", 0.1))
            else:
                analysis["dollar_strength"] = "weak"
                signals.append(("bullish", 0.2))
        
        # 計算綜合信號
        bullish = sum(s[1] for s in signals if s[0] == "bullish")
        bearish = sum(s[1] for s in signals if s[0] == "bearish")
        neutral = sum(s[1] for s in signals if s[0] == "neutral")
        
        if bullish > bearish + 0.2:
            analysis["overall"] = "bullish"
        elif bearish > bullish + 0.2:
            analysis["overall"] = "bearish"
        else:
            analysis["overall"] = "neutral"
        
        analysis["confidence"] = min(0.7, 0.3 + len(signals) * 0.08)

        # 構造可讀的環境描述列表
        env_list = []
        if analysis.get("rate_environment"):
            rate_map = {"high_rates": "高利率環境（>4.5%）不利成長股估值",
                        "moderate_rates": "適中利率環境（3.5-4.5%）",
                        "low_rates": "低利率環境（<3.5%）有利估值擴張"}
            env_list.append(rate_map.get(analysis["rate_environment"], analysis["rate_environment"]))
        if analysis.get("risk_sentiment"):
            risk_map = {"fear": "VIX高位市場恐慌（>30）",
                        "caution": "VIX偏高市場謹慎（20-30）",
                        "complacency": "VIX低位市場自滿（<20）"}
            env_list.append(risk_map.get(analysis["risk_sentiment"], analysis["risk_sentiment"]))
        if analysis.get("dollar_strength"):
            dxy_map = {"strong": "強美元（>105）不利新興市場",
                       "moderate": "適中美元（100-105）",
                       "weak": "弱美元（<100）有利風險資產"}
            env_list.append(dxy_map.get(analysis["dollar_strength"], analysis["dollar_strength"]))
        if analysis.get("gold_trend"):
            gold_map = {"strong_bid": "黃金強勢上漲（避險需求高）",
                        "mild_bid": "黃金小幅上漲",
                        "off_bid": "黃金承壓（避險需求低）"}
            env_list.append(gold_map.get(analysis["gold_trend"], analysis["gold_trend"]))
        analysis["environment_list"] = env_list

        return analysis
    
    def _calculate_score(self, environment: Dict) -> Dict[str, Any]:
        """計算宏觀評分"""
        overall = environment.get("overall", "neutral")
        confidence = environment.get("confidence", 0.5)
        
        if overall == "bullish":
            buy = 0.5 + confidence * 0.3
            sell = 0.1
        elif overall == "bearish":
            buy = 0.15
            sell = 0.5 + confidence * 0.3
        else:
            buy = 0.3
            sell = 0.3
        
        hold = 1 - buy - sell
        
        if overall == "bullish":
            signal = "buy"
        elif overall == "bearish":
            signal = "sell"
        else:
            signal = "neutral"
        
        summary_parts = []
        if environment.get("rate_environment"):
            rm = {"high_rates": "高利率", "moderate_rates": "適中利率", "low_rates": "低利率"}
            summary_parts.append(f"利率環境: {rm.get(environment['rate_environment'], environment['rate_environment'])}")
        if environment.get("risk_sentiment"):
            sm = {"fear": "市場恐慌", "caution": "市場謹慎", "complacency": "市場自滿"}
            summary_parts.append(f"風險情緒: {sm.get(environment['risk_sentiment'], environment['risk_sentiment'])}")
        if environment.get("dollar_strength"):
            dm = {"strong": "強美元", "moderate": "適中美元", "weak": "弱美元"}
            summary_parts.append(f"美元: {dm.get(environment['dollar_strength'], environment['dollar_strength'])}")
        if environment.get("gold_trend"):
            gm = {"strong_bid": "黃金強勢", "mild_bid": "黃金小幅上漲", "off_bid": "黃金承壓"}
            summary_parts.append(f"黃金: {gm.get(environment['gold_trend'], environment['gold_trend'])}")
        
        return {
            "buy": round(buy, 3),
            "hold": round(hold, 3),
            "sell": round(sell, 3),
            "signal": signal,
            "confidence": round(confidence, 2),
            "summary": f"宏觀{'偏多' if overall == 'bullish' else '偏空' if overall == 'bearish' else '中性'}。{'；'.join(summary_parts) if summary_parts else '數據不足'}。"
        }
