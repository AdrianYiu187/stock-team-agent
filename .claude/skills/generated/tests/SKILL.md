---
name: tests
description: "Skill for the Tests area of stock-team-agent. 10 symbols across 2 files."
---

# Tests

10 symbols | 2 files | Cohesion: 100%

## When to Use

- Working with code in `scripts/`
- Understanding how test_base_exception_to_dict, to_dict, test_decorator_returns_default_on_error work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `scripts/tests/test_stock_agent.py` | test_base_exception_to_dict, test_decorator_returns_default_on_error, failing_function, test_decorator_with_retries, sometimes_failing (+4) |
| `scripts/utils/errors.py` | to_dict |

## Entry Points

Start here when exploring this area:

- **`test_base_exception_to_dict`** (Function) — `scripts/tests/test_stock_agent.py:52`
- **`to_dict`** (Function) — `scripts/utils/errors.py:68`
- **`test_decorator_returns_default_on_error`** (Function) — `scripts/tests/test_stock_agent.py:180`
- **`failing_function`** (Function) — `scripts/tests/test_stock_agent.py:183`
- **`test_decorator_with_retries`** (Function) — `scripts/tests/test_stock_agent.py:189`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_base_exception_to_dict` | Function | `scripts/tests/test_stock_agent.py` | 52 |
| `to_dict` | Function | `scripts/utils/errors.py` | 68 |
| `test_decorator_returns_default_on_error` | Function | `scripts/tests/test_stock_agent.py` | 180 |
| `failing_function` | Function | `scripts/tests/test_stock_agent.py` | 183 |
| `test_decorator_with_retries` | Function | `scripts/tests/test_stock_agent.py` | 189 |
| `sometimes_failing` | Function | `scripts/tests/test_stock_agent.py` | 194 |
| `test_critical_error_reraises` | Function | `scripts/tests/test_stock_agent.py` | 208 |
| `critical_fail` | Function | `scripts/tests/test_stock_agent.py` | 211 |
| `test_critical_error_wraps_unknown` | Function | `scripts/tests/test_stock_agent.py` | 217 |
| `unknown_error` | Function | `scripts/tests/test_stock_agent.py` | 220 |

## How to Explore

1. `gitnexus_context({name: "test_base_exception_to_dict"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
