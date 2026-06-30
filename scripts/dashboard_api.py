"""v5.27 Step 2 + v5.28 P2 — FastAPI 後端,串接 dashboard 與 run_cross_market_comparison。

提供:
- GET /api/cross_market?close_source=real|mock → cross-market backtest 結果 (4D)
- GET /api/cross_market_7d?tickers=... → 7D 整合 composite (v5.28 NEW)
- GET /api/health → 健康檢查
- GET /api/config → 當前 MULTIFACTOR_WEIGHTS + MULTIFACTOR_WEIGHTS_7D + close_source 預設

啟動:
    cd ~/stock-team-agent
    uvicorn scripts.dashboard_api:app --reload --port 8080

前端串接:
    fetch('http://localhost:8080/api/cross_market?close_source=real')
      .then(r => r.json()).then(render)
    fetch('http://localhost:8080/api/cross_market_7d')
      .then(r => r.json()).then(render7d)

TDD: scripts/tests/test_dashboard_api.py 13 個 guards
"""

import json
import sys
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 確保 scripts/ 在 path
_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))

from backtest_v511_multifactor import (  # noqa: E402
    MULTIFACTOR_WEIGHTS,
    MULTIFACTOR_WEIGHTS_7D,
    MULTIFACTOR_WEIGHTS_7D_FALLBACK,
    apply_7d_weights,
    run_cross_market_comparison,
)

# v5.31 P0 — 4D fund_heavy weights 推廣為 7D shape (4 維度 + sentiment/news/macro=0)
# 用於 HK/CN region (兩者皆用 4D 路徑) 避免 hardcoded 重複
WEIGHTS_4D_FUND_HEAVY = {
    **dict(MULTIFACTOR_WEIGHTS),
    "sentiment": 0.0,
    "news": 0.0,
    "macro": 0.0,
}

# v5.31 P0 — Signal threshold 常數 (從 4D composite_to_signal 同步, 避免 future drift)
BUY_THRESHOLD = 0.58
SELL_THRESHOLD = 0.45

# v5.30 P3 — Per-region 7D weight 預設（量化勝出）
# 來源：v5.30 P2 evaluate_per_region_extended() 量化結果
# - US (10 ticker, 擴充後): best = hk_fund_heavy, Pearson=+0.7100
# - HK (9 ticker, 擴充後): 樣本全 sell, Pearson 變異為 0, 暫用 WEIGHTS_4D_FUND_HEAVY 為保守預設
# - CN (4 ticker): best = global_4d_fund_heavy (反轉結論, 4D 反而最穩)
# - Global: v5.30 預設 cn_macro_heavy
PER_REGION_WEIGHTS_7D = {
    "US": {
        "tech": 0.15, "fund": 0.45, "market": 0.15, "risk": 0.10,
        "sentiment": 0.05, "news": 0.05, "macro": 0.05,
        "_source": "us_fund_heavy (v5.30 P2 best, Pearson=+0.7100)",
    },
    "HK": {
        **dict(WEIGHTS_4D_FUND_HEAVY),
        "_source": "WEIGHTS_4D_FUND_HEAVY (HK 樣本 proxy 限制, 保守預設)",
    },
    "CN": {
        **dict(WEIGHTS_4D_FUND_HEAVY),
        "_source": "WEIGHTS_4D_FUND_HEAVY (v5.29 反轉結論, Pearson=+0.9452)",
    },
    "global": {
        **dict(MULTIFACTOR_WEIGHTS_7D),
        "_source": "v5.30 P1 default cn_macro_heavy (Pearson=+0.7730)",
    },
}

# 去除 _source metadata（呼叫端用不著）
PER_REGION_WEIGHTS_7D_CLEAN = {
    region: {k: v for k, v in weights.items() if not k.startswith("_")}
    for region, weights in PER_REGION_WEIGHTS_7D.items()
}

# 對應 ticker → region (用於 UI badge)
TICKER_REGION_MAP = {
    "AAPL": "US", "MSFT": "US", "GOOGL": "US", "NVDA": "US",
    "0700.HK": "HK", "9988.HK": "HK", "3690.HK": "HK",
    "600519.SS": "CN", "000858.SZ": "CN", "601318.SS": "CN", "000333.SZ": "CN",
}

REGION_DISPLAY = {
    "US": {"name": "US", "color": "#3b82f6", "advice": "us_fund_heavy"},
    "HK": {"name": "HK", "color": "#f59e0b", "advice": "4d_fund_heavy (保守)"},
    "CN": {"name": "CN", "color": "#ef4444", "advice": "4d_fund_heavy (4D 反而最佳)"},
    "global": {"name": "Global", "color": "#10b981", "advice": "cn_macro_heavy (v5.30 預設)"},
}


# ============================================================================
# FastAPI app
# ============================================================================

app = FastAPI(
    title="Stock Team Agent — Operator Dashboard API",
    description="v5.28 P2 + v5.30 P3 + v5.31 P0/P1 — 4D fund_heavy + 7D 整合層 (sentiment+news+macro) + per-region weights",
    version="5.31.0",
)

# CORS for dashboard/index.html 本地開發
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; prod 應該限制 origin
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ============================================================================
# Response models (Pydantic for OpenAPI docs)
# ============================================================================

class MetricsBlock(BaseModel):
    overall_accuracy: float
    directional_accuracy: float
    precision_buy: float
    precision_sell: float
    precision_hold: float
    n_total: int
    n_buy: int
    n_sell: int
    n_hold: int


class PerTickerScore(BaseModel):
    tech: float
    fund: float
    market: float
    risk: float
    composite: float
    n_predictions: int


class CapWarning(BaseModel):
    metric: str
    n_in_cap_zone: int
    coverage: float
    is_by_design: bool
    threshold_value: float
    tickers: list


class CrossMarketResponse(BaseModel):
    config: dict
    v5_10: MetricsBlock
    v5_11_3: MetricsBlock
    per_ticker: dict[str, PerTickerScore]
    cap_warnings: list[CapWarning]
    improvement_v5_11_3_over_v5_10_pp: dict
    close_source: Literal["mock", "real"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    weights: dict


# ============================================================================
# JSON-safe serialization helper
# ============================================================================

def _make_json_safe(obj):
    """遞迴把 numpy/Path 等非 JSON-serializable 轉成純 Python。"""
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    return obj


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """健康檢查 + 當前 weights。"""
    return HealthResponse(
        status="ok",
        version="5.31.0",
        weights=dict(MULTIFACTOR_WEIGHTS),
    )


@app.get("/api/config", response_model=dict)
def config() -> dict:
    """當前 MULTIFACTOR_WEIGHTS + MULTIFACTOR_WEIGHTS_7D + close_source 預設。

    Response shape:
        {
            "weights_4d": {...},              # fund_heavy (4 keys)
            "weights_7d": {...},              # cn_macro_heavy (7 keys, v5.30 NEW default)
            "weights_7d_fallback": {...},     # full_7d_balanced_0_15 (v5.28 預設, v5.30 NEW fallback)
            "per_region_weights_7d": {US:..., HK:..., CN:..., global:...},  # v5.30 P3 NEW
            "ticker_region_map": {AAPL:US, ...},  # v5.30 P3 NEW
            "available_regions": ["US", "HK", "CN", "global"],  # v5.30 P3 NEW
            "close_source_default": "real",
            "available_close_sources": ["mock", "real"],
            "version": "5.31.0"
        }
    """
    return {
        "weights_4d": dict(MULTIFACTOR_WEIGHTS),
        "weights_7d": dict(MULTIFACTOR_WEIGHTS_7D),
        "weights_7d_fallback": dict(MULTIFACTOR_WEIGHTS_7D_FALLBACK),
        "per_region_weights_7d": PER_REGION_WEIGHTS_7D_CLEAN,
        "ticker_region_map": TICKER_REGION_MAP,
        "available_regions": ["US", "HK", "CN", "global"],
        "close_source_default": "real",
        "available_close_sources": ["mock", "real"],
        "version": "5.31.0",
    }


@app.get("/api/cross_market")
def cross_market(
    close_source: Literal["mock", "real"] = Query(
        default="real",
        description="close prices 來源: 'real' = fixture 真實, 'mock' = GBM seed=42",
    ),
    tickers: Optional[str] = Query(
        default=None,
        description="comma-separated ticker list (e.g. 'AAPL,MSFT,GOOGL'), default = 全部 11",
    ),
) -> JSONResponse:
    """跨 11 ticker cross-market backtest,回傳完整 metrics + per_ticker + cap_warnings。"""
    ticker_list = None
    if tickers:
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]

    try:
        result = run_cross_market_comparison(
            close_source=close_source,
            tickers=ticker_list,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # JSON-safe serialization (cast through Any 避免 Pyright narrowing 誤報)
    result_safe = _make_json_safe(result)
    assert isinstance(result_safe, dict)
    payload = dict(result_safe)
    payload["close_source"] = close_source  # explicit echo

    return JSONResponse(content=payload)


@app.get("/api/cross_market_7d")
def cross_market_7d(
    tickers: Optional[str] = Query(
        default=None,
        description="comma-separated ticker list, default = 全部 11 (filter 從 fixture)",
    ),
    region: Literal["US", "HK", "CN", "global"] = Query(
        default="global",
        description="v5.30 P3 — 套用該 region 的最佳 7D weights (US=us_fund_heavy, HK/CN=4d_fund_heavy, global=v5.30 預設)",
    ),
) -> JSONResponse:
    """v5.28 P2 + v5.30 P3 — 7D 整合 composite per ticker, 支援 per-region weights。

    從 fixture `signal_distribution_per_ticker[t].components` 取 7 維度預計算分數,
    套用該 region 的 7D weights 加權, 輸出 composite + signal + region badge。

    Response shape:
        {
            "config": {
                "weights_7d": {...},  # 該 region 對應的 weights
                "region": "US|HK|CN|global",
                "source": "fixture_signal_distribution_per_ticker",
                "version": "5.30.0"
            },
            "per_ticker": {
                "AAPL": {
                    "tech": 0.5, "fund": 0.5914, "market": 0.5, "risk": 0.5,
                    "sentiment": 0.5167, "news": 0.5, "macro": 0.463,
                    "composite_7d": 0.5285,
                    "signal": "HOLD",
                    "majority": "buy",
                    "buy_ratio": 0.3815, "hold_ratio": 0.3092, "sell_ratio": 0.3092,
                    "region": "US",  # ticker 屬於的 region (badge)
                    "advice": "us_fund_heavy"  # 建議 config
                },
                ...
            }
        }
    """
    fixture_path = (
        Path(__file__).resolve().parent
        / "tests" / "fixtures" / "tickers_fundamentals.json"
    )
    with open(fixture_path) as f:
        fixture = json.load(f)

    sd = fixture["signal_distribution_per_ticker"]
    if tickers:
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        sd = {t: sd[t] for t in ticker_list if t in sd}

    # v5.30 P3 — 根據 region 選 weights
    weights_7d = PER_REGION_WEIGHTS_7D_CLEAN[region]

    per_ticker = {}
    for ticker, info in sd.items():
        comps_raw = info["components"]
        # fixture key mapping: technical → tech, fundamental → fund
        components_7d = {
            "tech": comps_raw["technical"],
            "fund": comps_raw["fundamental"],
            "market": comps_raw["market"],
            "risk": comps_raw["risk"],
            "sentiment": comps_raw["sentiment"],
            "news": comps_raw["news"],
            "macro": comps_raw["macro"],
        }
        # 用該 region 的 weights 算 composite
        composite_7d = round(
            sum(components_7d[k] * weights_7d[k] for k in weights_7d),
            4,
        )
        # 與 4D 共用 signal threshold (composite_to_signal: >BUY_THRESHOLD / <SELL_THRESHOLD / else HOLD)
        if composite_7d > BUY_THRESHOLD:
            signal = "BUY"
        elif composite_7d < SELL_THRESHOLD:
            signal = "SELL"
        else:
            signal = "HOLD"

        # v5.30 P3 — 每個 ticker 標記其 region (用於 UI badge)
        ticker_region = TICKER_REGION_MAP.get(ticker, "US")
        ticker_advice = REGION_DISPLAY[ticker_region]["advice"]

        per_ticker[ticker] = {
            **components_7d,
            "composite_7d": composite_7d,
            "signal": signal,
            "majority": info["majority"],
            "buy_ratio": info["buy_ratio"],
            "hold_ratio": info["hold_ratio"],
            "sell_ratio": info["sell_ratio"],
            "region": ticker_region,
            "advice": ticker_advice,
        }

    return JSONResponse(
        content={
            "config": {
                "weights_7d": dict(weights_7d),
                "region": region,
                "source": "fixture_signal_distribution_per_ticker",
                "version": "5.31.0",
            },
            "per_ticker": per_ticker,
        }
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "dashboard_api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
    )