from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
from typing import Any, cast
import unittest
from unittest.mock import Mock, patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.cloudflare_staging_secrets as staging_secrets
import scripts.cloudflare_worker_secret_state as secret_state
import scripts.manage_v10_cloudflare_production as production
import scripts.sync_v10_cloudflare_cf_d_bootstrap_origin as custody


_ACCOUNT_ID = "a" * 32
_SYNC_TOKEN = "c" * 64
_SYNTHETIC_DSN = "synthetic-runtime-dsn-value"
_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = (
    _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)


def _secret_row(name: str) -> list[dict[str, str]]:
    return [{"name": name, "type": "secret_text"}]


class _SecretApi:
    account_id = _ACCOUNT_ID

    def __init__(self, get_responses: list[object]) -> None:
        self.get_responses = list(get_responses)
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
        if method != "GET":
            return None
        if not self.get_responses:
            raise AssertionError("unexpected secret-state read")
        response = self.get_responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def method_count(self, method: str) -> int:
        return sum(call[0] == method for call in self.calls)


class CloudflareWorkerSecretConvergenceTests(unittest.TestCase):
    def test_read_only_helper_waits_for_delayed_state_without_hiding_errors(
        self,
    ) -> None:
        reader = Mock(side_effect=[False, False, True])
        with patch.object(secret_state.time, "sleep") as sleep:
            self.assertTrue(secret_state.wait_for_secret_state(reader, True))
        self.assertEqual(reader.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(secret_state._SECRET_STATE_CONVERGENCE_DELAY_SECONDS)

        failure = builds.BootstrapStopped("CLOUDFLARE_API_NETWORK_ERROR")
        failing_reader = Mock(side_effect=failure)
        with (
            patch.object(secret_state.time, "sleep") as failing_sleep,
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            secret_state.wait_for_secret_state(failing_reader, True)
        self.assertEqual(raised.exception.code, "CLOUDFLARE_API_NETWORK_ERROR")
        self.assertEqual(failing_reader.call_count, 1)
        failing_sleep.assert_not_called()

    def test_sync_token_presence_and_cleanup_allow_bounded_visibility_delay(
        self,
    ) -> None:
        api = _SecretApi(
            [
                _secret_row(custody._SYNC_TOKEN_BINDING),
                [],
                [],
                _secret_row(custody._SYNC_TOKEN_BINDING),
                _secret_row(custody._SYNC_TOKEN_BINDING),
                [],
            ]
        )
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(secret_state.time, "sleep") as sleep,
        ):
            with custody.bootstrap_origin_sync_token(
                cast(builds.CloudflareApi, api)
            ) as token:
                self.assertEqual(token, _SYNC_TOKEN)

        self.assertEqual(api.method_count("PUT"), 1)
        self.assertEqual(api.method_count("DELETE"), 2)
        self.assertEqual(api.method_count("GET"), 6)
        self.assertEqual(sleep.call_count, 3)

    def test_sync_token_preclear_exhaustion_stays_fail_closed_without_put(self) -> None:
        api = _SecretApi(
            [
                _secret_row(custody._SYNC_TOKEN_BINDING)
                for _ in range(secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS)
            ]
        )
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(secret_state.time, "sleep") as sleep,
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            with custody.bootstrap_origin_sync_token(cast(builds.CloudflareApi, api)):
                pass

        self.assertEqual(raised.exception.code, custody._SYNC_TOKEN_STALE)
        self.assertEqual(api.method_count("PUT"), 0)
        self.assertEqual(api.method_count("DELETE"), 1)
        self.assertEqual(
            api.method_count("GET"),
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS,
        )
        self.assertEqual(
            sleep.call_count,
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS - 1,
        )

    def test_sync_token_cleanup_exhaustion_stays_fail_closed_without_redelete(
        self,
    ) -> None:
        api = _SecretApi(
            [
                [],
                _secret_row(custody._SYNC_TOKEN_BINDING),
            ]
            + [
                _secret_row(custody._SYNC_TOKEN_BINDING)
                for _ in range(secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS)
            ]
        )
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(secret_state.time, "sleep") as sleep,
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            with custody.bootstrap_origin_sync_token(cast(builds.CloudflareApi, api)):
                pass

        self.assertEqual(raised.exception.code, custody._SYNC_TOKEN_STALE)
        self.assertEqual(api.method_count("PUT"), 1)
        self.assertEqual(api.method_count("DELETE"), 2)
        self.assertEqual(
            api.method_count("GET"),
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS + 2,
        )
        self.assertEqual(
            sleep.call_count,
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS - 1,
        )

    def test_staging_runtime_secret_waits_read_only_after_single_put(self) -> None:
        api = _SecretApi(
            [
                [],
                _secret_row(staging_secrets._RUNTIME_DSN_BINDING),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            dsn_file = Path(temp_dir) / builds._STAGING_DSN_FILENAME
            dsn_file.write_text(_SYNTHETIC_DSN, encoding="utf-8")
            with (
                patch.dict(os.environ, {"RUNNER_TEMP": temp_dir}, clear=False),
                patch.object(builds, "_mask"),
                patch.object(secret_state.time, "sleep") as sleep,
            ):
                staging_secrets.put_staging_runtime_secret(
                    cast(builds.CloudflareApi, api)
                )

        self.assertEqual(api.method_count("PUT"), 1)
        self.assertEqual(api.method_count("GET"), 2)
        self.assertEqual(sleep.call_count, 1)

    def test_production_runtime_secret_waits_read_only_after_single_put(self) -> None:
        api = _SecretApi(
            [
                [],
                _secret_row(production._RUNTIME_DSN_BINDING),
            ]
        )
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
                patch.object(production.builds, "_mask"),
                patch.object(secret_state.time, "sleep") as sleep,
            ):
                production.put_runtime_secret(environment)

        self.assertEqual(api.method_count("PUT"), 1)
        self.assertEqual(api.method_count("GET"), 2)
        self.assertEqual(sleep.call_count, 1)

    def test_production_runtime_secret_exhaustion_preserves_existing_red_code(
        self,
    ) -> None:
        api = _SecretApi(
            [[] for _ in range(secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS)]
        )
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
                patch.object(production.builds, "_mask"),
                patch.object(secret_state.time, "sleep") as sleep,
                self.assertRaises(builds.BootstrapStopped) as raised,
            ):
                production.put_runtime_secret(environment)

        self.assertEqual(
            raised.exception.code,
            "CLOUDFLARE_PRODUCTION_SECRET_VERIFY_FAILED",
        )
        self.assertEqual(api.method_count("PUT"), 1)
        self.assertEqual(
            api.method_count("GET"),
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS,
        )
        self.assertEqual(
            sleep.call_count,
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS - 1,
        )

    def test_malformed_staging_secret_state_is_not_retried(self) -> None:
        api = _SecretApi(
            [
                [
                    {"name": custody._SYNC_TOKEN_BINDING, "type": "secret_text"},
                    {"name": custody._SYNC_TOKEN_BINDING, "type": "secret_text"},
                ]
            ]
        )
        with (
            patch.object(secret_state.time, "sleep") as sleep,
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            staging_secrets.wait_staging_secret_type(
                cast(builds.CloudflareApi, api),
                custody._SYNC_TOKEN_BINDING,
                None,
            )
        self.assertEqual(
            raised.exception.code,
            "CLOUDFLARE_STAGING_SECRET_NOT_UNIQUE",
        )
        self.assertEqual(api.method_count("GET"), 1)
        sleep.assert_not_called()

    def test_release_contract_freezes_secret_convergence_policy(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        candidate = contract["candidate"]
        cutover = contract["cutover"]
        self.assertIs(
            candidate["staging_worker_secret_state_convergence_required"],
            True,
        )
        self.assertIs(
            candidate["staging_worker_secret_state_convergence_read_only"],
            True,
        )
        self.assertIs(
            candidate["staging_worker_secret_mutation_repeat_for_convergence_allowed"],
            False,
        )
        self.assertEqual(
            candidate["staging_worker_secret_state_convergence_attempts"],
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS,
        )
        self.assertEqual(
            candidate["staging_worker_secret_state_convergence_delay_seconds"],
            secret_state._SECRET_STATE_CONVERGENCE_DELAY_SECONDS,
        )
        self.assertIs(
            cutover["production_database_secret_state_convergence_required"],
            True,
        )
        self.assertIs(
            cutover["production_database_secret_state_convergence_read_only"],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_secret_mutation_repeat_for_convergence_allowed"
            ],
            False,
        )
        self.assertEqual(
            cutover["production_database_secret_state_convergence_attempts"],
            secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS,
        )
        self.assertEqual(
            cutover["production_database_secret_state_convergence_delay_seconds"],
            secret_state._SECRET_STATE_CONVERGENCE_DELAY_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
