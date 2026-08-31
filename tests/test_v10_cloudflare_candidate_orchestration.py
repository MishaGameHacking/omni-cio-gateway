from __future__ import annotations

import base64
import hashlib
from pathlib import PurePosixPath
from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.check_v10_cloudflare_candidate_orchestration as guard
import scripts.install_v10_cloudflare_delivery_toolchain as installer
import scripts.quarantine_v10_cloudflare_staging_trigger as quarantine
import scripts.run_v10_cloudflare_gated_candidate as gated


_EXPECTED_SHA = "a" * 40
_WORKER_TAG = "a" * 32
_ACCOUNT_ID = "b" * 32
_TRIGGER_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_BUILD_UUID = "11111111-2222-3333-4444-555555555555"
_EXTRA_TRIGGER_UUID = "99999999-8888-7777-6666-555555555555"
_OTHER_REPOSITORY = "other-repository"
_REVIEWED_NPM_SRI_BODY = "".join(
    (
        "iriPEPIk",
        "oMYUy3F6",
        "f3wwSZAU",
        "93E0Eg6c",
        "HwIR6jzz",
        "OXWSy+SD",
        "/rOODEs7",
        "4cVONHKS",
        "x2obXtuU",
        "oyidVEhI",
        "SrisgQ==",
    )
)


class CloudflareCandidateOrchestrationTests(unittest.TestCase):
    def test_repository_orchestration_contract_is_valid(self) -> None:
        guard.validate()

    def test_provider_npm_digest_matches_reviewed_dist_integrity(self) -> None:
        self.assertEqual(
            len(installer._NPM_TARBALL_SHA512),
            hashlib.sha512().digest_size,
        )
        self.assertEqual(
            base64.b64encode(installer._NPM_TARBALL_SHA512).decode("ascii"),
            _REVIEWED_NPM_SRI_BODY,
        )

    def test_provider_npm_integrity_is_fail_closed(self) -> None:
        payload = b"synthetic-npm-tarball"
        digest = hashlib.sha512(payload).digest()
        with patch.object(installer, "_NPM_TARBALL_SHA512", digest):
            installer._verify_integrity(payload)
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_NPM_INTEGRITY_MISMATCH",
            ):
                installer._verify_integrity(payload + b"-changed")

    def test_provider_npm_invalid_digest_config_fails_closed(self) -> None:
        with patch.object(installer, "_NPM_TARBALL_SHA512", b"short"):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_NPM_INTEGRITY_CONFIG_INVALID",
            ):
                installer._verify_integrity(b"synthetic-npm-tarball")

    def test_provider_npm_archive_path_rejects_cross_platform_escape(self) -> None:
        self.assertEqual(
            installer._safe_member_path("package/bin/npm-cli.js"),
            PurePosixPath("package/bin/npm-cli.js"),
        )
        for candidate in (
            "../escape",
            "/absolute",
            "package/../../escape",
            "package\\..\\escape",
            "package/C:/escape",
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NPM_TARBALL_PATH_INVALID",
                ):
                    installer._safe_member_path(candidate)

    def test_quarantine_rejects_trigger_repo_authority_drift(self) -> None:
        trigger: dict[str, Any] = {
            "trigger_uuid": _TRIGGER_UUID,
            "external_script_id": _WORKER_TAG,
            "repo_connection": {
                "provider_account_id": builds._GITHUB_OWNER_ID,
                "provider_account_name": builds._GITHUB_OWNER,
                "provider_type": "github",
                "repo_id": builds._GITHUB_REPO_ID,
                "repo_name": _OTHER_REPOSITORY,
            },
        }
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT",
        ):
            quarantine._validate_repo_authority(trigger, _WORKER_TAG)

    @staticmethod
    def _trigger(worker_tag: str, trigger_uuid: str) -> dict[str, Any]:
        return {
            "trigger_uuid": trigger_uuid,
            "trigger_name": builds._TRIGGER_NAME,
            "external_script_id": worker_tag,
            "repo_connection": {
                "provider_account_id": builds._GITHUB_OWNER_ID,
                "provider_account_name": builds._GITHUB_OWNER,
                "provider_type": "github",
                "repo_id": builds._GITHUB_REPO_ID,
                "repo_name": builds._GITHUB_REPO,
            },
        }

    def test_quarantine_validates_all_triggers_before_delete(self) -> None:
        first = self._trigger(_WORKER_TAG, _TRIGGER_UUID)
        second = self._trigger(_WORKER_TAG, _BUILD_UUID)
        second["repo_connection"]["repo_name"] = _OTHER_REPOSITORY

        class FakeApi:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.mutations: list[tuple[str, str]] = []

            def request(self, method: str, path: str, **kwargs):
                del kwargs
                if method == "GET":
                    return [first, second]
                self.mutations.append((method, path))
                return {}

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT",
        ):
            quarantine.remove_staging_triggers(api, _WORKER_TAG)
        self.assertEqual(raw_api.mutations, [])

    def test_quarantine_deletes_push_triggers_before_cancelling_builds(self) -> None:
        trigger = self._trigger(_WORKER_TAG, _TRIGGER_UUID)
        build = {
            "build_uuid": _BUILD_UUID,
            "build_outcome": None,
            "status": "running",
        }

        class FakeApi:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def request(self, method: str, path: str, **kwargs):
                del kwargs
                self.calls.append((method, path))
                if method == "GET" and path.endswith("/workers/scripts"):
                    return [{"id": builds._STAGING_WORKER, "tag": _WORKER_TAG}]
                if method == "GET" and path.endswith("/triggers"):
                    return [trigger]
                return {}

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        with patch.object(builds, "_builds_for_worker", return_value=[build]):
            cancelled, deleted = quarantine.quarantine_staging_autobuild(
                api,
                expected_sha=_EXPECTED_SHA,
                verify_head=False,
            )
        self.assertEqual((cancelled, deleted), (1, 1))
        delete_index = raw_api.calls.index(
            (
                "DELETE",
                f"/accounts/{raw_api.account_id}/builds/triggers/{_TRIGGER_UUID}",
            )
        )
        cancel_index = raw_api.calls.index(
            (
                "PUT",
                f"/accounts/{raw_api.account_id}/builds/builds/{_BUILD_UUID}/cancel",
            )
        )
        self.assertLess(delete_index, cancel_index)

    def test_gated_manual_build_posts_exact_branch_and_sha(self) -> None:
        class FakeApi:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.calls: list[tuple[str, str, dict[str, Any]]] = []

            def request(self, method: str, path: str, **kwargs):
                self.calls.append((method, path, kwargs))
                return {"build_uuid": _BUILD_UUID}

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        actual = gated._start_exact_manual_build(
            api,
            trigger_uuid=_TRIGGER_UUID,
            expected_sha=_EXPECTED_SHA,
        )
        self.assertEqual(actual, _BUILD_UUID)
        self.assertEqual(len(raw_api.calls), 1)
        method, path, kwargs = raw_api.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(path.endswith(f"/builds/triggers/{_TRIGGER_UUID}/builds"))
        self.assertEqual(
            kwargs["body"],
            {"branch": builds._BRANCH, "commit_hash": _EXPECTED_SHA},
        )
        self.assertEqual(kwargs["expected"], frozenset({200, 201}))

    def test_gated_trigger_uses_nonmatching_autobuild_sentinel(self) -> None:
        connection_uuid = _TRIGGER_UUID
        build_token_uuid = _BUILD_UUID

        class FakeApi:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.created_body: dict[str, Any] | None = None

            def request(self, method: str, path: str, **kwargs):
                if method == "GET":
                    return []
                if method == "POST" and path.endswith("/builds/triggers"):
                    self.created_body = dict(kwargs["body"])
                    return {
                        **self.created_body,
                        "trigger_uuid": _EXTRA_TRIGGER_UUID,
                        "external_script_id": _WORKER_TAG,
                        "repo_connection": {
                            "repo_connection_uuid": connection_uuid,
                            "provider_account_id": builds._GITHUB_OWNER_ID,
                            "provider_account_name": builds._GITHUB_OWNER,
                            "provider_type": "github",
                            "repo_id": builds._GITHUB_REPO_ID,
                            "repo_name": builds._GITHUB_REPO,
                        },
                    }
                raise AssertionError((method, path))

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        actual = gated._create_gated_trigger(
            api,
            worker_tag=_WORKER_TAG,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
        )
        self.assertEqual(actual, _EXTRA_TRIGGER_UUID)
        self.assertIsNotNone(raw_api.created_body)
        created_body = cast(dict[str, Any], raw_api.created_body)
        self.assertEqual(
            created_body["branch_includes"],
            [gated._GATED_AUTOBUILD_SENTINEL_BRANCH],
        )
        self.assertNotIn(builds._BRANCH, created_body["branch_includes"])

    def test_gated_runner_refuses_preexisting_push_trigger(self) -> None:
        class FakeApi:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def request(self, method: str, path: str, **kwargs):
                del kwargs
                self.calls.append((method, path))
                if method == "GET":
                    return [{"trigger_name": builds._TRIGGER_NAME}]
                raise AssertionError(
                    "gated runner must not mutate a preexisting trigger"
                )

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_GATED_TRIGGER_PREEXISTED",
        ):
            gated._create_gated_trigger(
                api,
                worker_tag=_WORKER_TAG,
                connection_uuid=_TRIGGER_UUID,
                build_token_uuid=_BUILD_UUID,
            )
        self.assertEqual(len(raw_api.calls), 1)
        self.assertEqual(raw_api.calls[0][0], "GET")

    def test_gated_runner_waits_for_terminal_build_before_cleanup(self) -> None:
        events: list[str] = []
        api = cast(builds.CloudflareApi, object())
        env = {
            "CLOUDFLARE_API_TOKEN": "synthetic-token",
            "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
        }

        def required_env(name: str) -> str:
            return env[name]

        def prepare(_api: builds.CloudflareApi, _sha: str) -> tuple[str, str]:
            events.append("prepare")
            return _WORKER_TAG, _BUILD_UUID

        def wait(
            _api: builds.CloudflareApi,
            _build_uuid: str,
            _sha: str,
        ) -> None:
            events.append("wait")

        def staging_url(_api: builds.CloudflareApi) -> str:
            events.append("url")
            return "https://omni-cio-v10-web-staging.example.workers.dev"

        def cleanup(*args, **kwargs) -> tuple[int, int]:
            del args, kwargs
            events.append("cleanup")
            return 0, 1

        with (
            patch.object(gated, "_assert_exact_head", return_value=_EXPECTED_SHA),
            patch.object(builds, "_required_env", side_effect=required_env),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(gated, "_prepare_candidate", side_effect=prepare),
            patch.object(builds, "_wait_build", side_effect=wait),
            patch.object(builds, "_staging_url", side_effect=staging_url),
            patch.object(gated, "quarantine_staging_autobuild", side_effect=cleanup),
            patch.object(builds, "_write_output"),
        ):
            actual = gated.run(_EXPECTED_SHA)

        self.assertEqual(
            actual,
            "https://omni-cio-v10-web-staging.example.workers.dev",
        )
        self.assertEqual(events, ["prepare", "wait", "url", "cleanup"])

    def test_gated_runner_cleans_up_after_terminal_build_failure(self) -> None:
        events: list[str] = []
        api = cast(builds.CloudflareApi, object())
        env = {
            "CLOUDFLARE_API_TOKEN": "synthetic-token",
            "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
        }

        def required_env(name: str) -> str:
            return env[name]

        def prepare(_api: builds.CloudflareApi, _sha: str) -> tuple[str, str]:
            events.append("prepare")
            return _WORKER_TAG, _BUILD_UUID

        def wait(
            _api: builds.CloudflareApi,
            _build_uuid: str,
            _sha: str,
        ) -> None:
            events.append("wait")
            raise builds.BootstrapStopped("CLOUDFLARE_STAGING_BUILD_FAILED")

        def cleanup(*args, **kwargs) -> tuple[int, int]:
            del args, kwargs
            events.append("cleanup")
            return 0, 1

        with (
            patch.object(gated, "_assert_exact_head", return_value=_EXPECTED_SHA),
            patch.object(builds, "_required_env", side_effect=required_env),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(gated, "_prepare_candidate", side_effect=prepare),
            patch.object(builds, "_wait_build", side_effect=wait),
            patch.object(gated, "quarantine_staging_autobuild", side_effect=cleanup),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_STAGING_BUILD_FAILED",
            ):
                gated.run(_EXPECTED_SHA)

        self.assertEqual(events, ["prepare", "wait", "cleanup"])


if __name__ == "__main__":
    unittest.main()
