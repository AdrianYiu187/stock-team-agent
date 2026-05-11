#!/usr/bin/env python3
"""
P16: 置信度加權倉位計算引擎
根據分析置信度和評分，計算建議倉位大小
"""

def calculate_position_size(
    ticker: str,
    confidence: float,
    final_score: float,
    account_size: float = 100000.0,
    risk_per_trade: float = 0.02
) -> dict:
    """
    根據置信度和評分計算建議倉位
    
    策略矩陣：
    - 高置信度(>0.7) + 高評分(>0.7) → 重倉 20-30%
    - 高置信度 + 中評分(0.5-0.7) → 標準+ 15-20%
    - 中置信度(0.4-0.7) + 高評分 → 標準+ 15-20%
    - 中置信度 + 中評分 → 標準 10-15%
    - 低置信度(<0.4) 或 低評分(<0.5) → 輕倉 <5%
    - 極低評分(<0.3) → 空倉 0%
    """
    # 基礎倉位矩陣
    if confidence > 0.7 and final_score > 0.7:
        base_pct = 0.25  # 25%
        signal = "heavy"
    elif confidence > 0.7 and final_score > 0.5:
        base_pct = 0.175  # 17.5%
        signal = "standard_plus"
    elif confidence > 0.4 and final_score > 0.7:
        base_pct = 0.175  # 17.5%
        signal = "standard_plus"
    elif confidence > 0.4 and final_score > 0.5:
        base_pct = 0.125  # 12.5%
        signal = "standard"
    elif confidence > 0.4 and final_score > 0.3:
        base_pct = 0.05  # 5%
        signal = "light"
    elif final_score > 0.3:
        base_pct = 0.02  # 2%
        signal = "speculative"
    else:
        base_pct = 0.0
        signal = "avoid"
    
    # 置信度調整因子（對倉位進行微調）
    conf_factor = 0.5 + (confidence * 0.5)  # 0.5-1.0
    final_pct = base_pct * conf_factor
    final_pct = min(0.40, max(0.0, final_pct))  # 上限 40%
    
    dollar_amount = account_size * final_pct
    risk_amount = account_size * risk_per_trade
    
    return {
        "position_size_pct": round(final_pct * 100, 2),
        "dollar_amount": round(dollar_amount, 2),
        "risk_amount": round(risk_amount, 2),
        "signal": signal,
        "confidence": confidence,
        "final_score": final_score,
        "account_size": account_size
    }


def format_position_report(ps: dict) -> str:
    """格式化倉位報告"""
    sig_emoji = {"heavy": "🔵", "standard_plus": "🟢", "standard": "🟡", 
                 "light": "🟠", "speculative": "🔴", "avoid": "⛔"}
    emoji = sig_emoji.get(ps["signal"], "⚪")
    return (
        f"{emoji} 倉位建議: {ps['position_size_pct']:.1f}% "
        f"(${ps['dollar_amount']:,.0f})\n"
        f"   信心水平: {ps['confidence']:.0%} | 評分: {ps['final_score']:.2f}"
    )


if __name__ == "__main__":
    # 測試用例
    test_cases = [
        ("AAPL", 0.85, 0.78),
        ("TSLA", 0.55, 0.62),
        ("NVDA", 0.30, 0.40),
        ("UNKNOWN", 0.20, 0.25),
    ]
    for ticker, conf, score in test_cases:
        r = calculate_position_size(ticker, conf, score)
        print(f"{ticker}: conf={conf:.2f} score={score:.2f} → {r['position_size_pct']:.1f}% ({r['signal']})")
