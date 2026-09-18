from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

import scripts.check_v10_cloudflare_release_acceptance as guard
from scripts.v10_jsonc import loads_jsonc


class CloudflareReleaseAcceptanceTests(unittest.TestCase):
    def test_repository_release_contract_is_valid(self) -> None:
        guard.validate()

    def test_guard_rejects_implicit_public_multi_user_expectation(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["live_assertions"][
            "public_multi_user_expectation_must_be_explicit"
        ] = False
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "release.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_LIVE_"
                    "PUBLIC_MULTI_USER_EXPECTATION_MUST_BE_EXPLICIT_INVALID",
                ):
                    guard.validate()

    def test_production_manager_avoids_hardcoded_secret_keyword_assignments(self) -> None:
        source = guard.PRODUCTION_MANAGER.read_text(encoding="utf-8")
        hardcoded_secret_assignment = re.compile(
            r"(?mi)^\s*[A-Z_][A-Z0-9_]*SECRET[A-Z0-9_]*\s*=\s*[\"']"
        )

        self.assertIsNone(hardcoded_secret_assignment.search(source))
        self.assertIn(
            '_RUNTIME_DSN_BINDING = "OMNI_V10_POSTGRES_DSN"',
            source,
        )

    def test_guard_rejects_versions_upload_as_container_candidate(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["candidate"]["non_production_versions_upload_is_candidate"] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "release.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_CANDIDATE_"
                    "NON_PRODUCTION_VERSIONS_UPLOAD_IS_CANDIDATE_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_direct_cloudflare_git_production_deploy(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["post_merge_gate"][
            "direct_cloudflare_git_production_deploy_allowed"
        ] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "release.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_POST_MERGE_"
                    "DIRECT_CLOUDFLARE_GIT_PRODUCTION_DEPLOY_ALLOWED_INVALID",
                ):
                    guard.validate()

    def test_guard_requires_stale_production_build_quarantine(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["cutover"][
            "stale_production_build_quarantine_before_snapshot_required"
        ] = False
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "release.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_CUTOVER_STALE_PRODUCTION_BUILD_"
                    "QUARANTINE_BEFORE_SNAPSHOT_REQUIRED_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_production_workers_dev(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        payload["workers_dev"] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_PRODUCTION_WORKERS_DEV_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_staging_without_workers_dev(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        payload["env"]["staging"]["workers_dev"] = False
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_STAGING_WORKERS_DEV_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_missing_staging_worker(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        del payload["env"]["staging"]
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_STAGING_INVALID"
                ):
                    guard.validate()

    def test_guard_rejects_missing_production_secret_declaration(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        del payload["secrets"]
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_PRODUCTION_SECRETS_INVALID"
                ):
                    guard.validate()

    def test_guard_rejects_missing_staging_secret_declaration(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        del payload["env"]["staging"]["secrets"]
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_STAGING_SECRETS_INVALID"
                ):
                    guard.validate()

    def test_guard_rejects_missing_staging_container(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        del payload["env"]["staging"]["containers"]
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_STAGING_CONTAINER_INVALID"
                ):
                    guard.validate()

    def test_guard_rejects_wrangler_custom_build_reentry(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        payload["build"] = {"command": guard._SECURE_WEB_BUILD}
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_WRANGLER_CUSTOM_BUILD_REENTRY_FORBIDDEN",
                ):
                    guard.validate()

    def test_guard_rejects_workers_builds_build_command_drift(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["candidate"]["workers_builds_build_command"] = "npm run alternate-build"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "release.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_CANDIDATE_WORKERS_BUILDS_BUILD_COMMAND_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_unsafe_root_build_dependency_install(self) -> None:
        payload = json.loads(guard.PACKAGE.read_text(encoding="utf-8"))
        payload["scripts"]["build"] = payload["scripts"]["build"].replace(
            "npm ci --ignore-scripts --prefix apps/web",
            "npm ci --prefix apps/web",
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_BUILD_SCRIPT_INVALID"
                ):
                    guard.validate()

    def test_guard_rejects_staging_deploy_without_container_rollout(self) -> None:
        payload = json.loads(guard.PACKAGE.read_text(encoding="utf-8"))
        payload["scripts"]["cloudflare:deploy:staging"] = (
            "wrangler versions upload --env staging"
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_STAGING_DEPLOY_INVALID"
                ):
                    guard.validate()

    def test_guard_rejects_production_deploy_without_container_rollout(self) -> None:
        payload = json.loads(guard.PACKAGE.read_text(encoding="utf-8"))
        payload["scripts"]["cloudflare:deploy"] = "wrangler deploy"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_PRODUCTION_DEPLOY_INVALID"
                ):
                    guard.validate()


if __name__ == "__main__":
    unittest.main()
