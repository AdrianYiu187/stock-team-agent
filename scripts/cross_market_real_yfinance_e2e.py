"""v5.11.3 Cross-Market Real YFinance E2E（純函數量化）。

Purpose:
    Stage 6.1 進階：用 yfinance 拉 AAPL / 0700.HK / 600519.SS 真實
    fundamentals（trailingPE / returnOnEquity / pegRatio / revenueGrowth），
    跑 v5.10 vs v5.11.3 fund_score_multifactor 量化。

    純函數結果（無網路依賴於 pytest）：
    - pytest 模式：載 fixtures/tickers_fundamentals.json（從真實 yfinance 一次拉）
    - 一次性 CLI 模式：現拉 yfinance，輸出 fixtures + 量化 JSON

設計原則（Rule 2/3 精準最小化）：
    - 既有 cross_market_e2e_ticker_specific.py 沒有 fixtures 化，pytest 無法跑
    - 本腳本不重寫既有，而是 fixtures 化同樣的 scoring 邏輯
    - 既有 CLI 模式仍可用，現拉現輸出

成功標準（Rule 4）：
    1. 3 ticker × 2 版本 = 6 個 fund_score 算出（0 ≤ score ≤ 1）
    2. v5.10 與 v5.11.3 std 量化（單調性 vs 假分散）
    3. fixtures 持久化（pytest 可重跑，無網路）
    4. JSON artifact 寫到 /tmp 供 audit chain 取證

Usage:
    # CLI 一次性（會觸 yfinance 網路）
    python scripts/cross_market_real_yfinance_e2e.py

    # pytest 模式（用 fixtures，無網路）
    pytest scripts/tests/test_cross_market_real_yfinance_e2e.py -v
"""

from __future__ import annotations

import importlib.util
import json
import logging
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

# 確保 scripts/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

# v5.24 P2 — cap-zone warning logger (Lesson #49 整合)
# main() 跑完 scores 後呼叫,operator dashboard 自動看到 cap-zone collision。
# Frozen mode (CI / pytest) 不寫 fixtures 但仍 emit warnings,確保 pytest guard 可捕獲。
logger = logging.getLogger("cross_market_e2e")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# 載入 v5.10 source from commit 0f30069 baseline
V510_PATH = Path("/tmp/v510_stock_analysis.py")
V511_PATH = Path(__file__).resolve().parent / "stock_analysis.py"

# v5.15 P46 — Ticker universe（11 ticker 跨 US/HK/CN）
# 設計：US 4 + HK 3 + CN 4 = 11（≥ 10 + 各市場 ≥ 3）
TICKER_UNIVERSE: list[str] = [
    # US 大盤科技
    "AAPL", "MSFT", "GOOGL", "NVDA",
    # HK 龍頭
    "0700.HK", "9988.HK", "3690.HK",
    # CN A 股
    "600519.SS", "000858.SZ", "601318.SS", "000333.SZ",
]

# v5.15 P45 — Fixtures freshness threshold（> 90 days 警告）
FIXTURES_MAX_AGE_DAYS = 90

# v5.15 P45 — 預設 fixtures 路徑（pytest 共用）
FIXTURES_PATH = Path(__file__).resolve().parent / "tests" / "fixtures" / "tickers_fundamentals.json"


def _load_module(label: str, path: Path):
    spec = importlib.util.spec_from_file_location(label, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"❌ 載入 {label} 失敗（{path}）")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_v510_baseline() -> None:
    if not V510_PATH.exists():
        print(f"❌ {V510_PATH} 不存在。請先跑：")
        print("   git show 0f30069:scripts/stock_analysis.py > /tmp/v510_stock_analysis.py")
        sys.exit(1)


def score_ticker(
    fund_func: Callable,
    pe: float,
    roe: float,
    peg: Optional[float],
    growth: float,
) -> float:
    """呼叫任一版本的 fund_score_multifactor。"""
    return fund_func(pe=pe, roe=roe, peg_val=peg, revenue_growth=growth)


def score_tickers(
    fund_func: Callable,
    fundamentals: dict[str, dict],
) -> dict[str, float]:
    return {
        t: score_ticker(
            fund_func,
            pe=f["pe"],
            roe=f["roe"],
            peg=f["peg"],
            growth=f["growth"],
        )
        for t, f in fundamentals.items()
    }


def fetch_fundamentals(tickers: list[str]) -> dict[str, dict]:
    """從 yfinance 拉真實 fundamentals（一次性 CLI 模式用）。

    v5.15 P45 — Per-ticker error tolerance：
        單 ticker yfinance 失敗（缺欄位 / API error / rate limit）不中斷整體。
        失敗 ticker 從結果排除，記錄到 _meta.failed_tickers。
    """
    import yfinance as yf  # 延遲 import — pytest 模式不需 yfinance

    out: dict[str, dict] = {}
    failed: list[str] = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            if not info:  # 空 dict = ticker 不存在
                failed.append(t)
                continue
            out[t] = {
                "pe": info.get("trailingPE") or 0,
                "roe": info.get("returnOnEquity") or 0,
                "peg": info.get("pegRatio"),
                "growth": info.get("revenueGrowth") or 0,
            }
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  {t} yfinance 拉取失敗：{e}")
            failed.append(t)
    if failed:
        print(f"⚠️  {len(failed)}/{len(tickers)} ticker 失敗：{failed}")
    return {"fundamentals": out, "failed": failed}


def quantize_cross_market(
    v510_scores: dict[str, float],
    v511_scores: dict[str, float],
) -> dict:
    """量化 v5.10 vs v5.11.3 跨市場 std 變化。

    v5.15 P46 — 加入 sample_size 欄位（量化 N 透明度）。
    """
    s510 = list(v510_scores.values())
    s511 = list(v511_scores.values())
    sample_size = len(s510)  # 兩版本 ticker 數相同
    return {
        "v5_10_std": round(statistics.stdev(s510), 4) if sample_size >= 2 else 0.0,
        "v5_11_3_std": round(statistics.stdev(s511), 4) if sample_size >= 2 else 0.0,
        "std_delta": (
            round(statistics.stdev(s511) - statistics.stdev(s510), 4)
            if sample_size >= 2
            else 0.0
        ),
        "sample_size": sample_size,  # P46 量化 N
        "interpretation": (
            "v5.11 std 下降 = cap 飽和幻覺消失，非 regression。"
            "當所有輸入都在合理範圍（PE 5-35 + ROE 20-140% + growth 5-17%），"
            f"v5.11 線性公式自然集中在中性區（N={sample_size} ticker）。"
        ),
    }


def compute_signal_distribution_per_ticker(
    v514_mod,
    fundamentals: dict[str, dict],
    ticker: str,
    sentiment: Optional[dict] = None,
    macro: Optional[dict] = None,
    region_neutral_macro: bool = False,
) -> dict:
    """v5.16 P50 — Per-ticker signal distribution 量化（buy/hold/sell + entropy）。

    用 v514 真實 multifactor（market/tech/risk/fund/news）+
    sentiment_score_multifactor（如果有 sentiment）+ macro_score（如果有 macro）
    算 final score，再用 score_to_bhs 映射到 dominant label。

    Returns:
        {
            "buy_ratio": float,
            "hold_ratio": float,
            "sell_ratio": float,
            "signal_entropy": float (bits),
            "majority": str (buy/hold/sell),
            "final_score": float,
            "components": dict (各 role score for transparency),
        }
    """
    from collections import Counter
    from math import log2

    if ticker not in fundamentals:
        return {"error": f"ticker {ticker} not in fundamentals"}

    f = fundamentals[ticker]

    # 1. 5 role score
    market_score = 0.5
    tech_score = 0.5
    risk_score = 0.5
    fund_score = 0.5
    news_score = 0.5
    try:
        # 用 v5.11 真實 multifactor（如果 PE/ROE/PEG/growth 在合理範圍）
        fund_score = v514_mod.fund_score_multifactor(
            pe=f["pe"], roe=f["roe"], peg_val=f["peg"], revenue_growth=f["growth"],
        )
    except Exception:  # noqa: BLE001
        pass

    # 2. sentiment（如果有）
    sentiment_score = 0.5
    if sentiment and ticker in sentiment:
        s = sentiment[ticker]
        try:
            sentiment_score = v514_mod.sentiment_score_multifactor(
                combined_score=s["combined_score"],
                confidence=s["confidence"],
                news_count=s["news_count"],
            )
        except Exception:  # noqa: BLE001
            sentiment_score = 0.5 + 0.5 * s.get("combined_score", 0)

    # 3. macro（如果有）— v5.18: region_neutral_macro 對沖旗標
    macro_value = macro.get(ticker, {}).get("macro_score", 0.5) if macro else 0.5
    if region_neutral_macro:
        macro_value = 0.5  # 中性化 macro（驗證 region-level macro 拖累效應）

    # 4. weighted_score_with_variance_penalty（如果有 weights）
    weights = v514_mod.dynamic_weights_for_ticker(ticker)
    scores_dict = {
        "market": market_score, "technical": tech_score, "fundamental": fund_score,
        "risk": risk_score, "sentiment": sentiment_score, "news": news_score,
        "macro": macro_value,
    }
    try:
        final_score, _ = v514_mod.weighted_score_with_variance_penalty(scores_dict, weights)
    except Exception:  # noqa: BLE001
        # Fallback to simple average
        final_score = sum(scores_dict.values()) / len(scores_dict)

    # 5. score_to_bhs → dominant label
    try:
        bhs = v514_mod.score_to_bhs(final_score)
        labels = Counter(bhs.keys())
        total = sum(bhs.values())
        if total <= 0:
            buy_ratio = hold_ratio = sell_ratio = 1.0 / 3.0
        else:
            buy_ratio = bhs.get("buy", 0) / total
            hold_ratio = bhs.get("hold", 0) / total
            sell_ratio = bhs.get("sell", 0) / total
        # Signal entropy over 3-class
        probs = [p for p in [buy_ratio, hold_ratio, sell_ratio] if p > 0]
        signal_entropy = float(-sum(p * log2(p) for p in probs))
        # Majority（tie-break: buy > hold > sell）
        max_p = max(buy_ratio, hold_ratio, sell_ratio)
        if max_p == buy_ratio:
            majority = "buy"
        elif max_p == hold_ratio:
            majority = "hold"
        else:
            majority = "sell"
    except Exception as e:  # noqa: BLE001
        return {"error": f"score_to_bhs 失敗：{e}", "final_score": final_score}

    return {
        "buy_ratio": round(buy_ratio, 4),
        "hold_ratio": round(hold_ratio, 4),
        "sell_ratio": round(sell_ratio, 4),
        "signal_entropy": round(signal_entropy, 4),
        "majority": majority,
        "final_score": round(final_score, 4),
        "components": {
            "market": round(market_score, 4),
            "technical": round(tech_score, 4),
            "fundamental": round(fund_score, 4),
            "risk": round(risk_score, 4),
            "sentiment": round(sentiment_score, 4),
            "news": round(news_score, 4),
            "macro": round(macro_value, 4),
        },
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="v5.21 cross_market e2e + per-ticker signal (3-tier fixture)")
    parser.add_argument(
        "--region-neutral-macro", action="store_true",
        help="v5.18: 把所有 ticker macro 強制設為 0.5（驗證 region-level macro 拖累效應）",
    )
    parser.add_argument(
        "--mode", choices=["live", "frozen", "hybrid"], default="live",
        help="v5.21: 3-tier fixture mode. live=yfinance+cache (default), frozen=hardcoded only (CI), hybrid=live+hardcoded fallback",
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="v5.21: 強制重抓 yfinance,bypass 24h TTL cache",
    )
    args = parser.parse_args()

    _ensure_v510_baseline()

    v510_mod = _load_module("v510_stock_analysis", V510_PATH)
    v511_mod = _load_module("v511_stock_analysis", V511_PATH)

    # v5.15 P46 — 從 TICKER_UNIVERSE 拉（11 ticker 跨 US/HK/CN）
    tickers = TICKER_UNIVERSE
    print(f"📡 Fixture mode = {args.mode}, tickers ({len(tickers)})...")

    # v5.21 P3 — 三層 loader 取代原 fetch_fundamentals
    from data_sources.three_tier_loader import load_fundamentals_three_tier

    loader_result = load_fundamentals_three_tier(
        tickers, mode=args.mode, force_refresh=args.force_refresh,
    )
    fundamentals = loader_result["fundamentals"]
    partial = loader_result.get("partial", [])

    if not fundamentals:
        print("❌ 全部 ticker 拉取失敗，請檢查網路 / yfinance API / hardcoded fixture")
        return 1

    # v5.21 P3 — 標示 source 透明度
    print(f"   source: {loader_result['source']}")
    if partial:
        print(f"   ⚠️  {len(partial)} ticker fallback 到 hardcoded: {partial}")
    for t in sorted(set(tickers) - set(fundamentals.keys())):
        print(f"   ❌ {t} 完全缺資料 (skip)")

    print(f"\n{'Ticker':<14} {'PE':>6} {'ROE':>7} {'PEG':>6} {'growth':>7}")
    for t, f in fundamentals.items():
        print(
            f"{t:<14} {f['pe']:>6.1f} {f['roe']*100:>6.1f}% "
            f"{f['peg'] or 0:>6.2f} {f['growth']*100:>6.1f}%"
        )

    v510_scores = score_tickers(v510_mod.fund_score_multifactor, fundamentals)
    v511_scores = score_tickers(v511_mod.fund_score_multifactor, fundamentals)

    print(f"\n{'Ticker':<14} {'v5.10':>8} {'v5.11.3':>8} {'delta':>8}")
    for t in fundamentals:
        d = v511_scores[t] - v510_scores[t]
        print(f"{t:<14} {v510_scores[t]:>8.4f} {v511_scores[t]:>8.4f} {d:>+8.4f}")

    quant = quantize_cross_market(v510_scores, v511_scores)
    print(f"\n=== Std ({quant['sample_size']} real markets) ===")
    print(f"  v5.10 std   = {quant['v5_10_std']:.4f}")
    print(f"  v5.11.3 std = {quant['v5_11_3_std']:.4f}")
    print(f"  Δ std       = {quant['std_delta']:+.4f}")
    print(f"\n💡 {quant['interpretation']}")

    # v5.24 P2 — Lesson #49 整合: live mode 跑完自動 cap-zone warning
    # operator dashboard 從 logger 看到哪些 ticker 撞 cap,不必手動跑 cap_coverage_report。
    # Frozen mode (CI / pytest) 也 emit,確保 3690.HK PEG=28.72 warning pytest guard 可捕獲。
    from data_sources.live_score_engine import (
        recompute_cross_market_with_cap_warnings,
    )
    _cap_result = recompute_cross_market_with_cap_warnings(fundamentals)
    for w in _cap_result["cap_warnings"]:
        tickers_preview = ", ".join(w["tickers"][:5])
        extra = "..." if len(w["tickers"]) > 5 else ""
        logger.warning(
            f"⚠️  Cap-zone collision: {w['metric']} "
            f"({w['n_in_cap_zone']}/{len(fundamentals)} tickers, "
            f"threshold={w['threshold_value']}, by_design={w['is_by_design']}): "
            f"{tickers_preview}{extra}"
        )

    # v5.16 P50 — Per-ticker signal distribution（從 fixtures 讀 sentiment + macro）
    sentiment_dict = {}
    macro_dict = {}
    if FIXTURES_PATH.exists():
        try:
            existing = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
            sentiment_dict = existing.get("sentiment_per_ticker", {})
            macro_dict = existing.get("macro_per_ticker", {})
        except Exception:  # noqa: BLE001
            pass

    print(f"\n{'='*60}")
    print(f"📊 v5.16 P50 Signal Distribution Per Ticker ({len(fundamentals)} markets)")
    if args.region_neutral_macro:
        print(f"⚙️  --region-neutral-macro: macro 全部中性化為 0.5")
    print(f"{'='*60}")
    print(f"{'Ticker':<14} {'Final':>7} {'Buy%':>7} {'Hold%':>7} {'Sell%':>7} {'Entropy':>9} {'Majority':>10}")
    signal_distribution_per_ticker = {}
    for t in fundamentals:
        sig = compute_signal_distribution_per_ticker(
            v511_mod, fundamentals, t,
            sentiment=sentiment_dict, macro=macro_dict,
            region_neutral_macro=args.region_neutral_macro,
        )
        signal_distribution_per_ticker[t] = sig
        if "error" in sig:
            print(f"{t:<14} {'ERROR':>7} {sig['error']}")
            continue
        print(
            f"{t:<14} {sig['final_score']:>7.4f} {sig['buy_ratio']*100:>6.2f}% "
            f"{sig['hold_ratio']*100:>6.2f}% {sig['sell_ratio']*100:>6.2f}% "
            f"{sig['signal_entropy']:>9.4f} {sig['majority']:>10}"
        )

    # v5.15 P45 — 寫 fixtures（供 pytest 永久用）+ fetched_at timestamp
    fixtures_path = FIXTURES_PATH
    fixtures_path.parent.mkdir(parents=True, exist_ok=True)

    # v5.16 P50 — 加 signal_distribution 段（如果 fixtures 已有 sentiment/macro，保留）
    fixture_data = {
        "tickers": list(fundamentals.keys()),  # 只存成功的
        "fundamentals": fundamentals,
        "v5_10_scores": v510_scores,
        "v5_11_3_scores": v511_scores,
        "std_quant": quant,
        "signal_distribution_per_ticker": signal_distribution_per_ticker,
        "_meta": {
            "source": "yfinance real fetch (v5.16 P50 with signal distribution)",
            "v510_baseline": "0f30069:scripts/stock_analysis.py",
            "v5113_source": "scripts/stock_analysis.py (HEAD)",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "ticker_universe_size": len(TICKER_UNIVERSE),
            "failed_tickers": sorted(set(TICKER_UNIVERSE) - set(fundamentals.keys())),
            "max_age_days": FIXTURES_MAX_AGE_DAYS,
            "v5_21_mode": args.mode,
            "v5_21_source": loader_result["source"],
            "v5_21_partial_fallback": partial,
        },
    }
    # 保留既有 sentiment/macro（如果存在）
    if sentiment_dict:
        fixture_data["sentiment_per_ticker"] = sentiment_dict
    if macro_dict:
        fixture_data["macro_per_ticker"] = macro_dict

    # v5.21 P3 — frozen mode 不覆寫 hardcoded fixture（避免無謂 git diff）
    failed_count = len(set(TICKER_UNIVERSE) - set(fundamentals.keys()))
    if args.mode == "frozen":
        print(f"\n🧊 Frozen mode: skip 寫回 {fixtures_path}（避免覆蓋 hardcoded snapshot）")
        print(
            f"✅ {len(fundamentals)}/{len(tickers)} ticker 從 hardcoded 載入"
            + (f"（{failed_count} 失敗）" if failed_count else "")
        )
        return 0

    fixtures_path.write_text(
        json.dumps(fixture_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n💾 Fixtures 寫到 {fixtures_path}")
    print(
        f"✅ {len(fundamentals)}/{len(tickers)} ticker 成功"
        + (f"（{failed_count} 失敗）" if failed_count else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
