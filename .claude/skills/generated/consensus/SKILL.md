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
| `scripts/consensus/consensus_engine.py` | integrate, _extract_scores, _calculate_weighted_scores, _detect_conflicts, _compute_consensus (+3) |

## Entry Points

Start here when exploring this area:

- **`integrate`** (Function) — `scripts/consensus/consensus_engine.py:45`
- **`main`** (Function) — `scripts/consensus/consensus_engine.py:243`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `integrate` | Function | `scripts/consensus/consensus_engine.py` | 45 |
| `main` | Function | `scripts/consensus/consensus_engine.py` | 243 |
| `_extract_scores` | Function | `scripts/consensus/consensus_engine.py` | 92 |
| `_calculate_weighted_scores` | Function | `scripts/consensus/consensus_engine.py` | 107 |
| `_detect_conflicts` | Function | `scripts/consensus/consensus_engine.py` | 124 |
| `_compute_consensus` | Function | `scripts/consensus/consensus_engine.py` | 165 |
| `_generate_recommendation` | Function | `scripts/consensus/consensus_engine.py` | 182 |
| `_calculate_confidence` | Function | `scripts/consensus/consensus_engine.py` | 210 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _extract_scores` | intra_community | 3 |
| `Main → _calculate_weighted_scores` | intra_community | 3 |
| `Main → _detect_conflicts` | intra_community | 3 |
| `Main → _compute_consensus` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "integrate"})` — see callers and callees
2. `gitnexus_query({query: "consensus"})` — find related execution flows
3. Read key files listed above for implementation details
