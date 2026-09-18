from __future__ import annotations

import io
from pathlib import Path
from typing import Any
import unittest
from unittest.mock import patch

import scripts.manage_v10_cloudflare_production as production


ROOT = Path(__file__).resolve().parents[1]
_ACCOUNT_ID = "a" * 32
_ZONE_ID = "b" * 32
_VERSION_ID = "11111111-2222-3333-4444-555555555555"


class _Api:
    def __init__(self, responses: dict[tuple[str, str], Any]) -> None:
        self.account_id = _ACCOUNT_ID
        self.token = "masked-token"
        self.responses = responses
        self.calls: list[tuple[str, str, object | None]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        **kwargs: Any,
    ) -> Any:
        if kwargs:
            raise AssertionError(kwargs)
        self.calls.append((method, path, body))
        key = (method, path)
        if key not in self.responses:
            raise AssertionError(key)
        result = self.responses[key]
        if isinstance(result, Exception):
            raise result
        return result


class CloudflareProductionManagerTests(unittest.TestCase):
    @staticmethod
    def _environment() -> dict[str, str]:
        return {
            "CLOUDFLARE_API_TOKEN": "masked-token",
            "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
            "OMNI_V10_CLOUDFLARE_CUSTOM_HOST": "omni.example.ru",
            "CLOUDFLARE_ZONE_ID": _ZONE_ID,
            "CLOUDFLARE_ZONE_NAME": "example.ru",
        }

    def test_runtime_secret_probe_distinguishes_reuse_and_bootstrap_without_value_access(
        self,
    ) -> None:
        path = f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/secrets"
        scenarios = (
            ([{"name": "OMNI_V10_POSTGRES_DSN", "type": "secret_text"}], 0, "REUSED"),
            ([], 10, "BOOTSTRAP_REQUIRED"),
        )
        for rows, expected_code, marker in scenarios:
            with self.subTest(marker=marker):
                api = _Api({("GET", path): rows})
                output = io.StringIO()
                with patch.object(production, "_api", return_value=api):
                    code = production.probe_runtime_secret(
                        self._environment(),
                        output=output,
                    )
                self.assertEqual(code, expected_code)
                self.assertIn(marker, output.getvalue())
                self.assertNotIn("text", output.getvalue())


    def test_telegram_readiness_requires_prod_secrets_and_staging_isolation(
        self,
    ) -> None:
        production_path = (
            f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/secrets"
        )
        staging_path = (
            f"/accounts/{_ACCOUNT_ID}/workers/scripts/"
            "omni-cio-v10-web-staging/secrets"
        )
        required = [
            {"name": name, "type": "secret_text"}
            for name in production._TELEGRAM_LOGIN_BINDINGS
        ]
        api = _Api(
            {
                ("GET", production_path): [
                    {"name": "OMNI_V10_POSTGRES_DSN", "type": "secret_text"},
                    *required,
                ],
                ("GET", staging_path): [
                    {"name": "OMNI_V10_POSTGRES_DSN", "type": "secret_text"}
                ],
            }
        )
        output = io.StringIO()
        with patch.object(production, "_api", return_value=api):
            code = production.probe_telegram_login_readiness(
                self._environment(),
                output=output,
            )
        self.assertEqual(code, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY "
            "production_bindings=4 staging_bindings=0",
        )

    def test_telegram_readiness_rejects_missing_duplicate_or_type_drift(self) -> None:
        path = f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/secrets"
        staging = (
            f"/accounts/{_ACCOUNT_ID}/workers/scripts/"
            "omni-cio-v10-web-staging/secrets"
        )
        required = [
            {"name": name, "type": "secret_text"}
            for name in production._TELEGRAM_LOGIN_BINDINGS
        ]
        drift = [dict(row) for row in required]
        drift[0]["type"] = "plain_text"
        scenarios = (
            (required[:-1], "CLOUDFLARE_TELEGRAM_LOGIN_BINDING_MISSING"),
            (
                [*required, dict(required[0])],
                "CLOUDFLARE_TELEGRAM_LOGIN_SECRET_NOT_UNIQUE",
            ),
            (drift, "CLOUDFLARE_TELEGRAM_LOGIN_SECRET_TYPE_DRIFT"),
        )
        for rows, marker in scenarios:
            with self.subTest(marker=marker):
                api = _Api({("GET", path): rows, ("GET", staging): []})
                output = io.StringIO()
                with patch.object(production, "_api", return_value=api):
                    code = production.probe_telegram_login_readiness(
                        self._environment(),
                        output=output,
                    )
                self.assertEqual(code, 78)
                self.assertIn(marker, output.getvalue())

    def test_telegram_readiness_blocks_staging_or_value_exposure(self) -> None:
        production_path = (
            f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/secrets"
        )
        staging_path = (
            f"/accounts/{_ACCOUNT_ID}/workers/scripts/"
            "omni-cio-v10-web-staging/secrets"
        )
        required = [
            {"name": name, "type": "secret_text"}
            for name in production._TELEGRAM_LOGIN_BINDINGS
        ]

        leaked = [dict(row) for row in required]
        leaked[1]["text"] = "must-never-be-printed"
        api = _Api({("GET", production_path): leaked})
        output = io.StringIO()
        with patch.object(production, "_api", return_value=api):
            code = production.probe_telegram_login_readiness(
                self._environment(),
                output=output,
            )
        self.assertEqual(code, 78)
        self.assertIn("CLOUDFLARE_TELEGRAM_LOGIN_SECRET_VALUE_EXPOSURE", output.getvalue())
        self.assertNotIn("must-never-be-printed", output.getvalue())

        api = _Api(
            {
                ("GET", production_path): required,
                ("GET", staging_path): [dict(required[0])],
            }
        )
        output = io.StringIO()
        with patch.object(production, "_api", return_value=api):
            code = production.probe_telegram_login_readiness(
                self._environment(),
                output=output,
            )
        self.assertEqual(code, 78)
        self.assertIn(
            "CLOUDFLARE_TELEGRAM_LOGIN_STAGING_BINDING_EXPOSED",
            output.getvalue(),
        )

    def test_telegram_readiness_workflow_reuses_existing_provider_custody(self) -> None:
        workflow = (
            ROOT / ".github/workflows/v10-cloudflare-provider-readiness.yml"
        ).read_text(encoding="utf-8")
        command = (
            "python -m scripts.manage_v10_cloudflare_production "
            "probe-telegram-login-readiness"
        )
        self.assertEqual(workflow.count(command), 1)
        for name in production._TELEGRAM_LOGIN_BINDINGS:
            self.assertNotIn(f"secrets.{name}", workflow)
        self.assertNotIn('"PUBLIC_MULTI_USER_ENABLED": "true"', (ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
        self.assertNotIn('"OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true"', (ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
        self.assertNotIn('"OMNI_V10_VK_ID_LOGIN_ENABLED": "true"', (ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))

    def test_domain_config_requires_ru_zone_and_host_within_zone(self) -> None:
        environment = self._environment()
        self.assertEqual(
            production.validate_domain_config(environment), "omni.example.ru"
        )

        invalid_zone = dict(environment, CLOUDFLARE_ZONE_NAME="example.com")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_PRODUCTION_ZONE_NAME_INVALID",
        ):
            production.validate_domain_config(invalid_zone)

        invalid_host = dict(environment, OMNI_V10_CLOUDFLARE_CUSTOM_HOST="other.ru")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_PRODUCTION_HOST_ZONE_MISMATCH",
        ):
            production.validate_domain_config(invalid_host)

    def test_existing_custom_domain_is_reused_only_with_exact_worker_and_zone_authority(
        self,
    ) -> None:
        environment = self._environment()
        path = f"/accounts/{_ACCOUNT_ID}/workers/domains?hostname=omni.example.ru"
        exact = {
            "id": "domain-id",
            "hostname": "omni.example.ru",
            "service": "omni-cio-v10-web",
            "zone_id": _ZONE_ID,
            "zone_name": "example.ru",
        }
        api = _Api({("GET", path): [exact]})
        with (
            patch.object(production, "_api", return_value=api),
            patch.object(production.builds, "_write_output") as write_output,
        ):
            self.assertFalse(production.attach_domain(environment))
        write_output.assert_called_once_with("custom_domain_created", "false")
        self.assertEqual(api.calls, [("GET", path, None)])

        drift = dict(exact, service="other-worker")
        api = _Api({("GET", path): [drift]})
        with patch.object(production, "_api", return_value=api):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_DOMAIN_AUTHORITY_DRIFT",
            ):
                production.attach_domain(environment)

    def test_new_custom_domain_records_rollback_intent_before_provider_mutation(
        self,
    ) -> None:
        environment = self._environment()
        list_path = f"/accounts/{_ACCOUNT_ID}/workers/domains?hostname=omni.example.ru"
        attach_path = f"/accounts/{_ACCOUNT_ID}/workers/domains"
        provider_error = production.builds.BootstrapStopped(
            "CLOUDFLARE_SYNTHETIC_ATTACH_FAILURE"
        )
        api = _Api(
            {
                ("GET", list_path): [],
                ("PUT", attach_path): provider_error,
            }
        )
        with (
            patch.object(production, "_api", return_value=api),
            patch.object(production.builds, "_write_output") as write_output,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_SYNTHETIC_ATTACH_FAILURE",
            ):
                production.attach_domain(environment)
        write_output.assert_called_once_with("custom_domain_created", "true")

    def test_new_custom_domain_preserves_rollback_output_when_response_drifts(
        self,
    ) -> None:
        environment = self._environment()
        list_path = f"/accounts/{_ACCOUNT_ID}/workers/domains?hostname=omni.example.ru"
        attach_path = f"/accounts/{_ACCOUNT_ID}/workers/domains"
        drift = {
            "id": "domain-id",
            "hostname": "omni.example.ru",
            "service": "other-worker",
            "zone_id": _ZONE_ID,
            "zone_name": "example.ru",
        }
        api = _Api({("GET", list_path): [], ("PUT", attach_path): drift})
        with (
            patch.object(production, "_api", return_value=api),
            patch.object(production.builds, "_write_output") as write_output,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_DOMAIN_ATTACH_DRIFT",
            ):
                production.attach_domain(environment)
        write_output.assert_called_once_with("custom_domain_created", "true")

    def test_snapshot_requires_single_version_at_one_hundred_percent(self) -> None:
        path = f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/deployments"
        payload = {
            "deployments": [
                {"versions": [{"percentage": 100, "version_id": _VERSION_ID}]}
            ]
        }
        api = _Api({("GET", path): payload})
        with (
            patch.object(production, "_api", return_value=api),
            patch.object(production.builds, "_write_output") as write_output,
        ):
            self.assertEqual(
                production.snapshot_active_deployment(self._environment()), _VERSION_ID
            )
        write_output.assert_called_once_with("previous_version_id", _VERSION_ID)

        split_payload = {
            "deployments": [
                {
                    "versions": [
                        {"percentage": 50, "version_id": _VERSION_ID},
                        {
                            "percentage": 50,
                            "version_id": "22222222-3333-4444-5555-666666666666",
                        },
                    ]
                }
            ]
        }
        api = _Api({("GET", path): split_payload})
        environment = self._environment()
        with patch.object(production, "_api", return_value=api):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_SPLIT_DEPLOYMENT_FORBIDDEN",
            ):
                production.snapshot_active_deployment(environment)

    def test_snapshot_accepts_exact_float_hundred_without_float_equality(self) -> None:
        path = f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/deployments"
        payload = {
            "deployments": [
                {"versions": [{"percentage": 100.0, "version_id": _VERSION_ID}]}
            ]
        }
        api = _Api({("GET", path): payload})
        with (
            patch.object(production, "_api", return_value=api),
            patch.object(production.builds, "_write_output"),
        ):
            self.assertEqual(
                production.snapshot_active_deployment(self._environment()), _VERSION_ID
            )

    def test_snapshot_rejects_boolean_percentage_with_classified_error(self) -> None:
        path = f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/deployments"
        environment = self._environment()
        for percentage in (True, False):
            with self.subTest(percentage=percentage):
                payload = {
                    "deployments": [
                        {
                            "versions": [
                                {"percentage": percentage, "version_id": _VERSION_ID}
                            ]
                        }
                    ]
                }
                api = _Api({("GET", path): payload})
                with patch.object(production, "_api", return_value=api):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "CLOUDFLARE_PRODUCTION_SPLIT_DEPLOYMENT_FORBIDDEN",
                    ):
                        production.snapshot_active_deployment(environment)


if __name__ == "__main__":
    unittest.main()
