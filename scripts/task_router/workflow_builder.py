"""
workflow_builder.py — Stock_Team_Agent 分析師調用鏈組合器
==========================================================
根據 task_router/stock_router.py 的 StockRouter 分析結果，
組合對應分析師的調用順序。
"""

from typing import List


# -------- 分析師固定順序 --------
ANALYST_CHAIN = [
    "MarketAnalyst",      # 市場狀態分析師
    "TechnicalAnalyst",   # 技術指標分析師
    "FundamentalAnalyst", # 基本面分析師
    "RiskAnalyst",        # 風險管理分析師
    "SentimentAnalyst",   # 情緒/消息面分析師
    "NewsAnalyst",        # 新聞分析師
    "MacroAnalyst",       # 宏觀分析師
]


def build_workflow(task_type: str, symbol: str = None) -> List[str]:
    """
    根據任務類型返回對應分析師調用鏈。
    
    Args:
        task_type: TaskType enum value (e.g. "full_analysis")
        symbol: 股票代碼
    
    Returns:
        按執行順序排列的分析師類名列表
    """
    if task_type == "full_analysis":
        return ANALYST_CHAIN
    if task_type == "technical_only":
        return ["TechnicalAnalyst"]
    if task_type == "fundamental_only":
        return ["FundamentalAnalyst"]
    if task_type == "risk_assessment":
        return ["RiskAnalyst", "MarketAnalyst"]
    if task_type == "sentiment_analysis":
        return ["SentimentAnalyst", "MacroAnalyst"]
    return ANALYST_CHAIN
