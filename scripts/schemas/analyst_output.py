"""
Pydantic models for analyst output validation.

Each analyst (Technical, Fundamental, Risk, Sentiment, Market, Macro)
returns data conforming to these schemas.
"""

from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class AnalystOutput(BaseModel):
    """Base model for all analyst outputs."""
    analyst: str = Field(..., description="Analyst identifier (e.g., 'technical')")
    timestamp: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall score 0-1")
    buy_score: float = Field(..., ge=0.0, le=1.0, description="Buy probability 0-1")
    hold_score: float = Field(..., ge=0.0, le=1.0, description="Hold probability 0-1")
    sell_score: float = Field(..., ge=0.0, le=1.0, description="Sell probability 0-1")
    signal: str = Field(..., description="Signal: buy/sell/neutral/strong_buy/strong_sell")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0-1")
    summary: str = Field(..., description="Human-readable summary")
    
    # Analyst-specific data (flexible)
    indicators: Optional[dict[str, Any]] = Field(default=None, description="Technical indicators")
    financials: Optional[dict[str, Any]] = Field(default=None, description="Financial metrics")
    risk_data: Optional[dict[str, Any]] = Field(default=None, description="Risk metrics")
    news_data: Optional[list[dict]] = Field(default=None, description="News articles")
    market_data: Optional[dict[str, Any]] = Field(default=None, description="Market data")
    macro_data: Optional[dict[str, Any]] = Field(default=None, description="Macro data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "analyst": "technical",
                "score": 0.72,
                "buy_score": 0.65,
                "hold_score": 0.30,
                "sell_score": 0.05,
                "signal": "buy",
                "confidence": 0.78,
                "summary": "RSI oversold, MACD bullish crossover, price above 20 SMA"
            }
        }


class TechnicalIndicators(BaseModel):
    """Technical indicator values."""
    sma20: Optional[float] = Field(None, description="20-day SMA")
    sma50: Optional[float] = Field(None, description="50-day SMA")
    sma200: Optional[float] = Field(None, description="200-day SMA")
    ema12: Optional[float] = Field(None, description="12-day EMA")
    ema26: Optional[float] = Field(None, description="26-day EMA")
    rsi: Optional[float] = Field(None, ge=0, le=100, description="RSI 0-100")
    macd: Optional[float] = Field(None, description="MACD value")
    macd_signal: Optional[float] = Field(None, description="MACD signal line")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram")
    boll_upper: Optional[float] = Field(None, description="Bollinger upper band")
    boll_middle: Optional[float] = Field(None, description="Bollinger middle band")
    boll_lower: Optional[float] = Field(None, description="Bollinger lower band")
    atr: Optional[float] = Field(None, description="Average True Range")
    volume: Optional[int] = Field(None, description="Trading volume")
    price: Optional[float] = Field(None, description="Current price")


class FundamentalMetrics(BaseModel):
    """Fundamental financial metrics."""
    revenue: Optional[float] = Field(None, description="Total revenue")
    net_income: Optional[float] = Field(None, description="Net income")
    total_assets: Optional[float] = Field(None, description="Total assets")
    total_equity: Optional[float] = Field(None, description="Total equity")
    debt_to_equity: Optional[float] = Field(None, ge=0, description="D/E ratio")
    current_ratio: Optional[float] = Field(None, ge=0, description="Current ratio")
    roe: Optional[float] = Field(None, ge=0, description="Return on Equity")
    roa: Optional[float] = Field(None, ge=0, description="Return on Assets")
    eps: Optional[float] = Field(None, description="Earnings per share")
    pe_ratio: Optional[float] = Field(None, ge=0, description="P/E ratio")
    pb_ratio: Optional[float] = Field(None, ge=0, description="P/B ratio")
    dividend_yield: Optional[float] = Field(None, ge=0, description="Dividend yield")
    revenue_growth: Optional[float] = Field(None, description="Revenue growth %")
    profit_growth: Optional[float] = Field(None, description="Profit growth %")


class RiskMetrics(BaseModel):
    """Risk assessment metrics."""
    volatility: Optional[float] = Field(None, ge=0, le=1, description="Volatility 0-1")
    beta: Optional[float] = Field(None, ge=0, description="Beta vs market")
    var_95: Optional[float] = Field(None, description="Value at Risk 95%")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[float] = Field(None, ge=0, description="Max drawdown %")
    debt_to_equity: Optional[float] = Field(None, ge=0, description="Leverage")
    risk_level: str = Field(default="medium", description="low/medium/high")


class SentimentData(BaseModel):
    """News and sentiment data."""
    news_count: int = Field(0, description="Number of news articles")
    positive_count: int = Field(0, description="Positive articles")
    negative_count: int = Field(0, description="Negative articles")
    neutral_count: int = Field(0, description="Neutral articles")
    avg_sentiment: float = Field(0, ge=-1, le=1, description="Average sentiment -1 to +1")
    sentiment_label: str = Field("neutral", description="overall/neutral/positive/negative")
    articles: list[dict] = Field(default_factory=list, description="News articles")


class MarketData(BaseModel):
    """Market context data."""
    price: Optional[float] = Field(None, description="Current price")
    ytd_return: Optional[float] = Field(None, description="Year-to-date return %")
    pe_ratio: Optional[float] = Field(None, ge=0, description="P/E ratio")
    market_cap: Optional[float] = Field(None, description="Market cap")
    sector: Optional[str] = Field(None, description="Sector")


class MacroData(BaseModel):
    """Macroeconomic context."""
    us_10y_yield: Optional[float] = Field(None, description="US 10Y yield %")
    vix: Optional[float] = Field(None, ge=0, description="VIX volatility index")
    gold: Optional[float] = Field(None, description="Gold price")
    dxy: Optional[float] = Field(None, description="US Dollar Index")
    risk_sentiment: str = Field("neutral", description="risk_on/risk_off/neutral")
