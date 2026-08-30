from __future__ import annotations

import io
from typing import Any
import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_candidate_delivery as guard
import scripts.probe_v10_cloudflare_staging_worker_anchor as worker_anchor


class _WorkerScriptsApi:
    account_id = "a" * 32

    def __init__(self, rows: object) -> None:
        self.rows = rows
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str) -> Any:
        self.calls.append((method, path))
        if method != "GET" or path != f"/accounts/{self.account_id}/workers/scripts":
            raise AssertionError((method, path))
        return self.rows


class CloudflareStagingWorkerAnchorTests(unittest.TestCase):
    def test_existing_anchor_is_reused_with_read_only_provider_access(self) -> None:
        api = _WorkerScriptsApi(
            [
                {
                    "id": "omni-cio-v10-web-staging",
                    "tag": "b" * 32,
                }
            ]
        )
        self.assertTrue(worker_anchor._staging_worker_anchor_present(api))
        self.assertEqual(
            api.calls,
            [("GET", f"/accounts/{api.account_id}/workers/scripts")],
        )

    def test_missing_anchor_requires_bootstrap_without_provider_mutation(self) -> None:
        api = _WorkerScriptsApi([])
        self.assertFalse(worker_anchor._staging_worker_anchor_present(api))
        self.assertEqual(
            api.calls,
            [("GET", f"/accounts/{api.account_id}/workers/scripts")],
        )

    def test_existing_anchor_requires_canonical_worker_tag(self) -> None:
        api = _WorkerScriptsApi(
            [
                {
                    "id": "omni-cio-v10-web-staging",
                    "tag": "b" * 31,
                }
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_WORKER_TAG_INVALID"):
            worker_anchor._staging_worker_anchor_present(api)

    def test_probe_exit_contract_distinguishes_reuse_missing_and_blocked(self) -> None:
        environment = {
            "CLOUDFLARE_API_TOKEN": "masked-token",
            "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        }
        scenarios = (
            (
                _WorkerScriptsApi(
                    [
                        {
                            "id": "omni-cio-v10-web-staging",
                            "tag": "b" * 32,
                        }
                    ]
                ),
                0,
                "CLOUDFLARE_STAGING_WORKER_ANCHOR=REUSED",
            ),
            (
                _WorkerScriptsApi([]),
                10,
                "CLOUDFLARE_STAGING_WORKER_ANCHOR=BOOTSTRAP_REQUIRED",
            ),
            (
                _WorkerScriptsApi("invalid"),
                78,
                "CLOUDFLARE_STAGING_WORKER_ANCHOR=BLOCKED",
            ),
        )
        for api, expected_code, expected_output in scenarios:
            with self.subTest(expected_code=expected_code):
                output = io.StringIO()
                with patch.object(worker_anchor, "CloudflareApi", return_value=api):
                    code = worker_anchor.probe_staging_worker_anchor(
                        environment,
                        output=output,
                    )
                self.assertEqual(code, expected_code)
                self.assertIn(expected_output, output.getvalue())

    def test_workflow_guard_requires_probe_gated_bootstrap_order(self) -> None:
        good = "\n".join(
            (
                guard._PROVIDER_MUTATION_STEP_MARKERS[1],
                guard._STAGING_WORKER_ANCHOR_COMMAND,
                "bootstrap_rc=$?",
                'case "$bootstrap_rc" in',
                "10)",
                guard._BOOTSTRAP_DEPLOY_COMMAND,
                guard._STAGING_WORKER_ANCHOR_COMMAND,
                "*)",
                guard._PROVIDER_MUTATION_STEP_MARKERS[2],
            )
        )
        guard._validate_idempotent_worker_anchor_bootstrap(good)

        unsafe = good.replace(
            "10)\n" + guard._BOOTSTRAP_DEPLOY_COMMAND,
            guard._BOOTSTRAP_DEPLOY_COMMAND + "\n10)",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CANDIDATE_BOOTSTRAP_GATE_ORDER_INVALID",
        ):
            guard._validate_idempotent_worker_anchor_bootstrap(unsafe)


if __name__ == "__main__":
    unittest.main()
