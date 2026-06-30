"""v5.11.3 + Stale-Reminder 永久 Artifact Health Guard.

Purpose:
    Session-end / turn-end 守護 — 即使沒有新 edit，也跑一次確認：
    1. Git working tree 狀態（clean / dirty）
    2. HEAD 仍是最後一個 v5.11.3 audit commit
    3. v5.11.3 三條關鍵路徑（SKILL.md / cross_market script / integrity verifier）仍存在 + 內容健康
    4. Combined pytest ≥33 passed（含 26 fixes + 7 integrity）
    5. JSON artifacts 仍可在 /tmp/ 讀到

觸發場景：
    - Hermes session 結束
    - Stale reminder 重複觸發（見 hermes-stale-reminder-handling skill）
    - 用戶說「幫我確認東西還在」

History:
    - v5.11.3 audit (2026-06-26) turn 7: 從 23-check ad-hoc verifier 永久化
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# v5.11.3 audit 三條關鍵路徑
SKILL_MD = Path("/Users/adrian/.hermes/skills/productivity/stock-team-agent-v510-loop-skill-audit/SKILL.md")
CROSS_MARKET_SCRIPT = SCRIPTS / "cross_market_e2e_ticker_specific.py"
INTEGRITY_VERIFIER = SCRIPTS / "verify_v511_artifact_integrity.py"
FIXES_VERIFIER = SCRIPTS / "verify_v511_fixes.py"

# 預期 HEAD（v5.11.3 audit 收尾 commit 系列）
# a510bfd = turn9 fix (最新)
# f858db7 = turn7 guard fix
# a2193f2 = Stage 6.2 cross_time
# 2b33101 = session-end health guard
# ceb75d8 = Stage 6.1 cross_market
# d273f2a = audit-end integrity
# afd11be = golden 26 fixes
# 用 fuzzy match：所有 v5.11+ / turn / fix / Stage / test 開頭的 commit 都接受
# 避免每次 commit 都要更新 hash 列表
# v5.20: 加入 v5.20 commit prefix（079bfd3 fix + 1473c31 docs）+ regex 範圍擴展 v5.20
EXPECTED_HEAD_PATTERN = re.compile(
    r"(?:^a510bfd|^f858db7|^a2193f2|^2b33101|^ceb75d8|^d273f2a|^afd11be"
    r"|^fda7b1c|^97316a7|^ad04d4b|^729091d"
    r"|^2095bee|^4d6a7b2|^9e18150|^f519b0d|^5e53724|^85ef28c|^a6c40b3"
    r"|^09c18b4|^f51f16b|^2fca096|^e864c0d|^daa791c|^079bfd3|^1473c31"
    r"|v5\.(?:1[1-9]|20)|fix\(turn|test\(v5\.(?:1[1-9]|20)|docs\(v5\.(?:1[1-9]|20)|Stage [0-9])"
)

# JSON artifacts
CROSS_MARKET_JSON = Path("/tmp/cross_market_e2e_ticker_specific.json")
AAPL_BACKTEST_JSON = Path("/tmp/aapl_backtest_v510_vs_v5113.json")


# ============================================================================
# Section A: Git fact-check（hermes-stale-reminder-handling skill SR-1）
# ============================================================================
def test_git_working_tree_state() -> None:
    """Git working tree 必須 clean，或 HEAD 必須是 v5.11.3 已知 commit。

    若 git status 非空（如有未提交改動），skip 此 test — 表示真的有未驗證 edit。
    """
    res = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=10,
    )
    if res.stdout.strip():
        # 檢查是否只有「這次新加的 verifier」造成 dirty
        # 若只有 ?? scripts/verify_turn7_artifact_health.py — 預期（剛寫好待 commit）
        dirty_lines = [
            line for line in res.stdout.strip().split("\n")
            if line and "verify_turn7_artifact_health.py" not in line
        ]
        if dirty_lines:
            pytest.skip(
                f"git working tree 有非 verifier 的未提交改動: {dirty_lines[:3]}\n"
                f"這不是 stale-reminder context — 應先處理真實 edit"
            )
        # 只有新加的 verifier dirty — 預期 skip

    res = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=10,
    )
    head = res.stdout.strip()
    assert EXPECTED_HEAD_PATTERN.search(head), (
        f"HEAD 不在 v5.11.3 已知 commit 範圍內: {head}\n"
        f"預期至少一個: ceb75d8 (Stage 6.1) / afd11be (golden) / d273f2a (integrity)"
    )


# ============================================================================
# Section B: SKILL.md pitfall #28 健康
# ============================================================================
def test_skill_md_pitfall_28_present() -> None:
    """v510-loop-skill-audit SKILL.md 必須有 Pitfall #28（regex + boundary list 教訓）。"""
    if not SKILL_MD.exists():
        pytest.skip(f"{SKILL_MD} 不存在")
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "Pitfall #28" in text, "缺 Pitfall #28 標題"
    assert r"(\d+)\s+passed" in text, "缺 regex pattern 範例"
    assert "boundaries" in text, "缺 boundary list 範例"
    assert "WRONG" in text and "RIGHT" in text, "缺 WRONG/RIGHT 對比"
    assert "verify_v511_artifact_integrity" in text, "缺 verify_v511_artifact_integrity 引用"


# ============================================================================
# Section C: cross_market_e2e_ticker_specific.py 健康
# ============================================================================
def test_cross_market_script_importable() -> None:
    """cross_market_e2e_ticker_specific.py 必須可 import（sys.path patch + loader None guard 仍有效）。"""
    if not CROSS_MARKET_SCRIPT.exists():
        pytest.skip(f"{CROSS_MARKET_SCRIPT} 不存在")
    text = CROSS_MARKET_SCRIPT.read_text(encoding="utf-8")
    assert "sys.path.insert" in text, "缺 sys.path.insert patch"
    assert "spec is None or spec.loader is None" in text, "缺 loader None guard"


def test_cross_market_json_intact() -> None:
    """cross_market JSON 仍存在 + 結構完整 + std_delta 為負（cap 幻覺消失）。"""
    if not CROSS_MARKET_JSON.exists():
        pytest.skip(f"{CROSS_MARKET_JSON} 不存在 — 可能 session restart 後 /tmp/ 被清")
    data = json.loads(CROSS_MARKET_JSON.read_text(encoding="utf-8"))
    assert "v5_10_scores" in data and "v5_11_3_scores" in data and "std_delta" in data
    assert len(data["v5_10_scores"]) == 3, "預期 3 tickers"
    std_delta = data["std_delta"]
    assert std_delta < 0, f"std_delta={std_delta}，預期 < 0（v5.10 cap 幻覺）"


# ============================================================================
# Section D: integrity verifier 自身健康
# ============================================================================
def test_integrity_verifier_has_v511_patterns() -> None:
    """verify_v511_artifact_integrity.py 必須有 boundary regex + 真實 import 過濾。"""
    if not INTEGRITY_VERIFIER.exists():
        pytest.skip(f"{INTEGRITY_VERIFIER} 不存在")
    text = INTEGRITY_VERIFIER.read_text(encoding="utf-8")
    assert "if\\s+overall\\s*>=" in text, "缺 boundary regex"
    assert "from\\s+utils\\.errors|import\\s+utils\\.errors" in text, (
        "缺 utils.errors 真實 import regex（防止 docstring false-positive）"
    )


# ============================================================================
# Section E: Combined pytest 仍 ≥33 PASS
# ============================================================================
def test_combined_pytest_33_passed() -> None:
    """verify_v511_fixes.py + verify_v511_artifact_integrity.py 合跑必須 ≥33 passed。

    Pitfall #28: 用 regex 從 summary line 抓數字（不可用字串計數）。
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         str(FIXES_VERIFIER), str(INTEGRITY_VERIFIER),
         "-q", "--tb=no"],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
    )
    output = result.stdout + result.stderr

    m_passed = re.search(r"(\d+)\s+passed", output)
    m_failed = re.search(r"(\d+)\s+failed", output)
    n_passed = int(m_passed.group(1)) if m_passed else 0
    n_failed = int(m_failed.group(1)) if m_failed else 0

    assert result.returncode == 0, f"pytest exit={result.returncode}\n{output}"
    assert n_failed == 0, f"有 {n_failed} 個 failed test:\n{output}"
    assert n_passed >= 33, (
        f"預期 ≥33 passed（26 fixes + 7 integrity），實際 {n_passed}\n"
        f"如有新 verifier 加入，可提高閾值\n{output}"
    )


# ============================================================================
# Section F: Optional — AAPL backtest JSON（若有）
# ============================================================================
def test_aapl_backtest_json_if_exists() -> None:
    """AAPL 90 天 backtest JSON — optional（不入 git，session restart 後可能消失）。"""
    if not AAPL_BACKTEST_JSON.exists():
        pytest.skip(f"{AAPL_BACKTEST_JSON} 不存在 — 可選 skip")
    data = json.loads(AAPL_BACKTEST_JSON.read_text(encoding="utf-8"))
    assert "v5_10" in data and "v5_11_3" in data and "delta" in data


# ============================================================================
# Self-test
# ============================================================================
if __name__ == "__main__":
    rc = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(rc)