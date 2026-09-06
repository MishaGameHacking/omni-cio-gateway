from __future__ import annotations

import unittest
from typing import Any, cast

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.cloudflare_staging_secrets as staging_secrets


class _RecordingApi:
    account_id = "a" * 32

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


class CloudflareStagingSecretsTests(unittest.TestCase):
    def test_secret_put_accepts_update_and_created_success_statuses(self) -> None:
        api = _RecordingApi()

        staging_secrets.put_staging_secret(
            cast(builds.CloudflareApi, api),
            "OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN",
            "redacted-test-value",
        )

        self.assertEqual(len(api.calls), 1)
        method, path, body, expected = api.calls[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(path, staging_secrets._secret_path(cast(builds.CloudflareApi, api)))
        self.assertEqual(
            body,
            {
                "name": "OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN",
                "text": "redacted-test-value",
                "type": "secret_text",
            },
        )
        self.assertEqual(expected, frozenset({200, 201}))


if __name__ == "__main__":
    unittest.main()
