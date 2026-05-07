---
name: github-integration
description: "Skill for the Github_integration area of stock-team-agent. 11 symbols across 1 files."
---

# Github_integration

11 symbols | 1 files | Cohesion: 95%

## When to Use

- Working with code in `scripts/`
- Understanding how search_financial_repos, get_trading_algorithms, get_data_tools work
- Modifying github_integration-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/github_integration/github_scanner_integration.py` | search_financial_repos, _search_github, _deduplicate_and_score, _score_repo, get_trading_algorithms (+6) |

## Entry Points

Start here when exploring this area:

- **`search_financial_repos`** (Function) — `scripts/github_integration/github_scanner_integration.py:175`
- **`get_trading_algorithms`** (Function) — `scripts/github_integration/github_scanner_integration.py:290`
- **`get_data_tools`** (Function) — `scripts/github_integration/github_scanner_integration.py:300`
- **`generate_analysis_enhancement_report`** (Function) — `scripts/github_integration/github_scanner_integration.py:341`
- **`query_scanner_db`** (Function) — `scripts/github_integration/github_scanner_integration.py:62`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `search_financial_repos` | Function | `scripts/github_integration/github_scanner_integration.py` | 175 |
| `get_trading_algorithms` | Function | `scripts/github_integration/github_scanner_integration.py` | 290 |
| `get_data_tools` | Function | `scripts/github_integration/github_scanner_integration.py` | 300 |
| `generate_analysis_enhancement_report` | Function | `scripts/github_integration/github_scanner_integration.py` | 341 |
| `query_scanner_db` | Function | `scripts/github_integration/github_scanner_integration.py` | 62 |
| `get_integration_recommendations` | Function | `scripts/github_integration/github_scanner_integration.py` | 135 |
| `_search_github` | Function | `scripts/github_integration/github_scanner_integration.py` | 208 |
| `_deduplicate_and_score` | Function | `scripts/github_integration/github_scanner_integration.py` | 244 |
| `_score_repo` | Function | `scripts/github_integration/github_scanner_integration.py` | 264 |
| `_assess_usability` | Function | `scripts/github_integration/github_scanner_integration.py` | 309 |
| `_identify_data_sources` | Function | `scripts/github_integration/github_scanner_integration.py` | 321 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Get_trading_algorithms → _score_repo` | intra_community | 4 |
| `Get_data_tools → _score_repo` | intra_community | 4 |
| `Generate_analysis_enhancement_report → _score_repo` | intra_community | 4 |
| `Get_trading_algorithms → _search_github` | intra_community | 3 |
| `Get_data_tools → _search_github` | intra_community | 3 |
| `Generate_analysis_enhancement_report → _search_github` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "search_financial_repos"})` — see callers and callees
2. `gitnexus_query({query: "github_integration"})` — find related execution flows
3. Read key files listed above for implementation details
