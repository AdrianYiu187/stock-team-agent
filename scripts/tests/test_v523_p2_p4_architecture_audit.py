"""v5.23 P2/P4 — Architecture audit pytest guard.

依據 Lesson #48 + #50, 量化證明架構不適用比「憑感覺跳過」更扎實。

此測試檔保存 Stage B-0 結論 (per scripts/quantify_v523_realtime_social_pitfall.py):
- realtime_quotes.py: I/O layer, 無 scoring cap-zone 概念
- social_sentiment_provider.py: 3-tier classifier, 非 continuous score

若未來有人修改這 2 個檔案加入 scoring function / 改 continuous, 此 pytest 會
紅燈警告重新評估。
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


def _import_module_safely(name):
    """Import module but allow optional requests dependency failure."""
    try:
        return __import__(f"data_sources.{name}", fromlist=[name])
    except ImportError:
        pytest.skip(f"{name} requires optional deps (requests etc.)")


def test_p2_realtime_quotes_no_scoring_function():
    """P2 guard: realtime_quotes.py 不該有 scoring function (架構 by-design I/O layer)。"""
    rt = _import_module_safely("realtime_quotes")
    assert rt is not None

    public_funcs = [
        (name, obj) for name, obj in inspect.getmembers(rt, inspect.isfunction)
        if not name.startswith("_") and obj.__module__ == rt.__name__
    ]

    # 所有 public functions 應回傳 Dict | None, 不該回傳 float (scoring)
    for name, fn in public_funcs:
        sig = inspect.signature(fn)
        assert sig.return_annotation not in (float, "float", int, "int"), (
            f"❌ {name}{sig} 看起來像 scoring function, "
            f"realtime_quotes.py 應該保持 I/O layer (Stage B-0 結論)。"
            f"若有真 pitfall, 跑 cap_coverage_report() 重新量化。"
        )


def test_p4_social_sentiment_keeps_3tier_classifier():
    """P4 guard: _calculate_sentiment_score 應保持 3-tier classifier (>20 / <-20), 非 continuous。"""
    sp = _import_module_safely("social_sentiment_provider")
    assert sp is not None

    calc_fn = getattr(sp, "_calculate_sentiment_score", None)
    assert calc_fn is not None, "_calculate_sentiment_score 不存在"

    src_lines = inspect.getsource(calc_fn).splitlines()
    has_threshold = any("> 20" in line or "< -20" in line for line in src_lines)
    assert has_threshold, (
        "❌ _calculate_sentiment_score 失去 >20 / <-20 threshold, "
        "可能改成 continuous score。Stage B-0 結論: classifier 架構 by-design,"
        "若改成 continuous 需重新跑 cap_coverage_report() 量化。"
    )


def test_p2_p4_quantification_script_runs_clean():
    """Stage B-0 量化腳本本身要可跑且結論穩定。"""
    import subprocess
    result = subprocess.run(
        ["python", str(SCRIPTS_DIR / "quantify_v523_realtime_social_pitfall.py")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"Stage B-0 failed: {result.stderr}"
    assert "✅" in result.stdout, "Stage B-0 結論必須明確標 ✅"
    assert "by-design 保留" in result.stdout
