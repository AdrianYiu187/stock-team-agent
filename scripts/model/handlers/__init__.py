"""
Stock_Team_Agent MacroAnalyst (model layer)
==========================================
v5.8: 6 個分析師 handler 已清理為死代碼（multifactor 純函數在 stock_analysis.py
直接調用，不需 OO wrapper）。本文件保留 MacroAnalyst 唯一真實實現。
"""

from .macro_analyst import MacroAnalyst

__all__ = ["MacroAnalyst"]
