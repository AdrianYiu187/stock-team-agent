---
name: scripts
description: "Skill for the Scripts area of stock-team-agent. 47 symbols across 6 files."
---

# Scripts

47 symbols | 6 files | Cohesion: 86%

## When to Use

- Working with code in `scripts/`
- Understanding how get_workflow_info, route, get_capabilities work
- Modifying scripts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/trigger.py` | execute, _identify_capabilities, _extract_symbol, _requires_full_analysis, _requires_technical_only (+18) |
| `scripts/workflow_engine.py` | get_workflow_info, execute_workflow, _execute_analyst, _generate_consensus, _get_recommendation (+4) |
| `scripts/stock_router.py` | route, _identify_task_type, _dispatch_analysts, _generate_charts_if_needed, get_capabilities (+1) |
| `scripts/indicators/professional_indices.py` | buffett_indicator, shiller_pe, risk_score, gold_cross_death_cross |
| `scripts/valuation/valuation_models.py` | dcf, ddm, peg |
| `scripts/stock_health_check.py` | check_file_exists, main |

## Entry Points

Start here when exploring this area:

- **`get_workflow_info`** (Function) — `scripts/workflow_engine.py:292`
- **`route`** (Function) — `scripts/stock_router.py:104`
- **`get_capabilities`** (Function) — `scripts/stock_router.py:230`
- **`main`** (Function) — `scripts/stock_router.py:243`
- **`check_file_exists`** (Function) — `scripts/stock_health_check.py:24`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_workflow_info` | Function | `scripts/workflow_engine.py` | 292 |
| `route` | Function | `scripts/stock_router.py` | 104 |
| `get_capabilities` | Function | `scripts/stock_router.py` | 230 |
| `main` | Function | `scripts/stock_router.py` | 243 |
| `check_file_exists` | Function | `scripts/stock_health_check.py` | 24 |
| `main` | Function | `scripts/stock_health_check.py` | 32 |
| `dcf` | Function | `scripts/valuation/valuation_models.py` | 36 |
| `ddm` | Function | `scripts/valuation/valuation_models.py` | 76 |
| `peg` | Function | `scripts/valuation/valuation_models.py` | 106 |
| `buffett_indicator` | Function | `scripts/indicators/professional_indices.py` | 46 |
| `shiller_pe` | Function | `scripts/indicators/professional_indices.py` | 77 |
| `risk_score` | Function | `scripts/indicators/professional_indices.py` | 123 |
| `gold_cross_death_cross` | Function | `scripts/indicators/professional_indices.py` | 200 |
| `execute` | Function | `scripts/trigger.py` | 137 |
| `main` | Function | `scripts/trigger.py` | 317 |
| `execute_workflow` | Function | `scripts/workflow_engine.py` | 135 |
| `demo_workflow` | Function | `scripts/workflow_engine.py` | 302 |
| `_identify_task_type` | Function | `scripts/stock_router.py` | 149 |
| `_dispatch_analysts` | Function | `scripts/stock_router.py` | 176 |
| `_generate_charts_if_needed` | Function | `scripts/stock_router.py` | 210 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _get_router` | cross_community | 4 |
| `Main → _generate_summary` | intra_community | 4 |
| `Main → _identify_task_type` | intra_community | 3 |
| `Main → _dispatch_analysts` | intra_community | 3 |
| `Main → _generate_charts_if_needed` | intra_community | 3 |
| `Main → _identify_task_type` | intra_community | 3 |
| `Main → _dispatch_analysts` | intra_community | 3 |
| `Main → _generate_charts_if_needed` | intra_community | 3 |
| `Main → _identify_capabilities` | intra_community | 3 |
| `Main → _extract_symbol` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Consensus | 1 calls |
| Github_integration | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_workflow_info"})` — see callers and callees
2. `gitnexus_query({query: "scripts"})` — find related execution flows
3. Read key files listed above for implementation details
