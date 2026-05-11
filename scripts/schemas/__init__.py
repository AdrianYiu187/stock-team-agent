"""
Stock Team Agent Pydantic Schemas & 5-Tier Rating System

Design principles:
1. All analyst outputs validated with Pydantic models
2. Unified signal vocabulary (5-tier)
3. Score normalization (0-1 for all)
4. Type-safe consensus building

5-Tier Rating System:
    STRONG_BUY  (5): Score 0.85-1.00 - 強烈買入
    BUY         (4): Score 0.65-0.84 - 適度買入  
    HOLD        (3): Score 0.45-0.64 - 持有觀望
    SELL        (2): Score 0.25-0.44 - 適度賣出
    STRONG_SELL (1): Score 0.00-0.24 - 強烈賣出

Usage:
    from schemas import AnalystOutput, ConsensusResult, FiveTierRating
    
    # Validate analyst output
    output = AnalystOutput(**raw_data)
    
    # Convert score to tier
    tier = FiveTierRating.from_score(output.score)
"""

from .analyst_output import (
    AnalystOutput,
    TechnicalIndicators,
    FundamentalMetrics,
    RiskMetrics,
    SentimentData,
    MarketData,
    MacroData,
)
from .consensus import (
    ConsensusResult,
    AnalystScores,
    WeightedScores,
    ConflictRecord,
)
from .ratings import (
    FiveTierRating,
    SignalType,
    Confidence,
    Recommendation,
)
from .decision_log import DecisionLogger

__all__ = [
    # Analyst Output
    "AnalystOutput",
    "TechnicalIndicators",
    "FundamentalMetrics",
    "RiskMetrics",
    "SentimentData",
    "MarketData",
    "MacroData",
    # Consensus
    "ConsensusResult",
    "AnalystScores",
    "WeightedScores",
    "ConflictRecord",
    # Ratings
    "FiveTierRating",
    "SignalType",
    "Confidence",
    "Recommendation",
    # Decision Log
    "DecisionLogger",
]
