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

    def test_terminal_invariant_guard_accepts_equivalent_tuple_syntax(self) -> None:
        source = """
def _verify_terminal_shape():
    expected = [
        ('is_enabled_public_network', False, 'TIMEWEB_CLUSTER_PUBLIC_NETWORK_DRIFT'),
        ('is_autobackups_enabled', False, 'TIMEWEB_CLUSTER_AUTOBACKUPS_DRIFT'),
        ('is_backup_schedule_enabled', False, 'TIMEWEB_CLUSTER_BACKUP_SCHEDULE_DRIFT'),
    ]
"""
        guard._validate_terminal_false_invariants(source)

    def test_terminal_invariant_guard_rejects_missing_required_invariant(self) -> None:
        source = """
def _verify_terminal_shape():
    expected = (
        ("is_enabled_public_network", False, "TIMEWEB_CLUSTER_PUBLIC_NETWORK_DRIFT"),
        ("is_autobackups_enabled", False, "TIMEWEB_CLUSTER_AUTOBACKUPS_DRIFT"),
    )
"""
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_SYNTHETIC_CREATE_PROVISIONER_DRIFT",
        ):
            guard._validate_terminal_false_invariants(source)

    def test_paid_create_transport_is_owner_approved_ipv4(self) -> None:
        guard._require_parity_transport_ready()
        payload = json.loads(Path(guard.CONTRACT).read_text(encoding="utf-8"))
        transport = payload["parity_transport_gate"]
        target = payload["target"]
        self.assertEqual(transport["status"], "READY")
        self.assertEqual(
            transport["selected_mode"],
            "PUBLIC_IPV4_OWNER_APPROVED",
        )
        self.assertTrue(transport["public_ipv4_owner_approval_recorded"])
        self.assertTrue(target["public_ipv4_authorized"])
        self.assertFalse(target["public_ipv6_authorized"])

    def test_blocked_transport_copy_still_fails_closed(self) -> None:
        payload = json.loads(Path(guard.CONTRACT).read_text(encoding="utf-8"))
        transport = payload["parity_transport_gate"]
        target = payload["target"]
        transport["status"] = "BLOCKED_PENDING_PROOF"
        transport["selected_mode"] = None
        transport["public_ipv4_owner_approval_recorded"] = False
        guard._validate_transport_state(transport, target, require_ready=False)
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_BLOCKED",
        ):
            guard._validate_transport_state(transport, target, require_ready=True)

    def test_transport_state_machine_accepts_exactly_one_proved_ready_mode(
        self,
    ) -> None:
        payload = json.loads(Path(guard.CONTRACT).read_text(encoding="utf-8"))
        transport = payload["parity_transport_gate"]
        transport["status"] = "READY"
        transport["selected_mode"] = "TIMEWEB_PRIVATE_VPC_RUNNER"
        transport["private_vpc_runner_evidence_accepted"] = True
        transport["public_ipv6_reachability_accepted"] = False
        transport["public_ipv4_owner_approval_recorded"] = False
        target = payload["target"]
        guard._validate_transport_state(transport, target, require_ready=True)

        transport["public_ipv6_reachability_accepted"] = True
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID",
        ):
            guard._validate_transport_state(transport, target, require_ready=True)

    def test_transport_state_machine_rejects_unproved_ready_mode(self) -> None:
        payload = json.loads(Path(guard.CONTRACT).read_text(encoding="utf-8"))
        transport = payload["parity_transport_gate"]
        transport["status"] = "READY"
        transport["selected_mode"] = "PUBLIC_IPV6_PROVEN"
        transport["private_vpc_runner_evidence_accepted"] = False
        transport["public_ipv6_reachability_accepted"] = False
        transport["public_ipv4_owner_approval_recorded"] = False
        target = payload["target"]
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID",
        ):
            guard._validate_transport_state(transport, target, require_ready=True)

    def test_public_transport_cannot_be_ready_while_create_shape_forbids_it(
        self,
    ) -> None:
        payload = json.loads(Path(guard.CONTRACT).read_text(encoding="utf-8"))
        transport = payload["parity_transport_gate"]
        target = payload["target"]
        transport["status"] = "READY"
        transport["selected_mode"] = "PUBLIC_IPV6_PROVEN"
        transport["private_vpc_runner_evidence_accepted"] = False
        transport["public_ipv6_reachability_accepted"] = True
        transport["public_ipv4_owner_approval_recorded"] = False
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_SYNTHETIC_CREATE_PARITY_TRANSPORT_INVALID",
        ):
            guard._validate_transport_state(transport, target, require_ready=True)

    def test_transport_gate_records_explicit_ipv4_security_authority(self) -> None:
        payload = json.loads(Path(guard.CONTRACT).read_text(encoding="utf-8"))
        transport = payload["parity_transport_gate"]
        target = payload["target"]
        self.assertEqual(transport["status"], "READY")
        self.assertEqual(
            transport["selected_mode"],
            "PUBLIC_IPV4_OWNER_APPROVED",
        )
        self.assertTrue(target["public_ipv4_authorized"])
        self.assertFalse(target["public_ipv6_authorized"])
        self.assertEqual(transport["public_ipv4_recurring_price_rub"], 200)
        self.assertTrue(transport["public_ipv4_price_is_separate_from_base_790"])
        self.assertTrue(transport["public_ipv4_security_source_required"])
        self.assertTrue(transport["public_ipv4_firewall_drop_required"])
        self.assertTrue(transport["public_ipv4_tls_verify_full_required"])

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

    def test_provider_convergence_budgets_are_multi_minute_and_workflow_bounded(
        self,
    ) -> None:
        reconcile_budget = sum(provisioner._RECONCILE_DELAYS_SECONDS)
        start_budget = sum(provisioner._START_DELAYS_SECONDS)
        self.assertGreaterEqual(reconcile_budget, 180.0)
        self.assertLess(reconcile_budget, 10 * 60)
        self.assertGreaterEqual(start_budget, 600.0)
        self.assertLess(start_budget, 13 * 60)

        read_attempts = len(read_only._RETRY_DELAYS_SECONDS) + 1
        read_retry_sleep_budget = sum(read_only._RETRY_DELAYS_SECONDS)
        observations = len(provisioner._START_DELAYS_SECONDS) + 1
        per_observation_read_budget = (
            read_attempts * provisioner._START_READ_TIMEOUT_SECONDS
            + read_retry_sleep_budget
        )
        worst_case_wait_budget = (
            start_budget + observations * per_observation_read_budget
        )
        workflow_budget = 35 * 60
        self.assertGreaterEqual(
            workflow_budget - worst_case_wait_budget,
            600.0,
        )

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

    def test_conflict_and_locked_create_enter_get_only_reconciliation(self) -> None:
        payload = provisioner._create_payload(
            provider_type="postgres18",
            preset_id=777,
            project_id="42",
        )
        for status in (409, 423):
            with self.subTest(status=status):
                failure = HTTPError(
                    "https://api.timeweb.cloud/api/v1/databases",
                    status,
                    "provider state conflict",
                    {},
                    io.BytesIO(b"provider-private-body"),
                )
                opener = _sequence_opener(failure)
                api = provisioner.TimewebCreateApi(
                    "synthetic-token",
                    opener=opener,
                )
                with self.assertRaises(provisioner.AmbiguousCreate):
                    api.post_once(payload)
                self.assertEqual(opener.open.call_count, 1)

    def test_ambiguous_reconcile_survives_transient_control_plane_read(self) -> None:
        api = mock.Mock()
        transient = provisioner._provider_base.ProvisioningStopped(
            "TIMEWEB_API_NETWORK_ERROR"
        )
        api.get.side_effect = [
            transient,
            {
                "databases": [
                    {
                        "id": 91,
                        "name": read_only.TARGET_CLUSTER_NAME,
                    }
                ]
            },
        ]
        sleeps: list[float] = []
        cluster_id = provisioner._reconcile_cluster_id(
            api,
            "/api/v1/projects/42/resources/databases",
            sleeper=sleeps.append,
            delays=(0.0,),
        )
        self.assertEqual(cluster_id, 91)
        self.assertEqual(api.get.call_count, 2)
        self.assertEqual(sleeps, [0.0])

    def test_ambiguous_reconcile_classifies_control_plane_only_timeout(self) -> None:
        api = mock.Mock()
        transient = provisioner._provider_base.ProvisioningStopped(
            "TIMEWEB_API_NETWORK_ERROR"
        )
        api.get.side_effect = [transient, transient]
        with self.assertRaises(
            provisioner._provider_base.ProvisioningStopped
        ) as raised:
            provisioner._reconcile_cluster_id(
                api,
                "/api/v1/projects/42/resources/databases",
                sleeper=lambda _seconds: None,
                delays=(0.0,),
            )
        self.assertEqual(
            raised.exception.code,
            "TIMEWEB_CLUSTER_CREATE_CONTROL_PLANE_READ_TIMEOUT",
        )

    def test_create_post_distinguishes_authentication_and_authorization(self) -> None:
        cases = (
            (401, read_only.AUTHENTICATION_REJECTED_CODE),
            (403, read_only.AUTHORIZATION_REJECTED_CODE),
        )
        payload = provisioner._create_payload(
            provider_type="postgres18",
            preset_id=777,
            project_id="42",
        )
        for status, expected_code in cases:
            with self.subTest(status=status):
                failure = HTTPError(
                    "https://api.timeweb.cloud/api/v1/databases",
                    status,
                    "auth rejected",
                    {},
                    io.BytesIO(b"provider-private-body"),
                )
                opener = _sequence_opener(failure)
                api = provisioner.TimewebCreateApi(
                    "synthetic-token",
                    opener=opener,
                )
                with self.assertRaises(
                    provisioner._provider_base.ProvisioningStopped
                ) as raised:
                    api.post_once(payload)
                self.assertEqual(raised.exception.code, expected_code)
                self.assertEqual(raised.exception.status, status)
                self.assertNotIn("provider-private-body", str(raised.exception))
                self.assertEqual(opener.open.call_count, 1)

    def test_provision_auth_failure_does_not_construct_create_writer(self) -> None:
        read_api = mock.Mock()
        with (
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=read_api,
            ),
            mock.patch.object(
                provisioner.read_only,
                "verify_credential_health",
                side_effect=provisioner._provider_base.ProvisioningStopped(
                    read_only.AUTHENTICATION_REJECTED_CODE,
                    status=401,
                ),
            ),
            mock.patch.object(provisioner, "TimewebCreateApi") as writer,
        ):
            with self.assertRaises(
                provisioner._provider_base.ProvisioningStopped
            ) as raised:
                provisioner.provision()
        self.assertEqual(
            raised.exception.code,
            read_only.AUTHENTICATION_REJECTED_CODE,
        )
        writer.assert_not_called()

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

    def test_start_wait_survives_transient_control_plane_read(self) -> None:
        api = mock.Mock()
        transient = provisioner._provider_base.ProvisioningStopped(
            "TIMEWEB_API_NETWORK_ERROR"
        )
        started = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 1,
                "ram": 2048,
                "preset_id": 777,
                "disk": {"size": 20_971_520, "used": 0},
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [{"id": 501, "db_id": 91}],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        api.get.side_effect = [transient, started]
        sleeps: list[float] = []
        provisioner._wait_for_started(
            api,
            91,
            provider_type="postgres18",
            preset_id=777,
            sleeper=sleeps.append,
            delays=(0.0,),
        )
        self.assertEqual(api.get.call_count, 2)
        self.assertEqual(
            [call.kwargs for call in api.get.call_args_list],
            [{"timeout": 10.0}, {"timeout": 10.0}],
        )
        self.assertEqual(sleeps, [0.0])

    def test_start_wait_classifies_control_plane_only_timeout(self) -> None:
        api = mock.Mock()
        transient = provisioner._provider_base.ProvisioningStopped(
            "TIMEWEB_API_NETWORK_ERROR"
        )
        api.get.side_effect = [transient, transient]
        with self.assertRaises(
            provisioner._provider_base.ProvisioningStopped
        ) as raised:
            provisioner._wait_for_started(
                api,
                91,
                provider_type="postgres18",
                preset_id=777,
                sleeper=lambda _seconds: None,
                delays=(0.0,),
            )
        self.assertEqual(
            raised.exception.code,
            "TIMEWEB_CLUSTER_START_CONTROL_PLANE_READ_TIMEOUT",
        )

    def test_start_wait_classifies_persistent_starting_state_separately(self) -> None:
        api = mock.Mock()
        starting = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "status": "starting",
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
            }
        }
        api.get.side_effect = [starting, starting]
        with self.assertRaises(
            provisioner._provider_base.ProvisioningStopped
        ) as raised:
            provisioner._wait_for_started(
                api,
                91,
                provider_type="postgres18",
                preset_id=777,
                sleeper=lambda _seconds: None,
                delays=(0.0,),
            )
        self.assertEqual(
            raised.exception.code,
            "TIMEWEB_CLUSTER_STARTING_READY_TIMEOUT",
        )
        self.assertEqual(api.get.call_count, 2)

    def test_start_wait_can_converge_after_many_safe_starting_observations(
        self,
    ) -> None:
        api = mock.Mock()
        starting = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "status": "starting",
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
            }
        }
        started = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 1,
                "ram": 2048,
                "preset_id": 777,
                "disk": {"size": 20_971_520, "used": 0},
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [{"id": 501, "db_id": 91}],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        api.get.side_effect = [starting] * 6 + [started]
        sleeps: list[float] = []
        provisioner._wait_for_started(
            api,
            91,
            provider_type="postgres18",
            preset_id=777,
            sleeper=sleeps.append,
            delays=(0.0,) * 6,
        )
        self.assertEqual(api.get.call_count, 7)
        self.assertEqual(sleeps, [0.0] * 6)

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
                "disk": {"size": 20_971_520, "used": 0},
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [{"id": 501, "db_id": 91}],
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

    def test_terminal_shape_rejects_replica_topology_count_drift(self) -> None:
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
                "disk": {"size": 20_971_520},
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [
                    {"id": 501, "db_id": 91},
                    {"id": 502, "db_id": 91},
                    {"id": 503, "db_id": 91},
                ],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_REPLICA_TOPOLOGY_DRIFT",
        ):
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            )

    def test_starting_shape_rejects_explicit_replica_topology_drift(self) -> None:
        payload = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "status": "starting",
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "replica_list": [
                    {"id": 501, "db_id": 91},
                    {"id": 502, "db_id": 91},
                    {"id": 503, "db_id": 91},
                ],
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_REPLICA_TOPOLOGY_DRIFT",
        ):
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
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
                "disk": {"size": 20_971_520},
                "is_enabled_public_network": True,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [{"id": 501, "db_id": 91}],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_PUBLIC_NETWORK_DRIFT",
        ):
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            )

    def test_starting_shape_allows_transient_missing_terminal_fields(self) -> None:
        payload = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "status": "starting",
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
            }
        }
        self.assertEqual(
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            ),
            "starting",
        )

    def test_starting_shape_rejects_explicit_unsafe_public_network(self) -> None:
        payload = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "status": "starting",
                "is_enabled_public_network": True,
                "is_enabled_public_ipv6": False,
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_PUBLIC_NETWORK_DRIFT",
        ):
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            )

    def test_terminal_shape_uses_field_specific_sanitized_drift_code(self) -> None:
        payload = {
            "db": {
                "id": 91,
                "name": read_only.TARGET_CLUSTER_NAME,
                "type": "postgres18",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 2,
                "ram": 2048,
                "preset_id": 777,
                "disk": {"size": 20_971_520},
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [{"id": 501, "db_id": 91}],
                "disk_autoscaling": {"is_enabled": False},
                "status": "started",
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_CPU_DRIFT",
        ):
            provisioner._verify_cluster_shape(
                payload,
                expected_cluster_id=91,
                provider_type="postgres18",
                preset_id=777,
            )

    def test_existing_exact_target_enters_get_only_recovery_without_writer(
        self,
    ) -> None:
        read_api = mock.Mock()
        project_path = "/api/v1/projects/42/resources/databases"
        responses = {
            "/api/v1/database-types": {
                "types": [
                    {
                        "name": "PostgreSQL",
                        "version": "18",
                        "type": "postgres18",
                        "is_deprecated": False,
                    }
                ]
            },
            "/api/v2/presets/dbs": {
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
            },
            project_path: {
                "databases": [
                    {"id": 91, "name": read_only.TARGET_CLUSTER_NAME},
                ]
            },
            "/api/v1/databases/91": {
                "db": {
                    "id": 91,
                    "name": read_only.TARGET_CLUSTER_NAME,
                    "type": "postgres18",
                    "location": "ru-3",
                    "availability_zone": "msk-1",
                    "cpu": 1,
                    "ram": 2048,
                    "preset_id": 777,
                    "disk": {"size": 20_971_520},
                    "is_enabled_public_network": False,
                    "is_enabled_public_ipv6": False,
                    "is_autobackups_enabled": False,
                    "is_backup_schedule_enabled": False,
                    "replica_list": [{"id": 501, "db_id": 91}],
                    "disk_autoscaling": {"is_enabled": False},
                    "status": "started",
                }
            },
        }
        read_api.get.side_effect = responses.__getitem__
        with (
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=read_api,
            ),
            mock.patch.object(
                provisioner.read_only,
                "verify_credential_health",
                return_value="42",
            ),
            mock.patch.object(provisioner, "TimewebCreateApi") as writer,
            mock.patch.object(provisioner._provider_base, "_emit"),
        ):
            provisioner.provision()
        writer.assert_not_called()

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
