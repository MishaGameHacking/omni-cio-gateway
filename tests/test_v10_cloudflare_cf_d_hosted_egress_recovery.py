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

_RETIRED_JOBS = (
    "inspect_database_state",
    "bootstrap_staging_database",
    "rehearse",
    "bootstrap_production_database",
    "promote",
    "release_outcome",
)


def _job_header(source: str, job_id: str, next_job_id: str | None) -> str:
    start = source.index(f"  {job_id}:\n")
    if next_job_id is None:
        section = source[start:]
    else:
        end = source.index(f"  {next_job_id}:\n", start + 1)
        section = source[start:end]
    return section.split("    steps:\n", 1)[0]


class CloudflareCfDHostedEgressRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = _WORKFLOW.read_text(encoding="utf-8")
        cls.adapter = _ADAPTER.read_text(encoding="utf-8")

    def test_workflow_is_archive_in_place_and_cannot_execute_provider_jobs(
        self,
    ) -> None:
        self.assertIn("ARCHIVE-IN-PLACE", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("workflow_run:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)
        self.assertEqual(self.workflow.count("if: ${{ false }}"), 6)
        self.assertNotIn("false &&", self.workflow)
        self.assertNotIn("actions/checkout@", self.workflow)
        self.assertNotIn("actions/upload-artifact@", self.workflow)
        self.assertNotIn("continue-on-error: true", self.workflow)

    def test_every_historical_release_job_is_unconditionally_disabled(self) -> None:
        for index, job_id in enumerate(_RETIRED_JOBS):
            next_job_id = (
                _RETIRED_JOBS[index + 1] if index + 1 < len(_RETIRED_JOBS) else None
            )
            header = _job_header(self.workflow, job_id, next_job_id)
            with self.subTest(job_id=job_id):
                self.assertIn("if: ${{ false }}", header)

    def test_historical_release_logic_remains_archive_evidence_only(self) -> None:
        for marker in (
            "check_v10_cloudflare_postmerge_release_gate",
            "bootstrap-staging",
            "bootstrap-production",
            "run_v10_cloudflare_gated_candidate",
            "run_v10_cloudflare_gated_production",
            "attach-domain",
            "probe_v10_cloudflare_live_release.sh",
            "wrangler rollback",
            "CLOUDFLARE_RELEASE_DAG=TERMINAL_SUCCESS",
        ):
            self.assertIn(marker, self.workflow)

    def test_legacy_function_transport_is_not_reactivated(self) -> None:
        for source in (self.workflow, self.adapter):
            self.assertNotIn("NEON_FUNCTION_DEPLOY_API_KEY", source)
            self.assertNotIn("deploy_v10_cloudflare_neon_bootstrap_function", source)
            self.assertNotIn("functions:invoke", source)

    def test_historical_dsn_never_crosses_job_outputs_or_artifacts(self) -> None:
        outputs = []
        for line in self.workflow.splitlines():
            if "outputs:" in line or "${{ steps." in line and ".outputs." in line:
                outputs.append(line)
        rendered = "\n".join(outputs).lower()
        self.assertNotIn("dsn", rendered)
        self.assertNotIn("postgres", rendered)
        self.assertNotIn("artifact", self.workflow.lower())

    def test_architecture_and_failure_learning_are_preserved(self) -> None:
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
        self.assertIn("CF_D_REQUIRED_RECOVERY_SKIP_PROPAGATION", dag_failure)
        self.assertIn("CF_D_HOSTED_RECOVERY_INCOMPLETE_IMPORT_CLOSURE", import_failure)
        self.assertIn(
            "CF_D_HOSTED_CUSTODY_TOKEN_AFTER_EXACT_BUILD",
            version_bound_failure,
        )


if __name__ == "__main__":
    unittest.main()
