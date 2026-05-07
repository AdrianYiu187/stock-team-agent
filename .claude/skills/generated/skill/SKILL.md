---
name: skill
description: "Skill for the 辩论 area of stock-team-agent. 7 symbols across 1 files."
---

# 辩论

7 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `scripts/`
- Understanding how send_message, run_debate work
- Modifying 辩论-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/辩论/llm_debate_engine.py` | _get_debate_context, _execute_llm_driven_round, _execute_cross_challenges, _execute_fallback_round, send_message (+2) |

## Entry Points

Start here when exploring this area:

- **`send_message`** (Function) — `scripts/辩论/llm_debate_engine.py:185`
- **`run_debate`** (Function) — `scripts/辩论/llm_debate_engine.py:204`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `send_message` | Function | `scripts/辩论/llm_debate_engine.py` | 185 |
| `run_debate` | Function | `scripts/辩论/llm_debate_engine.py` | 204 |
| `_get_debate_context` | Function | `scripts/辩论/llm_debate_engine.py` | 85 |
| `_execute_llm_driven_round` | Function | `scripts/辩论/llm_debate_engine.py` | 99 |
| `_execute_cross_challenges` | Function | `scripts/辩论/llm_debate_engine.py` | 159 |
| `_execute_fallback_round` | Function | `scripts/辩论/llm_debate_engine.py` | 179 |
| `_generate_consensus` | Function | `scripts/辩论/llm_debate_engine.py` | 240 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_debate → Send_message` | intra_community | 4 |
| `Run_debate → _execute_fallback_round` | intra_community | 3 |
| `Run_debate → _get_debate_context` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "send_message"})` — see callers and callees
2. `gitnexus_query({query: "辩论"})` — find related execution flows
3. Read key files listed above for implementation details
