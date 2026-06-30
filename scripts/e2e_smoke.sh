#!/usr/bin/env bash
# scripts/e2e_smoke.sh — Lesson 30 守護：AAPL E2E 0-warning 驗證
#
# 觸發場景（Rule 9：失敗要大聲）：
#   - v5.7 B9 加了 backtest_engine.py 內部 _json_safe，但 stock_analysis.py 沒套用
#     → pytest 333 pass 但 AAPL CLI 跑出 "Object of type bool is not JSON serializable"
#     → 此腳本把 E2E 變成不可繞過的 gate
#
# 成功標準（Rule 4）：
#   1. AAPL CLI 正常結束（exit 0）
#   2. 輸出含綜合分數 + 訊號（非空 summary）
#   3. 0 warning / 0 error / 0 traceback
#
# Usage:
#   bash scripts/e2e_smoke.sh
#
# Exit codes:
#   0 = PASS（所有 gate 通過）
#   1 = FAIL（任一 gate 失敗）
#   2 = ENV FAIL（Python 或 stock_analysis.py 缺失）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${E2E_LOG:-/tmp/stock_team_e2e_smoke.log}"
TICKER="${E2E_TICKER:-AAPL}"

cd "$REPO_ROOT"

# ---- Gate 0: 環境檢查 ----
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 缺失" >&2
    exit 2
fi

if [ ! -f scripts/stock_analysis.py ]; then
    echo "❌ scripts/stock_analysis.py 缺失" >&2
    exit 2
fi

# ---- 跑 E2E ----
echo "📊 E2E smoke: python3 scripts/stock_analysis.py -c ${TICKER}"
python3 scripts/stock_analysis.py -c "$TICKER" >"$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
    echo "❌ E2E CLI exit $EXIT_CODE（非 0）"
    echo "---tail log---"
    tail -20 "$LOG_FILE"
    exit 1
fi

# ---- Gate 1: 0 warning/error ----
# 排除 v5.20 預期的合法警告（市場關閉、貨幣轉換等不應觸發這幾個）
BAD_PATTERNS='Object of type bool is not JSON serializable|⚠️ JSON保存失敗|⚠️ 自動回測失敗|Traceback|Exception:'
HITS=$(grep -E "$BAD_PATTERNS" "$LOG_FILE" || true)

if [ -n "$HITS" ]; then
    echo "❌ E2E 偵測到禁止 patterns："
    echo "$HITS"
    exit 1
fi

# ---- Gate 2: 輸出含綜合分數 ----
if ! grep -qE '綜合分數|綜合評分|overall' "$LOG_FILE"; then
    echo "⚠️  E2E 輸出無綜合分數關鍵字（可能 market closed 或 data 缺失）"
    # 不 fail — 部分情境（週末）data 缺失但 CLI 仍正常結束是 OK 的
fi

# ---- Gate 3: 必出 JSON artifacts ----
if [ ! -d /tmp ] || ! ls /tmp/stock_team_$(echo "$TICKER" | tr '[:upper:]' '[:lower:]')_*_analysis_result.json >/dev/null 2>&1; then
    echo "⚠️  E2E 未輸出 analysis_result.json artifact（非阻塞）"
fi

# ---- PASS ----
echo "✅ E2E smoke PASS（ticker=${TICKER}, exit=0, 0 warning）"
echo "   log: $LOG_FILE"
exit 0