from __future__ import annotations

from io import StringIO
import unittest
from unittest.mock import patch

from scripts.bootstrap_v10_cloudflare_builds import BootstrapStopped
import scripts.probe_v10_cloudflare_workers_builds_authority as probe


class _ReadApi:
    account_id = "a" * 32

    def __init__(self, *, fail_path: str | None = None, token_status: str = "active") -> None:
        self.fail_path = fail_path
        self.token_status = token_status
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        self.calls.append((method, path))
        if path == self.fail_path:
            raise BootstrapStopped("CLOUDFLARE_API_TOKEN_INSUFFICIENT", status=403)
        if path == "/user/tokens/verify":
            return {"id": "b" * 32, "status": self.token_status}
        if path.endswith("/builds/tokens?per_page=1"):
            return []
        if path.endswith("/workers/scripts"):
            return []
        raise AssertionError((method, path))


class CloudflareWorkersBuildsAuthorityTests(unittest.TestCase):
    @staticmethod
    def _environment() -> dict[str, str]:
        return {
            probe._CLOUDFLARE_TOKEN_ENV: "test-provider-authority",
            probe._CLOUDFLARE_ACCOUNT_ENV: "a" * 32,
        }

    def test_read_probe_requires_user_token_and_both_build_authorities(self) -> None:
        api = _ReadApi()
        probe._probe_read_authority(api)
        self.assertEqual(
            api.calls,
            [
                ("GET", "/user/tokens/verify"),
                ("GET", f"/accounts/{api.account_id}/builds/tokens?per_page=1"),
                ("GET", f"/accounts/{api.account_id}/workers/scripts"),
            ],
        )
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_inactive_user_token_fails_closed_before_account_reads(self) -> None:
        api = _ReadApi(token_status="disabled")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_WORKERS_BUILDS_TOKEN_NOT_ACTIVE",
        ):
            probe._probe_read_authority(api)
        self.assertEqual(api.calls, [("GET", "/user/tokens/verify")])

    def test_builds_permission_failure_is_blocked_without_identifier_disclosure(self) -> None:
        api = _ReadApi(
            fail_path=f"/accounts/{'a' * 32}/builds/tokens?per_page=1",
        )
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn(
            "CLOUDFLARE_WORKERS_BUILDS_AUTHORITY=BLOCKED "
            "code=CLOUDFLARE_API_TOKEN_INSUFFICIENT",
            report,
        )
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_success_report_is_privacy_safe(self) -> None:
        api = _ReadApi()
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("CLOUDFLARE_WORKERS_BUILDS_TOKEN_SCOPE=USER_VERIFIED", report)
        self.assertIn("CLOUDFLARE_WORKERS_BUILDS_CONFIGURATION=READABLE", report)
        self.assertIn("CLOUDFLARE_WORKERS_SCRIPTS=READABLE", report)
        self.assertIn("CLOUDFLARE_WORKERS_BUILDS_AUTHORITY=READY", report)
        for value in environment.values():
            self.assertNotIn(value, report)


if __name__ == "__main__":
    unittest.main()
