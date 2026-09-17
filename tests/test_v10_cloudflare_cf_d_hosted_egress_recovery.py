from __future__ import annotations

import unittest
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
_ADAPTER = _ROOT / "scripts/bootstrap_v10_cloudflare_neon_hosted_egress.py"
_FAILURE_LEDGER = (
    _ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL157.md"
)
_ARCHITECTURE = _ROOT / "docs/architecture/V10_CLOUDFLARE_NEON_HOSTED_EGRESS_BRIDGE.md"


def _section(source: str, start: str, end: str | None) -> str:
    tail = source.split(start, 1)[1]
    return tail if end is None else tail.split(end, 1)[0]


class CloudflareCfDHostedEgressRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = _WORKFLOW.read_text(encoding="utf-8")
        cls.adapter = _ADAPTER.read_text(encoding="utf-8")

    def test_workflow_keeps_exact_main_release_gates(self) -> None:
        for marker in (
            "workflow_run:",
            "- Regression Shield",
            "github.event.workflow_run.conclusion == 'success'",
            "check_v10_cloudflare_postmerge_release_gate",
            "--source-branch main",
            "validate-domain-config",
            "probe-runtime-secret",
            "Quarantine stale production Builds before rollback snapshot",
            "--quarantine-only",
            "snapshot-active-deployment",
            "run_v10_cloudflare_gated_production",
            "attach-domain",
            "probe_v10_cloudflare_live_release.sh",
            "wrangler rollback",
            "previous_version_id",
            "OMNI_V10_PRODUCTION_DEPLOY_ATTEMPTED=1",
        ):
            self.assertIn(marker, self.workflow)
        self.assertNotIn("continue-on-error: true", self.workflow)
        self.assertNotIn("actions/checkout@", self.workflow)
        self.assertNotIn("actions/upload-artifact@", self.workflow)

    def test_only_missing_secret_recovery_jobs_use_hosted_runner(self) -> None:
        hosted_staging = _section(
            self.workflow,
            "  bootstrap_staging_database:\n",
            "  rehearse:\n",
        )
        hosted_production = _section(
            self.workflow,
            "  bootstrap_production_database:\n",
            "  promote:\n",
        )
        self.assertIn("runs-on: ubuntu-24.04", hosted_staging)
        self.assertIn("runs-on: ubuntu-24.04", hosted_production)
        self.assertIn(
            "if: needs.inspect_database_state.outputs.staging_bootstrap_required "
            "== 'true'",
            hosted_staging,
        )
        self.assertIn(
            "if: needs.rehearse.outputs.production_bootstrap_required == 'true'",
            hosted_production,
        )
        self.assertEqual(self.workflow.count("runs-on: ubuntu-24.04"), 2)
        self.assertEqual(
            self.workflow.count(
                "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
            ),
            2,
        )

    def test_neon_credentials_are_confined_to_hosted_recovery_jobs(self) -> None:
        inspect = _section(
            self.workflow,
            "  inspect_database_state:\n",
            "  bootstrap_staging_database:\n",
        )
        rehearse = _section(
            self.workflow,
            "  rehearse:\n",
            "  bootstrap_production_database:\n",
        )
        promote = _section(self.workflow, "  promote:\n", None)
        hosted_staging = _section(
            self.workflow,
            "  bootstrap_staging_database:\n",
            "  rehearse:\n",
        )
        hosted_production = _section(
            self.workflow,
            "  bootstrap_production_database:\n",
            "  promote:\n",
        )
        for self_hosted in (inspect, rehearse, promote):
            self.assertNotIn("secrets.NEON_API_KEY", self_hosted)
            self.assertNotIn("secrets.NEON_ORG_ID", self_hosted)
            self.assertNotIn("secrets.NEON_PROJECT_ID", self_hosted)
        for hosted in (hosted_staging, hosted_production):
            self.assertIn("secrets.NEON_API_KEY", hosted)
            self.assertIn("secrets.NEON_ORG_ID", hosted)
            self.assertIn("secrets.NEON_PROJECT_ID", hosted)
            pre_steps = hosted.split("    steps:\n", 1)[0]
            self.assertNotIn("secrets.NEON_API_KEY", pre_steps)
            self.assertNotIn("secrets.CLOUDFLARE_API_TOKEN", pre_steps)

    def test_production_custody_is_resynced_inside_hosted_job(self) -> None:
        hosted_production = _section(
            self.workflow,
            "  bootstrap_production_database:\n",
            "  promote:\n",
        )
        self.assertIn("bootstrap-production", hosted_production)
        self.assertNotIn("branch_binding", self.workflow.lower())
        self.assertNotIn("branch_id:", self.workflow)
        self.assertNotIn("neon_branch_id", self.workflow.lower())
        self.assertNotIn("upload-artifact", self.workflow)
        self.assertIn("bootstrap_origin_sync_token", self.adapter)
        self.assertIn("fetch_bootstrap_origin_custody", self.adapter)
        self.assertIn("write_bootstrap_origin_handoff", self.adapter)
        self.assertNotIn("branches?limit=100", self.adapter)

    def test_dsn_never_crosses_job_outputs_or_artifacts(self) -> None:
        outputs = []
        for line in self.workflow.splitlines():
            if "outputs:" in line or "${{ steps." in line and ".outputs." in line:
                outputs.append(line)
        rendered = "\n".join(outputs).lower()
        self.assertNotIn("dsn", rendered)
        self.assertNotIn("postgres", rendered)
        self.assertNotIn("artifact", self.workflow.lower())

    def test_hosted_dependency_projection_is_derived_from_canonical_lock(self) -> None:
        self.assertEqual(
            self.workflow.count("build_v10_cloudflare_hosted_control_plane_lock"),
            2,
        )
        self.assertNotIn(
            "requirements.cloudflare-control-plane-linux.txt",
            self.workflow,
        )
        self.assertIn("--require-hashes --no-deps --force-reinstall", self.workflow)

    def test_legacy_neon_function_transport_is_not_reactivated(self) -> None:
        for source in (self.workflow, self.adapter):
            self.assertNotIn("NEON_FUNCTION_DEPLOY_API_KEY", source)
            self.assertNotIn("deploy_v10_cloudflare_neon_bootstrap_function", source)
            self.assertNotIn("functions:invoke", source)

    def test_promotion_requires_applicable_hosted_recovery_success(self) -> None:
        promote = _section(self.workflow, "  promote:\n", None)
        self.assertIn("always()", promote)
        self.assertIn("needs.rehearse.result == 'success'", promote)
        self.assertIn(
            "needs.rehearse.outputs.production_bootstrap_required == 'false'",
            promote,
        )
        self.assertIn(
            "needs.bootstrap_production_database.result == 'success'",
            promote,
        )

    def test_staging_rehearsal_requires_applicable_hosted_recovery_success(
        self,
    ) -> None:
        rehearse = _section(
            self.workflow,
            "  rehearse:\n",
            "  bootstrap_production_database:\n",
        )
        self.assertIn("needs.inspect_database_state.result == 'success'", rehearse)
        self.assertIn(
            "needs.inspect_database_state.outputs.staging_bootstrap_required "
            "== 'false'",
            rehearse,
        )
        self.assertIn(
            "needs.bootstrap_staging_database.result == 'success'",
            rehearse,
        )

    def test_architecture_and_failure_learning_are_tracked(self) -> None:
        self.assertTrue(_ARCHITECTURE.is_file())
        self.assertTrue(_FAILURE_LEDGER.is_file())
        architecture = _ARCHITECTURE.read_text(encoding="utf-8")
        failure = _FAILURE_LEDGER.read_text(encoding="utf-8")
        for marker in (
            "GITHUB_HOSTED_MISSING_SECRET_RECOVERY_ONLY",
            "HOSTED_EPHEMERAL_BRANCH_CUSTODY_RESYNC",
            "DSN_JOB_BOUNDARY_FORBIDDEN",
            "LEGACY_NEON_FUNCTION_TRANSPORT_REMAINS_INACTIVE",
        ):
            self.assertIn(marker, architecture)
        self.assertIn("CF_D_NEON_SELF_HOSTED_EGRESS_BLOCKS_RUNTIME_BOOTSTRAP", failure)
        self.assertIn("Production Release #71", failure)


if __name__ == "__main__":
    unittest.main()
