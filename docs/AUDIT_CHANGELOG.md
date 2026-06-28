# Stock Team Agent — Audit Chain Changelog

> 所有 audit chain 重要 commit + verifier 結果的單一 source of truth。
> 維護者：audit-v5.3-2026-06-14 branch
> 每次 closure commit 必須更新對應版本段。

---

## v5.15（2026-06-28 closure）

**Branch HEAD**: `8fecbc5`  
**Tag**: `audit-v5.15-2026-06-28`  
**Commits ahead of origin**: 33

### Chain

| Commit | Description |
|--------|-------------|
| `8fecbc5` | feat(v5.15 closure verifier): Stage 9 health check script |
| `97316a7` | feat(v5.15 P45+P46): cross_market_e2e 擴展到 11 ticker + freshness + sample_size |
| `dde0a54` | fix(v5.14 P38 follow-up): make P37 pos_contribution dynamic base |
| `ea333a5` | docs(v5.14 closure): AUDIT_CHANGELOG v5.14 4-pitfall 收尾段 |
| `4ce9bc1` | feat(v5.14 P40): risk_score_multifactor var_95 + max_dd 線性化 |
| `dfcd08f` | feat(v5.14 P39): tech_score_multifactor RSI/macd/momentum 線性化 |
| `1b18cbf` | feat(v5.14 P38): market_score_multifactor from_high + ytd 邊界線性化 |
| `e64c704` | feat(v5.14 P37): market_score_multifactor pos_52wk 連續線性化 |
| `31bd636` | feat(Stage 0): 量化腳本 + 14 pitfall roadmap |

### v5.15 Pitfall 修復摘要

| ID | Pitfall | 量化結果 |
|----|---------|---------|
| **P41** | sentiment news_count ≥120 cap | 0.0% flat（罕見） |
| **P42** | news news_count ≥120 cap | 15.2% flat |
| **P43** | news region_count ≥3 cap | 50.1% → **16.0%** (-34.1pp) |
| **P44** | news source_diversity ≥6 cap | 58.8% → **8.9%** (-49.9pp) |
| **P45** | cross_market fixtures freshness + error tolerance | < 90 days check + per-ticker try/except |
| **P46** | cross_market TICKER_UNIVERSE 3 → 11 ticker | sample_size 11（US 4 + HK 3 + CN 4） |

### 量化指標（Stage 9 verifier 9/9 PASS）

| 指標 | 值 | 目標 |
|------|----|------|
| pytest | **260 passed** | ≥ 251 ✓ |
| 真實 cap flatlines | **2/16** | ≤ 2 ✓ |
| Cross-market sample_size | **11** | ≥ 10 ✓ |
| News region cap rate | **16.0%** | < 20% ✓ |
| News source cap rate | **8.9%** | < 10% ✓ |
| Fixtures freshness | **0 days** | < 90 ✓ |
| Working tree | clean | clean ✓ |
| HEAD = tag deref | `8fecbc5` = tag | equal ✓ |

### Directional accuracy 真相揭露（v5.14 backtest）

- v5.13 P36c baseline: **56.18%**
- v5.14 P37-P40 fix: **56.97%** (+0.80pp)
- Buy-only baseline: **56.97%** (= v5.14 actual)
- Random score baseline: **28.69%**

**結論**：directional_accuracy 不是 cap 修復的好 metric（在 bias 市場 ≈ buy-only baseline）。  
**真實 cap 修復價值**：訊號分布從 99% hold → 26% buy (+25.5pp 真實 buy 訊號恢復)。

---

## v5.14（2026-06-27 closure）

**Branch HEAD (at closure)**: `dde0a54`  
**Tag**: `audit-v5.14-2026-06-28`（待合併時 force-update）

### Chain

| Commit | Description |
|--------|-------------|
| `dde0a54` | fix(P38 follow-up): dynamic pos_contribution base (meta-fix) |
| `ea333a5` | docs: closure AUDIT_CHANGELOG v5.14 4-pitfall 收尾段 |
| `4ce9bc1` | feat(P40): risk_score_multifactor var_95 + max_dd 線性化 |
| `dfcd08f` | feat(P39): tech_score_multifactor RSI/macd/momentum 線性化 |
| `1b18cbf` | feat(P38): market_score_multifactor from_high + ytd 邊界線性化 |
| `e64c704` | feat(P37): market_score_multifactor pos_52wk 連續線性化 |
| `31bd636` | feat(Stage 0): 量化腳本 + 14 pitfall roadmap |

### v5.14 Pitfall 修復摘要

| ID | Pitfall | 量化結果 |
|----|---------|---------|
| **P37** | market pos_52wk 4-segment cap | 84% → 5% flat zone |
| **P38** | market from_high + ytd 邊界 cap | 12% → 5% flat zone |
| **P39** | tech RSI/macd/ma50/momentum cap | 33% → 5% flat zone |
| **P40** | risk var_95 + max_dd cap | 19% → 5% flat zone |

### 保留 cap（故意設計）

- `market beta <= 1.2 → 1.0`（低風險邊界罕見）
- `tech ma50 <= 0 → 0.5 fallback`（除零保護）

### 量化指標

| 指標 | v5.13 | v5.14 | 改善 |
|------|-------|-------|------|
| pytest | 200 | 241 | +41 |
| 真實 cap flatlines | 14/16 | **2/16** | -12 |
---

## v5.16（2026-06-29 真實數據整合）

**Branch HEAD**: `2095bee`  
**Main HEAD**: `a7d64b2` → `2095bee` (merge commit 為 65-commit squash)  
**Tag**: `audit-v5.15-2026-06-28` (保留，指向 squash merge)  
**Commits since v5.15 merge**: 1（v5.16 P49+P50）

### Chain（merge 到 main 之後）

| Commit | Description |
|--------|-------------|
| `2095bee` | feat(v5.16 P49+P50): real sentiment/macro + per-ticker signal distribution |
| `a7d64b2` | feat(v5.15 merge): consolidate 65 commits (v5.2 → v5.15 P48b) into main |
| `aa0b05a` | perf+cleanup(v5.2): parallel IO (3.4x) + dead code removal (705 lines) + HTML math consensus |

### v5.16 新增

**P49 — 真實 sentiment + macro 派生**
- `scripts/derive_real_sentiment_macro.py`（340 行, CLI+library）
  - 從 yfinance 拉 sentiment（news keyword count，中英文關鍵字）
  - 從 yfinance 拉 macro（market index 30d return + 波動率）
  - ticker → macro index 映射（US ^GSPC / HK ^HSI / CN SSE/SZSE）
  - 11/11 ticker 成功（HK macro 0.323 最弱，US 0.463 中性，CN 0.454-0.514 中性）
- `scripts/quantify_score_distribution.py` 新增 `--use-real-sentiment-macro` 旗標
- AAPL 實測 analyst_disagreement: 0.1107 → 0.1158 (+4.6%)
- 證明中性 0.5 基線遮蔽真實 macro 環境對 analyst disagreement 的影響

**P50 — 真實 per-ticker signal distribution**
- `scripts/cross_market_real_yfinance_e2e.py` 新增 `compute_signal_distribution_per_ticker`
- 用 v5.14 真實 `weighted_score_with_variance_penalty` + `dynamic_weights_for_ticker`
- 算每 ticker buy/hold/sell ratio + signal_entropy + majority + final_score + components
- fixtures 從 5 role → 7 role（加 sentiment + macro + signal_distribution_per_ticker）

**真實 11 ticker signal distribution（推翻 mock GBM 結論）**：

| Ticker | Region | Final | Buy% | Hold% | Sell% | Majority |
|--------|--------|-------|------|-------|-------|----------|
| AAPL | US | 0.5175 | 38.15% | 30.92% | 30.92% | **buy** |
| MSFT | US | 0.5100 | 36.06% | 31.97% | 31.97% | buy |
| GOOGL | US | 0.5092 | 35.84% | 32.08% | 32.08% | buy |
| NVDA | US | 0.5289 | 41.43% | 29.29% | 29.29% | buy |
| 0700.HK | HK | 0.4896 | 31.91% | 31.91% | **36.17%** | **sell** |
| 9988.HK | HK | 0.4935 | 32.46% | 32.46% | **35.08%** | **sell** |
| 3690.HK | HK | 0.4523 | **26.51%** | 26.51% | **46.99%** | **sell** |
| 600519.SS | CN | 0.5034 | 34.24% | 32.88% | 32.88% | buy |
| 000858.SZ | CN | 0.5119 | 36.57% | 31.72% | 31.72% | buy |
| 601318.SS | CN | 0.5115 | 36.46% | 31.77% | 31.77% | buy |
| 000333.SZ | CN | 0.4971 | 32.95% | 32.95% | **34.11%** | **sell** |

**Region-level 結論**：
- US 4/4 = buy（科技牛市偏買）
- HK 3/3 = sell（2025-2026 恒指弱勢 → 真實反映）
- CN 2 buy + 1 sell（mixed，600519/000858/601318 偏買，000333 偏賣）

### 量化指標（Stage 9 verifier 15/15 PASS）

| 指標 | 值 | 目標 |
|------|----|------|
| pytest | **317 passed** | ≥ 251 ✓ |
| 真實 cap flatlines | **2/16** | ≤ 2 ✓ |
| Cross-market sample_size | **11** | ≥ 10 ✓ |
| News region cap rate | **16.0%** | < 20% ✓ |
| News source cap rate | **8.9%** | < 10% ✓ |
| Fixtures freshness | **0 days** | < 90 ✓ |
| Wasserstein distance | **0.0064** | < 0.05 ✓ |
| Signal entropy delta (P48b mock) | **0.0741** | > 0 ✓ |
| Sell ratio v5.14 (P48b mock) | **0.9%** | > 0 ✓ |
| Per-ticker signal entropy (P50 real) | **1.5275 ~ 1.5848** | near log2(3) ✓ |
| Working tree | clean | clean ✓ |

### 死代碼/簡化（v5.16）
- 移除 main HEAD 的 75 個 `__pycache__/*.pyc` tracked files（commit `a7d64b2` amend）
- 移除 v5.15 chain 的 11 個 empty dirs（schemas/charts/consensus/github_integration/handlers/indicators/schemas/task_router/utils/valuation/handlers/valuation/handlers/handlers/handlers/handlers/handlers/handlers/handlers）

### 與 mock GBM 結論的差異（Rule 11 大聲修正）

| 結論 | Mock GBM (P48b) | 真實 11 ticker (P50) |
|------|-----------------|----------------------|
| 整體 majority | buy (100%) | US buy / HK sell / CN mixed |
| 整體 entropy | 0.0741 | 1.5275 ~ 1.5848（接近 log2(3) 上限）|
| sell 訊號 | 0.9% | **34-47%（HK）, 0%（US）** |
| 訊號分布均勻度 | 不均（buy-dominant） | 接近均勻（entropy 接近上限） |

**結論**：P48b mock GBM 結論「buy-dominant」是 mock 設計的 bias，**真實 11 ticker 數據顯示訊號分布接近 3-class 均勻**（除 HK 整體偏賣）。cap 修復的真實下游價值在「讓真實市場分歧（US buy / HK sell）浮現」，而非改變 buy/sell 比例的絕對值。
---

## v5.17 — HK Macro & 0700.HK PE 真實數據驗證（2026-06-29）

### Task A: HK macro 0.323 合理性驗證
- **HSI 30d 真實數據（2026-05-26 → 2026-06-26）**：
  - start = 26388.44, end = 22671.86, **ret_30d = -14.08%**
  - daily_vol = 1.09%, **annualized_vol = 17.27%**
  - |ret|/ann_vol = 0.8157, log1p(0.8157) = 0.5965
- **公式驗算**：`macro = 0.5 + 0.3 * (-1) * min(log1p(0.8157), 1.0) = 0.5 - 0.3*0.5965 = 0.3211`
- **fixture 輸出 0.323**，diff 0.002（close 浮點誤差內）→ **完全合理** ✅
- **解讀**：HSI 30d 跌 14% 但波動率 17%（年化），跌幅 ≈ 0.82 個年化波動 → 中度偏負面，宏觀分 0.323 反映「跌勢明確但未崩盤」

### Task B: 0700.HK PE 線性化驗證（Rule 11 大聲修正先前假設）
- **Tencent 0700.HK 真實數據（yfinance 2026-06-26）**：
  - trailingPE = 14.77, forwardPE = 10.79, PEG = 1.2
  - revenueGrowth = 9.1%, earningsGrowth = 22.9%
  - ROE = 20.5%, priceToBook = 2.86
- **PE linearization 公式**：`pe_factor = 0.95 - 0.90 * (pe + 50) / 550`
  - PE 14.77 → pe_factor = **0.8440**（高分）
  - PE 10~50 區間 pe_factor 都 > 0.78（**全部高分**）
- **fund_score_multifactor 完整拆解**：
  - pe_factor 0.8440 + roe_factor 0.2250 + peg_factor 0.7592 + growth_factor 0.1913
  - 加權 0.35/0.30/0.20/0.15 → **fund_score = 0.5453**（中性偏 buy）
- **0700.HK final = 0.4896 手算**：
  - HK 權重 (market 0.12 / tech 0.23 / fund 0.25 / risk 0.15 / sent 0.15 / news 0.07 / macro 0.08)
  - weighted_avg = 0.5247
  - analyst_std = 0.0674（macro 0.323 vs 其他 0.5+ 造成 disagreement）
  - penalty = max(0.85, 1 - 0.0674) = 0.9326
  - final = 0.5247 × 0.9326 = **0.4893** ≈ fixture 0.4896 ✅

### 重要發現（Rule 11 大聲修正「PE 20-25 對 HK 偏負面」假設）
**HK 偏賣的真實原因不是 PE**：

| 真實驅動因子 | 影響 |
|-------------|------|
| **macro 0.323**（HSI -14%） | 拉低 weighted_avg |
| **analyst disagreement**（macro vs 其他） | 拉低 penalty |
| **3690.HK 基本面崩盤**（pe=0/roe=-24%/peg=28.72） | fund_score 0.387 拉低 HK 均值 |

- 0700.HK 自身 PE 14.77 → pe_factor 0.84（**高分**），fund_score 0.545（中性偏 buy）
- 9988.HK PE 14.09 → pe_factor 0.85（**高分**），fund_score 0.564（buy）
- **PE 線性化對 HK 完全公平**，反而是 HSI macro 大跌 + 3690.HK 基本面崩盤拖累整個 region
- 「PE 20-25 對 HK 偏負面」是先驗假設錯誤，**真實 PE 14-15 對 HK 是高分**

### PE linearization 公式對 HK 友好驗證
| PE | pe_factor | fund_score |
|----|-----------|------------|
| 10 | 0.8518 | 0.5499 |
| 15 | 0.8436 | 0.5470 |
| 20 | 0.8355 | 0.5442 |
| 25 | 0.8273 | 0.5413 |
| 30 | 0.8191 | 0.5385 |
| 35 | 0.8109 | 0.5356 |

**結論**：HK region 在 PE 區間 10-35 都拿到 fund_score 0.54-0.55（中性偏 buy），PE 不是 HK 偏賣的原因。HK 偏賣完全歸因於 macro + analyst disagreement + 3690.HK outlier 基本面。