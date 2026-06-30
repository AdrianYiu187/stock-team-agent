"""v5.21 P3 — CLI integration tests for cross_market_real_yfinance_e2e.py.

驗證 (per docs/v5.21_live_fixtures_design.md §3.1):
1. --mode frozen: exit 0, 11/11 ticker 從 hardcoded 載入,fixtures JSON 不變
2. --mode live + no network: 仍能 fallback to cache 或 fail (graceful)
3. --mode hybrid: live + hardcoded fallback 邏輯正確
4. backward compat: 不加 flag 預設行為與 v5.20 一致（--mode live 但無 network = yfinance 失敗 → 仍 0 數據）
5. CLI flag --region-neutral-macro 仍 work
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
CLI_PATH = SCRIPTS_DIR / "cross_market_real_yfinance_e2e.py"
FIXTURES_PATH = SCRIPTS_DIR / "tests" / "fixtures" / "tickers_fundamentals.json"


def _run_cli(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run cross_market_real_yfinance_e2e.py with given args."""
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=SCRIPTS_DIR.parent,
    )


class TestCLIFrozenMode:
    """v5.21 P3 frozen mode CLI behavior."""

    def test_frozen_mode_exit_zero(self):
        """--mode frozen → exit 0."""
        result = _run_cli("--mode", "frozen")
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
        )

    def test_frozen_mode_loads_all_11_tickers(self):
        """--mode frozen → 11/11 ticker 從 hardcoded 載入."""
        result = _run_cli("--mode", "frozen")
        assert "11/11 ticker 從 hardcoded 載入" in result.stdout, (
            f"Expected hardcoded load message in stdout:\n{result.stdout[-500:]}"
        )

    def test_frozen_mode_does_not_overwrite_fixtures(self):
        """--mode frozen 不寫回 fixtures JSON (避免覆蓋 hardcoded snapshot)."""
        fixtures_before = FIXTURES_PATH.read_text(encoding="utf-8")
        result = _run_cli("--mode", "frozen")
        assert result.returncode == 0
        fixtures_after = FIXTURES_PATH.read_text(encoding="utf-8")
        assert fixtures_before == fixtures_after, (
            "Frozen mode should NOT modify hardcoded fixtures file"
        )

    def test_frozen_mode_skip_write_message(self):
        """--mode frozen 顯示 skip 寫回訊息."""
        result = _run_cli("--mode", "frozen")
        assert "Frozen mode: skip 寫回" in result.stdout

    def test_frozen_mode_region_neutral_macro(self):
        """--mode frozen + --region-neutral-macro 都 work."""
        result = _run_cli("--mode", "frozen", "--region-neutral-macro")
        assert result.returncode == 0
        assert "中性化為 0.5" in result.stdout


class TestCLIInvalidMode:
    """v5.21 P3 — invalid args handling."""

    def test_invalid_mode_exits_error(self):
        """--mode invalid → argparse error exit code 2."""
        result = _run_cli("--mode", "bogus")
        assert result.returncode != 0


class TestCLIOutputStructure:
    """v5.21 P3 — output contains expected sections (frozen mode)."""

    def test_includes_std_section(self):
        """Output 必含 Std 量化 section."""
        result = _run_cli("--mode", "frozen")
        assert "v5.10 std" in result.stdout
        assert "v5.11.3 std" in result.stdout
        assert "Δ std" in result.stdout

    def test_includes_signal_distribution(self):
        """Output 必含 v5.16 P50 signal distribution per ticker."""
        result = _run_cli("--mode", "frozen")
        assert "Signal Distribution Per Ticker" in result.stdout
        assert "Final" in result.stdout
        assert "Majority" in result.stdout

    def test_includes_all_11_tickers(self):
        """Output 必含全部 11 ticker."""
        result = _run_cli("--mode", "frozen")
        expected_tickers = [
            "AAPL", "MSFT", "GOOGL", "NVDA",
            "0700.HK", "9988.HK", "3690.HK",
            "600519.SS", "000858.SZ", "601318.SS", "000333.SZ",
        ]
        for t in expected_tickers:
            assert t in result.stdout, f"Ticker {t} missing from output"
