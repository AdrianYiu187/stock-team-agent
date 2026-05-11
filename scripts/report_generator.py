#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析報告生成器 (P8)
Stock Team Agent - 結構化報告輸出模組

功能：
- 接收 stock_analysis.py 的完整分析結果
- 生成 Markdown 格式報告
- 生成 ASCII 雷達圖（7 維度）

作者：Stock Team Agent
版本：1.0.0
"""

import os
import datetime
from pathlib import Path
from typing import Dict, Optional

# ============================================================================
# 常數定義
# ============================================================================

# 輸出目錄
OUTPUT_DIR = Path.home() / ".hermes" / "stock_outputs"

# 雷達圖 7 維度（順時針排列）
RADAR_DIMENSIONS = [
    "market",      # 市場維度
    "technical",   # 技術維度
    "fundamental", # 基本面維度
    "risk",        # 風險維度
    "sentiment",   # 情緒維度
    "news",        # 新聞維度
    "macro"        # 巨觀維度
]

# 維度標籤（用於雷達圖顯示）
DIMENSION_LABELS = {
    "market": "市場",
    "technical": "技術",
    "fundamental": "基本面",
    "risk": "風險",
    "sentiment": "情緒",
    "news": "新聞",
    "macro": "巨觀"
}

# 建議標籤
RECOMMENDATION_LABELS = {
    "BUY": "買入",
    "HOLD": "持有",
    "SELL": "賣出"
}


# ============================================================================
# 輔助函數
# ============================================================================

def _get_date_str() -> str:
    """取得目前日期字串（YYYY-MM-DD 格式）"""
    return datetime.date.today().strftime("%Y-%m-%d")


def _normalize_score(score: float) -> float:
    """
    將分數正規化到 0-1 範圍
    
    Args:
        score: 原始分數
        
    Returns:
        正規化後的分數（0-1）
    """
    if score < 0:
        return 0.0
    elif score > 1:
        return 1.0
    return score


def _score_to_level(score: float) -> str:
    """
    將分數轉換為建議等級
    
    Args:
        score: 正規化分數（0-1）
        
    Returns:
        BUY / HOLD / SELL
    """
    if score >= 0.65:
        return "BUY"
    elif score >= 0.45:
        return "HOLD"
    else:
        return "SELL"


def _ensure_output_dir() -> None:
    """確保輸出目錄存在"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# ASCII 雷達圖生成
# ============================================================================

def ascii_radar_chart(scores: Dict[str, float]) -> str:
    """
    生成 ASCII 格式的 7 維度雷達圖
    
    雷達圖佈局（7 軸）：
            BUY (軸1)
             A
            /|\\  ← 7軸放射狀排列
           / | \\
          ───+───→ SELL (軸4)
           \\ | /
            \\|/
             V
           HOLD (軸7)
    
    Args:
        scores: 維度分數字典，格式如 {"market": 0.8, "technical": 0.6, ...}
        
    Returns:
        ASCII 雷達圖字串
    """
    # 確保所有維度都有分數（預設 0.5）
    normalized_scores = {}
    for dim in RADAR_DIMENSIONS:
        raw_score = scores.get(dim, 0.5)
        normalized_scores[dim] = _normalize_score(raw_score)
    
    # 計算每個維度的「建議」
    dimension_advice = {}
    for dim, score in normalized_scores.items():
        dimension_advice[dim] = _score_to_level(score)
    
    # 取得主要建議（平均分數）
    avg_score = sum(normalized_scores.values()) / len(normalized_scores)
    main_recommendation = _score_to_level(avg_score)
    
    # 雷達圖半徑（字符數）
    max_radius = 6
    
    # 將 7 維度映射到 7 個方向
    # 軸1: market (上方, 90度)
    # 軸2: technical (右上, 45度)
    # 軸3: fundamental (右下, 315度)
    # 軸4: risk (下方, 270度)
    # 軸5: sentiment (左下, 225度)
    # 軸6: news (左上, 135度)
    # 軸7: macro (左方, 180度)
    
    # 預先計算每個維度在每個半徑位置的角度
    # 角度對應（度）：market=90, technical=45, fundamental=315, risk=270, sentiment=225, news=135, macro=180
    
    def get_point(radius: float, angle_deg: float) -> tuple:
        """根據半徑和角度取得點座標"""
        import math
        angle_rad = math.radians(angle_deg)
        x = radius * math.cos(angle_rad)
        y = radius * math.sin(angle_rad)
        return (x, y)
    
    # 建立網格（15x15 字符）
    grid_size = 15
    center = grid_size // 2
    
    # 初始化網格
    grid = [[" " for _ in range(grid_size)] for _ in range(grid_size)]
    
    # 填充邊界和軸線
    angles = {
        "market": 90,
        "technical": 45,
        "fundamental": 315,
        "risk": 270,
        "sentiment": 225,
        "news": 135,
        "macro": 180
    }
    
    # 繪製每個維度的軸線和分數點
    for dim, angle_deg in angles.items():
        score = normalized_scores[dim]
        score_radius = 1 + score * (max_radius - 1)  # 1 到 max_radius
        
        # 繪製從中心到邊緣的線
        for r in range(1, max_radius + 1):
            x, y = get_point(float(r), angle_deg)
            grid_x = int(round(center + x))
            grid_y = int(round(center - y))  # Y軸反轉（上方為正）
            
            if 0 <= grid_x < grid_size and 0 <= grid_y < grid_size:
                if r == max_radius:
                    # 邊緣放置維度標籤
                    label = DIMENSION_LABELS[dim]
                    grid[grid_y] = grid[grid_y][:grid_x] + [f"{label}({int(score*100)}%)"] + grid[grid_y][grid_x+1:]
                elif r == 1:
                    # 中心點
                    grid[grid_y][grid_x] = "+"
                elif r == int(score_radius):
                    # 分數位置
                    advice = dimension_advice[dim][:1]  # B/H/S
                    grid[grid_y][grid_x] = advice
    
    # 繪製多邊形連線（分數區域）
    points = []
    for dim in RADAR_DIMENSIONS:
        score = normalized_scores[dim]
        angle_deg = angles[dim]
        score_radius = 1 + score * (max_radius - 1)
        x, y = get_point(score_radius, angle_deg)
        points.append((int(round(center + x)), int(round(center - y))))
    
    # 連接多邊形頂點
    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        
        # 繪製線段
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        steps = max(abs(dx), abs(dy))
        
        if steps > 0:
            for step in range(steps + 1):
                x = int(p1[0] + (dx * step / steps))
                y = int(p1[1] + (dy * step / steps))
                if 0 <= x < grid_size and 0 <= y < grid_size:
                    if grid[y][x] == " ":
                        grid[y][x] = "*"
    
    # 轉換為字串
    lines = []
    for row in grid:
        lines.append("".join(row))
    
    # 組裝最終輸出
    output_lines = [
        "```",
        "       [ 7 維度綜合評分雷達圖 ]",
        "```",
        "```",
        "",
        f"   建議: {main_recommendation} ({RECOMMENDATION_LABELS[main_recommendation]})  平均分數: {avg_score:.1%}",
        "",
        "   維度分數:",
    ]
    
    for dim in RADAR_DIMENSIONS:
        score = normalized_scores[dim]
        advice = dimension_advice[dim]
        label = DIMENSION_LABELS[dim]
        bar_len = int(score * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        output_lines.append(f"     {label:8s}: {bar} {score:.0%}  → {advice}")
    
    output_lines.extend([
        "",
        "   圖例:",
        "     B = BUY (買入, ≥65%)",
        "     H = HOLD (持有, 45-65%)",
        "     S = SELL (賣出, <45%)",
        "     * = 分數連線",
        "```"
    ])
    
    return "\n".join(output_lines)


# ============================================================================
# 報告生成
# ============================================================================

def _format_dict_section(title: str, data: dict, indent: int = 0) -> list:
    """
    格式化字典為 Markdown 列表區塊
    
    Args:
        title: 區塊標題
        data: 資料字典
        indent: 縮排層級
        
    Returns:
        Markdown 行列表
    """
    prefix = "  " * indent
    lines = [f"{prefix}**{title}**", ""]
    
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}- **{key}:**")
            lines.extend(_format_dict_section("", value, indent + 2))
        elif isinstance(value, float):
            lines.append(f"{prefix}- {key}: {value:.4f}")
        elif value is None:
            lines.append(f"{prefix}- {key}: N/A")
        else:
            lines.append(f"{prefix}- {key}: {value}")
    
    return lines


def _extract_scores_from_result(result: dict) -> dict:
    """
    從分析結果中提取各維度分數
    
    Args:
        result: stock_analysis.py 的完整分析結果
        
    Returns:
        維度分數字典
    """
    scores = {}
    
    # 嘗試從不同結構中提取分數
    # 結構1: 直接在頂層
    if "scores" in result:
        scores = result["scores"]
    # 結構2: 在 analysis 內
    elif "analysis" in result and isinstance(result["analysis"], dict):
        scores = result["analysis"].get("scores", {})
    # 結構3: 在各維度內
    else:
        for dim in RADAR_DIMENSIONS:
            if dim in result:
                dim_data = result[dim]
                if isinstance(dim_data, dict):
                    scores[dim] = dim_data.get("score", dim_data.get("value", 0.5))
                elif isinstance(dim_data, (int, float)):
                    scores[dim] = float(dim_data)
                else:
                    scores[dim] = 0.5
            else:
                scores[dim] = 0.5
    
    # 確保所有維度都有值
    for dim in RADAR_DIMENSIONS:
        if dim not in scores:
            scores[dim] = 0.5
    
    return scores


def _extract_recommendation(result: dict) -> str:
    """
    從分析結果中提取投資建議
    
    Args:
        result: 分析結果字典
        
    Returns:
        投資建議（BUY/HOLD/SELL）
    """
    # 嘗試不同的結構
    if "recommendation" in result:
        return result["recommendation"]
    elif "signal" in result:
        return result["signal"]
    elif "action" in result:
        return result["action"]
    elif "conclusion" in result and isinstance(result["conclusion"], dict):
        return result["conclusion"].get("recommendation", 
               result["conclusion"].get("signal", "HOLD"))
    else:
        return "HOLD"


def _extract_summary(result: dict) -> str:
    """
    從分析結果中提取摘要文字
    
    Args:
        result: 分析結果字典
        
    Returns:
        摘要文字
    """
    if "summary" in result:
        return result["summary"]
    elif "conclusion" in result and isinstance(result["conclusion"], dict):
        return result["conclusion"].get("summary", result["conclusion"].get("text", ""))
    elif "description" in result:
        return result["description"]
    else:
        return "分析完成"


def generate_analysis_report(result: dict, ticker: str) -> str:
    """
    生成股票分析 Markdown 報告
    
    Args:
        result: stock_analysis.py 的完整分析結果字典
        ticker: 股票代碼（如 AAPL, TSLA）
        
    Returns:
        生成的報告檔案路徑
    """
    # 確保輸出目錄存在
    _ensure_output_dir()
    
    # 取得日期
    date_str = _get_date_str()
    
    # 提取資料
    scores = _extract_scores_from_result(result)
    recommendation = _extract_recommendation(result)
    summary = _extract_summary(result)
    
    # 計算平均分數
    avg_score = sum(scores.values()) / len(scores)
    
    # 產生雷達圖
    radar_chart = ascii_radar_chart(scores)
    
    # 組裝報告
    report_lines = [
        "# 股票分析報告",
        "",
        f"**股票代碼:** {ticker}",
        f"**分析日期:** {date_str}",
        f"**報告產生:** {datetime.datetime.now().strftime('%H:%M:%S')}",
        "",
        "---",
        "",
        "## 投資建議",
        "",
        f"**{recommendation}**",
        "",
        f"> {RECOMMENDATION_LABELS.get(recommendation, '持有')} (建議等级: {recommendation})",
        f"> 綜合評分: {avg_score:.1%}",
        "",
        "---",
        "",
        "## 雷達圖分析",
        "",
        radar_chart,
        "",
        "---",
        "",
        "## 分析摘要",
        "",
        summary,
        "",
        "---",
        "",
        "## 詳細分析資料",
        "",
    ]
    
    # 加入所有分析結果（遞迴格式化）
    report_lines.extend(_format_dict_section("完整分析結果", result))
    
    # 頁尾
    report_lines.extend([
        "",
        "---",
        "",
        f"*本報告由 Stock Team Agent 自動生成*",
        f"*分析時間: {datetime.datetime.now().isoformat()}*"
    ])
    
    # 組合報告內容
    report_content = "\n".join(report_lines)
    
    # 寫入檔案
    output_file = OUTPUT_DIR / f"{ticker}_{date_str}.md"
    output_file.write_text(report_content, encoding="utf-8")
    
    return str(output_file)


# ============================================================================
# 主程式（測試用）
# ============================================================================

if __name__ == "__main__":
    # 測試用虛構資料
    test_result = {
        "ticker": "AAPL",
        "recommendation": "BUY",
        "summary": "蘋果公司股價顯示強勁的上漲動能，基本面良好，技術面多頭排列。",
        "scores": {
            "market": 0.85,
            "technical": 0.78,
            "fundamental": 0.82,
            "risk": 0.35,
            "sentiment": 0.75,
            "news": 0.70,
            "macro": 0.65
        },
        "analysis": {
            "market": {"score": 0.85, "trend": "bullish"},
            "technical": {"score": 0.78, "signal": "strong_buy"},
            "fundamental": {"score": 0.82, "pe_ratio": 28.5},
            "risk": {"score": 0.35, "volatility": "low"},
            "sentiment": {"score": 0.75, "social_positive": True},
            "news": {"score": 0.70, "headlines": 15},
            "macro": {"score": 0.65, "rate_impact": "neutral"}
        }
    }
    
    print("測試報告生成...")
    output_path = generate_analysis_report(test_result, "AAPL")
    print(f"✅ 報告已生成: {output_path}")
    print()
    print("=" * 60)
    print("雷達圖預覽:")
    print("=" * 60)
    print(ascii_radar_chart(test_result["scores"]))
