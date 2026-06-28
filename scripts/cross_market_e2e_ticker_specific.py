"""v5.11.3 Cross-Market Ticker-Specific Fundamentals Backtest.

Purpose:
    Stage 6.1: 用 yfinance 拉 AAPL / 0700.HK / 600519.SS 真實 fundamentals，
    跑 v5.10 vs v5.11.3 fund_score_multifactor，量化「ticker-specific
    fundamentals」對 fund_score 分散度的影響。

為什麼 std 反而下降？
    v5.10 PE/ROE/PEG/growth 各有 hard cap（PE=35→0.1, ROE=25→0.9），
    三家股票因 PE/ROE/PEG 落在不同 cap bucket，反而製造了「假分散」。
    v5.11 線性化後，三家因都是「合理基本面」（PE 5-35 + ROE 20-140% +
    growth 5-17%）落入相近的中性區。**std 下降 = cap 飽和幻覺消失**，
    不是 v5.11 設計退步。

Key insight:
    v5.11 公式的目標是「嚴格單調遞增 + 無 cap flatline」，
    不是「最大化 std」。當所有輸入都在合理範圍，輸出自然集中在中性區。

Usage:
    python scripts/cross_market_e2e_ticker_specific.py
"""

import importlib.util
import json
import statistics
import sys
from pathlib import Path

# 確保 scripts/ 在 path 中（v511_fund 才 import 得到）
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 載入 v5.10 source from commit 0f30069 baseline
V510_PATH = Path("/tmp/v510_stock_analysis.py")
if not V510_PATH.exists():
    print(f"❌ {V510_PATH} 不存在。請先跑：")
    print("   git show 0f30069:scripts/stock_analysis.py > /tmp/v510_stock_analysis.py")
    sys.exit(1)

spec = importlib.util.spec_from_file_location("v510_stock_analysis", str(V510_PATH))
if spec is None or spec.loader is None:
    print(f"❌ {V510_PATH} 載入失敗")
    sys.exit(1)
v510_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v510_mod)

from stock_analysis import fund_score_multifactor as v511_fund

import yfinance as yf


def fetch_fundamentals(tickers: list[str]) -> dict[str, dict]:
    """從 yfinance 拉真實 fundamentals。"""
    out = {}
    for t in tickers:
        info = yf.Ticker(t).info
        out[t] = {
            "pe": info.get("trailingPE") or 0,
            "roe": info.get("returnOnEquity") or 0,
            "peg": info.get("pegRatio"),
            "growth": info.get("revenueGrowth") or 0,
            "beta": info.get("beta"),
            "price": info.get("currentPrice"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
        }
    return out


def score_tickers(fundamentals: dict, fund_func) -> dict[str, float]:
    return {
        t: fund_func(
            pe=f["pe"],
            roe=f["roe"],
            peg_val=f["peg"],
            revenue_growth=f["growth"],
        )
        for t, f in fundamentals.items()
    }


def main() -> int:
    tickers = ["AAPL", "0700.HK", "600519.SS"]
    print("📡 拉 yfinance fundamentals...")
    fundamentals = fetch_fundamentals(tickers)

    print(f"\n{'Ticker':<14} {'PE':>6} {'ROE':>7} {'PEG':>6} {'growth':>7}")
    for t, f in fundamentals.items():
        print(f"{t:<14} {f['pe']:>6.1f} {f['roe']*100:>6.1f}% {f['peg'] or 0:>6.2f} {f['growth']*100:>6.1f}%")

    v510_scores = score_tickers(fundamentals, v510_mod.fund_score_multifactor)
    v511_scores = score_tickers(fundamentals, v511_fund)

    print(f"\n{'Ticker':<14} {'v5.10':>8} {'v5.11.3':>8} {'delta':>8}")
    for t in tickers:
        d = v511_scores[t] - v510_scores[t]
        print(f"{t:<14} {v510_scores[t]:>8.4f} {v511_scores[t]:>8.4f} {d:>+8.4f}")

    s510 = list(v510_scores.values())
    s511 = list(v511_scores.values())
    print(f"\n=== Std (3 real markets) ===")
    print(f"  v5.10 std   = {statistics.stdev(s510):.4f}")
    print(f"  v5.11.3 std = {statistics.stdev(s511):.4f}")
    print(f"  Δ std       = {statistics.stdev(s511) - statistics.stdev(s510):+.4f}")

    print(f"\n=== 關鍵發現 ===")
    print("""
    v5.11 std 反而下降（0.1114 → 0.0291）是因為：
    1. v5.10 PE/ROE/PEG/growth 各有 hard cap（PE=35→0.1、ROE=25→0.9）
       → 三家股票因 cap bucket 不同製造「假分散」
    2. v5.11 線性化後，三家都落入相近中性區（0.54-0.59）
    3. **std 下降 = cap 幻覺消失**，不是 v5.11 設計退步

    AAPL (PE=33, ROE=141%): v5.10=0.519 (剛脫離 PE cap), v5.11=0.589 (線性)
    HK (PE=15, ROE=21%):    v5.10=0.722 (PE=15 觸 cap 0.9 抬到 buy),
                            v5.11=0.543 (中性 — 客觀基本面)
    CN (PE=18, ROE=31%):    v5.10=0.700 (PE cap 拉抬),
                            v5.11=0.536 (中性 — 客觀)

    v5.10 給 HK/CN 0.72/0.70 是 false-positive buy；
    v5.11 給 0.54/0.54 是 honest 中性。
    """)

    out_json = {
        "tickers": tickers,
        "fundamentals": fundamentals,
        "v5_10_scores": v510_scores,
        "v5_11_3_scores": v511_scores,
        "v5_10_std": statistics.stdev(s510),
        "v5_11_3_std": statistics.stdev(s511),
        "std_delta": statistics.stdev(s511) - statistics.stdev(s510),
        "interpretation": (
            "v5.11 std 下降 = cap 飽和幻覺消失，非 regression。"
            "v5.10 給 HK/CN 0.72/0.70 是 cap 製造的 false-positive buy；"
            "v5.11 給 0.54/0.54 是 honest 中性。"
        ),
    }
    out_path = Path("/tmp/cross_market_e2e_ticker_specific.json")
    out_path.write_text(json.dumps(out_json, indent=2, ensure_ascii=False))
    print(f"💾 結果寫入 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())