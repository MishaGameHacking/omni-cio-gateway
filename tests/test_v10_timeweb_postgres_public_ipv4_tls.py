from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import unittest
from unittest import mock
from urllib.error import HTTPError

from scripts import check_v10_timeweb_postgres_public_ipv4_tls as guard
from scripts import discover_v10_ru_pg_verifier_ipv4 as discoverer
from scripts import provision_v10_timeweb_postgres_public_ipv4_tls as provisioner


class TimewebPublicIpv4TlsTests(unittest.TestCase):
    @staticmethod
    def _healthy_credential_preflight() -> Any:
        return mock.patch.object(
            provisioner.read_only,
            "verify_credential_health",
            return_value="42",
        )

    def test_source_contract_passes(self) -> None:
        guard.validate()

    def test_verifier_cidr_requires_exact_global_ipv4_32(self) -> None:
        with mock.patch.dict(
            os.environ,
            {provisioner.VERIFIER_CIDR_ENV: "203.0.113.7/32"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_VERIFIER_CIDR_INVALID",
            ):
                provisioner._required_verifier_cidr()

        with mock.patch.dict(
            os.environ,
            {provisioner.VERIFIER_CIDR_ENV: "8.8.8.8/32"},
            clear=True,
        ):
            self.assertEqual(provisioner._required_verifier_cidr(), "8.8.8.8/32")

    def test_wildcard_firewall_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_FIREWALL_WILDCARD_FORBIDDEN",
        ):
            provisioner._rule_body("0.0.0.0/0")

    def test_firewall_rule_shape_is_exact(self) -> None:
        self.assertEqual(
            provisioner._rule_body("8.8.8.8/32"),
            {
                "description": "Omni-CIO RU-PG-B verifier PostgreSQL",
                "direction": "ingress",
                "port": "5432",
                "protocol": "tcp",
                "cidr": "8.8.8.8/32",
            },
        )

    def test_cluster_shape_rejects_mb_value_on_kb_provider_surface(self) -> None:
        api = mock.Mock()
        api.get.return_value = {
            "db": {
                "name": "omni-cio-v10-ru-pg-synthetic",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 1,
                "ram": 2048,
                "port": 5432,
                "disk": {"size": 20480},
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [{"id": 501, "db_id": 91}],
                "disk_autoscaling": {"is_enabled": False},
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_DISK_SIZE_DRIFT",
        ):
            provisioner._cluster(api, 91)

    def test_cluster_shape_rejects_replica_topology_count_drift(self) -> None:
        api = mock.Mock()
        api.get.return_value = {
            "db": {
                "name": "omni-cio-v10-ru-pg-synthetic",
                "location": "ru-3",
                "availability_zone": "msk-1",
                "cpu": 1,
                "ram": 2048,
                "port": 5432,
                "disk": {"size": 20_971_520},
                "is_enabled_public_ipv6": False,
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "replica_list": [
                    {"id": 501, "db_id": 91},
                    {"id": 502, "db_id": 91},
                    {"id": 503, "db_id": 91},
                ],
                "disk_autoscaling": {"is_enabled": False},
            }
        }
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_CLUSTER_REPLICA_TOPOLOGY_DRIFT",
        ):
            provisioner._cluster(api, 91)

    def test_public_ipv4_patch_excludes_tls_and_waits_for_binding(self) -> None:
        mutation = mock.Mock()
        api = mock.Mock()
        public_ready = {
            "is_enabled_public_network": True,
            "is_enabled_public_ipv6": False,
            "is_secure_connection_enabled": False,
            "status": "started",
        }
        with mock.patch.object(
            provisioner,
            "_wait_public_ipv4_ready",
            return_value=public_ready,
        ) as wait:
            actual = provisioner._patch_public_ipv4(
                mutation,
                api,
                91,
                "8.8.4.4",
            )
        self.assertIs(actual, public_ready)
        mutation.mutate_once.assert_called_once_with(
            "PATCH",
            "/api/v2/databases/91",
            operation="DATABASE_PUBLIC_IPV4_PATCH",
            body={
                "floating_ip": "8.8.4.4",
                "is_enabled_public_network": True,
                "is_enabled_public_ipv6": False,
            },
            expected_statuses=frozenset({200}),
            reconcile_statuses=provisioner._RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
        wait.assert_called_once_with(api, 91, "8.8.4.4")

    def test_tls_enable_patch_is_separate_after_public_ipv4(self) -> None:
        mutation = mock.Mock()
        api = mock.Mock()
        ready = {
            "is_enabled_public_network": True,
            "is_enabled_public_ipv6": False,
            "is_secure_connection_enabled": True,
            "status": "started",
            "domains": [{"fqdn": "example.twc1.net", "cert_status": "issued"}],
        }
        with mock.patch.object(
            provisioner,
            "_wait_network_ready",
            return_value=ready,
        ) as wait:
            actual = provisioner._enable_secure_connection(mutation, api, 91)
        self.assertIs(actual, ready)
        mutation.mutate_once.assert_called_once_with(
            "PATCH",
            "/api/v2/databases/91",
            operation="DATABASE_TLS_ENABLE_PATCH",
            body={"is_secure_connection_enable": True},
            expected_statuses=frozenset({200}),
            reconcile_statuses=provisioner._RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
        wait.assert_called_once_with(api, 91)

    def test_tls_context_uses_client_protocol_tls12_floor_and_verify_full(self) -> None:
        context = mock.Mock()
        with mock.patch.object(
            provisioner.ssl,
            "SSLContext",
            return_value=context,
        ) as constructor:
            actual = provisioner._tls_client_context(Path("provider-ca.crt"))
        self.assertIs(actual, context)
        constructor.assert_called_once_with(provisioner.ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(
            context.minimum_version,
            provisioner.ssl.TLSVersion.TLSv1_2,
        )
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, provisioner.ssl.CERT_REQUIRED)
        context.load_verify_locations.assert_called_once_with(cafile="provider-ca.crt")

    def test_multiple_firewall_groups_are_rejected(self) -> None:
        api = mock.Mock()
        with mock.patch.object(
            provisioner,
            "_service_groups",
            return_value=[{"id": "group-1"}, {"id": "group-2"}],
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_FIREWALL_SERVICE_GROUPS_NOT_EXCLUSIVE",
            ):
                provisioner._verify_exclusive_firewall(api, "group-1", 91)

    def test_safe_preexisting_rule_must_be_single_global_ipv4_32(self) -> None:
        api = mock.Mock()
        safe = {
            "description": "Omni-CIO RU-PG-B verifier PostgreSQL",
            "direction": "ingress",
            "port": "5432",
            "protocol": "tcp",
            "cidr": "8.8.8.8/32",
        }
        with mock.patch.object(provisioner, "_rules", return_value=[safe]):
            provisioner._verify_safe_narrow_rule(api, "group-1")

        unsafe = dict(safe)
        unsafe["cidr"] = "0.0.0.0/0"
        with mock.patch.object(provisioner, "_rules", return_value=[unsafe]):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_PREEXISTING_FIREWALL_NOT_NARROW",
            ):
                provisioner._verify_safe_narrow_rule(api, "group-1")

    def test_preexisting_public_ipv6_is_closed_and_rejected(self) -> None:
        api = mock.Mock()
        mutation = mock.Mock()
        initial = {
            "is_enabled_public_network": False,
            "is_enabled_public_ipv6": True,
        }
        with (
            self._healthy_credential_preflight(),
            mock.patch.object(provisioner, "_verify_allocation_prerequisite"),
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner,
                "_required_verifier_cidr",
                return_value="8.8.8.8/32",
            ),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            mock.patch.object(
                provisioner,
                "TimewebMutationApi",
                return_value=mutation,
            ),
            mock.patch.object(
                provisioner,
                "_target_cluster_id",
                return_value=91,
            ),
            mock.patch.object(
                provisioner,
                "_cluster",
                return_value=initial,
            ),
            mock.patch.object(provisioner, "_close_public_network") as close,
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_PREEXISTING_PUBLIC_IPV6_UNSAFE",
            ):
                provisioner.provision()
        close.assert_called_once_with(mutation, api, 91)

    def test_public_patch_failure_triggers_public_network_rollback(self) -> None:
        initial = {
            "is_enabled_public_network": False,
        }
        api = mock.Mock()
        mutation = mock.Mock()
        with (
            self._healthy_credential_preflight(),
            mock.patch.object(provisioner, "_verify_allocation_prerequisite"),
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner,
                "_required_verifier_cidr",
                return_value="8.8.8.8/32",
            ),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner,
                "_target_cluster_id",
                return_value=91,
            ),
            mock.patch.object(
                provisioner,
                "_cluster",
                return_value=initial,
            ),
            mock.patch.object(
                provisioner,
                "_ensure_group",                return_value="group-1",
            ),
            mock.patch.object(provisioner, "_ensure_rule"),
            mock.patch.object(provisioner, "_ensure_resource_link"),
            mock.patch.object(provisioner, "_verify_group"),
            mock.patch.object(provisioner, "_verify_exclusive_firewall"),
            mock.patch.object(
                provisioner,
                "_floating_ips",
                return_value=[],
            ),
            mock.patch.object(
                provisioner,
                "_resolve_transport_ipv4",
                return_value=("ip-1", "8.8.4.4", True),
            ),
            mock.patch.object(
                provisioner,
                "_network_ready",
                return_value=False,
            ),
            mock.patch.object(
                provisioner,
                "_patch_public_ipv4",
                side_effect=provisioner._provider_base.ProvisioningStopped(
                    "TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT"
                ),
            ),
            mock.patch.object(provisioner, "_close_public_network") as close,
            mock.patch.object(provisioner, "_delete_created_ipv4_if_unbound"),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            mock.patch.object(
                provisioner,
                "TimewebMutationApi",
                return_value=mutation,
            ),
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT",
            ):
                provisioner.provision()
        close.assert_called_once_with(mutation, api, 91)

    def test_tls_enable_failure_rolls_back_public_network(self) -> None:
        initial = {"is_enabled_public_network": False}
        public_ready = {
            "is_enabled_public_network": True,
            "is_enabled_public_ipv6": False,
            "is_secure_connection_enabled": False,
            "status": "started",
        }
        api = mock.Mock()
        mutation = mock.Mock()
        with (
            self._healthy_credential_preflight(),
            mock.patch.object(provisioner, "_verify_allocation_prerequisite"),
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner,
                "_required_verifier_cidr",
                return_value="8.8.8.8/32",
            ),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner,
                "_target_cluster_id",
                return_value=91,
            ),
            mock.patch.object(
                provisioner,
                "_cluster",
                return_value=initial,
            ),
            mock.patch.object(
                provisioner,
                "_converge_firewall",
                return_value="group-1",
            ),
            mock.patch.object(
                provisioner,
                "_resolve_transport_ipv4",
                return_value=("ip-1", "8.8.4.4", False),
            ),
            mock.patch.object(
                provisioner,
                "_network_ready",
                return_value=False,
            ),
            mock.patch.object(
                provisioner,
                "_patch_public_ipv4",
                return_value=public_ready,
            ),
            mock.patch.object(provisioner, "_verify_transport_scope"),
            mock.patch.object(
                provisioner,
                "_enable_secure_connection",
                side_effect=provisioner._provider_base.ProvisioningStopped(
                    "TIMEWEB_DATABASE_TLS_ENABLE_PATCH_REJECTED",
                    status=400,
                ),
            ),
            mock.patch.object(provisioner, "_close_public_network") as close,
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            mock.patch.object(
                provisioner,
                "TimewebMutationApi",
                return_value=mutation,
            ),
        ):
            with self.assertRaises(
                provisioner._provider_base.ProvisioningStopped
            ) as raised:
                provisioner.provision()
        self.assertEqual(
            raised.exception.code,
            "TIMEWEB_DATABASE_TLS_ENABLE_PATCH_REJECTED",
        )
        self.assertEqual(raised.exception.status, 400)
        close.assert_called_once_with(mutation, api, 91)

    def test_preexisting_public_network_without_managed_ipv4_is_closed(self) -> None:
        initial = {
            "is_enabled_public_network": True,
            "is_enabled_public_ipv6": False,
        }
        api = mock.Mock()
        mutation = mock.Mock()
        with (
            self._healthy_credential_preflight(),
            mock.patch.object(provisioner, "_verify_allocation_prerequisite"),
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner,
                "_required_verifier_cidr",
                return_value="8.8.8.8/32",
            ),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            mock.patch.object(
                provisioner,
                "TimewebMutationApi",
                return_value=mutation,
            ),
            mock.patch.object(
                provisioner,
                "_target_cluster_id",
                return_value=91,
            ),
            mock.patch.object(
                provisioner,
                "_cluster",
                return_value=initial,
            ),
            mock.patch.object(
                provisioner,
                "_group_id_by_name",
                return_value="group-1",
            ),
            mock.patch.object(provisioner, "_verify_group"),
            mock.patch.object(provisioner, "_verify_safe_narrow_rule"),
            mock.patch.object(provisioner, "_verify_resource_link"),
            mock.patch.object(provisioner, "_verify_exclusive_firewall"),
            mock.patch.object(
                provisioner,
                "_ensure_group",
                return_value="group-1",
            ),
            mock.patch.object(provisioner, "_ensure_rule"),
            mock.patch.object(provisioner, "_ensure_resource_link"),
            mock.patch.object(
                provisioner,
                "_floating_ips",
                return_value=[],
            ),
            mock.patch.object(provisioner, "_close_public_network") as close,
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_PUBLIC_NETWORK_WITHOUT_MANAGED_IPV4",
            ):
                provisioner.provision()
        close.assert_called_once_with(mutation, api, 91)

    def test_allocation_prerequisite_uses_canonical_transport_snapshot(self) -> None:
        api = mock.Mock()
        journal = mock.Mock()
        adapter = mock.Mock()
        with (
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="1" * 32,
            ),
            mock.patch.object(provisioner, "open_journal", return_value=journal),
            mock.patch.object(
                provisioner.allocation_provider,
                "TimewebAllocationProvider",
                return_value=adapter,
            ),
            mock.patch.object(
                provisioner.allocation,
                "verify_transport_prerequisite",
                return_value=provisioner.allocation.Outcome.RECEIPT_REVERIFIED,
            ) as verify,
        ):
            provisioner._verify_allocation_prerequisite(api)

        verify.assert_called_once_with("1" * 32, adapter.transport_snapshot, journal)

    def test_allocation_prerequisite_failure_is_sanitized(self) -> None:
        api = mock.Mock()
        with (
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="1" * 32,
            ),
            mock.patch.object(
                provisioner,
                "open_journal",
                side_effect=OSError("private-path"),
            ),
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TIMEWEB_ALLOCATION_TRANSPORT_PREREQUISITE_UNAVAILABLE",
            ) as raised:
                provisioner._verify_allocation_prerequisite(api)
        self.assertNotIn("private-path", str(raised.exception))

    def test_prerequisite_failure_prevents_mutation_adapter_construction(self) -> None:
        api = mock.Mock()
        with (
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner,
                "_required_verifier_cidr",
                return_value="8.8.8.8/32",
            ),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            self._healthy_credential_preflight(),
            mock.patch.object(
                provisioner,
                "_verify_allocation_prerequisite",
                side_effect=provisioner._provider_base.ProvisioningStopped(
                    "TIMEWEB_ALLOCATION_TRANSPORT_RECEIPT_REQUIRED"
                ),
            ),
            mock.patch.object(provisioner, "TimewebMutationApi") as mutation,
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "TRANSPORT_RECEIPT_REQUIRED",
            ):
                provisioner._provision_transport()
        mutation.assert_not_called()

    def test_floating_ip_create_shape_has_no_ddos_authority(self) -> None:
        mutation = mock.Mock()
        mutation.mutate_once.return_value = {
            "ip": {
                "id": "abc-123",
                "ip": "8.8.4.4",
                "is_ddos_guard": False,
                "availability_zone": "msk-1",
                "resource_type": None,
                "resource_id": None,
            }
        }
        api = mock.Mock()
        with mock.patch.object(provisioner, "_floating_ips", return_value=[]):
            ip_id, address, created = provisioner._create_floating_ip(
                mutation,
                api,
            )
        self.assertEqual(
            (ip_id, address, created),
            ("abc-123", "8.8.4.4", True),
        )
        mutation.mutate_once.assert_called_once_with(
            "POST",
            "/api/v1/floating-ips",
            operation="FLOATING_IP_CREATE",
            body={"is_ddos_guard": False, "availability_zone": "msk-1"},
            expected_statuses=frozenset({201}),
            reconcile_statuses=provisioner._RECONCILABLE_MUTATION_HTTP_STATUSES,
        )

    def test_bodyless_mutation_uses_json_content_type_like_provider_sdk(self) -> None:
        api = provisioner.TimewebMutationApi("synthetic-token", opener=mock.Mock())
        request = api._request(
            "POST",
            "/api/v1/firewall/groups/group-1/resources/91?resource_type=dbaas",
        )
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers.get("content-type"), "application/json")
        self.assertIsNone(request.data)

    def test_rejection_keeps_operation_and_status_without_response_body(self) -> None:
        opener = mock.Mock()
        opener.open.side_effect = HTTPError(
            "https://api.timeweb.cloud/api/v1/firewall/groups",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"do-not-log-provider-body"}'),
        )
        api = provisioner.TimewebMutationApi("synthetic-token", opener=opener)
        expected_statuses = frozenset({201})
        with self.assertRaises(
            provisioner._provider_base.ProvisioningStopped
        ) as raised:
            api.mutate_once(
                "POST",
                "/api/v1/firewall/groups?policy=DROP",
                operation="FIREWALL_GROUP_CREATE",
                body={"name": "synthetic"},
                expected_statuses=expected_statuses,
            )
        self.assertEqual(
            raised.exception.code,
            "TIMEWEB_FIREWALL_GROUP_CREATE_REJECTED",
        )
        self.assertEqual(raised.exception.status, 400)
        self.assertNotIn("do-not-log-provider-body", str(raised.exception))

    def test_mutation_api_distinguishes_authentication_and_authorization(self) -> None:
        cases = (
            (401, provisioner.read_only.AUTHENTICATION_REJECTED_CODE),
            (403, provisioner.read_only.AUTHORIZATION_REJECTED_CODE),
        )
        for status, expected_code in cases:
            with self.subTest(status=status):
                opener = mock.Mock()
                opener.open.side_effect = HTTPError(
                    "https://api.timeweb.cloud/api/v1/floating-ips",
                    status,
                    "auth rejected",
                    hdrs=None,
                    fp=io.BytesIO(b"provider-private-body"),
                )
                api = provisioner.TimewebMutationApi(
                    "synthetic-token",
                    opener=opener,
                )
                body = {"availability_zone": "msk-1"}
                expected_statuses = frozenset({201})
                with self.assertRaises(
                    provisioner._provider_base.ProvisioningStopped
                ) as raised:
                    api.mutate_once(
                        "POST",
                        "/api/v1/floating-ips",
                        operation="FLOATING_IP_CREATE",
                        body=body,                        expected_statuses=expected_statuses,
                    )
                self.assertEqual(raised.exception.code, expected_code)
                self.assertEqual(raised.exception.status, status)
                self.assertNotIn("provider-private-body", str(raised.exception))
                self.assertEqual(opener.open.call_count, 1)

    def test_read_auth_failure_prevents_transport_writer_construction(self) -> None:
        api = mock.Mock()
        with (
            mock.patch.object(provisioner, "_required_confirmation"),
            mock.patch.object(
                provisioner,
                "_required_verifier_cidr",
                return_value="8.8.8.8/32",
            ),
            mock.patch.object(
                provisioner._provider_base,
                "_required_env",
                return_value="synthetic-token",
            ),
            mock.patch.object(
                provisioner.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            mock.patch.object(
                provisioner.read_only,
                "verify_credential_health",
                side_effect=provisioner._provider_base.ProvisioningStopped(
                    provisioner.read_only.AUTHORIZATION_REJECTED_CODE,
                    status=403,
                ),
            ),
            mock.patch.object(provisioner, "TimewebMutationApi") as writer,
        ):
            with self.assertRaises(
                provisioner._provider_base.ProvisioningStopped
            ) as raised:
                provisioner._provision_transport()
        self.assertEqual(
            raised.exception.code,
            provisioner.read_only.AUTHORIZATION_REJECTED_CODE,
        )
        writer.assert_not_called()

    def test_documented_conflict_enters_get_reconciliation_not_blind_retry(
        self,
    ) -> None:
        opener = mock.Mock()
        opener.open.side_effect = HTTPError(
            "https://api.timeweb.cloud/api/v1/floating-ips",
            409,
            "Conflict",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"conflict"}'),
        )
        api = provisioner.TimewebMutationApi("synthetic-token", opener=opener)
        expected_statuses = frozenset({201})
        with self.assertRaises(provisioner.AmbiguousMutation) as raised:
            api.mutate_once(
                "POST",
                "/api/v1/floating-ips",
                operation="FLOATING_IP_CREATE",
                body={"is_ddos_guard": False, "availability_zone": "msk-1"},
                expected_statuses=expected_statuses,
                reconcile_statuses=provisioner._RECONCILABLE_MUTATION_HTTP_STATUSES,
            )
        self.assertEqual(raised.exception.operation, "FLOATING_IP_CREATE")
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(opener.open.call_count, 1)

    def test_stopped_marker_exposes_only_sanitized_operation_status(self) -> None:
        exc = provisioner._provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_RESOURCE_LINK_REJECTED",
            status=400,
        )
        self.assertEqual(
            provisioner._stopped_marker(exc),
            "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED "
            "code=TIMEWEB_FIREWALL_RESOURCE_LINK_REJECTED http_status=400",
        )

    def test_discoverer_validates_explicit_cidr_and_masks_value(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            env_path = handle.name
        self.addCleanup(lambda: Path(env_path).unlink(missing_ok=True))
        with (
            mock.patch.dict(
                os.environ,
                {
                    "GITHUB_ENV": env_path,
                    discoverer.CIDR_ENV: "8.8.8.8/32",
                },
                clear=True,
            ),
            mock.patch("builtins.print") as output,
        ):
            cidr = discoverer.discover()
        self.assertEqual(cidr, "8.8.8.8/32")
        self.assertEqual(
            Path(env_path).read_text(encoding="utf-8"),
            f"{discoverer.CIDR_ENV}=8.8.8.8/32\n",
        )
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertIn("::add-mask::8.8.8.8", rendered)
        self.assertIn("::add-mask::8.8.8.8/32", rendered)
        self.assertIn(
            "RU_PG_VERIFIER_EGRESS=READY source=/32",
            rendered,
        )

    def test_discoverer_rejects_missing_non_global_or_non_32_input(self) -> None:
        for env, reason in (
            ({}, "RU_PG_VERIFIER_CIDR_REQUIRED"),
            ({discoverer.CIDR_ENV: "203.0.113.7/32"}, "RU_PG_VERIFIER_CIDR_INVALID"),
            ({discoverer.CIDR_ENV: "8.8.8.0/24"}, "RU_PG_VERIFIER_CIDR_INVALID"),
            ({discoverer.CIDR_ENV: "8.8.8.8"}, "RU_PG_VERIFIER_CIDR_INVALID"),
        ):
            with self.subTest(env=env, reason=reason):
                with mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(discoverer.EgressStopped, reason):
                        discoverer.discover()

    def test_discoverer_has_no_retired_provider_network_dependency(self) -> None:
        source = Path(discoverer.__file__).read_text(encoding="utf-8").casefold()
        self.assertNotIn("cloudflare.com", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("http://", source)
        self.assertNotIn("https://", source)

    def test_contract_does_not_record_full_base_sha_literal(self) -> None:
        source = Path(guard.CONTRACT).read_text(encoding="utf-8")
        payload = json.loads(source)
        self.assertNotIn(
            "".join(payload["accepted_base_sha_parts"]),
            source,
        )


if __name__ == "__main__":
    unittest.main()