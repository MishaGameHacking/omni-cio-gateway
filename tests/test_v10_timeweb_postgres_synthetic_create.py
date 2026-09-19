from __future__ import annotations

import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock
from urllib.error import HTTPError

from scripts import check_v10_timeweb_postgres_synthetic_create as guard
from scripts import probe_v10_timeweb_postgres_control_plane as read_only
from scripts import provision_v10_timeweb_postgres_synthetic as provisioner


def _json_response(payload: object, *, status: int = 200) -> mock.MagicMock:
    raw = json.dumps(payload).encode("utf-8")
    response = mock.MagicMock()
    response.status = status
    response.read.side_effect = lambda amount=-1: raw if amount < 0 else raw[:amount]
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    return response


def _sequence_opener(*outcomes: object) -> mock.Mock:
    opener = mock.Mock()
    opener.open.side_effect = list(outcomes)
    return opener


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
        opener = _sequence_opener(
            _json_response(
                    {
                        "db": {
                            "id": 91,
                            "name": read_only.TARGET_CLUSTER_NAME,
                        }
                    },
                    status=201,
                )
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
        self.assertEqual(opener.open.call_count, 1)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://api.timeweb.cloud/api/v1/databases",
        )
        self.assertIn("Bearer synthetic-token", request.headers.values())
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertNotIn("synthetic-token", rendered)

    def test_ambiguous_post_reconciles_by_get_without_second_post(self) -> None:
        mutation_opener = _sequence_opener(OSError("lost response"))
        read_opener = _sequence_opener(
            _json_response(
                    {
                        "databases": [
                            {
                                "id": 91,
                                "name": read_only.TARGET_CLUSTER_NAME,
                            }
                        ]
                    }
                )
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
        self.assertEqual(mutation_opener.open.call_count, 1)
        self.assertEqual(mutation_opener.open.call_args.args[0].get_method(), "POST")
        self.assertEqual(read_opener.open.call_count, 1)
        self.assertEqual(read_opener.open.call_args.args[0].get_method(), "GET")

    def test_ambiguous_post_without_reconciliation_never_retries(self) -> None:
        mutation_opener = _sequence_opener(OSError("lost response"))
        read_opener = _sequence_opener(_json_response({"databases": []}))
        mutation_api = provisioner.TimewebCreateApi(
            "synthetic-token",
            opener=mutation_opener,
        )
        read_api = read_only.TimewebReadOnlyApi(
            "synthetic-token",
            opener=read_opener,
        )
        payload = provisioner._create_payload(
            provider_type="postgres18",
            preset_id=777,
            project_id="42",
        )
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS_RECONCILIATION_REQUIRED",
        ):
            provisioner._create_or_reconcile(
                mutation_api,
                read_api,
                "/api/v1/projects/42/resources/databases",
                payload,
                sleeper=lambda _seconds: None,
                reconcile_delays=(),
            )
        self.assertEqual(mutation_opener.open.call_count, 1)

    def test_transient_http_post_is_ambiguous_not_retried(self) -> None:
        failure = HTTPError(
            "https://api.timeweb.cloud/api/v1/databases",
            503,
            "unavailable",
            {},
            io.BytesIO(b"do not emit"),
        )
        opener = _sequence_opener(failure)
        api = provisioner.TimewebCreateApi("synthetic-token", opener=opener)
        payload = provisioner._create_payload(
            provider_type="postgres18",
            preset_id=777,
            project_id="42",
        )
        with self.assertRaisesRegex(
            provisioner.AmbiguousCreate,
            "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS",
        ):
            api.post_once(payload)
        self.assertEqual(opener.open.call_count, 1)

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
