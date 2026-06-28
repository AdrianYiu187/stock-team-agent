# Stock Team Agent 簡化方法論（2026-05-29）

## 本次簡化結果

| 檔案 | 簡化前 | 簡化後 | 節省 |
|------|--------|--------|------|
| `stock_analysis.py` | 1257 行 | 1115 行 | 142 行 |
| `workflow_engine.py` | 358 行 | 刪除 | 358 行 |
| `trigger.py` | 347 行 | 刪除 | 347 行 |
| 6 個 handlers stub | ~8 行 | 刪除 | ~8 行 |
| 之前審計刪除的4個檔案 | 744 行 | 刪除 | 744 行 |
| **總計** | | | **~1,599 行** |

## 步驟執行順序（逐步驗證）

```
Step 1: 刪除 6 個 handlers stub（零風險）
Step 2: 刪除 workflow_engine.py（358行死代碼）
Step 3: 刪除 trigger.py（347行死代碼）
Step 4: 重構 stock_analysis.py 分析師區塊（-142行）
Step 5: 消除 analyst_sections → _analyst_text 雙重寫入（隨Step4完成）
Step 6: 清理 _result 過度嵌套（修改HTML生成器+nested accessor）
```

## 核心發現

### 架構：真正生產入口只有一個

`stock_analysis.py`（1115行）是唯一生產入口。所有其他模組皆為此腳本的子模組。

### 死代碼識別方法

1. **搜索所有 import**：找到模組的所有引用位置
2. **確認生產 vs 測試**：只被 `stock_health_check.py`（健康檢查腳本）引用 = 生產未使用
3. **驗證生產入口**：確保主入口語法正常

### 分析師區塊重構模式

7個幾乎相同的分析師塊（約350行）→ 泛型 `_emit()` 函數 + 配置驅動（~50行）

```python
# 重構前：每個角色重複 ~50 行代碼 × 7 次
# 重構後：
def _emit(role, display, ds_lines, argument, evidence, conclusion, score, signal, confidence):
    """通用分析師報告輸出"""
    _add_report_line(f"【{display}】")
    _add_report_line("-" * 80)
    for ln in ds_lines:
        _add_report_line(ln)
    _add_report_line(...)
    _analyst_text[role] = {...}

# 每個角色變成一次 _emit() 調用
_emit("market", "市場數據分析師 (Market Analyst)", [...], argument, evidence, conclusion, ...)
_emit("technical", "技術分析師 (Technical Analyst)", [...], argument, evidence, conclusion, ...)
```

### 嵌套結構清理原則

HTML 生成器 (`stock_html_report.py`) 直接依賴 top-level 字段（`data.get("rsi")` 等）。清理嵌套需要：

1. 先修改 HTML 生成器，改用 nested accessor（如 `tech.get("rsi", data.get("rsi", 50))`）
2. 再移除 `stock_analysis.py` 中的 top-level 重複字段

## 備份位置

所有刪除的檔案已備份至：
`~/.hermes/backups/stock-team-agent-20260529_155250/`

包含：
- `workflow_engine.py` (358行)
- `trigger.py` (347行)
- 6 個 handlers stub
- `stock_analysis.py.orig` (原始1257行)
- `stock_html_report.py.orig` (HTML生成器修改前)

## 未來簡化方向

### 高價值目標（stock_analysis.py 內部）

| 問題 | 節省潛力 | 風險 |
|------|---------|------|
| 報告輸出冗餘（7角色×3次重複輸出） | ~100行 | 低 |
| WhatsApp nested function（可外置） | ~20行 | 中 |
| 結果字典過度嵌套 | 已完成 | — |

### 已確認安全的模組

| 模組 | 行數 | 狀態 |
|------|------|------|
| `analyst_tracker.py` | 659 | ✅ 生產使用 |
| `backtest_engine.py` | 473 | ✅ 生產使用 |
| `phase_b_cron.py` | 167 | ✅ 獨立cron |
| `memory_phase_ab.py` | 304 | ✅ 獨立內存 |
| `stock_health_check.py` | 292 | ✅ 測試腳本 |

## 驗證命令

每次修改後必須執行：
```bash
cd ~/.hermes/skills/productivity/stock-team-agent/scripts
python3 -m py_compile stock_analysis.py
python3 -m py_compile generate/stock_html_report.py
```

完整功能驗證（需要MiniMax API key）：
```bash
python3 stock_analysis.py -c AAPL -n "Apple Inc"
```
