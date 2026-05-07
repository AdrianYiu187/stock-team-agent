---
name: integrations
description: "Skill for the Integrations area of stock-team-agent. 10 symbols across 1 files."
---

# Integrations

10 symbols | 1 files | Cohesion: 80%

## When to Use

- Working with code in `scripts/`
- Understanding how generate_debate_argument, summarize_analyst_consensus, health_check work
- Modifying integrations-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/integrations/minimax_llm.py` | _call_api, _extract_json_objects, generate_debate_argument, summarize_analyst_consensus, health_check (+5) |

## Entry Points

Start here when exploring this area:

- **`generate_debate_argument`** (Function) — `scripts/integrations/minimax_llm.py:241`
- **`summarize_analyst_consensus`** (Function) — `scripts/integrations/minimax_llm.py:331`
- **`health_check`** (Function) — `scripts/integrations/minimax_llm.py:398`
- **`analyze_sentiment`** (Function) — `scripts/integrations/minimax_llm.py:119`
- **`analyze_stock_news`** (Function) — `scripts/integrations/minimax_llm.py:188`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `generate_debate_argument` | Function | `scripts/integrations/minimax_llm.py` | 241 |
| `summarize_analyst_consensus` | Function | `scripts/integrations/minimax_llm.py` | 331 |
| `health_check` | Function | `scripts/integrations/minimax_llm.py` | 398 |
| `analyze_sentiment` | Function | `scripts/integrations/minimax_llm.py` | 119 |
| `analyze_stock_news` | Function | `scripts/integrations/minimax_llm.py` | 188 |
| `analyze_sentiment` | Function | `scripts/integrations/minimax_llm.py` | 421 |
| `analyze_stock_news` | Function | `scripts/integrations/minimax_llm.py` | 427 |
| `_call_api` | Function | `scripts/integrations/minimax_llm.py` | 48 |
| `_extract_json_objects` | Function | `scripts/integrations/minimax_llm.py` | 100 |
| `_fallback_sentiment` | Function | `scripts/integrations/minimax_llm.py` | 170 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Analyze_stock_news → _extract_json_objects` | cross_community | 5 |
| `Analyze_sentiment → _extract_json_objects` | cross_community | 4 |
| `Analyze_stock_news → _fallback_sentiment` | intra_community | 4 |
| `Generate_debate_argument → _extract_json_objects` | intra_community | 3 |
| `Summarize_analyst_consensus → _extract_json_objects` | intra_community | 3 |
| `Analyze_sentiment → _fallback_sentiment` | intra_community | 3 |
| `Health_check → _extract_json_objects` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "generate_debate_argument"})` — see callers and callees
2. `gitnexus_query({query: "integrations"})` — find related execution flows
3. Read key files listed above for implementation details
