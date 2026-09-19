from __future__ import annotations

import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request

from scripts import check_v10_timeweb_postgres_synthetic_create as guard
from scripts import probe_v10_timeweb_postgres_control_plane as read_only
from scripts import provision_v10_timeweb_postgres_synthetic as provisioner


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
        self.requests: list[Request] = []

    def open(self, request: Request, *, timeout: float) -> _Response:
        del timeout
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, _Response)
        return outcome


class TimewebSyntheticCreateTests(unittest.TestCase):
    def test_source_contract_passes(self) -> None:
        guard.validate()

    def test_read_only_preset_returns_exact_provider_id(self) -> None:
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
        self.assertEqual(
            read_only._select_target_preset(payload, "postgres18"),
            777,
        )

    def test_create_payload_is_exact_and_has_no_addon_authority(self) -> None:
        payload = provisioner._create_payload(
            provider_type="postgres18",
            preset_id=777,
            project_id="42",
        )
        self.assertEqual(
            payload,
            {
                "availability_zone": "msk-1",
                "description": "Omni-CIO V10 RU-PG-B synthetic parity",
                "disk_autoscaling": {"is_enabled": False},
                "is_public_ipv6": False,
                "name": "omni-cio-v10-ru-pg-synthetic",
                "preset_id": 777,
                "project_id": 42,
                "type": "postgres18",
            },
        )
        for forbidden in (
            "admin",
            "instance",
            "network",
            "replication",
            "auto_backups",
            "backup_schedule",
            "maintenance_slot",
            "configuration",
            "config_parameters",
        ):
            self.assertNotIn(forbidden, payload)

    def test_create_post_is_exactly_once_and_secret_is_not_emitted(self) -> None:
        opener = _Opener(
            [
                _Response(
                    {
                        "db": {
                            "id": 91,
                            "name": read_only.TARGET_CLUSTER_NAME,
                        }
                    },
                    status=201,
                )
            ]
        )
        api = provisioner.TimewebCreateApi("synthetic-token", opener=opener)
        with mock.patch("builtins.print") as output:
            response = api.post_once(
                provisioner._create_payload(
                    provider_type="postgres18",
                    preset_id=777,
                    project_id="42",
                )
            )
        self.assertEqual(provisioner._create_response_cluster_id(response), 91)
        self.assertEqual(len(opener.requests), 1)
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://api.timeweb.cloud/api/v1/databases",
        )
        self.assertIn("Bearer synthetic-token", request.headers.values())
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertNotIn("synthetic-token", rendered)

    def test_ambiguous_post_reconciles_by_get_without_second_post(self) -> None:
        mutation_opener = _Opener([OSError("lost response")])
        read_opener = _Opener(
            [
                _Response(
                    {
                        "databases": [
                            {
                                "id": 91,
                                "name": read_only.TARGET_CLUSTER_NAME,
                            }
                        ]
                    }
                )
            ]
        )
        mutation_api = provisioner.TimewebCreateApi(
            "synthetic-token",
            opener=mutation_opener,
        )
        read_api = read_only.TimewebReadOnlyApi(
            "synthetic-token",
            opener=read_opener,
        )
        cluster_id, mode = provisioner._create_or_reconcile(
            mutation_api,
            read_api,
            "/api/v1/projects/42/resources/databases",
            provisioner._create_payload(
                provider_type="postgres18",
                preset_id=777,
                project_id="42",
            ),
            sleeper=lambda _seconds: None,
            reconcile_delays=(),
        )
        self.assertEqual((cluster_id, mode), (91, "reconciled"))
        self.assertEqual(len(mutation_opener.requests), 1)
        self.assertEqual(mutation_opener.requests[0].get_method(), "POST")
        self.assertEqual(len(read_opener.requests), 1)
        self.assertEqual(read_opener.requests[0].get_method(), "GET")

    def test_ambiguous_post_without_reconciliation_never_retries(self) -> None:
        mutation_opener = _Opener([OSError("lost response")])
        read_opener = _Opener([_Response({"databases": []})])
        mutation_api = provisioner.TimewebCreateApi(
            "synthetic-token",
            opener=mutation_opener,
        )
        read_api = read_only.TimewebReadOnlyApi(
            "synthetic-token",
            opener=read_opener,
        )
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS_RECONCILIATION_REQUIRED",
        ):
            provisioner._create_or_reconcile(
                mutation_api,
                read_api,
                "/api/v1/projects/42/resources/databases",
                provisioner._create_payload(
                    provider_type="postgres18",
                    preset_id=777,
                    project_id="42",
                ),
                sleeper=lambda _seconds: None,
                reconcile_delays=(),
            )
        self.assertEqual(len(mutation_opener.requests), 1)

    def test_transient_http_post_is_ambiguous_not_retried(self) -> None:
        failure = HTTPError(
            "https://api.timeweb.cloud/api/v1/databases",
            503,
            "unavailable",
            {},
            io.BytesIO(b"do not emit"),
        )
        opener = _Opener([failure])
        api = provisioner.TimewebCreateApi("synthetic-token", opener=opener)
        with self.assertRaisesRegex(
            provisioner.AmbiguousCreate,
            "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS",
        ):
            api.post_once(
                provisioner._create_payload(
                    provider_type="postgres18",
                    preset_id=777,
                    project_id="42",
                )
            )
        self.assertEqual(len(opener.requests), 1)

    def test_post_create_shape_requires_no_paid_addons(self) -> None:
        payload = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 1,
                "ram": 2048,
                "preset_id": 777,
                "disk": {"size": 20480, "used": 0},
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        self.assertEqual(
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            ),
            "started",
        )

    def test_public_network_after_create_fails_closed(self) -> None:
        payload = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 1,
                "ram": 2048,
                "preset_id": 777,
                "disk": {"size": 20480},
                "is_enabled_public_network": True,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_POST_CREATE_DRIFT",
        ):
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            )

    def test_duplicate_target_cluster_fails_closed(self) -> None:
        payload = {
            "databases": [
                {"id": 91, "name": read_only.TARGET_CLUSTER_NAME},
                {"id": 92, "name": read_only.TARGET_CLUSTER_NAME},
            ]
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_TARGET_CLUSTER_NOT_UNIQUE",
        ):
            provisioner._target_cluster_id(payload)

    def test_confirmation_is_exact(self) -> None:
        with mock.patch.dict(
            os.environ,
            {provisioner.CREATE_CONFIRMATION_ENV: "WRONG"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_CLUSTER_CREATE_CONFIRMATION_REQUIRED",
            ):
                provisioner._required_confirmation()

        with mock.patch.dict(
            os.environ,
            {
                provisioner.CREATE_CONFIRMATION_ENV: provisioner.CREATE_CONFIRMATION,
            },
            clear=True,
        ):
            provisioner._required_confirmation()

    def test_contract_does_not_record_full_base_sha_literal(self) -> None:
        source = Path(guard.CONTRACT).read_text(encoding="utf-8")
        payload = json.loads(source)
        parts = payload["accepted_base_sha_parts"]
        self.assertNotIn("".join(parts), source)


if __name__ == "__main__":
    unittest.main()
