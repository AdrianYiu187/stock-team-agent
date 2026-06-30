"""v5.26 Stage 1 — Mock GBM vs 真實 close prices 量化。

Purpose:
    v5.26 (b) 候選量化: 量化 mock GBM (single seed=42) vs 真實 per-ticker close prices
    在 cross-market backtest 下的差異。Lesson #54 候選 — 「mock GBM 適用於技術指標
    單元測試, 但不適用於 4D 整合驗證」。

Methodology:
    1. mock GBM: generate_mock_prices(seed=42) 對所有 11 ticker 共享
    2. 真實 close prices: 從 tests/fixtures/tickers_fundamentals.json (新增 close_prices key)
       每 ticker 各自的 close prices array (length=120)
    3. 兩種 source 跑 run_cross_market_comparison(close_source=...)
    4. 量化差異: per-ticker accuracy, signal distribution, v5.10 vs v5.11.3 Δ

Usage:
    python scripts/quantify_v526_mock_vs_real_close.py
"""

import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# 確保 scripts/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_v511_multifactor import (
    generate_mock_prices,
    run_v510_backtest_path,
    run_v5113_backtest_path,
    evaluate_predictions,
    MULTIFACTOR_WEIGHTS,
)


FIXTURES_PATH = Path(__file__).resolve().parent / "tests" / "fixtures" / "tickers_fundamentals.json"


def load_fixture_close_prices() -> Optional[Dict[str, List[float]]]:
    """從 fixture 載入真實 close prices (若已存在)。"""
    if not FIXTURES_PATH.exists():
        return None
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("close_prices")


def quantify_volatility_diff() -> Dict:
    """量化 mock GBM vs 真實 ticker vol 差異。

    Mock GBM: 單一 vol = 0.02 (日) ≈ 32% 年化
    真實 ticker: AAPL ~25% / 3690.HK ~50% 年化 → 3x 差異

    Returns:
        dict 含 mock_vol_annualized, real_vol_annualized_per_ticker, ratio
    """
    mock = generate_mock_prices(n_days=120, seed=42)
    mock_daily_vol = float(np.std(np.diff(mock) / mock[:-1]))
    mock_annualized = mock_daily_vol * np.sqrt(252)

    close_prices = load_fixture_close_prices()
    real_vols = {}
    if close_prices:
        for ticker, prices in close_prices.items():
            arr = np.array(prices)
            if len(arr) > 1:
                daily_vol = float(np.std(np.diff(arr) / arr[:-1]))
                real_vols[ticker] = {
                "daily_vol": round(daily_vol, 6),
                "annualized_vol": round(daily_vol * np.sqrt(252), 4),
            }

    return {
        "mock_daily_vol": round(mock_daily_vol, 6),
        "mock_annualized_vol": round(mock_annualized, 4),
        "real_vols": real_vols,
        "vol_ratio_range": None,  # populated if real_vols not empty
    }


def quantify_per_ticker_accuracy(
    close_source: str = "mock",
    close_prices_map: Optional[Dict[str, np.ndarray]] = None,
    n_days: int = 120,
    seed: int = 42,
) -> Dict:
    """對每 ticker 跑 v5.10 vs v5.11.3 路徑, 量化 per-ticker accuracy 差異。

    Args:
        close_source: "mock" 或 "real"
        close_prices_map: real 模式必填, {ticker: np.ndarray}
    """
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        fix = json.load(f)
    tickers = list(fix["fundamentals"].keys())

    per_ticker = {}
    for ticker in tickers:
        if close_source == "real" and close_prices_map and ticker in close_prices_map:
            close = np.array(close_prices_map[ticker])
        else:
            close = generate_mock_prices(n_days=n_days, seed=seed)

        fund = fix["fundamentals"][ticker]

        v510_preds = run_v510_backtest_path(close, days=90)
        v5113_preds = run_v5113_backtest_path(
            close, days=90,
            pe=float(fund.get("pe", 25.0)),
            roe=float(fund.get("roe", 1.5)),
            peg_val=float(fund.get("peg") or 1.2),
            revenue_growth=float(fund.get("growth", 0.10)),
        )

        v510_m = evaluate_predictions(v510_preds)
        v5113_m = evaluate_predictions(v5113_preds)

        per_ticker[ticker] = {
            "v5.10_directional": round(v510_m["directional_accuracy"], 4),
            "v5.11.3_directional": round(v5113_m["directional_accuracy"], 4),
            "delta_pp": round((v5113_m["directional_accuracy"] - v510_m["directional_accuracy"]) * 100, 2),
            "v5.11.3_n_buy": v5113_m["n_buy"],
            "v5.11.3_n_sell": v5113_m["n_sell"],
            "v5.11.3_n_hold": v5113_m["n_hold"],
        }

    return per_ticker


def main():
    """Stage 1 量化主程式。"""
    print("=" * 70)
    print("v5.26 Stage 1: Mock GBM vs 真實 close prices 量化")
    print("=" * 70)

    # 1. 波動率差異
    print("\n[1] 波動率差異 (mock GBM vs 真實 ticker)")
    vol_diff = quantify_volatility_diff()
    print(f"  Mock GBM annualized vol: {vol_diff['mock_annualized_vol']*100:.1f}%")
    if vol_diff["real_vols"]:
        vols = [v["annualized_vol"] for v in vol_diff["real_vols"].values()]
        print(f"  真實 ticker annualized vol: min={min(vols)*100:.1f}% max={max(vols)*100:.1f}%")
        vol_diff["vol_ratio_range"] = round(max(vols) / min(vols), 2)
        print(f"  vol ratio (max/min): {vol_diff['vol_ratio_range']}x")
    else:
        print("  [待補] close_prices fixture 尚未建立 (v5.26 P1 待執行)")

    # 2. Per-ticker accuracy (mock source)
    print("\n[2] Mock GBM per-ticker accuracy")
    mock_per_ticker = quantify_per_ticker_accuracy(close_source="mock")
    deltas = [t["delta_pp"] for t in mock_per_ticker.values()]
    print(f"  v5.10→v5.11.3 directional_accuracy Δ: mean={statistics.mean(deltas):+.2f}pp "
          f"std={statistics.stdev(deltas):.2f}pp")

    # 3. 真實 (若 fixture 已就緒)
    real_close = load_fixture_close_prices()
    if real_close:
        real_map = {t: np.array(p) for t, p in real_close.items()}
        print("\n[3] 真實 close prices per-ticker accuracy")
        real_per_ticker = quantify_per_ticker_accuracy(
            close_source="real", close_prices_map=real_map,
        )
        real_deltas = [t["delta_pp"] for t in real_per_ticker.values()]
        print(f"  v5.10→v5.11.3 directional_accuracy Δ: mean={statistics.mean(real_deltas):+.2f}pp "
              f"std={statistics.stdev(real_deltas):.2f}pp")

        # 4. mock vs real 差異
        print("\n[4] mock vs real Δ 對比")
        for ticker in mock_per_ticker:
            mock_d = mock_per_ticker[ticker]["delta_pp"]
            real_d = real_per_ticker.get(ticker, {}).get("delta_pp", float("nan"))
            diff = real_d - mock_d
            print(f"  {ticker:12s}: mock Δ={mock_d:+.2f}pp real Δ={real_d:+.2f}pp diff={diff:+.2f}pp")
    else:
        print("\n[3] 真實 close prices 尚未建立 — 待 v5.26 P1 執行")
        print("    Stage 1 量化建立後, P1 將注入 close_prices fixture 並重跑")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()