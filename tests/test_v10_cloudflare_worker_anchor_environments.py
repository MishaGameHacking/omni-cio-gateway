from __future__ import annotations

import io
from typing import Any
import unittest
from unittest.mock import patch

import scripts.probe_v10_cloudflare_staging_worker_anchor as anchor


class _Api:
    def __init__(self, rows: object) -> None:
        self.account_id = "a" * 32
        self.token = "masked-token"
        self.rows = rows

    def request(self, method: str, path: str, **kwargs: Any) -> object:
        if kwargs:
            raise AssertionError(kwargs)
        if method != "GET" or path != f"/accounts/{self.account_id}/workers/scripts":
            raise AssertionError((method, path))
        return self.rows


class CloudflareWorkerAnchorEnvironmentTests(unittest.TestCase):
    def test_production_probe_reuses_only_production_worker(self) -> None:
        environment = {
            "CLOUDFLARE_API_TOKEN": "masked-token",
            "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        }
        api = _Api([{"id": "omni-cio-v10-web", "tag": "b" * 32}])
        output = io.StringIO()
        with patch.object(anchor, "CloudflareApi", return_value=api):
            code = anchor.probe_worker_anchor(
                environment,
                environment="production",
                output=output,
            )
        self.assertEqual(code, 0)
        self.assertIn("CLOUDFLARE_PRODUCTION_WORKER_ANCHOR=REUSED", output.getvalue())

    def test_production_probe_does_not_accept_staging_anchor(self) -> None:
        environment = {
            "CLOUDFLARE_API_TOKEN": "masked-token",
            "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        }
        api = _Api([{"id": "omni-cio-v10-web-staging", "tag": "b" * 32}])
        output = io.StringIO()
        with patch.object(anchor, "CloudflareApi", return_value=api):
            code = anchor.probe_worker_anchor(
                environment,
                environment="production",
                output=output,
            )
        self.assertEqual(code, 10)
        self.assertIn(
            "CLOUDFLARE_PRODUCTION_WORKER_ANCHOR=BOOTSTRAP_REQUIRED",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
