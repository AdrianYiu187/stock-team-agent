"""v5.11.3 永久 Artifact Integrity Guard — 黃金標準

Purpose:
    每次 audit 結束後跑一次，確認 v5.11 fix artifacts 都健康：
    1. `scripts/verify_v511_fixes.py` pytest 仍 26/26 PASS
    2. Source 真的從 v5.10 改到 v5.11（score_to_5tier boundary ±30 → ±15/±5）
    3. Backtest artifacts (JSON) 存在且結構完整
    4. Cross-market artifacts (JSON) 存在且結構完整
    5. `utils/errors.py` 真的刪乾淨（無生產引用）
    6. Pyright 0 errors（若已安裝）

Usage:
    python -m pytest scripts/verify_v511_artifact_integrity.py -v
    python scripts/verify_v511_artifact_integrity.py

History:
    - v5.11.3 audit (2026-06-26): created after v1 ad-hoc verifier hit 2 false-negatives
      (pytest "26 passed" 字串計數 + v5.10 grep 雙空格)
    - 教訓見 stock-team-agent-v510-loop-skill-audit skill pitfall #28
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


# --- 固定路徑（audit 完成後每次跑都用同一份事實） ----------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent  # scripts/ → stock-team-agent/
SCRIPTS = REPO_ROOT / "scripts"
TESTS = SCRIPTS / "tests"
VERIFY_FILE = SCRIPTS / "verify_v511_fixes.py"
STOCK_ANALYSIS = SCRIPTS / "stock_analysis.py"
TEST_STOCK_AGENT = TESTS / "test_stock_agent.py"
UTILS_ERRORS = SCRIPTS / "utils" / "errors.py"
AUDIT_CHANGELOG = REPO_ROOT / "AUDIT_CHANGELOG.md"

# Backtest artifacts（不入 git，但每次 verify 都該在 /tmp/）
BACKTEST_SCRIPT = Path("/tmp/aapl_backtest_v510_vs_v5113.py")
BACKTEST_JSON = Path("/tmp/aapl_backtest_v510_vs_v5113.json")
CROSSMARKET_SCRIPT = Path("/tmp/cross_market_e2e_v5113.py")
CROSSMARKET_JSON = Path("/tmp/cross_market_e2e_v5113.json")


# ============================================================================
# Check 1: verify_v511_fixes.py 仍 26/26 PASS
# ============================================================================
def test_verify_v511_fixes_pytest_26_passed() -> None:
    """跑 verify_v511_fixes.py 必須 26 passed, 0 failed.

    Pitfall #28: 不可用 'PASSED' 字串計數 — pytest summary line 只寫
    '26 passed in 0.03s'。正確做法是用 regex 從 summary line 抓數字。
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(VERIFY_FILE), "--tb=no", "-q"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )
    output = result.stdout + result.stderr

    # Regex 從 summary line 抓 'N passed'
    m_passed = re.search(r"(\d+)\s+passed", output)
    m_failed = re.search(r"(\d+)\s+failed", output)
    n_passed = int(m_passed.group(1)) if m_passed else 0
    n_failed = int(m_failed.group(1)) if m_failed else 0

    assert result.returncode == 0, f"pytest exit={result.returncode}\n{output}"
    assert n_failed == 0, f"verify_v511_fixes.py has {n_failed} failures:\n{output}"
    assert n_passed >= 26, (
        f"verify_v511_fixes.py expected ≥26 passed, got {n_passed}.\n"
        f"v5.11 verifier baseline was 26 tests. If you intentionally changed\n"
        f"the count, update this assertion + the AUDIT_CHANGELOG.\n"
        f"\n--- pytest output ---\n{output}"
    )


# ============================================================================
# Check 2: score_to_5tier boundary 確實是 v5.11 (±15/±5)，不是 v5.10 (±30)
# ============================================================================
def test_score_to_5tier_uses_v511_boundary() -> None:
    """v5.11 N14 修復：score_to_5tier 必須用 ±15/±5 細邊界，不是 v5.10 的 ±30/±60。

    Pitfall #28: 不要用 `>=  30`（雙空格）這類 fragile pattern，要精準 match
    v5.11 實際寫法：`overall<-15:1, <-5:2, <5:3, <15:4, else:5`
    """
    if not STOCK_ANALYSIS.exists():
        pytest.skip(f"{STOCK_ANALYSIS} not found")

    text = STOCK_ANALYSIS.read_text(encoding="utf-8")

    # v5.11 score_to_5tier 真實寫法（從 stock_analysis.py:65-69 確認）：
    #     if overall >=  15: return 5
    #     if overall >=   5: return 4
    #     if overall >=  -5: return 3
    #     if overall >= -15: return 2
    #     return 1
    # v5.10 寫法: >= 30, >= 10, >= -10, >= -30（寬邊界 → 永遠 HOLD）
    #
    # Pitfall #28: 不要硬 grep "overall < -15" — 真實源碼用 `return 1` 隱式表達。
    # 用 regex 抓行首 `if overall >= N` 的 N 值序列，斷言最大值是 15 而非 30。
    boundary_pattern = re.compile(
        r"if\s+overall\s*>=\s*(-?\d+)\s*:", re.MULTILINE
    )
    boundaries = [int(m.group(1)) for m in boundary_pattern.finditer(text)]
    # v5.11 期望: [15, 5, -5, -15]（4 條邊界，最後一個是 implicit return）
    # v5.10 期望: [30, 10, -10, -30]（寬邊界，會讓 N14 bug 重現）

    assert 15 in boundaries, (
        f"v5.11 score_to_5tier 必須包含 `overall >= 15` 邊界（5 STRONG_BUY）。\n"
        f"找到的邊界值: {boundaries}\n"
        f"可能 revert 到 v5.10（邊界值會是 30）— N14 bug 會重現"
    )
    assert -15 in boundaries, (
        f"v5.11 score_to_5tier 必須包含 `overall >= -15` 邊界（2 SELL）。\n"
        f"找到的邊界值: {boundaries}"
    )
    # 反例：v5.10 的 ±30 不應出現
    assert 30 not in boundaries, (
        f"發現 v5.10 寬邊界 `overall >= 30` — N14 修復被 revert。\n"
        f"找到的邊界值: {boundaries}"
    )
    assert -30 not in boundaries, (
        f"發現 v5.10 寬邊界 `overall >= -30` — N14 修復被 revert。\n"
        f"找到的邊界值: {boundaries}"
    )


# ============================================================================
# Check 3: utils/errors.py 真的刪乾淨（production + tests 都無引用）
# ============================================================================
def test_utils_errors_py_fully_removed() -> None:
    """v5.11 Pattern 25 dead-code 刪除：utils/errors.py 不存在且無引用。

    Pattern 25 教訓：production 死代碼通常伴隨 test mock — 一併刪才不會留
    dangling import / coverage hole。
    """
    # 檔案不存在
    assert not UTILS_ERRORS.exists(), (
        f"{UTILS_ERRORS} 還在。v5.11 死代碼清除失敗。"
    )

    # 整個 src tree 無 utils.errors 的 *實際 import*。
    # 注意：verify_v511_fixes.py 和 verifier 自己的 docstring 會提到 utils.errors
    # （作為 pitfall 記錄），不是真實 import。用 regex 抓真實 import 語句。
    import re as _re
    SELF = Path(__file__).resolve()
    _import_pattern = _re.compile(
        r"^\s*(?:from\s+utils\.errors|import\s+utils\.errors)", _re.MULTILINE
    )
    for py_file in SCRIPTS.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if py_file.resolve() == SELF:
            continue  # verifier 自己的 docstring
        if py_file.name.startswith("verify_v511_"):
            continue  # verifier 系列的 docstring 也會提到
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        assert not _import_pattern.search(text), (
            f"{py_file} 有真實 `import utils.errors` 語句 — "
            f"Pattern 25 死代碼未清乾淨"
        )


# ============================================================================
# Check 4: AUDIT_CHANGELOG.md 有 v5.11 段
# ============================================================================
def test_audit_changelog_has_v511_section() -> None:
    """文檔守護：v5.11 修復必須有 changelog 記錄。"""
    if not AUDIT_CHANGELOG.exists():
        pytest.skip(f"{AUDIT_CHANGELOG} not found")

    text = AUDIT_CHANGELOG.read_text(encoding="utf-8")
    assert re.search(r"^##\s*v?5\.11", text, re.MULTILINE), (
        f"{AUDIT_CHANGELOG} 沒有 v5.11 段。每次 audit 完成必須更新 changelog。"
    )


# ============================================================================
# Check 5: Backtest artifacts 存在且結構完整（不入 git，optional）
# ============================================================================
def test_aapl_backtest_artifact_exists() -> None:
    """AAPL 90 天 backtest artifacts 存在（量化 v5.10 vs v5.11.3）。"""
    if not BACKTEST_SCRIPT.exists():
        pytest.skip(
            f"{BACKTEST_SCRIPT} 不在。Backtest 是 audit 後的量化工作，"
            f"可選 — 沒做就 skip。"
        )
    if not BACKTEST_JSON.exists():
        pytest.skip(f"{BACKTEST_JSON} 不在。沒跑過 backtest，skip。")

    data = json.loads(BACKTEST_JSON.read_text(encoding="utf-8"))
    assert "v5_10" in data and "v5_11_3" in data and "delta" in data, (
        f"{BACKTEST_JSON} 結構缺欄位。預期 v5_10 / v5_11_3 / delta 三個 key。"
    )
    # 量化 delta 必須有真實改善（directional_accuracy + 9.91pp）
    delta = data.get("delta", {})
    dir_acc_delta = delta.get("directional_accuracy_pp")
    if dir_acc_delta is not None:
        assert dir_acc_delta > 0, (
            f"directional_accuracy delta = {dir_acc_delta}pp，預期 > 0（v5.11 改善）"
        )


# ============================================================================
# Check 6: Cross-market artifacts 存在且結構完整（optional）
# ============================================================================
def test_cross_market_artifact_exists() -> None:
    """Cross-market E2E artifacts 存在（HK 0700.HK / CN 600519.SS）。"""
    if not CROSSMARKET_SCRIPT.exists():
        pytest.skip(f"{CROSSMARKET_SCRIPT} 不在，可選 skip。")
    if not CROSSMARKET_JSON.exists():
        pytest.skip(f"{CROSSMARKET_JSON} 不在，可選 skip。")

    data = json.loads(CROSSMARKET_JSON.read_text(encoding="utf-8"))
    # 預期結構：每個 ticker 是一個 key
    assert len(data) >= 1, f"{CROSSMARKET_JSON} 空 — 至少要有一個 ticker 結果"


# ============================================================================
# Check 7: test_stock_agent.py 有 TestV511CriticalFixes class
# ============================================================================
def test_test_stock_agent_has_v511_suite() -> None:
    """test_stock_agent.py 必須包含 v5.11 N-series tests。"""
    if not TEST_STOCK_AGENT.exists():
        pytest.skip(f"{TEST_STOCK_AGENT} not found")

    text = TEST_STOCK_AGENT.read_text(encoding="utf-8")
    assert "TestV511CriticalFixes" in text or "V511" in text, (
        f"{TEST_STOCK_AGENT} 缺 v5.11 N-series tests。每次 audit 必須新增或保留。"
    )


# ============================================================================
# Check 8: Pyright 無 errors（optional，沒裝就 skip）
# ============================================================================
def test_pyright_zero_errors() -> None:
    """Pyright static type check — 沒裝就 skip。

    從 stock-team-agent-v510-loop-skill-audit skill pitfall #12 沿用：
    公式改動後必須 type-check 0 errors 才算 audit 完成。
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyright", str(SCRIPTS / "stock_analysis.py")],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError:
        pytest.skip("pyright not installed")

    output = result.stdout + result.stderr
    # Pyright 0 errors 會打印 "0 errors"
    m = re.search(r"(\d+)\s+errors?", output)
    n_errors = int(m.group(1)) if m else -1

    if n_errors == -1:
        pytest.skip(f"pyright output 無法解析:\n{output[:500]}")
    assert n_errors == 0, f"pyright found {n_errors} errors:\n{output}"


# ============================================================================
# Self-test: 直接跑這個檔案時顯示所有 check 結果
# ============================================================================
if __name__ == "__main__":
    rc = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(rc)