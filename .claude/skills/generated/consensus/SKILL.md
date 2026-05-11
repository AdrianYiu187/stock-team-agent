---
name: consensus
description: "Skill for the Consensus area of stock-team-agent. 8 symbols across 1 files."
---

# Consensus

8 symbols | 1 files | Cohesion: 93%

## When to Use

- Working with code in `scripts/`
- Understanding how integrate, main work
- Modifying consensus-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/train/consensus_engine.py` | integrate, integrate_pydantic, _extract_scores, _calculate_weighted_scores, _detect_conflicts, _compute_consensus (+5) |
| `scripts/schemas/consensus.py` | **ConsensusResult Pydantic model** |
| `scripts/schemas/ratings.py` | **5-tier SignalType, FiveTierRating** |

## Entry Points

Start here when exploring this area:

- **`integrate`** (Function) — `scripts/train/consensus_engine.py:46` — legacy dict-based consensus
- **`integrate_pydantic`** (Function) — `scripts/train/consensus_engine.py:253` — returns typed ConsensusResult
- **`ConsensusResult`** (Class) — `scripts/schemas/consensus.py` — Pydantic model with `.to_markdown()` method

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `integrate` | Function | `scripts/train/consensus_engine.py` | 46 |
| `integrate_pydantic` | Function | `scripts/train/consensus_engine.py` | 253 |
| `ConsensusResult` | Class | `scripts/schemas/consensus.py` | ~50 |
| `SignalType` | Enum | `scripts/schemas/ratings.py` | — |
| `FiveTierRating` | Class | `scripts/schemas/ratings.py` | — |

## 5-Tier Signal System

| Score Range | Signal | Label |
|-------------|--------|-------|
| 0.85–1.00 | STRONG_BUY | 強烈買入 |
| 0.65–0.84 | BUY | 適度買入 |
| 0.45–0.64 | HOLD | 持有觀望 |
| 0.25–0.44 | SELL | 適度賣出 |
| 0.00–0.24 | STRONG_SELL | 強烈賣出 |

Use `SignalType.from_score(score)` to convert. ConsensusEngine maps overall_score (-100 to +100) to tiers: ≥60→5, ≥30→4, ≥-30→3, ≥-60→2, <-60→1.

## How to Explore

1. `gitnexus_context({name: "integrate"})` — see callers and callees
2. `gitnexus_query({query: "consensus"})` — find related execution flows
3. Read key files listed above for implementation details
