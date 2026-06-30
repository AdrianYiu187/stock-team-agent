#!/usr/bin/env python3
"""audit_v53x_dead_code.py — Generic dead-code / hardcode / drift auditor.

Lesson #58 promoted: every v5.32+ iteration must run this script before
merging. Detects five categories of rot:

  (a) Hardcoded cross-file duplication
  (b) Version drift between source / fixtures / changelog
  (c) Constants that should be extracted (magic numbers)
  (d) Dead code — definitions not referenced anywhere
  (e) Fixture / code sync — fixtures missing tickers present in TICKER_REGION_MAP

Usage:
    python3 scripts/audit_v53x_dead_code.py [--iteration v5.32] [--strict]

Exit code: 0 if no critical findings, 1 if critical (CRITICAL/HIGH) findings.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures"
DOCS = ROOT / "docs"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def find_python_files() -> List[Path]:
    return sorted(SCRIPTS.rglob("*.py"))


def parse_tree(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None


# ---------------------------------------------------------------------------
# (a) Hardcoded cross-file duplication
# ---------------------------------------------------------------------------
def audit_hardcode_duplication() -> List[Dict]:
    """Find numeric/string literals duplicated across 2+ files that look
    like they should be a single constant. Skips trivial literals (0.0,
    1.0, etc.) that are noise."""
    findings: List[Dict] = []
    literal_counts: Dict[str, Set[str]] = defaultdict(set)
    # Threshold: literal must appear in >= 2 distinct files and be >= 4 chars
    pat = re.compile(r'(?<![A-Za-z0-9_])((?:0\.\d+|[A-Z_][A-Z0-9_]{4,}))(?![A-Za-z0-9_])')

    # Noise filter: trivial / sentinel values that don't need extraction
    NOISE_LITERALS = {
        "0.0", "1.0", "0.5", "-1.0", "-0.0",
        "0.1", "0.2", "0.3", "0.4", "0.6", "0.7", "0.8", "0.9",
    }

    for py in find_python_files():
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        # Skip test files (allowed to embed magic numbers)
        if "tests" in py.parts:
            continue
        for m in pat.finditer(text):
            lit = m.group(1)
            # Skip common imports & standard names
            if lit in {"False", "True", "None"} or lit in NOISE_LITERALS:
                continue
            literal_counts[lit].add(str(py.relative_to(ROOT)))

    for lit, files in literal_counts.items():
        if len(files) >= 2:
            findings.append({
                "id": f"HARDCODE-DUP-{lit[:24]}",
                "severity": "MEDIUM",
                "category": "(a) hardcode duplication",
                "literal": lit,
                "files": sorted(files),
                "suggestion": f"Extract `{lit}` to scripts/constants.py and import.",
            })
    return findings


# ---------------------------------------------------------------------------
# (b) Version drift — version string disagreement
# ---------------------------------------------------------------------------
def audit_version_drift(expected_version: str) -> List[Dict]:
    """Look for `__version__ = "X.Y.Z"` or VERSION = "X.Y.Z" and check they
    match expected_version. Also checks CHANGELOG / AUDIT_CHANGELOG for
    latest entry."""
    findings: List[Dict] = []
    version_pat = re.compile(r'__version__\s*=\s*["\']([\d.]+)["\']')
    # Anchored to line start (re.MULTILINE) so we don't match sub-headings
    # like '### 19-Commit v5.11' which would otherwise cross-line match.
    changelog_pat = re.compile(r'^##\s*v?(\d+(?:\.\d+){0,3})\b', re.MULTILINE)

    versions_seen: Dict[str, List[str]] = defaultdict(list)
    for py in find_python_files():
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in version_pat.finditer(text):
            versions_seen[m.group(1)].append(str(py.relative_to(ROOT)))

    # Any version that doesn't match expected is drift
    for ver, files in versions_seen.items():
        if ver != expected_version:
            findings.append({
                "id": f"VERSION-DRIFT-{ver}",
                "severity": "CRITICAL",
                "category": "(b) version drift",
                "expected": expected_version,
                "found": ver,
                "files": files,
                "suggestion": f"Bump to {expected_version} or update --iteration flag.",
            })

    # CHANGELOG drift
    changelog_files = [
        DOCS / "AUDIT_CHANGELOG.md",
        DOCS / "CHANGELOG.md",
        ROOT / "AUDIT_CHANGELOG.md",
    ]
    for cf in changelog_files:
        if cf.exists():
            heads = changelog_pat.findall(cf.read_text(encoding="utf-8"))
            # Use the LATEST (highest) version in the file, not the first match.
            # Pad to equal width so '19' (1 part) doesn't outrank '5.31' (2 parts).
            if heads:
                def vkey(v: str) -> Tuple[int, ...]:
                    parts = []
                    for p in v.split("."):
                        try:
                            parts.append(int(p))
                        except ValueError:
                            parts.append(0)
                    # Pad to 4 components for stable ordering
                    while len(parts) < 4:
                        parts.append(0)
                    return tuple(parts)
                latest = max(heads, key=vkey)
                if latest != expected_version:
                    findings.append({
                        "id": f"CHANGELOG-DRIFT-{cf.name}",
                        "severity": "HIGH",
                        "category": "(b) version drift",
                        "expected": expected_version,
                        "found": latest,
                        "file": str(cf.relative_to(ROOT)),
                        "suggestion": f"Add new `## {expected_version} — ...` entry.",
                    })
    return findings


# ---------------------------------------------------------------------------
# (c) Constants extraction — magic numbers in business logic
# ---------------------------------------------------------------------------
def audit_magic_numbers() -> List[Dict]:
    """Scan for inline numeric thresholds in business logic that should be
    named constants. Heuristic: literal between 0 and 1 in non-test file,
    used in `if`/`return` contexts."""
    findings: List[Dict] = []
    magic_pat = re.compile(r'(?:if|return|>=|<=|>|<|==)\s+([01]\.\d{2,})')

    for py in find_python_files():
        if "tests" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in magic_pat.finditer(line):
                lit = m.group(1)
                # Skip if line is also assigning to a UPPER_CASE name (already a constant)
                if re.search(r'[A-Z_][A-Z0-9_]*\s*=\s*' + re.escape(lit), line):
                    continue
                findings.append({
                    "id": f"MAGIC-NUM-{py.stem}-{lineno}",
                    "severity": "LOW",
                    "category": "(c) magic number",
                    "file": str(py.relative_to(ROOT)),
                    "line": lineno,
                    "literal": lit,
                    "snippet": line.strip()[:80],
                    "suggestion": "Promote to named constant in scripts/constants.py.",
                })
    return findings


# ---------------------------------------------------------------------------
# (d) Dead code — top-level defs not referenced anywhere
# ---------------------------------------------------------------------------
def audit_dead_code() -> List[Dict]:
    """AST-walk all .py files, collect top-level def names, then check
    they appear as references in any other file. Excludes __main__ guards
    and test files."""
    findings: List[Dict] = []
    defs: Dict[str, Path] = {}
    references: Set[str] = set()

    for py in find_python_files():
        tree = parse_tree(py)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defs[node.name] = py
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        defs[t.id] = py

    # Collect all identifiers used anywhere
    for py in find_python_files():
        tree = parse_tree(py)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                references.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Also catch `module.foo` references via the attr name
                references.add(node.attr)

    # Skip dunders, main, test functions, public API markers
    skip_pat = re.compile(r'^(_|test_|main$)')
    # Heuristic: things that look like test classes / scripts are rarely "dead"
    # they're just standalone entry points. Only flag if defined in src paths
    # AND not used as a CLI entry point.
    CLI_ENTRY_PATS = ("scripts/", "verify_", "check_", "audit_", "upgrade_", "run_")
    for name, py in defs.items():
        if skip_pat.match(name):
            continue
        # Only flag if it's defined in scripts/ (not tests)
        if "tests" in py.parts:
            continue
        # Heuristic: if referenced anywhere OR is a Flask/FastAPI route
        if name in references:
            continue
        # Skip if file is __init__.py (re-exports)
        if py.name == "__init__.py":
            continue
        # Downgrade severity for likely CLI / verification scripts
        rel = str(py.relative_to(ROOT))
        is_cli_script = any(rel.startswith(p) or rel.startswith(p.replace("/", ""))
                            for p in CLI_ENTRY_PATS)
        severity = "LOW" if is_cli_script else "MEDIUM"
        findings.append({
            "id": f"DEAD-CODE-{name}",
            "severity": severity,
            "category": "(d) dead code",
            "name": name,
            "file": rel,
            "suggestion": "Remove if truly unused, or wire it up.",
        })
    return findings


# ---------------------------------------------------------------------------
# (e) Fixture / code sync — TICKER_REGION_MAP coverage in fixtures
# ---------------------------------------------------------------------------
def audit_fixture_sync() -> List[Dict]:
    """If TICKER_REGION_MAP defines tickers not present in any snapshot
    fixture, that's a sync gap."""
    findings: List[Dict] = []
    # Find TICKER_REGION_MAP definition
    map_file = SCRIPTS / "dashboard_api.py"
    if not map_file.exists():
        return findings
    src = map_file.read_text(encoding="utf-8")
    # Quick parse: look for dict of dicts pattern (TICKER->region)
    ticker_pat = re.compile(r'"([A-Z]{1,5}(?:\.[A-Z])?)"\s*:\s*"(?:US|HK|CN|TW|JP|EU)"')
    tickers_in_map = set(m.group(1) for m in ticker_pat.finditer(src))

    # Discover canonical fixture by globbing (don't hardcode a single path)
    candidates = list(ROOT.rglob("snapshot*more_tickers*.json")) + \
                 list(ROOT.rglob("snapshot*extended*.json"))
    if not candidates:
        findings.append({
            "id": "FIXTURE-MISSING",
            "severity": "HIGH",
            "category": "(e) fixture sync",
            "expected": "snapshot_*_more_tickers.json or snapshot_*_extended*.json",
            "suggestion": "Generate canonical snapshot fixture first.",
        })
        return findings
    canonical = candidates[0]
    if len(candidates) > 1:
        findings.append({
            "id": "FIXTURE-MULTIPLE",
            "severity": "LOW",
            "category": "(e) fixture sync",
            "files": [str(c.relative_to(ROOT)) for c in candidates],
            "suggestion": "Multiple snapshot fixtures found; review for canonical.",
        })

    try:
        data = json.loads(canonical.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        findings.append({
            "id": "FIXTURE-BAD-JSON",
            "severity": "HIGH",
            "category": "(e) fixture sync",
            "file": str(canonical.relative_to(ROOT)),
            "error": str(e),
        })
        return findings

    tickers_in_fixture: Set[str] = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                tickers_in_fixture.add(v.get("ticker") or v.get("symbol") or k)
            else:
                tickers_in_fixture.add(k)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                tickers_in_fixture.add(item.get("ticker") or item.get("symbol") or "")

    missing_in_fixture = tickers_in_map - tickers_in_fixture
    extra_in_fixture = tickers_in_fixture - tickers_in_map
    if missing_in_fixture:
        findings.append({
            "id": "FIXTURE-TICKERS-MISSING",
            "severity": "HIGH",
            "category": "(e) fixture sync",
            "missing": sorted(missing_in_fixture),
            "fixture": str(canonical.relative_to(ROOT)),
            "suggestion": "Add these tickers to canonical fixture or remove from map.",
        })
    if extra_in_fixture:
        findings.append({
            "id": "FIXTURE-TICKERS-EXTRA",
            "severity": "LOW",
            "category": "(e) fixture sync",
            "extra": sorted(extra_in_fixture),
            "fixture": str(canonical.relative_to(ROOT)),
            "suggestion": "Consider adding to TICKER_REGION_MAP for per-region coverage.",
        })
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--iteration", default="v5.32", help="Expected version (e.g. v5.32)")
    p.add_argument("--strict", action="store_true", help="Treat MEDIUM as failure")
    args = p.parse_args()

    expected = args.iteration.lstrip("v")
    print(f"=== audit_v53x_dead_code.py — {args.iteration} ===")
    print()

    findings: List[Dict] = []
    findings += audit_hardcode_duplication()
    findings += audit_version_drift(expected)
    findings += audit_magic_numbers()
    findings += audit_dead_code()
    findings += audit_fixture_sync()

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 99), f["id"]))

    by_sev: Dict[str, List[Dict]] = defaultdict(list)
    for f in findings:
        by_sev[f["severity"]].append(f)

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        items = by_sev.get(sev, [])
        print(f"[{sev}] {len(items)}")
        for f in items:
            print(f"  - {f['id']}: {f['category']}")
            for k, v in f.items():
                if k in {"id", "category"}:
                    continue
                if isinstance(v, list):
                    print(f"      {k}: {', '.join(str(x) for x in v[:6])}{'...' if len(v) > 6 else ''}")
                else:
                    print(f"      {k}: {v}")
        print()

    fail = bool(by_sev.get("CRITICAL")) or bool(by_sev.get("HIGH"))
    if args.strict:
        fail = fail or bool(by_sev.get("MEDIUM"))
    print(f"Total: {len(findings)} findings | Fail threshold: {'strict' if args.strict else 'CRITICAL+HIGH'}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())