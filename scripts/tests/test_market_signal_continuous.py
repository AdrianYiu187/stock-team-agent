"""
v5.13 P36 — market_signal 連續化測試

Pitfall 背景（v5.12 closure 量化結論）：
- v5.5/v5.6 引入 4 個 multifactor 連續函數（0-1 連續）
- 但最終決策層 L938: market_signal = "buy" if market_score > 0.6 else "sell" if market_score < 0.4 else "neutral"
- 連續函數的意義被 2pp 差距抵消：market_score=0.59 → neutral, market_score=0.61 → buy
- 違反 v5.11/v5.12「連續線性、無 cap、無 hard cut」精神

v5.13 P36 修法：
- 引入 `market_signal_from_score(score, midpoint=0.5, k=12)` 函數
- 輸出 (signal, strength, confidence)
- strength = sigmoid(score, midpoint, k) — 連續 0-1
- signal = "buy"/"sell"/"neutral" — 離散標籤（保留向後兼容）
- confidence = abs(strength - 0.5) * 2 — 距中位數越遠越自信

驗證目標（Rule 4 量化）：
1. 單調性：score 上升 → strength 上升
2. 中點：score=midpoint → strength=0.5 → neutral + confidence=0
3. 邊界：score=0 → strength<0.05（sell），score=1 → strength>0.95（buy）
4. 向後兼容：score=0.59（v5.11.3 neutral）→ strength=0.65（v5.13 buy，修正 hard cut）
5. 平滑：score 變化 0.01 → strength 變化 < 0.05
6. 對稱：score 距 midpoint 等距 → strength 等距
7. 邊界信號：score=0.39 → sell, score=0.61 → buy（單調邊界）
8. 函數存在：market_signal_from_score 在 stock_analysis 模組內可 import
"""
import math
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stock_analysis


# ============ 函數存在性檢查 ============

class TestP36FunctionExists:
    def test_market_signal_from_score_exists(self):
        """market_signal_from_score 函數已定義"""
        assert hasattr(stock_analysis, "market_signal_from_score"), \
            "v5.13 P36: market_signal_from_score 函數未定義"
        assert callable(stock_analysis.market_signal_from_score), \
            "v5.13 P36: market_signal_from_score 不是可調用函數"

    def test_returns_tuple_of_three(self):
        """函數返回 (signal, strength, confidence) 三元組"""
        result = stock_analysis.market_signal_from_score(0.5)
        assert isinstance(result, tuple), "應返回 tuple"
        assert len(result) == 3, "應返回 3 個值"
        signal, strength, confidence = result
        assert signal in ("buy", "sell", "neutral"), \
            f"signal 應為 buy/sell/neutral，got {signal}"
        assert 0.0 <= strength <= 1.0, f"strength 應在 [0, 1]，got {strength}"
        assert 0.0 <= confidence <= 1.0, f"confidence 應在 [0, 1]，got {confidence}"


# ============ 單調性測試（Rule 8：測試驗證「為什麼」） ============

class TestP36Monotonicity:
    def test_score_increases_strength_increases(self):
        """score 上升 → strength 上升（sigmoid 單調遞增）"""
        scores = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        strengths = [stock_analysis.market_signal_from_score(s)[1] for s in scores]
        for i in range(len(strengths) - 1):
            assert strengths[i] < strengths[i + 1], \
                f"score={scores[i]}→{scores[i+1]} 應單調遞增，但 strength={strengths[i]}→{strengths[i+1]}"


# ============ 中點 + 邊界測試 ============

class TestP36Boundaries:
    def test_midpoint_returns_neutral_zero_confidence(self):
        """score=midpoint → strength=0.5, signal=neutral, confidence=0"""
        signal, strength, confidence = stock_analysis.market_signal_from_score(0.5)
        assert abs(strength - 0.5) < 0.01, f"midpoint 應 strength=0.5, got {strength}"
        assert signal == "neutral", f"midpoint 應 signal=neutral, got {signal}"
        assert abs(confidence - 0.0) < 0.01, f"midpoint 應 confidence=0, got {confidence}"

    def test_extreme_low_returns_sell_high_confidence(self):
        """score=0 → strength≈0, signal=sell, confidence≈1"""
        signal, strength, confidence = stock_analysis.market_signal_from_score(0.0)
        assert strength < 0.05, f"score=0 應 strength<0.05, got {strength}"
        assert signal == "sell", f"score=0 應 signal=sell, got {signal}"
        assert confidence > 0.90, f"score=0 應 confidence>0.90, got {confidence}"

    def test_extreme_high_returns_buy_high_confidence(self):
        """score=1 → strength≈1, signal=buy, confidence≈1"""
        signal, strength, confidence = stock_analysis.market_signal_from_score(1.0)
        assert strength > 0.95, f"score=1 應 strength>0.95, got {strength}"
        assert signal == "buy", f"score=1 應 signal=buy, got {signal}"
        assert confidence > 0.90, f"score=1 應 confidence>0.90, got {confidence}"


# ============ 向後兼容：修正 v5.11.3 hard cut ============

class TestP36BackwardCompat:
    def test_score_059_buy_not_neutral(self):
        """score=0.59 在 v5.11.3 是 neutral（<0.6），v5.13 應是 buy（strength>0.6 修正 hard cut）"""
        signal, strength, confidence = stock_analysis.market_signal_from_score(0.59)
        assert strength > 0.6, \
            f"v5.13 P36 修正：score=0.59 應 strength>0.6（v5.11.3 hard cut=neutral 過於保守），got {strength}"
        assert signal == "buy", \
            f"v5.13 P36 修正：score=0.59 應 buy，got {signal}"

    def test_score_041_sell_not_neutral(self):
        """score=0.41 在 v5.11.3 是 neutral（>0.4），v5.13 應是 sell（strength<0.4 修正 hard cut）"""
        signal, strength, confidence = stock_analysis.market_signal_from_score(0.41)
        assert strength < 0.4, \
            f"v5.13 P36 修正：score=0.41 應 strength<0.4（v5.11.3 hard cut=neutral 過於保守），got {strength}"
        assert signal == "sell", \
            f"v5.13 P36 修正：score=0.41 應 sell，got {signal}"


# ============ 平滑性測試（連續函數核心性質） ============

class TestP36Smoothness:
    def test_small_score_change_small_strength_change(self):
        """score 變化 0.01 → strength 變化 < 0.05（連續函數平滑性）"""
        s1, strength1, _ = stock_analysis.market_signal_from_score(0.55)
        s2, strength2, _ = stock_analysis.market_signal_from_score(0.56)
        delta = abs(strength2 - strength1)
        assert delta < 0.05, \
            f"score 變化 0.01 應 strength 變化 < 0.05（sigmoid 平滑），got delta={delta:.4f}"

    def test_symmetric_around_midpoint(self):
        """score 距 midpoint 等距 → strength 距 0.5 等距（sigmoid 對稱性）"""
        _, s_low, _ = stock_analysis.market_signal_from_score(0.4)
        _, s_high, _ = stock_analysis.market_signal_from_score(0.6)
        assert abs(s_low - 0.5) == pytest.approx(abs(s_high - 0.5), abs=1e-6), \
            f"對稱性：score=0.4 vs 0.6 距 0.5 等距，strength={s_low:.4f} vs {s_high:.4f}"


# ============ 邊界信號測試（確保離散標籤連續） ============

class TestP36SignalContinuity:
    def test_score_039_sell(self):
        """score=0.39 → sell（v5.11.3 同樣 sell，確保無 regression）"""
        signal, _, _ = stock_analysis.market_signal_from_score(0.39)
        assert signal == "sell", f"score=0.39 應 sell，got {signal}"

    def test_score_061_buy(self):
        """score=0.61 → buy（v5.11.3 同樣 buy，確保無 regression）"""
        signal, _, _ = stock_analysis.market_signal_from_score(0.61)
        assert signal == "buy", f"score=0.61 應 buy，got {signal}"

    def test_score_050_neutral(self):
        """score=0.50 → neutral（中點）"""
        signal, _, _ = stock_analysis.market_signal_from_score(0.50)
        assert signal == "neutral", f"score=0.50 應 neutral，got {signal}"
