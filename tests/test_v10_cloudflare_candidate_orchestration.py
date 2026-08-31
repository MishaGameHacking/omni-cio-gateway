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


class CloudflareCandidateOrchestrationTests(unittest.TestCase):
    def test_repository_orchestration_contract_is_valid(self) -> None:
        guard.validate()

    def test_provider_npm_integrity_is_fail_closed(self) -> None:
        payload = b"synthetic-npm-tarball"
        integrity = "sha512-" + base64.b64encode(
            hashlib.sha512(payload).digest()
        ).decode()
        with patch.object(installer, "_NPM_TARBALL_INTEGRITY", integrity):
            installer._verify_integrity(payload)
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_NPM_INTEGRITY_MISMATCH",
            ):
                installer._verify_integrity(payload + b"-changed")

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
        worker_tag = "a" * 32
        trigger: dict[str, Any] = {
            "trigger_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "external_script_id": worker_tag,
            "repo_connection": {
                "provider_account_id": builds._GITHUB_OWNER_ID,
                "provider_account_name": builds._GITHUB_OWNER,
                "provider_type": "github",
                "repo_id": builds._GITHUB_REPO_ID,
                "repo_name": "other-repository",
            },
        }
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_STAGING_TRIGGER_REPO_AUTHORITY_DRIFT",
        ):
            quarantine._validate_repo_authority(trigger, worker_tag)

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
        worker_tag = "a" * 32
        first = self._trigger(
            worker_tag,
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        second = self._trigger(
            worker_tag,
            "11111111-2222-3333-4444-555555555555",
        )
        second["repo_connection"]["repo_name"] = "other-repository"

        class FakeApi:
            account_id = "b" * 32

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
            quarantine.remove_staging_triggers(api, worker_tag)
        self.assertEqual(raw_api.mutations, [])

    def test_quarantine_deletes_push_triggers_before_cancelling_builds(self) -> None:
        worker_tag = "a" * 32
        trigger_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        build_uuid = "11111111-2222-3333-4444-555555555555"
        trigger = self._trigger(worker_tag, trigger_uuid)
        build = {
            "build_uuid": build_uuid,
            "build_outcome": None,
            "status": "running",
        }

        class FakeApi:
            account_id = "b" * 32

            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def request(self, method: str, path: str, **kwargs):
                del kwargs
                self.calls.append((method, path))
                if method == "GET" and path.endswith("/workers/scripts"):
                    return [{"id": builds._STAGING_WORKER, "tag": worker_tag}]
                if method == "GET" and path.endswith("/triggers"):
                    return [trigger]
                return {}

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        with patch.object(builds, "_builds_for_worker", return_value=[build]):
            cancelled, deleted = quarantine.quarantine_staging_autobuild(
                api,
                expected_sha="a" * 40,
                verify_head=False,
            )
        self.assertEqual((cancelled, deleted), (1, 1))
        delete_index = raw_api.calls.index(
            ("DELETE", f"/accounts/{raw_api.account_id}/builds/triggers/{trigger_uuid}")
        )
        cancel_index = raw_api.calls.index(
            ("PUT", f"/accounts/{raw_api.account_id}/builds/builds/{build_uuid}/cancel")
        )
        self.assertLess(delete_index, cancel_index)

    def test_gated_manual_build_posts_exact_branch_and_sha(self) -> None:
        expected_sha = "a" * 40
        trigger_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        build_uuid = "11111111-2222-3333-4444-555555555555"

        class FakeApi:
            account_id = "b" * 32

            def __init__(self) -> None:
                self.calls: list[tuple[str, str, dict[str, Any]]] = []

            def request(self, method: str, path: str, **kwargs):
                self.calls.append((method, path, kwargs))
                return {"build_uuid": build_uuid}

        raw_api = FakeApi()
        api = cast(builds.CloudflareApi, raw_api)
        actual = gated._start_exact_manual_build(
            api,
            trigger_uuid=trigger_uuid,
            expected_sha=expected_sha,
        )
        self.assertEqual(actual, build_uuid)
        self.assertEqual(len(raw_api.calls), 1)
        method, path, kwargs = raw_api.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(path.endswith(f"/builds/triggers/{trigger_uuid}/builds"))
        self.assertEqual(
            kwargs["body"],
            {"branch": builds._BRANCH, "commit_hash": expected_sha},
        )
        self.assertEqual(kwargs["expected"], frozenset({200, 201}))

    def test_gated_trigger_uses_nonmatching_autobuild_sentinel(self) -> None:
        worker_tag = "a" * 32
        connection_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        build_token_uuid = "11111111-2222-3333-4444-555555555555"
        trigger_uuid = "99999999-8888-7777-6666-555555555555"

        class FakeApi:
            account_id = "b" * 32

            def __init__(self) -> None:
                self.created_body: dict[str, Any] | None = None

            def request(self, method: str, path: str, **kwargs):
                if method == "GET":
                    return []
                if method == "POST" and path.endswith("/builds/triggers"):
                    self.created_body = dict(kwargs["body"])
                    return {
                        **self.created_body,
                        "trigger_uuid": trigger_uuid,
                        "external_script_id": worker_tag,
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
            worker_tag=worker_tag,
            connection_uuid=connection_uuid,
            build_token_uuid=build_token_uuid,
        )
        self.assertEqual(actual, trigger_uuid)
        assert raw_api.created_body is not None
        self.assertEqual(
            raw_api.created_body["branch_includes"],
            [gated._GATED_AUTOBUILD_SENTINEL_BRANCH],
        )
        self.assertNotIn(builds._BRANCH, raw_api.created_body["branch_includes"])

    def test_gated_runner_refuses_preexisting_push_trigger(self) -> None:
        worker_tag = "a" * 32

        class FakeApi:
            account_id = "b" * 32

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
                worker_tag=worker_tag,
                connection_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                build_token_uuid="11111111-2222-3333-4444-555555555555",
            )
        self.assertEqual(len(raw_api.calls), 1)
        self.assertEqual(raw_api.calls[0][0], "GET")


if __name__ == "__main__":
    unittest.main()
