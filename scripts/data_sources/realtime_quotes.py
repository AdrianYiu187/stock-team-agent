# 即時報價整合模組
# 支援三個即時報價源：Finnhub、Alpha Vantage、Polygon.io
# 優先級：Finnhub > Alpha Vantage > Polygon（根據易用性）
# 從環境變量讀取 API keys

import os
import warnings
from datetime import datetime
from typing import Dict, Optional

import requests

# 環境變量中的 API keys
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
POLYGON_KEY = os.getenv("POLYGON_KEY")

# API 端點
FINNHUB_URL = "https://finnhub.io/api/v1/quote"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
POLYGON_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/prev"


def _get_finnhub_quote(ticker: str) -> Optional[Dict]:
    """
    從 Finnhub 獲取即時報價
    
    Finnhub 免費 tier 限制：每秒最多 60 請求
    返回格式：{'c': current, 'd': change, 'dp': change_pct, 'h': high, 'l': low, 'o': open, 'pc': previous_close, 't': timestamp}
    """
    if not FINNHUB_KEY:
        return None
    
    try:
        params = {"symbol": ticker, "token": FINNHUB_KEY}
        response = requests.get(FINNHUB_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Finnhub 返回 c=0 表示無數據
        if not data or data.get("c") == 0:
            return None
        
        return {
            "symbol": ticker.upper(),
            "price": float(data["c"]),
            "change": float(data["d"]),
            "change_pct": float(data["dp"]),
            "volume": 0,  # Finnhub 免費版不提供成交量
            "high": float(data["h"]),
            "low": float(data["l"]),
            "open": float(data["o"]),
            "previous_close": float(data["pc"]),
            "timestamp": datetime.fromtimestamp(data["t"]).isoformat(),
            "source": "finnhub"
        }
    except Exception:
        return None


def _get_alpha_vantage_quote(ticker: str) -> Optional[Dict]:
    """
    從 Alpha Vantage 獲取即時報價
    
    免費 tier 限制：每分鐘 5 請求，每天 500 請求
    返回格式：Global Quote API
    """
    if not ALPHA_VANTAGE_KEY:
        return None
    
    try:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker,
            "apikey": ALPHA_VANTAGE_KEY
        }
        response = requests.get(ALPHA_VANTAGE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        quote = data.get("Global Quote", {})
        if not quote or not quote.get("05. price"):
            return None
        
        return {
            "symbol": quote.get("01. symbol", ticker.upper()),
            "price": float(quote["05. price"]),
            "change": float(quote["09. change"]),
            "change_pct": float(quote["10. change percent"].rstrip("%")),
            "volume": int(quote["06. volume"]),
            "high": float(quote["03. high"]),
            "low": float(quote["04. low"]),
            "open": float(quote["02. open"]),
            "previous_close": float(quote["08. previous close"]),
            "timestamp": datetime.now().isoformat(),
            "source": "alpha_vantage"
        }
    except Exception:
        return None


def _get_polygon_quote(ticker: str) -> Optional[Dict]:
    """
    從 Polygon.io 獲取前一交易日收盤報價
    
    免費 tier 限制：每分鐘 5 請求
    注意：Polygon 免費版只提供前一交易日數據（prev），不是真正即時
    """
    if not POLYGON_KEY:
        return None
    
    try:
        url = POLYGON_URL.format(ticker=ticker.upper())
        params = {"adjusted": "true", "apiKey": POLYGON_KEY}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return None
        
        r = results[0]
        return {
            "symbol": ticker.upper(),
            "price": float(r["c"]),
            "change": float(r["c"]) - float(r["o"]),
            "change_pct": ((float(r["c"]) - float(r["o"])) / float(r["o"])) * 100,
            "volume": int(r.get("v", 0)),
            "high": float(r["h"]),
            "low": float(r["l"]),
            "open": float(r["o"]),
            "previous_close": float(r["c"]),
            "timestamp": datetime.fromtimestamp(r["t"] / 1000).isoformat(),
            "source": "polygon"
        }
    except Exception:
        return None


def get_realtime_quote(ticker: str) -> Dict:
    """
    統一的即時報價介面
    
    優先級：Finnhub > Alpha Vantage > Polygon
    如果所有 API key 都未設定，返回空 dict 並發出 warning
    
    參數:
        ticker: 股票代碼，如 'AAPL', 'TSLA'
    
    返回:
        包含報價資料的 dict，結構如下：
        {
            "symbol": str,       # 股票代碼
            "price": float,      # 現價
            "change": float,    # 漲跌金額
            "change_pct": float, # 漲跌百分比
            "volume": int,       # 成交量
            "high": float,       # 最高價
            "low": float,        # 最低價
            "open": float,       # 開盤價
            "previous_close": float,  # 昨收價
            "timestamp": str,    # 時間戳（ISO 格式）
            "source": str        # 數據來源：finnhub/alpha_vantage/polygon
        }
        
        若無法獲取數據，返回空 dict {}
    """
    # 檢查是否有任何 API key
    if not any([FINNHUB_KEY, ALPHA_VANTAGE_KEY, POLYGON_KEY]):
        warnings.warn(
            "無可用 API key！請設定以下環境變量之一："
            "FINNHUB_KEY, ALPHA_VANTAGE_KEY, POLYGON_KEY",
            RuntimeWarning
        )
        return {}
    
    # 按優先級嘗試各數據源
    quote = _get_finnhub_quote(ticker)
    if quote:
        return quote
    
    quote = _get_alpha_vantage_quote(ticker)
    if quote:
        return quote
    
    quote = _get_polygon_quote(ticker)
    if quote:
        return quote
    
    # 所有來源都失敗
    warnings.warn(f"無法獲取 {ticker} 的即時報價（所有數據源均失敗）", RuntimeWarning)
    return {}


# 測試入口
if __name__ == "__main__":
    import json
    
    # 測試 - 需設定環境變量
    test_ticker = "AAPL"
    result = get_realtime_quote(test_ticker)
    
    if result:
        print(f"✅ {test_ticker} 報價獲取成功（來源：{result['source']}）")
        print(json.dumps(result, indent=2))
    else:
        print(f"⚠️ 無法獲取 {test_ticker} 報價，請確認 API key 已設定")
