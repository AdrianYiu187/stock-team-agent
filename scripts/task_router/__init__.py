"""
task_router/ — Stock_Team_Agent 輕量級任務分發層
================================================
封裝職責：任務路由 + 工作流構建，與具體分析師實現解耦。

目錄結構：
  task_router/
    __init__.py         — 本包的公共 API
    dispatcher.py       — 任務意圖分類器（StockRouter 提取）
    workflow_builder.py — 分析師調用鏈組合器
    stock_router.py     — 【遷移目標】原始 stock_router.py 的未來位置

Phase 1（現在）：將 stock_router.py (287行) 遷入 task_router/，
                在原位置留 re-export shim 保持向後兼容。
"""

from .stock_router import StockRouter, TaskType
from .workflow_builder import build_workflow, ANALYST_CHAIN
from .dispatcher import dispatch, DispatchResult

__all__ = ["StockRouter", "TaskType", "build_workflow", "dispatch", "DispatchResult", "ANALYST_CHAIN"]
