"""v5.11.3 Cross-Market Real YFinance E2E — pytest 永久化。

設計：
    - 從 fixtures/tickers_fundamentals.json 載真實 yfinance 拉過的資料
    - 跑 v5.10 (commit 0f30069) vs v5.11.3 (HEAD) fund_score_multifactor
    - 驗證 6 條不變式：3 ticker × 2 版本 = 6 個 score，0 ≤ score ≤ 1
    - 驗證 std 量化結論（v5.11 ≤ v5.10，cap 飽和幻覺消失）
    - 無網路依賴（pytest mode 用 fixtures）

成功標準（Rule 4）：
    1. 6/6 scores 算出
    2. 所有 score ∈ [0, 1]
    3. v5.10 std ≥ v5.11.3 std（cap 假分散消失）
    4. 3 ticker 都有 v5.10 與 v5.11.3 score
    5. fixtures 存在（持久化 audit chain）
    6. 結論 interpretation 包含關鍵字
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from pathlib import Path

import pytest

# 確保 scripts/ 在 path 中
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from cross_market_real_yfinance_e2e import (  # noqa: E402
    quantize_cross_market,
    score_tickers,
)

V510_PATH = Path("/tmp/v510_stock_analysis.py")
V511_PATH = SCRIPTS_DIR / "stock_analysis.py"
FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "tickers_fundamentals.json"


def _load_module(label: str, path: Path):
    spec = importlib.util.spec_from_file_location(label, str(path))
    if spec is None or spec.loader is None:
        pytest.skip(f"無法載入 {label}（{path}）")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fixtures() -> dict:
    if not FIXTURES_PATH.exists():
        pytest.skip(
            f"Fixtures {FIXTURES_PATH} 不存在。"
            "請先跑：python scripts/cross_market_real_yfinance_e2e.py"
        )
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def v510_mod():
    if not V510_PATH.exists():
        pytest.skip(f"v510 baseline {V510_PATH} 不存在")
    return _load_module("v510_stock_analysis", V510_PATH)


@pytest.fixture(scope="module")
def v511_mod():
    return _load_module("v511_stock_analysis", V511_PATH)


class TestCrossMarketRealYFinanceE2E:
    """17 條 pytest 永久化跨市場 E2E 量化。"""

    def test_01_fixtures_exist(self):
        """Fixtures 必須存在（持久化 audit chain）。"""
        assert FIXTURES_PATH.exists(), f"Fixtures {FIXTURES_PATH} 不存在"

    def test_02_fixtures_has_at_least_3_tickers(self, fixtures):
        """Fixtures 至少有 3 tickers（v5.15 P46 已擴展到 11，舊測試 3 改為 ≥ 3）。"""
        assert len(fixtures["tickers"]) >= 3

    def test_03_fixtures_has_fundamentals(self, fixtures):
        """每 ticker 都有 pe/roe/peg/growth 4 個欄位。"""
        for t in fixtures["tickers"]:
            f = fixtures["fundamentals"][t]
            assert "pe" in f
            assert "roe" in f
            assert "peg" in f
            assert "growth" in f

    def test_04_v510_scores_computed(self, v510_mod, fixtures):
        """v5.10 ≥ 3 ticker 都算出 score（v5.15 P46 擴展後 ≥ 11）。"""
        scores = score_tickers(v510_mod.fund_score_multifactor, fixtures["fundamentals"])
        assert len(scores) >= 3
        for s in scores.values():
            assert 0.0 <= s <= 1.0, f"v5.10 score {s} 超出 [0,1]"

    def test_05_v5113_scores_computed(self, v511_mod, fixtures):
        """v5.11.3 ≥ 3 ticker 都算出 score（v5.15 P46 擴展後 ≥ 11）。"""
        scores = score_tickers(v511_mod.fund_score_multifactor, fixtures["fundamentals"])
        assert len(scores) >= 3
        for s in scores.values():
            assert 0.0 <= s <= 1.0, f"v5.11.3 score {s} 超出 [0,1]"

    def test_06_std_v510_ge_v5113(self, fixtures):
        """v5.10 std ≥ v5.11.3 std（cap 假分散消失）。"""
        quant = fixtures["std_quant"]
        assert quant["v5_10_std"] >= quant["v5_11_3_std"], (
            f"v5.10 std {quant['v5_10_std']} < v5.11.3 std {quant['v5_11_3_std']} "
            "— 預期 v5.11 線性化去除 cap 假分散"
        )

    def test_07_quantize_function_idempotent(self, fixtures):
        """quantize_cross_market 純函數 — 重跑結果一致。"""
        v510 = fixtures["v5_10_scores"]
        v511 = fixtures["v5_11_3_scores"]
        quant1 = quantize_cross_market(v510, v511)
        quant2 = quantize_cross_market(v510, v511)
        assert quant1 == quant2

    def test_08_all_6_scores_in_unit_interval(self, fixtures):
        """6 個 score 全部 ∈ [0, 1]。"""
        for t, s in fixtures["v5_10_scores"].items():
            assert 0.0 <= s <= 1.0, f"v5.10 {t}={s} 超出 [0,1]"
        for t, s in fixtures["v5_11_3_scores"].items():
            assert 0.0 <= s <= 1.0, f"v5.11.3 {t}={s} 超出 [0,1]"

    def test_09_interpretation_keyword_present(self, fixtures):
        """Interpretation 含「cap 飽和幻覺消失」關鍵字。"""
        interp = fixtures["std_quant"]["interpretation"]
        assert "cap 飽和幻覺消失" in interp

    def test_10_v510_has_at_least_3_distinct_tickers(self, fixtures):
        """v5.10 ≥ 3 ticker 全有 score（v5.15 P46 擴展後 11）。"""
        assert len(fixtures["v5_10_scores"]) >= 3

    def test_11_v5113_has_at_least_3_distinct_tickers(self, fixtures):
        """v5.11.3 ≥ 3 ticker 全有 score（v5.15 P46 擴展後 11）。"""
        assert len(fixtures["v5_11_3_scores"]) >= 3

    def test_12_fixtures_meta_source(self, fixtures):
        """Fixtures meta 含 yfinance source 標記。"""
        meta = fixtures.get("_meta", {})
        assert "yfinance" in meta.get("source", "")

    def test_13_fixtures_meta_v510_baseline(self, fixtures):
        """Fixtures meta 標記 v5.10 baseline commit。"""
        meta = fixtures.get("_meta", {})
        assert "0f30069" in meta.get("v510_baseline", "")

    def test_14_fixtures_meta_v5113_source(self, fixtures):
        """Fixtures meta 標記 v5.11.3 source。"""
        meta = fixtures.get("_meta", {})
        assert "stock_analysis.py" in meta.get("v5113_source", "")

    def test_15_std_delta_stored(self, fixtures):
        """std_delta 存到 fixtures 供 audit chain 取證。"""
        quant = fixtures["std_quant"]
        assert "std_delta" in quant
        assert isinstance(quant["std_delta"], (int, float))

    def test_16_v510_v5113_scores_match_fixtures(self, v510_mod, v511_mod, fixtures):
        """現算 v5.10 / v5.11.3 scores 與 fixtures 一致（若 fixtures 是同次真實拉取）。"""
        v510_re = score_tickers(v510_mod.fund_score_multifactor, fixtures["fundamentals"])
        v511_re = score_tickers(v511_mod.fund_score_multifactor, fixtures["fundamentals"])
        for t in fixtures["tickers"]:
            assert abs(v510_re[t] - fixtures["v5_10_scores"][t]) < 1e-6, (
                f"v5.10 {t}: 現算 {v510_re[t]} vs fixtures {fixtures['v5_10_scores'][t]}"
            )
            assert abs(v511_re[t] - fixtures["v5_11_3_scores"][t]) < 1e-6, (
                f"v5.11.3 {t}: 現算 {v511_re[t]} vs fixtures {fixtures['v5_11_3_scores'][t]}"
            )

    def test_17_recompute_std_matches_fixtures(self, fixtures):
        """現算 std 與 fixtures 一致（純函數驗證）。"""
        v510_scores = fixtures["v5_10_scores"]
        v511_scores = fixtures["v5_11_3_scores"]
        recomputed = quantize_cross_market(v510_scores, v511_scores)
        assert abs(recomputed["v5_10_std"] - fixtures["std_quant"]["v5_10_std"]) < 1e-4
        assert abs(recomputed["v5_11_3_std"] - fixtures["std_quant"]["v5_11_3_std"]) < 1e-4
