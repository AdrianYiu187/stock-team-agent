"""v5.27 Weight Sensitivity — MULTIFACTOR_WEIGHTS 重新校準量化。

依據 v5.26 P2 量化: 真實 close prices 下 mean Δ -28.77pp (mock -13.36pp),
v5.11.3 4D 整合在真實下比 mock 預測差 2.15x。本腳本探測 6 種 weight 配置,
量化 directional_accuracy / precision_buy / precision_sell 改善幅度,
找出在真實 close prices 下最佳的 4D 權重。

TDD 邏輯:
- 6 種 weight 配置: baseline, tech-heavy, fund-heavy, market-heavy, risk-heavy, balanced
- 每個 config monkey-patch MULTIFACTOR_WEIGHTS,跑 run_cross_market_comparison
- 比較 directional_accuracy Δ vs v5.10 技術 only
- 輸出最佳 config + 量化證據

輸出: docs/v5.27_weight_sensitivity.md + stdout 報告
"""

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

# 確保 scripts/ 在 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backtest_v511_multifactor as bv


# 6 種 weight 配置 (總和 = 1.0)
WEIGHT_CONFIGS = {
    "baseline_0.35_0.30_0.20_0.15": {
        "tech": 0.35, "fund": 0.30, "market": 0.20, "risk": 0.15,
        "rationale": "v5.11.3 default — 技術 0.35 + 基本面 0.30 + 市場 0.20 + 風險 0.15",
    },
    "tech_heavy_0.50_0.25_0.15_0.10": {
        "tech": 0.50, "fund": 0.25, "market": 0.15, "risk": 0.10,
        "rationale": "技術 0.50 — 押注 RSI/MACD/MA50 在真實波動下主導",
    },
    "fund_heavy_0.20_0.50_0.15_0.15": {
        "tech": 0.20, "fund": 0.50, "market": 0.15, "risk": 0.15,
        "rationale": "基本面 0.50 — PE/ROE/PEG/growth 對 long-term 最穩",
    },
    "market_heavy_0.25_0.20_0.45_0.10": {
        "tech": 0.25, "fund": 0.20, "market": 0.45, "risk": 0.10,
        "rationale": "市場 0.45 — ytd_return/pos_52wk 強化",
    },
    "risk_heavy_0.20_0.20_0.15_0.45": {
        "tech": 0.20, "fund": 0.20, "market": 0.15, "risk": 0.45,
        "rationale": "風險 0.45 — volatility/VaR/max_dd/sharpe 過濾極端值",
    },
    "balanced_0.25_0.25_0.25_0.25": {
        "tech": 0.25, "fund": 0.25, "market": 0.25, "risk": 0.25,
        "rationale": "balanced 0.25/0.25/0.25/0.25 — 等權基線",
    },
}


def run_sensitivity() -> dict:
    """跑 6 種 weight 配置 × 真實 close prices,計算每個 config 的 metrics。"""
    results = {}

    for config_name, weights in WEIGHT_CONFIGS.items():
        # Monkey-patch MULTIFACTOR_WEIGHTS
        original_weights = dict(bv.MULTIFACTOR_WEIGHTS)
        bv.MULTIFACTOR_WEIGHTS = weights

        try:
            # 跑 cross-market backtest
            r = bv.run_cross_market_comparison(close_source="real")

            v10 = r["v5.10"]
            v113 = r["v5.11.3"]
            imp = r["improvement_v5.11.3_over_v5.10_pp"]

            # 計算 per-ticker 改善度 (用 per_ticker composite mean)
            per_ticker_composites = [
                d["composite"] for d in r["per_ticker"].values()
            ]
            mean_composite = statistics.mean(per_ticker_composites) if per_ticker_composites else 0.0
            std_composite = statistics.stdev(per_ticker_composites) if len(per_ticker_composites) > 1 else 0.0

            # 計算 ticker 分布的多樣性 (entropy proxy = std * sqrt(N))
            diversity = std_composite * (len(per_ticker_composites) ** 0.5)

            results[config_name] = {
                "weights": weights,
                "rationale": weights["rationale"],
                "v5_10": {
                    "directional_accuracy": v10["directional_accuracy"],
                    "overall_accuracy": v10["overall_accuracy"],
                    "precision_buy": v10["precision_buy"],
                    "precision_sell": v10["precision_sell"],
                },
                "v5_11_3": {
                    "directional_accuracy": v113["directional_accuracy"],
                    "overall_accuracy": v113["overall_accuracy"],
                    "precision_buy": v113["precision_buy"],
                    "precision_sell": v113["precision_sell"],
                },
                "improvement_pp": imp,
                "per_ticker_mean_composite": round(mean_composite, 4),
                "per_ticker_std_composite": round(std_composite, 4),
                "diversity_score": round(diversity, 4),
            }
        finally:
            # 還原原 weights
            bv.MULTIFACTOR_WEIGHTS = original_weights

    return results


def rank_configs(results: dict) -> list:
    """按 directional_accuracy 改善幅度排名 (越高越好)。"""
    ranked = []
    for name, data in results.items():
        score = data["improvement_pp"]["directional_accuracy"]
        ranked.append((name, data, score))
    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked


def generate_report(results: dict, ranked: list) -> str:
    """生成 markdown 報告。"""
    lines = [
        "# v5.27 Weight Sensitivity — MULTIFACTOR_WEIGHTS 重新校準量化",
        "",
        f"> **建立日期**: {datetime.now().strftime('%Y-%m-%d')}",
        f"> **依據**: v5.26 P2 量化 (`0ac7ea1`) — 真實 close prices 下 4D 整合惡化 2.15x",
        f"> **目標**: 找出在真實波動下最佳的 4D 權重配置",
        "",
        "---",
        "",
        "## 1. 量化範圍",
        "",
        "| 項目 | 設定 |",
        "|------|------|",
        "| close_source | real (fixture close_prices) |",
        "| Tickers | 11 (fixture universe) |",
        "| Weight Configs | 6 (baseline + 5 perturbations + balanced) |",
        "| 量化指標 | directional_accuracy Δ / precision_buy / precision_sell / 4D std |",
        "",
        "## 2. Weight Configs",
        "",
        "| Config | tech | fund | market | risk | 設計邏輯 |",
        "|--------|------|------|--------|------|----------|",
    ]

    for name, data in results.items():
        w = data["weights"]
        lines.append(
            f"| `{name}` | {w['tech']:.2f} | {w['fund']:.2f} | "
            f"{w['market']:.2f} | {w['risk']:.2f} | {data['rationale']} |"
        )

    lines.extend([
        "",
        "## 3. 量化結果",
        "",
        "### 3.1 Per-Config 改善幅度 (v5.11.3 vs v5.10)",
        "",
        "| Config | Dir Acc Δ (pp) | Overall Δ (pp) | P_Buy Δ (pp) | P_Sell Δ (pp) |",
        "|--------|----------------|----------------|--------------|---------------|",
    ])

    for name, data, _ in ranked:
        imp = data["improvement_pp"]
        lines.append(
            f"| `{name}` | {imp['directional_accuracy']*100:+.2f} | "
            f"{imp['overall_accuracy']*100:+.2f} | {imp['precision_buy']*100:+.2f} | "
            f"{imp['precision_sell']*100:+.2f} |"
        )

    lines.extend([
        "",
        "### 3.2 4D Score 分布 (per_ticker composite)",
        "",
        "| Config | mean | std | diversity_score |",
        "|--------|------|-----|----------------|",
    ])

    for name, data, _ in ranked:
        lines.append(
            f"| `{name}` | {data['per_ticker_mean_composite']:.4f} | "
            f"{data['per_ticker_std_composite']:.4f} | {data['diversity_score']:.4f} |"
        )

    # 最佳配置
    best_name, best_data, best_score = ranked[0]
    baseline_data = results["baseline_0.35_0.30_0.20_0.15"]
    baseline_dir = baseline_data["improvement_pp"]["directional_accuracy"]

    lines.extend([
        "",
        "## 4. 排名結果",
        "",
        "### 4.1 按 directional_accuracy 改善幅度排名",
        "",
        "| Rank | Config | Dir Acc Δ (pp) | vs Baseline |",
        "|------|--------|----------------|-------------|",
    ])

    for i, (name, data, score) in enumerate(ranked, 1):
        diff = (score - baseline_dir) * 100
        lines.append(
            f"| {i} | `{name}` | {score*100:+.2f} | {diff:+.2f} |"
        )

    lines.extend([
        "",
        f"### 4.2 最佳配置",
        "",
        f"> **{best_name}**",
        f"> Dir Acc Δ: **{best_score*100:+.2f}pp** (vs baseline {baseline_dir*100:+.2f}pp)",
        f"> Rationale: {best_data['rationale']}",
        "",
    ])

    # 結論與 v5.27 建議
    if best_score > baseline_dir:
        verdict = "✅ 採用新配置"
        delta = (best_score - baseline_dir) * 100
    else:
        verdict = "⚠️ baseline 仍最佳,保留 v5.11.3 預設"
        delta = (baseline_dir - best_score) * 100

    lines.extend([
        "## 5. v5.27 結論與建議",
        "",
        f"**裁定**: {verdict} (改善 {delta:.2f}pp in directional_accuracy)",
        "",
        "### 5.1 若新配置勝出",
        "",
        "1. 將 `MULTIFACTOR_WEIGHTS` 從 baseline 改為新配置",
        "2. 新增 8 個 pytest guards 驗證 weights 變更後的行為",
        "3. 更新 `evaluate_predictions()` 預期值（precision_buy/sell 改善幅度）",
        "4. 重新跑 v5.26 P2 量化腳本確認改善幅度不衰減",
        "5. 寫 `docs/v5.27_changelog.md` + Lesson #55 永久化",
        "",
        "### 5.2 若 baseline 仍最佳",
        "",
        "1. 保留 v5.11.3 預設 weights",
        "2. 量化發現保留為 `v5.27_weight_sensitivity_archive.md`",
        "3. 後續 v5.28 候選: 引入 sentiment/news/macro 額外維度（v5.21 已 mock, 真實 fixture 已有）",
        "",
        "## 6. 量化細節",
        "",
        "### 6.1 Diversity Score 公式",
        "",
        "```",
        "diversity = std(per_ticker_composite) * sqrt(N)",
        "```",
        "",
        "- 高 diversity → 4D 對不同 ticker 給出不同 composite (有用)",
        "- 低 diversity → 4D 對所有 ticker 給相似 composite (訊號飽和/失真)",
        "",
        "### 6.2 為什麼用 directional_accuracy 作為主指標",
        "",
        "- overall_accuracy 含 HOLD 雜訊（大量 HOLD 稀釋 accuracy）",
        "- directional_accuracy 只看 BUY/SELL 方向預測，去除 HOLD 影響",
        "- precision_buy / precision_sell 揭示 BUY/SELL 各自的精準度",
        "",
        "---",
        "",
        "## 7. Verify Chain",
        "",
        "```bash",
        "# 預期 1 commit (此量化腳本 + 報告)",
        "git log --oneline -3",
        "",
        "# 跑量化",
        "python scripts/quantify_v527_weight_sensitivity.py",
        "",
        "# pytest 仍全綠 (僅 monkey-patch 模組層常數, 不改源碼)",
        "pytest scripts/tests/ -q  # 420 passed",
        "```",
    ])

    return "\n".join(lines)


def main() -> int:
    print("=" * 70)
    print("v5.27 Weight Sensitivity 量化")
    print("=" * 70)
    print(f"Configs: {len(WEIGHT_CONFIGS)}")
    print(f"Close source: real (fixture close_prices)")
    print()

    results = run_sensitivity()
    ranked = rank_configs(results)

    # stdout 摘要
    print("\n排名 (directional_accuracy Δ):")
    print(f"{'Rank':<5} {'Config':<40} {'Dir Acc Δ':<12}")
    print("-" * 60)
    for i, (name, data, score) in enumerate(ranked, 1):
        print(f"{i:<5} {name:<40} {score*100:+.2f}pp")

    print()
    best_name, best_data, best_score = ranked[0]
    baseline_data = results["baseline_0.35_0.30_0.20_0.15"]
    baseline_dir = baseline_data["improvement_pp"]["directional_accuracy"]
    print(f"最佳: {best_name} (Dir Acc Δ = {best_score*100:+.2f}pp)")
    print(f"Baseline: {baseline_dir*100:+.2f}pp")
    delta = (best_score - baseline_dir) * 100
    print(f"Δ vs baseline: {delta:+.2f}pp")

    # 寫報告
    report = generate_report(results, ranked)
    docs_path = Path(__file__).resolve().parent.parent / "docs" / "v5.27_weight_sensitivity.md"
    docs_path.write_text(report, encoding="utf-8")
    print(f"\n[完成] 報告已存: {docs_path}")

    # 寫 JSON (machine-readable)
    output_dir = Path.home() / ".hermes" / "stock_backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"v527_weight_sensitivity_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "results": results,
            "ranking": [(name, score) for name, _, score in ranked],
            "best_config": best_name,
            "best_dir_acc_delta_pp": best_score * 100,
            "baseline_dir_acc_delta_pp": baseline_dir * 100,
            "improvement_vs_baseline_pp": delta,
            "timestamp": timestamp,
        }, f, indent=2, ensure_ascii=False)
    print(f"[完成] JSON 已存: {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
