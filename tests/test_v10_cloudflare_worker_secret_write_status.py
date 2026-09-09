from __future__ import annotations

import inspect
import os
from pathlib import Path
import tempfile
from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.cloudflare_staging_secrets as staging_secrets
import scripts.manage_v10_cloudflare_production as production
import scripts.run_v10_cloudflare_gated_candidate as candidate


_ACCOUNT_ID = "a" * 32
_SYNTHETIC_DSN = "synthetic-runtime-dsn-value"
_EXPECTED_WRITE_STATUSES = frozenset({200, 201})


class _RecordingApi:
    account_id = _ACCOUNT_ID
    token = "synthetic-token"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object | None, frozenset[int]]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        del timeout
        self.calls.append((method, path, body, expected))
        return None


class CloudflareWorkerSecretWriteStatusTests(unittest.TestCase):
    def _assert_secret_put(
        self,
        api: _RecordingApi,
        *,
        worker: str,
        binding: str,
        value: str,
    ) -> None:
        self.assertEqual(len(api.calls), 1)
        method, path, body, expected = api.calls[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(
            path,
            f"/accounts/{_ACCOUNT_ID}/workers/scripts/{worker}/secrets",
        )
        self.assertEqual(
            body,
            {"name": binding, "text": value, "type": "secret_text"},
        )
        self.assertEqual(expected, _EXPECTED_WRITE_STATUSES)
        self.assertNotIn(202, expected)

    def test_staging_secret_write_accepts_create_and_update_success(self) -> None:
        api = _RecordingApi()
        staging_secrets.put_staging_secret(
            cast(builds.CloudflareApi, api),
            "OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN",
            "b" * 64,
        )
        self._assert_secret_put(
            api,
            worker=builds._STAGING_WORKER,
            binding="OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN",
            value="b" * 64,
        )

    def test_staging_runtime_secret_uses_corrected_write_contract(self) -> None:
        api = _RecordingApi()
        with tempfile.TemporaryDirectory() as temp_dir:
            dsn_file = Path(temp_dir) / builds._STAGING_DSN_FILENAME
            dsn_file.write_text(_SYNTHETIC_DSN, encoding="utf-8")
            with (
                patch.dict(os.environ, {"RUNNER_TEMP": temp_dir}, clear=False),
                patch.object(builds, "_mask"),
                patch.object(
                    staging_secrets,
                    "wait_staging_secret_type",
                    return_value=True,
                ),
            ):
                staging_secrets.put_staging_runtime_secret(
                    cast(builds.CloudflareApi, api)
                )

        self._assert_secret_put(
            api,
            worker=builds._STAGING_WORKER,
            binding="OMNI_V10_POSTGRES_DSN",
            value=_SYNTHETIC_DSN,
        )

    def test_active_candidate_never_calls_legacy_runtime_secret_writer(self) -> None:
        api = _RecordingApi()
        with tempfile.TemporaryDirectory() as temp_dir:
            dsn_file = Path(temp_dir) / builds._STAGING_DSN_FILENAME
            dsn_file.write_text(_SYNTHETIC_DSN, encoding="utf-8")
            with (
                patch.object(
                    candidate.builds, "_staging_dsn_file", return_value=dsn_file
                ),
                patch.object(candidate, "put_staging_runtime_secret") as corrected_put,
                patch.object(
                    candidate.builds,
                    "_put_runtime_secret",
                    side_effect=AssertionError(
                        "legacy secret writer must stay inactive"
                    ),
                ),
            ):
                candidate._sync_runtime_secret(cast(builds.CloudflareApi, api))
        corrected_put.assert_called_once_with(cast(builds.CloudflareApi, api))

    def test_production_runtime_secret_accepts_create_and_update_success(self) -> None:
        api = _RecordingApi()
        with tempfile.TemporaryDirectory() as temp_dir:
            dsn_file = Path(temp_dir) / "omni-cio-v10-cloudflare-production-dsn.txt"
            dsn_file.write_text(_SYNTHETIC_DSN, encoding="utf-8")
            environment = {"RUNNER_TEMP": temp_dir}
            with (
                patch.object(production, "_api", return_value=api),
                patch.object(
                    production.runtime,
                    "runtime_dsn_file",
                    return_value=dsn_file,
                ),
                patch.object(production, "_runtime_secret_present", return_value=True),
                patch.object(production.builds, "_mask"),
            ):
                production.put_runtime_secret(environment)

        self._assert_secret_put(
            api,
            worker=production._PRODUCTION_WORKER,
            binding=production._RUNTIME_DSN_BINDING,
            value=_SYNTHETIC_DSN,
        )

    def test_cloudflare_api_default_status_contract_remains_strict(self) -> None:
        expected_default = inspect.signature(builds.CloudflareApi.request).parameters[
            "expected"
        ].default
        self.assertEqual(expected_default, frozenset({200}))


if __name__ == "__main__":
    unittest.main()
