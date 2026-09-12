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
RECOVERY_ALIAS_BINDING = "NEON_API_KEY: ${{ secrets.NEON_FUNCTION_DEPLOY_API_KEY }}"
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

    def test_production_staging_recovery_probe_precedes_staging_provision(self) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        self.assertEqual(source.count(NEON_PROJECT_AUTHORITY_PROBE), 1)
        self.assertEqual(source.count(NEON_PROVISION), 2)

        staging_secret_probe = source.index(
            "python -m scripts.probe_v10_cloudflare_staging_runtime_secret"
        )
        provider_probe = source.index(NEON_PROJECT_AUTHORITY_PROBE)
        staging_provision = source.index("--environment staging", provider_probe)
        production_secret_probe = source.index(
            "python -m scripts.manage_v10_cloudflare_production probe-runtime-secret"
        )
        production_provision = source.index(
            "--environment production", production_secret_probe
        )

        self.assertLess(staging_secret_probe, provider_probe)
        self.assertLess(provider_probe, staging_provision)
        self.assertLess(staging_provision, production_secret_probe)
        self.assertLess(production_secret_probe, production_provision)
        self.assertIn(
            'if [ "$neon_rc" -ne 0 ]; then',
            source[provider_probe:staging_provision],
        )

    def test_production_database_bootstrap_uses_project_scoped_runtime_provisioner(
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
        self.assertIn(RECOVERY_ALIAS_BINDING, bootstrap)
        self.assertIn(NEON_ORG_BINDING, bootstrap)
        self.assertIn(FUNCTION_PROJECT_BINDING, bootstrap)
        self.assertIn(
            "steps.production_database_state.outputs.bootstrap_required == 'true'",
            bootstrap,
        )
        self.assertNotIn(LEGACY_FUNCTION_BOOTSTRAP, bootstrap)
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

    def test_function_invoke_secret_is_not_a_release_dependency(self) -> None:
        source = self._read(PRODUCTION_WORKFLOW)
        candidate = self._workflow_step(
            source,
            "Rehearse exact accepted main on isolated staging Worker and Container",
        )
        production_bootstrap = self._workflow_step(
            source,
            "Bootstrap production database secret if missing",
        )

        self.assertIn(FUNCTION_DEPLOY_BINDING, candidate)
        self.assertIn(FUNCTION_PROJECT_BINDING, candidate)
        self.assertIn(RECOVERY_ALIAS_BINDING, candidate)
        self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", candidate)
        self.assertIn(FUNCTION_PROJECT_BINDING, production_bootstrap)
        self.assertIn(RECOVERY_ALIAS_BINDING, production_bootstrap)
        self.assertIn(NEON_ORG_BINDING, production_bootstrap)
        self.assertNotIn(FUNCTION_DEPLOY_BINDING, production_bootstrap)
        self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", production_bootstrap)
        self.assertEqual(source.count(FUNCTION_DEPLOY_BINDING), 1)
        self.assertEqual(source.count(RECOVERY_ALIAS_BINDING), 2)
        self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", source)
        self.assertNotIn("echo $NEON_FUNCTION_DEPLOY_API_KEY", source)

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

    def test_neon_preflight_uses_only_runtime_secret_bindings(self) -> None:
        expected_bindings = {
            CANDIDATE_WORKFLOW: "NEON_API_KEY: ${{ secrets.NEON_API_KEY }}",
            PRODUCTION_WORKFLOW: RECOVERY_ALIAS_BINDING,
        }
        for path, authority_binding in expected_bindings.items():
            with self.subTest(path=path.name):
                source = self._read(path)
                probe_indexes = [
                    index
                    for index in range(len(source))
                    if source.startswith(NEON_PROJECT_AUTHORITY_PROBE, index)
                ]
                self.assertGreaterEqual(len(probe_indexes), 1)
                for probe_index in probe_indexes:
                    section_start = source.rfind("      - name:", 0, probe_index)
                    section_end = source.find("\n      - name:", probe_index)
                    self.assertGreaterEqual(section_start, 0)
                    self.assertGreater(section_end, probe_index)
                    section = source[section_start:section_end]
                    self.assertIn(authority_binding, section)
                    self.assertIn(NEON_ORG_BINDING, section)
                    self.assertIn(FUNCTION_PROJECT_BINDING, section)
                    self.assertNotIn("vars.NEON_", section)
                    self.assertNotIn("echo $NEON", section)


if __name__ == "__main__":
    unittest.main()
