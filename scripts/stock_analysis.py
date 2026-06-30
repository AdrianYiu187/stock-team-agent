#!/usr/bin/env python3

import logging
import atexit
import os
import sys
import argparse
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# v5.8: 動態 progress 日誌路徑（用 tempfile.NamedTemporaryFile 而非 /tmp 硬編碼）
import tempfile as _tempfile
_LOG_FILE = os.path.join(_tempfile.gettempdir(), "stock_analysis_progress.txt")

def _log(msg):
    try:
        with open(_LOG_FILE, "a") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass  # 日誌失敗不影響主流程


# ============================================================
# v5.4: 純函數提取（unit-testable）
# ============================================================
def score_to_bhs(score: float) -> Dict[str, float]:
    """將 0..1 的 overall score 映射到 buy/hold/sell 比例。

    v5.13 (P36c-bhs) 連續化: 用 sigmoid 軟切取代 score=0.5 hard 分段。

    設計：
        buy_strength = sigmoid(score, midpoint=0.5, k=12) ∈ (0, 1)
        sell_strength = 1 - buy_strength（buy/sell 對稱）
        hold = 1 - max(buy_strength, sell_strength)  ← 中段低、邊界更低
        保證 buy + hold + sell = 1.0（float 精度容忍 1e-9）

    行為對比：
        score=0.0  → (0, 0, 1)               ← 純 sell（邊界）
        score=0.5  → (0.5, 0, 0.5)           ← buy/sell 交鋒（中點）
        score=1.0  → (1, 0, 0)               ← 純 buy（邊界）
        score=0.4  → (~0.31, ~0.07, ~0.69)   ← 中段，hold 接近 0
        score=0.6  → (~0.69, ~0.07, ~0.31)   ← 中段，hold 接近 0

    為何不用舊版 (0, 1, 0) 完美中性：
        舊版把中段 score∈[0.4, 0.6] 全歸類為 hold（hold=0.8），造成 56% 中性比例。
        連續化後中段 hold ≈ 0.07（不歸類 hold），buy/sell 在中點交鋒更合理。
    """
    import math  # 函數內 conditional import（沿用 v5.12/v5.13 慣例）
    # Clamp score 到 [0, 1]
    s = max(0.0, min(1.0, float(score)))
    # Sigmoid 軟切：k=12 給 ~0.33 寬過渡帶（與 v5.13 P36 market_signal 一致）
    buy_strength = 1.0 / (1.0 + math.exp(-12.0 * (s - 0.5)))
    sell_strength = 1.0 - buy_strength
    # hold = 1 - max(buy, sell)：中段低、邊界 0
    hold = 1.0 - max(buy_strength, sell_strength)
    total = buy_strength + hold + sell_strength
    if abs(total - 1.0) > 1e-9:
        return {"buy": buy_strength / total, "hold": hold / total, "sell": sell_strength / total}
    return {"buy": buy_strength, "hold": hold, "sell": sell_strength}


def score_to_5tier(overall: float) -> int:
    """將 -100..+100 的 overall 共識分數映射到 5-tier（1=強賣, 3=中性, 5=強買）。

    v5.11 (Stage 4.1) N14 修復: 邊界值更靈敏，避免永遠 HOLD。
    舊版問題 (v5.10 BUG)：邊界值 ±30 跨度過寬，CE overall 通常落在 ±30 內 → 永遠 3 (HOLD)
    v5.11 改為更細邊界（±15 / ±5），確保實際 CE 結果能映射到 1-5 全範圍：
        overall >=  15  → 5 STRONG_BUY
        overall >=   5  → 4 BUY
        overall >=  -5  → 3 HOLD
        overall >= -15  → 2 SELL
        overall <  -15  → 1 STRONG_SELL
    """
    if overall >= 15:  return 5
    if overall >= 5:   return 4
    if overall >= -5:  return 3
    if overall >= -15: return 2
    return 1


def score_to_5tier_with_confidence(overall: float) -> Tuple[int, float]:
    """v5.13 P36c-5tier: 5-tier + confidence 雙返回（向後兼容 P36c 設計 B）。

    Rule 6 衝突攤開: v5.11 N14 已修 ±15/±5 邊界，5-tier 在真實 CE 分布下
    健康（每 tier 15-27%），無 hard-cap 飽和問題。但「just-crossed boundary」
    與「tier 中心」仍應有區別 — 用 confidence 表達 tier 內位置穩定度。

    Design:
      - score_to_5tier(overall) 不變（向後兼容 + Check 2 verifier 仍 PASS）
      - score_to_5tier_with_confidence(overall) → (tier, conf in [0.5, 1.0])
        - Tier boundary (just crossed): confidence = 0.5
        - Tier center (most stable): confidence = 1.0
        - Far saturated (>30 or <-30): confidence = 1.0

    Confidence 由「距離最近 tier 邊界」決定，距離越遠 → 信心越高。

    v5.11 N14 不對稱性注意:
      - STRONG_BUY (tier 5) 邊界: overall >= 15  (15 是 tier 5)
      - STRONG_SELL (tier 1) 邊界: overall <  -15 ( -15 是 tier 2，不是 1)
      這是真實行為，confidence 必須跟隨。
    """
    tier = score_to_5tier(overall)
    if tier == 5:    # overall >= 15
        # 15: boundary (0.5), 45: saturated (1.0)
        conf = 0.5 + (overall - 15) / 30
    elif tier == 4:  # 5 <= overall < 15
        # 5: boundary (0.5), 10: center (1.0), 15: 1.0
        # distance from nearest boundary (5 or 15)
        dist_to_edge = min(overall - 5, 15 - overall)
        conf = 0.5 + dist_to_edge / 10
    elif tier == 3:  # -5 <= overall < 5
        # -5: 0.5, 0: center (1.0), 5: 0.5
        dist_to_edge = 5 - abs(overall)
        conf = 0.5 + dist_to_edge / 10  # Symmetric with tier 2/4 (width 10)
    elif tier == 2:  # -15 <= overall < -5
        # -15: boundary (0.5), -10: center (1.0), -5: 0.5
        dist_to_edge = min(-5 - overall, overall + 15)
        conf = 0.5 + dist_to_edge / 10  # Symmetric with tier 4 (divisor 10)
    else:            # tier == 1, overall < -15
        # -15: boundary (0.5), -45: saturated (1.0)
        conf = 0.5 + (-15 - overall) / 30
    # Clamp to [0.5, 1.0] for safety (defensive)
    conf = max(0.5, min(1.0, conf))
    return (tier, conf)


# v5.8: 貨幣符號 module-level 常量（dedup 兩處）
CURRENCY_SYMBOLS: Dict[str, str] = {
    "USD": "$", "HKD": "HK$", "CNY": "¥", "JPY": "¥",
    "GBP": "£", "EUR": "€", "TWD": "NT$",
}


def currency_symbol(currency: str) -> str:
    """取得貨幣顯示符號（v5.8: 從 stock_html_report.py 也委派至此）"""
    return CURRENCY_SYMBOLS.get(currency, currency + " ")


def market_signal_from_score(score: float, midpoint: float = 0.5, k: float = 12.0):
    """
    v5.13 (P36) 新增 — 將連續 score 轉為 (signal, strength, confidence)。

    v5.13 (P36b) 推廣: 名稱保留 market_signal_from_score 以維持向後兼容，
    但本函數實際上是「0-1 score → (buy/sell/neutral, strength, confidence)」通用轉換器，
    適用於 tech/fund/risk 等所有 score ∈ [0,1] 的 analyst 信號。

    設計：
    - strength = sigmoid(score, midpoint, k) = 1 / (1 + exp(-k * (score - midpoint)))
      連續 0-1，單調遞增，中心化於 midpoint
    - signal: 離散標籤（buy/sell/neutral）保留向後兼容
      邊界改為 strength 0.6 / 0.4（不再是 score 0.6 / 0.4）
    - confidence: 0..1，abs(strength - 0.5) * 2
      中點 → 0，極值 → 1

    參數：
    - score: 0-1 連續評分（來自 multifactor；適用 market/tech/fund/risk）
    - midpoint: sigmoid 中點（預設 0.5 = 中性）
    - k: sigmoid 斜率（k=12 給 ~0.33 寬的過渡帶，與 v5.11.3 hard threshold 接近）

    返回：
    - (signal: str, strength: float, confidence: float)
      signal ∈ {"buy", "sell", "neutral"}
      strength ∈ [0, 1]
      confidence ∈ [0, 1]
    """
    import math  # 函數內 conditional import（沿用 v5.12 P32/P34 慣例）
    # Clamp score 到 [0, 1]（避免極端輸入爆掉 sigmoid）
    s = max(0.0, min(1.0, float(score)))
    # Sigmoid：strength ∈ (0, 1)
    try:
        strength = 1.0 / (1.0 + math.exp(-k * (s - midpoint)))
    except OverflowError:
        # score 極端時 exp 可能 overflow，保底給 0 / 1
        strength = 0.0 if s < midpoint else 1.0
    # 離散信號（向後兼容）
    if strength > 0.6:
        signal = "buy"
    elif strength < 0.4:
        signal = "sell"
    else:
        signal = "neutral"
    # Confidence：距中位數越遠越自信
    confidence = abs(strength - 0.5) * 2.0
    return (signal, strength, confidence)


def sentiment_signal_from_combined(combined_score: float, k: float = 6.0):
    """
    v5.13 (P36b) 新增 — 將雙極 sentiment combined_score (-1..1) 轉為 (signal, strength, confidence)。

    設計：
    - combined_score ∈ [-1, 1]（負=悲觀，正=樂觀）
    - strength = tanh(combined_score * k) 映射到 [-1, 1]，再線性映射到 [0, 1]
      保留正負號（v5.12 P34 修復精神）
      k=6 使 combined=±0.15 對應 strength≈0.60/0.40（接近 v5.11.3 hard threshold 行為）
    - signal: positive/negative/neutral（保留原 L1162 標籤）
      邊界：strength > 0.6 → positive, strength < 0.4 → negative, else neutral
    - confidence: abs(strength - 0.5) * 2

    參數：
    - combined_score: -1..1 雙極情緒分數（來自 sentiment_result['combined_score']）
    - k: tanh 斜率（k=6 使 threshold=0.15 對應 strength=0.60/0.40）

    返回：
    - (signal: str, strength: float, confidence: float)
      signal ∈ {"positive", "negative", "neutral"}
      strength ∈ [0, 1]
      confidence ∈ [0, 1]
    """
    import math  # 函數內 conditional import（沿用 v5.12 P32/P34 + v5.13 P36 慣例）
    # Clamp combined 到 [-1, 1]
    cs = max(-1.0, min(1.0, float(combined_score)))
    # tanh 平滑（保留正負號），再線性映射到 [0, 1]
    try:
        strength = 0.5 + 0.5 * math.tanh(cs * k)
    except OverflowError:
        strength = 0.0 if cs < 0 else 1.0
    # 離散信號
    if strength > 0.6:
        signal = "positive"
    elif strength < 0.4:
        signal = "negative"
    else:
        signal = "neutral"
    # Confidence
    confidence = abs(strength - 0.5) * 2.0
    return (signal, strength, confidence)


def market_score_multifactor(ytd_return: float, pos_52wk: float, from_high_pct: float, beta: float) -> float:
    """多因子評分（基於多個連續變數）

    v5.9 修正（C13 + C14 ytd 反轉/flatline BUG）:
        舊版問題 1 (C13): ytd_factor = max(0.3, 0.5 - ytd/60) 在 ytd > +30 後完全
                          衰減至 0.3 floor，造成 ytd=+10..+100 全部得 0.5558（flatline）
        舊版問題 2 (C14): 對負 ytd 給 1.0 (mean reversion buy)，對正 ytd 給 0.3-0.5 (sell)
                          結構性反轉：ytd=-50 (0.66) > ytd=+100 (0.5558)
        v5.9 改為：ytd 反映「趨勢確認 + 動量」
          - ytd < -30: 1.0 (deep drop = mean reversion buy, 保持)
          - ytd ∈ [-30, +30]: 線性 0.5 ± 0.5（中心化，ytd=0 → 0.5）
          - ytd ∈ [+30, +60]: 0.7 (strong uptrend, slight bonus)
          - ytd > +60: 0.6 (extreme uptrend, slight caution, NOT sell)
        同時 dd_factor 對創新高 from_high > 0 改給 0.55-0.65 bonus 而非 0.3 floor

    設計：均值回歸 + 趨勢確認（去反轉）
    - 從高點跌幅因子（權重 0.5）：跌深加分、創新高也加分（趨勢確認）
    - 52週位置因子（權重 0.3）：低位加分、高位中性（v5.8 C11）
    - YTD 因子（權重 0.15）：中心化、不反轉（v5.9 C13/C14）
    - Beta 因子（權重 0.05）：高 Beta 微扣

    邊界：
    - score=0.5 為中性
    - score>0.6 → buy 信號
    - score<0.4 → sell 信號
    """
    # v5.10 (Stage 4.3) C22 修復: 從高點跌幅因子 — dd > +30 連續加分（避免 cap 0.66）
    # v5.9 BUG: from_high > +30 一律 0.66（無法區分 +30 vs +50）
    # v5.14 (P38) 修復: 統一為 from_high [-200, +100] 連續線性（無 cap，極端值 clip）
    #   fhigh=-200 → 0.0  (極端崩盤 → 最低分)
    #   fhigh=-60  → 1.0  (深跌 → 強 buy)
    #   fhigh=0    → 0.5  (中性)
    #   fhigh=+30  → 0.65 (新高 = 微加分)
    #   fhigh=+100 → 0.85 (極強新高 = 強 buy)
    if from_high_pct <= -60:
        # 線性 1.0 (fhigh=-60) → 0.0 (fhigh=-200)，斜率 -1/140
        dd_factor = max(0.0, 1.0 - 1.0 * (-60 - from_high_pct) / 140)
    elif from_high_pct <= 0:
        dd_factor = 0.5 + 0.5 * (-from_high_pct) / 60  # 0.5..1.0
    elif from_high_pct <= 30:
        # 創新高：[0, +30] 線性映射 [0.55, 0.65]
        dd_factor = 0.55 + 0.10 * from_high_pct / 30
    else:
        # v5.10: 連續加分至 0.85（極強新高）
        dd_factor = min(0.85, 0.65 + 0.20 * (from_high_pct - 30) / 70)

    # v5.10 (Stage 4.3) C23 修復: 52 週位置因子分 5 段（避免 0-20 全 0.6450）
    # v5.9 BUG: pos 0-20 全部 0.6450（無法區分極度低位 vs 輕度低位）
    # v5.14 (P37) 修復: 統一為 pos [0, 100] 連續線性（高分=低位 / 低分=新高）
    #   pos=0   → 1.0  (極度低位 / 破底 → 強 buy)
    #   pos=50  → 0.75 (中位 → 微 buy)
    #   pos=100 → 0.5  (新高 → 中性)
    #   pos>100 → 0.5  (極值 cap 保留)
    if pos_52wk <= 100:
        pos_factor = 1.0 - 0.5 * pos_52wk / 100  # 1.0..0.5
    else:
        pos_factor = 0.5  # pos > 100 → cap

    # v5.10 (Stage 4.1): YTD 因子 — 中心化、不反轉、嚴格單調遞增到 peak
    # v5.9 BUG: 60→80→100 反轉（0.6258→0.6183→0.6108），強勢股被扣分
    # v5.10 修復: 6 段，ytd=60 是 peak (0.85)，之後 cap（不反轉、不降）
    # v5.11.1 (Stage 5.2) N16 修復: 舊版 ytd [-200, -30] 全 cap 1.0 → [0, 30] 0.5（regression）
    # v5.11.2 (Stage 5.3) 修正方向: 統一為 ytd -100 ~ +200 連續線性（嚴格單調遞增 = trend confirmation buy）：
    # v5.14 (P38) 修復: 統一為 ytd [-200, +200] 連續線性，無 cap：
    #   ytd=-200 → 0.0  (極端崩盤)
    #   ytd=-100 → 0.0  (深跌)
    #   ytd=0    → 0.33 (中性)
    #   ytd=+100 → 0.67 (強 uptrend 確認 buy)
    #   ytd=+200 → 1.0  (peak buy, 強趨勢延續)
    if ytd_return <= -200:
        ytd_factor = 0.0
    elif ytd_return <= 200:
        # 線性 0.0 (ytd=-200) → 1.0 (ytd=+200)，斜率 +1/400
        ytd_factor = (ytd_return + 200) / 400
    else:
        ytd_factor = 1.0  # ytd > +200 極端趨勢 → cap 最高

    # Beta 因子
    if beta <= 1.2:
        beta_factor = 1.0
    else:
        beta_factor = max(0.7, 1.0 - (beta - 1.2) * 0.2)

    score = dd_factor * 0.5 + pos_factor * 0.3 + ytd_factor * 0.15 + beta_factor * 0.05
    return max(0.0, min(1.0, score))


def tech_score_multifactor(rsi: float, macd_val: float, price: float, ma50: float, momentum_20d: float) -> float:
    """技術分析多因子評分

    v5.9 修正（C15 + C17 RSI/overbought BUG）:
        舊版問題 1 (C15): RSI 權重僅 0.3，rsi=5 (極度超賣=強 buy) 但因 MACD/MA50/mom
                          3 個負因子覆蓋，score=0.4125 (被判 SELL，邏輯錯誤)
        舊版問題 2 (C17): rsi >= 70 統一給 0.2，rsi=75 和 rsi=85 同分 (0.4350)
        v5.9 改為：
          - RSI 權重提升至 0.4（最強單一訊號）
          - MACD/MA50/mom 下限從 0.2/0.15 提升至 0.25/0.2（避免淹沒 RSI）
          - RSI 區段細分：< 20 給 0.95, 20-30 線性, 30-50 線性 0.7-0.55,
            50-70 線性 0.55-0.4, 70-80 線性 0.4-0.2, > 80 給 0.15

    設計：均值回歸 + 趨勢跟隨
    - RSI 因子（權重 0.4）：超賣加分、超買扣分（v5.9 提升）
    - MACD 因子（權重 0.15）：正→加分、負→扣分
    - MA50 位置因子（權重 0.2）：價格 > MA50 → 加分
    - 20日動量因子（權重 0.25）：正→加分

    邊界：
    - score=0.5 為中性
    - score > 0.6 → buy
    - score < 0.4 → sell
    """
    # v5.10 (Stage 4.2) C20 + C17 修復: RSI 全範圍分級（避免 flatline）
    # v5.9 BUG: rsi < 20 一個常數 0.95；rsi > 80 一個常數 0.15（區分度為 0）
    # v5.10 修復: rsi=5 應該 > rsi=10 > rsi=15（極度超賣連續加分）
    # v5.14 (P39) 修復: 統一 RSI [0, 100] 連續線性，無 cap flatline
    if rsi < 0:
        rsi_factor = 1.0  # 負值 clip（數據錯誤保護）
    elif rsi < 5:
        # 線性 1.05 (rsi=0) → 1.0 (rsi=5)，極度超賣細分
        rsi_factor = 1.05 - 0.05 * rsi / 5
    elif rsi < 20:
        # 線性 1.0 → 0.95 (rsi=5..19)
        rsi_factor = 1.0 - 0.05 * (rsi - 5) / 15
    elif rsi <= 30:
        rsi_factor = 0.85 - 0.15 * (rsi - 20) / 10  # 0.85..0.70
    elif rsi <= 50:
        rsi_factor = 0.70 - 0.15 * (rsi - 30) / 20  # 0.70..0.55
    elif rsi <= 70:
        rsi_factor = 0.55 - 0.15 * (rsi - 50) / 20  # 0.55..0.40
    elif rsi <= 80:
        rsi_factor = 0.40 - 0.20 * (rsi - 70) / 10  # 0.40..0.20
    elif rsi <= 95:
        rsi_factor = 0.20 - 0.10 * (rsi - 80) / 15  # 0.20..0.10
    else:
        rsi_factor = 0.05  # rsi >= 95 極度超買 → 強 sell（cap 保留）

    # MACD 因子
    # v5.14 (P39) 修復: 統一為 macd [-10, +10] 連續線性
    #   macd=-10 → 0.0  (極端負向 / 強 sell)
    #   macd=0   → 0.5  (中性)
    #   macd=+10 → 1.0  (極端正向 / 強 buy)
    if macd_val < -10:
        macd_factor = 0.0  # cap 極端負向
    elif macd_val > 10:
        macd_factor = 1.0  # cap 極端正向
    else:
        macd_factor = 0.5 + 0.05 * macd_val  # 0.0..1.0 線性

    # MA50 位置因子（v5.9: floor 提高 0.15 → 0.2）
    if ma50 <= 0:
        ma50_factor = 0.5  # ma50=0/負值 fallback（數據錯誤保護）
    else:
        # v5.22 (Stage B-0) P41 修復: 改 absolute diff-based，解決 ratio-based 設計 pitfall
        # 舊 v5.21: ratio = (price/ma50 - 1.0)/0.2 → price 固定時 ma50 變化比值梯度極小
        #   真實場景: price=$200 固定 → ma50=50,100,150 → score 完全相同 0.6234 (flat)
        #   罪魁禍首: ratio 在 ma50 << price 範圍 (e.g., price=200, ma50=50) 比率已遠 > 1
        #   經 min(0.85, ...) clip 到 0.85 floor, 整段平掉。
        # 新設計: ma50_pct = (price - ma50) / ma50 真實相對差,連續線性映射（無 mid cap）
        #   ma50_pct ∈ [-1.0, +1.0]: 線性 0.2..0.8 (symmetric)
        #   ma50_pct > 1.0 (price 倍 ma50): clip 0.8..1.0 (強 buy, 但 gradient 保留小段)
        #   ma50_pct < -1.0 (price 為 ma50 半): clip 0.2..0.0 (強 sell, 但有限)
        # 關鍵: 移除舊版 0.85 floor,讓真實大 pct 差異 (3.0 vs 1.0 vs 0.3) 都 distinct
        ma50_pct = (price - ma50) / ma50
        if ma50_pct >= 1.0:
            # 強 buy: ma50_pct=1.0→0.8, +=0.4 漸進至 1.0
            ma50_factor = min(1.0, 0.8 + 0.2 * min((ma50_pct - 1.0) / 1.0, 1.0))
        elif ma50_pct >= -1.0:
            # 中性區: ma50_pct=-1.0→0.2, ma50_pct=+1.0→0.8 (linear)
            ma50_factor = 0.5 + 0.3 * ma50_pct
        else:
            # 強 sell: ma50_pct=-1.0→0.2, -=0.4 漸進至 0.0
            ma50_factor = max(0.0, 0.2 + 0.2 * max((-1.0 - ma50_pct) / 1.0, 0.0))

    # v5.11 (Stage 4.2) N15 修復: momentum [-20, -10] 全 0.4450 + [10, 20] 全 0.6075（雙 cap flatline）
    # 統一為 momentum -50% ~ +50% 連續線性（高分 = 強動量 / 低分 = 弱動量）
    # v5.14 (P39) 修復: 統一為 momentum [-100, +50] 連續線性
    #   mom=-100 → 0.0  (極端崩盤)
    #   mom=-50  → 0.05 (深跌 → 弱)
    #   mom=+50  → 0.95 (強漲 → 強 buy)
    if momentum_20d < -100:
        mom_factor = 0.0  # cap 極端崩盤
    elif momentum_20d <= 50:
        # 線性 0.0 (mom=-100) → 0.95 (mom=+50)
        mom_factor = 0.0 + 0.95 * (momentum_20d + 100) / 150
    else:
        mom_factor = 0.95  # 極端上漲 → cap

    score = rsi_factor * 0.4 + macd_factor * 0.15 + ma50_factor * 0.2 + mom_factor * 0.25
    return max(0.0, min(1.0, score))


def fund_score_multifactor(pe: float, roe: float, peg_val: "Optional[float]", revenue_growth: float) -> float:
    """v5.6: 基本面多因子評分

    設計：低估優質成長股
    - P/E 因子（權重 0.35）：低 P/E 加分
    - ROE 因子（權重 0.3）：高 ROE 加分
    - PEG 因子（權重 0.2）：< 1 加分、> 2 扣分
    - 營收增長因子（權重 0.15）：高增長加分

    邊界：
    - score=0.5 中性
    - score > 0.65 → buy（基本面優秀）
    - score < 0.4 → sell
    """
    # v5.10 (Stage 4.3) C25 修復: P/E 因子 — 超過 35 不再硬切，漸進至 0.05（避免 cap 0.5380）
    # v5.9 BUG: pe > 35 一律 0.1（無法區分 PE=40 vs PE=100）
    # v5.11 (Stage 4.3) N12 修復: pe [0, 5] 全 0.4 + [150, 400] 全 0.05（雙 cap flatline）
    # v5.11.1 (Stage 5.1) N12.1 修復: pe=-50 cap 0.05 → pe=-10 線性 0.8845 跳 0.83（不連續）
    # 統一為 pe -50 ~ +500 連續線性（無 cap，從 pe=-50 到 pe=500 全線性）
    if pe <= 500:
        # 線性 0.95 (pe=-50) → 0.05 (pe=500)，無 cap
        pe_factor = 0.95 - 0.90 * (pe + 50) / 550
    else:
        pe_factor = 0.05  # 極端高估值（> 500）→ cap

    # v5.10 (Stage 4.3) C24 修復: ROE 因子 — 超過 25% 漸進加分至 0.95（避免 cap 0.72）
    # v5.9 BUG: roe >= 25% 一律 0.9（無法區分 AAPL 150% vs 平庸股 30%）
    # v5.11 (Stage 4.2) N7 修復: roe > 2.0 cap 0.95（roe=3 和 roe=10 同分；Stage 5.1 工作未完成）
    # 統一為 roe -50% ~ +300% 連續線性（保留單調遞增，無 cap flatline）
    if roe <= -0.5:
        roe_factor = 0.05  # 嚴重虧損（roe<-50%）→ 最低分
    elif roe <= 3.0:
        # 線性 0.05 (roe=-50%) → 0.95 (roe=300%)，無 cap
        roe_factor = 0.05 + 0.90 * (roe + 0.5) / 3.5
    else:
        roe_factor = 0.95  # roe > 300% 異常高 → cap

    # v5.11 (Stage 4.2) N9 修復: PEG [0.3, 1.0] 全 0.9190 + [3, 5] 全 0.7590（雙 cap flatline）
    # v5.22 (Stage B-0) P42 修復: PEG > 5 cap 0.10 → continuous decay (8.19% 真實樣本 cap-zone)
    # 舊 v5.21: peg > 5 一律 0.10 floor → PEG=6, 8, 15 完全相同 (flat pitfall)
    # 新設計: exponential decay, 保留「PEG > 5 = 高估」語義
    #   PEG ∈ [0, 5]: 線性 0.95 → 0.10 (N9 已修, 不變)
    #   PEG ∈ [5, 25]: 衰減 0.10 → 0.02 (PEG=10→0.037, PEG=15→0.014)
    #   PEG > 25: clip 0.0
    if peg_val is None or peg_val <= 0:
        peg_factor = 0.5  # 無 PEG → 中性
    elif peg_val <= 5:
        # 線性 0.95 (PEG=0.1) → 0.10 (PEG=5)（N9 v5.11 保留）
        peg_factor = 0.95 - 0.85 * (peg_val - 0.1) / 4.9
    elif peg_val <= 25:
        # v5.22 P42: 衰減 0.10 → 0.02 (slope -0.004 per unit)
        peg_factor = 0.10 - 0.08 * (peg_val - 5) / 20
    else:
        peg_factor = 0.0  # 極端高 PEG (>25) → 強 sell

    # v5.10 (Stage 4.3) C26 修復: 營收增長因子 — 超過 30% 漸進加分（避免 cap 0.6780）
    # v5.9 BUG: growth >= 30% 一律 0.9（無法區分 growth=30% vs growth=100%）
    # v5.11 (Stage 4.2) N8 修復: growth > 1.3 cap 0.95（growth=200% 和 growth=1000% 同分）
    # 統一為 growth -50% ~ +500% 連續線性（無 cap flatline）
    if revenue_growth <= -0.5:
        growth_factor = 0.10  # 嚴重衰退 → 最低
    elif revenue_growth <= 5.0:
        # 線性 0.10 (growth=-50%) → 0.95 (growth=500%)，無 cap
        growth_factor = 0.10 + 0.85 * (revenue_growth + 0.5) / 5.5
    else:
        growth_factor = 0.95  # growth > 500% 異常 → cap

    score = pe_factor * 0.35 + roe_factor * 0.3 + peg_factor * 0.2 + growth_factor * 0.15
    return max(0.0, min(1.0, score))


def risk_score_multifactor(volatility: "Optional[float]", var_95: "Optional[float]", max_dd: "Optional[float]", sharpe: "Optional[float]") -> float:
    """v5.6: 風險多因子評分（高分 = 低風險 = buy 信號）

    設計：低風險高分、高風險低分
    - 波動性因子（權重 0.3）：高波動 → 扣分
    - VaR 因子（權重 0.2）：高 VaR → 扣分
    - 最大回撤因子（權重 0.3）：深回撤 → 扣分
    - Sharpe 因子（權重 0.2）：高 Sharpe → 加分

    邊界：
    - score=0.5 中性風險
    - score > 0.6 → buy（低風險）
    - score < 0.4 → sell（高風險）
    """
    # v5.11 (Stage 4.2) N10 修復: vol [5, 10] 全 0.6390 + [60, 100] 全 0.4290（雙 cap flatline）
    # 統一為 vol 0-150% 連續線性（高分 = 低波動 / 低分 = 高波動）
    if volatility is None or volatility <= 0:
        vol_factor = 0.5  # 數據不足
    elif volatility <= 150:
        # 線性 0.95 (vol=0) → 0.05 (vol=150%)
        vol_factor = 0.95 - 0.90 * volatility / 150
    else:
        vol_factor = 0.05  # 極端高波動 → cap

    # VaR 因子：[0, -5%] 線性映射 [0.7, 0.2]
    # v5.14 (P40) 修復: 統一為 var_95 [-5%, +5%] 連續線性，無 cap
    #   var=-5% → 0.20 (高下行風險 → 弱 buy)
    #   var=0   → 0.55 (中性)
    #   var=+5% → 0.90 (反向 VaR / 異常正向)
    if var_95 is None:
        var_factor = 0.5
    elif var_95 >= 5:
        var_factor = 0.9  # cap 異常反向 VaR
    elif var_95 >= -5:
        # 線性 0.20 (var=-5%) → 0.90 (var=+5%)
        var_factor = 0.55 + 0.035 * var_95
    else:
        var_factor = 0.20  # cap 極端下行

    # 最大回撤因子：[-50%, 0] 線性映射 [0.15, 0.7]
    # v5.14 (P40) 修復: 統一為 max_dd [-50%, +5%] 連續線性，無 cap
    #   dd=-50% → 0.15 (深回撤 → 弱)
    #   dd=0    → 0.65 (中性)
    #   dd=+5% → 0.85 (正向反轉 / 異常)
    if max_dd is None:
        dd_factor = 0.5
    elif max_dd >= 5:
        dd_factor = 0.85  # cap 異常
    elif max_dd >= -50:
        # 線性 0.15 (dd=-50%) → 0.85 (dd=+5%)
        dd_factor = 0.65 + 0.014 * max_dd
    else:
        dd_factor = 0.10  # cap 極端

    # v5.11 (Stage 4.2) N11 修復: sharpe [2, 3] 全 0.6233（cap flatline）
    # 統一為 sharpe -2 ~ +5 連續線性（高分 = 高 Sharpe）
    if sharpe is None:
        sharpe_factor = 0.5
    elif sharpe <= 5:
        # 線性 0.10 (sharpe=-2) → 0.95 (sharpe=+5)
        sharpe_factor = 0.10 + 0.85 * (sharpe + 2) / 7
    else:
        sharpe_factor = 0.95  # 極端高 Sharpe → cap

    score = vol_factor * 0.3 + var_factor * 0.2 + dd_factor * 0.3 + sharpe_factor * 0.2
    return max(0.0, min(1.0, score))


def sentiment_score_multifactor(combined_score: float, confidence: float, news_count: int) -> float:
    """v5.12 (Pitfall #34): 情緒多因子評分（連續 tanh 映射，保留正負號）

    設計：低分=負面情緒(偏賣)，高分=正面情緒(偏買)
    - combined_score 因子（權重 0.7）：tanh 平滑，保留正負號
      - 正值（偏買）→ 高分；負值（偏賣）→ 低分；0 → 0.5 中性
    - confidence 因子（權重 0.2）：高 confidence 加分（0.5 中性，1.0 滿分）
    - news_count 因子（權重 0.1）：≥30 加分（覆蓋充足）

    邊界：
    - score=0.5 中性
    - score > 0.6 → positive
    - score < 0.4 → negative
    - combined_score ∈ [-1, 1]，tanh(combined_score * 2) ∈ [-0.96, 0.96]
    """
    import math

    # v5.12 P34: combined_score 因子 — tanh 平滑（保留正負號）
    # tanh(x * 2) 將 [-1, 1] 映射到 [-0.96, 0.96]，再 scale 到 [0.05, 0.95]
    cs_clamped = max(-1.0, min(1.0, combined_score))
    cs_factor = 0.5 + 0.45 * math.tanh(cs_clamped * 2)

    # confidence 因子：0.5 中性，1.0 滿分
    conf_clamped = max(0.0, min(1.0, confidence))
    conf_factor = 0.5 + 0.5 * conf_clamped  # [0.5, 1.0]

    # news_count 因子：0 條 → 0.4，30 條 → 0.7，60 條 → 0.9，120 條 → 0.95，500+ 條 → 1.0
    # v5.19 (N17) 修復: 120 → cap 0.95 改成 120→500 漸進至 1.0（避免極端新聞量 flatline）
    if news_count <= 0:
        nc_factor = 0.40
    elif news_count < 30:
        nc_factor = 0.40 + 0.30 * news_count / 30
    elif news_count < 60:
        nc_factor = 0.70 + 0.20 * (news_count - 30) / 30
    elif news_count < 120:
        nc_factor = 0.90 + 0.05 * (news_count - 60) / 60
    elif news_count < 500:
        nc_factor = 0.95 + 0.05 * (news_count - 120) / 380
    else:
        nc_factor = 1.0  # 真正極端覆蓋（>500 條）→ 滿分

    score = cs_factor * 0.7 + conf_factor * 0.2 + nc_factor * 0.1
    return max(0.0, min(1.0, score))


def news_score_multifactor(news_count: int, region_count: int, source_diversity: int) -> float:
    """v5.12 (Pitfall #33) + v5.15 (P43, P44): 新聞多因子評分（連續線性，無 hard threshold）

    設計：高分=新聞覆蓋充足且多元化
    - news_count 因子（權重 0.5）：線性 0 (0 條) → 0.95 (≥120 條)
    - region_count 因子（權重 0.3）：線性 0.3 (0 區) → 0.95 (5+ 區, v5.15 P43)
    - source_diversity 因子（權重 0.2）：線性 0.3 (1 源) → 0.95 (12+ 源, v5.15 P44)

    v5.15 P43/P44 量化（quantify_sentiment_news_cap.py）：
      - P43: region_count=3→4→5 真實分布 cap rate 50% → 線性延伸到 5+
      - P44: source_diversity=6→8→11 真實分布 cap rate 58.8% → 線性延伸到 12+

    邊界：
    - score=0.5 中性
    - score > 0.6 → 覆蓋良好
    - score < 0.4 → 覆蓋不足
    """
    # news_count 因子：線性 0 (0 條) → 0.95 (120 條) → 1.0 (500+ 條)
    # v5.19 (N18) 修復: ≥120 cap 0.95 改成 120→500 漸進至 1.0
    if news_count <= 0:
        nc_factor = 0.0
    elif news_count < 120:
        nc_factor = 0.95 * news_count / 120
    elif news_count < 500:
        nc_factor = 0.95 + 0.05 * (news_count - 120) / 380
    else:
        nc_factor = 1.0  # 真正極端覆蓋 → 滿分

    # region_count 因子：線性 0.3 (0 區) → 0.95 (5 區) → 1.0 (12+ 區)
    # v5.19 (N19) 修復: ≥5 cap 0.95 改成 5→12 漸進至 1.0（6+ 區域仍能區分）
    if region_count <= 0:
        rc_factor = 0.30
    elif region_count < 5:
        rc_factor = 0.30 + 0.65 * region_count / 5
    elif region_count < 12:
        rc_factor = 0.95 + 0.05 * (region_count - 5) / 7
    else:
        rc_factor = 1.0  # 12+ 區域 → 滿分

    # source_diversity 因子：線性 0.3 (1 源) → 0.95 (12 源) → 1.0 (30+ 源)
    if source_diversity <= 1:
        sd_factor = 0.30
    elif source_diversity < 12:
        sd_factor = 0.30 + 0.65 * (source_diversity - 1) / 11
    elif source_diversity < 30:
        sd_factor = 0.95 + 0.05 * (source_diversity - 12) / 18
    else:
        sd_factor = 1.0  # 30+ 來源 → 滿分

    score = nc_factor * 0.5 + rc_factor * 0.3 + sd_factor * 0.2
    return max(0.0, min(1.0, score))


def weighted_score_with_variance_penalty(
    scores: dict[str, float], weights: dict[str, float]
) -> tuple[float, float]:
    """v5.12 (Pitfall #32): 加權共識 + variance penalty（disagreement 降低信心）

    設計：
    - weighted_avg = Σ (score * weight)
    - analyst_std = stdev(analyst_scores)  (量度 disagreement)
    - penalty = 1 - 0.3 * analyst_std  (0.7~1.0 區間)
    - final_score = weighted_avg * penalty

    Returns: (final_score, analyst_std)

    邊界：
    - analyst_std = 0 (完全共識) → penalty = 1.0 → final = weighted_avg
    - analyst_std = 1.0 (完全相反) → penalty = 0.7 → final = weighted_avg * 0.7
    - 注意：這是「信心折扣」，不是「方向改變」
    """
    import math

    if not scores or not weights:
        return 0.5, 0.0

    # 過濾有效角色（必須有 score 與 weight）
    valid_roles = [r for r in weights if r in scores]
    if not valid_roles:
        return 0.5, 0.0

    # 加權平均
    total_weight = sum(weights[r] for r in valid_roles)
    if total_weight <= 0:
        return 0.5, 0.0
    weighted_avg = sum(scores[r] * weights[r] for r in valid_roles) / total_weight

    # analyst std（量度 disagreement）
    analyst_scores = [scores[r] for r in valid_roles]
    if len(analyst_scores) < 2:
        return weighted_avg, 0.0
    mean = sum(analyst_scores) / len(analyst_scores)
    variance = sum((s - mean) ** 2 for s in analyst_scores) / len(analyst_scores)
    analyst_std = math.sqrt(variance)

    # variance penalty：0.7~1.0（max disagreement 扣 30% 信心）
    penalty = max(0.7, 1.0 - 0.3 * min(analyst_std, 1.0))

    final_score = max(0.0, min(1.0, weighted_avg * penalty))
    return final_score, analyst_std


def dynamic_weights_for_ticker(ticker: str) -> dict[str, float]:
    """v5.12 (Pitfall #35): 根據 ticker profile 動態調整分析師權重

    設計：
    - base_weights: market 0.12 / technical 0.18 / fundamental 0.22 /
                    risk 0.15 / sentiment 0.18 / news 0.07 / macro 0.08
    - region="hk" (亞股波動大):  technical +0.05, fundamental +0.03, sentiment -0.03
    - region="cn" (政策風險):    fundamental +0.05, risk +0.03, market -0.03
    - region="us" (預設，default): fundamental +0.05, news +0.02, sentiment -0.02

    Returns: weights dict (sum ≈ 1.0)

    邊界：
    - 找不到 region 後綴 → region="us"
    - 調整後自動 normalize（避免加權和 ≠ 1.0）
    """
    # 基礎權重（與 v5.11 既有 weights 對齊）
    base = {
        "market": 0.12,
        "technical": 0.18,
        "fundamental": 0.22,
        "risk": 0.15,
        "sentiment": 0.18,
        "news": 0.07,
        "macro": 0.08,
    }

    # 推導 region
    ticker_upper = ticker.upper()
    if ticker_upper.endswith(".HK"):
        region = "hk"
    elif ticker_upper.endswith((".SS", ".SZ")):
        region = "cn"
    else:
        region = "us"  # 預設（AAPL/MSFT/GOOG 等）

    # 套用 region-specific 調整
    if region == "hk":
        adjustments = {
            "technical": +0.05,
            "fundamental": +0.03,
            "sentiment": -0.03,
        }
    elif region == "cn":
        adjustments = {
            "fundamental": +0.05,
            "risk": +0.03,
            "market": -0.03,
        }
    else:  # us
        adjustments = {
            "fundamental": +0.05,
            "news": +0.02,
            "sentiment": -0.02,
        }

    weights = {role: base[role] + adjustments.get(role, 0.0) for role in base}

    # Normalize: 確保加權和 = 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {role: w / total for role, w in weights.items()}

    return weights


_log("Script starting")
atexit.register(lambda: _log("Script exiting"))

# 命令列參數解析
parser = argparse.ArgumentParser(description='Stock_Team_Agent 深度分析')
parser.add_argument('--code', '-c', type=str, default='AAPL',
                    help='股票代碼（如 AAPL, 1810.HK, BTC-USD）')
parser.add_argument('--name', '-n', type=str, default=None,
                    help='股票名稱（可選，預設根據代碼自動識別）')
parser.add_argument('--tickers', '-t', type=str, default=None,
                    help='批量分析：逗號分隔的股票代碼（如 AAPL,MSFT,GOOGL）')
args_, _ = parser.parse_known_args()

# ============================================================
# 執行入口（僅作為腳本運行時執行，import 時不觸發）
# ============================================================
if __name__ == "__main__":
    # 批量模式：對每個 ticker 依次執行
    if args_.tickers:
        import subprocess
        tickers = [t.strip() for t in args_.tickers.split(",") if t.strip()]
        print(f"📊 批量模式：開始分析 {len(tickers)} 支股票")
        print("=" * 80)
        
        results = []
        for i, ticker in enumerate(tickers, 1):
            print(f"\n{'='*80}")
            print(f"📈 [{i}/{len(tickers)}] 開始分析: {ticker}")
            print(f"{'='*80}\n")
            _log(f"BATCH_START_{ticker}")
            
            result = subprocess.run(
                ["python3", __file__, "--code", ticker],
                capture_output=False
            )
            results.append((ticker, result.returncode == 0))
            _log(f"BATCH_END_{ticker}")
        
        # 批量摘要
        print("\n" + "=" * 80)
        print("📊 批量分析摘要")
        print("=" * 80)
        for ticker, success in results:
            status = "✅" if success else "❌"
            print(f"  {status} {ticker}")
        print(f"\n總計: {len(tickers)} 支股票")
        sys.exit(0)
    
    # 從 dotenv 載入環境變數
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser('~/.hermes/.env'), override=False)
    
    import yfinance as yf
    import pandas as pd
    import json
    from pathlib import Path
    from data_sources.enhanced_news_feed_provider import EnhancedNewsFeedProvider
    from integrations.minimax_llm import MiniMaxLLM
    from train.llm_debate_engine import LLMDebateEngine
    # v5.8: 刪除 model/handlers/ shim（其他 6 個分析師），保留 macro_analyst 唯一真實位置
    from model.handlers.macro_analyst import MacroAnalyst
    
    # 嘗試從 yfinance 自動識別股票名稱（容錯）
    try:
        _ticker_guess = yf.Ticker(args_.code).info
        _auto_name = _ticker_guess.get('longName') or _ticker_guess.get('shortName') or args_.code
    except Exception:
        _auto_name = args_.code
    
    ANALYSIS_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STOCK_CODE = args_.code
    STOCK_NAME = args_.name or _auto_name
    
    # 建立輸出目錄
    OUTPUT_DIR = os.path.expanduser(f"~/.hermes/task_outputs/{STOCK_CODE.replace('.', '_')}_{STOCK_NAME}_v5/")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 報告緩存（最終保存用）
    _report_lines = []
    
    def _add_report_line(line):
        """同時輸出到console和報告緩存"""
        print(line, flush=True)
        _report_lines.append(line)

    def _json_safe(obj):
        """v5.20: 遞迴轉換 numpy 型別為 JSON-safe（解決 backtest 結果含 np.bool_ 導致 dump 失敗）。
        Lazy-import numpy（避免 stock_analysis.py 直接依賴 numpy；保持 import graph 乾淨）。"""
        try:
            import numpy as _np
        except ImportError:
            _np = None
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_json_safe(v) for v in obj]
        if _np is not None:
            if isinstance(obj, _np.bool_):
                return bool(obj)
            if isinstance(obj, _np.integer):
                return int(obj)
            if isinstance(obj, _np.floating):
                return float(obj)
            if isinstance(obj, _np.ndarray):
                return obj.tolist()
        return obj

    # ============================================================
    # 第一階段：數據收集
    # ============================================================
    _log("PHASE1_START")
    
    _add_report_line("=" * 80)
    _add_report_line(f"📊 {STOCK_NAME} ({STOCK_CODE}) 專業投資分析報告")
    _add_report_line(f"📅 分析時間: {ANALYSIS_TIME}")
    _add_report_line(f"🔧 報告版本: v5 (專業投資報告格式)")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    _add_report_line("【第一階段：數據收集】")
    _add_report_line("-" * 80)
    
    # ============================================================
    # v5.2: 並行化數據獲取（5 個 IO 調用並行，預期 5-10x 加速）
    # ThreadPoolExecutor 用於 IO 密集型任務（不釋放 GIL 的 IO）
    # yfinance 內部多次 HTTP 調用 → 包成單一任務避免重複創建 session
    # ============================================================
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time

    _t_io_start = _time.time()

    def _fetch_yfinance():
        """yfinance 完整數據（info + 1y + 6mo）"""
        _t = yf.Ticker(STOCK_CODE)
        _info = _t.info or {}
        _hist = _t.history(period='1y') if hasattr(_t, 'history') else pd.DataFrame()
        _hist_6m = _t.history(period='6mo') if hasattr(_t, 'history') else pd.DataFrame()
        return _info, _hist, _hist_6m

    def _fetch_finnhub_quote():
        """Finnhub 即時報價"""
        try:
            from data_sources.realtime_quotes import get_realtime_quote
            return get_realtime_quote(STOCK_CODE)
        except Exception as _e:
            logging.debug(f"Finnhub import/call failed: {_e}")
            return None

    def _fetch_rss_news():
        """RSS 新聞（5+ 來源）"""
        _prov = EnhancedNewsFeedProvider()
        return _prov.fetch_all_working(limit_per_source=15)

    def _fetch_social_sentiment():
        """Reddit/PTT 社會情緒"""
        try:
            from data_sources.social_sentiment_provider import get_combined_social_sentiment
            return get_combined_social_sentiment(STOCK_CODE)
        except Exception as _e:
            logging.debug(f"Social sentiment import/call failed: {_e}")
            return None

    def _fetch_macro():
        """宏觀環境分析（純 CPU 但有 import + 邏輯 IO）"""
        try:
            from data_sources.stock_data_provider import StockDataProvider
            _dp = StockDataProvider()
            _ma = MacroAnalyst(_dp)
            return _ma.analyze(STOCK_CODE, "macro", "macro environment")
        except Exception as _e:
            logging.debug(f"MacroAnalyst failed: {_e}")
            return {"score_dict": {"confidence": 0.40, "signal": "neutral"}, "summary": "宏觀分析不可用", "env_items": []}

    # 並行啟動 5 個 IO 任務
    _io_tasks = {
        "yfinance": _fetch_yfinance,
        "finnhub": _fetch_finnhub_quote,
        "rss": _fetch_rss_news,
        "social": _fetch_social_sentiment,
        "macro": _fetch_macro,
    }

    _io_results = {}
    with ThreadPoolExecutor(max_workers=5) as _executor:
        _futures = {name: _executor.submit(fn) for name, fn in _io_tasks.items()}
        for _fname, _fut in _futures.items():
            try:
                _io_results[_fname] = _fut.result(timeout=60)
            except Exception as _e:
                logging.warning(f"[StockAnalysis] {_fname} failed: {_e}")
                _io_results[_fname] = None

    _t_io_elapsed = _time.time() - _t_io_start
    logging.warning(f"[StockAnalysis] 並行 IO 完成: {_t_io_elapsed:.2f}s (5 tasks)")

    # yfinance 結果
    try:
        info, hist, hist_6m = _io_results.get("yfinance") or ({}, pd.DataFrame(), pd.DataFrame())
        yfinance_success = bool(info)
    except Exception as e:
        logging.warning(f"[StockAnalysis] yfinance 結果解包失敗: {e}")
        ticker = None
        info = {}
        hist = pd.DataFrame()
        hist_6m = pd.DataFrame()
        yfinance_success = False
    if not yfinance_success:
        ticker = None
    
    # 市場數據（通用fallback，不 hardcode 特定股票數值）
    price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
    change_pct = float(info.get('regularMarketChangePercent', 0))
    week52_low = float(info.get('fiftyTwoWeekLow', 0) or 0)
    week52_high = float(info.get('fiftyTwoWeekHigh', 0) or 0)
    
    # ===== P14: 即時報價覆寫（Finnhub，從並行 IO 結果）=====
    try:
        _rt = _io_results.get("finnhub") if isinstance(_io_results.get("finnhub"), dict) else None
        if _rt and _rt.get("price"):
            _add_report_line(f"📡 即時報價: ${_rt.get('price')} ({_rt.get('source', 'Finnhub')})")
            price = float(_rt.get("price", price))
        else:
            _add_report_line("⚠️ 即時報價不可用，使用收盤價")
    except Exception as _e:
        _add_report_line(f"⚠️ 即時報價抓取失敗: {_e}")
    
    _currency = info.get('currency', 'USD')
    # v5.8: 委派給 module-level currency_symbol() 純函數（dedup 與 stock_html_report）
    _currency_symbol = currency_symbol(_currency)
    _market_cap = float(info.get('marketCap', 0) or 0)
    if _market_cap > 0:
        if _currency in ('HKD', 'CNY'):
            market_cap_native = _market_cap
        elif _currency == 'USD':
            market_cap_native = _market_cap  # 保留原幣別
        else:
            market_cap_native = _market_cap
    else:
        market_cap_native = 0
    
    pe = float(info.get('trailingPE', 0) or 0)
    volume = int(info.get('averageVolume', 0) or 0)
    eps = float(info.get('trailingEps', 0) or 0)
    roe = float(info.get('returnOnEquity', 0) or 0)
    revenue = float(info.get('totalRevenue', 0) or 0)
    revenue_growth = float(info.get('revenueGrowth', 0) or 0)
    pb = float(info.get('priceToBook', 0) or 0)
    beta = float(info.get('beta', 0) or 0)
    
    # YTD 計算
    if len(hist) > 0:
        year_start_price = float(hist['Close'].iloc[0])
        year_high = float(hist['High'].max())
        year_low = float(hist['Low'].min())
        ytd_return = (price / year_start_price - 1) * 100 if year_start_price > 0 else 0
    else:
        year_start_price = price
        year_high = price
        year_low = price
        ytd_return = 0
    
    # 技術指標（使用已獲取的 hist_6m，避免重複調用）
    if len(hist_6m) >= 20:
        ma20 = float(hist_6m['Close'].rolling(20).mean().iloc[-1])
    else:
        ma20 = price if price > 0 else 0
    
    if len(hist_6m) >= 50:
        ma50 = float(hist_6m['Close'].rolling(50).mean().iloc[-1])
    else:
        ma50 = price if price > 0 else 0
    
    if len(hist_6m) >= 14:
        delta = hist_6m['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        last_loss = float(loss.iloc[-1]) if not loss.isna().all() else 0
        if last_loss == 0:
            rsi = 100.0
        else:
            rsi = float((100 - (100 / (1 + float(gain.iloc[-1]) / last_loss))))
    else:
        rsi = 50.0
    
    if len(hist_6m) >= 26:
        ema12 = hist_6m['Close'].ewm(span=12).mean().iloc[-1]
        ema26 = hist_6m['Close'].ewm(span=26).mean().iloc[-1]
        macd_val = float(ema12 - ema26)
    else:
        macd_val = 0.0
    
    if len(hist_6m) >= 20:
        momentum_20d = float((hist_6m['Close'].iloc[-1] / hist_6m['Close'].iloc[-20] - 1) * 100)
    else:
        momentum_20d = 0
    
    # 風險指標（若歷史數據不足則為 None）
    if len(hist_6m) >= 20:
        returns = hist_6m['Close'].pct_change().dropna()
        volatility = float(returns.std() * (252**0.5) * 100) if len(returns) > 0 else None
        var_95 = float(returns.quantile(0.05) * 100) if len(returns) > 0 else None
        rolling_max = hist_6m['Close'].expanding().max()
        drawdown = (hist_6m['Close'] - rolling_max) / rolling_max
        max_dd = float(drawdown.min() * 100) if len(drawdown) > 0 else None
        sharpe = float(returns.mean() / returns.std() * (252**0.5)) if returns.std() > 0 else None
    else:
        volatility, var_95, max_dd, sharpe = None, None, None, None
    
    peg_val = pe / (revenue_growth * 100) if pe > 0 and revenue_growth > 0 else None
    
    # 標記數據狀態
    _data_status = "✅ yfinance" if yfinance_success else "⚠️ FALLBACK"
    logging.warning(f"[StockAnalysis] 數據狀態: {_data_status}, YTD: {ytd_return:+.2f}%, RSI: {rsi:.1f}")
    
    _add_report_line(f"✅ 數據來源: {_data_status}")
    _add_report_line(f"📌 現價: {_currency_symbol}{price:.2f}")
    _add_report_line(f"📌 YTD回報: {ytd_return:+.2f}%")
    _add_report_line("")
    
    # ============================================================
    # 第二階段：RSS 新聞情緒分析
    # ============================================================
    _log("PHASE2_START")
    
    _add_report_line("【第二階段：RSS 新聞情緒分析】")
    _add_report_line("-" * 80)
    
    # v5.2: 從並行 IO 結果取 RSS（避免重複創建 provider 和重複 HTTP）
    provider = EnhancedNewsFeedProvider()
    _rss_result = _io_results.get("rss") or {}
    all_feeds = _rss_result if isinstance(_rss_result, dict) else {}
    combined = all_feeds.get("all", [])

    sentiment_result = provider.analyze_with_price_context(
        combined, STOCK_CODE, ytd_return=ytd_return, momentum_20d=momentum_20d, volatility=volatility
    )

    _add_report_line(f"✅ RSS來源: {list(all_feeds.keys())}")
    _add_report_line(f"📊 總新聞數: {len(combined)} 條")
    _add_report_line("")

    # ===== P12: 社會情緒（從並行 IO 結果，避免重複抓取）=====
    try:
        _social = _io_results.get("social")
        if _social and isinstance(_social, dict) and _social.get("posts_found", 0) > 0:
            _add_report_line(f"🌐 社會情緒: Reddit {_social.get('reddit_bullish_pct', 0):.0f}% 看漲 | PTT {_social.get('ptt_bullish_pct', 0):.0f}% 看漲")
            sentiment_result['social'] = _social
        else:
            _add_report_line("⚠️ 社會情緒抓取失敗或無數據")
    except Exception as _e:
        _add_report_line(f"⚠️ 社會情緒抓取異常: {_e}")
    
    # ============================================================
    # 第三階段：7位角色完整推理分析（專業格式）
    # ============================================================
    _log("PHASE3_START")
    
    _add_report_line("=" * 80)
    _add_report_line("【第三階段：7位分析師專業評估】")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    # ===== 角色1: 市場數據分析師 =====
    _add_report_line("【市場數據分析師 (Market Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 實時市場數據")
    _add_report_line(f"   • 現價: {_currency_symbol}{price:.2f}")
    _add_report_line(f"   • 今日變化: {change_pct:+.2f}%")
    _add_report_line(f"   • 52週高點: {_currency_symbol}{week52_high:.2f}")
    _add_report_line(f"   • 52週低點: {_currency_symbol}{week52_low:.2f}")
    _add_report_line(f"   • 年初價格: {_currency_symbol}{year_start_price:.2f}")
    _add_report_line(f"   • YTD回報: {ytd_return:+.2f}%")
    _add_report_line(f"   • 市值: {_currency_symbol}{market_cap_native/1e9:.1f}B")
    _add_report_line(f"   • P/E: {pe:.2f}")
    _add_report_line(f"   • Beta: {beta:.2f}")
    
    pos_52wk = (price - week52_low) / (week52_high - week52_low) * 100 if week52_high > week52_low else 0
    pos_desc = '極度偏低' if pos_52wk < 20 else '偏低' if pos_52wk < 40 else '中性' if pos_52wk < 60 else '偏高' if pos_52wk < 80 else '極度高'
    ytd_desc = '嚴重落後大盤' if ytd_return < -30 else '明顯落後' if ytd_return < -15 else '輕微落後'
    beta_desc = '低於大盤波動' if beta < 0.8 else '與大盤同步' if beta < 1.2 else '高於大盤波動'
    from_high_pct = (price/week52_high-1)*100
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   基於52週位置{pos_52wk:.1f}%（{pos_desc}）及YTD {ytd_return:+.1f}%（{ytd_desc}），")
    _add_report_line(f"   價格已從高點回落{abs(from_high_pct):.1f}%，顯示顯著回調。")
    _add_report_line(f"   Beta {beta:.2f}表明股票{beta_desc}，當前估值處於歷史低位區間，")
    _add_report_line(f"   若宏觀環境好轉則估值修復空間较大。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 52週位置: {pos_52wk:.1f}% — 價格處於{pos_desc}區間")
    _add_report_line(f"   • YTD {ytd_return:+.2f}%: {ytd_desc}")
    _add_report_line(f"   • 從高點回落: {from_high_pct:+.1f}% — 下跌幅度顯示顯著回調")
    _add_report_line(f"   • Beta {beta:.2f}: {beta_desc}")
    
    # v5.5: 多因子 market_score（取代 v5.3 3 值啟發式）
    market_score = round(market_score_multifactor(ytd_return, pos_52wk, from_high_pct, beta), 4)
    # v5.13 (P36) 連續化: market_signal 從 hard threshold (0.6/0.4) 改為 sigmoid soft band
    # v5.11.3/v5.12 BUG: score=0.59→neutral, score=0.61→buy（2pp 差距抵消連續函數意義）
    # v5.13 修法: strength = sigmoid(score, midpoint=0.5, k=12), 離散 signal 仍保留向後兼容
    _market_signal, _market_strength, _market_conf_score = market_signal_from_score(market_score)
    market_signal = _market_signal
    market_confidence = "高" if _market_conf_score > 0.7 else "中" if _market_conf_score > 0.3 else "低"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {market_score:.3f}/1.00 | 信號: {market_signal} | 置信度: {market_confidence}")
    _add_report_line(f"   理由: YTD {ytd_return:+.1f}%處於{ytd_desc}區間，但52週位置{pos_52wk:.1f}%顯示價格接近歷史低點，")
    _add_report_line(f"         若宏觀環境好轉則估值修復空間大，給予中性偏正面評分")
    _add_report_line("")
    
    # ===== 角色2: 技術分析師 =====
    _add_report_line("【技術分析師 (Technical Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 6個月歷史K線數據")
    _add_report_line(f"   • MA20: {_currency_symbol}{ma20:.2f}" if ma20 > 0 else "   • MA20: N/A (數據不足)")
    _add_report_line(f"   • MA50: {_currency_symbol}{ma50:.2f}" if ma50 > 0 else "   • MA50: N/A (數據不足)")
    _add_report_line(f"   • RSI(14): {rsi:.2f} ({'超賣' if rsi < 35 else '超買' if rsi > 65 else '中性'})")
    _add_report_line(f"   • MACD: {macd_val:.4f} ({'負（空頭）' if macd_val < 0 else '正（多頭）'})")
    _add_report_line(f"   • 20日動量: {momentum_20d:+.2f}%")
    _add_report_line(f"   • 從高點跌幅: {from_high_pct:+.1f}%")
    
    price_vs_ma20 = "高於" if price > ma20 and ma20 > 0 else "低於" if ma20 > 0 else "無法判斷"
    price_vs_ma50 = "高於" if price > ma50 and ma50 > 0 else "低於" if ma50 > 0 else "無法判斷"
    rsi_desc = '超賣區域，技術性反彈機會增加' if rsi < 35 else '超買區域，回調風險上升' if rsi > 65 else '中性區域，趨勢不明確'
    macd_desc = '柱狀圖為負，空頭動能主導' if macd_val < 0 else '柱狀圖為正，多頭動能主導'
    mom_desc = '顯示短期動能增強' if momentum_20d > 5 else '顯示短期動能減弱' if momentum_20d < -5 else '動能中性'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   RSI {rsi:.1f}處於{rsi_desc}，MACD{macd_desc}。")
    _add_report_line(f"   價格{'高於' if price > ma50 else '低於'} MA50顯示中期趨勢{'向上' if price > ma50 else '向下'}。")
    _add_report_line(f"   20日動量{mom_desc}，從高點回落{abs(from_high_pct):.1f}%顯示調整幅度明顯。")
    _add_report_line(f"   技術面顯示短線存在反彈可能但中期趨勢仍偏弱。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 價格 {'高於' if price > ma50 else '低於'} MA50: 顯示中期趨勢{'向上' if price > ma50 else '向下'}")
    _add_report_line(f"   • RSI {rsi:.1f}: {rsi_desc}")
    _add_report_line(f"   • MACD {macd_val:.4f}: {macd_desc}")
    _add_report_line(f"   • {'價格已從高點大幅回落' if from_high_pct < -40 else '從高點回落幅度有限'}")
    _add_report_line(f"   • 20日動量 {momentum_20d:+.1f}%: {mom_desc}")
    
    # v5.6: 多因子 tech_score（取代 v5.3 3 值啟發式）
    tech_score = round(tech_score_multifactor(rsi, macd_val, price, ma50, momentum_20d), 4)
    # v5.13 (P36b) 連續化: tech_signal 從 hard threshold (0.6/0.4) 改為 sigmoid soft band
    _tech_signal, _tech_strength, _tech_conf_score = market_signal_from_score(tech_score)
    tech_signal = _tech_signal
    tech_confidence = "高" if _tech_conf_score > 0.7 else "中" if _tech_conf_score > 0.3 else "低"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {tech_score:.3f}/1.00 | 信號: {tech_signal} | 置信度: {tech_confidence}")
    _add_report_line(f"   理由: RSI {rsi:.1f}顯示{'輕微超賣' if 35 <= rsi < 50 else '超賣' if rsi < 35 else '中性偏正面'}，MACD空頭但{'價格接近MA50' if abs(price - ma50)/ma50 < 0.05 else '偏離均線'}")
    _add_report_line(f"         結合從高點回落{abs(from_high_pct):.0f}%，判斷為中性評分，短線存在技術反彈可能但中期趨勢仍偏弱")
    _add_report_line("")
    
    # ===== 角色3: 基本面分析師 =====
    _add_report_line("【基本面分析師 (Fundamental Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 財務數據")
    _add_report_line(f"   • P/E: {pe:.2f} (產業均值參考: ~18)")
    _add_report_line(f"   • ROE: {roe*100:.1f}%")
    _add_report_line(f"   • EPS: {_currency_symbol}{eps:.2f}")
    _add_report_line(f"   • PEG: {f'{peg_val:.2f}' if peg_val else 'N/A'}")
    _add_report_line(f"   • 營收增長: {revenue_growth*100:.1f}%")
    _add_report_line(f"   • P/B: {pb:.2f}")
    _add_report_line(f"   • 營收: {_currency_symbol}{revenue/1e9:.1f}B")
    
    pe_desc = '低於產業均值，顯示估值偏低' if pe < 15 else '處於產業合理區間' if pe < 22 else '高於產業均值，估值偏高'
    roe_desc = '優秀（>15%），顯示高效運用股東資本' if roe > 0.15 else '一般，資本效率平平'
    peg_desc = '偏低（<1），成長被低估' if peg_val and peg_val < 1 else '合理（1-2）' if peg_val and peg_val < 2 else '偏高（>2），成長放緩'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   P/E {pe:.2f}{pe_desc}。")
    _add_report_line(f"   ROE {roe*100:.1f}%顯示{roe_desc}。")
    _add_report_line(f"   PEG {f'{peg_val:.2f}' if peg_val else 'N/A'}: {peg_desc}。")
    _add_report_line(f"   營收增長{revenue_growth*100:.1f}%顯示核心業務仍具動能。")
    _add_report_line(f"   綜合來看，股價回落後估值吸引力提升，基本面支撐明確。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • P/E {pe:.2f}: {pe_desc}")
    _add_report_line(f"   • ROE {roe*100:.1f}%: {roe_desc}")
    _add_report_line(f"   • PEG {f'{peg_val:.2f}' if peg_val else 'N/A'}: {peg_desc}")
    
    # v5.6: 多因子 fund_score（取代 v5.3 3 值啟發式）
    fund_score = round(fund_score_multifactor(pe, roe, peg_val, revenue_growth), 4)
    # v5.13 (P36b) 連續化: fund_signal 從 hard threshold (0.6/0.4) 改為 sigmoid soft band
    _fund_signal, _fund_strength, _fund_conf_score = market_signal_from_score(fund_score)
    fund_signal = _fund_signal
    fund_confidence = "高" if _fund_conf_score > 0.7 else "中" if _fund_conf_score > 0.3 else "低"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {fund_score:.3f}/1.00 | 信號: {fund_signal} | 置信度: {fund_confidence}")
    _add_report_line(f"   理由: P/E {pe:.1f}相比同業處於低位，ROE {roe*100:.1f}%顯示優異盈利能力，股價回落後估值吸引力提升")
    _add_report_line(f"         營收增長{revenue_growth*100:.1f}%顯示核心業務仍具動能，給予基本面偏正面評分")
    _add_report_line("")
    
    # ===== 角色4: 風險分析師 =====
    _add_report_line("【風險分析師 (Risk Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ yfinance 歷史價格數據計算")
    _add_report_line(f"   • 年化波動性: {f'{volatility:.1f}%' if volatility else 'N/A'}")
    _add_report_line(f"   • VaR (95%): {f'{var_95:.2f}%' if var_95 else 'N/A'}")
    _add_report_line(f"   • 最大回撤: {f'{max_dd:.1f}%' if max_dd else 'N/A'}")
    _add_report_line(f"   • Sharpe Ratio: {f'{sharpe:.2f}' if sharpe else 'N/A'}")
    _add_report_line(f"   • Beta: {beta:.2f}")
    
    vol_desc = '極高波動（>40%），適合風險承受力強的投資者' if volatility and volatility > 40 else '高位波動（30-40%），需謹慎' if volatility and volatility > 30 else '中等波動'
    sharpe_desc = '極差（<0），風險回報不划算' if sharpe and sharpe < 0 else '一般（0-1）' if sharpe and sharpe < 1 else '良好（>1）'
    dd_desc = '歷史最大跌幅已達三分之一，風險已部分釋放' if max_dd and max_dd < -30 else '歷史最大跌幅在可接受範圍'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   波動性{f'{volatility:.1f}%' if volatility else 'N/A'}{f'屬於{vol_desc}' if volatility else '無法計算'}。")
    _add_report_line(f"   Sharpe {f'{sharpe:.2f}' if sharpe else 'N/A'}{f'，{sharpe_desc}' if sharpe else '，無法計算'}。")
    _add_report_line(f"   從高點已回落{f'{abs(max_dd):.0f}%' if max_dd else 'N/A'}顯示風險已大量釋放。")
    _add_report_line(f"   綜合來看，VaR顯示尾部風險顯著，但風險回報吸引力有限。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 波動性 {f'{volatility:.1f}%' if volatility else 'N/A'}: {vol_desc}")
    _add_report_line(f"   • VaR {f'{var_95:.2f}%' if var_95 else 'N/A'}: 明日有95%機率單日損失不超{f'{abs(var_95):.1f}%' if var_95 else 'N/A'}")
    _add_report_line(f"   • 最大回撤 {f'{max_dd:.1f}%' if max_dd else 'N/A'}: {dd_desc}")
    _add_report_line(f"   • Sharpe {f'{sharpe:.2f}' if sharpe else 'N/A'}: {sharpe_desc}")
    
    # v5.6: 多因子 risk_score（取代 v5.3 3 值啟發式）
    risk_score = round(risk_score_multifactor(volatility, var_95, max_dd, sharpe), 4)
    # v5.13 (P36b) 連續化: risk_signal 從 hard threshold (0.6/0.4) 改為 sigmoid soft band
    _risk_signal, _risk_strength, _risk_conf_score = market_signal_from_score(risk_score)
    risk_signal = _risk_signal
    risk_confidence = "高" if _risk_conf_score > 0.7 else "中" if _risk_conf_score > 0.3 else "低"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {risk_score:.3f}/1.00 | 信號: {risk_signal} | 置信度: {risk_confidence}")
    _add_report_line(f"   理由: 波動性{f'{volatility:.0f}%' if volatility else 'N/A'}屬於高波動股票，VaR顯示尾部風險顯著；")
    _add_report_line(f"         但從高點已回落{f'{max_dd:.0f}%' if max_dd else 'N/A'}顯示風險已大量釋放")
    _add_report_line(f"         Sharpe {sharpe if sharpe else 'N/A'}顯示風險回報吸引力有限，給予中性偏負面評分")
    _add_report_line("")
    
    # ===== 角色5: 情緒分析師 =====
    _add_report_line("【情緒分析師 (Sentiment Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ EnhancedNewsFeedProvider RSS新聞情緒分析")
    _add_report_line(f"   • 新聞情緒: {sentiment_result['news_sentiment']['sentiment']}")
    _add_report_line(f"   • 正面新聞: {sentiment_result['news_sentiment']['positive_count']}條")
    _add_report_line(f"   • 負面新聞: {sentiment_result['news_sentiment']['negative_count']}條")
    _add_report_line(f"   • 價格情緒: {sentiment_result['price_sentiment']:.2f}")
    _add_report_line(f"   • 綜合情緒: {sentiment_result['combined_label']} ({sentiment_result['combined_score']:.2f})")
    _add_report_line(f"   • 置信度: {sentiment_result['confidence']}")
    _add_report_line(f"   • RSS來源: {len(all_feeds)}類, {len(combined)}條")
    
    # v5.12 P34: sentiment_score 改用 multifactor（連續 tanh，保留正負號）
    _sentiment_combined = sentiment_result['combined_score']
    _sentiment_confidence = (
        0.8 if sentiment_result.get('confidence') == '高'
        else 0.5 if sentiment_result.get('confidence') == '中'
        else 0.3
    )
    _sentiment_news_count = (
        sentiment_result['news_sentiment']['positive_count'] +
        sentiment_result['news_sentiment']['negative_count']
    )
    sentiment_score = round(
        sentiment_score_multifactor(
            combined_score=_sentiment_combined,
            confidence=_sentiment_confidence,
            news_count=_sentiment_news_count,
        ),
        4,
    )
    # v5.13 (P36b) 連續化: sentiment_signal 從 hard threshold (±0.15) 改為 tanh soft band
    # v5.11.3 BUG: combined=0.14→neutral, 0.16→positive (硬切)
    _sent_signal, _sent_strength, _sent_conf_score = sentiment_signal_from_combined(_sentiment_combined)
    sentiment_signal = _sent_signal
    sentiment_confidence = sentiment_result['confidence']
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   新聞覆蓋: 正面{sentiment_result['news_sentiment']['positive_count']} vs 負面{sentiment_result['news_sentiment']['negative_count']} → 情緒略微偏正。")
    _add_report_line(f"   YTD {ytd_return:.1f}%已大概率反映悲觀預期，價格繼續下跌的邊際悲觀有限。")
    _add_report_line(f"   RSS來源涵蓋港/中/美三地，信息來源多元化。")
    _add_report_line(f"   市場情緒處於過度悲觀區域，關注均值回歸機會。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 新聞覆蓋: 正面{sentiment_result['news_sentiment']['positive_count']} vs 負面{sentiment_result['news_sentiment']['negative_count']} → 情緒略微偏正")
    _add_report_line(f"   • YTD {ytd_return:.1f}%已大概率反映悲觀預期，價格進一步下跌的邊際悲觀有限")
    _add_report_line(f"   • RSS來源涵蓋港/中/美三地，信息來源多元化")
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {sentiment_score:.3f}/1.00 | 信號: {sentiment_signal} | 置信度: {sentiment_confidence}")
    _add_report_line(f"   理由: 新聞情緒中性偏正面，YTD大幅下跌後價格進一步下跌的悲觀預期已被消化，")
    _add_report_line(f"         市場情緒處於過度悲觀區域，給予中性評分，關注均值回歸機會")
    _add_report_line("")
    
    # ===== 角色6: 新聞分析師 =====
    _add_report_line("【新聞分析師 (News Analyst)】")
    _add_report_line("-" * 80)
    
    _add_report_line("📊 數據來源：")
    _add_report_line(f"   ✅ EnhancedNewsFeedProvider RSS新聞聚合")
    _add_report_line(f"   • RSS類別: {list(all_feeds.keys())}")
    _add_report_line(f"   • 新聞總數: {len(combined)}條")
    for region in ["hk", "cn", "us"]:
        if region in all_feeds:
            _add_report_line(f"   • {region.upper()}: {len(all_feeds[region])}條")
    
    news_count = len(combined)
    # v5.12 P33: 統計 region 數 + source 數（從 all_feeds keys 推導）
    region_count = sum(1 for r in ["hk", "cn", "us"] if r in all_feeds)
    source_diversity = max(1, len(all_feeds) - 1)  # 扣掉 'all' key
    news_quality_score = round(
        news_score_multifactor(
            news_count=news_count,
            region_count=region_count,
            source_diversity=source_diversity,
        ),
        4,
    )
    news_coverage_desc = '覆蓋充足' if news_count >= 60 else '覆蓋一般' if news_count >= 30 else '覆蓋偏少'
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    _add_report_line(f"   新聞數量{news_count}條: {news_coverage_desc}。")
    _add_report_line(f"   區域分布: 覆蓋港/中/美三地，有助全面評估。")
    _add_report_line(f"   信息時效: RSS為實時或接近實時來源。")
    _add_report_line(f"   新聞覆蓋量{'充足' if news_count >= 60 else '中等'}，多元區域來源有助交叉驗證。")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    _add_report_line(f"   • 新聞數量 {news_count}條: {news_coverage_desc}")
    _add_report_line(f"   • 區域分布: 覆蓋港/中/美三地，有助全面評估")
    _add_report_line(f"   • 信息時效: RSS為實時或接近實時來源")
    
    news_score = news_quality_score
    news_signal = "neutral"
    news_confidence = "高" if news_count >= 60 else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    _add_report_line(f"   評分: {news_score:.3f}/1.00 | 信號: {news_signal} | 置信度: {news_confidence}")
    _add_report_line(f"   理由: 新聞覆蓋量{'充足' if news_count >= 60 else '中等'}，多元區域來源有助交叉驗證，給予中性偏正面評分")
    _add_report_line("")
    
    # ===== 角色7: 宏觀策略分析師 =====
    _add_report_line("【宏觀策略分析師 (Macro Strategy Analyst)】")
    _add_report_line("-" * 80)
    
    # v5.2: 重用並行 IO 結果中的宏觀分析（避免重複 yfinance 調用 ^TNX/^VIX/GC=F/DX-Y）
    _macro_result_obj = _io_results.get("macro") if isinstance(_io_results.get("macro"), dict) else None
    if _macro_result_obj and not _macro_result_obj.get("error"):
        macro_result = _macro_result_obj
    else:
        # Fallback：並行調用失敗時重新執行
        from data_sources.stock_data_provider import StockDataProvider
        _data_provider = StockDataProvider()
        _macro_analyst = MacroAnalyst(_data_provider)
        macro_result = _macro_analyst.analyze(STOCK_CODE, task_type="analysis", user_request="")
    
    macro_data = macro_result.get("macro_data", {})
    environment = macro_result.get("environment", {})
    score_dict = macro_result.get("score_dict", {})
    is_fallback = macro_data.get("⚠️ FALLBACK", True)
    
    _add_report_line("📊 數據來源：")
    if macro_data.get("us_10y_yield"):
        _add_report_line(f"   ✅ FRED 美國國債數據")
        _add_report_line(f"   • 美國10年期國債: {macro_data['us_10y_yield']:.2f}%")
    if macro_data.get("vix"):
        _add_report_line(f"   • VIX 波動率: {macro_data['vix']:.2f}")
    if macro_data.get("gold"):
        _add_report_line(f"   • 黃金: ${macro_data['gold']:.2f}")
    if macro_data.get("dxy"):
        _add_report_line(f"   • 美元指數: {macro_data['dxy']:.2f}")
    if macro_data.get("sp500"):
        _add_report_line(f"   • S&P 500: {macro_data['sp500']:.2f}")
    if is_fallback:
        _add_report_line(f"   ⚠️ FALLBACK: True (部分數據無法取得)")
    
    env_list = environment.get("environment_list", [])
    summary = score_dict.get("summary", "")
    
    _add_report_line("")
    _add_report_line("💡 核心論點：")
    for env_item in env_list:
        _add_report_line(f"   • {env_item}")
    if summary:
        _add_report_line(f"   • {summary}")
    
    _add_report_line("")
    _add_report_line("📈 關鍵證據：")
    for env_item in env_list:
        _add_report_line(f"   • {env_item}")
    if summary:
        _add_report_line(f"   • {summary}")
    
    macro_score = score_dict.get("confidence", 0.40)
    macro_signal = score_dict.get("signal", "sell")
    macro_confidence = "高" if not is_fallback else "中"
    
    _add_report_line("")
    _add_report_line("🎯 評估結論：")
    fallback_note = "（部分數據使用估算）" if is_fallback else ""
    _add_report_line(f"   評分: {macro_score:.3f}/1.00 | 信號: {macro_signal} | 置信度: {macro_confidence}")
    _add_report_line(f"   理由: {summary}{fallback_note}")
    _add_report_line("")
    
    # ============================================================
    # 第四階段：LLM 驅動辯論（專業格式）
    # ============================================================
    _log("PHASE4_START")
    
    _add_report_line("=" * 80)
    _add_report_line("【第四階段：MiniMax LLM 真實辯論記錄】")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    # 初始化LLM和辯論引擎
    miniMax = MiniMaxLLM()
    debate_engine = LLMDebateEngine(llm_integration=miniMax)
    
    _add_report_line("【LLM 配置】")
    _add_report_line(f"   MiniMax API: {'✅ 已啟用' if miniMax.enabled else '⚠️ 未啟用（使用模板）'}")
    _add_report_line(f"   模型: MiniMax-M2.7-highspeed")
    _add_report_line(f"   辯論輪次: {debate_engine.max_rounds}")
    _add_report_line("")
    
    # 初始立場
    initial_positions = {
        "market": {"score": market_score, "signal": market_signal, "summary": f"YTD {ytd_return:+.1f}%, 52週位置{pos_52wk:.1f}%, {pos_desc}"},
        "technical": {"score": tech_score, "signal": tech_signal, "summary": f"RSI {rsi:.1f}, MACD {macd_val:.4f}, {'超賣' if rsi < 35 else '中性'}"},
        "fundamental": {"score": fund_score, "signal": fund_signal, "summary": f"P/E {pe:.2f}, ROE {roe*100:.1f}%, PEG {peg_val if peg_val else 'N/A'}"},
        "risk": {"score": risk_score, "signal": risk_signal, "summary": f"波動性{volatility if volatility else 'N/A'}%, VaR {var_95 if var_95 else 'N/A'}%, Sharpe {sharpe if sharpe else 'N/A'}"},
        "sentiment": {"score": sentiment_score, "signal": sentiment_signal, "summary": f"新聞情緒{sentiment_result['combined_label']}({sentiment_result['combined_score']:.2f})"},
        "news": {"score": news_score, "signal": news_signal, "summary": f"新聞覆蓋{news_count}條, {news_coverage_desc}"},
        "macro": {"score": macro_score, "signal": macro_signal, "summary": summary[:100] if summary else "宏觀環境分析"}
    }
    
    _add_report_line("【初始立場】")
    for name, pos in initial_positions.items():
        bar = "█" * int(pos["score"] * 10) + "░" * (10 - int(pos["score"] * 10))
        icon = "✅" if pos["score"] >= 0.6 else "❌" if pos["score"] < 0.4 else "⚠️"
        _add_report_line(f"   {icon} {name:12s}: [{bar}] {pos['score']:.3f} ({pos['signal']})")
    _add_report_line("")
    
    # 註冊7位分析師到辯論引擎
    role_to_analyst = {
        "market": ("market", "市場分析師"),
        "technical": ("technical", "技術分析師"),
        "fundamental": ("fundamental", "基本面分析師"),
        "risk": ("risk", "風險分析師"),
        "sentiment": ("sentiment", "情緒分析師"),
        "news": ("news", "新聞分析師"),
        "macro": ("macro", "宏觀策略師"),
    }
    for name, (role, role_name) in role_to_analyst.items():
        debate_engine.register_analyst(name, role, initial_positions[name])
    
    # 執行LLM辯論
    _add_report_line("【執行LLM辯論...】（需要30-60秒，MiniMax API調用）")
    debate_result = debate_engine.run_debate(STOCK_CODE)
    _add_report_line("")
    
    _add_report_line("【辯論配置】")
    _add_report_line(f"   總輪數: {debate_result['rounds_completed']} | 總消息數: {debate_result['total_messages']}")
    _add_report_line(f"   分析師數: {len(debate_result['analysts'])}")
    _add_report_line("")
    
    # 完整辯論訊息（每輪每個角色的詳細記錄）
    type_icons = {
        "argument": "📢論點",
        "challenge": "❓挑戰",
        "counter": "🔄反駁",
        "concede": "👍讓步",
        "compromise": "🤝妥協",
        "support": "💪支持",
        "warning": "⚠️警告",
        "observation": "👁️觀察",
        "analysis": "📊分析",
        "data": "📈數據",
        "summary": "📋總結",
        "final": "🏁裁決"
    }
    
    # 組織辯論記錄（按輪次和角色）
    _add_report_line("【MiniMax LLM 真實辯論記錄】")
    _add_report_line("=" * 80)
    
    debate_log = debate_result.get("debate_log", [])
    
    # 按輪次分組呈現
    rounds_data = {}
    for entry in debate_log:
        rnd = entry.get("round", 0)
        if rnd not in rounds_data:
            rounds_data[rnd] = []
        rounds_data[rnd].append(entry)
    
    for rnd in sorted(rounds_data.keys()):
        _add_report_line("")
        _add_report_line(f"━━━ 第 {rnd} 輪辯論 ━━━")
        _add_report_line("-" * 80)
        
        for entry in rounds_data[rnd]:
            msg_type = entry.get("type", "argument")
            icon = type_icons.get(msg_type, f"•{msg_type}")
            
            _add_report_line(f"  {icon}")
            _add_report_line(f"     角色: {entry.get('from', '?')} → {entry.get('to', '?')}")
            
            content = entry.get("content", {})
            if content.get("argument"):
                _add_report_line(f"     論點: {content['argument']}")
            if content.get("challenge"):
                _add_report_line(f"     挑戰: {content['challenge']}")
            if content.get("evidence"):
                ev = content["evidence"]
                if isinstance(ev, list) and len(ev) > 0:
                    _add_report_line(f"     證據: {', '.join(str(e) for e in ev[:3])}")
                elif isinstance(ev, str):
                    _add_report_line(f"     證據: {ev}")
            if content.get("concession"):
                _add_report_line(f"     讓步: {content['concession']}")
            if content.get("adjustment") is not None:
                adj = content["adjustment"]
                _add_report_line(f"     調整幅度: {adj:+.4f}")
            if content.get("⚠️ LLM_GENERATED"):
                _add_report_line(f"     ⚠️ LLM生成標記: True")
    
    _add_report_line("")
    _add_report_line("【辯論後立場變化】")
    _add_report_line("-" * 80)
    
    analysts_result = debate_result.get("analysts", {})
    for name, init_pos in initial_positions.items():
        initial = init_pos["score"]
        final_data = analysts_result.get(name, {})
        final = final_data.get("final_score", initial)
        change = final - initial
        concessions = final_data.get("concessions", 0)
        if abs(change) > 0.001:
            _add_report_line(f"   {name:12s}: {initial:.3f} → {final:.3f} ({'+' if change > 0 else ''}{change:.4f}) | 讓步次數: {concessions}")
        else:
            _add_report_line(f"   {name:12s}: {initial:.3f} (不變) | 讓步次數: {concessions}")
    _add_report_line("")
    
    # 共識結論
    consensus = debate_result.get("consensus", {})
    
    _add_report_line("【共識形成過程】")
    _add_report_line("-" * 80)
    if consensus:
        bull_case = consensus.get("bull_case", "")
        bear_case = consensus.get("bear_case", "")
        consensus_signal = consensus.get("consensus_signal", "N/A")
        confidence = consensus.get("confidence", 0)
        
        _add_report_line(f"   共識信號: {consensus_signal}")
        _add_report_line(f"   置信度: {confidence:.2f}")
        if bull_case:
            _add_report_line(f"   看漲理由: {bull_case}")
        if bear_case:
            _add_report_line(f"   看跌理由: {bear_case}")
        
        # 顯示其他共識細節
        for key, val in consensus.items():
            if key not in ("bull_case", "bear_case", "details", "llm_raw", "consensus_signal", "confidence"):
                _add_report_line(f"   {key}: {val}")
    else:
        _add_report_line("   (共識生成中...)")
    _add_report_line("")
    
    _add_report_line("【主要分歧點】")
    _add_report_line("-" * 80)
    disagreement_found = False
    for name, data in analysts_result.items():
        concessions = data.get("concessions", 0)
        initial = initial_positions[name]["score"]
        final = data.get("final_score", initial)
        change = abs(final - initial)
        
        if concessions > 0 or change > 0.05:
            disagreement_found = True
            _add_report_line(f"   ⚔️ {name}: 做出{concessions}次讓步，評分變化{change:.4f}")
            if concessions > 0:
                # 顯示該角色的LLM生成論點
                analyst_obj = debate_engine.analysts.get(name)
                if analyst_obj and analyst_obj.get("llm_generated_arguments"):
                    latest_args = analyst_obj["llm_generated_arguments"][-1]
                    if latest_args.get("argument"):
                        _add_report_line(f"      最新論點: {latest_args['argument'][:80]}...")
    
    if not disagreement_found:
        _add_report_line("   (各分析師立場相對一致)")
    _add_report_line("")
    
    # 從initial_positions建立final_positions字典（向後相容）
    final_positions = {
        name: {"score": analysts_result.get(name, {}).get("final_score", init_pos["score"]), "signal": init_pos["signal"]}
        for name, init_pos in initial_positions.items()
    }

    # ============================================================
    # 第四階段 B：ConsensusEngine 數學共識（v5.1 新增）
    # 與 LLM 語義共識並行，提供多因子置信度 + 衝突檢測 + 5-tier 信號
    # ============================================================
    _log("PHASE4B_CONSENSUS")

    _add_report_line("=" * 80)
    _add_report_line("【共識引擎數學共識（7分析師加權整合）】")
    _add_report_line("-" * 80)

    _analyst_results_for_ce = {}
    for name, pos in final_positions.items():
        bhs = score_to_bhs(pos["score"])  # v5.7: 直接用 module-level 純函數（去除 wrapper）
        _analyst_results_for_ce[name] = {
            "signal": pos["signal"],
            "score": pos["score"],
            "buy_score": bhs["buy"],
            "hold_score": bhs["hold"],
            "sell_score": bhs["sell"],
            "confidence": pos["score"],  # 暫用 score 作為 confidence 代理
        }

    # 5-tier 信號映射（v5.7: 直接使用 module-level score_to_5tier 純函數）
    _signal_to_5tier = {
        "strong_buy": 5, "buy": 4,
        "hold": 3, "neutral": 3,
        "sell": 2, "strong_sell": 1,
    }

    _ce_consensus = {}
    try:
        # v5.4: 刪除 consensus/ shim，直接 import 實際位置
        from train.consensus_engine import ConsensusEngine as _CE
        _ce_engine = _CE()
        # D4 修復：用 _ce_engine 直接整合（保留 buy/hold/sell 字段空→引擎用默認權重）
        _ce_consensus = _ce_engine.integrate(_analyst_results_for_ce, "full", STOCK_CODE)
        _c = _ce_consensus["consensus"]
        _overall = _c["overall"]  # -100..+100
        _add_report_line(f"   📊 買入比例: {_c['buy']:.1f}% | 持有: {_c['hold']:.1f}% | 賣出: {_c['sell']:.1f}%")
        _add_report_line(f"   🎯 整體得分: {_overall:+.1f} (範圍 -100..+100)")
        _add_report_line(f"   🤖 數學建議: {_ce_consensus['recommendation']}")
        _add_report_line(f"   🔒 多因子置信度: {_ce_consensus['confidence']:.2f}")
        # 衝突檢測
        if _ce_consensus.get("conflicts"):
            for _cf in _ce_consensus["conflicts"]:
                _add_report_line(f"   ⚠️ 衝突: {_cf.get('type')} ({_cf.get('severity')})")
                if _cf.get("buy_analysts") and _cf.get("sell_analysts"):
                    _add_report_line(f"      買方: {', '.join(_cf['buy_analysts'])} | 賣方: {', '.join(_cf['sell_analysts'])}")
        _log(f"CE_CONSENSUS ok overall={_overall:.1f} conf={_ce_consensus['confidence']:.2f}")
    except Exception as _e:
        _add_report_line(f"   ⚠️ ConsensusEngine 整合失敗: {_e}")
        _log(f"CE_CONSENSUS failed: {_e}")

    # ============================================================
    # 第五階段：共識計算
    # ============================================================
    _log("PHASE5_START")
    
    _add_report_line("=" * 80)
    _add_report_line("【第五階段：共識計算與最終評分】")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    # v5.12 P35: 改用 dynamic_weights_for_ticker（按 ticker profile 動態調整）
    weights = dynamic_weights_for_ticker(STOCK_CODE)
    
    final_scores = {name: pos["score"] for name, pos in final_positions.items()}

    _add_report_line("【加權評分計算】")
    # v5.12 P32: 改用 weighted_score_with_variance_penalty（含 analyst disagreement 折扣）
    # 仍逐行輸出各 role 進度（保留原 visual bar），最後套用 variance penalty
    weighted_sum_no_penalty = 0.0
    for role, w in weights.items():
        score = final_scores.get(role, 0)
        contrib = score * w
        weighted_sum_no_penalty += contrib
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        icon = "✅" if score >= 0.6 else "❌" if score < 0.4 else "⚠️"
        _add_report_line(f"   {icon} {role:12s}: [{bar}] {score:.3f} × {w:.2f} = {contrib:.4f}")

    # v5.12 P32: variance penalty（disagreement 折扣）
    final_score, analyst_disagreement = weighted_score_with_variance_penalty(
        scores=final_scores, weights=weights
    )
    weighted_sum = final_score  # for backward-compat log

    if analyst_disagreement > 0.15:
        _add_report_line(f"   ⚠️ 分析師分歧: std={analyst_disagreement:.3f}（> 0.15，信心折扣啟動）")
    _add_report_line("")
    _add_report_line(f"   加權總分（無 penalty）: {weighted_sum_no_penalty:.4f}")
    _add_report_line(f"   加權總分（含 penalty）: {final_score:.4f}")
    _add_report_line("")
    rec = "🟢 強烈買入" if final_score > 0.70 else "🟢 適度買入" if final_score > 0.60 else "🟡 持有觀望" if final_score > 0.50 else "🟠 謹慎持有" if final_score > 0.40 else "🔴 減持"
    
    # ===== P17: 分析師評分持久化追蹤 =====
    try:
        from analyst_tracker import AnalystTracker
        _tracker = AnalystTracker()
        _tracker.log_analyst_results(symbol=STOCK_CODE, analyst_results=final_positions)
        _add_report_line("✅ P17 分析師評分已記錄")
    except Exception as _e:
        _add_report_line(f"⚠️ P17 記錄失敗: {_e}")
    
    # ============================================================
    # 最終報告：專業投資建議框架
    # ============================================================
    _add_report_line("=" * 80)
    _add_report_line(f"📊 {STOCK_NAME} ({STOCK_CODE}) 專業投資分析報告")
    _add_report_line(f"📅 分析時間: {ANALYSIS_TIME}")
    _add_report_line(f"🔧 辯論引擎: MiniMax LLM (真實AI生成，非模板)")
    _add_report_line("=" * 80)
    _add_report_line("")
    
    _add_report_line("【投資建議框架】")
    _add_report_line("-" * 80)
    _add_report_line(f"現價：{_currency_symbol}{price:.2f}")
    _add_report_line("")
    
    # 根據評分計算目標價和止損價
    if final_score > 0.70:
        short_target = price * 1.12
        short_stop = price * 0.92
        mid_target = price * 1.25
        mid_stop = price * 0.85
        long_target = price * 1.45
        long_stop = price * 0.75
    elif final_score > 0.60:
        short_target = price * 1.08
        short_stop = price * 0.90
        mid_target = price * 1.18
        mid_stop = price * 0.82
        long_target = price * 1.35
        long_stop = price * 0.72
    elif final_score > 0.50:
        short_target = price * 1.05
        short_stop = price * 0.93
        mid_target = price * 1.12
        mid_stop = price * 0.85
        long_target = price * 1.22
        long_stop = price * 0.78
    else:
        short_target = price * 1.03
        short_stop = price * 0.95
        mid_target = price * 1.08
        mid_stop = price * 0.88
        long_target = price * 1.15
        long_stop = price * 0.82
    
    range_tolerance = 0.03
    short_logic = f"基於技術面RSI {rsi:.1f}顯示{'超賣' if rsi < 40 else '中性'}，短線可能出現技術性反彈。建議在{range_tolerance:.0%}區間內分批建倉。"
    mid_logic = f"中期來看，P/E {pe:.2f}估值{pe_desc}，結合YTD {ytd_return:+.1f}%的回調，估值修復空間中長線顯現。"
    long_logic = f"長期投資需關注宏觀環境變化。若ROE {roe*100:.1f}%能持續，疊加營收增長{revenue_growth*100:.1f}%，股價有望逐步回歸合理價值。"
    
    _add_report_line("🟡 短期（1-4週）：持有觀望")
    _add_report_line(f"   入手價：{_currency_symbol}{price * (1 - range_tolerance):.2f}（-{range_tolerance*100:.0f}%）~ {_currency_symbol}{price * (1 + range_tolerance):.2f}（+{range_tolerance*100:.0f}%）")
    _add_report_line(f"   目標價：{_currency_symbol}{short_target:.2f}（+{(short_target/price-1)*100:.1f}%）")
    _add_report_line(f"   止損價：{_currency_symbol}{short_stop:.2f}（-{(1-short_stop/price)*100:.1f}%）")
    _add_report_line(f"   邏輯：{short_logic}")
    _add_report_line("")
    
    _add_report_line("🟡 中期（1-6個月）：適度增持")
    _add_report_line(f"   入手價：{_currency_symbol}{price * 0.95:.2f}（-5%）~ {_currency_symbol}{price * 1.02:.2f}（+2%）")
    _add_report_line(f"   目標價：{_currency_symbol}{mid_target:.2f}（+{(mid_target/price-1)*100:.1f}%）")
    _add_report_line(f"   止損價：{_currency_symbol}{mid_stop:.2f}（-{(1-mid_stop/price)*100:.1f}%）")
    _add_report_line(f"   邏輯：{mid_logic}")
    _add_report_line("")
    
    _add_report_line("🟢 長期（6-12個月）：戰略性持有")
    _add_report_line(f"   入手價：{_currency_symbol}{price * 0.90:.2f}（-10%）~ {_currency_symbol}{price * 1.05:.2f}（+5%）")
    _add_report_line(f"   目標價：{_currency_symbol}{long_target:.2f}（+{(long_target/price-1)*100:.1f}%）")
    _add_report_line(f"   止損價：{_currency_symbol}{long_stop:.2f}（-{(1-long_stop/price)*100:.1f}%）")
    _add_report_line(f"   邏輯：{long_logic}")
    _add_report_line("")
    
    # 風險警示
    _add_report_line("【風險警示】")
    _add_report_line("-" * 80)
    _add_report_line(f"   1. 波動性風險：年化波動性{f'{volatility:.1f}%' if volatility else 'N/A'}，高於大盤，投資者需留意短期回調")
    _add_report_line(f"   2. 市場風險：VaR (95%) {f'{var_95:.2f}%' if var_95 else 'N/A'}，明日有5%機率損失超此比例")
    _add_report_line(f"   3. 流動性風險：平均成交量 {volume:,} 股，需關注大額交易衝擊成本")
    _add_report_line(f"   4. 槓桿風險：Beta {beta:.2f}，{'高' if beta > 1.2 else '低'}於大盤波動")
    if max_dd:
        _add_report_line(f"   5. 回撤風險：歷史最大回撤 {max_dd:.1f}%，需評估自身風險承受力")
    _add_report_line(f"   6. 宏觀風險：若利率上行或地緣政治升溫，可能壓制估值")
    if sharpe and sharpe < 0:
        _add_report_line(f"   7. Sharpe Ratio {sharpe:.2f} < 0，風險調整後回報為負")
    _add_report_line("")
    
    # 各角色評分對照表
    _add_report_line("【各角色評分對照表】")
    _add_report_line("-" * 80)
    _add_report_line(f"   {'角色':12s} | {'評分':^8s} | {'信號':^8s} | {'狀態':^4s} | 評分依據")
    _add_report_line("   " + "-" * 76)
    role_info = [
        ("市場", market_score, market_signal, initial_positions["market"]["score"], final_scores.get("market", market_score)),
        ("技術", tech_score, tech_signal, initial_positions["technical"]["score"], final_scores.get("technical", tech_score)),
        ("基本面", fund_score, fund_signal, initial_positions["fundamental"]["score"], final_scores.get("fundamental", fund_score)),
        ("風險", risk_score, risk_signal, initial_positions["risk"]["score"], final_scores.get("risk", risk_score)),
        ("情緒", sentiment_score, sentiment_signal, initial_positions["sentiment"]["score"], final_scores.get("sentiment", sentiment_score)),
        ("新聞", news_score, news_signal, initial_positions["news"]["score"], final_scores.get("news", news_score)),
        ("宏觀", macro_score, macro_signal, initial_positions["macro"]["score"], final_scores.get("macro", macro_score)),
    ]
    for name, init_s, sig, orig_init, final_s in role_info:
        bar = "█" * int(final_s * 10) + "░" * (10 - int(final_s * 10))
        icon = "✅" if final_s >= 0.6 else "❌" if final_s < 0.4 else "⚠️"
        chg = final_s - orig_init
        chg_str = f"({'+' if chg > 0 else ''}{chg:.3f})" if abs(chg) > 0.001 else "(不變)"
        _add_report_line(f"   {name:12s} | [{bar}] | {sig:^8s} | {icon:^4s} | 辯論後 {final_s:.3f} {chg_str}")
    
    _add_report_line("")
    
    # 關鍵數據總結
    _add_report_line("【關鍵數據總結】")
    _add_report_line("-" * 80)
    _add_report_line(f"   價格: {_currency_symbol}{price:.2f} | YTD: {ytd_return:+.1f}% | 距高點: {from_high_pct:+.1f}%")
    _add_report_line(f"   P/E: {pe:.2f} | ROE: {roe*100:.1f}% | PEG: {f'{peg_val:.2f}' if peg_val else 'N/A'}")
    _add_report_line(f"   RSI: {rsi:.1f} | MACD: {macd_val:.4f} | 波動性: {f'{volatility:.1f}%' if volatility else 'N/A'}")
    _add_report_line(f"   新聞情緒: {sentiment_result['combined_label']} ({sentiment_result['combined_score']:+.2f})")
    
    # 初始化結果字典（供 P16/P17/P18 提前寫入）
    _result = {}
    
    # ===== P18: RSI/乖離率警報 =====
    try:
        from alert_engine import check_alerts, format_alerts
        _alerts = check_alerts(STOCK_CODE)
        if _alerts:
            _add_report_line("")
            _add_report_line("【P18 技術警報】")
            for _a in _alerts:
                _em = "🟢" if _a["signal"] == "BUY" else "🔴"
                _add_report_line(f"   {_em} {_a['message']}")
            _result["alerts"] = _alerts
        _result["rsi"] = round(rsi, 1)
    except Exception as _e:
        _add_report_line(f"⚠️ 警報檢查失敗: {_e}")
    _add_report_line("")
    
    # 最終評分與建議
    _add_report_line("【最終綜合評估】")
    _add_report_line("-" * 80)
    _add_report_line(f"   📊 綜合評分: {final_score:.2f}/1.00")
    _add_report_line(f"   📌 投資建議: {rec}")
    # v5.1: 結合 LLM 語義置信度 + ConsensusEngine 數學置信度
    # D8 修復：使用 min() + 加權平均（max 0.3 weight）— 過度保守會誤導
    _llm_conf = (consensus.get("confidence", 0) if consensus else 0) or 0
    _ce_conf = _ce_consensus.get("confidence", 0) if _ce_consensus else 0
    if _ce_conf > 0 and _llm_conf > 0:
        # 兩者都有：用 min 作為基線，再用 +5% 加權補強（避免雙方都 0.5 結果仍 0.5）
        _combined_confidence = round(min(_llm_conf, _ce_conf) * 0.7 + max(_llm_conf, _ce_conf) * 0.3, 3)
    else:
        _combined_confidence = _llm_conf or _ce_conf or final_score
    if _ce_conf > 0:
        _add_report_line(f"   🎯 置信度（LLM 語義）: {_llm_conf:.2f}")
        _add_report_line(f"   🔒 置信度（ConsensusEngine 數學）: {_ce_conf:.2f}")
        _add_report_line(f"   🛡️  合併置信度（min×0.7 + max×0.3）: {_combined_confidence:.3f}")
    elif _llm_conf:
        _add_report_line(f"   🎯 置信度: {_llm_conf:.2f}")
    consensus = consensus or {}  # 確保 dict 存在
    consensus["confidence"] = _combined_confidence or final_score  # 覆寫

    # ===== P16: 置信度加權倉位計算 =====
    try:
        from position_sizer import calculate_position_size, format_position_report
        _ps = calculate_position_size(
            ticker=STOCK_CODE,
            confidence=_combined_confidence or final_score,
            final_score=final_score,
            account_size=100000.0
        )
        _add_report_line("")
        _add_report_line("【P16 倉位計算】")
        _add_report_line(format_position_report(_ps))
        _result["position_sizing"] = _ps
    except Exception as _e:
        _add_report_line(f"⚠️ 倉位計算失敗: {_e}")
    
    _add_report_line("")
    _add_report_line("✅ 分析完成 (v5 專業投資報告格式)")
    _add_report_line("")
    
    # ===== JSON 結果保存 =====
    try:
        _result["stock"] = STOCK_CODE
        _result["stock_name"] = STOCK_NAME
        _result["price"] = price
        _result["ytd_return"] = round(ytd_return, 2)
        _result["week52_high"] = round(week52_high, 2)
        _result["week52_low"] = round(week52_low, 2)
        _result["pe"] = round(pe, 2)
        _result["roe"] = round(roe, 2)
        _result["rsi"] = round(rsi, 2)
        _result["macd"] = round(macd_val, 4)
        _result["volatility"] = round(volatility, 2) if volatility else None
        _result["var_95"] = round(var_95, 2) if var_95 else None
        _result["max_drawdown"] = round(max_dd, 2) if max_dd else None
        _result["sharpe"] = round(sharpe, 2) if sharpe else None
        _result["analysts"] = {name: {"score": pos["score"], "signal": pos["signal"]} for name, pos in final_positions.items()}
        _result["weighted_score"] = round(weighted_sum, 4)
        _result["final_score"] = round(final_score, 4)
        _result["recommendation"] = rec
        _result["consensus_signal"] = consensus.get("consensus_signal", "hold") if consensus else "hold"
        _result["confidence"] = round(_combined_confidence or (consensus.get("confidence", final_score) if consensus else final_score), 3)
        # v5.1: ConsensusEngine 數學共識
        if _ce_consensus:
            _result["math_consensus"] = {
                "buy_pct": _ce_consensus["consensus"]["buy"],
                "hold_pct": _ce_consensus["consensus"]["hold"],
                "sell_pct": _ce_consensus["consensus"]["sell"],
                "overall_score": _ce_consensus["consensus"]["overall"],
                "math_recommendation": _ce_consensus["recommendation"],
                "math_confidence": _ce_consensus["confidence"],
                "conflicts": _ce_consensus.get("conflicts", []),
                "consensus_signal_5tier": score_to_5tier(_ce_consensus["consensus"]["overall"]),
            }
        _result["target_prices"] = {
            "short_term": round(short_target, 2),
            "mid_term": round(mid_target, 2),
            "long_term": round(long_target, 2)
        }
        _result["stop_losses"] = {
            "short_term": round(short_stop, 2),
            "mid_term": round(mid_stop, 2),
            "long_term": round(long_stop, 2)
        }
        _result["news_count"] = len(combined)
        _result["sentiment"] = sentiment_result["combined_label"]
        _result["debate_rounds"] = debate_result["rounds_completed"]
        _result["debate_messages"] = debate_result["total_messages"]
        _result["analysis_time"] = ANALYSIS_TIME
        _result["output_dir"] = OUTPUT_DIR
        _json_path = os.path.join(OUTPUT_DIR, "analysis_result.json")
        with open(_json_path, "w", encoding="utf-8") as _f:
            json.dump(_json_safe(_result), _f, ensure_ascii=False, indent=2)
        _add_report_line(f"📄 JSON結果已保存: {_json_path}")
    except Exception as e:
        _add_report_line(f"⚠️ JSON保存失敗: {e}")
    
    # ===== 文本報告保存 =====
    try:
        _report_path = os.path.join(OUTPUT_DIR, "analysis_report.txt")
        with open(_report_path, "w", encoding="utf-8") as _f:
            _f.write("\n".join(_report_lines))
        _add_report_line(f"📄 文本報告已保存: {_report_path}")
    except Exception as e:
        _add_report_line(f"⚠️ 報告保存失敗: {e}")
    
    # ===== P13: 自動回測（過去 90 天）=====
    try:
        from backtest_engine import run_backtest
        _add_report_line("")
        _add_report_line("【P13 自動回測】")
        _bt = run_backtest(STOCK_CODE, days=90)
        if _bt and "error" not in _bt and _bt.get("effective_predictions", 0) >= 5:
            _btm = _bt.get("metrics", {})
            _add_report_line(f"   📊 總預測次數: {_bt.get('effective_predictions', 0)}")
            _add_report_line(f"   🎯 整體準確度: {_btm.get('overall_accuracy', 0)*100:.1f}%")
            _add_report_line(f"   📈 Buy 精準度: {_btm.get('precision_buy', 0)*100:.1f}%")
            _add_report_line(f"   📉 Sell 精準度: {_btm.get('precision_sell', 0)*100:.1f}%")
            _add_report_line(f"   📊 Buy/Sell/Hold: {_bt['signal_counts'].get('buy', 0)}/{_bt['signal_counts'].get('sell', 0)}/{_bt['signal_counts'].get('hold', 0)}")
            _bt_dir = Path.home() / ".hermes" / "stock_backtest"
            _bt_dir.mkdir(exist_ok=True)
            _bt_path = _bt_dir / f"{STOCK_CODE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(_bt_path, "w", encoding="utf-8") as _f:
                json.dump(_json_safe(_bt), _f, ensure_ascii=False, indent=2)
            _add_report_line(f"   ✅ 回測報告已保存: {_bt_path}")
        else:
            _add_report_line("   ⚠️ 回測數據不足（< 90 天歷史）")
    except Exception as _e:
        _add_report_line(f"⚠️ 自動回測失敗: {_e}")
    
    _add_report_line(f"📁 輸出目錄: {OUTPUT_DIR}")

    # ===== ASCII 雷達圖內聯版（原 report_generator.py 核心邏輯）=====
    def _ascii_radar_chart(scores: dict) -> str:
        """7 維度 ASCII 雷達圖（內聯版，原 report_generator.py:111 移植）"""
        import math
        _max_radius = 6
        _angles = {"market":90, "technical":45, "fundamental":315, "risk":270,
                   "sentiment":225, "news":135, "macro":180}
        _grid_size = 15
        _center = _grid_size // 2
        _grid = [[" " for _ in range(_grid_size)] for _ in range(_grid_size)]
        for _dim, _ang in _angles.items():
            _sc = max(0.0, min(1.0, scores.get(_dim, 0.5)))
            _sr = 1 + _sc * (_max_radius - 1)
            for _r in range(1, _max_radius + 1):
                _x = _r * math.cos(math.radians(_ang))
                _y = _r * math.sin(math.radians(_ang))
                _gx = int(round(_center + _x))
                _gy = int(round(_center - _y))
                if 0 <= _gx < _grid_size and 0 <= _gy < _grid_size:
                    _grid[_gy][_gx] = "●" if abs(_r - _sr) < 1.0 else "·"
        return "\n".join("".join(row) for row in _grid)

    # ===== v5.3 真正整合 HTML 報告生成（1,270 行 stock_html_report.py 從未被調用）=====
    try:
        from generate.stock_html_report import generate_html_report as _gen_html
        _add_report_line("")
        _add_report_line("【HTML 報告生成】")
        _html_path = _gen_html(_result, OUTPUT_DIR)
        if _html_path and os.path.exists(_html_path):
            _add_report_line(f"   📊 HTML 報告: {_html_path}")
            _add_report_line(f"   📦 檔案大小: {os.path.getsize(_html_path):,} bytes")
        else:
            _add_report_line(f"   ⚠️ HTML 報告生成失敗（路徑不存在）")
    except Exception as _e:
        _add_report_line(f"   ⚠️ HTML 報告生成異常: {_e}")

    # ===== Markdown 報告生成（內聯 ascii_radar_chart）=====
    try:
        _md_path = os.path.join(OUTPUT_DIR, "analysis_report.md")
        _analyst_scores = {n: pos["score"] for n, pos in final_positions.items()}
        _ascii_radar = _ascii_radar_chart(_analyst_scores)
        with open(_md_path, "w", encoding="utf-8") as _f:
            _f.write(f"# {STOCK_NAME} ({STOCK_CODE}) 投資分析報告\n\n")
            _f.write(f"> **分析時間**: {ANALYSIS_TIME}  \n")
            _f.write(f"> **綜合評分**: {final_score:.3f}/1.00  \n")
            _f.write(f"> **投資建議**: {rec}  \n")
            _f.write(f"> **置信度**: {_combined_confidence:.3f}\n\n")
            _f.write("## 7 維度評分雷達圖\n\n```\n")
            _f.write(_ascii_radar)
            _f.write("\n```\n\n")
            _f.write("## 7 維度評分明細\n\n| 維度 | 評分 | 信號 | 摘要 |\n")
            _f.write("|------|------|------|------|\n")
            _dim_label = {"market":"市場", "technical":"技術", "fundamental":"基本面",
                          "risk":"風險", "sentiment":"情緒", "news":"新聞", "macro":"宏觀"}
            for n in ["market","technical","fundamental","risk","sentiment","news","macro"]:
                _p = initial_positions.get(n, {})
                _f.write(f"| {_dim_label[n]} | {_p.get('score', 0):.3f} | "
                         f"{_p.get('signal', '?')} | {_p.get('summary', '')} |\n")
            if _ce_consensus:
                _c = _ce_consensus["consensus"]
                _f.write(f"\n## 數學共識（ConsensusEngine）\n\n")
                _f.write(f"- 買入: {_c['buy']:.1f}% | 持有: {_c['hold']:.1f}% | 賣出: {_c['sell']:.1f}%\n")
                _f.write(f"- 整體得分: {_c['overall']:+.1f} (-100..+100)\n")
                _f.write(f"- 5-Tier 信號: {score_to_5tier(_c['overall'])} (1=強賣, 5=強買)\n")
                _f.write(f"- 多因子置信度: {_ce_consensus['confidence']:.3f}\n")
                if _ce_consensus.get("conflicts"):
                    _f.write(f"- ⚠️ 衝突: {len(_ce_consensus['conflicts'])} 個\n")
        _add_report_line(f"   📝 Markdown 報告: {_md_path}")
    except Exception as _e:
        _add_report_line(f"   ⚠️ Markdown 報告生成失敗: {_e}")

    # ===== WhatsApp 自動發送已停用（2026-06-14 用戶要求）=====
    _add_report_line("")
    _add_report_line("【WhatsApp 推送已停用】")
