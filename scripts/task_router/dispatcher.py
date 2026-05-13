"""
dispatcher.py — Stock_Team_Agent 輕量任務分發器
===============================================
從 task_router/stock_router.py 的 StockRouter 抽取路由邏輯。
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DispatchResult:
    task_text: str
    symbol: Optional[str]
    region: str
    task_type: str
    confidence: float
    workflow: List[str]


def dispatch(task_text: str, symbol: str = None, region: str = "hk") -> DispatchResult:
    """
    Stock 任務分發入口。
    Phase 1 stub：調用 StockRouter 類完成識別。
    """
    from .stock_router import StockRouter
    router = StockRouter(symbol=symbol, region=region)
    # Phase 1 stub — 實際邏輯在 StockRouter.run()
    return DispatchResult(
        task_text=task_text,
        symbol=symbol,
        region=region,
        task_type="full_analysis",
        confidence=0.5,
        workflow=[],
    )
