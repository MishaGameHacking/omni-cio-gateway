from __future__ import annotations

import io
from pathlib import Path
from typing import Any
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.probe_v10_cloudflare_telegram_login_readiness as probe


ROOT = Path(__file__).resolve().parents[1]
_ACCOUNT_ID = "a" * 32
_TOKEN = "synthetic-token"
_PRODUCTION_PATH = (
    f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web/secrets"
)
_STAGING_PATH = (
    f"/accounts/{_ACCOUNT_ID}/workers/scripts/omni-cio-v10-web-staging/secrets"
)
_REQUIRED_ROWS = [
    {"name": name, "type": "secret_text"} for name in probe._REQUIRED_BINDINGS
]


class _Api:
    account_id = _ACCOUNT_ID

    def __init__(self, responses: dict[tuple[str, str], object]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        if kwargs:
            raise AssertionError(kwargs)
        self.requests.append((method, path))
        result = self.responses[(method, path)]
        if isinstance(result, Exception):
            raise result
        return result


def _environment() -> dict[str, str]:
    return {
        "CLOUDFLARE_API_TOKEN": _TOKEN,
        "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
    }


def _run(
    production_rows: object,
    staging_rows: object,
) -> tuple[int, str, _Api]:
    api = _Api(
        {
            ("GET", _PRODUCTION_PATH): production_rows,
            ("GET", _STAGING_PATH): staging_rows,
        }
    )
    output = io.StringIO()
    with (
        patch.object(builds, "CloudflareApi", return_value=api),
        patch.object(builds, "_mask"),
    ):
        rc = probe.probe_readiness(_environment(), output=output)
    return rc, output.getvalue().strip(), api


class CloudflareTelegramLoginReadinessTests(unittest.TestCase):
    def test_ready_requires_four_prod_secrets_and_zero_staging_bindings(
        self,
    ) -> None:
        production = [
            {"name": "OMNI_V10_POSTGRES_DSN", "type": "secret_text"},
            *_REQUIRED_ROWS,
        ]
        staging = [{"name": "OMNI_V10_POSTGRES_DSN", "type": "secret_text"}]
        rc, output, api = _run(production, staging)
        self.assertEqual(rc, 0)
        self.assertEqual(
            output,
            "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY "
            "production_bindings=4 staging_bindings=0",
        )
        self.assertEqual(
            api.requests,
            [("GET", _PRODUCTION_PATH), ("GET", _STAGING_PATH)],
        )

    def test_missing_production_binding_blocks_without_naming_or_values(self) -> None:
        production = _REQUIRED_ROWS[:-1]
        rc, output, _ = _run(production, [])
        self.assertEqual(rc, 78)
        self.assertEqual(
            output,
            "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=BLOCKED "
            "code=CLOUDFLARE_TELEGRAM_LOGIN_BINDING_MISSING",
        )
        self.assertNotIn(probe._REQUIRED_BINDINGS[-1], output)

    def test_duplicate_or_non_secret_production_binding_blocks(self) -> None:
        duplicate = [*_REQUIRED_ROWS, dict(_REQUIRED_ROWS[0])]
        rc, output, _ = _run(duplicate, [])
        self.assertEqual(rc, 78)
        self.assertIn("CLOUDFLARE_TELEGRAM_LOGIN_SECRET_NOT_UNIQUE", output)

        drift = [dict(row) for row in _REQUIRED_ROWS]
        drift[0]["type"] = "plain_text"
        rc, output, _ = _run(drift, [])
        self.assertEqual(rc, 78)
        self.assertIn("CLOUDFLARE_TELEGRAM_LOGIN_SECRET_TYPE_DRIFT", output)

    def test_staging_provider_binding_exposure_blocks(self) -> None:
        rc, output, _ = _run(_REQUIRED_ROWS, [dict(_REQUIRED_ROWS[0])])
        self.assertEqual(rc, 78)
        self.assertIn("CLOUDFLARE_TELEGRAM_LOGIN_STAGING_BINDING_EXPOSED", output)

    def test_provider_value_exposure_blocks_without_echoing_value(self) -> None:
        leaked = [dict(row) for row in _REQUIRED_ROWS]
        leaked[1]["text"] = "must-never-be-printed"
        rc, output, _ = _run(leaked, [])
        self.assertEqual(rc, 78)
        self.assertIn("CLOUDFLARE_TELEGRAM_LOGIN_SECRET_VALUE_EXPOSURE", output)
        self.assertNotIn("must-never-be-printed", output)

    def test_cloudflare_authority_failure_remains_blocking_and_sanitized(self) -> None:
        api = _Api(
            {
                (
                    "GET",
                    _PRODUCTION_PATH,
                ): builds.BootstrapStopped(
                    "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
                    status=403,
                )
            }
        )
        output = io.StringIO()
        with (
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(builds, "_mask"),
        ):
            rc = probe.probe_readiness(_environment(), output=output)
        self.assertEqual(rc, 78)
        self.assertEqual(
            output.getvalue().strip(),
            "CLOUDFLARE_TELEGRAM_LOGIN_READINESS=BLOCKED "
            "code=CLOUDFLARE_API_TOKEN_INSUFFICIENT status=403",
        )
        self.assertNotIn(_TOKEN, output.getvalue())

    def test_workflow_uses_existing_cloudflare_custody_only(self) -> None:
        workflow_path = ROOT / ".github/workflows/v10-cloudflare-provider-readiness.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        command = "python -m scripts.probe_v10_cloudflare_telegram_login_readiness"
        self.assertEqual(workflow.count(command), 1)
        command_index = workflow.index(command)
        accept_marker = "Accept provider readiness after database authority resolution"
        accept_index = workflow.index(accept_marker)
        self.assertLess(command_index, accept_index)
        for name in probe._REQUIRED_BINDINGS:
            self.assertNotIn(f"secrets.{name}", workflow)
        self.assertIn("secrets.CLOUDFLARE_API_TOKEN", workflow)
        self.assertIn("secrets.CLOUDFLARE_ACCOUNT_ID", workflow)

    def test_readiness_change_does_not_activate_public_or_vk_authority(self) -> None:
        wrangler = (ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
        self.assertNotIn('"PUBLIC_MULTI_USER_ENABLED": "true"', wrangler)
        self.assertNotIn('"OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true"', wrangler)
        self.assertNotIn('"OMNI_V10_VK_ID_LOGIN_ENABLED": "true"', wrangler)


if __name__ == "__main__":
    unittest.main()
