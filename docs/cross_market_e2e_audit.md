# cross_market_real_yfinance_e2e.py 審計報告

**日期**：2026-06-28
**範圍**：`scripts/cross_market_real_yfinance_e2e.py` (185 行) + `scripts/tests/test_cross_market_real_yfinance_e2e.py` (183 行) + `scripts/tests/fixtures/tickers_fundamentals.json`

---

## 1. 結構總覽

### 1.1 主腳本 (`cross_market_real_yfinance_e2e.py`)

| 函數 | 行數 | 職責 |
|------|------|------|
| `_load_module(label, path)` | L48-55 | 動態載入 v5.10 vs v5.11 stock_analysis 模組（隔離 import） |
| `_ensure_v510_baseline()` | L57-62 | 確保 v5.10 baseline commit `0f30069` 已 git checkout |
| `score_ticker(fund_fn, t, f)` | L64-73 | 對單 ticker 呼叫 fund_score_multifactor |
| `score_tickers(fund_fn, fundamentals)` | L75-88 | 對多 ticker 批次評分 |
| `fetch_fundamentals(tickers)` | L91-104 | **真實 yfinance fetch**（延遲 import，避免 pytest 觸網） |
| `quantize_cross_market(v510, v511)` | L107-123 | 計算 std 量化 |
| `main()` | L126-185 | CLI 入口（一次性拉 yfinance + 寫 fixtures） |

### 1.2 pytest (17 條)

```
test_01_fixtures_exist
test_02_fixtures_has_3_tickers
test_03_fixtures_has_fundamentals
test_04_v510_scores_computed
test_05_v5113_scores_computed
test_06_std_v510_ge_v5113
test_07_quantize_function_idempotent
test_08_all_6_scores_in_unit_interval
test_09_interpretation_keyword_present
test_10_v510_has_3_distinct_tickers
test_11_v5113_has_3_distinct_tickers
test_12_fixtures_meta_source
test_13_fixtures_meta_v510_baseline
test_14_fixtures_meta_v5113_source
test_15_std_delta_stored
test_16_v510_v5113_scores_match_fixtures
test_17_recompute_std_matches_fixtures
```

**結果**：17/17 PASS（0.02s）。

---

## 2. 數據真實性

### 2.1 真實 yfinance 數據（fixtures）

| Ticker | 市場 | PE | ROE | PEG | Growth | v5.10 score | v5.11.3 score |
|--------|------|----|----|-----|--------|-------------|---------------|
| AAPL | US | 33.35 | 141.47% | 2.37 | 16.6% | 0.5197 | 0.5892 |
| 0700.HK | HK | 14.76 | 20.52% | 1.28 | 9.1% | 0.7238 | 0.5426 |
| 600519.SS | CN | 17.69 | 31.20% | 1.65 | 6.5% | 0.7019 | 0.5357 |

**Std**: v5.10 = 0.112, v5.11.3 = 0.0291, Δ = -0.083（cap 飽和幻覺消失，非 regression）

**來源**：commit `7f9ff53 audit run`（fixtures `_meta.source`）

### 2.2 真實度評估

- ✅ **E2E 測試覆蓋 3 大市場**：US (AAPL), HK (騰訊), CN (茅台)
- ✅ **數據真實**：fixture 來自真實 yfinance `.info` API（非 mock）
- ⚠ **數據時效性**：fixtures 來自 `7f9ff53` commit，需要確認日期（v5.10 baseline 0f30069 之前）
- ⚠ **樣本數小**：只有 3 ticker，無 std 置信區間

---

## 3. 死代碼 / 硬編碼 / 計算深度審計

### 3.1 死代碼

- ✅ 無死代碼（所有函數都被 main 或 pytest 使用）
- ✅ `_load_module` 是雙模組隔離 import 必要機制

### 3.2 硬編碼

| 位置 | 硬編碼 | 建議 |
|------|--------|------|
| L132 | `tickers = ["AAPL", "0700.HK", "600519.SS"]` | 改為 CLI arg 或 env var |
| L99-103 | yfinance `.info` 欄位名 `trailingPE`, `returnOnEquity`, etc. | 可接受（API 契約穩定）|
| L161 | fixtures 檔名 `tickers_fundamentals.json` | 可接受（單一檔案） |

### 3.3 計算正確性

| 計算 | 公式 | 驗證 |
|------|------|------|
| `score_ticker` | 直接呼叫 `fund_score_multifactor` | ✅ pytest test_16/17 驗證 |
| `quantize_cross_market` | `statistics.stdev(s)` | ✅ pytest test_06/17 驗證 |
| `_ensure_v510_baseline` | `git checkout 0f30069 -- scripts/stock_analysis.py` | ⚠ 副作用：污染 working tree |

### 3.4 準確率風險

- ⚠ **樣本數 = 3**：std 統計量對 3 點極不穩定（單 ticker score 漂移 0.01 → std 變 0.005）
- ⚠ **沒跑多 ticker 子集 bootstrap 驗證**
- ⚠ **沒跑時效性回測**（AAPL PE 在 2020 牛市 vs 2022 熊市差異巨大）

---

## 4. 問題清單（Rule 6 攤開給用戶決策）

### P45 — fixtures 時效性
- 問題：fixtures 來自 commit `7f9ff53`，可能過時
- 影響：pytest 守住的 score 期望值可能反映舊數據
- 修法：定期 `python scripts/cross_market_real_yfinance_e2e.py` 刷新 fixtures

### P46 — 樣本數太小
- 問題：3 ticker 無法做置信區間
- 修法：擴展 tickers 列表到 10-20 個（含 US/HK/CN 各 3-7 個）

### P47 — `_ensure_v510_baseline` 副作用
- 問題：`git checkout` 污染 working tree
- 修法：用 `git worktree` 隔離 baseline 載入

### P48 — 沒價格/技術面 E2E
- 問題：只測 fund_score，沒測 market/tech/risk 跨市場
- 修法：擴展 E2E 到 4 個 score（market/tech/risk/fund）

---

## 5. 結論

| 面向 | 評分 |
|------|------|
| **pytest 覆蓋** | 17/17 ✓ |
| **數據真實性** | ✓ 真實 yfinance |
| **死代碼** | ✓ 無 |
| **硬編碼** | 1 處（tickers 列表） |
| **計算正確性** | ✓ 有 pytest guard |
| **樣本充足性** | ⚠ N=3 過小 |
| **時效性** | ⚠ fixtures 需刷新 |
| **E2E 完整性** | ⚠ 只測 fund_score |

**整體評估**：**B+ 等級**（pytest 完整、數據真實、無 dead code，但樣本小 + 時效性需監控 + 只測 fund_score）

**v5.15 路線圖第二項建議**：
1. 先解決 P45（刷新 fixtures 確認當前 PE/ROE）
2. 再處理 P46（擴展到 10-20 ticker）
3. P47（worktree 隔離）為 nice-to-have
4. P48（4 score 全 E2E）為 v5.16 候選
