#!/usr/bin/env python3
"""
Stock_Team_Agent 數據提供者 (DEPRECATED STUB)

v5.9 清理：原 StockDataProvider 全部 public methods（get_kline/get_financials/
get_news/get_market_risk）+ 2 個 mock generator（_generate_mock_kline/
_get_mock_financials）均無 production caller。主流程（stock_analysis.py）
直接調用 yfinance + EnhancedNewsFeedProvider + MacroAnalyst，完全繞過此類。

保留此類以維持 MacroAnalyst(data_provider) 的建構簽名向後相容。
MacroAnalyst.__init__ 接受 data_provider 但內部從未使用，傳 None 也安全。
"""


class StockDataProvider:
    """DEPRECATED stub — 保留僅為 MacroAnalyst(data_provider) 簽名相容"""

    def __init__(self, region: str = "hk"):
        self.region = region