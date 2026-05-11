"""
5-Tier Rating System for Stock Team Agent

Provides unified signal vocabulary across all analysts.
"""

from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SignalType(IntEnum):
    """5-tier signal system matching international standards."""
    STRONG_SELL = 1
    SELL = 2
    HOLD = 3
    BUY = 4
    STRONG_BUY = 5
    
    @property
    def label(self) -> str:
        """Chinese label for signal."""
        labels = {
            1: "強烈賣出",
            2: "適度賣出",
            3: "持有觀望",
            4: "適度買入",
            5: "強烈買入",
        }
        return labels[self.value]
    
    @property
    def emoji(self) -> str:
        """Visual indicator."""
        emojis = {
            1: "🔴",
            2: "🟠",
            3: "🟡",
            4: "🟢",
            5: "🟢",
        }
        return emojis[self.value]
    
    @property
    def signal_name(self) -> str:
        """Compatible signal name for legacy systems."""
        names = {
            1: "strong_sell",
            2: "sell",
            3: "hold",
            4: "buy",
            5: "strong_buy",
        }
        return names[self.value]
    
    @classmethod
    def from_score(cls, score: float) -> "SignalType":
        """Convert 0-1 score to 5-tier signal.
        
        Args:
            score: Score between 0.0 and 1.0
            
        Returns:
            SignalType enum value
        """
        if score >= 0.85:
            return cls.STRONG_BUY
        elif score >= 0.65:
            return cls.BUY
        elif score >= 0.45:
            return cls.HOLD
        elif score >= 0.25:
            return cls.SELL
        else:
            return cls.STRONG_SELL


class Confidence(BaseModel):
    """Confidence score with metadata."""
    value: float = Field(..., ge=0.0, le=1.0, description="Confidence 0-1")
    level: str = Field(..., description="high/medium/low")
    data_quality: str = Field(default="normal", description="normal/poor/excellent")
    sample_size: Optional[int] = Field(None, description="N of data points used")
    
    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid = {"high", "medium", "low"}
        if v not in valid:
            raise ValueError(f"level must be one of {valid}")
        return v
    
    @classmethod
    def from_score(cls, score: float, **kwargs) -> "Confidence":
        """Create from raw confidence score."""
        if score >= 0.75:
            level = "high"
        elif score >= 0.50:
            level = "medium"
        else:
            level = "low"
        return cls(value=score, level=level, **kwargs)


class FiveTierRating(BaseModel):
    """Complete 5-tier rating with score and confidence."""
    signal: SignalType = Field(..., description="5-tier signal")
    score: float = Field(..., ge=0.0, le=1.0, description="Raw score 0-1")
    confidence: Confidence = Field(..., description="Confidence assessment")
    target_price: Optional[float] = Field(None, description="Price target if available")
    upside_percent: Optional[float] = Field(None, description="Upside/downside %")
    
    @property
    def label(self) -> str:
        """Chinese label."""
        return self.signal.label
    
    @property
    def emoji(self) -> str:
        """Visual indicator."""
        return self.signal.emoji
    
    @property
    def is_actionable(self) -> bool:
        """Whether signal warrants action (not HOLD)."""
        return self.signal != SignalType.HOLD
    
    @classmethod
    def from_analyst_score(
        cls,
        score: float,
        confidence_score: float = 0.5,
        **kwargs
    ) -> "FiveTierRating":
        """Create rating from analyst score and confidence."""
        return cls(
            signal=SignalType.from_score(score),
            score=score,
            confidence=Confidence.from_score(confidence_score),
            **kwargs
        )


class Recommendation(BaseModel):
    """Final investment recommendation."""
    action: SignalType = Field(..., description="5-tier recommended action")
    rationale: str = Field(..., description="Why this action")
    risks: list[str] = Field(default_factory=list, description="Key risks")
    timeframe: str = Field(default="3-6 months", description="Investment horizon")
    caveats: list[str] = Field(default_factory=list, description="Important caveats")
    
    def to_markdown(self) -> str:
        """Format as markdown string."""
        lines = [
            f"# 📊 投資建議\n",
            f"**行動**: {self.action.emoji} {self.action.label}\n",
            f"**理由**: {self.rationale}\n",
        ]
        if self.risks:
            lines.append(f"\n**主要風險**:\n")
            for risk in self.risks:
                lines.append(f"- {risk}\n")
        if self.caveats:
            lines.append(f"\n**注意事項**:\n")
            for caveat in self.caveats:
                lines.append(f"- {caveat}\n")
        lines.append(f"\n**時間範圍**: {self.timeframe}\n")
        return "".join(lines)
