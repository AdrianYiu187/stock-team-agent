#!/usr/bin/env python3
"""
Stock_Team_Agent 多角色協作工作流
定義5位分析師之間的互動和協作模式
"""

import sys
import os
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TaskType(Enum):
    """任務類型枚舉"""
    FULL_ANALYSIS = "full_analysis"
    TECHNICAL_ONLY = "technical_only"
    FUNDAMENTAL_ONLY = "fundamental_only"
    RISK_ASSESSMENT = "risk_assessment"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    VALUATION_ONLY = "valuation_only"
    COMPARISON = "comparison"
    PORTFOLIO_REVIEW = "portfolio_review"
    REAL_TIME_ALERT = "real_time_alert"
    HISTORICAL_BACKTEST = "historical_backtest"


@dataclass
class AnalystResult:
    """分析師結果數據類"""
    analyst: str
    score: float
    signal: str
    confidence: float
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    dependencies: List[str] = field(default_factory=list)


@dataclass
class CollaborationMessage:
    """協作消息"""
    from_analyst: str
    to_analyst: str
    message_type: str  # request, response, insight, warning
    content: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MultiRoleWorkflow:
    """
    多角色協作工作流引擎
    
    5位分析師之間的互動模式：
    1. 順序依賴：風險分析師在估值完成後才能評估風險
    2. 並行執行：市場和技術分析師可並行
    3. 信息傳遞：技術分析師結果影響風險評估
    4. 衝突解決：共識引擎解決分歧
    """
    
    def __init__(self):
        self.workflows = self._initialize_workflows()
        self.collaboration_log: List[CollaborationMessage] = []
    
    def _initialize_workflows(self) -> Dict[str, Dict[str, Any]]:
        """初始化工作流配置"""
        return {
            "full_analysis": {
                "name": "全面分析工作流",
                "parallel": ["market", "technical", "fundamental"],
                "sequential": [
                    ("market", "sentiment"),
                    ("technical", "risk"),
                    ("fundamental", "risk"),
                    ("risk", "consensus"),
                    ("sentiment", "consensus"),
                ],
                "final": "consensus",
                "description": "5位分析師全部參與，市場/技術/基本面並行，風險和情緒有依賴關係"
            },
            "technical_only": {
                "name": "技術分析工作流",
                "parallel": [],
                "sequential": [
                    ("technical", "consensus")
                ],
                "final": "consensus",
                "description": "僅技術分析師參與，快速技術評估"
            },
            "fundamental_only": {
                "name": "基本面分析工作流",
                "parallel": [],
                "sequential": [
                    ("fundamental", "consensus")
                ],
                "final": "consensus",
                "description": "僅基本面分析師參與，深入財務評估"
            },
            "risk_assessment": {
                "name": "風險評估工作流",
                "parallel": ["technical", "fundamental"],
                "sequential": [
                    ("technical", "risk"),
                    ("fundamental", "risk"),
                    ("risk", "consensus")
                ],
                "final": "consensus",
                "description": "技術和基本面分析師結果輸入風險分析師"
            },
            "valuation_only": {
                "name": "估值分析工作流",
                "parallel": [],
                "sequential": [
                    ("fundamental", "consensus")
                ],
                "final": "consensus",
                "description": "基本面分析師專注估值模型計算"
            },
            "comparison": {
                "name": "比較分析工作流",
                "parallel": ["stock_a", "stock_b"],
                "sequential": [
                    ("stock_a", "comparison"),
                    ("stock_b", "comparison"),
                    ("comparison", "consensus")
                ],
                "final": "consensus",
                "description": "兩隻股票同時分析後進行比較"
            }
        }
    
    def execute_workflow(
        self, 
        task_type: str, 
        analysts: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        執行工作流
        
        Args:
            task_type: 任務類型
            analysts: 分析師字典 {名稱: 分析師實例}
            data: 輸入數據 {symbol, user_request, ...}
            
        Returns:
            工作流執行結果
        """
        workflow = self.workflows.get(task_type, self.workflows["full_analysis"])
        
        # 記錄工作流開始
        log_entry = CollaborationMessage(
            from_analyst="system",
            to_analyst="workflow",
            message_type="start",
            content={"workflow": workflow["name"], "task_type": task_type}
        )
        self.collaboration_log.append(log_entry)
        
        # 執行工作流
        results = {}
        
        # 第一階段：並行分析
        for analyst_name in workflow.get("parallel", []):
            if analyst_name in analysts:
                results[analyst_name] = self._execute_analyst(
                    analysts[analyst_name],
                    data,
                    dependencies=[]
                )
                self._log_interaction("system", analyst_name, "result", results[analyst_name])
        
        # 第二階段：順序依賴
        for from_analyst, to_analyst in workflow.get("sequential", []):
            if from_analyst in analysts and to_analyst in analysts:
                # 收集依賴結果
                deps = {d: results[d] for d in results if d in [from_analyst]}
                
                results[to_analyst] = self._execute_analyst(
                    analysts[to_analyst],
                    data,
                    dependencies=deps
                )
                self._log_interaction(from_analyst, to_analyst, "input", deps)
        
        # 第三階段：共識整合
        final_analyst = workflow.get("final", "consensus")
        if final_analyst == "consensus":
            results["consensus"] = self._generate_consensus(results)
        
        return {
            "workflow": workflow["name"],
            "task_type": task_type,
            "analyst_results": results,
            "collaboration_log": self.collaboration_log[-20:],  # 最近20條互動
            "timestamp": datetime.now().isoformat()
        }
    
    def _execute_analyst(
        self, 
        analyst: Any, 
        data: Dict, 
        dependencies: Dict[str, Any]
    ) -> AnalystResult:
        """執行單個分析師"""
        symbol = data.get("symbol", "")
        
        # 如果有依賴，先處理
        if dependencies:
            # 風險分析師需要技術和基本面結果
            if hasattr(analyst, 'name') and analyst.name == "Risk Analyst":
                # 從依賴中提取關鍵信息
                risk_inputs = {}
                for dep_name, dep_result in dependencies.items():
                    if isinstance(dep_result, dict):
                        risk_inputs[dep_name] = dep_result.get("score", 0.5)
        else:
            risk_inputs = {}
        
        # 調用分析師
        try:
            result = analyst.analyze(symbol=symbol, task_type=data.get("task_type", ""), user_request=data.get("user_request", ""))
            
            return AnalystResult(
                analyst=getattr(analyst, 'name', 'unknown'),
                score=result.get("score", 0.5),
                signal=result.get("signal", "hold"),
                confidence=result.get("confidence", 0.5),
                summary=result.get("summary", ""),
                data=result,
                dependencies=list(dependencies.keys())
            )
        except Exception as e:
            return AnalystResult(
                analyst=getattr(analyst, 'name', 'unknown'),
                score=0.5,
                signal="error",
                confidence=0,
                summary=f"分析失敗: {str(e)}"
            )
    
    def _generate_consensus(self, analyst_results: Dict[str, AnalystResult]) -> Dict[str, Any]:
        """生成共識"""
        buy_scores = []
        hold_scores = []
        sell_scores = []
        
        for name, result in analyst_results.items():
            if isinstance(result, AnalystResult) and result.signal != "error":
                buy_scores.append(result.confidence * (1 if "buy" in result.signal else 0))
                hold_scores.append(result.confidence * (1 if result.signal == "hold" else 0))
                sell_scores.append(result.confidence * (1 if "sell" in result.signal else 0))
        
        total = sum(buy_scores + hold_scores + sell_scores) or 1
        
        return {
            "buy": round(sum(buy_scores) / total * 100, 2),
            "hold": round(sum(hold_scores) / total * 100, 2),
            "sell": round(sum(sell_scores) / total * 100, 2),
            "recommendation": self._get_recommendation(sum(buy_scores), sum(hold_scores), sum(sell_scores)),
            "analysts_joined": len(analyst_results)
        }
    
    def _get_recommendation(self, buy: float, hold: float, sell: float) -> str:
        """根據分數生成建議"""
        if buy > hold and buy > sell:
            return "適度買入" if buy < 60 else "強烈買入"
        elif sell > buy and sell > hold:
            return "適度賣出" if sell < 60 else "強烈賣出"
        else:
            return "持有觀望"
    
    def _log_interaction(
        self, 
        from_analyst: str, 
        to_analyst: str, 
        msg_type: str, 
        content: Any
    ):
        """記錄互動"""
        msg = CollaborationMessage(
            from_analyst=from_analyst,
            to_analyst=to_analyst,
            message_type=msg_type,
            content={"summary": str(content)[:200]} if not isinstance(content, dict) else {"data": "result"}
        )
        self.collaboration_log.append(msg)
    
    def get_workflow_info(self, task_type: str = None) -> Dict[str, Any]:
        """獲取工作流信息"""
        if task_type:
            return self.workflows.get(task_type, {})
        return {
            "available_workflows": list(self.workflows.keys()),
            "workflows": self.workflows
        }


def demo_workflow():
    """演示工作流執行"""
    from handlers import (MarketAnalyst, TechnicalAnalyst, FundamentalAnalyst,
                          RiskAnalyst, SentimentAnalyst, MacroAnalyst, NewsAnalyst)
    from data_sources.stock_data_provider import StockDataProvider
    
    # 初始化（7 分析師，與共識引擎一致）
    provider = StockDataProvider()
    market = MarketAnalyst(provider)
    technical = TechnicalAnalyst(provider)
    fundamental = FundamentalAnalyst(provider)
    risk = RiskAnalyst(provider)
    sentiment = SentimentAnalyst(provider)
    macro = MacroAnalyst(provider)
    news = NewsAnalyst(provider)
    
    # 創建工作流引擎
    workflow = MultiRoleWorkflow()
    
    # 執行全面分析工作流（7 分析師）
    analysts = {
        "market": market,
        "technical": technical,
        "fundamental": fundamental,
        "risk": risk,
        "sentiment": sentiment,
        "macro": macro,
        "news": news
    }
    
    data = {
        "symbol": "0700.HK",
        "task_type": "full_analysis",
        "user_request": "全面分析騰訊"
    }
    
    result = workflow.execute_workflow("full_analysis", analysts, data)
    
    print("=== 多角色協作工作流執行結果 ===")
    print(f"工作流: {result['workflow']}")
    print(f"任務類型: {result['task_type']}")
    print()
    print("分析師結果:")
    for name, analyst_result in result['analyst_results'].items():
        if isinstance(analyst_result, AnalystResult):
            print(f"  {analyst_result.analyst}: signal={analyst_result.signal}, score={analyst_result.score}")
        else:
            print(f"  {name}: {analyst_result}")
    print()
    print("協作互動記錄:")
    for log in result['collaboration_log'][-5:]:
        print(f"  {log.from_analyst} -> {log.to_analyst}: {log.message_type}")


if __name__ == "__main__":
    demo_workflow()
