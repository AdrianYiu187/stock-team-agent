"""v5.14 quantify_cap_flatline 量化腳本的 pytest guard.

目的：守住 v5.13 後 14 個真實 cap flatline 的量化基線。
未來任何 commit 改 stock_analysis.py 的 multifactor 函數都可能改變這些 flatline %。
本測試確保：
1. 量化腳本能 import 並運行
2. AST 偵測能找到 ≥10 個 candidate cap branches
3. 14 個 SUSPICIOUS_CAPS 都有 ≥30% flat in zone（v5.13 baseline）
4. 2 個 control cases (fund roe, fund growth) 仍維持 0% flat（v5.11 N7/N8 修復 preserved）

歷史：
- 2026-06-28 created (v5.14 roadmap Stage 0)
"""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
QUANTIFY_SCRIPT = SCRIPTS_DIR / "quantify_cap_flatline.py"


def test_quantify_script_exists():
    """quantify_cap_flatline.py exists and is importable."""
    assert QUANTIFY_SCRIPT.exists(), f"Missing: {QUANTIFY_SCRIPT}"


def test_quantify_script_runs():
    """Script runs end-to-end (--quick mode) without error."""
    result = subprocess.run(
        [sys.executable, str(QUANTIFY_SCRIPT), "--quick"],
        capture_output=True, text=True, timeout=60, cwd=str(SCRIPTS_DIR),
    )
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert "Stage B" in result.stdout, "Stage B section missing"
    assert "real flatlines" in result.stdout.lower() or "FLAT" in result.stdout


def test_quantify_script_detects_at_least_10_caps():
    """AST stage must find ≥10 cap branches in stock_analysis.py."""
    result = subprocess.run(
        [sys.executable, str(QUANTIFY_SCRIPT), "--quick"],
        capture_output=True, text=True, timeout=60, cwd=str(SCRIPTS_DIR),
    )
    # Stage A output: "AST detected N potential cap branches"
    import re
    m = re.search(r"AST detected (\d+) potential cap branches", result.stdout)
    assert m is not None, "Stage A output missing"
    n = int(m.group(1))
    assert n >= 10, f"Expected >=10 AST caps, got {n}"


def test_v514_baseline_2_real_flats_remaining():
    """Verify v5.14 P37+P38+P39+P40 baseline: 14 → 2-4 real flatlines remaining.

    After v5.14 P37: market pos_52wk 4 segments → 0
    After v5.14 P38: market from_high + ytd 2 caps → 0
    After v5.14 P39: tech rsi + macd + momentum 3 caps → 0 (ma50 fallback preserved)
    After v5.14 P40: risk var_95 + max_dd 2 caps → 0
    Remaining: market beta 1 + tech ma50 1 (preserved by design) = 2
    """
    result = subprocess.run(
        [sys.executable, str(QUANTIFY_SCRIPT), "--quick"],
        capture_output=True, text=True, timeout=60, cwd=str(SCRIPTS_DIR),
    )
    import re
    m = re.search(r"Total real flatlines \(>30% flat\): (\d+)/(\d+)", result.stdout)
    assert m is not None, "Stage B summary missing"
    real = int(m.group(1))
    total = int(m.group(2))
    # After P37+P38+P39+P40: 14 → ~2-4
    # Remaining: market beta (1) + tech ma50 fallback (preserved, 1) = 2-3
    assert 1 <= real <= 4, f"Expected 1-4 real flatlines after P37+P38+P39+P40, got {real}"
    assert total == 16, f"Suspicious caps list changed: {total} (expected 16)"


def test_fund_score_no_cap_regression():
    """v5.11 N7/N8 fixes must remain in effect.

    fund roe and fund growth should NOT have flatline > 30%
    in any realistic cap zone (since v5.11 they are continuous).
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    from quantify_cap_flatline import quantify_flatline

    # These were the v5.11 N7/N8 fixes
    flat_roe, total = quantify_flatline("fund", "roe", -1, -0.5, n_samples=50)
    flat_growth, total = quantify_flatline("fund", "revenue_growth", -1, -0.5, n_samples=50)
    assert flat_roe / total < 0.30, f"fund roe regression: {flat_roe}/{total} flat (v5.11 N7 must be preserved)"
    assert flat_growth / total < 0.30, f"fund growth regression: {flat_growth}/{total} flat (v5.11 N8 must be preserved)"


def test_market_pos_52wk_no_longer_has_segments():
    """v5.14 P37 fix: market_score_multifactor pos_52wk is now continuous (no flat segments).

    Each segment should now produce flatline < 30% (was >=80% before P37).
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    from quantify_cap_flatline import quantify_flatline

    # After v5.14 P37: pos_52wk is fully linear in [0, 100], so each zone has < 30% flat
    for lo, hi in [(0, 5), (20, 50), (50, 80), (80, 100)]:
        flat, total = quantify_flatline("market", "pos_52wk", lo, hi, n_samples=50)
        pct = flat / total
        # After fix: < 30% flat (was >70% before)
        assert pct < 0.30, f"pos_52wk [{lo}, {hi}] still flat: {pct*100:.0f}% (v5.14 P37 must be preserved)"


def test_tech_macd_no_longer_two_sided_cap():
    """v5.14 P39 fix: tech macd_val [-10, +10] is now continuous (no cap)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from quantify_cap_flatline import quantify_flatline

    # After v5.14 P39: macd is linear in [-10, +10]
    flat_pos, _ = quantify_flatline("tech", "macd_val", 2, 5, n_samples=50)
    flat_neg, _ = quantify_flatline("tech", "macd_val", -5, -2, n_samples=50)
    assert flat_pos / 50 < 0.30, f"tech macd [+2, +5] still flat: {flat_pos}/50 (v5.14 P39 must be preserved)"
    assert flat_neg / 50 < 0.30, f"tech macd [-5, -2] still flat: {flat_neg}/50 (v5.14 P39 must be preserved)"
