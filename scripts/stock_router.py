#!/usr/bin/env python3
"""
Stock_Team_Agent 任務路由器 — 向後兼容 re-export shim
=====================================================
本文件是向後兼容的 re-export shim。
邏輯本體已遷移到 scripts/task_router/stock_router.py，請使用新路徑導入。

    舊（已棄用）：from scripts.stock_router import StockRouter
    新（推薦）：   from scripts.task_router import StockRouter

遷移日期：2026-05-13
"""

import sys
from pathlib import Path

# 將 task_router/ 加入路徑，確保相對導入可解析
_script_dir = Path(__file__).parent.resolve()
_task_router_dir = _script_dir / "task_router"
if str(_task_router_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from task_router.stock_router import StockRouter, TaskType

__all__ = ["StockRouter", "TaskType"]
