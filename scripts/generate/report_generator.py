"""
Stock_Team_Agent Report Generator
=================================
v5 Professional Investment Report Format.

Current state: Framework only.
The actual stock_analysis.py (992 lines) is a monolithic script that
interleaves data fetching + report generation + WhatsApp sending.
Future: Extract report generation into this module while keeping
stock_analysis.py as the CLI entry point.

Report Format (v5 professional investment style):
  1. Header: Stock code, name, price, change
  2. Technical: RSI, Bollinger, volume, support/resistance
  3. Fundamental: P/E, P/B, ROE, debt/equity
  4. Market: YTD return, 52-week position, relative performance
  5. Risk: Volatility, VaR, Sharpe ratio
  6. Sentiment: News score, social metrics
  7. Consensus: Buy/Hold/Sell with confidence
  8. Short/Mid/Long-term targets
  9. 7-class risk assessment
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class ReportConfig:
    """Configuration for stock report generation."""
    output_dir: str = "~/.hermes/task_outputs"
    send_whatsapp: bool = False
    league_emoji: str = "📈"
    confidence_threshold: float = 0.6


@dataclass 
class StockReport:
    """Structured stock analysis report."""
    code: str
    name: str
    timestamp: str
    price: float = 0.0
    change_pct: float = 0.0
    technical: Dict[str, Any] = field(default_factory=dict)
    fundamental: Dict[str, Any] = field(default_factory=dict)
    market: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    sentiment: Dict[str, Any] = field(default_factory=dict)
    consensus: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    confidence: float = 0.0
    short_term: str = ""
    mid_term: str = ""
    long_term: str = ""
    sections: List[str] = field(default_factory=list)


def build_report(
    code: str,
    name: str,
    price: float,
    change_pct: float,
    analyst_results: Dict[str, Dict],
    config: Optional[ReportConfig] = None,
) -> StockReport:
    """
    Build a structured StockReport from analyst results.
    
    This will be the extracted version of stock_analysis.py report generation.
    Currently a framework — real implementation pending.
    """
    config = config or ReportConfig()
    report = StockReport(
        code=code,
        name=name,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        price=price,
        change_pct=change_pct,
    )
    
    # Map analyst results to report sections
    if "technical" in analyst_results:
        report.technical = analyst_results["technical"]
    if "fundamental" in analyst_results:
        report.fundamental = analyst_results["fundamental"]
    if "market" in analyst_results:
        report.market = analyst_results["market"]
    if "risk" in analyst_results:
        report.risk = analyst_results["risk"]
    if "sentiment" in analyst_results:
        report.sentiment = analyst_results["sentiment"]
    
    return report


def to_telegram_text(report: StockReport) -> str:
    """
    Format stock report as Telegram Markdown.
    
    Matches the v5 professional investment format.
    """
    lines = []
    emoji = "📈" if report.change_pct >= 0 else "📉"
    sign = "+" if report.change_pct >= 0 else ""
    lines.append(f"{emoji} *{report.code}* — {report.name}")
    lines.append(f"💰 ${report.price:.2f} ({sign}{report.change_pct:.2f}%)")
    lines.append("")
    
    # Technical
    tech = report.technical
    if tech:
        rsi = tech.get("rsi", "N/A")
        lines.append(f"▎技術面: RSI {rsi}")
    
    # Fundamental
    fund = report.fundamental
    if fund:
        pe = fund.get("pe_ratio", "N/A")
        lines.append(f"▎基本面: P/E {pe}")
    
    # Consensus
    cons = report.consensus
    if cons:
        signal = cons.get("signal", "N/A")
        conf = cons.get("confidence", 0)
        lines.append(f"▎共識: {signal} (置信度 {conf:.0%})")
    
    # Recommendation
    if report.recommendation:
        lines.append("")
        lines.append(f"🎯 *{report.recommendation}*")
    
    return "\n".join(lines)


def to_whatsapp_text(report: StockReport) -> str:
    """Format stock report as plain text for WhatsApp."""
    emoji = "📈" if report.change_pct >= 0 else "📉"
    sign = "+" if report.change_pct >= 0 else ""
    lines = [
        f"{emoji} {report.code} — {report.name}",
        f"💰 ${report.price:.2f} ({sign}{report.change_pct:.2f}%)",
        f"🎯 {report.recommendation}" if report.recommendation else "",
    ]
    return "\n".join([l for l in lines if l])
