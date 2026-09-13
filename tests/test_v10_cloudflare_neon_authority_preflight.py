from __future__ import annotations

from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_provider_readiness as readiness


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"
NEON_PROJECT_AUTHORITY_PROBE = "probe_provider_access_from_env()"
NEON_PROVISION = "python -m scripts.provision_v10_cloudflare_neon_runtime"
LEGACY_FUNCTION_BOOTSTRAP = (
    "python -m scripts.bootstrap_v10_cloudflare_production_database_direct"
)
FUNCTION_DEPLOY_BINDING = (
    "NEON_FUNCTION_DEPLOY_API_KEY: ${{ secrets.NEON_FUNCTION_DEPLOY_API_KEY }}"
)
FUNCTION_PROJECT_BINDING = "NEON_PROJECT_ID: ${{ secrets.NEON_PROJECT_ID }}"
RUNTIME_AUTHORITY_BINDING = "NEON_API_KEY: ${{ secrets.NEON_API_KEY }}"
NEON_ORG_BINDING = "NEON_ORG_ID: ${{ secrets.NEON_ORG_ID }}"


class CloudflareNeonAuthorityPreflightTests(unittest.TestCase):
    @staticmethod
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _cloudflare_environment() -> dict[str, str]:
        return {
            readiness._CLOUDFLARE_AUTHORITY_ENV: "synthetic-cf-token",
            readiness._CLOUDFLARE_ACCOUNT_ENV: "a" * 32,
        }

    @staticmethod
    def _workflow_step(source: str, name: str) -> str:
        start = source.index(f"      - name: {name}")
        end = source.index("\n      - name:", start + 1)
        return source[start:end]

    def _assert_probe_precedes(self, source: str, markers: tuple[str, ...]) -> None:
        self.assertEqual(source.count(NEON_PROJECT_AUTHORITY_PROBE), 1)
        probe_index = source.index(NEON_PROJECT_AUTHORITY_PROBE)
        for marker in markers:
            with self.subTest(marker=marker):
                marker_index = source.index(marker)
                self.assertLess(probe_index, marker_index)

    def test_candidate_neon_authority_is_read_before_provider_mutation(self) -> None:
        source = self._read(CANDIDATE_WORKFLOW)
        self._assert_probe_precedes(
            source,
            (
                "- name: Quarantine stale automatic staging trigger",
                "- name: Install exact Cloudflare delivery toolchain",
                "- name: Provision isolated Neon staging runtime role",
                "- name: Bootstrap isolated staging Worker without local Containers",
                "- name: Configure Workers Builds and accept exact staging build",
            ),
        )

    def test_production_staging_recovery_separates_probe_and_neon_authority(
        self,
    ) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        self.assertEqual(source.count(NEON_PROJECT_AUTHORITY_PROBE), 1)
        self.assertEqual(source.count(NEON_PROVISION), 2)

        probe = self._workflow_step(
            source,
            "Probe reusable staging runtime secret before Neon management API",
        )
        bootstrap = self._workflow_step(
            source,
            "Bootstrap staging database secret if missing",
        )
        rehearsal = self._workflow_step(
            source,
            "Rehearse exact accepted main on isolated staging Worker and Container",
        )

        self.assertIn("probe_v10_cloudflare_staging_runtime_secret", probe)
        self.assertIn('echo "bootstrap_required=false" >> "$GITHUB_OUTPUT"', probe)
        self.assertIn('echo "bootstrap_required=true" >> "$GITHUB_OUTPUT"', probe)
        self.assertNotIn("NEON_API_KEY:", probe)
        self.assertNotIn("NEON_ORG_ID:", probe)
        self.assertNotIn("NEON_PROJECT_ID:", probe)

        self.assertIn(
            "steps.staging_database_state.outputs.bootstrap_required == 'true'",
            bootstrap,
        )
        self.assertIn(NEON_PROJECT_AUTHORITY_PROBE, bootstrap)
        self.assertIn(NEON_PROVISION, bootstrap)
        self.assertIn("--environment staging", bootstrap)
        self.assertIn(RUNTIME_AUTHORITY_BINDING, bootstrap)
        self.assertIn(NEON_ORG_BINDING, bootstrap)
        self.assertIn(FUNCTION_PROJECT_BINDING, bootstrap)
        self.assertNotIn(FUNCTION_DEPLOY_BINDING, bootstrap)

        self.assertIn("run_v10_cloudflare_gated_candidate", rehearsal)
        self.assertNotIn("NEON_API_KEY:", rehearsal)
        self.assertNotIn("NEON_ORG_ID:", rehearsal)
        self.assertNotIn("NEON_PROJECT_ID:", rehearsal)
        self.assertNotIn(FUNCTION_DEPLOY_BINDING, rehearsal)

    def test_production_database_bootstrap_uses_runtime_management_credential(
        self,
    ) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        probe = self._workflow_step(source, "Probe production database secret")
        bootstrap = self._workflow_step(
            source,
            "Bootstrap production database secret if missing",
        )
        confirm = self._workflow_step(
            source,
            "Confirm production database secret ready",
        )
        self.assertIn(NEON_PROVISION, bootstrap)
        self.assertIn("--environment production", bootstrap)
        self.assertIn(RUNTIME_AUTHORITY_BINDING, bootstrap)
        self.assertIn(NEON_ORG_BINDING, bootstrap)
        self.assertIn(FUNCTION_PROJECT_BINDING, bootstrap)
        self.assertIn(
            "steps.production_database_state.outputs.bootstrap_required == 'true'",
            bootstrap,
        )
        self.assertNotIn(LEGACY_FUNCTION_BOOTSTRAP, bootstrap)
        self.assertNotIn(FUNCTION_DEPLOY_BINDING, bootstrap)
        self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", bootstrap)
        self.assertNotIn("STAGING_ORIGIN", bootstrap)
        self.assertNotIn("--origin", bootstrap)
        self.assertNotIn("vars.NEON_", bootstrap)
        self.assertNotIn("echo $NEON", bootstrap)
        for section in (probe, confirm):
            self.assertNotIn("NEON_API_KEY:", section)
            self.assertNotIn("NEON_ORG_ID:", section)
            self.assertNotIn("NEON_PROJECT_ID:", section)
            self.assertNotIn("NEON_FUNCTION_DEPLOY_API_KEY", section)
            self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", section)

    def test_legacy_function_secret_is_not_active_release_dependency(self) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        staging_bootstrap = self._workflow_step(
            source,
            "Bootstrap staging database secret if missing",
        )
        production_bootstrap = self._workflow_step(
            source,
            "Bootstrap production database secret if missing",
        )

        for section in (staging_bootstrap, production_bootstrap):
            self.assertIn(RUNTIME_AUTHORITY_BINDING, section)
            self.assertIn(FUNCTION_PROJECT_BINDING, section)
            self.assertIn(NEON_ORG_BINDING, section)
            self.assertNotIn(FUNCTION_DEPLOY_BINDING, section)
            self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", section)

        self.assertNotIn("NEON_FUNCTION_DEPLOY_API_KEY", source)
        self.assertEqual(source.count(RUNTIME_AUTHORITY_BINDING), 2)
        self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", source)

    def test_provider_readiness_cli_defers_neon_until_bootstrap_is_needed(self) -> None:
        output = StringIO()
        environment = self._cloudflare_environment()
        with (
            patch.dict(readiness.os.environ, environment, clear=True),
            patch.object(readiness.shutil, "which", return_value=None),
            patch.object(readiness.sys, "stdout", output),
        ):
            status = readiness.main([])
        report = output.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("CLOUDFLARE_API_TOKEN=AVAILABLE", report)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID=AVAILABLE", report)
        self.assertIn("NEON_BOOTSTRAP_AUTHORITY=DEFERRED_UNTIL_REQUIRED", report)
        self.assertNotIn("NEON_API_KEY=", report)
        self.assertNotIn(environment[readiness._CLOUDFLARE_AUTHORITY_ENV], report)

    def test_provider_readiness_cli_can_still_require_neon_fail_closed(self) -> None:
        output = StringIO()
        with (
            patch.dict(
                readiness.os.environ,
                self._cloudflare_environment(),
                clear=True,
            ),
            patch.object(readiness.shutil, "which", return_value=None),
            patch.object(readiness.sys, "stdout", output),
        ):
            status = readiness.main(["--require-neon"])
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("NEON_API_KEY=MISSING", report)
        self.assertIn("NEON_ORG_ID=MISSING", report)
        self.assertIn("NEON_PROJECT_ID=MISSING", report)
        self.assertIn("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", report)

    def test_deferred_neon_mode_still_blocks_missing_cloudflare_authority(self) -> None:
        output = StringIO()
        environment = self._cloudflare_environment()
        environment[readiness._CLOUDFLARE_AUTHORITY_ENV] = ""
        with patch.object(readiness.shutil, "which", return_value=None):
            status = readiness.check_provider_readiness(
                environment,
                output=output,
                require_neon=False,
            )
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("CLOUDFLARE_API_TOKEN=MISSING", report)
        self.assertIn("NEON_BOOTSTRAP_AUTHORITY=DEFERRED_UNTIL_REQUIRED", report)
        self.assertIn("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", report)

    def test_neon_preflight_uses_only_runtime_management_secret(self) -> None:
        expected_steps = {
            CANDIDATE_WORKFLOW: (
                "Verify Neon exact-project read authority before provider mutation"
            ),
            PRODUCTION_WORKFLOW: "Bootstrap staging database secret if missing",
        }
        for path, step_name in expected_steps.items():
            with self.subTest(path=path.name):
                source = self._read(path)
                section = self._workflow_step(source, step_name)
                self.assertIn(NEON_PROJECT_AUTHORITY_PROBE, section)
                self.assertIn(RUNTIME_AUTHORITY_BINDING, section)
                self.assertIn(NEON_ORG_BINDING, section)
                self.assertIn(FUNCTION_PROJECT_BINDING, section)
                self.assertNotIn(FUNCTION_DEPLOY_BINDING, section)
                self.assertNotIn("vars.NEON_", section)
                self.assertNotIn("echo $NEON", section)


if __name__ == "__main__":
    unittest.main()
