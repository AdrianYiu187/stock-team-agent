# PR: audit-v5.3-2026-06-14 → main (v5.15 closure)

> **Branch**: `audit-v5.3-2026-06-14` → `main`
> **Commits**: 61 commits ahead of `main`
> **Tag**: `audit-v5.15-2026-06-28` (deref = HEAD)
> **Status**: ✅ Stage 9 verifier 13/13 PASS

## 摘要

本 PR 將 v5.3 → v5.15 的累積 audit 成果合併回 `main`。包含 **v5.14 P37-P40 線性化**、**v5.15 P43-P44 news cap 線性化**、**P45-P46 cross-market E2E 11 ticker 擴展**、**P47 score distribution metric**。

---

## Reviewer 重點檢查區段

### 🔴 HIGH PRIORITY — v5.14 P37-P40 線性化（改多個 scoring 函數數學）

| Commit | 改動 | 函數 | 數學改變 |
|--------|------|------|----------|
| `e64c704` | P37 | `market_score_multifactor` | `pos_52wk` 從 4-segment cap (0.7/0.55/0.5/1.0) → 連續線性（0→100 對應 0.3→0.9） |
| `1b18cbf` | P38 | `market_score_multifactor` | `from_high` 與 `ytd_return` cap 邊界線性化（[-200,-60] / [-200,-100] 從 hard cap → 線性延伸） |
| `dfcd08f` | P39 | `tech_score_multifactor` | RSI[0,5]、macd[2,5]、ma50[-10,0]、momentum[-100,-50] 4 個 cap 線性化 |
| `4ce9bc1` | P40 | `risk_score_multifactor` | `var_95[0,0.1]` 與 `max_dd[0,0.5]` cap 線性化 |

**建議至少 2 reviewer** 確認：
1. 線性公式的斜率/截距是否合理（特別 RSI、macd 邊界值）
2. cap zone 外的 fallback 是否仍保留（如 `ma50 ≤ 0 → 0.5` 作為數據錯誤保護）
3. 加權是否正確（market: dd 0.5 + pos 0.3 + ytd 0.15 + beta 0.05；tech: rsi 0.4 + macd 0.15 + ma50 0.2 + mom 0.25）

### 🟡 MEDIUM PRIORITY — v5.15 P43-P44 news cap 線性化

| Commit | 改動 | 函數 |
|--------|------|------|
| `fda7b1c` | P43+P44 | `news_score_multifactor` region/source cap 邊界從 ≥3/≥6 → ≥5/≥12 |

**量化改善**：region cap rate 50.1% → 16.0%，source cap rate 58.8% → 8.9%。

### 🟢 LOW PRIORITY — P45-P47 metric 與測試基礎設施

| Commit | 改動 |
|--------|------|
| `97316a7` | P45+P46: cross_market_real_yfinance_e2e.py 擴展到 11 ticker + freshness + error tolerance |
| `e667944` | P47: quantify_score_distribution.py 新 metric（mean delta / Wasserstein / entropy / std） |
| `729091d` | verify_v515_closure.py Stage 9 verifier |

---

## 量化資產

### 真實 cap flatline 改善

| 階段 | 數量 | cap rate |
|------|------|----------|
| v5.13 P36c baseline | **14 / 16 (87.5%)** | 嚴重飽和 |
| v5.14 + v5.15 修復後 | **2 / 16 (12.5%)** | market beta 56.6% + tech ma50 fallback（故意保留） |

### news cap 量化

| Metric | v5.12 P33 baseline | v5.15 P43+P44 | 改善 |
|--------|---------------------|----------------|------|
| region cap rate | 50.1% | **16.0%** | -34.1pp |
| source cap rate | 58.8% | **8.9%** | -49.9pp |

### Cross-market E2E 覆蓋

| 階段 | Tickers | 覆蓋 market |
|------|---------|-------------|
| v5.10 baseline | 3 | US/HK/CN 各 1 |
| **v5.15 P45+P46** | **11** | US 4 + HK 3 + CN 4 |

### Score distribution (P47)

| Metric | v5.13 vs v5.14 | 詮釋 |
|--------|----------------|------|
| Mean delta | -0.0064 | 幾乎無差異 |
| Wasserstein distance | 0.0064 | 分布位移極小 |
| **Entropy delta** | **-0.0139 bits** | v5.14 略更集中 |
| Std delta | -0.0006 | 變化可忽略 |

> ⚠️ **重要**：cap 修復對 score **distribution** 影響極小（Wasserstein 0.0064），但對 **訊號分布**（buy/hold/sell）有顯著改善（99% hold → 26% buy on AAPL mock GBM）。P48 將量化多 ticker 訊號分布。

---

## 測試

- ✅ pytest **271 passed** (0 regression)
- ✅ Stage 9 verifier **13/13 PASS**
- ✅ AUDIT_CHANGELOG v5.15 段 9 hash refs

---

## 建議合併策略

1. **Squash merge**（推薦）：61 commits → 1 squash commit on main，message 為本 PR 標題
2. **Merge commit**：保留 audit branch 歷史（適合長期追蹤 v5.x 演進）
3. **Rebase**：需協商 rebase strategy（本分支 61 commits 較大）

---

## 風險評估

| 風險 | 嚴重度 | 緩解 |
|------|--------|------|
| Scoring 函數數學改變影響 production | 🔴 HIGH | Stage 9 verifier 守住；建議 shadow deploy 1 週 |
| Cross-market E2E 11 ticker yfinance rate limit | 🟡 MED | 已加 per-ticker try/except + 失敗容忍 |
| Fixtures 過時（> 90 days） | 🟢 LOW | 已加 `fetched_at` + `_meta.fetched_at` freshness check |
| 動態權重 vs 等權重 metric 差異 | 🟢 LOW | P48 將量化真實動態權重結果 |

---

## 下一步（v5.16+ 候選）

- **P48 random baseline + 訊號分布 metric** — 量化 buy/hold/sell 比例 + entropy，確認 99% hold → 26% buy 在多 ticker 上也成立
- **weight tuning** — `quantify_score_distribution.py` 改用 `weighted_score_with_variance_penalty` 真實動態權重
- **merge to main** — 本 PR 批准後合併

---

**Generated**: 2026-06-28 by Stock Team Agent audit-v5.15 closure
