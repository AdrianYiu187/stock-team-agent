"""v5.31 P2 — 升級後 per-region 7D weight 重新量化。

業務動機:
  v5.30 P2 量化結果:
    - US (10 ticker): best = hk_fund_heavy, Pearson=+0.7100 ✅
    - HK (9 ticker): 樣本全 sell, Pearson=0 ❌ (proxy 限制)
    - CN (4 ticker): best = global_4d_fund_heavy, Pearson=+0.9452 ✅

  v5.31 P1 升級: 12 個 extended ticker 的 sentiment/news/macro 從 proxy 0.5
  升級為 volatility-derived 真實分數 + ticker hash noise (per-ticker 變異)。

  本腳本量化 v5.31 升級後的 per-region Pearson correlation, 預期:
    - HK Pearson 解鎖到 > 0.3 (因 sentiment/news/macro 從 variance=0 變有變異)
    - US Pearson 變化 < 10pp (US 已有多樣性, 升級影響小)
    - CN Pearson 不變 (CN 來自既有 11 ticker, 不受影響)

方法:
  1. 載入 fixture (既有 11 + 升級後 12 = 23 ticker)
  2. 按 region 分組
  3. 對 5 種 weight configs 算 composite vs majority Pearson
  4. 報告 v5.31 per-region 改善 vs v5.30 baseline

執行:
  python scripts/quantify_v531_per_region_full_7d.py

TDD: scripts/tests/test_v531_p2_full_7d_evaluate.py (8 guards)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from backtest_v511_multifactor import (  # noqa: E402
    MULTIFACTOR_WEIGHTS_7D,
    MULTIFACTOR_WEIGHTS_7D_FALLBACK,
)


FIXTURE_PATH = (
    _REPO_ROOT / "scripts" / "tests" / "fixtures" / "tickers_fundamentals.json"
)


# v5.31 P2 — Region map (US + HK + CN)
REGION_MAP = {
    # US
    "AAPL": "US", "MSFT": "US", "GOOGL": "US", "NVDA": "US",
    "AMZN": "US", "META": "US", "TSLA": "US", "JPM": "US", "V": "US", "JNJ": "US",
    # HK
    "0700.HK": "HK", "9988.HK": "HK", "3690.HK": "HK",
    "0941.HK": "HK", "1299.HK": "HK", "0388.HK": "HK",
    "2318.HK": "HK", "2628.HK": "HK", "1177.HK": "HK",
    # CN
    "600519.SS": "CN", "000858.SZ": "CN", "601318.SS": "CN", "000333.SZ": "CN",
}


# v5.31 P2 — Weight configs (與 v5.29 candidate 量化腳本一致, 確保可比)
WEIGHT_CONFIGS = {
    "global_4d_fund_heavy": {
        "tech": 0.20, "fund": 0.50, "market": 0.15, "risk": 0.15,
        "sentiment": 0.0, "news": 0.0, "macro": 0.0,
    },
    "global_7d_balanced_0_15": dict(MULTIFACTOR_WEIGHTS_7D_FALLBACK),
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
        "sentiment": 0.15, "news": 0.10, "macro": 0.25,
    },
}


def pearson(xs: List[float], ys: List[float]) -> float:
    """Pearson correlation. 樣本不足或變異為 0 → 0.0。"""
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


def _normalize_components(comps: Dict[str, float]) -> Dict[str, float]:
    """fixture key → 7D key mapping (兼容兩種格式)

    - 既有 11 ticker: keys 為 {technical, fundamental, market, risk, sentiment, news, macro}
      → technical → tech, fundamental → fund
    - v5.31 升級 12 ticker (full 7D): keys 為 {tech, fund, market, risk, sentiment, news, macro}
      → 直接對應
    """
    if "tech" in comps:
        return {k: comps[k] for k in ("tech", "fund", "market", "risk", "sentiment", "news", "macro") if k in comps}
    return {
        "tech": comps["technical"],
        "fund": comps["fundamental"],
        "market": comps["market"],
        "risk": comps["risk"],
        "sentiment": comps["sentiment"],
        "news": comps["news"],
        "macro": comps["macro"],
    }


def compute_composite(components: Dict[str, float], weights: Dict[str, float]) -> float:
    norm = _normalize_components(components)
    return round(
        sum(norm[k] * weights[k] for k in weights),
        4,
    )


def evaluate_per_region_v531() -> Dict:
    """主函式: 跑 v5.31 升級後的 per-region candidate evaluation。

    Returns:
        {
            "regions": {US/HK/CN: {n_tickers, best_config, best_pearson, results}},
            "global_best": {config: pearson},
            "v530_baseline": {US: 0.7100, HK: 0.0, CN: 0.9452},
            "summary": {us_improvement_pp, hk_improvement_pp, ...},
        }
    """
    data = json.loads(FIXTURE_PATH.read_text())
    sd = data.get("signal_distribution_per_ticker", {})
    sd_ext = data.get("extended_signal_distribution_per_ticker", {})
    sd_merged = dict(sd_ext)
    sd_merged.update(sd)  # 既有優先

    # 按 region 分組
    by_region: Dict[str, List[Tuple[str, Dict]]] = {"US": [], "HK": [], "CN": []}
    for ticker, info in sd_merged.items():
        region = REGION_MAP.get(ticker, "US")
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
                comps = info["components"]
                composite = compute_composite(comps, weights)
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

    # Global
    global_results = {}
    for cfg_name, weights in WEIGHT_CONFIGS.items():
        composites = []
        majorities = []
        for ticker, info in sd_merged.items():
            comps = info["components"]
            composite = compute_composite(comps, weights)
            composites.append(composite)
            majorities.append({"buy": 1, "hold": 0, "sell": -1}[info["majority"]])
        global_results[cfg_name] = round(pearson(composites, majorities), 4)

    # v5.30 baseline (升級前)
    v530_baseline = {
        "US": 0.7100,  # hk_fund_heavy
        "HK": 0.0,     # proxy 限制
        "CN": 0.9452,  # global_4d_fund_heavy
    }

    summary = {}
    for region, report in regions_report.items():
        v531_best = report["best_pearson"]
        v530_base = v530_baseline[region]
        improvement_pp = round((v531_best - v530_base) * 100, 2)
        summary[f"{region.lower()}_improvement_pp"] = improvement_pp
        summary[f"{region.lower()}_v531_pearson"] = v531_best
        summary[f"{region.lower()}_n_tickers"] = report["n_tickers"]

    return {
        "regions": regions_report,
        "global_best": global_results,
        "v530_baseline": v530_baseline,
        "summary": summary,
    }


def main():
    report = evaluate_per_region_v531()
    print("=" * 72)
    print("v5.31 P2 Per-Region Full 7D 量化報告")
    print("=" * 72)
    print(f"\nFixture: {FIXTURE_PATH.relative_to(_REPO_ROOT)}")
    print()

    print("【v5.30 P2 Baseline (proxy 階段)】")
    for region, pearson_v in report["v530_baseline"].items():
        print(f"  {region}: Pearson = {pearson_v:+.4f}")
    print()

    for region, r in report["regions"].items():
        print(f"【{region} ({r['n_tickers']} tickers) — v5.31 升級後】")
        for cfg, pearson_v in r["results"].items():
            marker = " ← best" if cfg == r["best_config"] else ""
            print(f"  {cfg:32s}: Pearson = {pearson_v:+.4f}{marker}")
        v531 = r["best_pearson"]
        v530 = report["v530_baseline"][region]
        diff = (v531 - v530) * 100
        print(f"  → v5.30 → v5.31 改善: {v530:+.4f} → {v531:+.4f} ({diff:+.2f}pp)")
        print()

    print("【Global Best (23 ticker vs 5 configs)】")
    for cfg, pearson_v in report["global_best"].items():
        print(f"  {cfg:32s}: Pearson = {pearson_v:+.4f}")

    print("\n【Summary — Per-Region Improvement vs v5.30 Baseline】")
    for k, v in report["summary"].items():
        sign = "+" if isinstance(v, float) and v >= 0 else ""
        print(f"  {k:32s}: {sign}{v}")

    # 寫 docs
    docs_dir = _REPO_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "v5.31_p2_per_region_full_7d.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n✅ Report saved to: {report_path.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()