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


# ============================================================================
# FastAPI app
# ============================================================================

app = FastAPI(
    title="Stock Team Agent — Operator Dashboard API",
    description="v5.28 — fund_heavy 4D + 7D 整合層 (sentiment+news+macro)",
    version="5.28.0",
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
        version="5.28.0",
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
            "close_source_default": "real",
            "available_close_sources": ["mock", "real"],
            "version": "5.30.0"
        }
    """
    return {
        "weights_4d": dict(MULTIFACTOR_WEIGHTS),
        "weights_7d": dict(MULTIFACTOR_WEIGHTS_7D),
        "weights_7d_fallback": dict(MULTIFACTOR_WEIGHTS_7D_FALLBACK),
        "close_source_default": "real",
        "available_close_sources": ["mock", "real"],
        "version": "5.30.0",
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
) -> JSONResponse:
    """v5.28 P2 — 7D 整合 composite per ticker。

    直接從 fixture `signal_distribution_per_ticker[t].components` 取 7 維度預計算分數,
    套用 `MULTIFACTOR_WEIGHTS_7D` 加權, 輸出 composite + signal + 各維度分數。

    Response shape:
        {
            "config": {
                "weights_7d": {...},
                "source": "fixture_signal_distribution_per_ticker",
                "version": "5.28.0"
            },
            "per_ticker": {
                "AAPL": {
                    "tech": 0.5, "fund": 0.5914, "market": 0.5, "risk": 0.5,
                    "sentiment": 0.5167, "news": 0.5, "macro": 0.463,
                    "composite_7d": 0.5285,
                    "signal": "HOLD",
                    "majority": "buy",
                    "buy_ratio": 0.3815, "hold_ratio": 0.3092, "sell_ratio": 0.3092
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
        composite_7d = apply_7d_weights(components_7d)
        # 與 4D 共用 signal threshold (composite_to_signal: >0.58 BUY / <0.45 SELL / else HOLD)
        if composite_7d > 0.58:
            signal = "BUY"
        elif composite_7d < 0.45:
            signal = "SELL"
        else:
            signal = "HOLD"

        per_ticker[ticker] = {
            **components_7d,
            "composite_7d": composite_7d,
            "signal": signal,
            "majority": info["majority"],
            "buy_ratio": info["buy_ratio"],
            "hold_ratio": info["hold_ratio"],
            "sell_ratio": info["sell_ratio"],
        }

    return JSONResponse(
        content={
            "config": {
                "weights_7d": dict(MULTIFACTOR_WEIGHTS_7D),
                "source": "fixture_signal_distribution_per_ticker",
                "version": "5.28.0",
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