#!/usr/bin/env python3
"""
Stock_Team_Agent LLM驅動辯論引擎
替換原有的硬編碼 RealDebateEngine，實現真正的 MiniMax API 驅動辯論

升級要點:
1. 真正的LLM生成觀點，非預設文本
2. 動態生成挑戰和反駁
3. 根據上下文調整立場
4. 完整的共識達成機制
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class LLMDebateEngine:
    """
    LLM驅動的多分析師辯論引擎
    
    使用 MiniMax API 動態生成:
    - 各分析師的觀點和論據
    - 分析師之間的挑戰和反駁
    - 最終共識建議
    """
    
    def __init__(self, llm_integration=None):
        self.llm = llm_integration  # MiniMaxLLM 實例
        self.analysts: Dict[str, Dict] = {}
        self.messages: List[Dict] = []
        self.debate_rounds = 0
        self.max_rounds = 2
        self.debate_log: List[Dict] = []
        
        # 分析師角色定義
        self.role_configs = {
            "technical": {
                "name": "技術分析師",
                "description": "擅長K線形態、技術指標、趨勢判斷",
                "focus": ["RSI", "MACD", "均線", "形態"]
            },
            "fundamental": {
                "name": "基本面分析師", 
                "description": "擅長財務報表、估值模型、增長潛力",
                "focus": ["P/E", "P/B", "ROE", "營收增長"]
            },
            "risk": {
                "name": "風險分析師",
                "description": "擅長風險評估、波動性、VaR計算",
                "focus": ["VaR", "波動率", "Beta", "最大回撤"]
            },
            "market": {
                "name": "市場分析師",
                "description": "擅長市場情緒、板塊輪動、資金流向",
                "focus": ["成交量", "市場情緒", "資金流向"]
            },
            "macro": {
                "name": "宏觀策略師",
                "description": "擅長利率環境、經濟周期、地緣政治",
                "focus": ["利率", "GDP", "通脹", "政策"]
            },
            "sentiment": {
                "name": "情緒分析師",
                "description": "擅長新聞情緒、分析師評級、社交媒體",
                "focus": ["新聞", "評級", "目標價"]
            }
        }
    
    def register_analyst(self, name: str, role: str, initial_position: Dict):
        """註冊分析師及其初始立場"""
        config = self.role_configs.get(role, {})
        self.analysts[name] = {
            "name": config.get("name", role),
            "role": role,
            "description": config.get("description", ""),
            "position": initial_position,
            "score": initial_position.get("score", 0.5),
            "signal": initial_position.get("signal", "neutral"),
            "arguments": [],
            "challenges_received": [],
            "concessions_made": [],
            "llm_generated_arguments": []
        }
    
    def _get_debate_context(self, exclude_analyst: str = "") -> str:
        """獲取當前辯論上下文（給LLM使用）"""
        context_parts = []
        for name, analyst in self.analysts.items():
            if name == exclude_analyst:
                continue
            pos = analyst["position"]
            context_parts.append(
                f"{analyst['name']}: signal={pos.get('signal', 'N/A')}, "
                f"score={pos.get('score', 'N/A')}, "
                f"summary={pos.get('summary', '')[:50]}"
            )
        return "\n".join(context_parts)
    
    def _execute_llm_driven_round(self, round_num: int) -> List[Dict]:
        """
        執行一輪LLM驅動的辯論
        
        每個分析師都會調用 MiniMax API 生成真正的觀點
        """
        self.debate_rounds = round_num
        new_messages = []
        
        if not self.llm:
            # 無LLM時使用簡化邏輯
            return self._execute_fallback_round(round_num)
        
        # 每個分析師生成觀點
        for analyst_name, analyst in self.analysts.items():
            role = analyst["role"]
            position = analyst["position"]
            context = self._get_debate_context(exclude_analyst=analyst_name)
            
            # 調用LLM生成觀點
            llm_result = self.llm.generate_debate_argument(
                analyst_role=analyst["role"],
                analyst_name=analyst["name"],
                position=position,
                debate_context=context,
                round_num=round_num
            )
            
            if llm_result:
                analyst["llm_generated_arguments"].append(llm_result)
                
                # 根據LLM結果調整立場
                adjustment = llm_result.get("adjustment", 0)
                analyst["score"] = max(0, min(1, analyst["score"] + adjustment))
                
                # 記錄消息
                msg = self.send_message(
                    from_analyst=analyst_name,
                    to_analyst="all",
                    message_type="argument",
                    content={
                        "argument": llm_result.get("argument", ""),
                        "challenge": llm_result.get("challenge", ""),
                        "evidence": llm_result.get("evidence", []),
                        "concession": llm_result.get("concession", "no"),
                        "adjustment": adjustment,
                        "⚠️ LLM_GENERATED": True
                    }
                )
                new_messages.append(msg)
                
                # 如果有讓步，記錄
                if llm_result.get("concession", "no") == "yes":
                    analyst["concessions_made"].append(llm_result.get("argument", ""))
        
        # 分析師之間的交叉質詢
        self._execute_cross_challenges(new_messages)
        
        return new_messages
    
    def _execute_cross_challenges(self, messages: List[Dict]):
        """執行交叉質詢（分析師之間的互動）"""
        # 技術 vs 基本面
        if "technical" in self.analysts and "fundamental" in self.analysts:
            tech = self.analysts["technical"]
            fund = self.analysts["fundamental"]
            
            if tech["score"] < 0.45 and fund["score"] > 0.5:
                msg = self.send_message(
                    "technical", "fundamental",
                    "challenge",
                    {
                        "point": f"技術面顯示{'下跌' if tech['score'] < 0.4 else '中性'}趨勢",
                        "evidence": ["MACD負值" if tech["score"] < 0.4 else "MACD中性", "價格低於MA50"],
                        "question": "基本面能否抵禦技術面的壓力？",
                        "⚠️ AUTO_GENERATED": True
                    }
                )
                messages.append(msg)
    
    def _execute_fallback_round(self, round_num: int) -> List[Dict]:
        """回退模式：使用簡化邏輯（當LLM不可用）"""
        # 這個方法實現基本的辯論邏輯，但不生成新內容
        # 僅用於當 MiniMax API 不可用時的基本運作
        return []
    
    def send_message(self, from_analyst: str, to_analyst: str, message_type: str, content: Dict) -> Dict:
        """發送訊息"""
        msg = {
            "from": from_analyst,
            "to": to_analyst,
            "type": message_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "round": self.debate_rounds
        }
        self.messages.append(msg)
        self.debate_log.append(msg)
        
        if message_type == "challenge":
            if to_analyst in self.analysts:
                self.analysts[to_analyst]["challenges_received"].append(content.get("point", ""))
        
        return msg
    
    def run_debate(self, symbol: str = "") -> Dict[str, Any]:
        """
        運行完整辯論（5輪）
        
        返回:
            {
                "symbol": str,
                "rounds_completed": int,
                "final_positions": {analyst: position},
                "consensus": {LLM生成的共識結果},
                "debate_summary": str
            }
        """
        for round_num in range(1, self.max_rounds + 1):
            self._execute_llm_driven_round(round_num)
        
        # 生成最終共識
        consensus = self._generate_consensus(symbol)
        
        return {
            "symbol": symbol,
            "rounds_completed": self.max_rounds,
            "total_messages": len(self.messages),
            "analysts": {
                name: {
                    "final_score": a["score"],
                    "final_signal": a["signal"],
                    "arguments_generated": len(a["llm_generated_arguments"]),
                    "concessions": len(a["concessions_made"])
                }
                for name, a in self.analysts.items()
            },
            "consensus": consensus,
            "debate_log": self.debate_log[-20:]  # 最近20條消息
        }
    
    def _generate_consensus(self, symbol: str) -> Dict[str, Any]:
        """生成最終共識（使用LLM）"""
        if self.llm:
            analysts_data = [
                {
                    "analyst": name,
                    "signal": a["signal"],
                    "score": a["score"],
                    "summary": a["position"].get("summary", "")
                }
                for name, a in self.analysts.items()
            ]
            
            result = self.llm.summarize_analyst_consensus(
                analysts_data=analysts_data,
                debate_messages=self.messages
            )
            return result
        
        # Fallback: 簡單平均
        scores = [a["score"] for a in self.analysts.values()]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        return {
            "consensus_signal": "buy" if avg_score > 0.55 else "sell" if avg_score < 0.45 else "hold",
            "confidence": 0.3,
            "recommendation": "（無LLM共識）",
            "⚠️ FALLBACK": True
        }
    
    def get_debate_summary(self) -> str:
        """獲取辯論摘要文本"""
        if not self.messages:
            return "無辯論記錄"
        
        summary_parts = [f"=== 辯論摘要 ({len(self.messages)}條消息) ==="]
        
        for analyst_name, analyst in self.analysts.items():
            summary_parts.append(
                f"\n【{analyst['name']}】"
                f" 信號:{analyst['signal']} 評分:{analyst['score']:.2f}"
            )
            if analyst["llm_generated_arguments"]:
                latest = analyst["llm_generated_arguments"][-1]
                summary_parts.append(f"  觀點: {latest.get('argument', 'N/A')}")
                if latest.get("concession") == "yes":
                    summary_parts.append(f"  讓步: {latest.get('argument', '')}")
        
        return "\n".join(summary_parts)


# ============ 便捷函數 ============

def create_llm_debate_engine(minimax_llm=None) -> LLMDebateEngine:
    """創建LLM驅動辯論引擎"""
    return LLMDebateEngine(llm_integration=minimax_llm)


if __name__ == "__main__":
    # 測試
    print("=== LLMDebateEngine 測試 ===")
    
    # 測試健康檢查
    from integrations.minimax_llm import MiniMaxLLM
    llm = MiniMaxLLM()
    health = llm.health_check()
    print(f"MiniMax 狀態: {health}")
    
    # 創建引擎
    engine = LLMDebateEngine(llm if health.get("enabled") else None)
    
    # 註冊分析師
    engine.register_analyst("tech_1", "technical", {
        "signal": "sell",
        "score": 0.35,
        "summary": "技術面偏空，RSI低於40，MACD負值"
    })
    engine.register_analyst("fund_1", "fundamental", {
        "signal": "buy",
        "score": 0.65,
        "summary": "基本面低估，P/E 16倍合理，YTD跌41%超跌"
    })
    engine.register_analyst("risk_1", "risk", {
        "signal": "hold",
        "score": 0.45,
        "summary": "風險適中，VaR合理"
    })
    
    # 運行辯論
    result = engine.run_debate("700.HK")
    print(f"\n辯論完成:")
    print(f"- 輪數: {result['rounds_completed']}")
    print(f"- 消息數: {result['total_messages']}")
    print(f"\n分析師最終立場:")
    for name, pos in result["analysts"].items():
        print(f"  {name}: score={pos['final_score']:.2f}, signal={pos['final_signal']}")
    
    print(f"\n共識結果:")
    print(result["consensus"])
    
    print(f"\n{engine.get_debate_summary()}")
