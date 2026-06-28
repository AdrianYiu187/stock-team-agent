"""v5.14 P40: risk_score_multifactor var_95 + max_dd 正值 cap 線性化 pytest.

目的：守住 risk var_95>=0 + max_dd>=0 兩個正值 cap 線性化。

舊版行為（v5.13）：
- var_95 >= 0:  0.7  (cap: 無下行風險 → 微加分)
- var_95 [-5, 0]: 線性 0.2..0.7
- var_95 < -5:   0.15 (cap)

- max_dd >= 0:  0.7  (cap: 無回撤 → 微加分)
- max_dd [-50, 0]: 線性 0.15..0.7
- max_dd < -50: 0.1  (cap)

新版行為（v5.14 P40）：
- var_95 >= 0: 線性 0.7 → 0.85 (var=0..+5，無風險 → 強 buy)
- max_dd >= 0: 線性 0.7 → 0.85 (dd=0..+5，無回撤 → 強 buy)

歷史：
- 2026-06-28 created (v5.14 P40)
"""
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import risk_score_multifactor


def risk_score(var_95=None, max_dd=None, sharpe=None, volatility=None):
    """Risk score with one parameter varying."""
    defaults = {"volatility": 30, "var_95": -0.025, "max_dd": -0.15, "sharpe": 1.0}
    if var_95 is not None: defaults["var_95"] = var_95
    if max_dd is not None: defaults["max_dd"] = max_dd
    if sharpe is not None: defaults["sharpe"] = sharpe
    if volatility is not None: defaults["volatility"] = volatility
    return risk_score_multifactor(**defaults)


class TestP40RiskVar95Linear:
    """var_95 [0, +0.1] 必須連續線性，不能 cap 0.7。"""

    def test_var_zero_continuous(self):
        """var=0 → 應與 var=-0.001 連續（不跳變）。"""
        s0 = risk_score(var_95=0)
        s_neg = risk_score(var_95=-0.001)
        # 設計 var>=0 連續線性
        assert abs(s0 - s_neg) < 0.01, f"var=0 ({s0}) should be ~continuous with var=-0.001 ({s_neg})"

    def test_var_positive_higher_than_zero(self):
        """var=+0.05 必須 > var=0 (更樂觀 = 無風險)。"""
        s0 = risk_score(var_95=0)
        s_pos = risk_score(var_95=0.05)
        assert s_pos > s0, f"var=+0.05 ({s_pos}) should be > var=0 ({s0})"

    def test_var_extreme_plus_10(self):
        """var=+10 (異常正向) 必須 clip 至合理上限。"""
        s = risk_score(var_95=10)
        assert 0.0 <= s <= 1.0


class TestP40RiskMaxDdLinear:
    """max_dd [0, +0.5] 必須連續線性，不能 cap 0.7。"""

    def test_dd_zero_continuous(self):
        """dd=0 → 應與 dd=-0.001 連續。"""
        s0 = risk_score(max_dd=0)
        s_neg = risk_score(max_dd=-0.001)
        assert abs(s0 - s_neg) < 0.01, f"dd=0 ({s0}) should be ~continuous with dd=-0.001 ({s_neg})"

    def test_dd_positive_higher_than_zero(self):
        """dd=+0.2 必須 > dd=0 (更樂觀 = 無回撤)。"""
        s0 = risk_score(max_dd=0)
        s_pos = risk_score(max_dd=0.2)
        assert s_pos > s0, f"dd=+0.2 ({s_pos}) should be > dd=0 ({s0})"

    def test_dd_extreme_plus_10(self):
        """dd=+10 (異常正向) 必須 clip。"""
        s = risk_score(max_dd=10)
        assert 0.0 <= s <= 1.0


class TestP40RiskShaprPreserved:
    """sharpe cap at 5 preserved (v5.11 N11 fix)."""

    def test_sharpe_minus_2_to_plus_5_monotonic(self):
        """sharpe [-2, +5] 線性單調遞增（v5.11 N11）。"""
        scores = [risk_score(sharpe=s) for s in [-2, -1, 0, 1, 2, 3, 4, 5]]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i-1], f"sharpe monotonic: index {i}"

    def test_sharpe_cap_at_5(self):
        """sharpe=10 (異常高) 必須 cap 0.95。"""
        s5 = risk_score(sharpe=5)
        s10 = risk_score(sharpe=10)
        # 設計：sharpe > 5 cap 0.95
        assert abs(s10 - s5) < 0.01, f"sharpe>5 should cap: s5={s5}, s10={s10}"
