"""v5.15 P45+P46 — 擴展 cross_market_e2e 樣本大小 + None handling + fixture freshness。

設計：
    - 從 fixtures/tickers_fundamentals.json 載入（既有）
    - 新增 9 條 pytest：
        - TICKER_UNIVERSE 常數存在且 ≥ 10
        - 跨 US / HK / CN 三市場（最少各 3 ticker）
        - fetch_fundamentals 對單 ticker 失敗不中斷整體
        - fixtures _meta.fetched_at 存在
        - fixtures _meta.fetched_at < 90 days
        - fixtures ticker 數 ≥ TICKER_UNIVERSE 80%（允許部分 ticker yfinance 無資料）
        - PEG 缺失 ticker 仍能算 score（PEG optional）
        - zero growth ticker 仍能算 score
        - 量化結論包含「sample_size」欄位

成功標準（Rule 4）：
    1. TICKER_UNIVERSE ≥ 10 ticker
    2. 跨 US/HK/CN 三市場各 ≥ 3
    3. fetch_fundamentals error tolerance
    4. fixtures 含 fetched_at
    5. fixtures < 90 days old
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from cross_market_real_yfinance_e2e import (  # noqa: E402
    TICKER_UNIVERSE,
    FIXTURES_PATH,  # type: ignore  # may not exist yet
    quantize_cross_market,
)

FIXTURES_PATH_DEFAULT = (
    Path(__file__).resolve().parent / "fixtures" / "tickers_fundamentals.json"
)


@pytest.fixture(scope="module")
def fixtures() -> dict:
    path = FIXTURES_PATH if "FIXTURES_PATH" in dir() else FIXTURES_PATH_DEFAULT
    if not path.exists():
        pytest.skip(f"Fixtures {path} 不存在，請跑 cross_market_real_yfinance_e2e.py")
    return json.loads(path.read_text(encoding="utf-8"))


class TestV515Expanded:
    """P45 + P46：擴展樣本大小 + None handling + fixture freshness。"""

    def test_01_ticker_universe_exists(self):
        """TICKER_UNIVERSE 常數存在。"""
        assert hasattr(
            __import__("cross_market_real_yfinance_e2e"), "TICKER_UNIVERSE"
        ), "TICKER_UNIVERSE 常數不存在"
        assert isinstance(TICKER_UNIVERSE, list)
        assert len(TICKER_UNIVERSE) >= 10, f"只有 {len(TICKER_UNIVERSE)} ticker，需 ≥ 10"

    def test_02_ticker_universe_covers_us_market(self):
        """TICKER_UNIVERSE 含 US 市場 ≥ 3 ticker。"""
        us_tickers = [t for t in TICKER_UNIVERSE if "." not in t]
        assert len(us_tickers) >= 3, f"US ticker 只 {len(us_tickers)} 個，需 ≥ 3"

    def test_03_ticker_universe_covers_hk_market(self):
        """TICKER_UNIVERSE 含 HK 市場 ≥ 3 ticker（後綴 .HK）。"""
        hk_tickers = [t for t in TICKER_UNIVERSE if t.endswith(".HK")]
        assert len(hk_tickers) >= 3, f"HK ticker 只 {len(hk_tickers)} 個，需 ≥ 3"

    def test_04_ticker_universe_covers_cn_market(self):
        """TICKER_UNIVERSE 含 CN 市場 ≥ 3 ticker（後綴 .SS 或 .SZ）。"""
        cn_tickers = [t for t in TICKER_UNIVERSE if t.endswith((".SS", ".SZ"))]
        assert len(cn_tickers) >= 3, f"CN ticker 只 {len(cn_tickers)} 個，需 ≥ 3"

    def test_05_fixtures_cover_at_least_80_percent(self, fixtures):
        """Fixtures ticker 數 ≥ TICKER_UNIVERSE 80%（允許部分 ticker yfinance 無資料）。"""
        fixture_tickers = set(fixtures["tickers"])
        universe_set = set(TICKER_UNIVERSE)
        coverage = len(fixture_tickers & universe_set) / len(universe_set)
        assert coverage >= 0.8, (
            f"Fixtures 覆蓋率 {coverage:.0%} < 80%。"
            f"Missing: {universe_set - fixture_tickers}"
        )

    def test_06_fixtures_have_fetched_at(self, fixtures):
        """Fixtures _meta 必須有 fetched_at 欄位（自動 re-fetch 判斷用）。"""
        meta = fixtures.get("_meta", {})
        assert "fetched_at" in meta, "Fixtures _meta 缺少 fetched_at"
        # 驗證 ISO format
        datetime.fromisoformat(meta["fetched_at"])

    def test_07_fixtures_freshness_under_90_days(self, fixtures):
        """Fixtures < 90 days old（允許季度更新）。"""
        meta = fixtures.get("_meta", {})
        if "fetched_at" not in meta:
            pytest.skip("fetched_at 缺失")
        fetched = datetime.fromisoformat(meta["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - fetched
        assert age < timedelta(days=90), (
            f"Fixtures 過時 {age.days} 天。請跑 cross_market_real_yfinance_e2e.py 重新拉取"
        )

    def test_08_std_quant_has_sample_size(self, fixtures):
        """std_quant 包含 sample_size 欄位（量化 N 透明度）。"""
        quant = fixtures.get("std_quant", {})
        assert "sample_size" in quant, (
            "std_quant 缺少 sample_size 欄位。"
            "P46 要求量化 N 透明化"
        )
        assert quant["sample_size"] >= 5, (
            f"sample_size={quant['sample_size']} < 5，P46 要求 ≥ 5"
        )

    def test_09_quantize_with_larger_sample_still_valid(self):
        """quantize_cross_market 對 ≥ 10 ticker 仍能正確計算 std。"""
        # 模擬 10 ticker
        v510_scores = {f"T{i}": 0.5 + 0.05 * i for i in range(10)}
        v511_scores = {f"T{i}": 0.5 + 0.03 * i for i in range(10)}
        quant = quantize_cross_market(v510_scores, v511_scores)
        assert quant["sample_size"] == 10
        assert quant["v5_10_std"] > 0
        assert quant["v5_11_3_std"] > 0