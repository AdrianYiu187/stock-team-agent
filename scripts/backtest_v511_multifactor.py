"""v5.11.3 Stage 7: Backtest integration with 4 multifactor scoring.

Purpose:
    把 backtest 從「只用技術指標 (generate_signal_score)」升級到「4 維度
    multifactor 整合」(market/tech/fund/risk)，量化 v5.11.3 對 overall_accuracy
    / directional_accuracy / precision_buy/sell 的實際影響。

設計原則（Rule 2 最小代碼）:
- 不改 backtest_engine.py（向後相容）
- 複用 generate_signal_score 技術訊號 + 加 4 multifactor 加權層
- 純函數、無 yfinance 網路依賴（用 numpy mock close array）
- 對比 v5.10 (技術 only) vs v5.11.3 (4-multifactor) 兩條路徑

為什麼 mock 數據？
- hermes-stale-reminder-handling skill 強調 reproducibility
- 真實 yfinance 數據會隨時間漂移，量化結果無法 git diff
- mock 數據用 deterministic seed，重跑結果 100% 一致

量化指標（Rule 4 成功標準）:
1. overall_accuracy: 整體（含 HOLD）
2. directional_accuracy: 去掉 HOLD 後的方向準確率
3. precision_buy / precision_sell: 各信號精準度
4. signal_distribution: BUY/HOLD/SELL 分布變化

Usage:
    python scripts/backtest_v511_multifactor.py
    pytest scripts/tests/test_backtest_v511_multifactor.py -v
"""

import importlib.util
import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

# 確保 scripts/ 在 path 中（import stock_analysis 與 backtest_engine）
sys.path.insert(0, str(Path(__file__).resolve().parent))

# === 載入 4 個 multifactor ===
from stock_analysis import (
    fund_score_multifactor,
    market_score_multifactor,
    risk_score_multifactor,
    tech_score_multifactor,
)

# === 載入既有 backtest 函數（技術指標計算 + 技術信號） ===
from backtest_engine import (
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    generate_signal_score,
)

# === 載入 v5.10 baseline（技術 only 信號）做對照組 ===
V510_PATH = Path("/tmp/v510_backtest_engine.py")
if V510_PATH.exists():
    spec = importlib.util.spec_from_file_location("v510_bt", str(V510_PATH))
    if spec is not None and spec.loader is not None:
        v510_bt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v510_bt)
    else:
        v510_bt = None
else:
    v510_bt = None


# ============================================================================
# Mock 數據生成（無網路依賴，deterministic）
# ============================================================================

def generate_mock_prices(
    n_days: int = 120,
    seed: int = 42,
    start_price: float = 150.0,
    drift: float = 0.0005,
    volatility: float = 0.02,
) -> np.ndarray:
    """生成 deterministic mock close prices（geometric Brownian motion）。

    為什麼用 GBM？
    - 模擬真實股票走勢（mean-reverting drift + random walk）
    - 固定 seed → 重跑結果 100% 一致
    - 無 yfinance 網路依賴，pytest 0 flake

    參數:
        n_days: 模擬天數（預設 120 = backtest 90 + 指標預熱 30）
        seed: random seed（保證 reproducible）
        start_price: 起始價
        drift: 日均 drift（0.0005 ≈ +12% 年化）
        volatility: 日波動率（0.02 ≈ 32% 年化）

    返回:
        close prices array (length n_days)
    """
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=drift, scale=volatility, size=n_days)
    prices = start_price * np.cumprod(1 + returns)
    return prices


# ============================================================================
# 4 維度 multifactor 整合（v5.11.3 路徑）
# ============================================================================

# 4 維度權重（總和 = 1.0）
# 設計：技術 0.35 + 基本面 0.30 + 市場 0.20 + 風險 0.15
# 理由：技術 + 基本面是預測核心；市場 + 風險是 filter
MULTIFACTOR_WEIGHTS = {
    "tech": 0.35,
    "fund": 0.30,
    "market": 0.20,
    "risk": 0.15,
}


def compute_dynamic_market_params(close: np.ndarray, i: int, lookback_52w: int = 252) -> Tuple[float, float, float]:
    """從 close array 動態計算 market_score 3 個時間序列參數。

    為什麼動態計算？
    - market_score_multifactor 輸入若全為常數 → score 每天相同 → composite
      變動只靠 tech，誤導結論
    - 真實世界 ytd_return / pos_52wk / from_high_pct 每日不同，必須從
      close array 算出來

    參數:
        close: 價格陣列
        i: 當前索引
        lookback_52w: 52 週 = 252 交易日

    返回:
        (ytd_return%, pos_52wk%, from_high_pct%) 三元組
    """
    # ytd_return: 假設 1 年前 = 252 個交易日
    if i >= lookback_52w and close[i - lookback_52w] > 0:
        ytd_return = (close[i] - close[i - lookback_52w]) / close[i - lookback_52w] * 100
    else:
        ytd_return = 0.0

    # pos_52wk + from_high_pct: 過去 252 日區間
    window = close[max(0, i - lookback_52w + 1):i + 1]
    low_52w = float(np.min(window)) if len(window) > 0 else float(close[i])
    high_52w = float(np.max(window)) if len(window) > 0 else float(close[i])

    if high_52w > low_52w:
        pos_52wk = (close[i] - low_52w) / (high_52w - low_52w) * 100
    else:
        pos_52wk = 50.0

    if high_52w > 0:
        from_high_pct = (close[i] - high_52w) / high_52w * 100
    else:
        from_high_pct = 0.0

    return float(ytd_return), float(pos_52wk), float(from_high_pct)


def compute_4d_multifactor(
    close: np.ndarray,
    i: int,
    sma_50_arr: np.ndarray,
    rsi_arr: np.ndarray,
    macd_hist_arr: np.ndarray,
    momentum_20d_arr: np.ndarray,
    pe: float = 25.0,
    roe: float = 1.5,
    peg_val: float = 1.2,
    revenue_growth: float = 0.10,
    volatility: float = 30.0,
    var_95: float = -2.5,
    max_dd: float = -20.0,
    sharpe: float = 1.0,
    beta: float = 1.1,
) -> Dict[str, float]:
    """計算第 i 日的 4 維度 multifactor 分數。

    設計：除技術指標從 close array 計算外，其餘輸入用 mock fundamental/risk
    參數（這是 backtest 整合層，yfinance 拉真實 PE/ROE 是 cross-market 階段
    的工作，本腳本專注於 backtest pipeline 整合）。

    返回:
        {"tech": 0.55, "fund": 0.62, "market": 0.48, "risk": 0.70,
         "composite": 0.58}
    """
    tech_score = tech_score_multifactor(
        rsi=float(rsi_arr[i]),
        macd_val=float(macd_hist_arr[i]),
        price=float(close[i]),
        ma50=float(sma_50_arr[i]),
        momentum_20d=float(momentum_20d_arr[i]),
    )

    fund_score = fund_score_multifactor(
        pe=pe,
        roe=roe,
        peg_val=peg_val,
        revenue_growth=revenue_growth,
    )

    ytd_return, pos_52wk, from_high_pct = compute_dynamic_market_params(close, i)
    market_score = market_score_multifactor(
        ytd_return=ytd_return,
        pos_52wk=pos_52wk,
        from_high_pct=from_high_pct,
        beta=beta,
    )

    risk_score = risk_score_multifactor(
        volatility=volatility,
        var_95=var_95,
        max_dd=max_dd,
        sharpe=sharpe,
    )

    composite = (
        tech_score * MULTIFACTOR_WEIGHTS["tech"]
        + fund_score * MULTIFACTOR_WEIGHTS["fund"]
        + market_score * MULTIFACTOR_WEIGHTS["market"]
        + risk_score * MULTIFACTOR_WEIGHTS["risk"]
    )

    return {
        "tech": tech_score,
        "fund": fund_score,
        "market": market_score,
        "risk": risk_score,
        "composite": round(composite, 4),
    }


def composite_to_signal(composite: float) -> str:
    """綜合分數 → BUY/HOLD/SELL 信號。

    設計:
    - composite > 0.58 → BUY（4 維度都中性偏上）
    - composite < 0.45 → SELL（4 維度都中性偏下）
    - 其餘 → HOLD
    """
    if composite > 0.58:
        return "BUY"
    elif composite < 0.45:
        return "SELL"
    return "HOLD"


# ============================================================================
# Backtest pipeline（v5.10 vs v5.11.3 量化對比）
# ============================================================================

def run_v510_backtest_path(close: np.ndarray, days: int = 90) -> List[Dict]:
    """v5.10 路徑：只用 generate_signal_score（純技術指標）。

    返回每日預測 dict list（與 backtest_engine.run_backtest 同結構）。
    """
    sma_20 = calculate_sma(close, 20)
    sma_60 = calculate_sma(close, 60)
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, macd_hist = calculate_macd(close)

    predictions = []
    lookback = 70
    for i in range(lookback, len(close) - 1):
        if np.isnan(sma_60[i]):
            continue
        score = generate_signal_score(
            close=float(close[i]),
            sma_20=float(sma_20[i]),
            sma_60=float(sma_60[i]),
            rsi=float(rsi[i]),
            macd_hist=float(macd_hist[i]),
            bb_position=50.0,  # mock（避免 BB 計算複雜化）
            atr=0.0,
            prev_close=float(close[i - 1]),
        )
        predictions.append({
            "i": i,
            "close": close[i],
            "next_close": close[i + 1],
            "signal": score["signal"],
            "composite": score["buy_strength"],  # 用 buy_strength 當 v5.10 數值 proxy
        })
    return predictions


def run_v5113_backtest_path(close: np.ndarray, days: int = 90) -> List[Dict]:
    """v5.11.3 路徑：4 維度 multifactor 整合。

    返回每日預測 dict list（含 4 維度分數 + composite + signal）。
    """
    sma_50 = calculate_sma(close, 50)
    rsi = calculate_rsi(close, 14)
    macd_line, signal_line, macd_hist = calculate_macd(close)

    # 20 日動量
    momentum_20d = np.zeros_like(close)
    for i in range(20, len(close)):
        momentum_20d[i] = (close[i] - close[i - 20]) / close[i - 20] * 100

    predictions = []
    lookback = 70
    for i in range(lookback, len(close) - 1):
        if np.isnan(sma_50[i]):
            continue
        scores = compute_4d_multifactor(
            close=close, i=i,
            sma_50_arr=sma_50, rsi_arr=rsi, macd_hist_arr=macd_hist,
            momentum_20d_arr=momentum_20d,
        )
        predictions.append({
            "i": i,
            "close": close[i],
            "next_close": close[i + 1],
            "tech": scores["tech"],
            "fund": scores["fund"],
            "market": scores["market"],
            "risk": scores["risk"],
            "composite": scores["composite"],
            "signal": composite_to_signal(scores["composite"]),
        })
    return predictions


def evaluate_predictions(predictions: List[Dict]) -> Dict[str, float]:
    """計算 backtest 指標（與 backtest_engine.run_backtest 對齊）。

    正確性邏輯（v5.7 修復後）:
    - BUY 預測對：明日漲 OR 實際變動 < ±0.5%
    - SELL 預測對：明日跌 OR 實際變動 < ±0.5%
    - HOLD 預測對：明日變動 < ±0.5%
    """
    if not predictions:
        return {
            "overall_accuracy": 0.0, "directional_accuracy": 0.0,
            "precision_buy": 0.0, "precision_sell": 0.0, "precision_hold": 0.0,
            "n_total": 0, "n_buy": 0, "n_sell": 0, "n_hold": 0,
        }

    n_total = len(predictions)
    correct_total = 0
    correct_buy = correct_sell = correct_hold = 0
    n_buy = n_sell = n_hold = 0
    correct_directional = 0
    n_directional = 0

    for p in predictions:
        change = p["next_close"] - p["close"]
        pct = abs(change / p["close"]) if p["close"] > 0 else 0
        direction = "UP" if change > 0 else "DOWN"

        if p["signal"] == "BUY":
            n_buy += 1
            n_directional += 1
            ok = (direction == "UP") or (pct < 0.005)
        elif p["signal"] == "SELL":
            n_sell += 1
            n_directional += 1
            ok = (direction == "DOWN") or (pct < 0.005)
        else:
            n_hold += 1
            ok = pct < 0.005

        if ok:
            correct_total += 1
            if p["signal"] == "BUY":
                correct_buy += 1
                correct_directional += 1
            elif p["signal"] == "SELL":
                correct_sell += 1
                correct_directional += 1
            elif p["signal"] == "HOLD":
                correct_hold += 1

    return {
        "overall_accuracy": correct_total / n_total,
        "directional_accuracy": correct_directional / n_directional if n_directional > 0 else 0.0,
        "precision_buy": correct_buy / n_buy if n_buy > 0 else 0.0,
        "precision_sell": correct_sell / n_sell if n_sell > 0 else 0.0,
        "precision_hold": correct_hold / n_hold if n_hold > 0 else 0.0,
        "n_total": n_total,
        "n_buy": n_buy, "n_sell": n_sell, "n_hold": n_hold,
    }


def run_comparison(
    n_days: int = 120,
    seed: int = 42,
) -> Dict:
    """v5.10 vs v5.11.3 backtest 量化對比。

    Returns:
        dict 含 v5.10 與 v5.11.3 兩條路徑的 metrics + 改善幅度
    """
    close = generate_mock_prices(n_days=n_days, seed=seed)

    # v5.10 路徑
    v510_preds = run_v510_backtest_path(close, days=90)
    v510_metrics = evaluate_predictions(v510_preds)

    # v5.11.3 路徑
    v5113_preds = run_v5113_backtest_path(close, days=90)
    v5113_metrics = evaluate_predictions(v5113_preds)

    # 改善幅度（v5.11.3 - v5.10，pp = percentage points）
    improvement = {
        k: round(v5113_metrics[k] - v510_metrics[k], 4)
        for k in ["overall_accuracy", "directional_accuracy",
                  "precision_buy", "precision_sell"]
    }

    # 信號分布變化
    v510_dist = {
        "buy_pct": v510_metrics["n_buy"] / v510_metrics["n_total"] if v510_metrics["n_total"] else 0,
        "sell_pct": v510_metrics["n_sell"] / v510_metrics["n_total"] if v510_metrics["n_total"] else 0,
        "hold_pct": v510_metrics["n_hold"] / v510_metrics["n_total"] if v510_metrics["n_total"] else 0,
    }
    v5113_dist = {
        "buy_pct": v5113_metrics["n_buy"] / v5113_metrics["n_total"] if v5113_metrics["n_total"] else 0,
        "sell_pct": v5113_metrics["n_sell"] / v5113_metrics["n_total"] if v5113_metrics["n_total"] else 0,
        "hold_pct": v5113_metrics["n_hold"] / v5113_metrics["n_total"] if v5113_metrics["n_total"] else 0,
    }

    # 4 維度分數 std（量化 multifactor 分散度）
    composite_std = statistics.stdev([p["composite"] for p in v5113_preds]) if len(v5113_preds) > 1 else 0.0
    tech_std = statistics.stdev([p["tech"] for p in v5113_preds]) if len(v5113_preds) > 1 else 0.0
    fund_std = statistics.stdev([p["fund"] for p in v5113_preds]) if len(v5113_preds) > 1 else 0.0
    market_std = statistics.stdev([p["market"] for p in v5113_preds]) if len(v5113_preds) > 1 else 0.0
    risk_std = statistics.stdev([p["risk"] for p in v5113_preds]) if len(v5113_preds) > 1 else 0.0

    return {
        "config": {
            "n_days": n_days, "seed": seed,
            "weights": MULTIFACTOR_WEIGHTS,
        },
        "v5.10": {
            "metrics": v510_metrics,
            "signal_distribution": v510_dist,
        },
        "v5.11.3": {
            "metrics": v5113_metrics,
            "signal_distribution": v5113_dist,
            "4d_std": {
                "tech": round(tech_std, 4),
                "fund": round(fund_std, 4),
                "market": round(market_std, 4),
                "risk": round(risk_std, 4),
                "composite": round(composite_std, 4),
            },
        },
        "improvement_v5.11.3_over_v5.10_pp": improvement,
    }


def print_report(result: Dict) -> None:
    """格式化輸出量化對比報告。"""
    v510 = result["v5.10"]["metrics"]
    v5113 = result["v5.11.3"]["metrics"]
    imp = result["improvement_v5.11.3_over_v5.10_pp"]

    print("\n" + "=" * 70)
    print("v5.11.3 Stage 7: Backtest 4-Multifactor 整合量化")
    print("=" * 70)
    print(f"Config: n_days={result['config']['n_days']}, "
          f"seed={result['config']['seed']}")
    print(f"Weights: {result['config']['weights']}")
    print()
    print(f"{'指標':<25} {'v5.10 (技術 only)':<20} {'v5.11.3 (4D)':<15} {'改善 (pp)':<10}")
    print("-" * 70)
    for k, label in [
        ("overall_accuracy", "Overall Accuracy"),
        ("directional_accuracy", "Directional Accuracy"),
        ("precision_buy", "Precision Buy"),
        ("precision_sell", "Precision Sell"),
    ]:
        print(f"{label:<25} {v510[k]:<20.4f} {v5113[k]:<15.4f} {imp[k]:+.4f}")
    print()
    print(f"v5.10 信號分布: buy={result['v5.10']['signal_distribution']['buy_pct']:.1%}, "
          f"sell={result['v5.10']['signal_distribution']['sell_pct']:.1%}, "
          f"hold={result['v5.10']['signal_distribution']['hold_pct']:.1%}")
    print(f"v5.11.3 信號分布: buy={result['v5.11.3']['signal_distribution']['buy_pct']:.1%}, "
          f"sell={result['v5.11.3']['signal_distribution']['sell_pct']:.1%}, "
          f"hold={result['v5.11.3']['signal_distribution']['hold_pct']:.1%}")
    print()
    std = result["v5.11.3"]["4d_std"]
    print(f"4D 分數 std: tech={std['tech']:.4f}, fund={std['fund']:.4f}, "
          f"market={std['market']:.4f}, risk={std['risk']:.4f}, "
          f"composite={std['composite']:.4f}")
    print("=" * 70)


# ============================================================================
# 主程式
# ============================================================================

if __name__ == "__main__":
    result = run_comparison(n_days=120, seed=42)
    print_report(result)

    # 輸出 JSON 報告到 ~/.hermes/stock_backtest/
    output_dir = Path.home() / ".hermes" / "stock_backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"v5113_multifactor_backtest_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n[完成] JSON 報告已存: {output_file}")
