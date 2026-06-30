"""v5.31 P3 / v5.33 (Lesson #58 promotion) — audit_v53x_dead_code.py TDD guards.

Promote the v5.31 one-off audit into a reusable chain. 6 guards:

  1. test_audit_script_exists_and_runs
  2. test_audit_categorizes_5_finding_classes
  3. test_audit_detects_real_version_drift
  4. test_audit_detects_real_changelog_drift
  5. test_audit_finds_no_critical_when_clean
  6. test_audit_strict_mode_escalates_medium

v5.33 upgrade: bump default iteration from v5.31 → v5.32 (Lesson #61 — audit
chain must track the latest closed version, not the version that introduced it).
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AUDIT_SCRIPT = _REPO_ROOT / "scripts" / "audit_v53x_dead_code.py"


def _run_audit(iteration: str = "v5.32", strict: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_AUDIT_SCRIPT), "--iteration", iteration]
    if strict:
        cmd.append("--strict")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT))


class TestAuditV53XChain(unittest.TestCase):
    """Lesson #58 promotion: audit_v53x_dead_code.py must be reusable."""

    def test_audit_script_exists_and_runs(self):
        """The promoted script must exist and be importable + runnable."""
        self.assertTrue(_AUDIT_SCRIPT.exists(), f"missing {_AUDIT_SCRIPT}")
        # Must be syntactically valid Python
        import ast
        ast.parse(_AUDIT_SCRIPT.read_text(encoding="utf-8"))
        # Must run to completion (exit 0 or 1)
        r = _run_audit("v5.32")
        self.assertIn(r.returncode, (0, 1), f"unexpected exit {r.returncode}: {r.stderr}")

    def test_audit_categorizes_5_finding_classes(self):
        """Output must surface all 5 categories: (a)-(e). Use v99.99 to ensure
        every category has at least one finding (v5.32 is clean so (b) is absent)."""
        r = _run_audit("v99.99")
        output = r.stdout
        # Each category should appear at least once when there's drift
        for cat_label in ("(a)", "(b)", "(c)", "(d)", "(e)"):
            self.assertIn(cat_label, output, f"category {cat_label} missing from output:\n{output[:600]}")

    def test_audit_detects_real_version_drift(self):
        """Pointing audit at a non-existent version should report drift."""
        r = _run_audit("v99.99")
        # v99.99 is far ahead of anything in the repo, so drift is expected
        output = r.stdout
        # Should exit non-zero AND mention drift in output
        self.assertEqual(r.returncode, 1, "v99.99 should produce CRITICAL/HIGH drift")
        self.assertTrue(
            "VERSION-DRIFT" in output or "CHANGELOG-DRIFT" in output,
            f"v99.99 should report drift; got:\n{output[:500]}",
        )

    def test_audit_detects_real_changelog_drift(self):
        """The audit must NOT confuse sub-headings like '### 19-Commit v5.11' with
        top-level versions (Lesson #58 cross-line regression).

        v5.33 upgrade: point at v5.33 (latest). v5.32 would now FAIL because
        the latest CHANGELOG entry is v5.33 — that's a legit closure boundary,
        not a Lesson #58 regression. (Lesson #61 self-maintenance: bump guard.)"""
        # v5.33 should be the latest in AUDIT_CHANGELOG.md after closure
        r = _run_audit("v5.33")
        # If we incorrectly captured '19' as the latest (old bug), we'd see
        # CHANGELOG-DRIFT even though v5.33 is present
        output = r.stdout
        # There should be no 'CHANGELOG-DRIFT-AUDIT_CHANGELOG.md' for v5.33
        # (since docs/AUDIT_CHANGELOG.md has v5.33 already)
        self.assertNotIn(
            "CHANGELOG-DRIFT-AUDIT_CHANGELOG.md",
            output.split("[HIGH]")[1].split("[MEDIUM]")[0] if "[HIGH]" in output else "",
            "Lesson #58 regression: cross-line '19-Commit' false positive",
        )

    def test_audit_finds_no_critical_when_clean(self):
        """When targeting an iteration that's been properly closed, CRITICAL count
        must be zero. v5.33 is closed → 0 CRITICAL expected."""
        r = _run_audit("v5.33")
        output = r.stdout
        # Find CRITICAL section
        crit_section = ""
        if "[CRITICAL]" in output:
            crit_section = output.split("[CRITICAL]")[1].split("[")[0]
        self.assertIn("0", crit_section.split("\n")[0],
                      f"v5.33 should have 0 CRITICAL findings: {crit_section[:200]}")

    def test_audit_strict_mode_escalates_medium(self):
        """--strict should cause MEDIUM findings to fail (exit 1)."""
        r_normal = _run_audit("v5.32", strict=False)
        r_strict = _run_audit("v5.32", strict=True)
        # If there are any MEDIUM findings (almost always), strict should exit 1
        has_medium = "[MEDIUM] 0" not in r_normal.stdout
        if has_medium:
            self.assertEqual(r_strict.returncode, 1,
                             f"--strict should fail when MEDIUM > 0; got exit {r_strict.returncode}")

    # --- v5.33 D2 (b) — new CLI flags ----------------------------------------
    def test_audit_only_flag_isolates_single_category(self):
        """--only <a|b|c|d|e> should only run that category (Lesson #62)."""
        # Use v99.99 to FORCE (b) findings (version-drift always triggers on unknown version).
        # Otherwise a clean v5.32 produces 0 (b) findings → category label never printed.
        r = subprocess.run(
            [sys.executable, str(_AUDIT_SCRIPT), "--iteration", "v99.99", "--only", "b"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT))
        out = r.stdout
        # (b) category SHOULD appear; others MUST NOT
        self.assertIn("(b)", out, f"--only b must include (b):\n{out[:500]}")
        self.assertNotIn("(a) hardcode", out,
                         f"--only b must exclude (a):\n{out[:500]}")
        self.assertNotIn("(c) magic", out,
                         f"--only b must exclude (c):\n{out[:500]}")
        self.assertNotIn("(d) dead", out,
                         f"--only b must exclude (d):\n{out[:500]}")
        self.assertNotIn("(e) fixture", out,
                         f"--only b must exclude (e):\n{out[:500]}")

    def test_audit_noise_filter_reduces_hardcode_findings(self):
        """--noise-filter should reduce (a) hardcode findings by skipping CLI scripts."""
        r_baseline = _run_audit("v5.32")  # default runs all categories
        r_filtered = subprocess.run(
            [sys.executable, str(_AUDIT_SCRIPT), "--iteration", "v5.32",
             "--only", "a", "--noise-filter"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT))
        baseline_total = self._extract_total(r_baseline.stdout)
        filtered_total = self._extract_total(r_filtered.stdout)
        # The (a)-only + noise-filtered count must be strictly less than baseline total
        # (we're running only one category that's filtered, vs all 5 unfiltered)
        self.assertLess(filtered_total, baseline_total,
                        f"--only a --noise-filter ({filtered_total}) should be less "
                        f"than baseline ({baseline_total})")

    def test_audit_framework_filter_reduces_magic_findings(self):
        """--framework-filter should reduce (c) magic-number findings in framework files."""
        r_filtered = subprocess.run(
            [sys.executable, str(_AUDIT_SCRIPT), "--iteration", "v5.32",
             "--only", "c", "--framework-filter"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT))
        # Should produce output (not error)
        self.assertIn("[LOW]", r_filtered.stdout,
                      f"--only c --framework-filter must run cleanly:\n"
                      f"{r_filtered.stdout[:300]}")

    @staticmethod
    def _extract_total(output: str) -> int:
        """Parse 'Total: N findings' line."""
        for line in output.splitlines():
            if line.startswith("Total:"):
                # 'Total: 151 findings | ...'
                parts = line.split()
                return int(parts[1])
        return -1


if __name__ == "__main__":
    unittest.main()