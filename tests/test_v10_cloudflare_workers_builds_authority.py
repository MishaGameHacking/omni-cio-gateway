from __future__ import annotations

from io import StringIO
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.bootstrap_v10_cloudflare_builds import BootstrapStopped
import scripts.probe_v10_cloudflare_workers_builds_authority as probe


_TOKEN_ID = "b" * 32
_OTHER_TOKEN_ID = "c" * 32
_BUILD_TOKEN_UUID = "11111111-1111-1111-1111-111111111111"


def _build_token_record(
    *,
    token_id: str = _TOKEN_ID,
    owner_type: str = "user",
) -> dict[str, str]:
    return {
        "build_token_name": builds._BUILD_TOKEN_NAME,
        "build_token_uuid": _BUILD_TOKEN_UUID,
        "cloudflare_token_id": token_id,
        "owner_type": owner_type,
    }


class _ReadApi:
    account_id = "a" * 32

    def __init__(
        self,
        *,
        fail_path: str | None = None,
        failure_code: str = "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
        failure_status: int | None = 403,
        token_status: str = "active",
        token_result: object | None = None,
        build_tokens: list[dict[str, str]] | None = None,
    ) -> None:
        self.fail_path = fail_path
        self.failure_code = failure_code
        self.failure_status = failure_status
        self.token_status = token_status
        self.token_result = token_result
        self.build_tokens = [] if build_tokens is None else build_tokens
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs):
        del kwargs
        self.calls.append((method, path))
        if path == self.fail_path:
            raise BootstrapStopped(self.failure_code, status=self.failure_status)
        if path == "/user/tokens/verify":
            if self.token_result is not None:
                return self.token_result
            return {"id": _TOKEN_ID, "status": self.token_status}
        if path.endswith("/builds/tokens?per_page=200"):
            return list(self.build_tokens)
        if path.endswith("/workers/scripts"):
            return []
        raise AssertionError((method, path))


class _BuildTokenApi:
    account_id = "a" * 32
    token = "test-provider-authority"

    def __init__(
        self,
        *,
        rows: list[dict[str, str]],
        created: dict[str, str] | None = None,
    ) -> None:
        self.rows = rows
        self.created = created
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "GET" and path.endswith("/builds/tokens?per_page=200"):
            return list(self.rows)
        if method == "POST" and path.endswith("/builds/tokens"):
            if self.created is None:
                raise AssertionError("unexpected build-token create")
            return dict(self.created)
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
                ("GET", f"/accounts/{api.account_id}/builds/tokens?per_page=200"),
                ("GET", f"/accounts/{api.account_id}/workers/scripts"),
            ],
        )
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_read_probe_validates_existing_named_build_token_binding(self) -> None:
        api = _ReadApi(build_tokens=[_build_token_record()])
        probe._probe_read_authority(api)
        self.assertEqual(
            api.calls[-1],
            ("GET", f"/accounts/{api.account_id}/workers/scripts"),
        )

    def test_read_probe_rejects_existing_build_token_authority_drift(self) -> None:
        for record in (
            _build_token_record(token_id=_OTHER_TOKEN_ID),
            _build_token_record(owner_type="account"),
        ):
            with self.subTest(record=record):
                api = _ReadApi(build_tokens=[record])
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT",
                ):
                    probe._probe_read_authority(api)
                self.assertNotIn(
                    ("GET", f"/accounts/{api.account_id}/workers/scripts"),
                    api.calls,
                )

    def test_inactive_user_token_fails_closed_before_account_reads(self) -> None:
        api = _ReadApi(token_status="disabled")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_WORKERS_BUILDS_TOKEN_NOT_ACTIVE",
        ):
            probe._probe_read_authority(api)
        self.assertEqual(api.calls, [("GET", "/user/tokens/verify")])

    def test_token_verify_permission_failure_reports_exact_safe_stage(self) -> None:
        api = _ReadApi(fail_path="/user/tokens/verify", failure_status=401)
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("code=CLOUDFLARE_API_TOKEN_INSUFFICIENT", report)
        self.assertIn("stage=USER_TOKEN_VERIFY", report)
        self.assertIn("status=401", report)
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_builds_permission_failure_is_blocked_without_identifier_disclosure(self) -> None:
        api = _ReadApi(
            fail_path=f"/accounts/{'a' * 32}/builds/tokens?per_page=200",
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
        self.assertIn("stage=WORKERS_BUILDS_TOKENS", report)
        self.assertIn("status=403", report)
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_worker_scripts_permission_failure_reports_exact_safe_stage(self) -> None:
        api = _ReadApi(fail_path=f"/accounts/{'a' * 32}/workers/scripts")
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("code=CLOUDFLARE_API_TOKEN_INSUFFICIENT", report)
        self.assertIn("stage=WORKERS_SCRIPTS", report)
        self.assertIn("status=403", report)
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_provider_network_failure_reports_stage_without_provider_path(self) -> None:
        api = _ReadApi(
            fail_path=f"/accounts/{'a' * 32}/builds/tokens?per_page=200",
            failure_code="CLOUDFLARE_API_NETWORK_ERROR",
            failure_status=None,
        )
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("code=CLOUDFLARE_API_NETWORK_ERROR", report)
        self.assertIn("stage=WORKERS_BUILDS_TOKENS", report)
        self.assertNotIn("status=", report)
        self.assertNotIn("/accounts/", report)
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_invalid_token_response_is_attributed_to_token_verify_stage(self) -> None:
        api = _ReadApi(token_result=[])
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn(
            "code=CLOUDFLARE_WORKERS_BUILDS_TOKEN_VERIFY_INVALID",
            report,
        )
        self.assertIn("stage=USER_TOKEN_VERIFY", report)
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_build_token_authority_drift_is_attributed_to_build_stage(self) -> None:
        api = _ReadApi(build_tokens=[_build_token_record(token_id=_OTHER_TOKEN_ID)])
        output = StringIO()
        environment = self._environment()
        with patch.object(probe, "CloudflareApi", return_value=api):
            status = probe.probe_workers_builds_authority(environment, output=output)
        report = output.getvalue()
        self.assertEqual(status, 78)
        self.assertIn("code=CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT", report)
        self.assertIn("stage=WORKERS_BUILDS_TOKENS", report)
        self.assertNotIn("WORKERS_SCRIPTS", report)
        for value in environment.values():
            self.assertNotIn(value, report)

    def test_success_report_is_privacy_safe(self) -> None:
        api = _ReadApi(build_tokens=[_build_token_record()])
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

    def test_bootstrap_reuse_requires_verified_user_owner_binding(self) -> None:
        api = _BuildTokenApi(rows=[_build_token_record()])
        self.assertEqual(builds._ensure_build_token(api, _TOKEN_ID), _BUILD_TOKEN_UUID)
        self.assertEqual(len(api.calls), 1)

        for record in (
            _build_token_record(token_id=_OTHER_TOKEN_ID),
            _build_token_record(owner_type="account"),
        ):
            with self.subTest(record=record):
                drift_api = _BuildTokenApi(rows=[record])
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT",
                ):
                    builds._ensure_build_token(drift_api, _TOKEN_ID)
                self.assertEqual(len(drift_api.calls), 1)

    def test_bootstrap_create_validates_provider_response_binding(self) -> None:
        api = _BuildTokenApi(rows=[], created=_build_token_record())
        self.assertEqual(builds._ensure_build_token(api, _TOKEN_ID), _BUILD_TOKEN_UUID)
        self.assertEqual([call[0] for call in api.calls], ["GET", "POST"])
        request_body = api.calls[1][2]["body"]
        self.assertIsInstance(request_body, dict)
        assert isinstance(request_body, dict)
        self.assertEqual(request_body["cloudflare_token_id"], _TOKEN_ID)
        self.assertEqual(request_body[builds._BUILD_TOKEN_VALUE_FIELD], api.token)

        for created in (
            _build_token_record(token_id=_OTHER_TOKEN_ID),
            _build_token_record(owner_type="account"),
            {
                "build_token_name": builds._BUILD_TOKEN_NAME,
                "build_token_uuid": _BUILD_TOKEN_UUID,
                "cloudflare_token_id": _TOKEN_ID,
            },
        ):
            with self.subTest(created=created):
                drift_api = _BuildTokenApi(rows=[], created=created)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_BUILD_TOKEN_AUTHORITY_DRIFT",
                ):
                    builds._ensure_build_token(drift_api, _TOKEN_ID)
                self.assertEqual([call[0] for call in drift_api.calls], ["GET", "POST"])


if __name__ == "__main__":
    unittest.main()
