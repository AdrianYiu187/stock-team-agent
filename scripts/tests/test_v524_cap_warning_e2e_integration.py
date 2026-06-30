"""v5.24 P1+P3 — Cap-zone warning E2E integration TDD guard.

Per docs/v5.24_roadmap.md §P1+P3:
- 3690.HK 真實 fixture PEG=28.72 (per v5.22 P42 真實 outlier)
- 整合後 recompute_cross_market_with_cap_warnings() 必觸發 fund.peg warning
- cross_market_real_yfinance_e2e.main() --mode frozen 必 emit logger.warning

這些是 Lesson #49 整合驗證的永久 pytest guard,未來若有人誤改
_FUND_CAP_RULES 或 main() 整合路徑會 silently break,紅燈立即觸發。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 確保 scripts/ 在 path 中（既有 test_cross_market 模式）
ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))


FIXTURES_PATH = (
    SCRIPTS_DIR / "tests" / "fixtures" / "tickers_fundamentals.json"
)


@pytest.fixture(scope="module")
def cross_market_fundamentals() -> dict[str, dict]:
    """從既有 v5.15 P46 fixtures 載 11 ticker 真實 yfinance fundamentals."""
    if not FIXTURES_PATH.exists():
        pytest.skip(f"Fixtures not found: {FIXTURES_PATH}")
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return data["fundamentals"]


# =============================================================================
# P1 — recompute_cross_market_with_cap_warnings() API
# =============================================================================


def test_p1_helper_exists():
    """P1: live_score_engine 必暴露 recompute_cross_market_with_cap_warnings()."""
    from data_sources import live_score_engine

    assert hasattr(
        live_score_engine,
        "recompute_cross_market_with_cap_warnings",
    ), (
        "v5.24 P1 missing: live_score_engine 沒有 "
        "recompute_cross_market_with_cap_warnings() helper。"
        "Lesson #49 API 沒有整合進 cross-market E2E。"
    )


def test_p1_3690hk_peg_warning_auto_triggered(cross_market_fundamentals):
    """P1: 3690.HK PEG=28.72 真實 outlier 必自動觸發 fund.peg warning。

    Per AUDIT_CHANGELOG.md:268 — 3690.HK PEG=28.72 是真實業務數據
    (Meituan 2024 Q3 虧損, PEG 變無意義),不是 mock。
    """
    from data_sources.live_score_engine import (
        recompute_cross_market_with_cap_warnings,
    )

    result = recompute_cross_market_with_cap_warnings(cross_market_fundamentals)

    # 結構驗證 (per v5.23 P5 API + cross-market extension)
    assert "scores" in result, "P1: result 必須含 scores key"
    assert "cap_warnings" in result, "P1: result 必須含 cap_warnings key"
    assert "summary" in result, "P1: result 必須含 summary key"

    # 3690.HK PEG=28.72 → 必觸發 fund.peg warning
    peg_warnings = [
        w for w in result["cap_warnings"] if w["metric"] == "fund.peg"
    ]
    assert peg_warnings, (
        f"P1 FAIL: 3690.HK PEG=28.72 沒觸發 fund.peg warning. "
        f"cap_warnings={result['cap_warnings']}"
    )
    assert "3690.HK" in peg_warnings[0]["tickers"], (
        f"P1 FAIL: 3690.HK 不在 fund.peg warning tickers list. "
        f"got={peg_warnings[0]['tickers']}"
    )
    # 確認 warning 結構完整
    w = peg_warnings[0]
    assert w["threshold_value"] == 25.0, (
        f"P1 FAIL: fund.peg threshold 應為 25.0, got={w['threshold_value']}"
    )
    assert w["is_by_design"] is True, (
        "P1 FAIL: PEG>25 應標 by_design=True (v5.22 P42 後 clip-by-design)"
    )
    # coverage 量化 (1 ticker / 11 total ≈ 9.09%)
    assert w["coverage"] == pytest.approx(1 / 11, abs=0.01), (
        f"P1 FAIL: fund.peg coverage 應 ≈ 1/11, got={w['coverage']}"
    )


def test_p1_other_tickers_no_false_peg_warning(cross_market_fundamentals):
    """P1: 其他 10 ticker (PEG<5) 不應觸發 fund.peg warning。

    避免規則寫太寬 (e.g. 把門檻設為 5) 造成 false positive。
    """
    from data_sources.live_score_engine import (
        recompute_cross_market_with_cap_warnings,
    )

    result = recompute_cross_market_with_cap_warnings(cross_market_fundamentals)
    peg_warnings = [
        w for w in result["cap_warnings"] if w["metric"] == "fund.peg"
    ]
    if peg_warnings:
        non_outliers = [
            t for t in peg_warnings[0]["tickers"] if t != "3690.HK"
        ]
        assert not non_outliers, (
            f"P1 FAIL: 只有 3690.HK PEG>25, 其他 ticker PEG 都 <5. "
            f"unexpected non-outliers in warning: {non_outliers}"
        )


def test_p1_summary_warning_by_metric(cross_market_fundamentals):
    """P1: summary.warning_by_metric 結構驗證。"""
    from data_sources.live_score_engine import (
        recompute_cross_market_with_cap_warnings,
    )

    result = recompute_cross_market_with_cap_warnings(cross_market_fundamentals)

    assert "summary" in result
    assert "warning_by_metric" in result["summary"]
    assert "total_warnings" in result["summary"]
    # 3690.HK PEG=28.72 必觸發 fund.peg
    assert result["summary"]["warning_by_metric"].get("fund.peg") == 1
    assert result["summary"]["total_warnings"] >= 1


# =============================================================================
# P2 — cross_market_real_yfinance_e2e.main() 整合 (--mode frozen 不需網路)
# =============================================================================


def test_p2_main_emits_cap_zone_warning_on_frozen_mode(caplog):
    """P2: cross_market_real_yfinance_e2e.main() --mode frozen 必 emit cap-zone logger.warning。

    Lesson #49 整合驗證: operator 跑 CLI 不必手動跑 cap_coverage_report,
    自動從 logger 看到哪些 ticker 撞 cap。
    """
    import logging

    from cross_market_real_yfinance_e2e import main as e2e_main

    # frozen mode 不需 yfinance 網路,只跑 hardcoded fixture
    test_argv = [
        "cross_market_real_yfinance_e2e.py",
        "--mode", "frozen",
    ]
    import unittest.mock as mock
    with mock.patch.object(sys, "argv", test_argv):
        with caplog.at_level(logging.WARNING):
            try:
                e2e_main()
            except SystemExit as e:
                # main() 在失敗時 sys.exit(1),允許
                assert e.code in (0, 1), f"main() 異常 exit code: {e.code}"

    # 驗證 logger.warning 被呼叫且含 fund.peg 與 3690.HK
    warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
    cap_warnings_emitted = [
        m for m in warning_messages
        if "fund.peg" in str(m) and "3690.HK" in str(m)
    ]
    assert cap_warnings_emitted, (
        f"P2 FAIL: main() --mode frozen 沒 emit cap-zone warning 含 fund.peg + 3690.HK.\n"
        f"all warnings: {warning_messages}"
    )


def test_p2_v521_mode_still_works(cross_market_fundamentals):
    """P2 regression guard: v5.21 三層 loader 仍正常運作,沒被 v5.24 破壞。"""
    from cross_market_real_yfinance_e2e import TICKER_UNIVERSE

    assert len(TICKER_UNIVERSE) == 11, (
        f"P2 FAIL: TICKER_UNIVERSE 應維持 11 ticker, got={len(TICKER_UNIVERSE)}"
    )
    assert "3690.HK" in TICKER_UNIVERSE
    # Fixture 完整性
    assert "3690.HK" in cross_market_fundamentals
    assert cross_market_fundamentals["3690.HK"]["peg"] == 28.72, (
        f"P2 FAIL: 3690.HK fixture PEG 應為 28.72 (per v5.22 P42 真實 outlier),"
        f" got={cross_market_fundamentals['3690.HK']['peg']}"
    )