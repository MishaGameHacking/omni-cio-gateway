from __future__ import annotations

import unittest
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
_ADAPTER = _ROOT / "scripts/bootstrap_v10_cloudflare_neon_hosted_egress.py"
_FAILURE_LEDGER = (
    _ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL157.md"
)
_DAG_FAILURE_LEDGER = (
    _ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL158.md"
)
_IMPORT_FAILURE_LEDGER = (
    _ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL160.md"
)
_VERSION_BOUND_FAILURE_LEDGER = (
    _ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL161.md"
)
_ARCHITECTURE = _ROOT / "docs/architecture/V10_CLOUDFLARE_NEON_HOSTED_EGRESS_BRIDGE.md"


def _section(source: str, start: str, end: str | None) -> str:
    tail = source.split(start, 1)[1]
    return tail if end is None else tail.split(end, 1)[0]


def _job_header(section: str) -> str:
    return section.split("    steps:\n", 1)[0]


class CloudflareCfDHostedEgressRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = _WORKFLOW.read_text(encoding="utf-8")
        cls.adapter = _ADAPTER.read_text(encoding="utf-8")

    def test_workflow_is_archive_in_place_and_cannot_mutate_provider(self) -> None:
        self.assertIn("ARCHIVE-IN-PLACE", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("workflow_run:", self.workflow)
        self.assertNotIn("- Regression Shield", self.workflow)
        self.assertEqual(self.workflow.count("      false &&"), 6)

        for historical_marker in (
            "check_v10_cloudflare_postmerge_release_gate",
            "--source-branch main",
            "validate-domain-config",
            "probe-runtime-secret",
            "run_v10_cloudflare_gated_production",
            "attach-domain",
            "probe_v10_cloudflare_live_release.sh",
            "wrangler rollback",
        ):
            self.assertIn(historical_marker, self.workflow)

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
        self.assertIn("!cancelled()", _job_header(hosted_staging))
        self.assertIn("needs.inspect_database_state.result == 'success'", hosted_staging)
        self.assertIn(
            "needs.inspect_database_state.outputs.staging_bootstrap_required == 'true'",
            hosted_staging,
        )
        self.assertIn("!cancelled()", _job_header(hosted_production))
        self.assertIn("needs.rehearse.result == 'success'", hosted_production)
        self.assertIn(
            "needs.rehearse.outputs.production_bootstrap_required == 'true'",
            hosted_production,
        )
        self.assertEqual(self.workflow.count("runs-on: ubuntu-24.04"), 3)
        self.assertEqual(
            self.workflow.count(
                "uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
            ),
            2,
        )

    def test_provider_mutating_jobs_are_cancellation_safe(self) -> None:
        provider_mutating_jobs = (
            _section(
                self.workflow,
                "  bootstrap_staging_database:\n",
                "  rehearse:\n",
            ),
            _section(
                self.workflow,
                "  rehearse:\n",
                "  bootstrap_production_database:\n",
            ),
            _section(
                self.workflow,
                "  bootstrap_production_database:\n",
                "  promote:\n",
            ),
            _section(self.workflow, "  promote:\n", "  release_outcome:\n"),
        )
        for job in provider_mutating_jobs:
            header = _job_header(job)
            self.assertIn("!cancelled()", header)
            self.assertNotIn("always()", header)
        self.assertEqual(self.workflow.count("!cancelled()"), 4)

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
        promote = _section(self.workflow, "  promote:\n", "  release_outcome:\n")
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
        self.assertIn('gated.run(expected_sha, source_branch="main")', self.adapter)
        for forbidden in (
            "bootstrap_origin_sync_token",
            "fetch_bootstrap_origin_custody",
            "assert_staging_exact_release",
            "write_bootstrap_origin_handoff",
        ):
            self.assertNotIn(forbidden, self.adapter)
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
            self.workflow.count(
                "python -m scripts.build_v10_cloudflare_hosted_control_plane_lock"
            ),
            2,
        )
        self.assertNotIn(
            "requirements.cloudflare-control-plane-linux.txt",
            self.workflow,
        )
        self.assertIn("--require-hashes --no-deps --force-reinstall", self.workflow)
        self.assertEqual(
            self.workflow.count("verify_installed_control_plane_versions"),
            2,
        )
        self.assertNotIn("expected={'psycopg':'3.3.4'", self.workflow)

    def test_legacy_neon_function_transport_is_not_reactivated(self) -> None:
        for source in (self.workflow, self.adapter):
            self.assertNotIn("NEON_FUNCTION_DEPLOY_API_KEY", source)
            self.assertNotIn("deploy_v10_cloudflare_neon_bootstrap_function", source)
            self.assertNotIn("functions:invoke", source)

    def test_promotion_requires_applicable_hosted_recovery_success(self) -> None:
        promote = _section(self.workflow, "  promote:\n", "  release_outcome:\n")
        self.assertIn("!cancelled()", _job_header(promote))
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
        self.assertIn("!cancelled()", _job_header(rehearse))
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

    def test_terminal_release_gate_rejects_required_recovery_skip(self) -> None:
        terminal = _section(self.workflow, "  release_outcome:\n", None)
        header = _job_header(terminal)
        self.assertIn("always()", header)
        self.assertNotIn("!cancelled()", header)
        for marker in (
            "needs.inspect_database_state.result",
            "needs.inspect_database_state.outputs.staging_bootstrap_required",
            "needs.bootstrap_staging_database.result",
            "needs.rehearse.result",
            "needs.rehearse.outputs.production_bootstrap_required",
            "needs.bootstrap_production_database.result",
            "needs.promote.result",
            'if [ "$STAGING_REQUIRED" = "true" ]; then',
            'test "$STAGING_RECOVERY_RESULT" = "success"',
            'if [ "$PRODUCTION_REQUIRED" = "true" ]; then',
            'test "$PRODUCTION_RECOVERY_RESULT" = "success"',
            'test "$PROMOTE_RESULT" = "success"',
            "CLOUDFLARE_RELEASE_DAG=TERMINAL_SUCCESS",
        ):
            self.assertIn(marker, terminal)
        self.assertNotIn("secrets.", terminal)

    def test_architecture_and_failure_learning_are_tracked(self) -> None:
        self.assertTrue(_ARCHITECTURE.is_file())
        self.assertTrue(_FAILURE_LEDGER.is_file())
        self.assertTrue(_DAG_FAILURE_LEDGER.is_file())
        self.assertTrue(_IMPORT_FAILURE_LEDGER.is_file())
        self.assertTrue(_VERSION_BOUND_FAILURE_LEDGER.is_file())
        architecture = _ARCHITECTURE.read_text(encoding="utf-8")
        failure = _FAILURE_LEDGER.read_text(encoding="utf-8")
        dag_failure = _DAG_FAILURE_LEDGER.read_text(encoding="utf-8")
        import_failure = _IMPORT_FAILURE_LEDGER.read_text(encoding="utf-8")
        version_bound_failure = _VERSION_BOUND_FAILURE_LEDGER.read_text(
            encoding="utf-8"
        )
        for marker in (
            "GITHUB_HOSTED_MISSING_SECRET_RECOVERY_ONLY",
            "HOSTED_EPHEMERAL_BRANCH_CUSTODY_RESYNC",
            "HOSTED_CUSTODY_REUSES_VERSION_BOUND_CANDIDATE",
            "DSN_JOB_BOUNDARY_FORBIDDEN",
            "LEGACY_NEON_FUNCTION_TRANSPORT_REMAINS_INACTIVE",
        ):
            self.assertIn(marker, architecture)
        self.assertIn("CF_D_NEON_SELF_HOSTED_EGRESS_BLOCKS_RUNTIME_BOOTSTRAP", failure)
        self.assertIn("Production Release #71", failure)
        self.assertIn("CF_D_REQUIRED_RECOVERY_SKIP_PROPAGATION", dag_failure)
        self.assertIn("CANCELLATION_FAIL_CLOSED", dag_failure)
        self.assertIn("Production Release #72", dag_failure)
        self.assertIn(
            "CF_D_HOSTED_RECOVERY_INCOMPLETE_IMPORT_CLOSURE",
            import_failure,
        )
        self.assertIn("Production Release #74", import_failure)
        self.assertIn("PYDANTIC_IMPORT_CLOSURE_EXPLICIT", architecture)
        self.assertIn(
            "CF_D_HOSTED_CUSTODY_TOKEN_AFTER_EXACT_BUILD",
            version_bound_failure,
        )
        self.assertIn("Production Release #75", version_bound_failure)


if __name__ == "__main__":
    unittest.main()
