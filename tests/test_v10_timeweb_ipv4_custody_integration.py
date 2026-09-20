from __future__ import annotations

import ast
import copy
from pathlib import Path
import unittest
from unittest import mock

from scripts import check_v10_timeweb_postgres_public_ipv4_tls as guard
from scripts import probe_v10_timeweb_ipv4_custody as observer
from scripts import provision_v10_timeweb_postgres_public_ipv4_tls as provisioner
from scripts import timeweb_ipv4_custody as custody


def ip_row(**changes: object) -> dict[str, object]:
    row = dict(
        id="fixture-ip-2",
        ip="8.8.8.8",
        availability_zone="msk-1",
        is_ddos_guard=False,
        resource_type=None,
        resource_id=None,
        comment="",
    )
    row.update(changes)
    return row


class Ipv4CustodyIntegrationTests(unittest.TestCase):
    def test_unproven_orphan_stops_before_firewall_or_purchase(self) -> None:
        api = mock.Mock()
        api.get.return_value = {"ips": [ip_row()]}
        mutation = mock.Mock()
        initial = {"is_enabled_public_network": False}
        with mock.patch.object(provisioner, "_converge_firewall") as firewall:
            with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
                provisioner._configure_transport(
                    mutation,
                    api,
                    91,
                    initial,
                    "1.1.1.1/32",
                    preexisting_public_network=False,
                )
        firewall.assert_not_called()
        mutation.mutate_once.assert_not_called()

    def test_preflight_unknown_public_state_fails_closed(self) -> None:
        api = mock.Mock()
        api.get.return_value = {"ips": []}
        initial = {}
        with self.assertRaisesRegex(custody.CustodyStopped, "PUBLIC_STATE_UNKNOWN"):
            provisioner._preflight_ipv4_custody(api, 91, initial)

    def test_resolver_recovers_only_exact_managed_row_without_writes(self) -> None:
        row = ip_row()
        row["comment"] = custody.marker(91, custody.inventory([row])[0])
        api = mock.Mock()
        api.get.return_value = {"ips": [row]}
        mutation = mock.Mock()
        actual = provisioner._resolve_transport_ipv4(
            mutation,
            api,
            91,
            preexisting_public_network=False,
        )
        self.assertEqual(actual, ("fixture-ip-2", "8.8.8.8", False))
        self.assertEqual(api.get.call_count, 2)
        mutation.mutate_once.assert_not_called()

    def test_stamp_changes_comment_only_once_and_accepts_exact_status(self) -> None:
        mutation = mock.Mock()
        provisioner._stamp_created_ipv4(mutation, "fixture-ip-2", "association")
        mutation.mutate_once.assert_called_once_with(
            "PATCH",
            "/api/v1/floating-ips/fixture-ip-2",
            operation="FLOATING_IP_CUSTODY_STAMP",
            body={"comment": "association"},
            expected_statuses=frozenset({200}),
            reconcile_statuses=provisioner._RECONCILABLE_MUTATION_HTTP_STATUSES,
        )

    def test_ambiguous_create_delta_is_not_stampable_receipt(self) -> None:
        api = mock.Mock()
        api.get.side_effect = [{"ips": []}, {"ips": [ip_row()]}]
        mutation = mock.Mock()
        mutation.mutate_once.side_effect = provisioner.AmbiguousMutation(
            "TIMEWEB_MUTATION_AMBIGUOUS",
            operation="FLOATING_IP_CREATE",
        )
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "CREATE_RECEIPT_UNPROVEN",
        ):
            provisioner._create_floating_ip(mutation, api)
        mutation.mutate_once.assert_called_once()
        self.assertEqual(api.get.call_count, 2)

    def test_ambiguous_stamp_has_no_blind_patch_retry(self) -> None:
        mutation = mock.Mock()
        mutation.mutate_once.side_effect = provisioner.AmbiguousMutation("ambiguous")
        provisioner._stamp_created_ipv4(mutation, "fixture-ip-2", "association")
        mutation.mutate_once.assert_called_once()

    def test_cleanup_waits_for_absence_without_second_delete(self) -> None:
        api = mock.Mock()
        api.get.side_effect = [
            {"ips": [ip_row()]},
            {"ips": [ip_row()]},
            {"ips": []},
        ]
        mutation = mock.Mock()
        mutation.mutate_once.side_effect = provisioner.AmbiguousMutation("ambiguous")
        with mock.patch.object(provisioner.time, "sleep"):
            provisioner._delete_created_ipv4_if_unbound(mutation, api, "fixture-ip-2")
        mutation.mutate_once.assert_called_once()
        self.assertEqual(api.get.call_count, 3)

    def test_cleanup_never_deletes_resource_bound_elsewhere(self) -> None:
        api = mock.Mock()
        api.get.return_value = {"ips": [ip_row(resource_type="server", resource_id=7)]}
        mutation = mock.Mock()
        provisioner._delete_created_ipv4_if_unbound(mutation, api, "fixture-ip-2")
        mutation.mutate_once.assert_not_called()

    def test_cleanup_without_absence_proof_stays_stopped(self) -> None:
        api = mock.Mock()
        api.get.return_value = {"ips": [ip_row()]}
        mutation = mock.Mock()
        with mock.patch.object(provisioner.time, "sleep"):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "ABSENCE_UNPROVEN",
            ):
                provisioner._delete_created_ipv4_if_unbound(
                    mutation,
                    api,
                    "fixture-ip-2",
                )
        mutation.mutate_once.assert_called_once()

    def test_recovered_resource_is_not_owned_by_cleanup(self) -> None:
        mutation = mock.Mock()
        api = mock.Mock()
        with mock.patch.object(
            provisioner,
            "_delete_created_ipv4_if_unbound",
        ) as delete:
            provisioner._rollback_failed_transport(
                mutation,
                api,
                91,
                public_exposure_possible=False,
                created_this_run=False,
                floating_id="fixture-ip-2",
            )
        delete.assert_not_called()
        mutation.mutate_once.assert_not_called()

    def test_new_custody_stop_preserves_adapter_exception_contract(self) -> None:
        failure = custody.CustodyStopped("TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED")
        with mock.patch.object(
            provisioner,
            "_provision_transport",
            side_effect=failure,
        ):
            with self.assertRaisesRegex(
                provisioner._provider_base.ProvisioningStopped,
                "PROVENANCE_REQUIRED",
            ):
                provisioner.provision()

    def test_bound_database_alias_and_numeric_id_are_normalized(self) -> None:
        for kind in ("database", "dbaas"):
            for identifier in (91, "91"):
                row = ip_row(resource_type=kind, resource_id=identifier)
                with self.subTest(kind=kind, identifier=identifier):
                    self.assertEqual(provisioner._bound_ip_for_cluster([row], 91), row)

    def test_missing_binding_never_reaches_delete(self) -> None:
        row = ip_row()
        del row["resource_id"]
        api = mock.Mock()
        api.get.return_value = {"ips": [row]}
        mutation = mock.Mock()
        with self.assertRaisesRegex(custody.CustodyStopped, "BINDING_STATE_UNKNOWN"):
            provisioner._delete_created_ipv4_if_unbound(mutation, api, "fixture-ip-2")
        mutation.mutate_once.assert_not_called()

    def test_truncated_inventory_never_becomes_empty_create_opportunity(self) -> None:
        api = mock.Mock()
        api.get.return_value = {"ips": [], "meta": {"total": 2}}
        with self.assertRaisesRegex(custody.CustodyStopped, "INVENTORY_INCOMPLETE"):
            provisioner._floating_ips(api)

    def test_numeric_target_coercion_rejects_bool_float_and_padding(self) -> None:
        for value in (True, 1.5, 91.0, "091", " 91", "0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(provisioner._provider_base.ProvisioningStopped):
                    provisioner._numeric_id(value, "TARGET_INVALID")

    def test_observer_reports_blocked_without_mutation_or_ready_claim(self) -> None:
        api = mock.Mock()
        target = {
            "db": {
                "name": observer.read_only.TARGET_CLUSTER_NAME,
                "is_enabled_public_network": False,
            },
        }
        api.get.side_effect = [{}, {}, target, {"ips": [ip_row()]}]
        with (
            mock.patch.object(
                observer.provider_base,
                "_required_env",
                return_value="fixture-token",
            ),
            mock.patch.object(
                observer.read_only,
                "TimewebReadOnlyApi",
                return_value=api,
            ),
            mock.patch.object(observer.read_only, "_select_project", return_value=5),
            mock.patch.object(
                observer.read_only,
                "_target_cluster_id",
                return_value="91",
            ),
            mock.patch.object(observer.provider_base, "_emit") as emit,
        ):
            result = observer.main()
        self.assertEqual(result, 0)
        self.assertEqual(
            [c.args[0] for c in api.get.call_args_list],
            [
                "/api/v1/projects",
                "/api/v1/projects/5/resources/databases",
                "/api/v1/databases/91",
                "/api/v1/floating-ips",
            ],
        )
        output = " ".join(c.args[0] for c in emit.call_args_list)
        self.assertIn(
            "RECOVERY=BLOCKED code=TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED",
            output,
        )
        for forbidden in (
            "8.8.8.8",
            "fixture-ip-2",
            "fixture-token",
            "=READY",
            "=PASS",
        ):
            self.assertNotIn(forbidden, output)
        self.assertEqual(len(api.mock_calls), 4)

    def test_observer_failure_does_not_disclose_exception_payload(self) -> None:
        error = OSError("do-not-log-private-provider-response")
        with (
            mock.patch.object(observer, "observe", side_effect=error),
            mock.patch.object(observer.provider_base, "_emit") as emit,
        ):
            self.assertEqual(observer.main(), 1)
        emit.assert_called_once_with(
            "TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED "
            "code=TIMEWEB_IPV4_OBSERVATION_UNAVAILABLE",
        )

    def test_guard_enforces_comment_only_patch_and_order(self) -> None:
        source = Path(provisioner.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        guard._validate_custody_stamp(tree)
        guard._validate_custody_order(tree)
        guard._validate_custody_probe(
            Path(observer.__file__).read_text(
                encoding="utf-8",
            ),
        )
        changed = source.replace(
            '{"comment": management_marker}',
            '{"ptr": management_marker}',
        )
        changed_tree = ast.parse(changed)
        with self.assertRaisesRegex(RuntimeError, "STAMP_INVALID"):
            guard._validate_custody_stamp(changed_tree)
        changed = source.replace(
            "        _preflight_ipv4_custody(api, cluster_id, initial)\n",
            "",
        )
        changed_tree = ast.parse(changed)
        with self.assertRaisesRegex(RuntimeError, "ORDER_INVALID"):
            guard._validate_custody_order(changed_tree)

    def test_guard_rejects_diagnostic_write_or_false_ready(self) -> None:
        source = Path(observer.__file__).read_text(encoding="utf-8")
        for changed in (
            source.replace(
                'api.get("/api/v1/floating-ips")',
                'api.post("/api/v1/floating-ips")',
            ),
            source + "\n# TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY\n",
        ):
            with self.subTest(kind="diagnostic-boundary"):
                with self.assertRaises(RuntimeError):
                    guard._validate_custody_probe(changed)

    def test_contract_rejects_unmarked_adoption_and_false_atomicity(self) -> None:
        original = guard._load(guard.CONTRACT)
        guard._validate_ipv4_custody_contract(original)
        for field in (
            "unmarked_existing_adoption_allowed",
            "create_and_stamp_are_atomic",
            "marker_is_cryptographic_authentication",
            "ambiguous_create_delta_is_ownership_proof",
        ):
            changed = copy.deepcopy(original)
            changed["ipv4_custody"][field] = True
            with self.subTest(field=field):
                with self.assertRaises(RuntimeError):
                    guard._validate_ipv4_custody_contract(changed)


if __name__ == "__main__":
    unittest.main()
