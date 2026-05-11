#!/usr/bin/env python3
"""
Stock Team Agent — Phase A/B 反思內存系統
基於 TradingAgents 的雙階段反思模式

Phase A (store_pending):  分析完成時，寫入 pending 決策日誌
Phase B (resolve):        下次運行同一 ticker 時，fetch 實際回報，調用 LLM 反思

借鑒 TradingAgents:
- Atomic write 防止崩潰
- 2-4句純文本反思（限制長度，防止 Prompt Injection）
- 與現有 DecisionLogger 無縫整合
"""

from __future__ import annotations

import json
import os
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DEFAULT_MEMORY_DIR = Path.home() / ".hermes" / "stock_memory"
PHASE_A_LOG = DEFAULT_MEMORY_DIR / "phase_a_pending.jsonl"
PHASE_B_LOG = DEFAULT_MEMORY_DIR / "phase_b_resolved.jsonl"
LOCK_FILE = DEFAULT_MEMORY_DIR / ".phase_ab.lock"


# ─── Atomic Write ─────────────────────────────────────────────────────────────

def _atomic_write(path: Path, content: str) -> None:
    """寫入臨時文件再 rename，防止崩潰導致日誌損壞"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


def _atomic_append(path: Path, line: str) -> None:
    """一行一行 atomic append（只用於 phase_a_pending）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".append.tmp")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    tmp.write_text(existing + line + "\n", encoding="utf-8")
    tmp.rename(path)


# ─── Phase A: Store Pending Decision ─────────────────────────────────────────

def store_pending_decision(
    symbol: str,
    date: str,
    decision: dict,  # full analysis_result dict from stock_analysis.py
    rating: str,
    final_score: float,
    confidence: float,
    rationale: str,
    analysts: dict,  # {name: {score, signal, summary}}
    price: float,
) -> None:
    """
    Phase A: 分析完成後寫入 pending 列表。
    等下次同一 symbol 分析時觸發 Phase B（fetch 實際回報 → LLM 反思）。
    """
    entry = {
        "phase": "A",
        "decision_id": f"{symbol}_{date.replace(':', '-').replace(' ', '_')}",
        "symbol": symbol.upper(),
        "analysis_date": date,
        "rating": rating,
        "final_score": final_score,
        "confidence": confidence,
        "rationale": rationale[:500] if rationale else "",
        "analysts": analysts,
        "price_at_decision": price,
        "stored_at": datetime.now().isoformat(),
    }
    _atomic_append(PHASE_A_LOG, json.dumps(entry, ensure_ascii=False))


# ─── Phase B: Resolve Pending Decisions ────────────────────────────────────────

def _fetch_actual_return(symbol: str, entry_date: str, current_price: float) -> Optional[dict]:
    """
    從 Yahoo Finance 獲取從決策日到現在的回報率。
    返回 {raw_return, alpha_vs_sp500, holding_period_days, decision_price}
    """
    try:
        decision_dt = datetime.fromisoformat(entry_date.replace(" ", "T").split("T")[0])
        holding_days = max(1, (datetime.now() - decision_dt).days)

        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=decision_dt.date(), end=datetime.now().date() + timedelta(days=1))

        if hist.empty or len(hist) < 2:
            return None

        decision_price = float(hist["Close"].iloc[0])
        end_price = float(hist["Close"].iloc[-1]) if len(hist) > 1 else current_price
        raw_return = (end_price - decision_price) / decision_price * 100

        # Alpha vs SP500
        try:
            sp500 = yf.Ticker("^GSPC")
            sp_hist = sp500.history(start=decision_dt.date(), end=datetime.now().date() + timedelta(days=1))
            if not sp_hist.empty and len(sp_hist) > 1:
                sp_start = float(sp_hist["Close"].iloc[0])
                sp_end = float(sp_hist["Close"].iloc[-1])
                sp_return = (sp_end - sp_start) / sp_start * 100
                alpha = raw_return - sp_return
            else:
                alpha = None
        except Exception:
            alpha = None

        return {
            "raw_return": round(raw_return, 2),
            "alpha_vs_sp500": round(alpha, 2) if alpha is not None else None,
            "holding_period_days": holding_days,
            "decision_price": round(decision_price, 2),
            "end_price": round(end_price, 2),
        }
    except Exception:
        return None


def _generate_reflection(decision: dict, outcome: dict, llm_client=None) -> str:
    """
    使用 MiniMax LLM 生成 2-4 句反思。
    限制長度，防止 Prompt Injection 攻擊。
    如果 MiniMax 不可用，回退到基於規則的簡單反思。
    """
    if llm_client is None:
        # 回退：基於規則的反思（始終可用）
        raw = outcome.get("raw_return", 0)
        decision_score = decision.get("final_score", 0.5)
        rationale = decision.get("rationale", "")

        if raw > 5:
            verdict = "符合預期" if decision_score > 0.6 else "僥倖"
        elif raw > 0:
            verdict = "基本正確" if decision_score > 0.5 else "判斷失誤"
        elif raw > -5:
            verdict = "小幅偏差" if decision_score < 0.5 else "分析失效"
        else:
            verdict = "嚴重錯誤" if decision_score > 0.6 else "正確預警"

        direction = "高於" if raw > 0 else "低於"
        correction = "分析邏輯需修正。" if abs(raw) > 10 else "波動在合理範圍。"
        return (
            f"結果：{verdict}。"
            f"實際回報 {raw:+.1f}%，"
            f"{direction}預期。 "
            f"{correction}"
        )

    # MiniMax LLM 反思
        raw_val = outcome.get('raw_return', 0)
        raw_str = f"{raw_val:+.1f}%"
        hold_days = outcome.get('holding_period_days', 0)
        alpha_val = outcome.get('alpha_vs_sp500')
        alpha_str = f"{alpha_val:+.1f}%" if alpha_val is not None else "N/A"
        prompt = (
            f"你是一位資深投資分析師，請根據以下決策和實際結果，生成 2-4 句簡短反思。\n"
            f"決策日期：{decision.get('analysis_date')}\n"
            f"決策評分：{decision.get('final_score')}\n"
            f"決策理由：{decision.get('rationale')}\n"
            f"實際回報：" + raw_str + "（持有 " + str(hold_days) + " 天）\n"
            f"Alpha vs S&P500：" + alpha_str + " \n"
            f"要求：純文本，2-4 句，不超過 100 字，無列表格式，直接給結論。\n"
            f"反思："
        )

    try:
        response = llm_client.generate(prompt, max_tokens=120)
        text = response.strip() if response else ""
        # 限制長度，防止 Prompt Injection
        if len(text) > 200:
            text = text[:200] + "..."
        return text
    except Exception:
        return _generate_reflection(decision, outcome, llm_client=None)


def resolve_pending_for_symbol(symbol: str, current_price: float, llm_client=None) -> list[dict]:
    """
    檢查並解決同一 symbol 的所有 pending 決策（Phase B）。
    調用時機：stock_analysis.py 啟動時，針對同一 ticker。
    返回：解決的決策列表（每條含 reflection）。
    """
    if not PHASE_A_LOG.exists():
        return []

    symbol = symbol.upper()
    resolved = []

    # 讀取所有 pending 條目
    lines = PHASE_A_LOG.read_text(encoding="utf-8").strip().split("\n")
    remaining = []

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("phase") != "A":
            remaining.append(line)
            continue

        if entry.get("symbol") != symbol:
            remaining.append(line)
            continue

        # 找到同一 symbol 的 pending 條目 → 觸發 Phase B
        outcome = _fetch_actual_return(
            symbol,
            entry.get("analysis_date", ""),
            current_price,
        )

        if outcome is None:
            # 數據不夠，保留為 pending（稍后再試）
            remaining.append(line)
            continue

        reflection = _generate_reflection(entry, outcome, llm_client)

        resolved_entry = {
            **entry,
            "phase": "B",
            "resolved_at": datetime.now().isoformat(),
            "outcome": outcome,
            "reflection": reflection,
        }

        # atomic write 到 resolved 日誌
        _atomic_append(PHASE_B_LOG, json.dumps(resolved_entry, ensure_ascii=False))
        resolved.append(resolved_entry)

    # 重新寫入剩餘 pending（移除已解決的）
    if remaining:
        content = "\n".join(remaining) + "\n"
        _atomic_write(PHASE_A_LOG, content)
    else:
        # 全部已解決，清空 pending
        _atomic_write(PHASE_A_LOG, "")

    return resolved


# ─── Context Injection ─────────────────────────────────────────────────────────

def get_recent_reflections(symbol: str, limit: int = 5) -> str:
    """
    為 stock_analysis.py 生成的 prompt 注入過往反思。
    放在分析師 prompt 的最前面，讓 LLM 知道歷史教訓。
    """
    if not PHASE_B_LOG.exists():
        return ""

    symbol = symbol.upper()
    lines = PHASE_B_LOG.read_text(encoding="utf-8").strip().split("\n")
    reflections = []

    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("symbol") != symbol:
            continue
        reflection = entry.get("reflection", "")
        if reflection:
            reflections.append(f"[{entry.get('analysis_date', '')[:10]}] {reflection}")
        if len(reflections) >= limit:
            break

    if not reflections:
        return ""

    header = "\n⚠️ 過往反思（過往教訓，請納入分析）：\n"
    return header + "\n".join(f"  • {r}" for r in reflections)


# ─── CLI Test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Testing Phase A/B for {symbol}...")
    print(f"Memory dir: {DEFAULT_MEMORY_DIR}")
    print(f"Phase A log: {PHASE_A_LOG} (exists={PHASE_A_LOG.exists()})")
    print(f"Phase B log: {PHASE_B_LOG} (exists={PHASE_B_LOG.exists()})")
    resolved = resolve_pending_for_symbol(symbol, 150.0)
    print(f"Resolved: {len(resolved)} entries")
    for r in resolved:
        print(f"  - {r.get('analysis_date')} | {r.get('outcome', {}).get('raw_return'):+.1f}% | {r.get('reflection', '')[:80]}")
    print(f"\nRecent reflections:\n{get_recent_reflections(symbol)}")
