from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json
import os
import tempfile
from typing import cast
import unittest
from unittest.mock import MagicMock, Mock, patch

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
    ) -> object | None:
        del timeout
        self.calls.append((method, path, body, expected))
        if method != "GET":
            return None
        if not self.get_responses:
            raise AssertionError("unexpected secret-state read")
        response = self.get_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def method_count(self, method: str) -> int:
        return sum(call[0] == method for call in self.calls)


@contextmanager
def _token_patches() -> Iterator[MagicMock]:
    with (
        patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
        patch.object(custody.builds, "_mask"),
        patch.object(secret_state.time, "sleep") as sleep,
    ):
        yield sleep


class CloudflareWorkerSecretConvergenceTests(unittest.TestCase):
    def _assert_method_counts(
        self,
        api: _SecretApi,
        *,
        put: int,
        delete: int,
        get: int,
    ) -> None:
        self.assertEqual(api.method_count("PUT"), put)
        self.assertEqual(api.method_count("DELETE"), delete)
        self.assertEqual(api.method_count("GET"), get)

    def _write_production_runtime_secret(
        self,
        api: _SecretApi,
        *,
        expected_error: str | None = None,
    ) -> MagicMock:
        with tempfile.TemporaryDirectory() as temp_dir:
            dsn_file = Path(temp_dir) / "omni-cio-v10-cloudflare-production-dsn.txt"
            dsn_file.write_text(_SYNTHETIC_DSN, encoding="utf-8")
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
                if expected_error is None:
                    production.put_runtime_secret({"RUNNER_TEMP": temp_dir})
                else:
                    with self.assertRaises(builds.BootstrapStopped) as raised:
                        production.put_runtime_secret({"RUNNER_TEMP": temp_dir})
                    self.assertEqual(raised.exception.code, expected_error)
        return sleep

    def test_read_only_helper_waits_for_delayed_state_without_hiding_errors(
        self,
    ) -> None:
        reader = Mock(side_effect=[False, False, True])
        with patch.object(secret_state.time, "sleep") as sleep:
            self.assertTrue(secret_state.wait_for_secret_state(reader, True))
        self.assertEqual((reader.call_count, sleep.call_count), (3, 2))
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
        token = _secret_row(custody._SYNC_TOKEN_BINDING)
        api = _SecretApi([token, [], [], token, token, []])
        with _token_patches() as sleep:
            with custody.bootstrap_origin_sync_token(
                cast(builds.CloudflareApi, api)
            ) as actual:
                self.assertEqual(actual, _SYNC_TOKEN)
        self._assert_method_counts(api, put=1, delete=2, get=6)
        self.assertEqual(sleep.call_count, 3)

    def test_sync_token_preclear_exhaustion_stays_fail_closed_without_put(self) -> None:
        attempts = secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS
        api = _SecretApi([_secret_row(custody._SYNC_TOKEN_BINDING)] * attempts)
        typed_api = cast(builds.CloudflareApi, api)
        with _token_patches() as sleep:
            with self.assertRaises(builds.BootstrapStopped) as raised:
                with custody.bootstrap_origin_sync_token(typed_api):
                    pass
        self.assertEqual(raised.exception.code, custody._SYNC_TOKEN_STALE)
        self._assert_method_counts(api, put=0, delete=1, get=attempts)
        self.assertEqual(sleep.call_count, attempts - 1)

    def test_sync_token_cleanup_exhaustion_stays_fail_closed_without_redelete(
        self,
    ) -> None:
        attempts = secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS
        token = _secret_row(custody._SYNC_TOKEN_BINDING)
        api = _SecretApi([[], token] + [token] * attempts)
        typed_api = cast(builds.CloudflareApi, api)
        with _token_patches() as sleep:
            with self.assertRaises(builds.BootstrapStopped) as raised:
                with custody.bootstrap_origin_sync_token(typed_api):
                    pass
        self.assertEqual(raised.exception.code, custody._SYNC_TOKEN_STALE)
        self._assert_method_counts(api, put=1, delete=2, get=attempts + 2)
        self.assertEqual(sleep.call_count, attempts - 1)

    def test_staging_runtime_secret_waits_read_only_after_single_put(self) -> None:
        binding = staging_secrets._RUNTIME_DSN_BINDING
        api = _SecretApi([[], _secret_row(binding)])
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
        self._assert_method_counts(api, put=1, delete=0, get=2)
        self.assertEqual(sleep.call_count, 1)

    def test_production_runtime_secret_convergence_and_exhaustion(self) -> None:
        binding = production._RUNTIME_DSN_BINDING
        delayed = _SecretApi([[], _secret_row(binding)])
        delayed_sleep = self._write_production_runtime_secret(delayed)
        self._assert_method_counts(delayed, put=1, delete=0, get=2)
        self.assertEqual(delayed_sleep.call_count, 1)

        attempts = secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS
        exhausted = _SecretApi([[]] * attempts)
        exhausted_sleep = self._write_production_runtime_secret(
            exhausted,
            expected_error="CLOUDFLARE_PRODUCTION_SECRET_VERIFY_FAILED",
        )
        self._assert_method_counts(exhausted, put=1, delete=0, get=attempts)
        self.assertEqual(exhausted_sleep.call_count, attempts - 1)

    def test_staging_list_404_does_not_prove_secret_absence(self) -> None:
        api = _SecretApi(
            [builds.BootstrapStopped("CLOUDFLARE_API_HTTP_ERROR", status=404)]
        )
        typed_api = cast(builds.CloudflareApi, api)
        with (
            patch.object(secret_state.time, "sleep") as sleep,
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            staging_secrets.wait_staging_secret_type(
                typed_api,
                custody._SYNC_TOKEN_BINDING,
                None,
            )
        self.assertEqual(
            (raised.exception.code, raised.exception.status),
            ("CLOUDFLARE_API_HTTP_ERROR", 404),
        )
        self._assert_method_counts(api, put=0, delete=0, get=1)
        sleep.assert_not_called()

    def test_malformed_and_duplicate_staging_state_are_not_retried(self) -> None:
        target = {"name": custody._SYNC_TOKEN_BINDING, "type": "secret_text"}
        cases = (
            (
                "malformed-row",
                [target, {"name": "UNRELATED_SECRET"}],
                "CLOUDFLARE_STAGING_SECRETS_INVALID",
            ),
            (
                "duplicate-target",
                [target, target],
                "CLOUDFLARE_STAGING_SECRET_NOT_UNIQUE",
            ),
        )
        for label, response, expected_code in cases:
            with self.subTest(label=label):
                api = _SecretApi([response])
                typed_api = cast(builds.CloudflareApi, api)
                with (
                    patch.object(secret_state.time, "sleep") as sleep,
                    self.assertRaises(builds.BootstrapStopped) as raised,
                ):
                    staging_secrets.wait_staging_secret_type(
                        typed_api,
                        custody._SYNC_TOKEN_BINDING,
                        "secret_text",
                    )
                self.assertEqual(raised.exception.code, expected_code)
                self._assert_method_counts(api, put=0, delete=0, get=1)
                sleep.assert_not_called()

    def test_malformed_production_secret_state_is_not_retried(self) -> None:
        binding = production._RUNTIME_DSN_BINDING
        api = _SecretApi([[{"name": binding, "type": "secret_text"}, None]])
        typed_api = cast(builds.CloudflareApi, api)
        with (
            patch.object(secret_state.time, "sleep") as sleep,
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            production._wait_runtime_secret_present(typed_api)
        self.assertEqual(raised.exception.code, "CLOUDFLARE_PRODUCTION_SECRETS_INVALID")
        self._assert_method_counts(api, put=0, delete=0, get=1)
        sleep.assert_not_called()

    def test_release_contract_freezes_secret_convergence_policy(self) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        expected = {
            "candidate": {
                "staging_worker_secret_state_convergence_required": True,
                "staging_worker_secret_state_convergence_read_only": True,
                "staging_worker_secret_mutation_repeat_for_convergence_allowed": False,
                "staging_worker_secret_state_convergence_attempts": (
                    secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS
                ),
                "staging_worker_secret_state_convergence_delay_seconds": (
                    secret_state._SECRET_STATE_CONVERGENCE_DELAY_SECONDS
                ),
            },
            "cutover": {
                "production_database_secret_state_convergence_required": True,
                "production_database_secret_state_convergence_read_only": True,
                "production_database_secret_mutation_repeat_for_convergence_allowed": (
                    False
                ),
                "production_database_secret_state_convergence_attempts": (
                    secret_state._SECRET_STATE_CONVERGENCE_ATTEMPTS
                ),
                "production_database_secret_state_convergence_delay_seconds": (
                    secret_state._SECRET_STATE_CONVERGENCE_DELAY_SECONDS
                ),
            },
        }
        for section, fields in expected.items():
            for field, value in fields.items():
                with self.subTest(section=section, field=field):
                    self.assertEqual(contract[section][field], value)


if __name__ == "__main__":
    unittest.main()
