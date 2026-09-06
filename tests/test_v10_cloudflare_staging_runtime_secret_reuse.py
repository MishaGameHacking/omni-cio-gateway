from __future__ import annotations

import io
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.probe_v10_cloudflare_staging_runtime_secret as probe
import scripts.run_v10_cloudflare_gated_candidate as gated


_ACCOUNT_ID = "a" * 32


class _Api:
    account_id = _ACCOUNT_ID

    def __init__(self, result: object) -> None:
        self.result = result
        self.requests: list[tuple[str, str]] = []

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        del kwargs
        self.requests.append((method, path))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class CloudflareStagingRuntimeSecretReuseTests(unittest.TestCase):
    def test_probe_reuses_exact_secret_text_binding_without_value_read(self) -> None:
        api = _Api([{"name": "OMNI_V10_POSTGRES_DSN", "type": "secret_text"}])
        output = io.StringIO()
        with (
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(builds, "_mask"),
        ):
            rc = probe.probe_runtime_secret(
                {
                    "CLOUDFLARE_API_TOKEN": "synthetic-token",
                    "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
                },
                output=output,
            )
        self.assertEqual(rc, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "CLOUDFLARE_STAGING_DATABASE_SECRET=REUSED",
        )
        self.assertEqual(len(api.requests), 1)
        self.assertEqual(api.requests[0][0], "GET")
        self.assertTrue(api.requests[0][1].endswith("/secrets"))

    def test_probe_requires_bootstrap_when_binding_is_absent(self) -> None:
        api = _Api([])
        with (
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(builds, "_mask"),
        ):
            rc = probe.probe_runtime_secret(
                {
                    "CLOUDFLARE_API_TOKEN": "synthetic-token",
                    "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
                },
                output=io.StringIO(),
            )
        self.assertEqual(rc, 10)

    def test_probe_requires_bootstrap_when_staging_worker_is_absent(self) -> None:
        api = _Api(
            builds.BootstrapStopped("CLOUDFLARE_API_HTTP_ERROR", status=404)
        )
        output = io.StringIO()
        with (
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(builds, "_mask"),
        ):
            rc = probe.probe_runtime_secret(
                {
                    "CLOUDFLARE_API_TOKEN": "synthetic-token",
                    "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
                },
                output=output,
            )
        self.assertEqual(rc, 10)
        self.assertEqual(
            output.getvalue().strip(),
            "CLOUDFLARE_STAGING_DATABASE_SECRET=BOOTSTRAP_REQUIRED",
        )

    def test_probe_keeps_cloudflare_authority_failure_blocking(self) -> None:
        api = _Api(
            builds.BootstrapStopped(
                "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
                status=403,
            )
        )
        output = io.StringIO()
        with (
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(builds, "_mask"),
        ):
            rc = probe.probe_runtime_secret(
                {
                    "CLOUDFLARE_API_TOKEN": "synthetic-token",
                    "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
                },
                output=output,
            )
        self.assertEqual(rc, 78)
        self.assertIn("status=403", output.getvalue())

    def test_probe_rejects_binding_type_drift(self) -> None:
        api = _Api([{"name": "OMNI_V10_POSTGRES_DSN", "type": "plain_text"}])
        with (
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(builds, "_mask"),
        ):
            rc = probe.probe_runtime_secret(
                {
                    "CLOUDFLARE_API_TOKEN": "synthetic-token",
                    "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
                },
                output=io.StringIO(),
            )
        self.assertEqual(rc, 78)

    def test_candidate_reuses_provider_secret_when_no_dsn_file_exists(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with TemporaryDirectory() as temp:
            dsn = Path(temp) / "omni-cio-v10-cloudflare-staging-dsn.txt"
            with (
                patch.object(builds, "_staging_dsn_file", return_value=dsn),
                patch.object(gated, "_runtime_secret_present", return_value=True),
                patch.object(gated, "put_staging_runtime_secret") as put_secret,
            ):
                gated._sync_runtime_secret(api)
        put_secret.assert_not_called()

    def test_candidate_refreshes_provider_secret_when_fresh_dsn_exists(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with TemporaryDirectory() as temp:
            dsn = Path(temp) / "omni-cio-v10-cloudflare-staging-dsn.txt"
            dsn.write_text("synthetic-dsn", encoding="utf-8")
            with (
                patch.object(builds, "_staging_dsn_file", return_value=dsn),
                patch.object(gated, "_runtime_secret_present") as present,
                patch.object(gated, "put_staging_runtime_secret") as put_secret,
            ):
                gated._sync_runtime_secret(api)
        put_secret.assert_called_once_with(api)
        present.assert_not_called()

    def test_candidate_fails_closed_without_fresh_or_existing_secret(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with TemporaryDirectory() as temp:
            dsn = Path(temp) / "omni-cio-v10-cloudflare-staging-dsn.txt"
            with (
                patch.object(builds, "_staging_dsn_file", return_value=dsn),
                patch.object(gated, "_runtime_secret_present", return_value=False),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_STAGING_DATABASE_SECRET_MISSING",
                ):
                    gated._sync_runtime_secret(api)


if __name__ == "__main__":
    unittest.main()
