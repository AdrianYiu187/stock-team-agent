#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P7: 回測引擎 (Backtest Engine)
=============================
用於測試技術指標策略的有效性

功能：
1. 用 yfinance 拉取歷史 K 線數據
2. 對每個交易日，用過去 N 日數據計算技術指標
3. 根據指標生成簡單評分（不調用 LLM）
4. 與實際漲跌對比，計算準確度

作者：Stock Team Agent
版本：1.0.0
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import yfinance as yf

# ---------------------------------------------------------------------------
# 技術指標計算模組
# ---------------------------------------------------------------------------

def calculate_sma(prices: np.ndarray, period: int) -> np.ndarray:
    """
    計算簡單移動平均線 (Simple Moving Average)

    參數：
        prices: 價格陣列
        period: 週期

    返回：
        SMA 陣列（與輸入等長，前面部分為 NaN）
    """
    if len(prices) < period:
        return np.full_like(prices, np.nan)
    sma = np.full_like(prices, np.nan)
    sma[period - 1:] = np.convolve(prices, np.ones(period) / period, mode='valid')
    return sma


def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """
    計算指數移動平均線 (Exponential Moving Average)

    參數：
        prices: 價格陣列
        period: 週期

    返回：
        EMA 陣列
    """
    if len(prices) < period:
        return np.full_like(prices, np.nan)
    ema = np.full_like(prices, np.nan)
    ema[period - 1] = np.mean(prices[:period])
    multiplier = 2 / (period + 1)
    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    計算相對強弱指數 (Relative Strength Index)

    參數：
        prices: 價格陣列
        period: 計算週期（預設 14 日）

    返回：
        RSI 陣列（0-100）
    """
    if len(prices) < period + 1:
        return np.full_like(prices, np.nan)

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.full_like(prices, np.nan)
    avg_loss = np.full_like(prices, np.nan)

    # 初始平均值
    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    # 平滑計算
    for i in range(period + 1, len(prices)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    rs = avg_gain / np.maximum(avg_loss, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    計算 MACD (Moving Average Convergence Divergence)

    參數：
        prices: 價格陣列
        fast: 快線週期（預設 12）
        slow: 慢線週期（預設 26）
        signal: 訊號線週期（預設 9）

    返回：
        (MACD 線, 訊號線, 柱狀圖)
    """
    if len(prices) < slow:
        n = len(prices)
        return np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)

    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line[~np.isnan(macd_line)], signal) if not np.all(np.isnan(macd_line)) else np.full_like(macd_line, np.nan)
    
    # 對齊訊號線長度
    valid_macd = macd_line[~np.isnan(macd_line)]
    if len(valid_macd) >= signal:
        signal_full = np.full_like(macd_line, np.nan)
        signal_full[len(macd_line) - len(valid_macd):] = signal_line
        macd_hist = macd_line - np.where(np.isnan(signal_full), np.nan, signal_full)
    else:
        macd_hist = np.full_like(macd_line, np.nan)

    return macd_line, signal_full, macd_hist


def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    計算布林帶 (Bollinger Bands)

    參數：
        prices: 價格陣列
        period: 週期（預設 20 日）
        std_dev: 標準差倍數（預設 2）

    返回：
        (上軌, 中軌, 下軌)
    """
    if len(prices) < period:
        return np.full_like(prices, np.nan), np.full_like(prices, np.nan), np.full_like(prices, np.nan)

    sma = calculate_sma(prices, period)
    std = np.full_like(prices, np.nan)
    for i in range(period - 1, len(prices)):
        std[i] = np.std(prices[i - period + 1:i + 1])

    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    計算平均真實波幅 (Average True Range)

    參數：
        high: 最高價陣列
        low: 最低價陣列
        close: 收盤價陣列
        period: 週期（預設 14）

    返回：
        ATR 陣列
    """
    if len(high) < 2:
        return np.full_like(high, np.nan)

    tr = np.full_like(high, np.nan)
    tr[1:] = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )

    atr = np.full_like(high, np.nan)
    if len(tr) >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, len(tr)):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


# ---------------------------------------------------------------------------
# 訊號評分系統
# ---------------------------------------------------------------------------

def generate_signal_score(
    close: float,
    sma_20: float,
    sma_60: float,
    rsi: float,
    macd_hist: float,
    bb_position: float,
    atr: float,
    prev_close: float
) -> Dict[str, any]:
    """
    根據技術指標生成買/賣評分（不調用 LLM）

    評分邏輯：
    - RSI > 70: 過熱，可能回調（偏賣）
    - RSI < 30: 超賣，可能反彈（偏買）
    - 價格 > SMA20 > SMA60: 多頭排列（偏買）
    - MACD 柱狀圖 > 0: 動量向上（偏買）
    - 價格觸及布林帶上軌: 超買（偏賣）
    - 價格觸及布林帶下軌: 超賣（偏買）

    參數：
        close: 當前收盤價
        sma_20: 20 日均線
        sma_60: 60 日均線
        rsi: RSI 指標值
        macd_hist: MACD 柱狀圖
        bb_position: 布林帶位置 (0-100)
        atr: 平均真實波幅
        prev_close: 前日收盤價

    返回：
        包含信號方向和強度的字典
    """
    buy_score = 0.0
    sell_score = 0.0
    reasons = []

    # 1. 移動平均線評分
    if sma_20 > sma_60 and close > sma_20:
        buy_score += 2.0
        reasons.append("多頭排列")
    elif sma_20 < sma_60 and close < sma_20:
        sell_score += 2.0
        reasons.append("空頭排列")

    # 2. RSI 評分
    if rsi > 70:
        sell_score += 2.0
        reasons.append("RSI 超買")
    elif rsi < 30:
        buy_score += 2.0
        reasons.append("RSI 超賣")
    elif rsi > 60:
        buy_score += 1.0
        reasons.append("RSI 偏多")
    elif rsi < 40:
        sell_score += 1.0
        reasons.append("RSI 偏空")

    # 3. MACD 柱狀圖評分
    if macd_hist > 0:
        buy_score += 1.5
        reasons.append("MACD 多頭")
    else:
        sell_score += 1.5
        reasons.append("MACD 空頭")

    # 4. 布林帶位置評分
    if bb_position > 90:
        sell_score += 1.5
        reasons.append("觸及布林上軌")
    elif bb_position < 10:
        buy_score += 1.5
        reasons.append("觸及布林下軌")

    # 5. 價格動量評分
    price_change = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0
    if price_change > 2:
        buy_score += 1.0
        reasons.append("漲幅超過 2%")
    elif price_change < -2:
        sell_score += 1.0
        reasons.append("跌幅超過 2%")

    # 標準化評分
    total_score = buy_score + sell_score
    if total_score > 0:
        buy_strength = buy_score / total_score
        sell_strength = sell_score / total_score
    else:
        buy_strength = 0.5
        sell_strength = 0.5

    # 決定信號
    if buy_strength > 0.6:
        signal = "BUY"
    elif sell_strength > 0.6:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "signal": signal,
        "buy_score": round(buy_score, 2),
        "sell_score": round(sell_score, 2),
        "buy_strength": round(buy_strength, 4),
        "sell_strength": round(sell_strength, 4),
        "reasons": reasons
    }


# ---------------------------------------------------------------------------
# 回測引擎核心
# ---------------------------------------------------------------------------

def run_backtest(ticker: str, days: int = 90) -> Dict:
    """
    執行回測分析

    參數：
        ticker: 股票代碼（如 "AAPL", "2330.TW"）
        days: 回測天數（預設 90 天）

    返回：
        包含回測結果的字典
    """
    print(f"[回測引擎] 開始回測 {ticker}，回測期間: {days} 天")

    # 1. 取得歷史數據
    try:
        stock = yf.Ticker(ticker)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 120)  # 多取一些用於計算指標
        df = stock.history(start=start_date, end=end_date)
    except Exception as e:
        print(f"[錯誤] 無法取得 {ticker} 的歷史數據: {e}")
        return {"error": str(e)}

    if len(df) < 60:
        print(f"[錯誤] 數據不足，僅有 {len(df)} 筆")
        return {"error": "數據不足"}

    # 2. 計算技術指標
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    dates = df.index.to_numpy()

    sma_20 = calculate_sma(close, 20)
    sma_60 = calculate_sma(close, 60)
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, macd_hist = calculate_macd(close)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close, 20)
    atr = calculate_atr(high, low, close, 14)

    # 3. 計算布林帶位置
    bb_width = bb_upper - bb_lower
    bb_position = np.where(bb_width > 0, (close - bb_lower) / bb_width * 100, 50)

    # 4. 每日評分與預測
    predictions = []
    lookback = 70  # 至少需要 60 日計算 SMA60

    for i in range(lookback, len(df) - 1):
        score = generate_signal_score(
            close=close[i],
            sma_20=sma_20[i],
            sma_60=sma_60[i],
            rsi=rsi[i],
            macd_hist=macd_hist[i],
            bb_position=bb_position[i],
            atr=atr[i],
            prev_close=close[i - 1]
        )

        # 實際漲跌
        actual_change = close[i + 1] - close[i]
        actual_direction = "UP" if actual_change > 0 else "DOWN"

        # 預測是否正確
        correct = (score["signal"] == "BUY" and actual_direction == "UP") or \
                  (score["signal"] == "SELL" and actual_direction == "DOWN") or \
                  (score["signal"] == "HOLD")

        predictions.append({
            "date": str(dates[i]),
            "close": round(close[i], 2),
            "next_close": round(close[i + 1], 2),
            "actual_change": round(actual_change, 2),
            "actual_direction": actual_direction,
            **score,
            "correct": correct
        })

    # 5. 計算準確度指標
    total_predictions = len(predictions)
    correct_predictions = sum(1 for p in predictions if p["correct"])

    buy_predictions = [p for p in predictions if p["signal"] == "BUY"]
    sell_predictions = [p for p in predictions if p["signal"] == "SELL"]
    hold_predictions = [p for p in predictions if p["signal"] == "HOLD"]

    buy_correct = sum(1 for p in buy_predictions if p["correct"])
    sell_correct = sum(1 for p in sell_predictions if p["correct"])
    hold_correct = sum(1 for p in hold_predictions if p["correct"])

    precision_buy = buy_correct / len(buy_predictions) if buy_predictions else 0
    precision_sell = sell_correct / len(sell_predictions) if sell_predictions else 0
    precision_hold = hold_correct / len(hold_predictions) if hold_predictions else 0
    overall_accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0

    # 6. 組合結果
    result = {
        "ticker": ticker,
        "backtest_days": days,
        "effective_predictions": total_predictions,
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "overall_accuracy": round(overall_accuracy, 4),
            "precision_buy": round(precision_buy, 4),
            "precision_sell": round(precision_sell, 4),
            "precision_hold": round(precision_hold, 4),
            "total_correct": correct_predictions,
        },
        "signal_counts": {
            "buy": len(buy_predictions),
            "sell": len(sell_predictions),
            "hold": len(hold_predictions),
            "buy_correct": buy_correct,
            "sell_correct": sell_correct,
            "hold_correct": hold_correct,
        },
        "predictions": predictions[-20:]  # 只保留最後 20 筆詳細資料
    }

    # 7. 輸出 JSON 報告
    output_dir = Path.home() / ".hermes" / "stock_backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{ticker}_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[回測引擎] 完成！報告已儲存至: {output_file}")
    print(f"[回測引擎] 準確度: {overall_accuracy:.2%}")
    print(f"[回測引擎] 買入準確度 (Precision@Buy): {precision_buy:.2%}")
    print(f"[回測引擎] 賣出準確度 (Precision@Sell): {precision_sell:.2%}")

    return result


# ---------------------------------------------------------------------------
# 主程式進入點
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python backtest_engine.py <股票代碼> [天數]")
        print("範例: python backtest_engine.py AAPL 90")
        print("範例: python backtest_engine.py 2330.TW 180")
        sys.exit(1)

    ticker_symbol = sys.argv[1]
    num_days = int(sys.argv[2]) if len(sys.argv) > 2 else 90

    result = run_backtest(ticker_symbol, num_days)
    print(json.dumps(result["metrics"], indent=2))
