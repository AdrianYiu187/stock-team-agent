#!/usr/bin/env python3
"""
Stock_Team_Agent 能力觸發器
Hermes Agent 透過此模組呼叫 Stock_Team_Agent

使用方法：
  from trigger import StockCapabilityTrigger
  trigger = StockCapabilityTrigger()
  result = trigger.execute("分析騰訊0700.HK")
"""

import sys
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

# 添加 scripts 目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class StockCapabilityTrigger:
    """
    Stock_Team_Agent 能力觸發器
    
    將 Hermes Agent 的請求轉換為 Stock_Team_Agent 任務
    """
    
    def __init__(self):
        self.capabilities = self._load_capabilities()
        self.router = None  # 延遲載入
    
    def _load_capabilities(self) -> Dict[str, Any]:
        """載入能力映射"""
        return {
            # S1-S10: 任務路由
            "S1": {"name": "任務識別", "keywords": ["分析", "評估", "研究"]},
            "S2": {"name": "任務分發", "keywords": ["全面", "完整", "技術", "基本面"]},
            "S3": {"name": "符號解析", "keywords": ["0700", "9988", "AAPL", "TSLA"]},
            
            # S11-S20: 市場分析
            "S11": {"name": "市場趨勢", "keywords": ["趨勢", "市場", "板塊"]},
            "S12": {"name": "資金流向", "keywords": ["資金", "流入", "流出"]},
            "S13": {"name": "板塊輪動", "keywords": ["板塊", "輪動", "強勢"]},
            
            # S21-S30: 共識引擎
            "S21": {"name": "評分提取", "keywords": ["評分", "評級"]},
            "S22": {"name": "加權計算", "keywords": ["加權", "權重"]},
            "S23": {"name": "衝突檢測", "keywords": ["衝突", "分歧"]},
            
            # S31-S40: 技術指標
            "S31": {"name": "SMA均線", "keywords": ["SMA", "均線", "MA"]},
            "S32": {"name": "EMA均線", "keywords": ["EMA", "指數均線"]},
            "S33": {"name": "RSI", "keywords": ["RSI", "相對強弱"]},
            "S34": {"name": "MACD", "keywords": ["MACD"]},
            "S35": {"name": "布林帶", "keywords": ["布林", "Bollinger"]},
            "S36": {"name": "ATR", "keywords": ["ATR", "波幅"]},
            "S37": {"name": "隨機指標", "keywords": ["隨機", "KD", "stoch"]},
            
            # S41-S50: 專業指數
            "S41": {"name": "巴菲特指標", "keywords": ["巴菲特", "Buffett"]},
            "S42": {"name": "席勒PE", "keywords": ["席勒", "Shiller", "CAPE"]},
            "S43": {"name": "黃金切割", "keywords": ["黃金切割", "Fibonacci"]},
            "S44": {"name": "風險評分", "keywords": ["風險", "risk"]},
            "S45": {"name": "波動率", "keywords": ["波動率", "volatility"]},
            "S46": {"name": "VaR", "keywords": ["VaR", "風險價值"]},
            "S47": {"name": "夏普比率", "keywords": ["夏普", "Sharpe"]},
            
            # S51-S60: 估值模型
            "S51": {"name": "DCF", "keywords": ["DCF", "現金流折現"]},
            "S52": {"name": "DDM", "keywords": ["DDM", "股利折現"]},
            "S53": {"name": "PEG", "keywords": ["PEG", "市盈率增長"]},
            "S54": {"name": "相對估值", "keywords": ["相對估值", "同行對比"]},
            "S55": {"name": "內在價值", "keywords": ["內在價值", "intrinsic"]},
            "S56": {"name": "目標價", "keywords": ["目標價", "target"]},
            
            # S61-S70: 圖表生成
            "S61": {"name": "K線圖", "keywords": ["K線", "kline", "candlestick"]},
            "S62": {"name": "均線圖", "keywords": ["均線圖", "ma"]},
            "S63": {"name": "技術指標圖", "keywords": ["指標圖", "rsi圖", "macd圖"]},
            "S64": {"name": "估值圖", "keywords": ["估值圖", "pe圖"]},
            "S65": {"name": "雷達圖", "keywords": ["雷達圖", "雷達"]},
            
            # S71-S80: 數據獲取
            "S71": {"name": "實時報價", "keywords": ["實時", "股價", "報價"]},
            "S72": {"name": "財務數據", "keywords": ["財務", "營收", "利潤"]},
            "S73": {"name": "新聞數據", "keywords": ["新聞", "消息"]},
            "S74": {"name": "分析師評級", "keywords": ["分析師", "評級", "buy", "sell"]},
            
            # S81-S90: 形態識別
            "S81": {"name": "K線形態", "keywords": ["形態", "pattern", "锤子", "吞噬"]},
            "S82": {"name": "趨勢線", "keywords": ["趨勢線", "trendline"]},
            "S83": {"name": "通道", "keywords": ["通道", "channel"]},
            "S85": {"name": "頭肩頂底", "keywords": ["頭肩", "head shoulders"]},
            "S86": {"name": "雙頂雙底", "keywords": ["雙頂", "雙底", "double"]},
            
            # S91-S100: 風險管理
            "S91": {"name": "倉位計算", "keywords": ["倉位", "position"]},
            "S92": {"name": "止損設置", "keywords": ["止損", "stop loss"]},
            "S93": {"name": "風險收益比", "keywords": ["風險收益", "risk reward"]},
            "S94": {"name": "最大回撤", "keywords": ["最大回撤", "drawdown"]},
            
            # S101-S110: 比較分析
            "S101": {"name": "估值比較", "keywords": ["估值比較", "對比", "vs"]},
            "S102": {"name": "盈利比較", "keywords": ["盈利比較", "ROE"]},
            "S103": {"name": "成長比較", "keywords": ["成長比較", "增長"]},
            
            # S111-S120: 組合分析
            "S111": {"name": "持倉分析", "keywords": ["持倉", "portfolio"]},
            "S112": {"name": "風險暴露", "keywords": ["風險暴露", "exposure"]},
            "S113": {"name": "相關性分析", "keywords": ["相關性", "correlation"]},
            "S114": {"name": "再平衡", "keywords": ["再平衡", "rebalance"]},
            
            # S121-S130: 情緒分析
            "S121": {"name": "新聞情緒", "keywords": ["新聞情緒", "sentiment"]},
            "S122": {"name": "公告解讀", "keywords": ["公告", "新聞"]},
            "S123": {"name": "分析師評級", "keywords": ["分析師評級", "rating"]},
            
            # S131-S140: 歷史回測
            "S131": {"name": "策略回測", "keywords": ["回測", "backtest"]},
            "S132": {"name": "區間回測", "keywords": ["區間", "period"]},
            
            # S141-S150: 警報
            "S141": {"name": "價格警報", "keywords": ["價格警報", "alert"]},
            "S142": {"name": "指標警報", "keywords": ["指標警報"]},
            
            # S151-S160: GitHub整合
            "S151": {"name": "項目發現", "keywords": ["項目", "github", "開源"]},
            "S152": {"name": "策略發現", "keywords": ["策略", "strategy"]},
        }
    
    def _get_router(self):
        """延遲載入路由器"""
        if self.router is None:
            from stock_router import StockRouter
            self.router = StockRouter()
        return self.router
    
    def execute(self, request: str, symbol: str = None, **kwargs) -> Dict[str, Any]:
        """
        執行股票分析任務
        
        Args:
            request: 自然語言請求
            symbol: 股票代碼（可選）
            
        Returns:
            分析結果字典
        """
        # 識別需要的能力
        required_caps = self._identify_capabilities(request)
        
        # 解析股票代碼
        if symbol is None:
            symbol = self._extract_symbol(request)
        
        # 根據能力類型執行任務
        if self._requires_full_analysis(required_caps):
            return self._execute_full_analysis(request, symbol, **kwargs)
        elif self._requires_technical_only(required_caps):
            return self._execute_technical(request, symbol, **kwargs)
        elif self._requires_fundamental_only(required_caps):
            return self._execute_fundamental(request, symbol, **kwargs)
        elif self._requires_comparison(required_caps):
            return self._execute_comparison(request, symbol, **kwargs)
        elif self._requires_risk_assessment(required_caps):
            return self._execute_risk(request, symbol, **kwargs)
        elif self._requires_sentiment(required_caps):
            return self._execute_sentiment(request, symbol, **kwargs)
        elif self._requires_valuation(required_caps):
            return self._execute_valuation(request, symbol, **kwargs)
        else:
            return self._execute_full_analysis(request, symbol, **kwargs)
    
    def _identify_capabilities(self, request: str) -> List[str]:
        """識別請求需要的能力"""
        request_lower = request.lower()
        required = []
        
        for cap_id, cap_info in self.capabilities.items():
            for keyword in cap_info["keywords"]:
                if keyword.lower() in request_lower:
                    required.append(cap_id)
                    break
        
        return required if required else ["S1", "S2"]  # 默認全面分析
    
    def _extract_symbol(self, request: str) -> Optional[str]:
        """從請求中提取股票代碼"""
        import re
        
        # 港股格式
        hk_match = re.search(r'(\d{4})\.HK', request, re.IGNORECASE)
        if hk_match:
            return f"{hk_match.group(1)}.HK"
        
        # A股格式
        a_match = re.search(r'(\d{6})\.(SS|SZ)', request, re.IGNORECASE)
        if a_match:
            return f"{a_match.group(1)}.{a_match.group(2).upper()}"
        
        # 美股格式（簡單匹配大寫字母）
        us_match = re.search(r'([A-Z]{2,5})', request)
        if us_match:
            return us_match.group(1)
        
        return None
    
    def _requires_full_analysis(self, caps: List[str]) -> bool:
        """是否需要全面分析"""
        return any(c in caps for c in ["S1", "S2", "S11", "S21", "S111"])
    
    def _requires_technical_only(self, caps: List[str]) -> bool:
        """是否只需要技術分析"""
        tech_caps = [f"S{i}" for i in range(31, 41)] + [f"S{i}" for i in range(81, 91)]
        return any(c in tech_caps for c in caps) and len(caps) <= 3
    
    def _requires_fundamental_only(self, caps: List[str]) -> bool:
        """是否只需要基本面分析"""
        fund_caps = [f"S{i}" for i in range(51, 61)]
        return any(c in fund_caps for c in caps)
    
    def _requires_comparison(self, caps: List[str]) -> bool:
        """是否需要比較分析"""
        return "S101" in caps or "vs" in str(caps).lower()
    
    def _requires_risk_assessment(self, caps: List[str]) -> bool:
        """是否需要風險評估"""
        risk_caps = [f"S{i}" for i in range(91, 101)]
        return any(c in risk_caps for c in caps)
    
    def _requires_sentiment(self, caps: List[str]) -> bool:
        """是否需要情緒分析"""
        sent_caps = [f"S{i}" for i in range(121, 131)]
        return any(c in sent_caps for c in caps)
    
    def _requires_valuation(self, caps: List[str]) -> bool:
        """是否需要估值分析"""
        val_caps = [f"S{i}" for i in range(51, 61)]
        return any(c in val_caps for c in caps)
    
    def _execute_full_analysis(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行全面分析"""
        router = self._get_router()
        result = router.route(request, symbol=symbol, **kwargs)
        return {
            "status": "success",
            "task_type": "full_analysis",
            "symbol": symbol,
            "capabilities_used": ["S1-S10", "S11-S20", "S21-S30", "S31-S40", "S41-S50", "S51-S60"],
            "analyst_results": result.get("analyst_results", {}),
            "consensus": result.get("consensus", {}),
            "recommendation": result.get("consensus", {}).get("recommendation", "N/A"),
            "confidence": result.get("consensus", {}).get("confidence", 0),
            "charts": result.get("charts", []),
            "summary": self._generate_summary(result)
        }
    
    def _execute_technical(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行技術分析"""
        router = self._get_router()
        result = router.route("技術分析", symbol=symbol, **kwargs)
        return self._format_result(result, "technical_analysis")
    
    def _execute_fundamental(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行基本面分析"""
        router = self._get_router()
        result = router.route("基本面分析", symbol=symbol, **kwargs)
        return self._format_result(result, "fundamental_analysis")
    
    def _execute_comparison(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行比較分析"""
        router = self._get_router()
        # 提取第二個股票
        import re
        match = re.search(r'[vsVS]\s*([A-Z0-9.\-]+)', request)
        symbol2 = match.group(1) if match else None
        
        result = router.route(f"比較{symbol}和{symbol2}", symbol=symbol, **kwargs)
        return self._format_result(result, "comparison")
    
    def _execute_risk(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行風險評估"""
        router = self._get_router()
        result = router.route("風險評估", symbol=symbol, **kwargs)
        return self._format_result(result, "risk_assessment")
    
    def _execute_sentiment(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行情緒分析"""
        router = self._get_router()
        result = router.route("情緒分析", symbol=symbol, **kwargs)
        return self._format_result(result, "sentiment_analysis")
    
    def _execute_valuation(self, request: str, symbol: str, **kwargs) -> Dict[str, Any]:
        """執行估值分析"""
        router = self._get_router()
        result = router.route("估值分析", symbol=symbol, **kwargs)
        return self._format_result(result, "valuation_analysis")
    
    def _format_result(self, result: Dict, task_type: str) -> Dict[str, Any]:
        """格式化結果"""
        return {
            "status": "success",
            "task_type": task_type,
            "symbol": result.get("symbol"),
            "consensus": result.get("consensus", {}),
            "charts": result.get("charts", [])
        }
    
    def _generate_summary(self, result: Dict) -> str:
        """生成摘要"""
        consensus = result.get("consensus", {})
        recommendation = consensus.get("recommendation", "N/A")
        confidence = consensus.get("confidence", 0)
        
        return f"綜合評估建議：{recommendation}（信心度：{confidence}）"


def main():
    """命令列入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Stock_Team_Agent 能力觸發器")
    parser.add_argument("--request", "-r", required=True, help="分析請求")
    parser.add_argument("--symbol", "-s", help="股票代碼")
    parser.add_argument("--capabilities", "-c", action="store_true", help="顯示能力列表")
    
    args = parser.parse_args()
    
    trigger = StockCapabilityTrigger()
    
    if args.capabilities:
        print("=== Stock_Team_Agent 能力列表 ===")
        for cap_id, cap_info in sorted(trigger.capabilities.items()):
            print(f"  {cap_id}: {cap_info['name']}")
            print(f"    關鍵詞: {', '.join(cap_info['keywords'][:5])}")
        return
    
    result = trigger.execute(args.request, args.symbol)
    print(f"狀態: {result['status']}")
    print(f"任務類型: {result['task_type']}")
    print(f"股票: {result.get('symbol', 'N/A')}")
    print(f"建議: {result.get('recommendation', 'N/A')}")
    print(f"信心度: {result.get('confidence', 0)}")


if __name__ == "__main__":
    main()
