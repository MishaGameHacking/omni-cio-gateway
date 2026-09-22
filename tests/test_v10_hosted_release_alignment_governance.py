from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_hosted_release_alignment_governance.py"
PHASE4_WORKFLOW = ROOT / ".github/workflows/v10-phase4-free-preview-deploy.yml"
ALIGNMENT_WORKFLOW = ROOT / ".github/workflows/v10-hosted-release-alignment.yml"
CLOUDFLARE_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md"
)
CLOUDFLARE_CONTRACT = (
    ROOT / "docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json"
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


def _sources() -> dict[str, object]:
    return {
        "phase4_workflow": PHASE4_WORKFLOW.read_text(encoding="utf-8"),
        "alignment_workflow": ALIGNMENT_WORKFLOW.read_text(encoding="utf-8"),
        "cloudflare_amendment": CLOUDFLARE_AMENDMENT.read_text(encoding="utf-8"),
        "cloudflare_contract": json.loads(
            CLOUDFLARE_CONTRACT.read_text(encoding="utf-8")
        ),
    }


class HostedReleaseAlignmentGovernanceTests(unittest.TestCase):
    def test_current_repository_satisfies_retired_render_governance(self) -> None:
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
            "Legacy Render Phase-4 deployment: manual-only and fail-closed",
            completed.stdout,
        )
        self.assertIn(
            "Legacy Render hosted alignment: manual-only and fail-closed",
            completed.stdout,
        )
        self.assertIn(
            "Historical Amendment-14 Cloudflare release authority: preserved evidence only",
            completed.stdout,
        )
        self.assertIn(
            "Current/future V10 provider authority: Timeweb under Amendment 18",
            completed.stdout,
        )

    def test_validator_rejects_reactivated_workflow_run_trigger(self) -> None:
        governance = _module()
        sources = _sources()
        sources["phase4_workflow"] = str(sources["phase4_workflow"]).replace(
            "  workflow_dispatch:\n",
            "  workflow_run:\n    workflows: [Regression Shield]\n    types: [completed]\n    branches: [main]\n  workflow_dispatch:\n",
        )
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertTrue(
            any("workflow_run:" in failure for failure in failures), failures
        )

    def test_validator_rejects_reactivated_schedule(self) -> None:
        governance = _module()
        sources = _sources()
        sources["alignment_workflow"] = str(sources["alignment_workflow"]).replace(
            "  workflow_dispatch:\n",
            '  workflow_dispatch:\n  schedule:\n    - cron: "23 3 * * *"\n',
        )
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertTrue(any("schedule:" in failure for failure in failures), failures)

    def test_validator_rejects_provider_secret_or_mutation_markers(self) -> None:
        governance = _module()
        sources = _sources()
        sources["phase4_workflow"] = str(sources["phase4_workflow"]) + (
            "\n# RENDER_API_KEY\n# NEON_API_KEY\n"
        )
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertTrue(
            any("active-provider marker" in failure for failure in failures),
            failures,
        )

    def test_validator_requires_fail_closed_retirement_markers(self) -> None:
        governance = _module()
        sources = _sources()
        sources["alignment_workflow"] = str(sources["alignment_workflow"]).replace(
            "LEGACY_RENDER_ALIGNMENT_RETIRED_AMENDMENT_14",
            "legacy marker removed",
        )
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertTrue(
            any(
                "LEGACY_RENDER_ALIGNMENT_RETIRED_AMENDMENT_14" in failure
                for failure in failures
            ),
            failures,
        )

    def test_validator_rejects_render_as_new_v10_target(self) -> None:
        governance = _module()
        sources = _sources()
        contract = dict(sources["cloudflare_contract"])
        provider = dict(contract["provider_transition"])
        provider["render_new_v10_target_selected"] = True
        contract["provider_transition"] = provider
        sources["cloudflare_contract"] = contract
        failures: list[str] = []

        governance.validate_sources(**sources, failures=failures)

        self.assertIn("Render must remain disabled as a new V10 target", failures)


if __name__ == "__main__":
    unittest.main()
