"""v5.27 Step 2 — FastAPI 後端,串接 dashboard 與 run_cross_market_comparison。

提供:
- GET /api/cross_market?close_source=real|mock → cross-market backtest 結果
- GET /api/health → 健康檢查
- GET /api/config → 當前 MULTIFACTOR_WEIGHTS + close_source 預設

啟動:
    cd ~/stock-team-agent
    uvicorn scripts.dashboard_api:app --reload --port 8080

前端串接:
    fetch('http://localhost:8080/api/cross_market?close_source=real')
      .then(r => r.json()).then(render)

TDD: scripts/tests/test_dashboard_api.py 5 個 guards
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
    run_cross_market_comparison,
)


# ============================================================================
# FastAPI app
# ============================================================================

app = FastAPI(
    title="Stock Team Agent — Operator Dashboard API",
    description="v5.27 — fund_heavy weights + real close prices backtest",
    version="5.27.0",
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
        version="5.27.0",
        weights=dict(MULTIFACTOR_WEIGHTS),
    )


@app.get("/api/config", response_model=dict)
def config() -> dict:
    """當前 MULTIFACTOR_WEIGHTS + close_source 預設。"""
    return {
        "weights": dict(MULTIFACTOR_WEIGHTS),
        "close_source_default": "real",
        "available_close_sources": ["mock", "real"],
        "version": "5.27.0",
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