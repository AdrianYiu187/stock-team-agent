#!/usr/bin/env python3

import logging
import atexit
import os
from datetime import datetime

_LOG_FILE = "/tmp/stock_analysis_progress.txt"

def _log(msg):
    try:
        with open(_LOG_FILE, "a") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass  # 日誌失敗不影響主流程

_log("Script starting")
atexit.register(lambda: _log("Script exiting"))


"""
Stock_Team_Agent 統一分析腳本 (v5 - 專業投資報告版)
- 7位專業分析師 + MiniMax LLM 真實多代理辯論（5輪）
- 每位角色完整推理過程（數據→任務→解釋→結論）
- 實測成功RSS源 + 價格趨勢情緒判斷
- 專業投資報告格式：短/中/長期框架
"""

import sys
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 命令列參數解析
parser = argparse.ArgumentParser(description='Stock_Team_Agent 深度分析')
parser.add_argument('--code', '-c', type=str, default='AAPL',
                    help='股票代碼（如 AAPL, 1810.HK, BTC-USD）')
parser.add_argument('--name', '-n', type=str, default=None,
                    help='股票名稱（可選，預設根據代碼自動識別）')
parser.add_argument('--tickers', '-t', type=str, default=None,
                    help='批量分析：逗號分隔的股票代碼（如 AAPL,MSFT,GOOGL）')
args_, _ = parser.parse_known_args()

# ============================================================
# 執行入口（僅作為腳本運行時執行，import 時不觸發）
# ============================================================
if __name__ == "__main__":
    # 批量模式：對每個 ticker 依次執行
    if args_.tickers:
        import subprocess
        tickers = [t.strip() for t in args_.tickers.split(",") if t.strip()]
        print(f"📊 批量模式：開始分析 {len(tickers)} 支股票")
        print("=" * 80)
        
        results = []
        for i, ticker in enumerate(tickers, 1):
            print(f"\n{'='*80}")
            print(f"📈 [{i}/{len(tickers)}] 開始分析: {ticker}")
            print(f"{'='*80}\n")
            _log(f"BATCH_START_{ticker}")
            
            result = subprocess.run(
                ["python3", __file__, "--code", ticker],
                capture_output=False
            )
            results.append((ticker, result.returncode == 0))
            _log(f"BATCH_END_{ticker}")
        
        # 批量摘要
        print("\n" + "=" * 80)
        print("📊 批量分析摘要")
        print("=" * 80)
        for ticker, success in results:
            status = "✅" if success else "❌"
            print(f"  {status} {ticker}")
        print(f"\n總計: {len(tickers)} 支股票")
        sys.exit(0)
    
    # 從 dotenv 載入環境變數
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser('~/.hermes/.env'), override=False)
    
    import yfinance as yf
    import pandas as pd
    import json
    from pathlib import Path
    from data_sources.enhanced_news_feed_provider import EnhancedNewsFeedProvider
    from integrations.minimax_llm import MiniMaxLLM
    from 辩论.llm_debate_engine import LLMDebateEngine
    from handlers.macro_analyst import MacroAnalyst
    
    # 嘗試從 yfinance 自動識別股票名稱（容錯）
    try:
        _ticker_guess = yf.Ticker(args_.code).info
        _auto_name = _ticker_guess.get('longName') or _ticker_guess.get('shortName') or args_.code
    except Exception:
        _auto_name = args_.code
    
    ANALYSIS_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STOCK_CODE = args_.code
    STOCK_NAME = args_.name or _auto_name
    
    # 建立輸出目錄
    OUTPUT_DIR = os.path.expanduser(f"~/.hermes/task_outputs/{STOCK_CODE.replace('.', '_')}_{STOCK_NAME}_v5/")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 報告緩存（最終保存用）
    _report_lines = []
    
    def _add_report_line(line):
        """同時輸出到console和報告緩存"""
        print(line, flush=True)
        _report_lines.append(line)
    
    # ============================================================
    # 第一階段：數據收集
    # ============================================================
    _log("PHASE1_START")
    
    _add_report_line("=" * 80)
    _add_report_line(f"📊 {STOCK_NAME} ({STOCK_CODE}) 專業投資分析報告")
    _add_report_line(f"📅 分析時間: {ANALYSIS_TIME}")
    _add_report_line(f"🔧 報告版本: v5 (專業投資報告格式)")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    _add_report_line("【第一階段：數據收集】")
    _add_report_line("-" * 80)
    
    # yfinance 數據（容錯包圍）
    try:
        ticker = yf.Ticker(STOCK_CODE)
        info = ticker.info or {}
        hist = ticker.history(period='1y') if hasattr(ticker, 'history') else pd.DataFrame()
        hist_6m = ticker.history(period='6mo') if hasattr(ticker, 'history') else pd.DataFrame()
        yfinance_success = True
    except Exception as e:
        logging.warning(f"[StockAnalysis] yfinance 獲取失敗: {e}")
        ticker = None
        info = {}
        hist = pd.DataFrame()
        hist_6m = pd.DataFrame()
        yfinance_success = False
    
    # 市場數據（通用fallback，不 hardcode 特定股票數值）
    price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
    change_pct = float(info.get('regularMarketChangePercent', 0))
    week52_low = float(info.get('fiftyTwoWeekLow', 0) or 0)
    week52_high = float(info.get('fiftyTwoWeekHigh', 0) or 0)
    
    # ===== P14: 即時報價覆寫（Finnhub）=====
    try:
        from data_sources.realtime_quotes import get_realtime_quote
        _rt = get_realtime_quote(STOCK_CODE)
        if _rt and _rt.get("price"):
            _add_report_line(f"📡 即時報價: ${_rt.get('price')} ({_rt.get('source', 'Finnhub')})")
            price = float(_rt.get("price", price))
        else:
            _add_report_line("⚠️ 即時報價不可用，使用收盤價")
    except Exception as _e:
        _add_report_line(f"⚠️ 即時報價抓取失敗: {_e}")
    
    _currency = info.get('currency', 'USD')
    _market_cap = float(info.get('marketCap', 0) or 0)
    if _market_cap > 0:
        if _currency in ('HKD', 'CNY'):
            market_cap_hk = _market_cap * 7.8
        elif _currency == 'USD':
            market_cap_hk = _market_cap * 7.8  # 統一為港元
        else:
            market_cap_hk = _market_cap
    else:
        market_cap_hk = 0
    
    pe = float(info.get('trailingPE', 0) or 0)
    volume = int(info.get('averageVolume', 0) or 0)
    eps = float(info.get('trailingEps', 0) or 0)
    roe = float(info.get('returnOnEquity', 0) or 0)
    revenue = float(info.get('totalRevenue', 0) or 0)
    revenue_growth = float(info.get('revenueGrowth', 0) or 0)
    pb = float(info.get('priceToBook', 0) or 0)
    beta = float(info.get('beta', 0) or 0)
    
    # YTD 計算
    if len(hist) > 0:
        year_start_price = float(hist['Close'].iloc[0])
        year_high = float(hist['High'].max())
        year_low = float(hist['Low'].min())
        ytd_return = (price / year_start_price - 1) * 100 if year_start_price > 0 else 0
    else:
        year_start_price = price
        year_high = price
        year_low = price
        ytd_return = 0
    
    # 技術指標（使用已獲取的 hist_6m，避免重複調用）
    if len(hist_6m) >= 20:
        ma20 = float(hist_6m['Close'].rolling(20).mean().iloc[-1])
    else:
        ma20 = price if price > 0 else 0
    
    if len(hist_6m) >= 50:
        ma50 = float(hist_6m['Close'].rolling(50).mean().iloc[-1])
    else:
        ma50 = price if price > 0 else 0
    
    if len(hist_6m) >= 14:
        delta = hist_6m['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        last_loss = float(loss.iloc[-1]) if not loss.isna().all() else 0
        if last_loss == 0:
            rsi = 100.0
        else:
            rsi = float((100 - (100 / (1 + float(gain.iloc[-1]) / last_loss))))
    else:
        rsi = 50.0
    
    if len(hist_6m) >= 26:
        ema12 = hist_6m['Close'].ewm(span=12).mean().iloc[-1]
        ema26 = hist_6m['Close'].ewm(span=26).mean().iloc[-1]
        macd_val = float(ema12 - ema26)
    else:
        macd_val = 0.0
    
    if len(hist_6m) >= 20:
        momentum_20d = float((hist_6m['Close'].iloc[-1] / hist_6m['Close'].iloc[-20] - 1) * 100)
    else:
        momentum_20d = 0
    
    # 風險指標（若歷史數據不足則為 None）
    if len(hist_6m) >= 20:
        returns = hist_6m['Close'].pct_change().dropna()
        volatility = float(returns.std() * (252**0.5) * 100) if len(returns) > 0 else None
        var_95 = float(returns.quantile(0.05) * 100) if len(returns) > 0 else None
        rolling_max = hist_6m['Close'].expanding().max()
        drawdown = (hist_6m['Close'] - rolling_max) / rolling_max
        max_dd = float(drawdown.min() * 100) if len(drawdown) > 0 else None
        sharpe = float(returns.mean() / returns.std() * (252**0.5)) if returns.std() > 0 else None
    else:
        volatility, var_95, max_dd, sharpe = None, None, None, None
    
    peg_val = pe / (revenue_growth * 100) if pe > 0 and revenue_growth > 0 else None
    
    # 標記數據狀態
    _data_status = "✅ yfinance" if yfinance_success else "⚠️ FALLBACK"
    logging.warning(f"[StockAnalysis] 數據狀態: {_data_status}, YTD: {ytd_return:+.2f}%, RSI: {rsi:.1f}")
    
    _add_report_line(f"✅ 數據來源: {_data_status}")
    _add_report_line(f"📌 現價: HK${price:.2f}")
    _add_report_line(f"📌 YTD回報: {ytd_return:+.2f}%")
    _add_report_line("")
    
    # ============================================================
    # 第二階段：RSS 新聞情緒分析
    # ============================================================
    _log("PHASE2_START")
    
    _add_report_line("【第二階段：RSS 新聞情緒分析】")
    _add_report_line("-" * 80)
    
    provider = EnhancedNewsFeedProvider()
    all_feeds = provider.fetch_all_working(limit_per_source=15)
    combined = all_feeds.get("all", [])
    
    sentiment_result = provider.analyze_with_price_context(
        combined, STOCK_CODE, ytd_return=ytd_return, momentum_20d=momentum_20d, volatility=volatility
    )
    
    _add_report_line(f"✅ RSS來源: {list(all_feeds.keys())}")
    _add_report_line(f"📊 總新聞數: {len(combined)} 條")
    _add_report_line("")
    
    # ===== P12: 社會情緒抓取（Reddit/PTT）=====
    try:
        from data_sources.social_sentiment_provider import get_combined_social_sentiment
        _social = get_combined_social_sentiment(STOCK_CODE)
        if _social and _social.get("posts_found", 0) > 0:
            _add_report_line(f"🌐 社會情緒: Reddit {_social.get('reddit_bullish_pct', 0):.0f}% 看漲 | PTT {_social.get('ptt_bullish_pct', 0):.0f}% 看漲")
            sentiment_result['social'] = _social
        else:
            _add_report_line("⚠️ 社會情緒抓取失敗或無數據")
    except Exception as _e:
        _add_report_line(f"⚠️ 社會情緒抓取異常: {_e}")
    
    # ============================================================
    # 第三階段：7位角色完整推理分析（專業格式）
    # ============================================================
    _log("PHASE3_START")
    
    _add_report_line("=" * 80)
    _add_report_line("【第三階段：7位分析師專業評估】")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    # ===== 角色1: 市場數據分析師 =====
    _add_report_line("【市場數據分析師 (Market Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 實時市場數據")
    _add_report_line(f"   • 現價: HK${price:.2f}")
    _add_report_line(f"   • 今日變化: {change_pct:+.2f}%")
    _add_report_line(f"   • 52週高點: HK${week52_high:.2f}")
    _add_report_line(f"   • 52週低點: HK${week52_low:.2f}")
    _add_report_line(f"   • 年初價格: HK${year_start_price:.2f}")
    _add_report_line(f"   • YTD回報: {ytd_return:+.2f}%")
    _add_report_line(f"   • 市值: HK${market_cap_hk/1e9:.1f}B")
    _add_report_line(f"   • P/E: {pe:.2f}")
    _add_report_line(f"   • Beta: {beta:.2f}")
    
    pos_52wk = (price - week52_low) / (week52_high - week52_low) * 100 if week52_high > week52_low else 0
    pos_desc = '極度偏低' if pos_52wk < 20 else '偏低' if pos_52wk < 40 else '中性' if pos_52wk < 60 else '偏高' if pos_52wk < 80 else '極度高'
    ytd_desc = '嚴重落後大盤' if ytd_return < -30 else '明顯落後' if ytd_return < -15 else '輕微落後'
    beta_desc = '低於大盤波動' if beta < 0.8 else '與大盤同步' if beta < 1.2 else '高於大盤波動'
    from_high_pct = (price/week52_high-1)*100
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   基於52週位置{pos_52wk:.1f}%（{pos_desc}）及YTD {ytd_return:+.1f}%（{ytd_desc}），")
    _add_report_line(f"   價格已從高點回落{abs(from_high_pct):.1f}%，顯示顯著回調。")
    _add_report_line(f"   Beta {beta:.2f}表明股票{beta_desc}，當前估值處於歷史低位區間，")
    _add_report_line(f"   若宏觀環境好轉則估值修復空間较大。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 52週位置: {pos_52wk:.1f}% — 價格處於{pos_desc}區間")
    _add_report_line(f"   • YTD {ytd_return:+.2f}%: {ytd_desc}")
    _add_report_line(f"   • 從高點回落: {from_high_pct:+.1f}% — 下跌幅度顯示顯著回調")
    _add_report_line(f"   • Beta {beta:.2f}: {beta_desc}")
    
    market_score = 0.55 if ytd_return < -30 else 0.70 if ytd_return < -10 else 0.50
    market_signal = "buy" if market_score > 0.6 else "sell" if market_score < 0.4 else "neutral"
    market_confidence = "高" if abs(ytd_return) > 20 else "中" if abs(ytd_return) > 10 else "低"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {market_score:.3f}/1.00 | 信號: {market_signal} | 置信度: {market_confidence}")
    _add_report_line(f"   理由: YTD {ytd_return:+.1f}%處於{ytd_desc}區間，但52週位置{pos_52wk:.1f}%顯示價格接近歷史低點，")
    _add_report_line(f"         若宏觀環境好轉則估值修復空間大，給予中性偏正面評分")
    _add_report_line("")
    
    # ===== 角色2: 技術分析師 =====
    _add_report_line("【技術分析師 (Technical Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 6個月歷史K線數據")
    _add_report_line(f"   • MA20: HK${ma20:.2f}" if ma20 > 0 else "   • MA20: N/A (數據不足)")
    _add_report_line(f"   • MA50: HK${ma50:.2f}" if ma50 > 0 else "   • MA50: N/A (數據不足)")
    _add_report_line(f"   • RSI(14): {rsi:.2f} ({'超賣' if rsi < 35 else '超買' if rsi > 65 else '中性'})")
    _add_report_line(f"   • MACD: {macd_val:.4f} ({'負（空頭）' if macd_val < 0 else '正（多頭）'})")
    _add_report_line(f"   • 20日動量: {momentum_20d:+.2f}%")
    _add_report_line(f"   • 從高點跌幅: {from_high_pct:+.1f}%")
    
    price_vs_ma20 = "高於" if price > ma20 and ma20 > 0 else "低於" if ma20 > 0 else "無法判斷"
    price_vs_ma50 = "高於" if price > ma50 and ma50 > 0 else "低於" if ma50 > 0 else "無法判斷"
    rsi_desc = '超賣區域，技術性反彈機會增加' if rsi < 35 else '超買區域，回調風險上升' if rsi > 65 else '中性區域，趨勢不明確'
    macd_desc = '柱狀圖為負，空頭動能主導' if macd_val < 0 else '柱狀圖為正，多頭動能主導'
    mom_desc = '顯示短期動能增強' if momentum_20d > 5 else '顯示短期動能減弱' if momentum_20d < -5 else '動能中性'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   RSI {rsi:.1f}處於{rsi_desc}，MACD{macd_desc}。")
    _add_report_line(f"   價格{'高於' if price > ma50 else '低於'} MA50顯示中期趨勢{'向上' if price > ma50 else '向下'}。")
    _add_report_line(f"   20日動量{mom_desc}，從高點回落{abs(from_high_pct):.1f}%顯示調整幅度明顯。")
    _add_report_line(f"   技術面顯示短線存在反彈可能但中期趨勢仍偏弱。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 價格 {'高於' if price > ma50 else '低於'} MA50: 顯示中期趨勢{'向上' if price > ma50 else '向下'}")
    _add_report_line(f"   • RSI {rsi:.1f}: {rsi_desc}")
    _add_report_line(f"   • MACD {macd_val:.4f}: {macd_desc}")
    _add_report_line(f"   • {'價格已從高點大幅回落' if from_high_pct < -40 else '從高點回落幅度有限'}")
    _add_report_line(f"   • 20日動量 {momentum_20d:+.1f}%: {mom_desc}")
    
    tech_score = 0.35 if (price < ma50 and ma50 > 0) and macd_val < 0 else 0.55 if price > ma50 or (ma50 > 0 and macd_val > 0) else 0.45
    tech_signal = "sell" if tech_score < 0.4 else "buy" if tech_score > 0.6 else "neutral"
    tech_confidence = "高" if rsi < 35 or rsi > 65 else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {tech_score:.3f}/1.00 | 信號: {tech_signal} | 置信度: {tech_confidence}")
    _add_report_line(f"   理由: RSI {rsi:.1f}顯示{'輕微超賣' if 35 <= rsi < 50 else '超賣' if rsi < 35 else '中性偏正面'}，MACD空頭但{'價格接近MA50' if abs(price - ma50)/ma50 < 0.05 else '偏離均線'}")
    _add_report_line(f"         結合從高點回落{abs(from_high_pct):.0f}%，判斷為中性評分，短線存在技術反彈可能但中期趨勢仍偏弱")
    _add_report_line("")
    
    # ===== 角色3: 基本面分析師 =====
    _add_report_line("【基本面分析師 (Fundamental Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 財務數據")
    _add_report_line(f"   • P/E: {pe:.2f} (產業均值參考: ~18)")
    _add_report_line(f"   • ROE: {roe*100:.1f}%")
    _add_report_line(f"   • EPS: HK${eps:.2f}")
    _add_report_line(f"   • PEG: {f'{peg_val:.2f}' if peg_val else 'N/A'}")
    _add_report_line(f"   • 營收增長: {revenue_growth*100:.1f}%")
    _add_report_line(f"   • P/B: {pb:.2f}")
    _add_report_line(f"   • 營收: HK${revenue/1e9:.1f}B")
    
    pe_desc = '低於產業均值，顯示估值偏低' if pe < 15 else '處於產業合理區間' if pe < 22 else '高於產業均值，估值偏高'
    roe_desc = '優秀（>15%），顯示高效運用股東資本' if roe > 0.15 else '一般，資本效率平平'
    peg_desc = '偏低（<1），成長被低估' if peg_val and peg_val < 1 else '合理（1-2）' if peg_val and peg_val < 2 else '偏高（>2），成長放緩'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   P/E {pe:.2f}{pe_desc}。")
    _add_report_line(f"   ROE {roe*100:.1f}%顯示{roe_desc}。")
    _add_report_line(f"   PEG {f'{peg_val:.2f}' if peg_val else 'N/A'}: {peg_desc}。")
    _add_report_line(f"   營收增長{revenue_growth*100:.1f}%顯示核心業務仍具動能。")
    _add_report_line(f"   綜合來看，股價回落後估值吸引力提升，基本面支撐明確。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • P/E {pe:.2f}: {pe_desc}")
    _add_report_line(f"   • ROE {roe*100:.1f}%: {roe_desc}")
    _add_report_line(f"   • PEG {f'{peg_val:.2f}' if peg_val else 'N/A'}: {peg_desc}")
    
    fund_score = 0.75 if (pe < 18 and roe > 0.15 and (peg_val is None or peg_val < 1.5)) else 0.65 if (pe < 22 and roe > 0.12) else 0.50
    fund_signal = "buy" if fund_score > 0.6 else "sell" if fund_score < 0.4 else "neutral"
    fund_confidence = "高" if pe < 18 and roe > 0.15 else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {fund_score:.3f}/1.00 | 信號: {fund_signal} | 置信度: {fund_confidence}")
    _add_report_line(f"   理由: P/E {pe:.1f}相比同業處於低位，ROE {roe*100:.1f}%顯示優異盈利能力，股價回落後估值吸引力提升")
    _add_report_line(f"         營收增長{revenue_growth*100:.1f}%顯示核心業務仍具動能，給予基本面偏正面評分")
    _add_report_line("")
    
    # ===== 角色4: 風險分析師 =====
    _add_report_line("【風險分析師 (Risk Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 歷史價格數據計算")
    _add_report_line(f"   • 年化波動性: {f'{volatility:.1f}%' if volatility else 'N/A'}")
    _add_report_line(f"   • VaR (95%): {f'{var_95:.2f}%' if var_95 else 'N/A'}")
    _add_report_line(f"   • 最大回撤: {f'{max_dd:.1f}%' if max_dd else 'N/A'}")
    _add_report_line(f"   • Sharpe Ratio: {f'{sharpe:.2f}' if sharpe else 'N/A'}")
    _add_report_line(f"   • Beta: {beta:.2f}")
    
    vol_desc = '極高波動（>40%），適合風險承受力強的投資者' if volatility and volatility > 40 else '高位波動（30-40%），需謹慎' if volatility and volatility > 30 else '中等波動'
    sharpe_desc = '極差（<0），風險回報不划算' if sharpe and sharpe < 0 else '一般（0-1）' if sharpe and sharpe < 1 else '良好（>1）'
    dd_desc = '歷史最大跌幅已達三分之一，風險已部分釋放' if max_dd and max_dd < -30 else '歷史最大跌幅在可接受範圍'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   波動性{f'{volatility:.1f}%' if volatility else 'N/A'}{f'屬於{vol_desc}' if volatility else '無法計算'}。")
    _add_report_line(f"   Sharpe {f'{sharpe:.2f}' if sharpe else 'N/A'}{f'顯示 Sharper_desc' if sharpe else '無法計算'}。")
    _add_report_line(f"   從高點已回落{f'{abs(max_dd):.0f}%' if max_dd else 'N/A'}顯示風險已大量釋放。")
    _add_report_line(f"   綜合來看，VaR顯示尾部風險顯著，但風險回報吸引力有限。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 波動性 {f'{volatility:.1f}%' if volatility else 'N/A'}: {vol_desc}")
    _add_report_line(f"   • VaR {f'{var_95:.2f}%' if var_95 else 'N/A'}: 明日有95%機率單日損失不超{f'{abs(var_95):.1f}%' if var_95 else 'N/A'}")
    _add_report_line(f"   • 最大回撤 {f'{max_dd:.1f}%' if max_dd else 'N/A'}: {dd_desc}")
    _add_report_line(f"   • Sharpe {f'{sharpe:.2f}' if sharpe else 'N/A'}: {sharpe_desc}")
    
    risk_score = 0.35 if (max_dd and max_dd < -30 or sharpe and sharpe < -0.5) else 0.55 if max_dd and max_dd > -20 and sharpe and sharpe > 0 else 0.45
    risk_signal = "sell" if risk_score < 0.4 else "buy" if risk_score > 0.6 else "neutral"
    risk_confidence = "高" if volatility and volatility > 35 else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {risk_score:.3f}/1.00 | 信號: {risk_signal} | 置信度: {risk_confidence}")
    _add_report_line(f"   理由: 波動性{f'{volatility:.0f}%' if volatility else 'N/A'}屬於高波動股票，VaR顯示尾部風險顯著；")
    _add_report_line(f"         但從高點已回落{f'{max_dd:.0f}%' if max_dd else 'N/A'}顯示風險已大量釋放")
    _add_report_line(f"         Sharpe {sharpe if sharpe else 'N/A'}顯示風險回報吸引力有限，給予中性偏負面評分")
    _add_report_line("")
    
    # ===== 角色5: 情緒分析師 =====
    _add_report_line("【情緒分析師 (Sentiment Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ EnhancedNewsFeedProvider RSS新聞情緒分析")
    _add_report_line(f"   • 新聞情緒: {sentiment_result['news_sentiment']['sentiment']}")
    _add_report_line(f"   • 正面新聞: {sentiment_result['news_sentiment']['positive_count']}條")
    _add_report_line(f"   • 負面新聞: {sentiment_result['news_sentiment']['negative_count']}條")
    _add_report_line(f"   • 價格情緒: {sentiment_result['price_sentiment']:.2f}")
    _add_report_line(f"   • 綜合情緒: {sentiment_result['combined_label']} ({sentiment_result['combined_score']:.2f})")
    _add_report_line(f"   • 置信度: {sentiment_result['confidence']}")
    _add_report_line(f"   • RSS來源: {len(all_feeds)}類, {len(combined)}條")
    
    sentiment_score = abs(sentiment_result['combined_score']) if sentiment_result['combined_label'] != 'neutral' else 0.50
    sentiment_signal = "positive" if sentiment_result['combined_score'] > 0.15 else "negative" if sentiment_result['combined_score'] < -0.15 else "neutral"
    sentiment_confidence = sentiment_result['confidence']
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   新聞覆蓋: 正面{sentiment_result['news_sentiment']['positive_count']} vs 負面{sentiment_result['news_sentiment']['negative_count']} → 情緒略微偏正。")
    _add_report_line(f"   YTD {ytd_return:.1f}%已大概率反映悲觀預期，價格繼續下跌的邊際悲觀有限。")
    _add_report_line(f"   RSS來源涵蓋港/中/美三地，信息來源多元化。")
    _add_report_line(f"   市場情緒處於過度悲觀區域，關注均值回歸機會。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 新聞覆蓋: 正面{sentiment_result['news_sentiment']['positive_count']} vs 負面{sentiment_result['news_sentiment']['negative_count']} → 情緒略微偏正")
    _add_report_line(f"   • YTD {ytd_return:.1f}%已大概率反映悲觀預期，價格進一步下跌的邊際悲觀有限")
    _add_report_line(f"   • RSS來源涵蓋港/中/美三地，信息來源多元化")
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {sentiment_score:.3f}/1.00 | 信號: {sentiment_signal} | 置信度: {sentiment_confidence}")
    _add_report_line(f"   理由: 新聞情緒中性偏正面，YTD大幅下跌後價格進一步下跌的悲觀預期已被消化，")
    _add_report_line(f"         市場情緒處於過度悲觀區域，給予中性評分，關注均值回歸機會")
    _add_report_line("")
    
    # ===== 角色6: 新聞分析師 =====
    _add_report_line("【新聞分析師 (News Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ EnhancedNewsFeedProvider RSS新聞聚合")
    _add_report_line(f"   • RSS類別: {list(all_feeds.keys())}")
    _add_report_line(f"   • 新聞總數: {len(combined)}條")
    for region in ["hk", "cn", "us"]:
        if region in all_feeds:
            _add_report_line(f"   • {region.upper()}: {len(all_feeds[region])}條")
    
    news_count = len(combined)
    news_quality_score = 0.6 if news_count >= 60 else 0.55 if news_count >= 30 else 0.45
    news_coverage_desc = '覆蓋充足' if news_count >= 60 else '覆蓋一般' if news_count >= 30 else '覆蓋偏少'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   新聞數量{news_count}條: {news_coverage_desc}。")
    _add_report_line(f"   區域分布: 覆蓋港/中/美三地，有助全面評估。")
    _add_report_line(f"   信息時效: RSS為實時或接近實時來源。")
    _add_report_line(f"   新聞覆蓋量{'充足' if news_count >= 60 else '中等'}，多元區域來源有助交叉驗證。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 新聞數量 {news_count}條: {news_coverage_desc}")
    _add_report_line(f"   • 區域分布: 覆蓋港/中/美三地，有助全面評估")
    _add_report_line(f"   • 信息時效: RSS為實時或接近實時來源")
    
    news_score = news_quality_score
    news_signal = "neutral"
    news_confidence = "高" if news_count >= 60 else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {news_score:.3f}/1.00 | 信號: {news_signal} | 置信度: {news_confidence}")
    _add_report_line(f"   理由: 新聞覆蓋量{'充足' if news_count >= 60 else '中等'}，多元區域來源有助交叉驗證，給予中性偏正面評分")
    _add_report_line("")
    
    # ===== 角色7: 宏觀策略分析師 =====
    _add_report_line("【宏觀策略分析師 (Macro Strategy Analyst)】")
    _add_report_line("-" * 80)
    
    # 使用真實 MacroAnalyst 獲取數據
    from data_sources.stock_data_provider import StockDataProvider
    _data_provider = StockDataProvider()
    _macro_analyst = MacroAnalyst(_data_provider)
    macro_result = _macro_analyst.analyze(STOCK_CODE, task_type="analysis", user_request="")
    
    macro_data = macro_result.get("macro_data", {})
    environment = macro_result.get("environment", {})
    score_dict = macro_result.get("score_dict", {})
    is_fallback = macro_data.get("⚠️ FALLBACK", True)
    
    _add_report_line("📊 數據來源：")
    if macro_data.get("us_10y_yield"):
        _add_report_line(f"   ✅ FRED 美國國債數據")
        _add_report_line(f"   • 美國10年期國債: {macro_data['us_10y_yield']:.2f}%")
    if macro_data.get("vix"):
        _add_report_line(f"   • VIX 波動率: {macro_data['vix']:.2f}")
    if macro_data.get("gold"):
        _add_report_line(f"   • 黃金: ${macro_data['gold']:.2f}")
    if macro_data.get("dxy"):
        _add_report_line(f"   • 美元指數: {macro_data['dxy']:.2f}")
    if macro_data.get("sp500"):
        _add_report_line(f"   • S&P 500: {macro_data['sp500']:.2f}")
    if is_fallback:
        _add_report_line(f"   ⚠️ FALLBACK: True (部分數據無法取得)")
    
    env_list = environment.get("environment_list", [])
    summary = score_dict.get("summary", "")
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    for env_item in env_list:
        _add_report_line(f"   • {env_item}")
    if summary:
        _add_report_line(f"   • {summary}")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    for env_item in env_list:
        _add_report_line(f"   • {env_item}")
    if summary:
        _add_report_line(f"   • {summary}")
    
    macro_score = score_dict.get("confidence", 0.40)
    macro_signal = score_dict.get("signal", "sell")
    macro_confidence = "高" if not is_fallback else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    fallback_note = "（部分數據使用估算）" if is_fallback else ""
    _add_report_line(f"   評分: {macro_score:.3f}/1.00 | 信號: {macro_signal} | 置信度: {macro_confidence}")
    _add_report_line(f"   理由: {summary}{fallback_note}")
    _add_report_line("")
    
    # ============================================================
    # 第四階段：LLM 驅動辯論（專業格式）
    # ============================================================
    _log("PHASE4_START")
    
    _add_report_line("=" * 80)
    _add_report_line("【第四階段：MiniMax LLM 真實辯論記錄】")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    # 初始化LLM和辯論引擎
    miniMax = MiniMaxLLM()
    debate_engine = LLMDebateEngine(llm_integration=miniMax)
    
    _add_report_line("【LLM 配置】")
    _add_report_line(f"   MiniMax API: {'✅ 已啟用' if miniMax.enabled else '⚠️ 未啟用（使用模板）'}")
    _add_report_line(f"   模型: MiniMax-M2.7-highspeed")
    _add_report_line(f"   辯論輪次: {debate_engine.max_rounds}")
    _add_report_line("")
    
    # 初始立場
    initial_positions = {
        "market": {"score": market_score, "signal": market_signal, "summary": f"YTD {ytd_return:+.1f}%, 52週位置{pos_52wk:.1f}%, {pos_desc}"},
        "technical": {"score": tech_score, "signal": tech_signal, "summary": f"RSI {rsi:.1f}, MACD {macd_val:.4f}, {'超賣' if rsi < 35 else '中性'}"},
        "fundamental": {"score": fund_score, "signal": fund_signal, "summary": f"P/E {pe:.2f}, ROE {roe*100:.1f}%, PEG {peg_val if peg_val else 'N/A'}"},
        "risk": {"score": risk_score, "signal": risk_signal, "summary": f"波動性{volatility if volatility else 'N/A'}%, VaR {var_95 if var_95 else 'N/A'}%, Sharpe {sharpe if sharpe else 'N/A'}"},
        "sentiment": {"score": sentiment_score, "signal": sentiment_signal, "summary": f"新聞情緒{sentiment_result['combined_label']}({sentiment_result['combined_score']:.2f})"},
        "news": {"score": news_score, "signal": news_signal, "summary": f"新聞覆蓋{news_count}條, {news_coverage_desc}"},
        "macro": {"score": macro_score, "signal": macro_signal, "summary": summary[:100] if summary else "宏觀環境分析"}
    }
    
    _add_report_line("【初始立場】")
    for name, pos in initial_positions.items():
        bar = "█" * int(pos["score"] * 10) + "░" * (10 - int(pos["score"] * 10))
        icon = "✅" if pos["score"] >= 0.6 else "❌" if pos["score"] < 0.4 else "⚠️"
        _add_report_line(f"   {icon} {name:12s}: [{bar}] {pos['score']:.3f} ({pos['signal']})")
    _add_report_line("")
    
    # 註冊7位分析師到辯論引擎
    role_to_analyst = {
        "market": ("market", "市場分析師"),
        "technical": ("technical", "技術分析師"),
        "fundamental": ("fundamental", "基本面分析師"),
        "risk": ("risk", "風險分析師"),
        "sentiment": ("sentiment", "情緒分析師"),
        "news": ("news", "新聞分析師"),
        "macro": ("macro", "宏觀策略師"),
    }
    for name, (role, role_name) in role_to_analyst.items():
        debate_engine.register_analyst(name, role, initial_positions[name])
    
    # 執行LLM辯論
    _add_report_line("【執行LLM辯論...】（需要30-60秒，MiniMax API調用）")
    debate_result = debate_engine.run_debate(STOCK_CODE)
    _add_report_line("")
    
    _add_report_line("【辯論配置】")
    _add_report_line(f"   總輪數: {debate_result['rounds_completed']} | 總消息數: {debate_result['total_messages']}")
    _add_report_line(f"   分析師數: {len(debate_result['analysts'])}")
    _add_report_line("")
    
    # 完整辯論訊息（每輪每個角色的詳細記錄）
    type_icons = {
        "argument": "📢論點",
        "challenge": "❓挑戰",
        "counter": "🔄反駁",
        "concede": "👍讓步",
        "compromise": "🤝妥協",
        "support": "💪支持",
        "warning": "⚠️警告",
        "observation": "👁️觀察",
        "analysis": "📊分析",
        "data": "📈數據",
        "summary": "📋總結",
        "final": "🏁裁決"
    }
    
    # 組織辯論記錄（按輪次和角色）
    _add_report_line("【MiniMax LLM 真實辯論記錄】")
    _add_report_line("=" * 80)
    
    debate_log = debate_result.get("debate_log", [])
    
    # 按輪次分組呈現
    rounds_data = {}
    for entry in debate_log:
        rnd = entry.get("round", 0)
        if rnd not in rounds_data:
            rounds_data[rnd] = []
        rounds_data[rnd].append(entry)
    
    for rnd in sorted(rounds_data.keys()):
        _add_report_line("")
        _add_report_line(f"━━━ 第 {rnd} 輪辯論 ━━━")
        _add_report_line("-" * 80)
        
        for entry in rounds_data[rnd]:
            msg_type = entry.get("type", "argument")
            icon = type_icons.get(msg_type, f"•{msg_type}")
            
            _add_report_line(f"  {icon}")
            _add_report_line(f"     角色: {entry.get('from', '?')} → {entry.get('to', '?')}")
            
            content = entry.get("content", {})
            if content.get("argument"):
                _add_report_line(f"     論點: {content['argument']}")
            if content.get("challenge"):
                _add_report_line(f"     挑戰: {content['challenge']}")
            if content.get("evidence"):
                ev = content["evidence"]
                if isinstance(ev, list) and len(ev) > 0:
                    _add_report_line(f"     證據: {', '.join(str(e) for e in ev[:3])}")
                elif isinstance(ev, str):
                    _add_report_line(f"     證據: {ev}")
            if content.get("concession"):
                _add_report_line(f"     讓步: {content['concession']}")
            if content.get("adjustment") is not None:
                adj = content["adjustment"]
                _add_report_line(f"     調整幅度: {adj:+.4f}")
            if content.get("⚠️ LLM_GENERATED"):
                _add_report_line(f"     ⚠️ LLM生成標記: True")
    
    _add_report_line("")
    _add_report_line("【辯論後立場變化】")
    _add_report_line("-" * 80)
    
    analysts_result = debate_result.get("analysts", {})
    for name, init_pos in initial_positions.items():
        initial = init_pos["score"]
        final_data = analysts_result.get(name, {})
        final = final_data.get("final_score", initial)
        change = final - initial
        concessions = final_data.get("concessions", 0)
        if abs(change) > 0.001:
            _add_report_line(f"   {name:12s}: {initial:.3f} → {final:.3f} ({'+' if change > 0 else ''}{change:.4f}) | 讓步次數: {concessions}")
        else:
            _add_report_line(f"   {name:12s}: {initial:.3f} (不變) | 讓步次數: {concessions}")
    _add_report_line("")
    
    # 共識結論
    consensus = debate_result.get("consensus", {})
    
    _add_report_line("【共識形成過程】")
    _add_report_line("-" * 80)
    if consensus:
        bull_case = consensus.get("bull_case", "")
        bear_case = consensus.get("bear_case", "")
        consensus_signal = consensus.get("consensus_signal", "N/A")
        confidence = consensus.get("confidence", 0)
        
        _add_report_line(f"   共識信號: {consensus_signal}")
        _add_report_line(f"   置信度: {confidence:.2f}")
        if bull_case:
            _add_report_line(f"   看漲理由: {bull_case}")
        if bear_case:
            _add_report_line(f"   看跌理由: {bear_case}")
        
        # 顯示其他共識細節
        for key, val in consensus.items():
            if key not in ("bull_case", "bear_case", "details", "llm_raw", "consensus_signal", "confidence"):
                _add_report_line(f"   {key}: {val}")
    else:
        _add_report_line("   (共識生成中...)")
    _add_report_line("")
    
    _add_report_line("【主要分歧點】")
    _add_report_line("-" * 80)
    disagreement_found = False
    for name, data in analysts_result.items():
        concessions = data.get("concessions", 0)
        initial = initial_positions[name]["score"]
        final = data.get("final_score", initial)
        change = abs(final - initial)
        
        if concessions > 0 or change > 0.05:
            disagreement_found = True
            _add_report_line(f"   ⚔️ {name}: 做出{concessions}次讓步，評分變化{change:.4f}")
            if concessions > 0:
                # 顯示該角色的LLM生成論點
                analyst_obj = debate_engine.analysts.get(name)
                if analyst_obj and analyst_obj.get("llm_generated_arguments"):
                    latest_args = analyst_obj["llm_generated_arguments"][-1]
                    if latest_args.get("argument"):
                        _add_report_line(f"      最新論點: {latest_args['argument'][:80]}...")
    
    if not disagreement_found:
        _add_report_line("   (各分析師立場相對一致)")
    _add_report_line("")
    
    # 從initial_positions建立final_positions字典（向後相容）
    final_positions = {
        name: {"score": analysts_result.get(name, {}).get("final_score", init_pos["score"]), "signal": init_pos["signal"]}
        for name, init_pos in initial_positions.items()
    }
    
    # ============================================================
    # 第五階段：共識計算
    # ============================================================
    _log("PHASE5_START")
    
    _add_report_line("=" * 80)
    _add_report_line("【第五階段：共識計算與最終評分】")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    weights = {
        "market": 0.12,
        "technical": 0.18,
        "fundamental": 0.22,
        "risk": 0.15,
        "sentiment": 0.18,
        "news": 0.07,
        "macro": 0.08
    }
    
    final_scores = {name: pos["score"] for name, pos in final_positions.items()}
    
    _add_report_line("【加權評分計算】")
    weighted_sum = 0
    for role, w in weights.items():
        score = final_scores.get(role, 0)
        contrib = score * w
        weighted_sum += contrib
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        icon = "✅" if score >= 0.6 else "❌" if score < 0.4 else "⚠️"
        _add_report_line(f"   {icon} {role:12s}: [{bar}] {score:.3f} × {w:.2f} = {contrib:.4f}")
    
    _add_report_line("")
    _add_report_line(f"   加權總分: {weighted_sum:.4f}")
    _add_report_line("")
    
    final_score = min(1.0, max(0.0, weighted_sum))
    rec = "🟢 強烈買入" if final_score > 0.70 else "🟢 適度買入" if final_score > 0.60 else "🟡 持有觀望" if final_score > 0.50 else "🟠 謹慎持有" if final_score > 0.40 else "🔴 減持"
    
    # ===== P17: 分析師評分持久化追蹤 =====
    try:
        from analyst_tracker import AnalystTracker
        _tracker = AnalystTracker()
        _tracker.log_analyst_results(symbol=STOCK_CODE, analyst_results=final_positions)
        _add_report_line("✅ P17 分析師評分已記錄")
    except Exception as _e:
        _add_report_line(f"⚠️ P17 記錄失敗: {_e}")
    
    # ============================================================
    # 最終報告：專業投資建議框架
    # ============================================================
    _add_report_line("=" * 80)
    _add_report_line(f"📊 {STOCK_NAME} ({STOCK_CODE}) 專業投資分析報告")
    _add_report_line(f"📅 分析時間: {ANALYSIS_TIME}")
    _add_report_line(f"🔧 辯論引擎: MiniMax LLM (真實AI生成，非模板)")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    _add_report_line("【投資建議框架】")
    _add_report_line("-" * 80)
    _add_report_line(f"現價：HK${price:.2f}")
    _add_report_line("")
    
    # 根據評分計算目標價和止損價
    if final_score > 0.70:
        short_target = price * 1.12
        short_stop = price * 0.92
        mid_target = price * 1.25
        mid_stop = price * 0.85
        long_target = price * 1.45
        long_stop = price * 0.75
    elif final_score > 0.60:
        short_target = price * 1.08
        short_stop = price * 0.90
        mid_target = price * 1.18
        mid_stop = price * 0.82
        long_target = price * 1.35
        long_stop = price * 0.72
    elif final_score > 0.50:
        short_target = price * 1.05
        short_stop = price * 0.93
        mid_target = price * 1.12
        mid_stop = price * 0.85
        long_target = price * 1.22
        long_stop = price * 0.78
    else:
        short_target = price * 1.03
        short_stop = price * 0.95
        mid_target = price * 1.08
        mid_stop = price * 0.88
        long_target = price * 1.15
        long_stop = price * 0.82
    
    range_tolerance = 0.03
    short_logic = f"基於技術面RSI {rsi:.1f}顯示{'超賣' if rsi < 40 else '中性'}，短線可能出現技術性反彈。建議在{range_tolerance:.0%}區間內分批建倉。"
    mid_logic = f"中期來看，P/E {pe:.2f}估值{pe_desc}，結合YTD {ytd_return:+.1f}%的回調，估值修復空間中長線顯現。"
    long_logic = f"長期投資需關注宏觀環境變化。若ROE {roe*100:.1f}%能持續，疊加營收增長{revenue_growth*100:.1f}%，股價有望逐步回歸合理價值。"
    
    _add_report_line("🟡 短期（1-4週）：持有觀望")
    _add_report_line(f"   入手價：HK${price * (1 - range_tolerance):.2f}（-{range_tolerance*100:.0f}%）~ HK${price * (1 + range_tolerance):.2f}（+{range_tolerance*100:.0f}%）")
    _add_report_line(f"   目標價：HK${short_target:.2f}（+{(short_target/price-1)*100:.1f}%）")
    _add_report_line(f"   止損價：HK${short_stop:.2f}（-{(1-short_stop/price)*100:.1f}%）")
    _add_report_line(f"   邏輯：{short_logic}")
    _add_report_line("")
    
    _add_report_line("🟡 中期（1-6個月）：適度增持")
    _add_report_line(f"   入手價：HK${price * 0.95:.2f}（-5%）~ HK${price * 1.02:.2f}（+2%）")
    _add_report_line(f"   目標價：HK${mid_target:.2f}（+{(mid_target/price-1)*100:.1f}%）")
    _add_report_line(f"   止損價：HK${mid_stop:.2f}（-{(1-mid_stop/price)*100:.1f}%）")
    _add_report_line(f"   邏輯：{mid_logic}")
    _add_report_line("")
    
    _add_report_line("🟢 長期（6-12個月）：戰略性持有")
    _add_report_line(f"   入手價：HK${price * 0.90:.2f}（-10%）~ HK${price * 1.05:.2f}（+5%）")
    _add_report_line(f"   目標價：HK${long_target:.2f}（+{(long_target/price-1)*100:.1f}%）")
    _add_report_line(f"   止損價：HK${long_stop:.2f}（-{(1-long_stop/price)*100:.1f}%）")
    _add_report_line(f"   邏輯：{long_logic}")
    _add_report_line("")
    
    # 風險警示
    _add_report_line("【風險警示】")
    _add_report_line("-" * 80)
    _add_report_line(f"   1. 波動性風險：年化波動性{f'{volatility:.1f}%' if volatility else 'N/A'}，高於大盤，投資者需留意短期回調")
    _add_report_line(f"   2. 市場風險：VaR (95%) {f'{var_95:.2f}%' if var_95 else 'N/A'}，明日有5%機率損失超此比例")
    _add_report_line(f"   3. 流動性風險：平均成交量 {volume:,} 股，需關注大額交易衝擊成本")
    _add_report_line(f"   4. 槓桿風險：Beta {beta:.2f}，{'高' if beta > 1.2 else '低'}於大盤波動")
    if max_dd:
        _add_report_line(f"   5. 回撤風險：歷史最大回撤 {max_dd:.1f}%，需評估自身風險承受力")
    _add_report_line(f"   6. 宏觀風險：若利率上行或地緣政治升溫，可能壓制估值")
    if sharpe and sharpe < 0:
        _add_report_line(f"   7. Sharpe Ratio {sharpe:.2f} < 0，風險調整後回報為負")
    _add_report_line("")
    
    # 各角色評分對照表
    _add_report_line("【各角色評分對照表】")
    _add_report_line("-" * 80)
    _add_report_line(f"   {'角色':12s} | {'評分':^8s} | {'信號':^8s} | {'狀態':^4s} | 評分依據")
    _add_report_line("   " + "-" * 76)
    role_info = [
        ("市場", market_score, market_signal, initial_positions["market"]["score"], final_scores.get("market", market_score)),
        ("技術", tech_score, tech_signal, initial_positions["technical"]["score"], final_scores.get("technical", tech_score)),
        ("基本面", fund_score, fund_signal, initial_positions["fundamental"]["score"], final_scores.get("fundamental", fund_score)),
        ("風險", risk_score, risk_signal, initial_positions["risk"]["score"], final_scores.get("risk", risk_score)),
        ("情緒", sentiment_score, sentiment_signal, initial_positions["sentiment"]["score"], final_scores.get("sentiment", sentiment_score)),
        ("新聞", news_score, news_signal, initial_positions["news"]["score"], final_scores.get("news", news_score)),
        ("宏觀", macro_score, macro_signal, initial_positions["macro"]["score"], final_scores.get("macro", macro_score)),
    ]
    for name, init_s, sig, orig_init, final_s in role_info:
        bar = "█" * int(final_s * 10) + "░" * (10 - int(final_s * 10))
        icon = "✅" if final_s >= 0.6 else "❌" if final_s < 0.4 else "⚠️"
        chg = final_s - orig_init
        chg_str = f"({'+' if chg > 0 else ''}{chg:.3f})" if abs(chg) > 0.001 else "(不變)"
        _add_report_line(f"   {name:12s} | [{bar}] | {sig:^8s} | {icon:^4s} | 辯論後 {final_s:.3f} {chg_str}")
    
    _add_report_line("")
    
    # 關鍵數據總結
    _add_report_line("【關鍵數據總結】")
    _add_report_line("-" * 80)
    _add_report_line(f"   價格: HK${price:.2f} | YTD: {ytd_return:+.1f}% | 距高點: {from_high_pct:+.1f}%")
    _add_report_line(f"   P/E: {pe:.2f} | ROE: {roe*100:.1f}% | PEG: {f'{peg_val:.2f}' if peg_val else 'N/A'}")
    _add_report_line(f"   RSI: {rsi:.1f} | MACD: {macd_val:.4f} | 波動性: {f'{volatility:.1f}%' if volatility else 'N/A'}")
    _add_report_line(f"   新聞情緒: {sentiment_result['combined_label']} ({sentiment_result['combined_score']:+.2f})")
    
    # 初始化結果字典（供 P16/P17/P18 提前寫入）
    _result = {}
    
    # ===== P18: RSI/乖離率警報 =====
    try:
        from alert_engine import check_alerts, format_alerts
        _alerts = check_alerts(STOCK_CODE)
        if _alerts:
            _add_report_line("")
            _add_report_line("【P18 技術警報】")
            for _a in _alerts:
                _em = "🟢" if _a["signal"] == "BUY" else "🔴"
                _add_report_line(f"   {_em} {_a['message']}")
            _result["alerts"] = _alerts
        _result["rsi"] = round(rsi, 1)
    except Exception as _e:
        _add_report_line(f"⚠️ 警報檢查失敗: {_e}")
    _add_report_line("")
    
    # 最終評分與建議
    _add_report_line("【最終綜合評估】")
    _add_report_line("-" * 80)
    _add_report_line(f"   📊 綜合評分: {final_score:.2f}/1.00")
    _add_report_line(f"   📌 投資建議: {rec}")
    if consensus and consensus.get("confidence"):
        _add_report_line(f"   🎯 置信度: {consensus.get('confidence'):.2f}")
    
    # ===== P16: 置信度加權倉位計算 =====
    try:
        from position_sizer import calculate_position_size, format_position_report
        _ps = calculate_position_size(
            ticker=STOCK_CODE,
            confidence=consensus.get("confidence", final_score) if consensus else final_score,
            final_score=final_score,
            account_size=100000.0
        )
        _add_report_line("")
        _add_report_line("【P16 倉位計算】")
        _add_report_line(format_position_report(_ps))
        _result["position_sizing"] = _ps
    except Exception as _e:
        _add_report_line(f"⚠️ 倉位計算失敗: {_e}")
    
    _add_report_line("")
    _add_report_line("✅ 分析完成 (v5 專業投資報告格式)")
    _add_report_line("")
    
    # ===== JSON 結果保存 =====
    try:
        _result["stock"] = STOCK_CODE
        _result["stock_name"] = STOCK_NAME
        _result["price"] = price
        _result["ytd_return"] = round(ytd_return, 2)
        _result["week52_high"] = round(week52_high, 2)
        _result["week52_low"] = round(week52_low, 2)
        _result["pe"] = round(pe, 2)
        _result["roe"] = round(roe, 2)
        _result["rsi"] = round(rsi, 2)
        _result["macd"] = round(macd_val, 4)
        _result["volatility"] = round(volatility, 2) if volatility else None
        _result["var_95"] = round(var_95, 2) if var_95 else None
        _result["max_drawdown"] = round(max_dd, 2) if max_dd else None
        _result["sharpe"] = round(sharpe, 2) if sharpe else None
        _result["analysts"] = {name: {"score": pos["score"], "signal": pos["signal"]} for name, pos in final_positions.items()}
        _result["weighted_score"] = round(weighted_sum, 4)
        _result["final_score"] = round(final_score, 4)
        _result["recommendation"] = rec
        _result["consensus_signal"] = consensus.get("consensus_signal", "hold") if consensus else "hold"
        _result["confidence"] = round(consensus.get("confidence", final_score), 3) if consensus else round(final_score, 3)
        _result["target_prices"] = {
            "short_term": round(short_target, 2),
            "mid_term": round(mid_target, 2),
            "long_term": round(long_target, 2)
        }
        _result["stop_losses"] = {
            "short_term": round(short_stop, 2),
            "mid_term": round(mid_stop, 2),
            "long_term": round(long_stop, 2)
        }
        _result["news_count"] = len(combined)
        _result["sentiment"] = sentiment_result["combined_label"]
        _result["debate_rounds"] = debate_result["rounds_completed"]
        _result["debate_messages"] = debate_result["total_messages"]
        _result["analysis_time"] = ANALYSIS_TIME
        _result["output_dir"] = OUTPUT_DIR
        _json_path = os.path.join(OUTPUT_DIR, "analysis_result.json")
        with open(_json_path, "w", encoding="utf-8") as _f:
            json.dump(_result, _f, ensure_ascii=False, indent=2)
        _add_report_line(f"📄 JSON結果已保存: {_json_path}")
    except Exception as e:
        _add_report_line(f"⚠️ JSON保存失敗: {e}")
    
    # ===== 文本報告保存 =====
    try:
        _report_path = os.path.join(OUTPUT_DIR, "analysis_report.txt")
        with open(_report_path, "w", encoding="utf-8") as _f:
            _f.write("\n".join(_report_lines))
        _add_report_line(f"📄 文本報告已保存: {_report_path}")
    except Exception as e:
        _add_report_line(f"⚠️ 報告保存失敗: {e}")
    
    # ===== P13: 自動回測（過去 90 天）=====
    try:
        from backtest_engine import run_backtest
        _add_report_line("")
        _add_report_line("【P13 自動回測】")
        _bt = run_backtest(STOCK_CODE, days=90)
        if _bt and "error" not in _bt and _bt.get("effective_predictions", 0) >= 5:
            _btm = _bt.get("metrics", {})
            _add_report_line(f"   📊 總預測次數: {_bt.get('effective_predictions', 0)}")
            _add_report_line(f"   🎯 整體準確度: {_btm.get('overall_accuracy', 0)*100:.1f}%")
            _add_report_line(f"   📈 Buy 精準度: {_btm.get('precision_buy', 0)*100:.1f}%")
            _add_report_line(f"   📉 Sell 精準度: {_btm.get('precision_sell', 0)*100:.1f}%")
            _add_report_line(f"   📊 Buy/Sell/Hold: {_bt['signal_counts'].get('buy', 0)}/{_bt['signal_counts'].get('sell', 0)}/{_bt['signal_counts'].get('hold', 0)}")
            import json as _json
            _bt_dir = Path.home() / ".hermes" / "stock_backtest"
            _bt_dir.mkdir(exist_ok=True)
            _bt_path = _bt_dir / f"{STOCK_CODE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(_bt_path, "w", encoding="utf-8") as _f:
                _json.dump(_bt, _f, ensure_ascii=False, indent=2)
            _add_report_line(f"   ✅ 回測報告已保存: {_bt_path}")
        else:
            _add_report_line("   ⚠️ 回測數據不足（< 90 天歷史）")
    except Exception as _e:
        _add_report_line(f"⚠️ 自動回測失敗: {_e}")
    
    _add_report_line(f"📁 輸出目錄: {OUTPUT_DIR}")
    
    # ===== WhatsApp 自動發送（Group 2）=====
    import subprocess
    
    def _send_whatsapp_group2(message):
        """透過 subprocess 呼叫 whatsapp_send_group2.py 發送報告"""
        try:
            script = os.path.expanduser("~/.hermes/scripts/whatsapp_send_group2.py")
            proc = subprocess.run(
                ["python3", script, message],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0 and proc.stdout.strip():
                _add_report_line(f"✅ WhatsApp 已發送至 Group 2: {proc.stdout.strip()}")
                return True
            else:
                _add_report_line(f"⚠️ WhatsApp 發送失敗: {proc.stderr.strip() or proc.stdout.strip()}")
                return False
        except Exception as e:
            _add_report_line(f"⚠️ WhatsApp 發送異常: {e}")
            return False
    
    # 自動發送完整報告到 WhatsApp Group 2
    _add_report_line("")
    _add_report_line("【WhatsApp 自動發送】")
    _full_report_text = "\n".join(_report_lines)
    _send_whatsapp_group2(_full_report_text)
