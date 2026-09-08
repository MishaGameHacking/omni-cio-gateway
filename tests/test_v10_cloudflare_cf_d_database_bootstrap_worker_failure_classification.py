from __future__ import annotations

import json
import unittest

from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    NEON_BOOTSTRAP_REJECTED,
    WORKER_FAILURE_STATUS_BY_CODE,
    classify_neon_bootstrap_provider_failure,
)


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class CloudflareCfDDatabaseBootstrapWorkerFailureClassificationTests(unittest.TestCase):
    def test_worker_failures_require_exact_code_status_and_shape(self) -> None:
        for code, status in WORKER_FAILURE_STATUS_BY_CODE.items():
            with self.subTest(code=code, status=status):
                content = _json_bytes({"detail": code})
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(status, content),
                    code,
                )
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(599, content),
                    NEON_BOOTSTRAP_REJECTED,
                )
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(
                        status,
                        _json_bytes({"detail": code, "extra": "forbidden"}),
                    ),
                    NEON_BOOTSTRAP_REJECTED,
                )


if __name__ == "__main__":
    unittest.main()
