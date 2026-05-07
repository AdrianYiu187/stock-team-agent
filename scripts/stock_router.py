#!/usr/bin/env python3
"""
Stock_Team_Agent - 任務路由器
自動識別股票分析任務類型並分發給相應處理器

能力範圍：
- S1-S10: 市場狀態分析
- S11-S20: 技術指標分析
- S21-S30: 基本面分析
- S31-S40: 風險管理
- S41-S50: 情緒/消息面分析
- S51-S60: 估值模型
- S61-S70: 圖表生成
- S71-S80: 共識引擎
- S81-S90: 實時監控
- S91-S100: GitHub/外部數據整合
"""

import sys
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple


class TaskType:
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


class StockRouter:
    """
    Stock_Team_Agent 任務路由器
    
    自動分析用戶請求，識別任務類型，
    調用相應的分析師模組，最後透過共識引擎整合結果
    """
    
    def __init__(self, symbol: str = None, region: str = "hk"):
        self.symbol = symbol
        self.region = region
        
        # 初始化數據提供者
        try:
            from .data_sources.stock_data_provider import StockDataProvider
            self.data_provider = StockDataProvider(region=region)
        except ImportError:
            from data_sources.stock_data_provider import StockDataProvider
            self.data_provider = StockDataProvider(region=region)
        
        # 初始化5位分析師
        try:
            from .handlers.market_analyst import MarketAnalyst
            from .handlers.technical_analyst import TechnicalAnalyst
            from .handlers.fundamental_analyst import FundamentalAnalyst
            from .handlers.risk_analyst import RiskAnalyst
            from .handlers.sentiment_analyst import SentimentAnalyst
        except ImportError:
            from handlers.market_analyst import MarketAnalyst
            from handlers.technical_analyst import TechnicalAnalyst
            from handlers.fundamental_analyst import FundamentalAnalyst
            from handlers.risk_analyst import RiskAnalyst
            from handlers.sentiment_analyst import SentimentAnalyst
        
        self.analysts = {
            "market": MarketAnalyst(self.data_provider),
            "technical": TechnicalAnalyst(self.data_provider),
            "fundamental": FundamentalAnalyst(self.data_provider),
            "risk": RiskAnalyst(self.data_provider),
            "sentiment": SentimentAnalyst(self.data_provider),
        }
        
        # 初始化專業工具
        try:
            from .consensus.consensus_engine import ConsensusEngine
            from .indicators.technical_indicators import StockTechnicalIndicators
            from .indicators.professional_indices import ProfessionalIndices
            from .valuation.valuation_models import ValuationModels
            from .charts.chart_generator import ChartGenerator
        except ImportError:
            from consensus.consensus_engine import ConsensusEngine
            from indicators.technical_indicators import StockTechnicalIndicators
            from indicators.professional_indices import ProfessionalIndices
            from valuation.valuation_models import ValuationModels
            from charts.chart_generator import ChartGenerator
        
        self.technical_indicators = StockTechnicalIndicators()
        self.professional_indices = ProfessionalIndices()
        self.valuation_models = ValuationModels()
        self.chart_generator = ChartGenerator()
        self.consensus_engine = ConsensusEngine()
        
        # 任務歷史
        self.task_history: List[Dict] = []
        
    def route(self, user_request: str, symbol: str = None, **kwargs) -> Dict[str, Any]:
        """
        主路由函數：分析請求 → 分發任務 → 共識整合 → 返回結果
        """
        self.symbol = symbol or self.symbol
        if not self.symbol:
            raise ValueError("股票代碼 symbol 是必需的")
        
        # Step 1: 識別任務類型
        task_type = self._identify_task_type(user_request)
        
        # Step 2: 根據任務類型調用相應分析師
        start_time = datetime.now()
        analyst_results = self._dispatch_analysts(task_type, user_request, **kwargs)
        
        # Step 3: 共識整合
        consensus_result = self.consensus_engine.integrate(
            analyst_results,
            task_type=task_type,
            symbol=self.symbol
        )
        
        # Step 4: 生成圖表（如需要）
        charts = self._generate_charts_if_needed(task_type, analyst_results)
        
        # 記錄任務
        task_record = {
            "timestamp": start_time.isoformat(),
            "symbol": self.symbol,
            "task_type": task_type,
            "analysts_called": list(analyst_results.keys()),
            "consensus": consensus_result,
            "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
        }
        self.task_history.append(task_record)
        
        return {
            "symbol": self.symbol,
            "task_type": task_type,
            "analyst_results": analyst_results,
            "consensus": consensus_result,
            "charts": charts,
            "task_record": task_record
        }
    
    def _identify_task_type(self, request: str) -> str:
        """從自然語言識別任務類型"""
        request_lower = request.lower()
        
        if any(kw in request_lower for kw in ["全面分析", "完整分析", "full analysis", "comprehensive"]):
            return TaskType.FULL_ANALYSIS
        if any(kw in request_lower for kw in ["技術分析", "technical", "指標", "chart"]):
            return TaskType.TECHNICAL_ONLY
        if any(kw in request_lower for kw in ["基本面", "fundamental", "財務", "營收", "eps"]):
            return TaskType.FUNDAMENTAL_ONLY
        if any(kw in request_lower for kw in ["風險", "risk", "止损", "止損", "倉位"]):
            return TaskType.RISK_ASSESSMENT
        if any(kw in request_lower for kw in ["情緒", "sentiment", "新聞", "消息", "公告"]):
            return TaskType.SENTIMENT_ANALYSIS
        if any(kw in request_lower for kw in ["估值", "valuation", "目標價", "dcf", "dividend"]):
            return TaskType.VALUATION_ONLY
        if any(kw in request_lower for kw in ["比較", "compare", "對比", "vs "]):
            return TaskType.COMPARISON
        if any(kw in request_lower for kw in ["投資組合", "portfolio", "持倉", "倉位"]):
            return TaskType.PORTFOLIO_REVIEW
        if any(kw in request_lower for kw in ["預警", "alert", "通知", "提醒"]):
            return TaskType.REAL_TIME_ALERT
        if any(kw in request_lower for kw in ["回測", "backtest", "歷史"]):
            return TaskType.HISTORICAL_BACKTEST
        
        return TaskType.FULL_ANALYSIS
    
    def _dispatch_analysts(self, task_type: str, user_request: str, **kwargs) -> Dict[str, Dict]:
        """根據任務類型分發給相應分析師"""
        results = {}
        
        analyst_map = {
            TaskType.FULL_ANALYSIS: ["market", "technical", "fundamental", "risk", "sentiment"],
            TaskType.TECHNICAL_ONLY: ["market", "technical"],
            TaskType.FUNDAMENTAL_ONLY: ["fundamental", "risk"],
            TaskType.RISK_ASSESSMENT: ["risk", "technical"],
            TaskType.SENTIMENT_ANALYSIS: ["sentiment", "market"],
            TaskType.VALUATION_ONLY: ["fundamental", "risk"],
            TaskType.COMPARISON: ["technical", "fundamental"],
            TaskType.PORTFOLIO_REVIEW: ["risk", "fundamental", "technical"],
            TaskType.REAL_TIME_ALERT: ["market", "technical", "sentiment"],
            TaskType.HISTORICAL_BACKTEST: ["technical", "risk"],
        }
        
        analysts_to_call = analyst_map.get(task_type, ["market", "technical", "fundamental"])
        
        for analyst_name in analysts_to_call:
            analyst = self.analysts[analyst_name]
            try:
                result = analyst.analyze(
                    symbol=self.symbol,
                    task_type=task_type,
                    user_request=user_request,
                    **kwargs
                )
                results[analyst_name] = result
            except Exception as e:
                results[analyst_name] = {"error": str(e), "status": "failed"}
        
        return results
    
    def _generate_charts_if_needed(self, task_type: str, analyst_results: Dict) -> Dict[str, Any]:
        """按需生成圖表"""
        if task_type in [TaskType.FULL_ANALYSIS, TaskType.TECHNICAL_ONLY, TaskType.COMPARISON]:
            try:
                kline_data = self.data_provider.get_kline(self.symbol, period="daily", limit=100)
                charts = {
                    "candlestick": self.chart_generator.candlestick(kline_data, self.symbol),
                    "volume": self.chart_generator.volume(kline_data),
                    "macd": self.chart_generator.macd(kline_data),
                    "rsi": self.chart_generator.rsi(kline_data),
                }
                return charts
            except Exception as e:
                return {"error": str(e)}
        return {}
    
    def get_task_history(self) -> List[Dict]:
        """獲取任務歷史"""
        return self.task_history
    
    def get_capabilities(self) -> Dict[str, Any]:
        """返回Stock_Team_Agent能力清單"""
        return {
            "name": "Stock_Team_Agent",
            "version": "1.0.0",
            "analysts": list(self.analysts.keys()),
            "task_types": list(TaskType.__dict__.values()),
            "technical_indicators": self.technical_indicators.list_indicators(),
            "professional_indices": self.professional_indices.list_indices(),
            "valuation_models": self.valuation_models.list_models(),
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Stock_Team_Agent 任務路由器")
    parser.add_argument("--symbol", "-s", required=True, help="股票代碼")
    parser.add_argument("--request", "-r", default="全面分析", help="分析請求")
    parser.add_argument("--region", default="hk", help="地區: hk/cn/us")
    parser.add_argument("--capabilities", action="store_true", help="顯示能力清單")
    parser.add_argument("--test", action="store_true", help="測試模式")
    
    args = parser.parse_args()
    
    if args.capabilities:
        router = StockRouter()
        print(json.dumps(router.get_capabilities(), indent=2, ensure_ascii=False))
        return
    
    if args.test:
        router = StockRouter(symbol=args.symbol, region=args.region)
        result = router.route(args.request)
        print(json.dumps(result["consensus"], indent=2, ensure_ascii=False))
        return
    
    router = StockRouter(symbol=args.symbol, region=args.region)
    result = router.route(args.request)
    
    print(f"\n{'='*70}")
    print(f"Stock_Team_Agent 分析報告 - {args.symbol}")
    print(f"{'='*70}")
    print(f"\n任務類型: {result['task_type']}")
    print(f"共識分數: {result['consensus'].get('overall_score', 'N/A')}")
    print(f"建議: {result['consensus'].get('recommendation', 'N/A')}")


if __name__ == "__main__":
    main()
