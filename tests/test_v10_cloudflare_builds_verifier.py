from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import scripts.check_v10_cloudflare_builds_verifier as guard
import scripts.run_v10_cloudflare_verifier as runner


class CloudflareBuildsVerifierTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        guard.validate()

    def test_runner_has_exact_six_shards(self) -> None:
        self.assertEqual(
            [item.identifier for item in runner.SHARDS],
            guard.EXPECTED_SHARDS,
        )

    def test_workers_sha_is_required_and_exact(self) -> None:
        sha = "a" * 40
        self.assertEqual(
            runner._provider_sha(
                {
                    "WORKERS_CI": "1",
                    "WORKERS_CI_COMMIT_SHA": sha,
                    "GITHUB_SHA": sha,
                }
            ),
            sha,
        )
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_VERIFIER_WORKERS_SHA_REQUIRED"
        ):
            runner._provider_sha({"WORKERS_CI": "1"})
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_VERIFIER_SHA_MISMATCH"
        ):
            runner._provider_sha(
                {
                    "WORKERS_CI": "1",
                    "WORKERS_CI_COMMIT_SHA": sha,
                    "GITHUB_SHA": "b" * 40,
                }
            )

    def test_unknown_shard_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_VERIFIER_SHARD_UNKNOWN"
        ):
            runner._shard("CFV-UNKNOWN")

    def test_guard_rejects_secret_bearing_shard(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["shards"][0]["requires_runtime_secrets"] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "contract.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_VERIFIER_SHARD_SECRET_SCOPE_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_paid_overage_authority(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        payload["workers_builds_reference"][
            "automatic_paid_overage_authorized"
        ] = True
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "contract.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "CONTRACT", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_VERIFIER_REFERENCE_AUTOMATIC_PAID_OVERAGE_AUTHORIZED_INVALID",
                ):
                    guard.validate()


if __name__ == "__main__":
    unittest.main()
