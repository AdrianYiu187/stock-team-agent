#!/usr/bin/env python3
"""
Stock Team Agent — Phase B Cronjob 觸發腳本

功能：
  1. 讀取 ~/.hermes/stock_memory/phase_a_pending.jsonl
  2. 對指定 symbol 用 yfinance fetch 最新收盤價
  3. 調用 memory_phase_ab.resolve_pending_for_symbol() 生成反思
  4. 從 phase_a_pending.jsonl 移除已 resolved 的 entry

用法：
  python phase_b_cron.py AAPL      # 處理單一股票
  python phase_b_cron.py --all     # 處理所有 pending symbols

技術：
  - import 從 scripts/ 相對路徑
  - MiniMaxLLM client 初始化
  - yfinance fetch 最新收盤價
  - atomic write 防止日誌損壞
"""

from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path

# ─── 相對路徑 import ──────────────────────────────────────────────────────────
# scripts/ itself 入 sys.path（integrations/ 和 memory_phase_ab.py 都在 scripts/ 下）
_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR.parent))  # 保留 parent 以便 model/ 等模組

import yfinance as yf
from integrations.minimax_llm import MiniMaxLLM
from memory_phase_ab import (
    resolve_pending_for_symbol,
    PHASE_A_LOG,
    _atomic_write,
)

# 預設記憶體目錄
DEFAULT_MEMORY_DIR = Path.home() / ".hermes" / "stock_memory"


# ─── yfinance 最新收盤價抓取 ───────────────────────────────────────────────────

def fetch_latest_close(symbol: str) -> float | None:
    """
    用 yfinance 抓取指定股票的最新收盤價。
    失敗時回傳 None。
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period="5d")  # 最近5個交易日，確保有資料
        if hist.empty:
            return None
        close_prices = hist["Close"].dropna()
        if close_prices.empty:
            return None
        return float(close_prices.iloc[-1])
    except Exception as e:
        print(f"[警告] yfinance 獲取 {symbol} 失敗: {e}")
        return None


# ─── 讀取 phase_a_pending.jsonl 中所有 unique symbols ─────────────────────────

def get_all_pending_symbols() -> list[str]:
    """掃描 phase_a_pending.jsonl，回傳所有未處理的 symbols（去重）。"""
    if not PHASE_A_LOG.exists():
        return []
    symbols: set[str] = set()
    try:
        lines = PHASE_A_LOG.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("phase") == "A" and entry.get("symbol"):
                    symbols.add(entry["symbol"].upper())
            except json.JSONDecodeError:
                continue
    except Exception as e:
        print(f"[警告] 讀取 phase_a_pending.jsonl 失敗: {e}")
    return sorted(symbols)


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase B cronjob：對 pending symbols 抓取最新報價並生成反思"
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default=None,
        help="指定要處理的股票代碼（如 AAPL）。若搭配 --all，則額外處理此符號。",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="遍歷 phase_a_pending.jsonl 中所有 symbols 並逐一處理",
    )
    args = parser.parse_args()

    # 初始化 MiniMax LLM client
    llm_client = MiniMaxLLM()
    if not llm_client.enabled:
        print("[警告] MiniMax API Key 未設定或無效，反思生成將使用 fallback。")

    # 決定要處理的 symbols
    symbols_to_process: list[str] = []
    if args.symbol:
        symbols_to_process.append(args.symbol.upper())
    if args.all:
        pending = get_all_pending_symbols()
        for s in pending:
            if s not in symbols_to_process:
                symbols_to_process.append(s)

    if not symbols_to_process:
        print("沒有要處理的 symbols，退出。")
        return

    print(f"=== Phase B Cronjob 開始 ===")
    print(f"待處理 symbols: {symbols_to_process}")

    total_resolved = 0
    for symbol in symbols_to_process:
        print(f"\n── 處理 {symbol} ──")

        # Step 1: 用 yfinance fetch 最新收盤價
        current_price = fetch_latest_close(symbol)
        if current_price is None:
            print(f"  [跳過] 無法獲取 {symbol} 最新報價")
            continue
        print(f"  最新收盤價: ${current_price:.2f}")

        # Step 2: 呼叫 resolve_pending_for_symbol（會 atomic 寫入 phase_b_resolved.jsonl
        #         並從 phase_a_pending.jsonl 移除已 resolved 的 entry）
        try:
            resolved = resolve_pending_for_symbol(symbol, current_price, llm_client)
            if resolved:
                print(f"  ✅ 已 resolved {len(resolved)} 筆 entry")
                total_resolved += len(resolved)
                for r in resolved:
                    outcome = r.get("outcome", {})
                    reflection = r.get("reflection", "")
                    raw_ret = outcome.get("raw_return", "N/A")
                    alpha = outcome.get("alpha_vs_sp500", "N/A")
                    print(f"     回報: {raw_ret}% | Alpha vs SP500: {alpha}%")
                    print(f"     反思: {reflection[:80]}{'...' if len(reflection) > 80 else ''}")
            else:
                print(f"  (無 pending entry 需要處理)")
        except Exception as e:
            print(f"  [錯誤] resolve_pending_for_symbol 失敗: {e}")

    print(f"\n=== Phase B Cronjob 完成 ===")
    print(f"總共 resolved: {total_resolved} 筆")


if __name__ == "__main__":
    main()
