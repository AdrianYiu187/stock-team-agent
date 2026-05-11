"""
Pydantic models for consensus building and final results.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class AnalystScores(BaseModel):
    """Scores from a single analyst."""
    buy: float = Field(..., ge=0.0, le=1.0, description="Buy probability 0-1")
    hold: float = Field(..., ge=0.0, le=1.0, description="Hold probability 0-1")
    sell: float = Field(..., ge=0.0, le=1.0, description="Sell probability 0-1")
    overall: float = Field(..., ge=0.0, le=1.0, description="Overall normalized score 0-1")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0-1")


class WeightedScores(BaseModel):
    """Consensus weighted scores across all analysts."""
    buy: float = Field(..., ge=0.0, le=1.0, description="Weighted buy score")
    hold: float = Field(..., ge=0.0, le=1.0, description="Weighted hold score")
    sell: float = Field(..., ge=0.0, le=1.0, description="Weighted sell score")
    
    @property
    def total(self) -> float:
        """Total should sum to 1.0"""
        return self.buy + self.hold + self.sell


class ConflictRecord(BaseModel):
    """Record of disagreement between analysts."""
    type: str = Field(..., description="Conflict type: buy_vs_sell, high_divergence, etc.")
    analysts_involved: list[str] = Field(..., description="Analyst names")
    details: str = Field(..., description="Conflict description")
    severity: str = Field(..., description="high/medium/low")
    resolution: Optional[str] = Field(None, description="How conflict was resolved")


class ConsensusResult(BaseModel):
    """Final consensus result combining all analysts.
    
    This is the output of ConsensusEngine.integrate().
    """
    symbol: str = Field(..., description="Stock ticker")
    task_type: str = Field(default="stock_analysis", description="Analysis type")
    timestamp: datetime = Field(default_factory=datetime.now, description="Analysis time")
    
    # Per-analyst breakdown
    analyst_scores: dict[str, AnalystScores] = Field(
        ..., description="Scores from each analyst"
    )
    
    # Weighted consensus
    weighted_scores: WeightedScores = Field(
        ..., description="Consensus weighted scores"
    )
    
    # Percentage breakdown
    consensus_pct: dict[str, float] = Field(
        ..., description="Consensus as percentages: {buy: 45.0, hold: 30.0, sell: 25.0}"
    )
    
    # Overall score (-100 to +100)
    overall_score: float = Field(
        ..., ge=-100.0, le=100.0,
        description="Overall score: -100 (strong sell) to +100 (strong buy)"
    )
    
    # Conflicts detected
    conflicts: list[ConflictRecord] = Field(
        default_factory=list, description="Analyst disagreements"
    )
    
    # Final recommendation
    recommendation: str = Field(
        ..., description="Chinese recommendation: 強烈買入/適度買入/持有觀望/etc."
    )
    signal_strength: int = Field(
        ..., ge=1, le=5,
        description="5-tier signal: 1=STRONG_SELL, 2=SELL, 3=HOLD, 4=BUY, 5=STRONG_BUY"
    )
    
    # Confidence
    confidence: float = Field(..., ge=0.0, le=1.0, description="Consensus confidence 0-1")
    confidence_label: str = Field(..., description="high/medium/low")
    
    # Status
    status: str = Field(default="success", description="success/warning/error")
    errors: list[str] = Field(default_factory=list, description="Any errors")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump()
    
    def to_markdown(self) -> str:
        """Format as readable markdown."""
        signal_emojis = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "🟢"}
        emoji = signal_emojis.get(self.signal_strength, "⚪")
        
        lines = [
            f"# 📊 共識分析結果: {self.symbol}\n",
            f"**時間**: {self.timestamp.strftime('%Y-%m-%d %H:%M')}\n",
            f"\n",
            f"{emoji} **{self.recommendation}** (信心: {self.confidence_label})\n",
            f"\n",
            f"## 各分析師評分\n",
            f"| 分析師 | 買入 | 持有 | 賣出 | 信心 |\n",
            f"|--------|------|------|------|------|\n",
        ]
        
        for analyst, scores in self.analyst_scores.items():
            lines.append(
                f"| {analyst} | {scores.buy:.0%} | {scores.hold:.0%} | {scores.sell:.0%} | {scores.confidence:.0%} |\n"
            )
        
        lines.extend([
            f"\n",
            f"## 共識加權\n",
            f"- 買入: {self.weighted_scores.buy:.1%}\n",
            f"- 持有: {self.weighted_scores.hold:.1%}\n",
            f"- 賣出: {self.weighted_scores.sell:.1%}\n",
            f"\n",
            f"**綜合評分**: {self.overall_score:+.0f} / 100\n",
        ])
        
        if self.conflicts:
            lines.append(f"\n## ⚠️ 分析師分歧\n")
            for conflict in self.conflicts:
                lines.append(f"- [{conflict.severity.upper()}] {conflict.type}: {conflict.details}\n")
        
        return "".join(lines)
