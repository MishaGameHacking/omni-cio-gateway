from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import scripts.check_v10_cloudflare_release_acceptance as guard
from scripts.v10_jsonc import loads_jsonc


class CloudflareReleaseAcceptanceTests(unittest.TestCase):
    def test_repository_release_contract_is_valid(self) -> None:
        guard.validate()

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

    def test_guard_rejects_unsafe_wrangler_dependency_install(self) -> None:
        payload = loads_jsonc(guard.WRANGLER.read_text(encoding="utf-8"))
        payload["build"]["command"] = payload["build"]["command"].replace(
            "npm ci --ignore-scripts --prefix apps/web",
            "npm ci --prefix apps/web",
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.jsonc"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RELEASE_SELF_CONTAINED_BUILD_INVALID",
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


if __name__ == "__main__":
    unittest.main()
