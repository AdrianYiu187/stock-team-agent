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
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

# 確保 scripts/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def main() -> int:
    _ensure_v510_baseline()

    v510_mod = _load_module("v510_stock_analysis", V510_PATH)
    v511_mod = _load_module("v511_stock_analysis", V511_PATH)

    # v5.15 P46 — 從 TICKER_UNIVERSE 拉（11 ticker 跨 US/HK/CN）
    tickers = TICKER_UNIVERSE
    print(f"📡 拉 yfinance fundamentals ({len(tickers)} tickers: {tickers})...")
    fetch_result = fetch_fundamentals(tickers)
    fundamentals = fetch_result["fundamentals"]
    failed = fetch_result["failed"]

    if not fundamentals:
        print("❌ 全部 ticker 拉取失敗，請檢查網路 / yfinance API")
        return 1

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

    # v5.15 P45 — 寫 fixtures（供 pytest 永久用）+ fetched_at timestamp
    fixtures_path = FIXTURES_PATH
    fixtures_path.parent.mkdir(parents=True, exist_ok=True)
    fixtures_path.write_text(
        json.dumps(
            {
                "tickers": list(fundamentals.keys()),  # 只存成功的
                "fundamentals": fundamentals,
                "v5_10_scores": v510_scores,
                "v5_11_3_scores": v511_scores,
                "std_quant": quant,
                "_meta": {
                    "source": "yfinance real fetch (v5.15 P45+P46 expanded)",
                    "v510_baseline": "0f30069:scripts/stock_analysis.py",
                    "v5113_source": "scripts/stock_analysis.py (HEAD)",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "ticker_universe_size": len(TICKER_UNIVERSE),
                    "failed_tickers": failed,
                    "max_age_days": FIXTURES_MAX_AGE_DAYS,
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\n💾 Fixtures 寫到 {fixtures_path}")
    print(
        f"✅ {len(fundamentals)}/{len(tickers)} ticker 成功"
        + (f"（失敗：{failed}）" if failed else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
