"""v5.31 P0 — 死代碼 + 硬代碼第二輪審計 (per user request)

掃描目標:
  1. scripts/dashboard_api.py — v5.30 P3 新增的 PER_REGION_WEIGHTS_7D 內部是否有 hardcoded weight
     應 reuse MULTIFACTOR_WEIGHTS (4D fund_heavy) 而非重複數值
  2. scripts/dashboard_api.py — signal threshold (0.58 / 0.45) 應為常數
  3. scripts/dashboard_api.py — FastAPI app.version 與 docstring 應為 v5.31
  4. TICKER_REGION_MAP 內 ticker 與 fixture signal_distribution_per_ticker + extended_signal_distribution_per_ticker 比對
     (死碼: 在 region map 但 fixture 沒有 → 永遠 fallback 為 "US")

審計結果輸出:
  - findings: List[Dict{rule, file, line, severity, message}]
  - counts: {critical, warning, info}

執行:
  python scripts/audit_v531_dead_code.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS  # noqa: E402

DASHBOARD_API = _REPO_ROOT / "scripts" / "dashboard_api.py"
FIXTURE = _REPO_ROOT / "scripts" / "tests" / "fixtures" / "tickers_fundamentals.json"


def audit_dashboard_api() -> List[Dict]:
    """掃描 dashboard_api.py 找死碼 / 硬碼 / 版本漂移。"""
    findings: List[Dict] = []
    src = DASHBOARD_API.read_text()
    lines = src.splitlines()

    # Rule 1: HK/CN weights 應 reuse MULTIFACTOR_WEIGHTS 而非 hardcoded
    # 找 PER_REGION_WEIGHTS_7D 內 HK 段
    hk_block_re = re.compile(
        r'"HK":\s*\{([^}]+)\}',
        re.DOTALL,
    )
    cn_block_re = re.compile(
        r'"CN":\s*\{([^}]+)\}',
        re.DOTALL,
    )
    hk_match = hk_block_re.search(src)
    cn_match = cn_block_re.search(src)
    if hk_match and cn_match:
        hk_body = hk_match.group(1)
        cn_body = cn_match.group(1)
        # 檢查是否 hardcoded tech:0.20, fund:0.50, market:0.15, risk:0.15
        for key, expected in [
            ("tech", "0.20"),
            ("fund", "0.50"),
            ("market", "0.15"),
            ("risk", "0.15"),
        ]:
            if f'"{key}": {expected}' in hk_body and f'"{key}": {expected}' in cn_body:
                findings.append({
                    "rule": "hardcoded_weight_reuse_multifactor_weights",
                    "file": str(DASHBOARD_API.relative_to(_REPO_ROOT)),
                    "severity": "warning",
                    "message": (
                        f"HK/CN region weights hardcode {key}={expected}. "
                        f"應提取 `WEIGHTS_4D_FUND_HEAVY = {{**dict(MULTIFACTOR_WEIGHTS), "
                        f"'sentiment':0.0, 'news':0.0, 'macro':0.0}}` 常數並 reuse。"
                    ),
                })
                break  # 一個 finding 代表整個 block 問題

    # Rule 2: signal threshold 應為常數 (composite_7d > 0.58 BUY / < 0.45 SELL)
    if "if composite_7d > 0.58" in src and "elif composite_7d < 0.45" in src:
        # 找對應行
        for i, line in enumerate(lines, start=1):
            if "composite_7d > 0.58" in line:
                findings.append({
                    "rule": "hardcoded_threshold_extract_constant",
                    "file": str(DASHBOARD_API.relative_to(_REPO_ROOT)),
                    "line": i,
                    "severity": "info",
                    "message": (
                        "signal threshold 0.58 (BUY) / 0.45 (SELL) hardcoded. "
                        "應提取 `BUY_THRESHOLD = 0.58`, `SELL_THRESHOLD = 0.45` 常數 "
                        "(與 4D composite_to_signal 同步, 避免 future drift)。"
                    ),
                })
                break

    # Rule 3: FastAPI app.version 應為 v5.31
    version_match = re.search(r'version="(\d+\.\d+\.\d+)"', src)
    if version_match:
        current_ver = version_match.group(1)
        if current_ver != "5.31.0":
            findings.append({
                "rule": "version_drift",
                "file": str(DASHBOARD_API.relative_to(_REPO_ROOT)),
                "line": _find_line(lines, f'version="{current_ver}"'),
                "severity": "critical",
                "message": (
                    f"app.version='{current_ver}' 應升級為 '5.31.0' "
                    f"(v5.31 iteration 含 P0 死碼審計 + P1 升級 + P2 重新量化)。"
                ),
            })

    # Rule 4: TICKER_REGION_MAP 內 ticker 與 fixture 比對 (死碼)
    # 提取 ticker set
    map_match = re.search(r'TICKER_REGION_MAP\s*=\s*\{([^}]+)\}', src, re.DOTALL)
    if map_match and FIXTURE.exists():
        body = map_match.group(1)
        map_tickers = set(re.findall(r'"([\w\.\-]+)":\s*"[A-Z]+"', body))
        fixture_data = json.loads(FIXTURE.read_text())
        fixture_tickers = set(fixture_data.get("signal_distribution_per_ticker", {}).keys()) | set(
            fixture_data.get("extended_signal_distribution_per_ticker", {}).keys()
        )
        # 移除 dict 自帶 key
        map_tickers.discard("US")
        map_tickers.discard("HK")
        map_tickers.discard("CN")
        map_tickers.discard("global")
        missing = map_tickers - fixture_tickers
        if missing:
            findings.append({
                "rule": "dead_code_ticker_region_map_missing_in_fixture",
                "file": str(DASHBOARD_API.relative_to(_REPO_ROOT)),
                "severity": "warning",
                "message": (
                    f"TICKER_REGION_MAP 內 {len(missing)} 個 ticker 在 fixture 不存在 "
                    f"(永遠 fallback 'US'): {sorted(missing)}。"
                ),
            })

    return findings


def _find_line(lines: List[str], needle: str) -> int:
    for i, line in enumerate(lines, start=1):
        if needle in line:
            return i
    return 0


def main():
    findings = audit_dashboard_api()
    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] += 1

    print("=" * 72)
    print("v5.31 P0 死代碼 + 硬代碼審計報告")
    print("=" * 72)
    print(f"\n總計: {len(findings)} 個 findings")
    print(f"  critical: {counts['critical']}")
    print(f"  warning:  {counts['warning']}")
    print(f"  info:     {counts['info']}")
    print()

    if not findings:
        print("✅ 零死碼 / 零硬碼 / 版本一致 — v5.31 P0 通過")
    else:
        for f in findings:
            loc = f"line {f['line']}" if "line" in f else "—"
            print(f"[{f['severity'].upper():8s}] {f['rule']}")
            print(f"  file: {f['file']}  {loc}")
            print(f"  {f['message']}")
            print()

    # 寫 JSON 報告
    report_path = _REPO_ROOT / "docs" / "v5.31_p0_dead_code_audit.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps({
        "findings": findings,
        "counts": counts,
    }, indent=2, ensure_ascii=False))
    print(f"✅ Report saved to: {report_path.relative_to(_REPO_ROOT)}")

    # 退出碼: critical=2, warning=1, info=0
    if counts["critical"] > 0:
        sys.exit(2)
    elif counts["warning"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()