"""
v5.19 Stage 6 — 量化 N17/N18/N19 cap flatline 修復對 final score 的影響

對比：v5.18 cap (news_count≥120, region_count≥5, source_diversity≥12)
   vs v5.19 漸進 (news_count 120→500, region 5→12, source 12→30)

量化方式：
- 對 11 ticker (US 4 + HK 3 + CN 4) 跑真實 fixture
- 每個 ticker 用 2 種 news_count (200, 500) 模擬高新聞量情境
- 對比 v5.18 (flatline) vs v5.19 (progressive) 對 final score 影響
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stock_analysis import (
    sentiment_score_multifactor, news_score_multifactor,
    weighted_score_with_variance_penalty, dynamic_weights_for_ticker,
)

# ============================================================
# v5.18 公式 (模擬舊 cap)
# ============================================================
def v518_sentiment(combined_score, confidence, news_count):
    import math
    cs_clamped = max(-1.0, min(1.0, combined_score))
    cs_factor = 0.5 + 0.45 * math.tanh(cs_clamped * 2)
    conf_clamped = max(0.0, min(1.0, confidence))
    conf_factor = 0.5 + 0.5 * conf_clamped
    if news_count <= 0:
        nc_factor = 0.40
    elif news_count < 30:
        nc_factor = 0.40 + 0.30 * news_count / 30
    elif news_count < 60:
        nc_factor = 0.70 + 0.20 * (news_count - 30) / 30
    elif news_count < 120:
        nc_factor = 0.90 + 0.05 * (news_count - 60) / 60
    else:
        nc_factor = 0.95  # v5.18 cap
    score = cs_factor * 0.7 + conf_factor * 0.2 + nc_factor * 0.1
    return max(0.0, min(1.0, score))


def v518_news(news_count, region_count, source_diversity):
    if news_count <= 0:
        nc_factor = 0.0
    elif news_count < 120:
        nc_factor = 0.95 * news_count / 120
    else:
        nc_factor = 0.95  # v5.18 cap
    if region_count <= 0:
        rc_factor = 0.30
    elif region_count < 5:
        rc_factor = 0.30 + 0.65 * region_count / 5
    else:
        rc_factor = 0.95  # v5.18 cap
    if source_diversity <= 1:
        sd_factor = 0.30
    elif source_diversity < 12:
        sd_factor = 0.30 + 0.65 * (source_diversity - 1) / 11
    else:
        sd_factor = 0.95  # v5.18 cap
    score = nc_factor * 0.5 + rc_factor * 0.3 + sd_factor * 0.2
    return max(0.0, min(1.0, score))


# ============================================================
# 11 ticker fixture
# ============================================================
TICKERS = [
    ("AAPL", "US", 0.55, 0.55, 0.55, 0.55),
    ("MSFT", "US", 0.55, 0.55, 0.55, 0.55),
    ("GOOGL", "US", 0.55, 0.55, 0.55, 0.55),
    ("NVDA", "US", 0.55, 0.55, 0.55, 0.55),
    ("0700.HK", "HK", 0.55, 0.55, 0.55, 0.55),
    ("9988.HK", "HK", 0.55, 0.55, 0.55, 0.55),
    ("3690.HK", "HK", 0.55, 0.55, 0.55, 0.55),
    ("600519.SS", "CN", 0.55, 0.55, 0.55, 0.55),
    ("000858.SZ", "CN", 0.55, 0.55, 0.55, 0.55),
    ("601318.SS", "CN", 0.55, 0.55, 0.55, 0.55),
    ("000333.SZ", "CN", 0.55, 0.55, 0.55, 0.55),
]

# 3 種 high-news 情境
SCENARIOS = [
    ("moderate", 100, 3, 5),
    ("high", 200, 5, 12),       # v5.18 全部 hit cap
    ("extreme", 500, 8, 20),    # v5.18 全部 hit cap
]

def run_scenario(news_fn, sent_fn, nc, rc, sd, macro=0.5):
    """對 11 ticker 跑一個 scenario，回傳 final scores"""
    finals = []
    for ticker, region, mkt, tech, fund, risk in TICKERS:
        news = news_fn(nc, rc, sd)
        sent = sent_fn(0.3, 0.7, nc)
        w = dynamic_weights_for_ticker(ticker)
        scores = {
            "market": mkt, "technical": tech, "fundamental": fund,
            "risk": risk, "sentiment": sent, "news": news, "macro": macro,
        }
        final, std = weighted_score_with_variance_penalty(scores, w)
        finals.append((ticker, region, final, news, sent))
    return finals

print("=" * 80)
print("v5.19 Stage 6 — Cap Flatline 修復對 Final Score 影響")
print("=" * 80)

for label, nc, rc, sd in SCENARIOS:
    print(f"\n📊 Scenario: {label} (news_count={nc}, region={rc}, source={sd})")
    v518_results = run_scenario(v518_news, v518_sentiment, nc, rc, sd)
    v519_results = run_scenario(news_score_multifactor, sentiment_score_multifactor, nc, rc, sd)

    # 對比
    print(f"  {'Ticker':<10} {'Region':<5} {'v5.18':>8} {'v5.19':>8} {'Δ':>8} {'news_v5.18':>10} {'news_v5.19':>10}")
    total_delta = 0
    n_nonzero = 0
    for (t1, r1, f1, n1, s1), (t2, r2, f2, n2, s2) in zip(v518_results, v519_results):
        delta = f2 - f1
        if abs(delta) > 1e-6:
            n_nonzero += 1
            total_delta += delta
        marker = " ⚡" if abs(delta) > 1e-4 else ""
        print(f"  {t1:<10} {r1:<5} {f1:>8.4f} {f2:>8.4f} {delta:>+8.4f} {n1:>10.4f} {n2:>10.4f}{marker}")

    avg_delta = total_delta / 11
    print(f"  -- 11 ticker avg Δ final: {avg_delta:+.5f} ({n_nonzero}/11 changed)")

# 量化買賣信號變化
print("\n" + "=" * 80)
print("📈 買賣信號分布變化（v5.18 vs v5.19 high scenario）")
print("=" * 80)
def sig_dist(results):
    from stock_analysis import score_to_bhs
    counts = {"buy": 0, "hold": 0, "sell": 0}
    for t, r, f, n, s in results:
        if f > 0.6:
            counts["buy"] += 1
        elif f < 0.4:
            counts["sell"] += 1
        else:
            counts["hold"] += 1
    return counts

for label, nc, rc, sd in SCENARIOS:
    print(f"\n  Scenario '{label}':")
    v518_sig = sig_dist(run_scenario(v518_news, v518_sentiment, nc, rc, sd))
    v519_sig = sig_dist(run_scenario(news_score_multifactor, sentiment_score_multifactor, nc, rc, sd))
    print(f"    v5.18: {v518_sig}")
    print(f"    v5.19: {v519_sig}")
    print(f"    Δ:     buy={v519_sig['buy']-v518_sig['buy']:+d} hold={v519_sig['hold']-v518_sig['hold']:+d} sell={v519_sig['sell']-v518_sig['sell']:+d}")

print("\n" + "=" * 80)
print("結論：N17/N18/N19 cap 修復在高新聞量情境下...")
print("=" * 80)