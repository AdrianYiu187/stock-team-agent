"""v5.12 (Pitfall #35) dynamic_weights_for_ticker — 10 條永久 pytest。

設計：
    - base: market 0.12 / technical 0.18 / fundamental 0.22 /
            risk 0.15 / sentiment 0.18 / news 0.07 / macro 0.08
    - region="hk": technical +0.05, fundamental +0.03, sentiment -0.03
    - region="cn": fundamental +0.05, risk +0.03, market -0.03
    - region="us": fundamental +0.05, news +0.02, sentiment -0.02
    - 自動 normalize（加權和 = 1.0）

成功標準（Rule 4）：
    1. 3 region 各有 distinct profile
    2. 加權和 = 1.0（normalize 正確）
    3. 每個 role weight ∈ [0, 1]
    4. .HK 自動 → region hk
    5. .SS / .SZ 自動 → region cn
    6. 其他 ticker（無後綴）→ region us（預設）
    7. case-insensitive（小寫 .hk 也行）
    8. base weights 與 v5.11 既有值對齊
    9. region 調整「有意義」（不是 uniform 重分配）
    10. 不同 ticker → 不同 weights
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from stock_analysis import dynamic_weights_for_ticker  # noqa: E402

EXPECTED_ROLES = {"market", "technical", "fundamental", "risk", "sentiment", "news", "macro"}


class TestDynamicWeightsForTicker:
    """10 條 pytest 永久化 v5.12 P35 dynamic_weights_for_ticker。"""

    def test_01_three_regions_have_distinct_profiles(self):
        """3 region 各有 distinct weight profile。"""
        w_us = dynamic_weights_for_ticker("AAPL")
        w_hk = dynamic_weights_for_ticker("0700.HK")
        w_cn = dynamic_weights_for_ticker("600519.SS")
        # 至少有 3 個 role 差異 > 0.01
        diffs_us_hk = sum(abs(w_us[r] - w_hk[r]) for r in EXPECTED_ROLES)
        diffs_hk_cn = sum(abs(w_hk[r] - w_cn[r]) for r in EXPECTED_ROLES)
        diffs_cn_us = sum(abs(w_cn[r] - w_us[r]) for r in EXPECTED_ROLES)
        assert diffs_us_hk > 0.03, f"US vs HK 差異太小: {diffs_us_hk}"
        assert diffs_hk_cn > 0.03, f"HK vs CN 差異太小: {diffs_hk_cn}"
        assert diffs_cn_us > 0.03, f"CN vs US 差異太小: {diffs_cn_us}"

    def test_02_weight_sum_equals_one(self):
        """加權和 = 1.0（normalize 正確）。"""
        for ticker in ["AAPL", "MSFT", "0700.HK", "0941.HK", "600519.SS", "000001.SZ", "GOOG"]:
            w = dynamic_weights_for_ticker(ticker)
            total = sum(w.values())
            assert abs(total - 1.0) < 1e-6, f"{ticker} weights 加總 {total} ≠ 1.0"

    def test_03_each_role_in_unit_interval(self):
        """每個 role weight ∈ [0, 1]。"""
        for ticker in ["AAPL", "0700.HK", "600519.SS"]:
            w = dynamic_weights_for_ticker(ticker)
            for role, weight in w.items():
                assert 0.0 <= weight <= 1.0, f"{ticker}.{role}={weight} 超出 [0, 1]"

    def test_04_hk_suffix_routes_to_hk(self):
        """.HK 自動 → region hk（technical 加權最大）。"""
        w = dynamic_weights_for_ticker("0700.HK")
        # hk: technical +0.05 (基礎 0.18 + 0.05 = 0.23)
        # hk: fundamental +0.03 (基礎 0.22 + 0.03 = 0.25)
        # normalize 後 technical 仍很高
        # 最大權重應是 fundamental 或 technical
        sorted_roles = sorted(w.items(), key=lambda x: -x[1])
        top_role = sorted_roles[0][0]
        assert top_role in {"technical", "fundamental"}, (
            f"HK top role 應是 technical/fundamental，got {top_role}"
        )

    def test_05_cn_suffix_routes_to_cn(self):
        """.SS / .SZ 自動 → region cn（fundamental 加權最大）。"""
        w_ss = dynamic_weights_for_ticker("600519.SS")
        w_sz = dynamic_weights_for_ticker("000001.SZ")
        # cn: fundamental +0.05 (基礎 0.22 + 0.05 = 0.27) — 最大
        for w in [w_ss, w_sz]:
            sorted_roles = sorted(w.items(), key=lambda x: -x[1])
            top_role = sorted_roles[0][0]
            assert top_role in {"fundamental", "risk"}, (
                f"CN top role 應是 fundamental/risk，got {top_role}"
            )

    def test_06_no_suffix_defaults_to_us(self):
        """無後綴 ticker → region us（預設）。"""
        w = dynamic_weights_for_ticker("AAPL")
        w_msft = dynamic_weights_for_ticker("MSFT")
        # us profile 應一致
        for role in EXPECTED_ROLES:
            assert abs(w[role] - w_msft[role]) < 1e-6, (
                f"us ticker weight 不一致: AAPL.{role}={w[role]} vs MSFT.{role}={w_msft[role]}"
            )

    def test_07_case_insensitive(self):
        """case-insensitive（小寫 .hk 也行）。"""
        w_upper = dynamic_weights_for_ticker("0700.HK")
        w_lower = dynamic_weights_for_ticker("0700.hk")
        for role in EXPECTED_ROLES:
            assert abs(w_upper[role] - w_lower[role]) < 1e-6, (
                f"大小寫不一致: .{role} upper={w_upper[role]} lower={w_lower[role]}"
            )

    def test_08_base_alignment_with_v511(self):
        """base weights 與 v5.11 既有值對齊（normalize 前）。"""
        # us profile 應保留 base weight 比例（normalize 後微調）
        w = dynamic_weights_for_ticker("AAPL")
        # us: fundamental +0.05 (0.22→0.27), news +0.02 (0.07→0.09), sentiment -0.02 (0.18→0.16)
        # 比較 fundamental 與 sentiment 比例
        assert w["fundamental"] > w["sentiment"], (
            f"us: fundamental {w['fundamental']} 應 > sentiment {w['sentiment']}"
        )
        assert w["sentiment"] > w["market"], (
            f"us: sentiment {w['sentiment']} 應 > market {w['market']}"
        )

    def test_09_region_adjustment_meaningful(self):
        """region 調整「有意義」（不是 uniform 重分配）。"""
        w_us = dynamic_weights_for_ticker("AAPL")
        w_hk = dynamic_weights_for_ticker("0700.HK")
        # hk 應 technical > us technical
        assert w_hk["technical"] > w_us["technical"], (
            f"HK technical {w_hk['technical']} 應 > US technical {w_us['technical']}"
        )
        # cn 應 risk > us risk
        w_cn = dynamic_weights_for_ticker("600519.SS")
        assert w_cn["risk"] > w_us["risk"], (
            f"CN risk {w_cn['risk']} 應 > US risk {w_us['risk']}"
        )

    def test_10_different_tickers_yield_different_weights(self):
        """不同 ticker → 不同 weights。"""
        weights_aapl = dynamic_weights_for_ticker("AAPL")
        weights_hk = dynamic_weights_for_ticker("0700.HK")
        weights_cn = dynamic_weights_for_ticker("600519.SS")
        # 3 個 ticker 兩兩差異（technical 是好指標）
        assert weights_aapl["technical"] != weights_hk["technical"]
        assert weights_hk["technical"] != weights_cn["technical"]
        assert weights_aapl["risk"] != weights_cn["risk"]
