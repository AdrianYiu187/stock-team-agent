---
name: cluster-17
description: "Skill for the Cluster_17 area of stock-team-agent. 9 symbols across 1 files."
---

# Cluster_17

9 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `scripts/`
- Understanding how StockAgentBaseException, DataFetchError, DataParseError work
- Modifying cluster_17-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/utils/errors.py` | StockAgentBaseException, DataFetchError, DataParseError, APIError, APITimeoutError (+4) |

## Entry Points

Start here when exploring this area:

- **`StockAgentBaseException`** (Class) — `scripts/utils/errors.py:49`
- **`DataFetchError`** (Class) — `scripts/utils/errors.py:81`
- **`DataParseError`** (Class) — `scripts/utils/errors.py:97`
- **`APIError`** (Class) — `scripts/utils/errors.py:111`
- **`APITimeoutError`** (Class) — `scripts/utils/errors.py:127`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `StockAgentBaseException` | Class | `scripts/utils/errors.py` | 49 |
| `DataFetchError` | Class | `scripts/utils/errors.py` | 81 |
| `DataParseError` | Class | `scripts/utils/errors.py` | 97 |
| `APIError` | Class | `scripts/utils/errors.py` | 111 |
| `APITimeoutError` | Class | `scripts/utils/errors.py` | 127 |
| `APIRateLimitError` | Class | `scripts/utils/errors.py` | 141 |
| `AnalysisError` | Class | `scripts/utils/errors.py` | 155 |
| `ConsensusError` | Class | `scripts/utils/errors.py` | 171 |
| `DebateEngineError` | Class | `scripts/utils/errors.py` | 183 |

## How to Explore

1. `gitnexus_context({name: "StockAgentBaseException"})` — see callers and callees
2. `gitnexus_query({query: "cluster_17"})` — find related execution flows
3. Read key files listed above for implementation details
