"""v5.29 候選 — per-region 7D weight 重新校準。

業務動機 (v5.27 Step 2 + v5.28 Step 3):
- 全域 fund_heavy 對 US/HK 改善 +2.64pp, 對 A 股 (CN) 5 個 HIGH-risk ticker 中 2 個反向 BUY
- 假設: per-region 重新校準 7D weights, 可能改善 A 股 accuracy（因為 CN 情緒/新聞/宏觀特別敏感）
- 此腳本量化「per-region 7D vs 全域 7D (full_7d_balanced_0_15)」的 Pearson correlation 改善

方法:
1. 載入 fixture `signal_distribution_per_ticker[t].components` (7 維度)
2. 按 region 分組 (US / HK / CN)
3. 對每個 region, 對 5 種 weight configs 算 composite:
   - global_4d_fund_heavy
   - global_7d_balanced_0_15 (v5.28 baseline)
   - region_optimized_tech_heavy (US 假設 tech 重要)
   - region_optimized_fund_heavy (HK 假設 fund 重要, 港股穩健)
   - region_optimized_macro_heavy (CN 假設 macro/情緒 重要, 政策驅動)
4. 對每個 region 算 composite vs majority 的 Pearson correlation
5. 報告: per-region 最佳 config 是否 > global 7D baseline

TDD: scripts/tests/test_v529_per_region_sensitivity.py 6 guards
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from backtest_v511_multifactor import (  # noqa: E402
    MULTIFACTOR_WEIGHTS_7D,
    MULTIFACTOR_WEIGHTS_7D_FALLBACK,
    apply_7d_weights,
)


FIXTURE_PATH = _REPO_ROOT / "scripts" / "tests" / "fixtures" / "tickers_fundamentals.json"


REGION_MAP = {
    # US
    "AAPL": "US", "MSFT": "GOOGL".replace("GOOGL", "US"),  # base
    "NVDA": "US",
    # HK
    "0700.HK": "HK", "9988.HK": "HK", "3690.HK": "HK",
    # CN
    "600519.SS": "CN", "000858.SZ": "CN", "601318.SS": "CN", "000333.SZ": "CN",
}
# Simplify with explicit (avoid the trick above):
REGION_MAP = {
    "AAPL": "US", "MSFT": "US", "GOOGL": "US", "NVDA": "US",
    "0700.HK": "HK", "9988.HK": "HK", "3690.HK": "HK",
    "600519.SS": "CN", "000858.SZ": "CN", "601318.SS": "CN", "000333.SZ": "CN",
}

# v5.30 P2 — 擴充 ticker region map (12 ticker 從 S&P 500 / Hang Seng)
REGION_MAP_EXTENDED = dict(REGION_MAP)
REGION_MAP_EXTENDED.update({
    "AMZN": "US", "META": "US", "TSLA": "US",
    "JPM": "US", "V": "US", "JNJ": "US",
    "0941.HK": "HK", "1299.HK": "HK", "0388.HK": "HK",
    "2318.HK": "HK", "2628.HK": "HK", "1177.HK": "HK",
})


# Weight configs 候選 (sum=1.0 for 7 keys)
# v5.30 P1 修正: global_7d_balanced_0_15 改用 MULTIFACTOR_WEIGHTS_7D_FALLBACK (v5.28 預設)
# 而非 dict(MULTIFACTOR_WEIGHTS_7D) — 後者會隨 v5.30 升級而改變, 失去 baseline 意義
WEIGHT_CONFIGS = {
    # Baseline 4D (fund_heavy) — 故意把 sentiment/news/macro 權重設 0 模擬 4D 路徑
    "global_4d_fund_heavy": {
        "tech": 0.20, "fund": 0.50, "market": 0.15, "risk": 0.15,
        "sentiment": 0.0, "news": 0.0, "macro": 0.0,
    },
    # Global 7D (v5.28 量化勝出) — 用 FALLBACK 鎖定 v5.28 值
    "global_7d_balanced_0_15": dict(MULTIFACTOR_WEIGHTS_7D_FALLBACK),
    # Region-tuned candidates
    "us_tech_heavy": {
        "tech": 0.30, "fund": 0.25, "market": 0.15, "risk": 0.10,
        "sentiment": 0.10, "news": 0.05, "macro": 0.05,
    },
    "hk_fund_heavy": {
        "tech": 0.15, "fund": 0.45, "market": 0.15, "risk": 0.10,
        "sentiment": 0.05, "news": 0.05, "macro": 0.05,
    },
    "cn_macro_heavy": {
        "tech": 0.10, "fund": 0.25, "market": 0.10, "risk": 0.05,
        "sentiment": 0.15, "news": 0.10, "macro": 0.25,  # 政策/情緒/宏觀特別敏感
    },
}


def _map_components(comps_raw: Dict[str, float]) -> Dict[str, float]:
    """fixture key → 7D key mapping

    兼容兩種 fixture 格式:
    - 既有 11 ticker: keys 為 {technical, fundamental, market, risk, sentiment, news, macro}
      → technical → tech, fundamental → fund
    - v5.30 P2 擴充 12 ticker (proxy): keys 為 {tech, fund, market, risk, sentiment, news, macro}
      → 直接對應, 不需 mapping
    """
    if "tech" in comps_raw:
        # 已是 7D 標準 key (proxy 格式)
        return {k: comps_raw[k] for k in MULTIFACTOR_WEIGHTS_7D if k in comps_raw}
    # 既有格式 (technical/fundamental)
    return {
        "tech": comps_raw["technical"],
        "fund": comps_raw["fundamental"],
        "market": comps_raw["market"],
        "risk": comps_raw["risk"],
        "sentiment": comps_raw["sentiment"],
        "news": comps_raw["news"],
        "macro": comps_raw["macro"],
    }


def pearson(xs: List[float], ys: List[float]) -> float:
    """Pearson correlation. 回傳 0.0 若樣本不足或變異為 0。"""
    n = len(xs)
    if n < 3:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return 0.0
    return cov / denom


def compute_composite_with_weights(components: Dict[str, float], weights: Dict[str, float]) -> float:
    """Pure helper: 給定 components + weights 算 composite 純量。
    Weights 必須 sum=1.0 且 keys 覆蓋 components。"""
    return round(
        sum(components[k] * weights[k] for k in weights),
        4,
    )


def evaluate_per_region(
    fixture_path: Path = FIXTURE_PATH,
) -> Dict:
    """主函式 — 跑 per-region candidate evaluation, 回傳結構化報告。

    Returns:
        {
            "regions": {
                "US": {
                    "n_tickers": 4,
                    "tickers": [...],
                    "best_config": "us_tech_heavy",
                    "best_pearson": 0.85,
                    "results": {
                        "global_4d_fund_heavy": 0.40,
                        "global_7d_balanced_0_15": 0.62,
                        "us_tech_heavy": 0.85,
                        ...
                    }
                },
                "HK": {...},
                "CN": {...}
            },
            "global_best": {
                "global_7d_balanced_0_15": 0.55,
                ...
            },
            "summary": {
                "us_improvement_pp": 23.0,  # us_tech_heavy - global_7d
                "hk_improvement_pp": -5.0,
                "cn_improvement_pp": 15.0,
            }
        }
    """
    with open(fixture_path) as f:
        fixture = json.load(f)

    sd = fixture["signal_distribution_per_ticker"]

    # 按 region 分組
    by_region: Dict[str, List[Tuple[str, Dict]]] = {"US": [], "HK": [], "CN": []}
    for ticker, info in sd.items():
        region = REGION_MAP.get(ticker, "US")
        by_region[region].append((ticker, info))

    regions_report = {}
    for region, items in by_region.items():
        if not items:
            continue

        # 對每個 config 算 Pearson correlation vs majority
        results = {}
        for cfg_name, weights in WEIGHT_CONFIGS.items():
            composites = []
            majorities = []
            for ticker, info in items:
                components_7d = _map_components(info["components"])
                composite = compute_composite_with_weights(components_7d, weights)
                composites.append(composite)
                majorities.append({"buy": 1, "hold": 0, "sell": -1}[info["majority"]])

            results[cfg_name] = round(pearson(composites, majorities), 4)

        # 找 best config
        best_cfg = max(results.items(), key=lambda kv: kv[1])[0]
        regions_report[region] = {
            "n_tickers": len(items),
            "tickers": [t for t, _ in items],
            "best_config": best_cfg,
            "best_pearson": results[best_cfg],
            "results": results,
        }

    # Global best (全域 11 ticker vs 每個 config)
    global_results = {}
    for cfg_name, weights in WEIGHT_CONFIGS.items():
        composites = []
        majorities = []
        for ticker, info in sd.items():
            components_7d = _map_components(info["components"])
            composite = compute_composite_with_weights(components_7d, weights)
            composites.append(composite)
            majorities.append({"buy": 1, "hold": 0, "sell": -1}[info["majority"]])
        global_results[cfg_name] = round(pearson(composites, majorities), 4)

    # Summary: per-region best vs global 7D baseline
    global_7d_baseline = global_results["global_7d_balanced_0_15"]
    summary = {}
    for region, report in regions_report.items():
        improvement = report["best_pearson"] - global_7d_baseline
        summary[f"{region.lower()}_improvement_pp"] = round(improvement * 100, 2)

    return {
        "regions": regions_report,
        "global_best": global_results,
        "summary": summary,
    }


def evaluate_per_region_extended(
    fixture_path: Path = FIXTURE_PATH,
) -> Dict:
    """v5.30 P2 — 擴充版 evaluate, 合併既有 11 ticker + 12 擴充 ticker。

    Returns:
        {
            "regions": { "US": {...}, "HK": {...}, "CN": {...} },  # 同 evaluate_per_region
            "global_best": {...},  # 23 ticker vs 5 configs
            "summary": {
                "us_improvement_pp": ...,
                "hk_improvement_pp": ...,
                "cn_improvement_pp": ...,
                "us_n_tickers": 10,
                "hk_n_tickers": 9,
                "cn_n_tickers": 4,
            }
        }
    """
    with open(fixture_path) as f:
        fixture = json.load(f)

    sd = fixture.get("signal_distribution_per_ticker", {})
    sd_ext = fixture.get("extended_signal_distribution_per_ticker", {})
    # 合併: 既有優先, 擴充補充
    sd_merged = dict(sd_ext)
    sd_merged.update(sd)  # 既有覆蓋擴充 (避免衝突)

    # 按 region 分組
    by_region: Dict[str, List[Tuple[str, Dict]]] = {"US": [], "HK": [], "CN": []}
    for ticker, info in sd_merged.items():
        region = REGION_MAP_EXTENDED.get(ticker, "US")
        by_region[region].append((ticker, info))

    regions_report = {}
    for region, items in by_region.items():
        if not items:
            continue

        results = {}
        for cfg_name, weights in WEIGHT_CONFIGS.items():
            composites = []
            majorities = []
            for ticker, info in items:
                components_7d = _map_components(info["components"])
                composite = compute_composite_with_weights(components_7d, weights)
                composites.append(composite)
                majorities.append({"buy": 1, "hold": 0, "sell": -1}[info["majority"]])

            results[cfg_name] = round(pearson(composites, majorities), 4)

        best_cfg = max(results.items(), key=lambda kv: kv[1])[0]
        regions_report[region] = {
            "n_tickers": len(items),
            "tickers": [t for t, _ in items],
            "best_config": best_cfg,
            "best_pearson": results[best_cfg],
            "results": results,
        }

    # Global best (23 ticker vs 每個 config)
    global_results = {}
    for cfg_name, weights in WEIGHT_CONFIGS.items():
        composites = []
        majorities = []
        for ticker, info in sd_merged.items():
            components_7d = _map_components(info["components"])
            composite = compute_composite_with_weights(components_7d, weights)
            composites.append(composite)
            majorities.append({"buy": 1, "hold": 0, "sell": -1}[info["majority"]])
        global_results[cfg_name] = round(pearson(composites, majorities), 4)

    global_7d_baseline = global_results["global_7d_balanced_0_15"]
    summary = {}
    for region, report in regions_report.items():
        improvement = report["best_pearson"] - global_7d_baseline
        summary[f"{region.lower()}_improvement_pp"] = round(improvement * 100, 2)
        summary[f"{region.lower()}_n_tickers"] = report["n_tickers"]

    return {
        "regions": regions_report,
        "global_best": global_results,
        "summary": summary,
    }


def main():
    report = evaluate_per_region()
    print("=" * 72)
    print("v5.29 Per-Region 7D Weight Sensitivity Report")
    print("=" * 72)
    print(f"\nFixture: {FIXTURE_PATH.relative_to(_REPO_ROOT)}")
    print(f"Tickers: US=4 (AAPL/MSFT/GOOGL/NVDA), HK=3 (0700/9988/3690), CN=4 (600519/000858/601318/000333)")
    print()

    print("【Global Baseline (all 11 tickers)】")
    for cfg, pearson_v in report["global_best"].items():
        print(f"  {cfg:32s}: Pearson = {pearson_v:+.4f}")
    print()

    for region, r in report["regions"].items():
        print(f"【{region} ({r['n_tickers']} tickers: {', '.join(r['tickers'])})】")
        for cfg, pearson_v in r["results"].items():
            marker = " ← best" if cfg == r["best_config"] else ""
            print(f"  {cfg:32s}: Pearson = {pearson_v:+.4f}{marker}")
        print()

    print("【Per-Region Improvement vs Global 7D baseline (pearson units × 100)】")
    for k, v in report["summary"].items():
        sign = "+" if v >= 0 else ""
        print(f"  {k:32s}: {sign}{v:.2f} pp")

    # 寫報告到 docs
    docs_dir = _REPO_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "v5.29_per_region_candidate.md"
    with open(report_path, "w") as f:
        f.write(_render_markdown(report))
    print(f"\n✅ Report saved to: {report_path.relative_to(_REPO_ROOT)}")


def _render_markdown(report: Dict) -> str:
    md = ["# v5.29 Per-Region 7D Weight Sensitivity — Candidate Report", ""]
    md.append("**Date**: 2026-06-30")
    md.append("**業務動機**: v5.27 Step 2 全域 fund_heavy 對 US/HK 改善 +2.64pp, 對 A 股 5 個 HIGH-risk 中 2 個反向 BUY。")
    md.append("**假設**: per-region 重新校準 7D weights 可能改善 A 股 accuracy (CN 對 sentiment/macro 特別敏感)。")
    md.append("")
    md.append("## 方法")
    md.append("- 5 weight configs × 3 regions (US/HK/CN)")
    md.append("- Pearson correlation: composite_7d vs signal_dist majority direction")
    md.append("- 樣本量: US=4, HK=3, CN=4 (per-region 樣本偏小, 結果僅作 candidate 不作為結論)")
    md.append("")
    md.append("## Global Baseline (all 11 tickers)")
    md.append("")
    md.append("| Config | Pearson |")
    md.append("|--------|---------|")
    for cfg, v in report["global_best"].items():
        md.append(f"| `{cfg}` | {v:+.4f} |")
    md.append("")
    md.append("## Per-Region Results")
    md.append("")
    for region, r in report["regions"].items():
        md.append(f"### {region} ({r['n_tickers']} tickers: {', '.join(r['tickers'])})")
        md.append("")
        md.append("| Config | Pearson |")
        md.append("|--------|---------|")
        for cfg, v in r["results"].items():
            marker = " ← **best**" if cfg == r["best_config"] else ""
            md.append(f"| `{cfg}` | {v:+.4f}{marker} |")
        md.append("")
    md.append("## Improvement vs Global 7D Baseline")
    md.append("")
    md.append("| Region | Best Config | Best Pearson | Improvement (pp) |")
    md.append("|--------|-------------|--------------|------------------|")
    global_7d_baseline = report["global_best"]["global_7d_balanced_0_15"]
    for region, r in report["regions"].items():
        improvement = r["best_pearson"] - global_7d_baseline
        sign = "+" if improvement >= 0 else ""
        md.append(
            f"| {region} | `{r['best_config']}` | {r['best_pearson']:+.4f} | {sign}{improvement*100:.2f}pp |"
        )
    md.append("")
    md.append("## Caveats")
    md.append("- Per-region 樣本量過小 (US=4 / HK=3 / CN=4), Pearson 結果 noise 較大")
    md.append("- 若 improvement < 5pp, 視為 noise 不採納 per-region 校準")
    md.append("- 真實採納前需先擴大 sample (每 region ≥ 10 ticker)")
    md.append("- 採納門檻: per-region best 比 global 7D 改善 ≥ +5pp")
    return "\n".join(md)


if __name__ == "__main__":
    main()