"""v5.25 P1 — Backtest Cross-Market 真實 fundamental 注入整合測試。

Purpose:
    Permanent regression guard for v5.25 P1: 把 cross-market E2E 真實 11 ticker
    fundamental 注入 backtest,驗證 (1) per-ticker 4D multifactor 用真實 PE/ROE/PEG
    而非共用 mock,(2) cap-zone 警告整合(Lesson #49),(3) v5.10 vs v5.11.3 量化對比
    在真實 fundamental 下仍維持改善。

Lesson 對齊:
    - Lesson #52 (量化決策): v5.25 (b) backtest mock fundamental bias 修正路徑
    - Lesson #49 (cap-zone warning API): 3690.HK PEG=28.72 自動觸發
    - Lesson #51 (API → E2E 整合): fixture 真實注入而非共用 mock

Run:
    pytest scripts/tests/test_v525_backtest_cross_market.py -v
"""

import os
import sys

# 確保 scripts/ + repo root 在 path 中 (P0 fix 對齊 codebase 風格)
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _SCRIPTS_DIR)


class TestV525BacktestCrossMarket:
    """v5.25 P1: 11 ticker 真實 fundamental 注入 backtest。"""

    def test_run_cross_market_comparison_exists(self):
        """P1 API 暴露: run_cross_market_comparison() 對齊 run_comparison()。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        assert callable(run_cross_market_comparison)

    def test_run_cross_market_comparison_returns_11_tickers(self):
        """P1 範圍: 11 ticker backtest 結果(對齊 TICKER_UNIVERSE)。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        result = run_cross_market_comparison()

        # 必須包含 v5.10 + v5.11.3 + per-ticker metrics
        assert "v5.10" in result
        assert "v5.11.3" in result
        assert "per_ticker" in result

        per_ticker = result["per_ticker"]
        assert len(per_ticker) == 11, f"期望 11 ticker,實際 {len(per_ticker)}"

    def test_per_ticker_uses_real_fundamentals_not_mock(self):
        """P1 真實 fundamental 注入: per-ticker 結果反映真實 PE/ROE/PEG 差異。

        3690.HK PEG=28.72 應讓其 fund_score 明顯低於其他 ticker
        (PEG>25 cap-zone 觸發),而非共用 mock peg=1.2 全部 ticker fund_score 相同。
        """
        from backtest_v511_multifactor import run_cross_market_comparison
        result = run_cross_market_comparison()

        per_ticker = result["per_ticker"]
        fund_scores_3690 = per_ticker["3690.HK"]["fund"]
        fund_scores_aapl = per_ticker["AAPL"]["fund"]

        # 3690.HK PEG=28.72 撞 cap-zone → fund score 應 lower than AAPL PEG=2.29
        assert fund_scores_3690 < fund_scores_aapl, (
            f"3690.HK fund_score ({fund_scores_3690}) 應 < AAPL ({fund_scores_aapl}) "
            f"因 PEG=28.72 撞 cap-zone,AAPL PEG=2.29 健康。"
        )

    def test_cap_zone_warnings_emitted(self):
        """P1 + Lesson #49 整合: cap-zone warning 自動 emit (對齊 cross_market E2E)。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        result = run_cross_market_comparison()

        # cap_warnings 必含 3690.HK PEG collision
        warnings = result.get("cap_warnings", [])
        peg_warnings = [w for w in warnings if w.get("metric") == "fund.peg"]
        assert len(peg_warnings) >= 1, f"預期至少 1 個 fund.peg warning,實際 {len(peg_warnings)}"

        peg_warning = peg_warnings[0]
        assert "3690.HK" in peg_warning["tickers"]
        assert peg_warning["threshold_value"] == 25.0
        assert peg_warning["is_by_design"] is True

    def test_v5113_still_better_than_v510_under_real_fundamentals(self):
        """P1 真實 fundamental 下,v5.11.3 仍應改善 over v5.10。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        result = run_cross_market_comparison()

        v510_overall = result["v5.10"]["overall_accuracy"]
        v5113_overall = result["v5.11.3"]["overall_accuracy"]

        # v5.11.3 應 ≥ v5.10 (per v5.22 sweep 結論 + 真實 fund 不應 reverse)
        assert v5113_overall >= v510_overall, (
            f"v5.11.3 ({v5113_overall:.4f}) 應 ≥ v5.10 ({v510_overall:.4f}) "
            f"即使在真實 fundamental 下"
        )