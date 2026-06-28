#!/usr/bin/env python3
"""
Stock_Team_Agent MiniMax LLM 整合模組
使用 MiniMax API 驅動真實LLM分析、情緒判斷、辯論生成

用法:
    from integrations.minimax_llm import MiniMaxLLM
    llm = MiniMaxLLM()
    result = llm.analyze_sentiment("騰訊業績超預期，股價大漲")
"""

import os
import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List


class MiniMaxLLM:
    """
    MiniMax API 整合類
    
    支援:
    - 情緒分析 (sentiment)
    - 股票評論分析 (stock_comment)
    - 新聞摘要 (news_summary)
    - 辯論觀點生成 (debate_argument)
    - 多角度分析 (multi_perspective)
    """
    
    def __init__(self):
        # 優先從真實環境變數讀取，否則從 .env 解析真實 key（避免遮罩值）
        self.api_key = os.environ.get("MINIMAX_API_KEY", "")
        if not self.api_key or self.api_key == "***":
            env_path = os.path.expanduser("~/.hermes/.env")
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("MINIMAX_API_KEY="):
                            key_val = line.split("=", 1)[1].strip()
                            if key_val and key_val != "***":
                                self.api_key = key_val
                                break
        self.base_url = "https://api.minimax.io/v1/chat/completions"
        self.model = "MiniMax-M2.7-highspeed"
        self.enabled = bool(self.api_key and self.api_key != "***")
    
    def _call_api(self, messages: List[Dict], max_tokens: int = 200, temperature: float = 0.3) -> Optional[str]:
        """調用 MiniMax API"""
        if not self.enabled:
            return None
        
        try:
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps({
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                reply = result.get("reply", "")
                if not reply:
                    choices = result.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        raw_content = message.get("content", "") or ""
                        if raw_content:
                            # MiniMax returns <think>...</think>ANSWER format
                            parts = raw_content.split('</think>')
                            answer_text = parts[-1].strip() if parts else ""
                            
                            if answer_text.startswith('{'):
                                json_objects = self._extract_json_objects(answer_text)
                                if json_objects:
                                    reply = json_objects[-1]
                            elif answer_text.startswith('```'):
                                cleaned = re.sub(r'^```[a-z]*\n?', '', answer_text, flags=re.IGNORECASE)
                                cleaned = re.sub(r'\n?```$', '', cleaned)
                                json_objects = self._extract_json_objects(cleaned)
                                if json_objects:
                                    reply = json_objects[-1]
                                else:
                                    reply = cleaned
                            else:
                                reply = answer_text
                return reply if reply else None
        except Exception as e:
            print(f"⚠️ MiniMax API 調用失敗: {e}")
            return None

    def _extract_json_objects(self, text: str) -> List[str]:
        """使用大括號匹配提取文本中的所有JSON對象"""
        results = []
        start = None
        brace_count = 0
        
        for i, c in enumerate(text):
            if c == '{':
                if start is None:
                    start = i
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if start is not None and brace_count == 0:
                    results.append(text[start:i+1])
                    start = None
        
        return results
    
    # v5.10 (Stage 4.5b) DEPRECATED: analyze_sentiment 0 caller in stock-team-agent (50 lines)
    # 保留以維持向後相容（外部腳本可能呼叫）
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:  # noqa: kept for backward compat
        """
        分析文本情緒
        
        返回:
            {
                "sentiment": "positive|negative|neutral",
                "score": float,  # -1 to 1
                "confidence": float,  # 0 to 1
                "reasoning": str
            }
        """
        if not text:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "reasoning": "空文本"}
        
        messages = [{
            "role": "user",
            "content": f"""你是一位專業的金融情緒分析師。請分析以下文本的情緒傾向。

分析文本: {text[:500]}

請以JSON格式返回分析結果:
{{
    "sentiment": "positive 或 negative 或 neutral",
    "score": -1到1之間的浮點數（正數=積極，負數=消極）,
    "confidence": 0到1之間的置信度,
    "reasoning": "簡短解釋你的判斷理由"
}}

只返回JSON，不要其他文字。"""
        }]
        
        response = self._call_api(messages, max_tokens=500, temperature=0.1)
        
        if response:
            try:
                # 嘗試解析JSON
                result = json.loads(response)
                return {
                    "sentiment": result.get("sentiment", "neutral"),
                    "score": float(result.get("score", 0)),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", ""),
                    "⚠️ LLM_USED": True
                }
            except json.JSONDecodeError:
                pass
        
        # Fallback: 使用關鍵詞分析
        return self._fallback_sentiment(text)
    
    def _fallback_sentiment(self, text: str) -> Dict[str, Any]:
        """關鍵詞回退機制（當MiniMax API不可用時）— DEPRECATED (v5.10, 0 caller in stock-team-agent)"""
        positive_keywords = ["上漲", "增長", "超預期", "利好", "突破", "買入", "強勁", "大漲", "飙升", "盈利", "增持", "推薦"]
        negative_keywords = ["下跌", "暴跌", "虧損", "降級", "利空", "風險", "裁員", "倒閉", "破產", "訴訟", "裁員", "警告"]

        pos_count = sum(1 for kw in positive_keywords if kw in text)
        neg_count = sum(1 for kw in negative_keywords if kw in text)

        score = (pos_count - neg_count) / max(pos_count + neg_count, 1)

        return {
            "sentiment": "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral",
            "score": score,
            "confidence": 0.3,  # 低置信度，因為是關鍵詞匹配
            "reasoning": "使用關鍵詞回退機制（MiniMax API不可用）",
            "⚠️ FALLBACK_KEYWORD": True
        }

    # v5.10 (Stage 4.5b) DEPRECATED: analyze_stock_news 0 caller in stock-team-agent (40+ lines)
    # 保留以維持向後相容（外部腳本可能呼叫）
    def analyze_stock_news(self, title: str, description: str = "", symbol: str = "") -> Dict[str, Any]:  # noqa: kept for backward compat
        """
        分析股票新聞的影響
        
        返回:
            {
                "impact": "positive|negative|neutral",
                "impact_score": float,  # -1 to 1
                "key_points": [str],
                "trading_signal": "buy|sell|hold",
                "confidence": float
            }
        """
        text = f"{title} {description}"[:1000]
        
        messages = [{
            "role": "user",
            "content": f"""你是一位資深的股票分析師。請分析以下新聞對股票 {symbol if symbol else "相關股票"} 的影響。

新聞標題: {title}
新聞內容: {description[:500]}

請以JSON格式返回分析結果:
{{
    "impact": "positive 或 negative 或 neutral",
    "impact_score": -1到1之間的影響分數,
    "key_points": ["要點1", "要點2"],
    "trading_signal": "buy 或 sell 或 hold",
    "confidence": 0到1之間的置信度
}}

只返回JSON，不要其他文字。"""
        }]
        
        response = self._call_api(messages, max_tokens=1500, temperature=0.2)
        
        if response:
            try:
                result = json.loads(response)
                return {
                    "impact": result.get("impact", "neutral"),
                    "impact_score": float(result.get("impact_score", 0)),
                    "key_points": result.get("key_points", []),
                    "trading_signal": result.get("trading_signal", "hold"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "⚠️ LLM_USED": True
                }
            except json.JSONDecodeError:
                pass
        
        # Fallback
        return self.analyze_sentiment(text)
    
    def generate_debate_argument(
        self,
        analyst_role: str,
        analyst_name: str,
        position: Dict[str, Any],
        debate_context: str,
        round_num: int
    ) -> Optional[Dict[str, Any]]:
        """
        生成辯論觀點（真正的LLM驅動）
        
        參數:
            analyst_role: 分析師角色 (如 "技術分析師", "基本面分析師")
            analyst_name: 分析師名稱
            position: 當前立場數據
            debate_context: 辯論上下文（其他分析師的觀點）
            round_num: 當前回合
            
        返回:
            {{
                "argument": str,  # 生成的觀點
                "challenge": str,  # 向其他分析師的提問
                "evidence": [str],  # 支持證據
                "concession": str,  # 是否讓步
                "adjustment": float  # 立場調整
            }}
        """
        role_descriptions = {
            "技術分析師": "擅長K線形態、技術指標、趨勢判斷",
            "基本面分析師": "擅長財務報表、估值模型、增長潛力",
            "風險分析師": "擅長風險評估、波動性、VaR計算",
            "市場分析師": "擅長市場情緒、板塊輪動、資金流向",
            "宏觀策略師": "擅長利率環境、經濟周期、地緣政治"
        }
        
        role_desc = role_descriptions.get(analyst_role, analyst_role)
        
        messages = [{
            "role": "user",
            "content": f"""你是一位{role_desc}的專業金融分析師，名為{analyst_name}。

這是第{round_num}輪辯論。

你的當前立場:
- 信號: {position.get('signal', 'neutral')}
- 評分: {position.get('score', 0.5)}
- 關鍵觀點: {position.get('summary', '')}

其他分析師的觀點:
{debate_context[:800]}

請生成你的辯論觀點。考慮:
1. 提出有力的支持和反對證據
2. 挑戰其他分析師的觀點
3. 根據證據調整你的立場（如果合理）
4. 保持專業客觀

請以JSON格式返回:
{{
    "argument": "你的主要論點（50字以內）",
    "challenge": "向其他分析師的尖銳提問（30字以內）",
    "evidence": ["證據1", "證據2"],
    "concession": "是否承認其他觀點有道理（yes/no）",
    "adjustment": -0.1到0.1之間的評分調整
}}

只返回JSON，不要其他文字。"""
        }]
        
        response = self._call_api(messages, max_tokens=1500, temperature=0.4)
        
        if response:
            try:
                result = json.loads(response)
                return {
                    "argument": result.get("argument", ""),
                    "challenge": result.get("challenge", ""),
                    "evidence": result.get("evidence", []),
                    "concession": result.get("concession", "no"),
                    "adjustment": float(result.get("adjustment", 0)),
                    "analyst": analyst_name,
                    "role": analyst_role,
                    "round": round_num,
                    "⚠️ LLM_USED": True
                }
            except json.JSONDecodeError:
                pass
        
        return None
    
    def summarize_analyst_consensus(
        self,
        analysts_data: List[Dict[str, Any]],
        debate_messages: List[Dict]
    ) -> Dict[str, Any]:
        """
        總結分析師共識（LLM驅動）
        
        返回:
            {
                "consensus_signal": str,
                "confidence": float,
                "main_themes": [str],
                "dissenting_views": [str],
                "recommendation": str
            }
        """
        analysts_summary = "\n".join([
            f"- {a.get('analyst', 'Unknown')}: signal={a.get('signal', 'N/A')}, score={a.get('score', 'N/A')}"
            for a in analysts_data
        ])
        
        debate_summary = "\n".join([
            f"[{m.get('round', '?')}輪] {m.get('from', '?')} → {m.get('to', '?')}: {m.get('content', {}).get('point', '')}"
            for m in debate_messages[-10:]
        ])
        
        messages = [{
            "role": "user",
            "content": f"""你是一位中立的投资顾问。请分析以下多位分析师的辩论，总结共识观点。

分析师立场:
{analysts_summary}

辩论摘要:
{debate_summary}

请以JSON格式返回总结:
{{
    "consensus_signal": "buy 或 sell 或 hold",
    "confidence": 0到1之间的置信度,
    "main_themes": ["主题1", "主题2"],
    "dissenting_views": ["异议观点1"],
    "recommendation": "最终投资建议（50字以内）"
}}

只返回JSON，不要其他文字。"""
        }]
        
        response = self._call_api(messages, max_tokens=1500, temperature=0.2)
        
        if response:
            try:
                result = json.loads(response)
                return {
                    "consensus_signal": result.get("consensus_signal", "hold"),
                    "confidence": float(result.get("confidence", 0.5)),
                    "main_themes": result.get("main_themes", []),
                    "dissenting_views": result.get("dissenting_views", []),
                    "recommendation": result.get("recommendation", ""),
                    "⚠️ LLM_USED": True
                }
            except json.JSONDecodeError:
                pass
        
        return {"consensus_signal": "hold", "confidence": 0.3, "⚠️ FALLBACK": True}
    
    def health_check(self) -> Dict[str, Any]:
        """檢查MiniMax API連接狀態"""
        if not self.enabled:
            return {
                "status": "disabled",
                "reason": "MINIMAX_API_KEY 未設置",
                "enabled": False
            }
        
        # 使用更長的max_tokens來確保模型能生成完整回應
        messages = [{"role": "user", "content": "Respond with exactly the word 'OK' in English. Only the word OK, nothing else."}]
        response = self._call_api(messages, max_tokens=50, temperature=0)
        
        return {
            "status": "ok" if response and "OK" in response.upper() else "error",
            "enabled": self.enabled,
            "response_received": bool(response),
            "response_preview": response[:50] if response else None,
            "⚠️ LLM_AVAILABLE": bool(response and "OK" in response.upper())
        }


# 便捷函數
def analyze_sentiment(text: str) -> Dict[str, Any]:
    """快速情緒分析"""
    llm = MiniMaxLLM()
    return llm.analyze_sentiment(text)


def analyze_stock_news(title: str, description: str = "", symbol: str = "") -> Dict[str, Any]:
    """快速新聞分析"""
    llm = MiniMaxLLM()
    return llm.analyze_stock_news(title, description, symbol)


if __name__ == "__main__":
    # 測試
    llm = MiniMaxLLM()
    print("=== MiniMax LLM 健康檢查 ===")
    print(llm.health_check())
    
    print("\n=== 情緒分析測試 ===")
    print(llm.analyze_sentiment("騰訊業績超預期，股價大漲5%，分析師看好"))
    
    print("\n=== 新聞分析測試 ===")
    print(llm.analyze_stock_news(
        "蘋果發布新iPhone，銷量超預期",
        "分析師預測季度營收將創新高",
        "AAPL"
    ))
