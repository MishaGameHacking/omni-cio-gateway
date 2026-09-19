from __future__ import annotations

import io
import json
from unittest import mock
import unittest
from urllib.error import HTTPError

from scripts import check_v10_timeweb_postgres_control_plane as guard
from scripts import probe_v10_timeweb_postgres_control_plane as probe


class _Response:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self._raw
        return self._raw[:amount]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        del args


class _Opener:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> _Response:
        del timeout
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, _Response)
        return outcome


class TimewebControlPlaneTests(unittest.TestCase):
    def test_source_contract_is_valid(self) -> None:
        guard.validate()

    def test_project_id_rejects_non_ascii_digits(self) -> None:
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_PROJECT_ID_INVALID",
        ):
            probe._project_id("١٢٣")

    def test_project_selection_is_exact_and_unique(self) -> None:
        payload = {
            "projects": [
                {"id": 1, "name": "Other"},
                {"id": 2, "name": probe.TARGET_PROJECT_NAME},
            ]
        }
        self.assertEqual(probe._select_project(payload), "2")

    def test_postgres18_type_is_discovered_not_hardcoded(self) -> None:
        payload = {
            "types": [
                {
                    "name": "PostgreSQL",
                    "version": "18",
                    "type": "pg_current_18",
                    "is_deprecated": False,
                }
            ]
        }
        self.assertEqual(
            probe._select_postgres18_type(payload),
            "pg_current_18",
        )

    def test_deprecated_postgres18_type_is_rejected(self) -> None:
        payload = {
            "types": [
                {
                    "name": "PostgreSQL",
                    "version": 18,
                    "type": "postgres18",
                    "is_deprecated": True,
                }
            ]
        }
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_POSTGRES18_TYPE_NOT_UNIQUE",
        ):
            probe._select_postgres18_type(payload)

    def test_beta_preset_requires_exact_resources_and_price(self) -> None:
        payload = {
            "databases_presets": [
                {
                    "id": 777,
                    "type": "postgres",
                    "location": "ru-3",
                    "cpu": 1,
                    "ram": 2048,
                    "disk": 20480,
                    "price": 790,
                }
            ]
        }
        probe._select_target_preset(payload, "postgres18")

    def test_beta_preset_price_drift_fails_closed(self) -> None:
        payload = {
            "databases_presets": [
                {
                    "id": 777,
                    "type": "postgres",
                    "location": "ru-3",
                    "cpu": 1,
                    "ram": 2048,
                    "disk": 20480,
                    "price": 791,
                }
            ]
        }
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_BETA_PRESET_NOT_UNIQUE_OR_PRICE_DRIFT",
        ):
            probe._select_target_preset(payload, "postgres18")

    def test_existing_target_cluster_fails_closed(self) -> None:
        payload = {
            "databases": [
                {"id": 99, "name": probe.TARGET_CLUSTER_NAME},
            ]
        }
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_TARGET_CLUSTER_ALREADY_EXISTS",
        ):
            probe._verify_cluster_name_available(payload)

    def test_read_only_api_masks_auth_failure(self) -> None:
        request = HTTPError(
            "https://api.timeweb.cloud/api/v1/projects",
            403,
            "forbidden",
            {},
            io.BytesIO(b'{"detail":"do not emit"}'),
        )
        opener = _Opener([request])
        api = probe.TimewebReadOnlyApi(
            "synthetic-token",
            opener=opener,
        )
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT",
        ):
            api.get("/api/v1/projects")

    def test_transient_get_retry_is_bounded(self) -> None:
        first = HTTPError(
            "https://api.timeweb.cloud/api/v1/projects",
            429,
            "rate limited",
            {},
            io.BytesIO(b"provider detail"),
        )
        opener = _Opener(
            [
                first,
                _Response({"projects": []}),
            ]
        )
        sleeps: list[float] = []
        api = probe.TimewebReadOnlyApi(
            "synthetic-token",
            opener=opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(api.get("/api/v1/projects"), {"projects": []})
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(len(opener.requests), 2)

    def test_request_is_get_only_and_token_is_not_emitted(self) -> None:
        opener = _Opener([_Response({"projects": []})])
        api = probe.TimewebReadOnlyApi(
            "synthetic-token",
            opener=opener,
        )
        with mock.patch("builtins.print") as output:
            api.get("/api/v1/projects")
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn(
            "Bearer synthetic-token",
            request.headers.values(),
        )
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertNotIn("synthetic-token", rendered)


if __name__ == "__main__":
    unittest.main()
