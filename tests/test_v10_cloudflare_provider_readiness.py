from __future__ import annotations

from io import StringIO
import subprocess
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

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
            body = kwargs.get("body")
            if not isinstance(body, dict):
                raise AssertionError("build token body required")
            self.created_body = body
            return {
                "build_token_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "cloudflare_token_id": body.get("cloudflare_token_id"),
                "owner_type": "user",
            }
        raise AssertionError((method, path))


class _BuildHistoryApi:
    account_id = "a" * 32

    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = [] if rows is None else rows
        self.created_body: dict[str, object] | None = None

    def request(self, method: str, path: str, **kwargs):
        if method == "GET" and "/builds/workers/" in path:
            return self.rows
        if method == "POST" and "/builds/triggers/" in path:
            self.created_body = kwargs.get("body")
            return {"build_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        raise AssertionError((method, path))


def _trigger_payload(
    *,
    worker_tag: str,
    connection_uuid: str,
    build_token_uuid: str,
    trigger_uuid: str,
) -> dict[str, object]:
    desired = builds._desired_trigger(connection_uuid, build_token_uuid)
    return {
        **{
            key: value
            for key, value in desired.items()
            if key != "repo_connection_uuid"
        },
        "external_script_id": worker_tag,
        "trigger_uuid": trigger_uuid,
        "repo_connection": {
            "repo_connection_uuid": connection_uuid,
            "provider_account_id": builds._GITHUB_OWNER_ID,
            "provider_account_name": builds._GITHUB_OWNER,
            "provider_type": "github",
            "repo_id": builds._GITHUB_REPO_ID,
            "repo_name": builds._GITHUB_REPO,
        },
    }


class _TriggerApi:
    account_id = "a" * 32

    def __init__(
        self,
        trigger: dict[str, object] | None,
        *,
        updated: dict[str, object] | None = None,
        created: dict[str, object] | None = None,
    ) -> None:
        self.trigger = trigger
        self.updated = updated
        self.created = created
        self.patch_body: dict[str, object] | None = None
        self.create_body: dict[str, object] | None = None

    def request(self, method: str, path: str, **kwargs):
        if method == "GET" and path.endswith("/triggers"):
            return [] if self.trigger is None else [self.trigger]
        if method == "PATCH" and "/builds/triggers/" in path:
            self.patch_body = kwargs.get("body")
            if self.updated is None:
                raise AssertionError("missing trigger PATCH response")
            return self.updated
        if method == "POST" and path.endswith("/builds/triggers"):
            self.create_body = kwargs.get("body")
            if self.created is None:
                raise AssertionError("missing trigger POST response")
            return self.created
        raise AssertionError((method, path))


class _Response:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback

    def read(self, limit: int) -> bytes:
        return self._payload[:limit]


class _SequenceOpener:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.calls = 0

    def open(self, request, timeout: float):
        del request, timeout
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _http_error(status: int) -> HTTPError:
    return HTTPError("https://api.cloudflare.com", status, "test", hdrs=None, fp=None)


class CloudflareProviderReadinessTests(unittest.TestCase):
    @staticmethod
    def _complete_environment() -> dict[str, str]:
        return {
            readiness._CLOUDFLARE_AUTHORITY_ENV: "cf-value",
            readiness._CLOUDFLARE_ACCOUNT_ENV: "a" * 32,
            readiness._NEON_AUTHORITY_ENV: "neon-value",
            readiness._NEON_ORGANIZATION_ENV: "org-test",
            readiness._NEON_PROJECT_ENV: "project-test",
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

    def test_invalid_provider_identifiers_fail_closed_without_value_disclosure(
        self,
    ) -> None:
        cases = (
            (readiness._CLOUDFLARE_ACCOUNT_ENV, "CLOUDFLARE_ACCOUNT_ID", "not-an-id"),
            (readiness._NEON_ORGANIZATION_ENV, "NEON_ORG_ID", "INVALID_ORG"),
            (readiness._NEON_PROJECT_ENV, "NEON_PROJECT_ID", "INVALID_PROJECT"),
        )
        for name, label, invalid_value in cases:
            with self.subTest(label=label):
                environment = self._complete_environment()
                environment[name] = invalid_value
                output = StringIO()
                with patch.object(readiness.shutil, "which", return_value=None):
                    status = readiness.check_provider_readiness(
                        environment,
                        output=output,
                    )
                report = output.getvalue()
                self.assertEqual(status, 78)
                self.assertIn(f"{label}=INVALID", report)
                self.assertNotIn(invalid_value, report)
                self.assertIn("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", report)

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
        token_id = "b" * 32
        api = _BuildTokenApi()
        identifier = builds._ensure_build_token(api, token_id)
        self.assertEqual(identifier, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertIsNotNone(api.created_body)
        assert api.created_body is not None
        self.assertEqual(
            api.created_body[builds._BUILD_TOKEN_VALUE_FIELD],
            api.token,
        )
        self.assertEqual(api.created_body["cloudflare_token_id"], token_id)
        self.assertEqual(
            set(api.created_body),
            {
                "build_token_name",
                builds._BUILD_TOKEN_VALUE_FIELD,
                "cloudflare_token_id",
            },
        )

    def test_cloudflare_get_retries_only_transient_http_failures(self) -> None:
        opener = _SequenceOpener(
            _http_error(503),
            _Response(200, b'{"success":true,"result":{"ok":true}}'),
        )
        api = builds.CloudflareApi("a" * 32, "masked")
        with (
            patch.object(builds, "_OPENER", opener),
            patch.object(builds.time, "sleep") as sleep,
        ):
            result = api.request("GET", "/user/tokens/verify")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(opener.calls, 2)
        sleep.assert_called_once_with(1.0)

    def test_cloudflare_post_does_not_retry_transient_http_failure(self) -> None:
        opener = _SequenceOpener(_http_error(503))
        api = builds.CloudflareApi("a" * 32, "masked")
        with (
            patch.object(builds, "_OPENER", opener),
            patch.object(builds.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_API_HTTP_ERROR status=503",
            ):
                api.request("POST", "/accounts/test", body={"value": 1})
        self.assertEqual(opener.calls, 1)
        sleep.assert_not_called()

    def test_cloudflare_auth_failure_remains_fail_closed(self) -> None:
        opener = _SequenceOpener(_http_error(403))
        api = builds.CloudflareApi("a" * 32, "masked")
        with patch.object(builds, "_OPENER", opener):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_API_TOKEN_INSUFFICIENT status=403",
            ):
                api.request("GET", "/user/tokens/verify")
        self.assertEqual(opener.calls, 1)

    def test_cloudflare_network_failure_has_bounded_get_retry(self) -> None:
        opener = _SequenceOpener(
            OSError("transient"),
            OSError("transient"),
            OSError("terminal"),
        )
        api = builds.CloudflareApi("a" * 32, "masked")
        with (
            patch.object(builds, "_OPENER", opener),
            patch.object(builds.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_API_NETWORK_ERROR"):
                api.request("GET", "/user/tokens/verify")
        self.assertEqual(opener.calls, 3)
        self.assertEqual([call.args for call in sleep.call_args_list], [(1.0,), (2.0,)])

    def test_existing_trigger_requires_exact_immutable_repo_authority(self) -> None:
        worker_tag = "d" * 32
        connection_uuid = "11111111-2222-3333-4444-555555555555"
        build_token_uuid = "66666666-7777-8888-9999-aaaaaaaaaaaa"
        trigger_uuid = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        trigger = _trigger_payload(
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
            trigger_uuid=trigger_uuid,
        )
        updated = dict(trigger)
        api = _TriggerApi(trigger, updated=updated)

        identifier, created = builds._ensure_trigger(
            api,
            worker_tag,
            connection_uuid,
            build_token_uuid,
        )

        self.assertEqual(identifier, trigger_uuid)
        self.assertFalse(created)
        self.assertIsNotNone(api.patch_body)
        assert api.patch_body is not None
        self.assertNotIn("repo_connection_uuid", api.patch_body)
        self.assertEqual(
            api.patch_body["deploy_command"],
            builds._DEPLOY_COMMAND,
        )

    def test_existing_trigger_rejects_repo_connection_authority_drift(self) -> None:
        worker_tag = "d" * 32
        connection_uuid = "11111111-2222-3333-4444-555555555555"
        trigger = _trigger_payload(
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid="66666666-7777-8888-9999-aaaaaaaaaaaa",
            trigger_uuid="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        )
        repo = dict(trigger["repo_connection"])
        repo["repo_connection_uuid"] = "00000000-1111-2222-3333-444444444444"
        trigger["repo_connection"] = repo
        api = _TriggerApi(trigger)

        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT",
        ):
            builds._ensure_trigger(
                api,
                worker_tag,
                connection_uuid,
                "66666666-7777-8888-9999-aaaaaaaaaaaa",
            )
        self.assertIsNone(api.patch_body)

    def test_existing_trigger_rejects_worker_authority_drift(self) -> None:
        worker_tag = "d" * 32
        connection_uuid = "11111111-2222-3333-4444-555555555555"
        trigger = _trigger_payload(
            worker_tag="e" * 32,
            connection_uuid=connection_uuid,
            build_token_uuid="66666666-7777-8888-9999-aaaaaaaaaaaa",
            trigger_uuid="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        )
        api = _TriggerApi(trigger)

        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_STAGING_TRIGGER_WORKER_DRIFT",
        ):
            builds._ensure_trigger(
                api,
                worker_tag,
                connection_uuid,
                "66666666-7777-8888-9999-aaaaaaaaaaaa",
            )
        self.assertIsNone(api.patch_body)

    def test_trigger_patch_response_must_match_exact_configuration(self) -> None:
        worker_tag = "d" * 32
        connection_uuid = "11111111-2222-3333-4444-555555555555"
        build_token_uuid = "66666666-7777-8888-9999-aaaaaaaaaaaa"
        trigger_uuid = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        trigger = _trigger_payload(
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
            trigger_uuid=trigger_uuid,
        )
        updated = dict(trigger)
        updated["deploy_command"] = "echo stale-provider-state"
        api = _TriggerApi(trigger, updated=updated)

        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_STAGING_TRIGGER_CONFIGURATION_DRIFT",
        ):
            builds._ensure_trigger(
                api,
                worker_tag,
                connection_uuid,
                build_token_uuid,
            )

    def test_created_trigger_requires_exact_returned_authority(self) -> None:
        worker_tag = "d" * 32
        connection_uuid = "11111111-2222-3333-4444-555555555555"
        build_token_uuid = "66666666-7777-8888-9999-aaaaaaaaaaaa"
        trigger_uuid = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        created_payload = _trigger_payload(
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
            trigger_uuid=trigger_uuid,
        )
        api = _TriggerApi(None, created=created_payload)

        identifier, created = builds._ensure_trigger(
            api,
            worker_tag,
            connection_uuid,
            build_token_uuid,
        )

        self.assertEqual(identifier, trigger_uuid)
        self.assertTrue(created)
        self.assertIsNotNone(api.create_body)
        assert api.create_body is not None
        self.assertEqual(api.create_body["repo_connection_uuid"], connection_uuid)
        self.assertEqual(api.create_body["external_script_id"], worker_tag)

    def test_build_history_requires_exact_candidate_metadata(self) -> None:
        sha = "c" * 40
        row = {
            "build_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "status": "running",
            "build_trigger_metadata": {
                "commit_hash": sha,
                "branch": builds._BRANCH,
                "build_command": builds._BUILD_COMMAND,
                "deploy_command": builds._DEPLOY_COMMAND,
            },
        }
        api = _BuildHistoryApi([row])
        self.assertIs(builds._find_exact_build(api, "d" * 32, sha), row)

        wrong_command = {
            **row,
            "build_trigger_metadata": {
                **row["build_trigger_metadata"],
                "deploy_command": "echo unsafe-drift",
            },
        }
        api = _BuildHistoryApi([wrong_command])
        self.assertIsNone(builds._find_exact_build(api, "d" * 32, sha))

        terminal_failure = {
            **row,
            "status": "stopped",
            "build_outcome": "fail",
        }
        api = _BuildHistoryApi([terminal_failure])
        self.assertIsNone(builds._find_exact_build(api, "d" * 32, sha))

    def test_manual_build_is_pinned_to_branch_and_exact_commit(self) -> None:
        sha = "c" * 40
        api = _BuildHistoryApi()
        with patch.object(builds.time, "sleep"):
            identifier = builds._start_or_reuse_build(
                api,
                "d" * 32,
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                sha,
                True,
            )
        self.assertEqual(identifier, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertEqual(
            api.created_body,
            {"branch": builds._BRANCH, "commit_hash": sha},
        )

    def test_successful_build_requires_complete_candidate_identity(self) -> None:
        sha = "c" * 40

        class _StatusApi:
            account_id = "a" * 32

            @staticmethod
            def request(method: str, path: str, **kwargs):
                del kwargs
                if method == "GET" and "/builds/builds/" in path:
                    return {
                        "status": "stopped",
                        "build_outcome": "success",
                        "build_trigger_metadata": {
                            "commit_hash": sha,
                            "branch": builds._BRANCH,
                            "build_command": builds._BUILD_COMMAND,
                            "deploy_command": builds._DEPLOY_COMMAND,
                        },
                    }
                raise AssertionError((method, path))

        builds._wait_build(_StatusApi(), "e" * 36, sha)

    def test_stopped_build_without_outcome_fails_closed(self) -> None:
        sha = "c" * 40

        class _StatusApi:
            account_id = "a" * 32

            @staticmethod
            def request(method: str, path: str, **kwargs):
                del kwargs
                if method == "GET" and "/builds/builds/" in path:
                    return {
                        "status": "stopped",
                        "build_trigger_metadata": {"commit_hash": sha},
                    }
                raise AssertionError((method, path))

        api = _StatusApi()
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_BUILD_OUTCOME_MISSING"
        ):
            builds._wait_build(api, "e" * 36, sha)

    def test_successful_build_requires_nested_exact_commit_hash(self) -> None:
        sha = "c" * 40

        class _StatusApi:
            account_id = "a" * 32

            @staticmethod
            def request(method: str, path: str, **kwargs):
                del kwargs
                if method == "GET" and "/builds/builds/" in path:
                    return {
                        "build_outcome": "success",
                        "build_trigger_metadata": {"commit_hash": "d" * 40},
                    }
                raise AssertionError((method, path))

        api = _StatusApi()
        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_BUILD_SHA_MISMATCH"):
            builds._wait_build(api, "e" * 36, sha)


if __name__ == "__main__":
    unittest.main()
