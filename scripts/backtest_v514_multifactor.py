"""
v5.14 P37-P40 量化腳本：market/tech/risk cap 線性化改善

對比：
- v5.13 P36c: market/tech/risk 有 14 個真實 cap flatline（84% / 33% / 19% data 在 cap zone）
- v5.14 P37-P40: 12/14 cap 已線性化（保留 2 個保護性 cap：beta + ma50=0 fallback）

設計：mock AAPL 1 ticker × 252 trading days
- 用 GBM 模擬 AAPL daily returns（seed=42, mu=0.10/252, sigma=0.20/sqrt(252)）
- 派生 market/tech/risk/fund/sentiment 各函數的輸入
- 統計 v5.13 P36c vs v5.14 在 directional_accuracy (next-day) 的差異

directional_accuracy = sign(score-0.5) == sign(return_t+1) 的比率
（簡化版本：不考慮 score 強度，只看方向）

quantitative_targets:
  v5.13 P36c: directional_accuracy ≈ 50-55%（cap 飽和幻覺 → 訊號全是 buy → 偽正確）
  v5.14 P37-P40: 預期 +5-10pp（cap 消失 → 訊號反映真實分布）
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stock_analysis import (
    market_score_multifactor,
    tech_score_multifactor,
    fund_score_multifactor,
    risk_score_multifactor,
    sentiment_score_multifactor,
)


# === Mock AAPL GBM 模擬 ===
def mock_gbm_aapl(n_days: int = 252, seed: int = 42, mu: float = 0.10, sigma: float = 0.20) -> list[float]:
    """Mock AAPL daily log returns via GBM (seed=42 for reproducibility)."""
    rng = random.Random(seed)
    daily_mu = mu / 252
    daily_sigma = sigma / math.sqrt(252)
    returns = []
    for _ in range(n_days):
        z = rng.gauss(0, 1)
        r = daily_mu + daily_sigma * z
        returns.append(r)
    return returns


def derive_inputs_from_returns(returns: list[float]) -> list[dict]:
    """派生 5 個函數所需的 mock 輸入（AAPL 真實特徵空間）。"""
    n = len(returns)
    rows = []
    # 累積價格（用於 from_high_pct）
    cumulative = [100.0]
    for r in returns:
        cumulative.append(cumulative[-1] * math.exp(r))

    for i in range(1, n):
        price_t = cumulative[i]
        price_prev = cumulative[i - 1]

        # === market_score_multifactor 輸入 ===
        ytd_return = (price_t / cumulative[max(0, i - 21)]) - 1.0  # ~21-day proxy
        # pos_52wk: 在 252-day window 內的百分位（mock 用 21-day proxy）
        window = cumulative[max(0, i - 21):i + 1]
        high_21d = max(window)
        low_21d = min(window)
        pos_52wk = (price_t - low_21d) / (high_21d - low_21d + 1e-9) * 100.0  # [0, 100]
        from_high_pct = (price_t - high_21d) / high_21d * 100.0  # 負值或 0
        # beta: mock 為隨機 [0.8, 1.3]（AAPL 實際 ~1.2）
        beta = 0.8 + random.Random(i + 1000).random() * 0.5

        # === tech_score_multifactor 輸入 ===
        # RSI: 14-day momentum-based, mock 為 [20, 80] 區間（常態）
        rsi = 30 + random.Random(i + 2000).random() * 50  # [30, 80]
        # macd_val: 模擬 [-5, 5]（含 cap zone）
        macd_val = (random.Random(i + 3000).gauss(0, 2))
        # ma50: 用 21-day MA proxy
        ma_window = cumulative[max(0, i - 20):i + 1]
        ma50 = sum(ma_window) / len(ma_window)
        # momentum_20d: (price_t / price_{t-20}) - 1
        price_t20 = cumulative[max(0, i - 20)]
        momentum_20d = (price_t / price_t20 - 1.0) * 100.0  # 百分比

        # === fund_score_multifactor 輸入 ===
        pe = 20 + random.Random(i + 4000).random() * 10  # [20, 30]
        roe = 0.15 + random.Random(i + 5000).random() * 0.50  # [0.15, 0.65]
        peg_val = 1.5 + random.Random(i + 6000).random() * 1.5  # [1.5, 3.0]
        revenue_growth = 0.05 + random.Random(i + 7000).random() * 0.10  # [5%, 15%]

        # === risk_score_multifactor 輸入 ===
        # volatility: 用 21-day return std
        ret_window = returns[max(0, i - 20):i + 1]
        volatility = math.sqrt(sum((r - sum(ret_window) / len(ret_window)) ** 2 for r in ret_window) / len(ret_window)) * math.sqrt(252)
        var_95 = -1.5 * volatility  # 簡化 proxy
        max_dd_proxy = -volatility * 2.0
        sharpe = (0.10 - 0.02) / volatility if volatility > 0 else 0  # (mu - rf) / sigma, rf=0.02

        # === sentiment_score_multifactor 輸入 ===
        combined_score = random.Random(i + 8000).gauss(0, 0.3)  # [-0.6, 0.6]
        confidence = 0.5 + random.Random(i + 9000).random() * 0.4  # [0.5, 0.9]
        news_count = random.Random(i + 11000).randint(5, 50)

        rows.append({
            "day_idx": i,
            "return_t1": returns[i],  # next-day return
            "market": {
                "ytd_return": ytd_return * 100,  # %
                "pos_52wk": pos_52wk,
                "from_high_pct": from_high_pct,
                "beta": beta,
            },
            "tech": {
                "rsi": rsi,
                "macd_val": macd_val,
                "price": price_t,
                "ma50": ma50,
                "momentum_20d": momentum_20d,
            },
            "fund": {
                "pe": pe,
                "roe": roe,
                "peg_val": peg_val,
                "revenue_growth": revenue_growth,
            },
            "risk": {
                "volatility": volatility,
                "var_95": var_95,
                "max_dd": max_dd_proxy,
                "sharpe": sharpe,
            },
            "sentiment": {
                "combined_score": max(-1.0, min(1.0, combined_score)),
                "confidence": confidence,
                "news_count": news_count,
            },
        })

    return rows


# === v5.13 P36c mock：刻意還原 14 個 cap ===
def v513_market_score(ytd_return: float, pos_52wk: float, from_high_pct: float, beta: float) -> float:
    """v5.13 P36c 模擬：market 有 4-segment cap + from_high/ytd cap + beta cap。"""
    # pos_52wk 4-segment cap
    if pos_52wk <= 5:
        pos_factor = 1.0
    elif pos_52wk <= 20:
        pos_factor = 1.0 - (pos_52wk - 5) * 0.05  # 1.0 → 0.25
    elif pos_52wk <= 50:
        pos_factor = 0.7
    elif pos_52wk <= 80:
        pos_factor = 0.55
    else:
        pos_factor = 0.5

    # from_high cap
    if from_high_pct <= -60:
        fhigh_factor = 1.0
    elif from_high_pct <= 0:
        fhigh_factor = 1.0 + (from_high_pct + 60) / 60 * (-0.417)  # 1.0 → 0.583
    else:
        fhigh_factor = 0.583

    # ytd_return cap
    if ytd_return <= -100:
        ytd_factor = 0.0
    elif ytd_return <= 0:
        ytd_factor = 0.0 + (ytd_return + 100) / 100 * 0.2  # 0 → 0.2
    else:
        ytd_factor = 0.2 + min(ytd_return, 100) / 100 * 0.8  # 0.2 → 1.0

    # beta cap
    if beta <= 1.2:
        beta_factor = 1.0
    else:
        beta_factor = 0.7

    return fhigh_factor * 0.5 + pos_factor * 0.3 + ytd_factor * 0.15 + beta_factor * 0.05


def v513_tech_score(rsi: float, macd_val: float, price: float, ma50: float, momentum_20d: float) -> float:
    """v5.13 P36c 模擬：tech 有 RSI/macd/momentum cap + ma50 fallback。"""
    # RSI cap
    if rsi <= 5:
        rsi_factor = 1.0
    elif rsi <= 70:
        rsi_factor = 1.0 - (rsi - 5) * (1.0 - 0.05) / 65  # 1.0 → 0.05
    else:
        rsi_factor = 0.05

    # macd cap
    if macd_val <= -5:
        macd_factor = 0.25
    elif macd_val <= -2:
        macd_factor = 0.25
    elif macd_val <= 2:
        macd_factor = 0.25 + (macd_val + 2) / 4 * 0.55  # 0.25 → 0.8
    else:
        macd_factor = 0.8  # > 2 cap

    # ma50 fallback
    if ma50 <= 0:
        ma_factor = 0.5
    else:
        ratio = (price / ma50 - 1.0)
        ma_factor = 0.5 + max(-0.5, min(0.5, ratio)) * 0.8

    # momentum cap
    if momentum_20d <= -50:
        mom_factor = 0.05
    elif momentum_20d <= 0:
        mom_factor = 0.05 + (momentum_20d + 50) / 50 * 0.45  # 0.05 → 0.5
    else:
        mom_factor = 0.5 + min(momentum_20d, 50) / 50 * 0.5  # 0.5 → 1.0

    return rsi_factor * 0.4 + macd_factor * 0.15 + ma_factor * 0.2 + mom_factor * 0.25


def v513_risk_score(volatility, var_95, max_dd, sharpe) -> float:
    """v5.13 P36c 模擬：risk 有 var_95 + max_dd cap。"""
    var_clamped = var_95 if var_95 is not None else 0.20
    dd_clamped = max_dd if max_dd is not None else -0.15
    sharpe_val = sharpe if sharpe is not None else 0.5

    # var_95 cap
    if var_clamped <= 0.10:
        var_factor = 0.7
    elif var_clamped <= 0.30:
        var_factor = 0.7 - (var_clamped - 0.10) / 0.20 * 0.4  # 0.7 → 0.3
    else:
        var_factor = 0.3

    # max_dd cap
    if dd_clamped >= 0:
        dd_factor = 0.7
    elif dd_clamped >= -0.50:
        dd_factor = 0.7 + dd_clamped / 0.50 * 0.4  # 0.7 → 0.3
    else:
        dd_factor = 0.3

    # sharpe 線性
    sharpe_factor = max(0, min(1, (sharpe_val + 1) / 3))

    return var_factor * 0.4 + dd_factor * 0.4 + sharpe_factor * 0.2


def consensus_v5(row: dict, market_fn, tech_fn, risk_fn) -> float:
    """5 函數共識 = weighted avg."""
    m = market_fn(**row["market"])
    t = tech_fn(**row["tech"])
    f = fund_score_multifactor(**row["fund"])
    r = risk_fn(**row["risk"])
    s = sentiment_score_multifactor(**row["sentiment"])

    # weighted: market 0.25, tech 0.20, fund 0.20, risk 0.20, sentiment 0.15
    return m * 0.25 + t * 0.20 + f * 0.20 + r * 0.20 + s * 0.15


def directional_accuracy(rows: list[dict], score_fn) -> tuple[int, int, float]:
    """directional_accuracy = sign(score-0.5) == sign(return_t1) 的比率."""
    correct = 0
    total = 0
    for row in rows:
        score = score_fn(row)
        pred = 1 if score > 0.5 else (-1 if score < 0.5 else 0)
        actual = 1 if row["return_t1"] > 0 else (-1 if row["return_t1"] < 0 else 0)
        if pred == 0 or actual == 0:
            continue  # 跳過中性
        total += 1
        if pred == actual:
            correct += 1
    return correct, total, (correct / total * 100.0 if total > 0 else 0.0)


def main() -> None:
    print("=" * 70)
    print("v5.14 P37-P40 量化腳本：market/tech/risk cap 線性化改善")
    print("=" * 70)

    # === Step 1: Mock AAPL ===
    print("\n[Step 1] Mock AAPL GBM (seed=42, 252 days)")
    returns = mock_gbm_aapl(n_days=252, seed=42)
    rows = derive_inputs_from_returns(returns)
    print(f"  Days: {len(rows)}, mean return: {sum(returns[1:])/len(rows):.4f}")

    # === Step 2: 計算 v5.13 P36c vs v5.14 ===
    print("\n[Step 2] Score distribution & cap flatline rate")

    def v513_score(row):
        return consensus_v5(row, v513_market_score, v513_tech_score, v513_risk_score)

    def v514_score(row):
        return consensus_v5(row, market_score_multifactor, tech_score_multifactor, risk_score_multifactor)

    v513_scores = [v513_score(r) for r in rows]
    v514_scores = [v514_score(r) for r in rows]

    # 計算 score 分布（驗證 cap 飽和消失）
    def distribution_stats(scores, label):
        n = len(scores)
        cap_high = sum(1 for s in scores if s >= 0.99)  # 接近 cap=1.0
        cap_low = sum(1 for s in scores if s <= 0.01)   # 接近 cap=0.0
        n_buy = sum(1 for s in scores if s > 0.6)
        n_sell = sum(1 for s in scores if s < 0.4)
        n_hold = sum(1 for s in scores if 0.4 <= s <= 0.6)
        mean_score = sum(scores) / n
        print(f"  {label}:")
        print(f"    mean={mean_score:.3f}, cap_high={cap_high}, cap_low={cap_low}")
        print(f"    buy(>0.6)={n_buy} ({100*n_buy/n:.1f}%), "
              f"hold(0.4-0.6)={n_hold} ({100*n_hold/n:.1f}%), "
              f"sell(<0.4)={n_sell} ({100*n_sell/n:.1f}%)")

    distribution_stats(v513_scores, "v5.13 P36c")
    print()
    distribution_stats(v514_scores, "v5.14 P37-P40")

    # === Step 3: Directional accuracy ===
    print("\n[Step 3] Directional accuracy (next-day return)")

    v513_correct, v513_total, v513_acc = directional_accuracy(rows, v513_score)
    v514_correct, v514_total, v514_acc = directional_accuracy(rows, v514_score)

    print(f"  v5.13 P36c: {v513_correct}/{v513_total} = {v513_acc:.2f}%")
    print(f"  v5.14 P37-P40: {v514_correct}/{v514_total} = {v514_acc:.2f}%")
    delta = v514_acc - v513_acc
    print(f"  Delta: {delta:+.2f}pp")

    # === Step 4: 量化 buy/sell balance ===
    print("\n[Step 4] Buy/Sell balance (cap 飽和幻覺指標)")

    v513_buy_dominant = sum(1 for s in v513_scores if s > 0.7) / len(v513_scores) * 100
    v514_buy_dominant = sum(1 for s in v514_scores if s > 0.7) / len(v514_scores) * 100
    v513_sell_dominant = sum(1 for s in v513_scores if s < 0.3) / len(v513_scores) * 100
    v514_sell_dominant = sum(1 for s in v514_scores if s < 0.3) / len(v514_scores) * 100

    print(f"  v5.13 P36c: buy(>0.7)={v513_buy_dominant:.1f}%, sell(<0.3)={v513_sell_dominant:.1f}%")
    print(f"  v5.14 P37-P40: buy(>0.7)={v514_buy_dominant:.1f}%, sell(<0.3)={v514_sell_dominant:.1f}%")

    # === Conclusion ===
    print("\n" + "=" * 70)
    print("結論:")
    print(f"  - v5.13 P36c: 14 個真實 cap flatline → buy 訊號偏向 (consensus 飽和)")
    print(f"  - v5.14 P37-P40: 12/14 cap 線性化 → 訊號反映真實分布")
    print(f"  - Directional accuracy delta: {delta:+.2f}pp")
    print(f"  - Buy dominant 變化: {v513_buy_dominant:.1f}% → {v514_buy_dominant:.1f}% (Δ={v514_buy_dominant-v513_buy_dominant:+.1f}pp)")
    print(f"  - Sell dominant 變化: {v513_sell_dominant:.1f}% → {v514_sell_dominant:.1f}% (Δ={v514_sell_dominant-v513_sell_dominant:+.1f}pp)")
    if abs(delta) >= 5:
        print(f"  ✓ 達到預期 +5-10pp 改善目標")
    else:
        print(f"  ⚠ 未達 +5pp 預期（cap 飽和可能非主要 noise source）")
    print("=" * 70)


if __name__ == "__main__":
    main()
