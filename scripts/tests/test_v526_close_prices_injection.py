"""v5.26 P1 — close_prices 注入 TDD red light。

Purpose:
    Permanent regression guard for v5.26 P1: 把 11 ticker 真實 close prices
    注入 backtest_v511_multifactor.run_cross_market_comparison(),
    驗證 (1) close_prices fixture 完整 (2) close_source 注入路徑正確
    (3) mock 模式向後相容 (4) 真實模式下 per-ticker 結果反映真實 vol 差異。

Lesson 對齊:
    - Lesson #53 (mock ≠ 真實): close prices 延伸
    - Lesson #54 候選 (mock GBM 適用範圍): 真實 close prices 量化驗證

Run:
    pytest scripts/tests/test_v526_close_prices_injection.py -v
"""

import json
import os
import sys
from pathlib import Path

# 確保 scripts/ 在 path 中
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _SCRIPTS_DIR)

FIXTURES_PATH = Path(_SCRIPTS_DIR) / "tests" / "fixtures" / "tickers_fundamentals.json"


class TestV526ClosePricesFixture:
    """v5.26 P1: fixture 包含 close_prices key, 11 ticker 各 120 day。"""

    def test_fixture_has_close_prices_key(self):
        """P1 fixture 完整性: tests/fixtures/tickers_fundamentals.json 必須含 close_prices key。"""
        assert FIXTURES_PATH.exists(), f"fixture 缺失: {FIXTURES_PATH}"
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        assert "close_prices" in data, (
            "fixture 必須含 close_prices key (v5.26 P1 close prices 注入需求)"
        )

    def test_close_prices_covers_all_11_tickers(self):
        """P1 fixture 範圍: 11 ticker 全部要有 close_prices entry。"""
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        close_prices = data.get("close_prices", {})
        fundamentals = data.get("fundamentals", {})
        assert set(close_prices.keys()) == set(fundamentals.keys()), (
            f"close_prices tickers {set(close_prices.keys())} "
            f"vs fundamentals tickers {set(fundamentals.keys())} 不一致"
        )
        assert len(close_prices) == 11, f"期望 11 ticker close_prices, 實際 {len(close_prices)}"

    def test_close_prices_array_length_120(self):
        """P1 fixture 長度: 每 ticker close prices 陣列 = 120 days (與 mock 一致)。"""
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        for ticker, prices in data.get("close_prices", {}).items():
            assert len(prices) == 120, (
                f"{ticker} close_prices 長度 {len(prices)} ≠ 120"
            )

    def test_close_prices_all_positive(self):
        """P1 fixture sanity: 所有 price > 0 (避免 log/division by zero)。"""
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        for ticker, prices in data.get("close_prices", {}).items():
            for i, p in enumerate(prices):
                assert p > 0, f"{ticker}[{i}]={p} ≤ 0"


class TestV526CloseSourceParameter:
    """v5.26 P1: run_cross_market_comparison() 必須支援 close_source 參數。"""

    def test_run_cross_market_comparison_accepts_close_source(self):
        """P1 API: run_cross_market_comparison() 必須接受 close_source 參數 (default='mock')。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        import inspect
        sig = inspect.signature(run_cross_market_comparison)
        assert "close_source" in sig.parameters, (
            f"run_cross_market_comparison() 必須含 close_source 參數, "
            f"實際參數: {list(sig.parameters.keys())}"
        )
        # 預設 'mock' 向後相容
        assert sig.parameters["close_source"].default == "mock", (
            "close_source 預設值必須為 'mock' (v5.25 向後相容)"
        )

    def test_run_cross_market_comparison_mock_mode_backward_compatible(self):
        """P1 向後相容: close_source='mock' (default) 必須對齊 v5.25 行為。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        result_mock = run_cross_market_comparison(close_source="mock")
        assert "v5.10" in result_mock
        assert "v5.11.3" in result_mock
        assert "per_ticker" in result_mock
        assert len(result_mock["per_ticker"]) == 11

    def test_run_cross_market_comparison_real_mode_uses_fixture(self):
        """P1 真實注入: close_source='real' 必須從 fixture 拿 close_prices (per-ticker 不同)。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        result_real = run_cross_market_comparison(close_source="real")
        assert "v5.10" in result_real
        assert "v5.11.3" in result_real
        assert "per_ticker" in result_real
        # 真實模式下 per-ticker 結果必須有完整 11 ticker (與 mock 同)
        assert len(result_real["per_ticker"]) == 11


class TestV526MockVsRealDiff:
    """v5.26 P1: 真實 vs mock 結果差異量化 (Lesson #54 候選驗證)。"""

    def test_real_vs_mock_results_differ(self):
        """P1 量化發現: 真實 vs mock per-ticker result 必須有實質差異 (mock ≠ 真實)。"""
        from backtest_v511_multifactor import run_cross_market_comparison
        result_mock = run_cross_market_comparison(close_source="mock")
        result_real = run_cross_market_comparison(close_source="real")

        # Per-ticker v5.11.3 directional_accuracy 差異必須 > 0 (mock ≠ 真實)
        diffs = []
        for ticker in result_mock["per_ticker"]:
            mock_d = result_mock["per_ticker"][ticker].get("composite", 0.0)
            real_d = result_real["per_ticker"][ticker].get("composite", 0.0)
            diffs.append(abs(mock_d - real_d))

        # 至少 1 個 ticker 差異 > 0.001 (真實 ≠ mock)
        max_diff = max(diffs) if diffs else 0.0
        assert max_diff > 0.001, (
            f"mock vs real per-ticker 結果完全相同 (max_diff={max_diff:.6f}), "
            f"Lesson #53 驗證失敗: mock GBM 應該被真實 close prices 改變"
        )