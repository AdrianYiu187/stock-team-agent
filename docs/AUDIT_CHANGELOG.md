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