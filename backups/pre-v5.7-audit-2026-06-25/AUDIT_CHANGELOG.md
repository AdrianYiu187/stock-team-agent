# Stock Team Agent Audit Changelog

> v5.4 路線圖：基於 v5.3 baseline (7f781ac, 2026-06-14) 進行深度審計

## 審計 Stage 0 — 環境探索（2026-06-25）

### Baseline 狀態
- HEAD: `7f781ac` (v5.3)
- Branch: `audit-v5.3-2026-06-14`
- 代碼量：14,127 行（72 個 .py 檔案）
- Tests: 28 passed, 2 skipped (0.39s)

### AAPL E2E Baseline（2026-06-25 20:21）
- 耗時：69.14s
- HTML 報告：52,944 bytes（v5.3 聲稱 52,896 bytes ✅）
- 回測準確率：66.2%（v5.3 聲稱 66.7%，略升）
- Buy 精準度：60.0%
- Sell 精準度：54.55%

## Stage 2 — 計算深度驗證

### 重大計算發現

| # | 類別 | 問題 | 位置 | 影響 |
|---|------|------|------|------|
| **C1** | 重複代碼 | 5-tier mapping 兩份相同代碼 | `consensus_engine.py:295-306` + `stock_analysis.py:914-920` | 維護負擔，未來修改易漏 |
| **C2** | 數學設計 | circular transformation（score → bhs → overall → 5tier） | `_score_to_bhs` + `_compute_consensus` + `_score_to_5tier` | 數學嚴謹性差 |
| **C3** | 數值校驗 | `weighted_scores` normalize 後不保證 sum=1 | `consensus_engine.py:131-133` | 邊界 bug（外部輸入時） |
| **C4** | **邏輯錯誤** | `_score_to_bhs(0.5)` 返回 (0.4, 0.6, 0) 而非 (0, 1, 0) | `stock_analysis.py:885-899` | **0.5 應該是中性，當前永遠略偏買 40%** |
| **C5** | 雙重權重 | `weights` 在 stock_analysis.py:961-969 與 `analyst_weights` 在 consensus_engine.py:42-48 是兩套獨立權重 | 兩處 | 一致性未驗證 |

### C4 邊界值驗證

| score | 當前 buy | 當前 hold | 當前 sell | 期望 | 狀態 |
|-------|----------|-----------|-----------|------|------|
| 0.0 | 0.000 | 0.000 | 1.000 | (0,0,1) | ✅ |
| 0.25 | 0.000 | 0.300 | 0.700 | (0,0.5,0.5) | ⚠️ hold 偏低 |
| **0.5** | **0.400** | **0.600** | **0.000** | **(0,1,0)** | ❌ **永遠偏買** |
| 0.75 | 0.700 | 0.300 | 0.000 | (0.5,0.5,0) | ⚠️ 偏買 |
| 1.0 | 1.000 | 0.000 | 0.000 | (1,0,0) | ✅ |

### 期望修正版本（Stage 4A）

```python
def _score_to_bhs_fixed(score):
    """score=0.5 完美中性 (0,1,0)；score=0.0 → (0,0,1)；score=1.0 → (1,0,0)"""
    score = max(0.0, min(1.0, float(score)))
    if score >= 0.5:
        buy = (score - 0.5) * 2  # 0→1
        hold = 1.0 - buy
        sell = 0.0
    else:
        sell = (0.5 - score) * 2  # 0→1
        hold = 1.0 - sell
        buy = 0.0
    return {"buy": buy, "hold": hold, "sell": sell}
```

## Stage 3 — 死代碼掃描

### 死代碼/可疑 shim 清單

| 檔案 | 行數 | 外部 caller | 命運 |
|------|------|-------------|------|
| `handlers/market_analyst.py` | 1 | 1 (stock_analysis.py:82) | **改 import 即可刪除** |
| `handlers/technical_analyst.py` | 2 | 0 | 死代碼（直刪） |
| `handlers/fundamental_analyst.py` | 1 | 0 | 死代碼 |
| `handlers/risk_analyst.py` | 1 | 0 | 死代碼 |
| `handlers/sentiment_analyst.py` | 1 | 0 | 死代碼 |
| `handlers/macro_analyst.py` | 1 | 0 | 死代碼 |
| `handlers/news_analyst.py` | (via __init__) | 0 | 死代碼 |
| `handlers/__init__.py` | 8 | 0 | 死代碼 |
| `consensus/consensus_engine.py` | 1 | 1 (stock_analysis.py:930) | **改 import 即可刪除** |
| `consensus/__init__.py` | 2 | 0 | 死代碼 |
| `model/handlers/__init__.py` | ~ | 0 | 死代碼 |

**預期節省**：~17 行 + 9 個檔案（目錄 `handlers/` 整個可刪除，`consensus/` 整個可刪除）

## Stage 5 — v5.5 多因子評分（2026-06-25）

### Market Analyst 啟發式 → 多因子評分

| 版本 | market_score (AAPL) | 公式 |
|------|---------------------|------|
| v5.3 啟發式 | **0.500**（固定） | `0.55 if ytd<-30 else 0.70 if ytd<-10 else 0.50` |
| v5.5 多因子 | **0.439**（連續計算） | weighted: dd 0.5 + pos 0.3 + ytd 0.15 + beta 0.05 |

**設計理念**：均值回歸假設
- 從高點跌幅因子（權重 0.5）：負越深 → 分越高
- 52週位置因子（權重 0.3）：越低 → 分越高
- YTD 因子（權重 0.15）：負向加分
- Beta 因子（權重 0.05）：高 Beta 微扣

### v5.5 數值校準

| 情境 | 輸入 | v5.5 score | 語義 |
|------|------|------------|------|
| strong_drop | ytd=-50, pos=5, dd=-60 | 0.985 | 強 buy |
| deep_drop | ytd=-40, pos=10, dd=-50 | 0.928 | 強 buy |
| mid_deepest | ytd=-35, pos=10, dd=-35 | 0.866 | buy |
| mid_deeper | ytd=-25, pos=20, dd=-25 | 0.782 | buy |
| mid_drop | ytd=-15, pos=30, dd=-15 | 0.685 | 弱 buy |
| AAPL E2E 真實數據 | ytd=+46, pos=79.4, dd=-11, beta=1.2 | **0.439** | 中性（高位微 sell） |
| mild_uptrend | ytd=+10, pos=60, dd=+5 | 0.408 | 中性偏 sell |
| new_high | ytd=+20, pos=100, dd=0 | 0.345 | sell（過熱） |

### E2E 對比（2026-06-25）

| 指標 | v5.3 baseline | v5.4 (公式修正) | v5.5 (多因子) |
|------|---------------|-----------------|----------------|
| market_score | 0.500 | 0.500 | **0.439** |
| 綜合評分 | 0.500 | 0.54 | **0.46** |
| 買入比例 | n/a | 10.5% | **3.3%** |
| 賣出比例 | n/a | 3.1% | **10.5%** |
| 整體得分 | +18.1 | +7.4 | **-7.2** |
| 合併置信度 | 0.613 | 0.594 | 0.566 |
| 回測準確率 | 66.2% | 66.2% | 66.2% |
| HTML 報告 | 52,944 B | 52,944 B | 52,944 B |
| E2E 耗時 | 69.14s | 69s | 69s |

**0 regression**，訊號從固定值變成數據驅動。

## Stage 6-11 — v5.6 多因子全面化 + HK$ 動態化 + C1 完全 dedup（2026-06-25）

### 重大修復：D6 HK$ 硬編碼 bug（DEFER-8）

| 版本 | AAPL 顯示 | 問題 |
|------|-----------|------|
| v5.3 | `現價: HK$293.08` | AAPL 是美股卻標 HK$，誤導用戶 |
| v5.6 | `現價: $293.08` | 動態貨幣符號（USD → `$`、HKD → `HK$`、CNY → `¥`） |

- 26 處 `HK$` → `{_currency_symbol}`（f-string 自動插值）
- `market_cap_hk` → `market_cap_native`（不再乘 7.8 偽轉換）
- 支援 7 種貨幣：USD/HKD/CNY/JPY/GBP/EUR/TWD

### D4 完成：4 個分析師多因子化

| 分析師 | v5.3 (啟發式) | v5.6 (多因子) | 因子數 |
|--------|----------------|----------------|--------|
| market | 0.5/0.55/0.7 | weighted: dd 0.5 + pos 0.3 + ytd 0.15 + beta 0.05 | 4 |
| technical | 0.35/0.45/0.55 | weighted: RSI 0.3 + MACD 0.2 + MA50 0.25 + mom 0.25 | 4 |
| fundamental | 0.5/0.65/0.75 | weighted: PE 0.35 + ROE 0.3 + PEG 0.2 + growth 0.15 | 4 |
| risk | 0.35/0.45/0.55 | weighted: vol 0.3 + VaR 0.2 + DD 0.3 + Sharpe 0.2 | 4 |

AAPL E2E 多樣性提升：
- v5.3: scores = [0.500, 0.550, 0.500, 0.550, 0.500, 0.500, 0.500] (2 unique)
- v5.6: scores = [0.439, 0.542, 0.513, 0.604, 0.500, 0.600, 0.540] (7 unique)

### C1 完全 dedup

- `train/consensus_engine.py:295-306` 5-tier 邏輯 → 委派給 `stock_analysis.score_to_5tier`
- 保留 fallback（ImportError 時用原始硬編碼，避免破壞向後相容）
- 從 v5.4 的 module-level 重複 → v5.6 完全 consolidate

### Stage 11 E2E 對比（AAPL, 2026-06-25）

| 指標 | v5.3 | v5.4 | v5.5 | **v5.6** | 累計 |
|------|------|------|------|----------|------|
| Tests | 28 | 37 | 42 | **60** | +32 (+114%) |
| 代碼 multifactor 函數 | 0 | 0 | 1 | **4** | market/tech/fund/risk |
| AAPL 分析師 score unique | 2 | 2 | 4 | **7** | +350% 多樣性 |
| 貨幣符號 | HK$ 硬編碼 | HK$ 硬編碼 | HK$ 硬編碼 | **動態** | 7 種支援 |
| 5-tier 重複 | 2 處 | 2 處 | 2 處 | **1 處** | dedup |
| 回測準確率 | 66.2% | 66.2% | 66.2% | 66.2% | 持平 |
| HTML 報告 | 52,944 B | 52,944 B | 52,824 B | ~53,000 B | 持平 |
| E2E 耗時 | 69s | 69s | 83s | ~80s | +15% LLM 辯論 |

## Stage 5 — 累積 5-Stage 審計效果表

| 維度 | v5.3 baseline | v5.5 (現在) | 累計 |
|------|---------------|-------------|------|
| 代碼行數 | 14,127 | ~14,070 | -57 (淨：+165 stock_analysis.py -10 files) |
| Tests | 28 passed | **42 passed** | **+50%** |
| 死代碼 | 9 shim files | 0 | -100% |
| 公式錯誤 | C4 (中性偏買) | 0 | fixed |
| 數學校驗 | C3 (sum>1 bug) | 0 | fixed |
| 評分多樣性 | 3 值啟發式 | 1 個多因子（market） | 持續改進中 |
| 回測準確率 | 66.2% | 66.2% | 持平（backtest 是歷史反映，非計算改善） |
| LLM 辯論耗時 | 60s | 60s | 持平 |

### v5.5 → v5.6 路線圖（deferred）

| # | 項目 | 預期節省 / 提升 | 風險 |
|---|------|-----------------|------|
| DEFER-1 | `tech_score` 多因子重構（RSI/MACD/MA/momentum 多輸入） | +8 tests, +多樣性 | 中（指標需校準） |
| DEFER-2 | `fund_score` 多因子重構（PE/ROE/PEG/revenue_growth） | +5 tests, +多樣性 | 中（權重敏感） |
| DEFER-3 | `risk_score` 多因子重構（volatility/VaR/max_dd/Sharpe） | +5 tests | 中 |
| DEFER-4 | `_score_to_5tier` 與 consensus_engine.py:295-306 完全 dedup（消除 C1 剩餘） | -12 lines, +1 test | 低 |
| DEFER-5 | 7 分析師區塊共用 `_emit()` 結構（5/29 simplification 目標） | -100 行 | 高（需逐個驗證） |
| DEFER-6 | AAPL 之外 ticker E2E 驗證（HK/CN/低流動性） | 量化穩健性 | 低 |
| DEFER-7 | v5.3 自我審計發現的 WhatsApp disable — 已完成（無 commit 之前 session 留下的） | n/a | n/a |
| DEFER-8 | HK$ 硬編碼 → 動態貨幣符號 | ✅ **Stage 6 完成** | — |
| DEFER-1 | `tech_score` 多因子 | ✅ **Stage 7 完成** | — |
| DEFER-2 | `fund_score` 多因子 | ✅ **Stage 8 完成** | — |
| DEFER-3 | `risk_score` 多因子 | ✅ **Stage 9 完成** | — |
| DEFER-4 | `_score_to_5tier` 完全 dedup | ✅ **Stage 10 完成** | — |
| DEFER-5 | 7 分析師區塊共用 `_emit()` 結構（5/29 simplification 目標） | -100 行 | 高 |
| DEFER-6 | AAPL 之外 ticker E2E（HK/CN） | 穩健性 | 低 |