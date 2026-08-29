from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import scripts.check_v10_cloudflare_runtime_compatibility as guard
import scripts.write_v10_cloudflare_build_info as build_info


class CloudflareRuntimeCompatibilityTests(unittest.TestCase):
    def test_repository_runtime_contract_is_valid(self) -> None:
        guard.validate()

    def test_build_identity_prefers_workers_ci(self) -> None:
        with mock.patch.dict(
            build_info.os.environ,
            {
                "WORKERS_CI_COMMIT_SHA": "a" * 40,
                "GITHUB_SHA": "b" * 40,
            },
            clear=True,
        ):
            self.assertEqual(build_info._source_sha(), "a" * 40)

    def test_build_identity_requires_exact_sha(self) -> None:
        with mock.patch.dict(
            build_info.os.environ,
            {"WORKERS_CI_COMMIT_SHA": "not-a-sha"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "CLOUDFLARE_BUILD_SOURCE_SHA_INVALID"
            ):
                build_info._source_sha()
        with mock.patch.dict(build_info.os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError, "CLOUDFLARE_BUILD_SOURCE_SHA_REQUIRED"
            ):
                build_info._source_sha()

    def test_guard_rejects_hyperdrive_assumption(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["database"]["hyperdrive_used"] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "runtime.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_DATABASE_SUBSTITUTION_FORBIDDEN",
                ):
                    guard.validate()

    def test_guard_rejects_public_multi_user_activation(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["security"]["public_multi_user_enabled"] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "runtime.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_PUBLIC_MULTI_USER_ENABLED_MUST_BE_FALSE",
                ):
                    guard.validate()

    def test_guard_rejects_forwarded_header_trust_reenable(self) -> None:
        dockerfile = guard.DOCKERFILE.read_text(encoding="utf-8").replace(
            '"--port", "8080"]',
            '"--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]',
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "Dockerfile.cloudflare"
            candidate.write_text(dockerfile, encoding="utf-8")
            with mock.patch.object(guard, "DOCKERFILE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_PROXY_HEADER_TRUST_FORBIDDEN",
                ):
                    guard.validate()

    def test_guard_rejects_dynamic_container_transport_contract(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["security"]["container_transport_uses_fixed_internal_url"] = False
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "runtime.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_CONTAINER_TRANSPORT_USES_FIXED_INTERNAL_URL_"
                    "MUST_BE_TRUE",
                ):
                    guard.validate()

    def test_guard_rejects_changed_container_transport_url(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["security"]["container_transport_url"] = "https://example.com/"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "runtime.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_CONTAINER_TRANSPORT_URL_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_container_scale_widening(self) -> None:
        payload = json.loads(guard.WRANGLER.read_text(encoding="utf-8"))
        payload["containers"][0]["max_instances"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrangler.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "WRANGLER", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_RUNTIME_CONTAINER_LIMIT_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_container_dependency_lifecycle_scripts(self) -> None:
        dockerfile = guard.DOCKERFILE.read_text(encoding="utf-8").replace(
            "RUN npm ci --ignore-scripts --prefix apps/web",
            "RUN npm ci --prefix apps/web",
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "Dockerfile.cloudflare"
            candidate.write_text(dockerfile, encoding="utf-8")
            with mock.patch.object(guard, "DOCKERFILE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RUNTIME_DOCKER_GUARD_MISSING"
                ):
                    guard.validate()


if __name__ == "__main__":
    unittest.main()
