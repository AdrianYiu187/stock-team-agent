"""
v5.13 P36b — sentiment_signal 連續化測試

Pitfall 背景（v5.12 closure 量化結論）：
- v5.11.3 sentiment_signal L1162 hard threshold ±0.15
  sentiment_signal = "positive" if combined > 0.15 else "negative" if combined < -0.15 else "neutral"
- 雙極 hard cut：combined=0.14→neutral, 0.16→positive（破壞連續函數意義）
- 違背 v5.11/v5.12「連續線性、無 cap、無 hard cut」精神
- P36 已修 market_signal，這是 P36b 推廣

v5.13 P36b 修法：
- 新增 sentiment_signal_from_combined(combined_score, k=6.0)
  - 輸入雙極 [-1, 1]（不像 market/tech/fund/risk 是 [0, 1]）
  - strength = 0.5 + 0.5 * tanh(combined * k)，保留正負號
  - k=6 使 threshold=0.15 對應 strength≈0.60/0.40（接近 v5.11.3 行為）
  - 輸出 (signal, strength, confidence)
    signal ∈ {positive, negative, neutral}

驗證目標：
1. 函數存在 + 正確返回 tuple
2. 中點：combined=0 → strength=0.5, signal=neutral, confidence=0
3. 邊界正：combined=1 → strength>0.95, signal=positive
4. 邊界負：combined=-1 → strength<0.05, signal=negative
5. 向後兼容：combined=0.14（v5.11.3 neutral）→ positive（修正 hard cut）
6. 向後兼容：combined=-0.14 → negative（修正 hard cut）
7. 平滑：combined 變化 0.01 → strength 變化 < 0.05
8. 對稱性：combined 距 0 等距 → strength 距 0.5 等距
9. 雙極保留：combined=0.5 應 > 0.5 + 0.1；combined=-0.5 應 < 0.5 - 0.1
10. 邊界信號：combined=0.16 → positive（與 v5.11.3 一致無 regression）
"""
import math
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stock_analysis


# ============ 函數存在性檢查 ============

class TestP36bSentimentFunctionExists:
    def test_sentiment_signal_from_combined_exists(self):
        """sentiment_signal_from_combined 函數已定義"""
        assert hasattr(stock_analysis, "sentiment_signal_from_combined"), \
            "v5.13 P36b: sentiment_signal_from_combined 函數未定義"
        assert callable(stock_analysis.sentiment_signal_from_combined), \
            "v5.13 P36b: sentiment_signal_from_combined 不是可調用函數"

    def test_returns_tuple_of_three(self):
        """函數返回 (signal, strength, confidence) 三元組"""
        result = stock_analysis.sentiment_signal_from_combined(0.0)
        assert isinstance(result, tuple), "應返回 tuple"
        assert len(result) == 3, "應返回 3 個值"
        signal, strength, confidence = result
        assert signal in ("positive", "negative", "neutral"), \
            f"signal 應為 positive/negative/neutral，got {signal}"
        assert 0.0 <= strength <= 1.0, f"strength 應在 [0, 1]，got {strength}"
        assert 0.0 <= confidence <= 1.0, f"confidence 應在 [0, 1]，got {confidence}"


# ============ 中點 + 邊界測試 ============

class TestP36bSentimentBoundaries:
    def test_zero_returns_neutral_zero_confidence(self):
        """combined=0 → strength=0.5, signal=neutral, confidence=0"""
        signal, strength, confidence = stock_analysis.sentiment_signal_from_combined(0.0)
        assert abs(strength - 0.5) < 0.01, f"中點應 strength=0.5, got {strength}"
        assert signal == "neutral", f"中點應 signal=neutral, got {signal}"
        assert abs(confidence - 0.0) < 0.01, f"中點應 confidence=0, got {confidence}"

    def test_extreme_positive_returns_positive_high_confidence(self):
        """combined=1 → strength≈1, signal=positive, confidence≈1"""
        signal, strength, confidence = stock_analysis.sentiment_signal_from_combined(1.0)
        assert strength > 0.95, f"combined=1 應 strength>0.95, got {strength}"
        assert signal == "positive", f"combined=1 應 signal=positive, got {signal}"
        assert confidence > 0.90, f"combined=1 應 confidence>0.90, got {confidence}"

    def test_extreme_negative_returns_negative_high_confidence(self):
        """combined=-1 → strength≈0, signal=negative, confidence≈1"""
        signal, strength, confidence = stock_analysis.sentiment_signal_from_combined(-1.0)
        assert strength < 0.05, f"combined=-1 應 strength<0.05, got {strength}"
        assert signal == "negative", f"combined=-1 應 signal=negative, got {signal}"
        assert confidence > 0.90, f"combined=-1 應 confidence>0.90, got {confidence}"


# ============ 向後兼容：修正 v5.11.3 hard cut ============

class TestP36bSentimentBackwardCompat:
    def test_combined_014_positive_not_neutral(self):
        """combined=0.14 在 v5.11.3 是 neutral（<0.15），v5.13 應是 positive（修正 hard cut）"""
        signal, strength, confidence = stock_analysis.sentiment_signal_from_combined(0.14)
        assert strength > 0.5, \
            f"v5.13 P36b 修正：combined=0.14 應 strength>0.5（v5.11.3 hard cut=neutral），got {strength}"
        assert signal == "positive", \
            f"v5.13 P36b 修正：combined=0.14 應 positive，got {signal}"

    def test_combined_minus014_negative_not_neutral(self):
        """combined=-0.14 在 v5.11.3 是 neutral（>-0.15），v5.13 應是 negative（修正 hard cut）"""
        signal, strength, confidence = stock_analysis.sentiment_signal_from_combined(-0.14)
        assert strength < 0.5, \
            f"v5.13 P36b 修正：combined=-0.14 應 strength<0.5（v5.11.3 hard cut=neutral），got {strength}"
        assert signal == "negative", \
            f"v5.13 P36b 修正：combined=-0.14 應 negative，got {signal}"


# ============ 平滑 + 雙極對稱測試 ============

class TestP36bSentimentSmoothness:
    def test_small_combined_change_small_strength_change(self):
        """combined 變化 0.01 → strength 變化 < 0.05（連續函數平滑性）"""
        _, s1, _ = stock_analysis.sentiment_signal_from_combined(0.10)
        _, s2, _ = stock_analysis.sentiment_signal_from_combined(0.11)
        delta = abs(s2 - s1)
        assert delta < 0.05, \
            f"combined 變化 0.01 應 strength 變化 < 0.05（tanh 平滑），got delta={delta:.4f}"

    def test_symmetric_around_zero(self):
        """combined 距 0 等距 → strength 距 0.5 等距（雙極對稱）"""
        _, s_pos, _ = stock_analysis.sentiment_signal_from_combined(0.3)
        _, s_neg, _ = stock_analysis.sentiment_signal_from_combined(-0.3)
        assert abs(s_pos - 0.5) == pytest.approx(abs(s_neg - 0.5), abs=1e-6), \
            f"對稱性：±0.3 距 0 等距，strength={s_pos:.4f} vs {s_neg:.4f}"


# ============ 雙極保留（v5.12 P34 修復精神） ============

class TestP36bSentimentSignPreservation:
    def test_positive_combined_above_neutral(self):
        """combined=0.5 應 strength>0.6（保留正號 → positive）"""
        signal, strength, _ = stock_analysis.sentiment_signal_from_combined(0.5)
        assert strength > 0.6, f"combined=0.5 應 strength>0.6，got {strength}"
        assert signal == "positive", f"combined=0.5 應 positive，got {signal}"

    def test_negative_combined_below_neutral(self):
        """combined=-0.5 應 strength<0.4（保留負號 → negative）"""
        signal, strength, _ = stock_analysis.sentiment_signal_from_combined(-0.5)
        assert strength < 0.4, f"combined=-0.5 應 strength<0.4，got {strength}"
        assert signal == "negative", f"combined=-0.5 應 negative，got {signal}"


# ============ 邊界信號（無 regression 測試） ============

class TestP36bSentimentSignalContinuity:
    def test_combined_016_positive(self):
        """combined=0.16 → positive（v5.11.3 同樣 positive，確保無 regression）"""
        signal, _, _ = stock_analysis.sentiment_signal_from_combined(0.16)
        assert signal == "positive", f"combined=0.16 應 positive，got {signal}"

    def test_combined_minus016_negative(self):
        """combined=-0.16 → negative（v5.11.3 同樣 negative，確保無 regression）"""
        signal, _, _ = stock_analysis.sentiment_signal_from_combined(-0.16)
        assert signal == "negative", f"combined=-0.16 應 negative，got {signal}"

    def test_combined_050_neutral(self):
        """combined=0.0 → neutral（中點）"""
        signal, _, _ = stock_analysis.sentiment_signal_from_combined(0.0)
        assert signal == "neutral", f"combined=0.0 應 neutral，got {signal}"