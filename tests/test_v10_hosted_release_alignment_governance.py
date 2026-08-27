from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_hosted_release_alignment_governance.py"
ALIGNMENT_WORKFLOW = ROOT / ".github/workflows/v10-hosted-release-alignment.yml"
ALIGNMENT_STANDARD = ROOT / "docs/operations/V10_HOSTED_RELEASE_ALIGNMENT_STANDARD.md"
FAILURE_LEARNING = (
    ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL054.md"
)
ENGINEERING_GOVERNANCE_WORKFLOW = (
    ROOT / ".github/workflows/v10-engineering-governance.yml"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "hosted_release_alignment_governance",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise AssertionError(
            "hosted release alignment governance script cannot be loaded"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sources() -> dict[str, str]:
    return {
        "alignment_workflow": ALIGNMENT_WORKFLOW.read_text(encoding="utf-8"),
        "alignment_standard": ALIGNMENT_STANDARD.read_text(encoding="utf-8"),
        "failure_learning": FAILURE_LEARNING.read_text(encoding="utf-8"),
        "engineering_governance_workflow": ENGINEERING_GOVERNANCE_WORKFLOW.read_text(
            encoding="utf-8"
        ),
    }


class HostedReleaseAlignmentGovernanceTests(unittest.TestCase):
    def test_current_repository_satisfies_alignment_governance(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn(
            "Post-merge downstream topology: terminal exact-main alignment "
            "SUCCESS required",
            completed.stdout,
        )

    def test_workflow_run_parser_tolerates_benign_yaml_formatting(self) -> None:
        governance = _module()
        workflow = """
on:
  workflow_dispatch:
  workflow_run:
    branches:
      - "main"
    workflows:
      - 'V10 Phase 4 Free Preview Deploy'
    types:
      - completed # terminal event

permissions:
  contents: read
"""

        self.assertEqual(
            governance._workflow_run_lists(workflow),
            {
                "workflows": {"V10 Phase 4 Free Preview Deploy"},
                "types": {"completed"},
                "branches": {"main"},
            },
        )

    def test_workflow_run_parser_accepts_inline_lists(self) -> None:
        governance = _module()
        workflow = """
on:
  workflow_run:
    workflows: ["V10 Phase 4 Free Preview Deploy"]
    types: [completed]
    branches: [main]
"""

        self.assertEqual(
            governance._workflow_run_lists(workflow),
            {
                "workflows": {"V10 Phase 4 Free Preview Deploy"},
                "types": {"completed"},
                "branches": {"main"},
            },
        )

    def test_validator_rejects_success_only_downstream_trigger(self) -> None:
        governance = _module()
        sources = _sources()
        sources["alignment_workflow"] += (
            "\n# github.event.workflow_run.conclusion == 'success'\n"
        )
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertTrue(
            any("forbidden governance marker" in failure for failure in failures),
            failures,
        )

    def test_validator_rejects_missing_terminal_post_merge_rule(self) -> None:
        governance = _module()
        sources = _sources()
        sources["alignment_standard"] = sources["alignment_standard"].replace(
            "not accepted post-merge runtime evidence",
            "temporarily acceptable runtime evidence",
        )
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertTrue(
            any(
                "not accepted post-merge runtime evidence" in failure
                for failure in failures
            ),
            failures,
        )

    def test_engineering_governance_executes_guard_and_regression_suite(self) -> None:
        text = ENGINEERING_GOVERNANCE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "python scripts/check_v10_hosted_release_alignment_governance.py",
            text,
        )
        self.assertIn(
            "scripts/check_v10_hosted_release_alignment_governance.py",
            text,
        )
        self.assertIn("tests.test_v10_hosted_release_alignment_governance", text)


if __name__ == "__main__":
    unittest.main()
