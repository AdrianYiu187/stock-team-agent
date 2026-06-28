#!/usr/bin/env python3
"""
P18: RSI/乖離率超賣超買警報引擎
"""

import yfinance as yf
from datetime import datetime

def calculate_rsi(prices: list, period: int = 14) -> float:
    """計算 RSI"""
    if len(prices) < period + 1:
        return 50.0  # 數據不足返回中性
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# v5.10 (Stage 4.5): calculate_deviation 從未被 check_alerts 之外的 caller 使用 (0 external caller)
# 保留以維持向後相容（外部腳本可能 import）
def calculate_deviation(prices: list) -> float:  # noqa: kept for backward compat
    """計算 MA5/MA20 乖離率 (%)"""
    if len(prices) < 20:
        return 0.0
    ma5 = sum(prices[-5:]) / 5
    ma20 = sum(prices[-20:]) / 20
    if ma20 == 0:
        return 0.0
    return ((ma5 - ma20) / ma20) * 100

def check_alerts(ticker: str) -> list[dict]:
    """
    檢查股票警報
    返回警報列表（空列表=無警報）
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3mo")
        if hist.empty or len(hist) < 20:
            return []
        closes = hist["Close"].tolist()
        rsi = calculate_rsi(closes)
        dev = calculate_deviation(closes)
        alerts = []
        # RSI 警報
        if rsi < 30:
            alerts.append({"type": "RSI_OVERSOLD", "value": rsi, 
                           "signal": "BUY", "message": f"RSI 超賣 {rsi:.1f}"})
        elif rsi > 70:
            alerts.append({"type": "RSI_OVERBOUGHT", "value": rsi,
                           "signal": "SELL", "message": f"RSI 超買 {rsi:.1f}"})
        # 乖離率警報
        if dev < -5:
            alerts.append({"type": "DEVIATION_OVERSOLD", "value": dev,
                           "signal": "BUY", "message": f"嚴重超賣 乖離率 {dev:.1f}%"})
        elif dev > 5:
            alerts.append({"type": "DEVIATION_OVERBOUGHT", "value": dev,
                           "signal": "SELL", "message": f"嚴重超買 乖離率 {dev:.1f}%"})
        return alerts
    except Exception:
        return []

def format_alerts(alerts: list) -> str:
    if not alerts:
        return "無警報"
    lines = []
    for a in alerts:
        emoji = "🟢" if a["signal"] == "BUY" else "🔴"
        lines.append(f"{emoji} {a['message']}")
    return "\n".join(lines)

if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    a = check_alerts(t)
    print(f"{t}: {format_alerts(a)}")