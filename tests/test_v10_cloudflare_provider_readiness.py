from __future__ import annotations

from io import StringIO
import subprocess
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.check_v10_cloudflare_provider_readiness as readiness


class _BuildTokenApi:
    account_id = "a" * 32
    token = "provider-value"

    def __init__(self) -> None:
        self.created_body: dict[str, object] | None = None

    def request(self, method: str, path: str, **kwargs):
        if method == "GET" and path.endswith("/builds/tokens?per_page=200"):
            return []
        if method == "POST" and path.endswith("/builds/tokens"):
            self.created_body = kwargs.get("body")
            return {"build_token_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        raise AssertionError((method, path))


class CloudflareProviderReadinessTests(unittest.TestCase):
    @staticmethod
    def _complete_environment() -> dict[str, str]:
        return {
            readiness._CLOUDFLARE_AUTHORITY_ENV: "cf-value",
            readiness._CLOUDFLARE_ACCOUNT_PRIMARY_ENV: "account-value",
            readiness._NEON_AUTHORITY_ENV: "neon-value",
            readiness._NEON_ORGANIZATION_ENV: "org-value",
        }

    def test_complete_authority_with_docker_selects_direct_deploy(self) -> None:
        output = StringIO()
        completed = subprocess.CompletedProcess(["docker", "info"], 0)
        with (
            patch.object(readiness.shutil, "which", return_value="docker"),
            patch.object(readiness.subprocess, "run", return_value=completed),
        ):
            status = readiness.check_provider_readiness(
                self._complete_environment(),
                output=output,
            )
        self.assertEqual(status, 0)
        self.assertIn(
            "CLOUDFLARE_DEPLOY_PATH=DIRECT_WRANGLER_AVAILABLE", output.getvalue()
        )

    def test_missing_authority_blocks_without_revealing_values(self) -> None:
        environment = self._complete_environment()
        environment[readiness._NEON_AUTHORITY_ENV] = ""
        output = StringIO()
        with patch.object(readiness.shutil, "which", return_value=None):
            status = readiness.check_provider_readiness(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("NEON_API_KEY=MISSING", report)
        self.assertIn("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", report)
        for value in environment.values():
            if value:
                self.assertNotIn(value, report)

    def test_missing_docker_selects_workers_builds_without_blocking(self) -> None:
        output = StringIO()
        with patch.object(readiness.shutil, "which", return_value=None):
            status = readiness.check_provider_readiness(
                self._complete_environment(),
                output=output,
            )
        self.assertEqual(status, 0)
        self.assertIn("CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS", output.getvalue())

    def test_unhealthy_docker_selects_workers_builds_without_blocking(self) -> None:
        output = StringIO()
        completed = subprocess.CompletedProcess(["docker", "info"], 1)
        with (
            patch.object(readiness.shutil, "which", return_value="docker"),
            patch.object(readiness.subprocess, "run", return_value=completed),
        ):
            status = readiness.check_provider_readiness(
                self._complete_environment(),
                output=output,
            )
        self.assertEqual(status, 0)
        self.assertIn("CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS", output.getvalue())

    def test_build_token_payload_uses_provider_field_without_scan_allowlist(
        self,
    ) -> None:
        api = _BuildTokenApi()
        identifier = builds._ensure_build_token(api, "b" * 32)
        self.assertEqual(identifier, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertIsNotNone(api.created_body)
        assert api.created_body is not None
        self.assertEqual(
            api.created_body[builds._BUILD_TOKEN_VALUE_FIELD],
            api.token,
        )
        self.assertEqual(
            set(api.created_body),
            {
                "build_token_name",
                builds._BUILD_TOKEN_VALUE_FIELD,
                "cloudflare_token_id",
            },
        )


if __name__ == "__main__":
    unittest.main()
