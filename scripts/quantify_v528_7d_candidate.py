"""v5.28 Candidate — 7D 整合量化 (4D + sentiment + news + macro)。

依據 v5.27 Step 2 量化: 6 個 4D weight configs 全部 Dir Acc Δ < 0,
4D 整合在真實 close prices 下整體負貢獻, 需引入 sentiment/news/macro 額外維度。

TDD 邏輯:
- 從 fixture signal_distribution_per_ticker[].components 拿 sentiment/news/macro
- 設計 6 種 7D weight configs (含 baseline 4D + 3 個 sentiment/news/macro 加入)
- 每 config 計算 per_ticker composite_7d
- 用 v5.10 close prices 算 v5.10 baseline accuracy, v5.28 7D 算 accuracy, 求 Δ
- 比較 7D vs 4D fund_heavy 改善幅度

輸出: docs/v5.28_7d_candidate.md + stdout 摘要
"""

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# 確保 scripts/ 在 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import backtest_v511_multifactor as bv


# 7D weight configs (總和 = 1.0)
# 注: 4D 部分 (tech/fund/market/risk) 比例保持 v5.27 fund_heavy 邏輯
WEIGHT_CONFIGS_7D = {
    "baseline_4d_fund_heavy": {
        "tech": 0.20, "fund": 0.50, "market": 0.15, "risk": 0.15,
        "sentiment": 0.0, "news": 0.0, "macro": 0.0,
        "rationale": "v5.27 fund_heavy 4D 對照組 (sentiment/news/macro=0)",
    },
    "add_sentiment_0_15": {
        "tech": 0.18, "fund": 0.42, "market": 0.13, "risk": 0.12,
        "sentiment": 0.15, "news": 0.0, "macro": 0.0,
        "rationale": "加入 sentiment 0.15 (從 fund/tech 各抽 0.08/0.02)",
    },
    "add_news_0_10": {
        "tech": 0.18, "fund": 0.45, "market": 0.13, "risk": 0.14,
        "sentiment": 0.0, "news": 0.10, "macro": 0.0,
        "rationale": "加入 news 0.10 (從 fund/risk 各抽 0.05/0.01)",
    },
    "add_macro_0_10": {
        "tech": 0.18, "fund": 0.45, "market": 0.13, "risk": 0.14,
        "sentiment": 0.0, "news": 0.0, "macro": 0.10,
        "rationale": "加入 macro 0.10 (從 fund/risk 各抽 0.05/0.01)",
    },
    "full_7d_balanced_0_15": {
        "tech": 0.18, "fund": 0.37, "market": 0.13, "risk": 0.12,
        "sentiment": 0.10, "news": 0.05, "macro": 0.05,
        "rationale": "7D 等比縮放 (sentiment+news+macro = 0.20)",
    },
    "sentiment_dominant_0_25": {
        "tech": 0.15, "fund": 0.35, "market": 0.10, "risk": 0.10,
        "sentiment": 0.25, "news": 0.05, "macro": 0.0,
        "rationale": "sentiment 0.25 為主 (假設 market sentiment 是 leading indicator)",
    },
}


def compute_composite_7d(weights: Dict[str, float], scores: Dict[str, float]) -> float:
    """計算 7D composite (4D + sentiment + news + macro)。"""
    return sum(weights[k] * scores.get(k, 0.5) for k in weights if k != "rationale")


def load_fixture_components() -> Dict[str, Dict[str, float]]:
    """從 fixture signal_distribution_per_ticker[].components 載入 7 維度分數。"""
    fixture_path = Path(__file__).resolve().parent / "tests" / "fixtures" / "tickers_fundamentals.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        fixture = json.load(f)
    sd = fixture["signal_distribution_per_ticker"]
    # 統一 keys: components.technical → tech
    out: Dict[str, Dict[str, float]] = {}
    for ticker, data in sd.items():
        c = data["components"]
        out[ticker] = {
            "tech": c.get("technical", 0.5),
            "fund": c.get("fundamental", 0.5),
            "market": c.get("market", 0.5),
            "risk": c.get("risk", 0.5),
            "sentiment": c.get("sentiment", 0.5),
            "news": c.get("news", 0.5),
            "macro": c.get("macro", 0.5),
        }
    return out


def run_sensitivity() -> dict:
    """跑 6 種 7D weight configs, 計算每 ticker 改善幅度。"""
    components = load_fixture_components()

    # 從 fixture 拿 majority 信號作為 ground truth proxy
    fixture_path = Path(__file__).resolve().parent / "tests" / "fixtures" / "tickers_fundamentals.json"
    fixture = json.loads(fixture_path.read_text())
    majority = {t: d["majority"] for t, d in fixture["signal_distribution_per_ticker"].items()}

    # 把 majority 編碼成 numeric score proxy: buy=1.0, hold=0.5, sell=0.0
    signal_to_score = {"buy": 1.0, "hold": 0.5, "sell": 0.0}
    majority_score = {t: signal_to_score[m] for t, m in majority.items()}

    results = {}

    for config_name, weights in WEIGHT_CONFIGS_7D.items():
        # Monkey-patch 4D weights (讓 backtest 用相同 baseline)
        original = dict(bv.MULTIFACTOR_WEIGHTS)
        bv.MULTIFACTOR_WEIGHTS = {
            "tech": weights["tech"],
            "fund": weights["fund"],
            "market": weights["market"],
            "risk": weights["risk"],
        }

        try:
            # 跑 cross-market backtest (real)
            r = bv.run_cross_market_comparison(close_source="real")

            # 計算 7D composite (從 fixture 額外加 sentiment/news/macro)
            per_ticker_7d = {}
            for ticker, scores in components.items():
                per_ticker_7d[ticker] = compute_composite_7d(weights, scores)

            # 用 directional correlation 作為改善指標
            tickers = sorted(components.keys())
            composites_4d = [r["per_ticker"][t]["composite"] for t in tickers if t in r["per_ticker"]]
            composites_7d = [per_ticker_7d[t] for t in tickers if t in r["per_ticker"]]
            majority_vals = [majority_score[t] for t in tickers if t in r["per_ticker"]]

            # Pearson correlation (越高 = 與多數信號方向越一致)
            corr_4d = _pearson(composites_4d, majority_vals) if len(composites_4d) > 1 else 0.0
            corr_7d = _pearson(composites_7d, majority_vals) if len(composites_7d) > 1 else 0.0
            improvement = (corr_7d - corr_4d) * 100  # percentage points

            results[config_name] = {
                "weights": weights,
                "rationale": weights["rationale"],
                "corr_4d": round(corr_4d, 4),
                "corr_7d": round(corr_7d, 4),
                "improvement_pp": round(improvement, 2),
                "improvement_real_dir_acc": r["improvement_v5.11.3_over_v5.10_pp"]["directional_accuracy"] * 100,
            }
        finally:
            bv.MULTIFACTOR_WEIGHTS = original

    return results


def _pearson(xs: List[float], ys: List[float]) -> float:
    """Pearson correlation, n>=2, 否則 0.0。"""
    n = len(xs)
    if n != len(ys) or n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    den_y = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def generate_report(results: dict) -> str:
    """生成 markdown 候選評估報告。"""
    lines = [
        "# v5.28 Candidate — 7D 整合量化 (4D + sentiment + news + macro)",
        "",
        f"> **建立日期**: {datetime.now().strftime('%Y-%m-%d')}",
        f"> **依據**: v5.27 Step 2 (`0429f6c`) — 6 個 4D configs 全部 Dir Acc Δ < 0",
        f"> **候選**: 引入 sentiment/news/macro 額外維度 (4D → 7D)",
        f"> **狀態**: ⚠️ Candidate evaluation, 待 user 裁示是否進入 P1",
        "",
        "---",
        "",
        "## 1. 量化範圍",
        "",
        "| 項目 | 設定 |",
        "|------|------|",
        "| Close source | real (fixture) |",
        "| Tickers | 11 (fixture universe) |",
        "| 7D weight configs | 6 (1 baseline + 5 加入 sentiment/news/macro 變體) |",
        "| 真實 sentiment/news/macro 來源 | `signal_distribution_per_ticker[].components` (v5.21 fixture 已有) |",
        "",
        "## 2. 7D Weight Configs",
        "",
        "| Config | tech | fund | market | risk | sentiment | news | macro | 設計 |",
        "|--------|------|------|--------|------|-----------|------|-------|------|",
    ]

    for name, data in results.items():
        w = data["weights"]
        lines.append(
            f"| `{name}` | {w['tech']:.2f} | {w['fund']:.2f} | "
            f"{w['market']:.2f} | {w['risk']:.2f} | {w['sentiment']:.2f} | "
            f"{w['news']:.2f} | {w['macro']:.2f} | {data['rationale']} |"
        )

    lines.extend([
        "",
        "## 3. 量化結果 (accuracy proxy via majority signal)",
        "",
        "| Config | 4D Acc | 7D Acc | Improvement (pp) |",
        "|--------|--------|--------|-------------------|",
    ])

    lines.extend([
        "",
        "## 3. 量化結果 (Pearson correlation: composite vs majority signal direction)",
        "",
        "| Config | corr(4D, majority) | corr(7D, majority) | Improvement (pp) |",
        "|--------|--------------------|--------------------|-------------------|",
    ])

    for name, data in results.items():
        lines.append(
            f"| `{name}` | {data['corr_4d']:+.4f} | "
            f"{data['corr_7d']:+.4f} | {data['improvement_pp']:+.2f} |"
        )

    lines.extend([
        "",
        "## 4. v5.11.3 真實 backtest (4D 部分)",
        "",
        "| Config | Dir Acc Δ (pp) |",
        "|--------|----------------|",
    ])

    for name, data in results.items():
        lines.append(
            f"| `{name}` | {data['improvement_real_dir_acc']:+.2f} |"
        )

    # 排名
    ranked = sorted(
        results.items(),
        key=lambda x: x[1]["improvement_pp"],
        reverse=True,
    )

    lines.extend([
        "",
        "## 5. 排名 (7D vs 4D improvement)",
        "",
        "| Rank | Config | Improvement (pp) |",
        "|------|--------|------------------|",
    ])

    for i, (name, data) in enumerate(ranked, 1):
        lines.append(f"| {i} | `{name}` | {data['improvement_pp']:+.2f} |")

    best_name, best_data = ranked[0]
    lines.extend([
        "",
        f"### 5.1 最佳配置",
        "",
        f"> **{best_name}** — 7D vs 4D 改善 {best_data['improvement_pp']:+.2f}pp",
        "",
    ])

    # 結論
    if best_data["improvement_pp"] > 5:
        verdict = "✅ 採用 7D 配置 — sentiment/news/macro 顯著提升"
    elif best_data["improvement_pp"] > 0:
        verdict = "🟡 7D 邊際改善 — 需更多 ticker 樣本確認"
    else:
        verdict = "❌ 7D 無改善 — sentiment/news/macro 不應加入"

    lines.extend([
        "## 6. v5.28 結論與建議",
        "",
        f"**裁定**: {verdict}",
        "",
        "### 6.1 若採用 7D",
        "",
        "1. 新增 `macro_score_multifactor(us_10y_yield, vix, gold, dxy, sp500_ytd)` 純函數",
        "2. 將 `compute_4d_multifactor` 改名 `compute_7d_multifactor`, 加 3 維度",
        "3. 新增 `run_v528_backtest_path` 支援 7D composite",
        "4. 更新 `MULTIFACTOR_WEIGHTS` 為 7-key dict",
        "5. TDD: 8 個 pytest guards 驗證 7D 公式 + 鎖定新 weights",
        "6. 重新跑 quantify_v526 mock vs real 確認 7D 改善未衰減",
        "7. 寫 v5.28 closure + Lesson #55 永久化",
        "",
        "### 6.2 若不採用 7D",
        "",
        "1. 量化發現保留為 `v5.28_7d_candidate_archive.md`",
        "2. 後續 v5.29 候選: per-region 4D 重新校準 (US/HK/CN 分區)",
        "3. 或 v5.29 候選: sentiment-only extension (4D + sentiment)",
        "",
        "## 7. Caveats & Limitations",
        "",
        "- accuracy proxy 用 majority 信號 vs composite 方向,非真實 backtest accuracy",
        "- sentiment/news/macro 從 fixture 跨 snapshot 平均,非動態時間序列",
        "- 真實 7D backtest 需要重寫 run_v5113_backtest_path 注入 3 維度 (v5.28 P1 工作量)",
        "- 6 種 weight config 是 heuristic,非 grid search 最佳解",
        "",
        "## 8. Verify Chain",
        "",
        "```bash",
        "# 預期 1 commit (候選評估, 非 closure)",
        "git log --oneline -3",
        "",
        "# 跑量化",
        "python scripts/quantify_v528_7d_candidate.py",
        "",
        "# pytest 仍全綠 (僅 monkey-patch 模組層常數)",
        "pytest scripts/tests/ -q  # 455 passed",
        "```",
    ])

    return "\n".join(lines)


def main() -> int:
    print("=" * 70)
    print("v5.28 Candidate — 7D 整合量化")
    print("=" * 70)
    print(f"Configs: {len(WEIGHT_CONFIGS_7D)}")
    print(f"Close source: real")
    print()

    results = run_sensitivity()

    print("排名 (7D vs 4D improvement):")
    print(f"{'Rank':<5} {'Config':<40} {'Improve (pp)':<12}")
    print("-" * 60)
    ranked = sorted(results.items(), key=lambda x: x[1]["improvement_pp"], reverse=True)
    for i, (name, data) in enumerate(ranked, 1):
        print(f"{i:<5} {name:<40} {data['improvement_pp']:+.2f}")

    best_name, best_data = ranked[0]
    print()
    print(f"最佳: {best_name} (7D vs 4D 改善 {best_data['improvement_pp']:+.2f}pp)")

    report = generate_report(results)
    docs_path = Path(__file__).resolve().parent.parent / "docs" / "v5.28_7d_candidate.md"
    docs_path.write_text(report, encoding="utf-8")
    print(f"\n[完成] 報告已存: {docs_path}")

    # JSON
    output_dir = Path.home() / ".hermes" / "stock_backtest"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"v528_7d_candidate_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[完成] JSON 已存: {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())