from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import scripts.probe_v10_cloudflare_container_registry_authority as registry


class CloudflareContainerRegistryAuthorityTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        node = root / "node.exe"
        node.write_text("test-node", encoding="utf-8")
        wrangler = root / "node_modules" / "wrangler" / "bin" / "wrangler.js"
        wrangler.parent.mkdir(parents=True)
        wrangler.write_text("test-wrangler", encoding="utf-8")
        return node, wrangler

    @staticmethod
    def _environment() -> dict[str, str]:
        return {
            "CLOUDFLARE_API_TOKEN": "synthetic-sensitive-token",
            "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        }

    def test_read_probe_is_exact_silent_and_privacy_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            node, wrangler = self._fixture(root)
            output = StringIO()
            completed = subprocess.CompletedProcess([], 0)
            with (
                patch.object(registry, "_REPO_ROOT", root),
                patch.object(registry.subprocess, "run", return_value=completed) as runner,
            ):
                status = registry.probe_container_registry_authority(
                    self._environment(),
                    output=output,
                    node_executable=node,
                    wrangler_cli=wrangler,
                )

        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), "CLOUDFLARE_CONTAINERS_REGISTRY_READ=READY\n")
        command = runner.call_args.args[0]
        kwargs = runner.call_args.kwargs
        self.assertEqual(
            command,
            (
                str(node.resolve()),
                str(wrangler.resolve()),
                "containers",
                "images",
                "list",
                "--json",
            ),
        )
        self.assertEqual(kwargs["cwd"], root)
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["timeout"], registry._PROBE_TIMEOUT_SECONDS)
        self.assertNotIn("shell", kwargs)
        report = output.getvalue()
        self.assertNotIn("synthetic-sensitive-token", report)
        self.assertNotIn("a" * 32, report)

    def test_provider_denial_is_controlled_and_never_echoes_provider_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            node, wrangler = self._fixture(root)
            output = StringIO()
            completed = subprocess.CompletedProcess([], 1)
            with (
                patch.object(registry, "_REPO_ROOT", root),
                patch.object(registry.subprocess, "run", return_value=completed),
            ):
                status = registry.probe_container_registry_authority(
                    self._environment(),
                    output=output,
                    node_executable=node,
                    wrangler_cli=wrangler,
                )

        self.assertEqual(status, registry._PROVIDER_BLOCKED)
        self.assertEqual(
            output.getvalue(),
            "CLOUDFLARE_CONTAINERS_REGISTRY_READ=BLOCKED "
            "code=CLOUDFLARE_CONTAINERS_REGISTRY_AUTHORITY_REQUIRED\n",
        )
        self.assertNotIn("synthetic-sensitive-token", output.getvalue())
        self.assertNotIn("a" * 32, output.getvalue())

    def test_probe_timeout_fails_closed_without_retry_or_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            node, wrangler = self._fixture(root)
            output = StringIO()
            timeout = subprocess.TimeoutExpired(["node"], registry._PROBE_TIMEOUT_SECONDS)
            with (
                patch.object(registry, "_REPO_ROOT", root),
                patch.object(registry.subprocess, "run", side_effect=timeout) as runner,
            ):
                status = registry.probe_container_registry_authority(
                    self._environment(),
                    output=output,
                    node_executable=node,
                    wrangler_cli=wrangler,
                )

        self.assertEqual(status, registry._PROVIDER_BLOCKED)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(
            output.getvalue(),
            "CLOUDFLARE_CONTAINERS_REGISTRY_READ=BLOCKED "
            "code=CLOUDFLARE_CONTAINERS_REGISTRY_PROBE_TIMEOUT\n",
        )

    def test_missing_or_malformed_authority_fails_before_process_execution(self) -> None:
        cases = (
            ({"CLOUDFLARE_ACCOUNT_ID": "a" * 32}, "CLOUDFLARE_API_TOKEN_REQUIRED"),
            (
                {"CLOUDFLARE_API_TOKEN": "synthetic", "CLOUDFLARE_ACCOUNT_ID": "bad"},
                "CLOUDFLARE_ACCOUNT_ID_INVALID",
            ),
        )
        for environment, code in cases:
            with self.subTest(code=code):
                with patch.object(registry.subprocess, "run") as runner:
                    with self.assertRaisesRegex(RuntimeError, code):
                        registry.probe_container_registry_authority(environment)
                runner.assert_not_called()

    def test_wrangler_probe_path_cannot_escape_repository_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            node_modules = root / "node_modules"
            node_modules.mkdir()
            outside = root / "wrangler.js"
            outside.write_text("outside", encoding="utf-8")
            with patch.object(registry, "_REPO_ROOT", root):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_CONTAINER_PROBE_WRANGLER_UNAVAILABLE",
                ):
                    registry._wrangler_cli(outside)

    def test_candidate_workflow_runs_registry_probe_before_any_provider_mutation(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (
            root / ".github/workflows/v10-cloudflare-candidate-deploy.yml"
        ).read_text(encoding="utf-8")
        toolchain = workflow.find("- name: Install exact Cloudflare delivery toolchain")
        probe = workflow.find(
            "- name: Verify Cloudflare Containers registry read authority"
        )
        probe_command = workflow.find(
            "python -m scripts.probe_v10_cloudflare_container_registry_authority"
        )
        mutations = tuple(
            workflow.find(marker)
            for marker in (
                "- name: Provision isolated Neon staging runtime role",
                "- name: Bootstrap isolated staging Worker without local Containers",
                "- name: Configure Workers Builds and accept exact staging build",
            )
        )
        self.assertGreaterEqual(toolchain, 0)
        self.assertGreater(probe, toolchain)
        self.assertGreaterEqual(probe_command, probe)
        self.assertTrue(all(index > probe_command for index in mutations))

    def test_container_deploy_authority_contract_preserves_fail_closed_boundaries(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        contract = json.loads(
            (
                root
                / "docs/architecture/V10_CLOUDFLARE_CONTAINER_DEPLOY_AUTHORITY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(contract["milestone"], "CF-C")
        authority = contract["authority"]
        self.assertFalse(
            authority[
                "default_workers_builds_token_may_be_assumed_to_include_containers_permissions"
            ]
        )
        self.assertFalse(authority["read_probe_success_is_candidate_deploy_acceptance"])
        self.assertTrue(authority["real_exact_sha_container_build_and_live_probe_still_required"])
        probe = contract["pre_mutation_probe"]
        self.assertEqual(probe["operation"], "READ_ONLY")
        self.assertTrue(probe["must_run_before_neon_or_cloudflare_candidate_mutation"])
        self.assertTrue(probe["stdout_must_be_suppressed"])
        self.assertTrue(probe["stderr_must_be_suppressed"])
        self.assertEqual(probe["blocked_exit_code"], 78)
        protected = contract["protected_invariants"]
        self.assertFalse(protected["PUBLIC_MULTI_USER_ENABLED"])
        self.assertFalse(protected["telegram_vk_provider_activation"])
        self.assertFalse(protected["broker_write"])
        self.assertFalse(protected["trading_methods"])
        self.assertFalse(protected["REAL_TRADING_ENABLED"])
        self.assertFalse(protected["cf_d_unlocked_before_cf_c_acceptance"])


if __name__ == "__main__":
    unittest.main()
