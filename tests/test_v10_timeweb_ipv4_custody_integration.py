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
        actual = provisioner._resolve_transport_ipv4(
            api,
            91,
            preexisting_public_network=False,
        )
        self.assertEqual(actual, "8.8.8.8")
        self.assertEqual(api.get.call_count, 2)

    def test_resolver_refuses_missing_allocated_ipv4_without_create(self) -> None:
        api = mock.Mock()
        api.get.return_value = {"ips": []}
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_ALLOCATED_IPV4_MISSING",
        ):
            provisioner._resolve_transport_ipv4(
                api,
                91,
                preexisting_public_network=False,
            )
        self.assertEqual(api.get.call_count, 1)

    def test_resolver_refuses_provider_drift_between_reads(self) -> None:
        first = ip_row()
        first["comment"] = custody.marker(91, custody.inventory([first])[0])
        second = ip_row(id="fixture-ip-3", ip="8.8.4.4")
        second["comment"] = custody.marker(91, custody.inventory([second])[0])
        api = mock.Mock()
        api.get.side_effect = [{"ips": [first]}, {"ips": [second]}]
        with self.assertRaisesRegex(
            provisioner._provider_base.ProvisioningStopped,
            "TIMEWEB_ALLOCATED_IPV4_DRIFT",
        ):
            provisioner._resolve_transport_ipv4(
                api,
                91,
                preexisting_public_network=False,
            )
        self.assertEqual(api.get.call_count, 2)

    def test_rollback_without_public_exposure_is_noop(self) -> None:
        mutation = mock.Mock()
        api = mock.Mock()
        provisioner._rollback_failed_transport(
            mutation,
            api,
            91,
            public_exposure_possible=False,
        )
        mutation.mutate_once.assert_not_called()

    def test_resolver_rejects_missing_binding_state(self) -> None:
        row = ip_row()
        del row["resource_id"]
        api = mock.Mock()
        api.get.return_value = {"ips": [row]}
        with self.assertRaisesRegex(custody.CustodyStopped, "BINDING_STATE_UNKNOWN"):
            provisioner._resolve_transport_ipv4(
                api,
                91,
                preexisting_public_network=False,
            )

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

    def test_observer_target_absent_is_nonfatal_but_custody_stays_blocked(
        self,
    ) -> None:
        api = mock.Mock()
        api.get.side_effect = [{}, {}, {"ips": [ip_row()]}]
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
                return_value=None,
            ),
            mock.patch.object(observer.provider_base, "_emit") as emit,
        ):
            result = observer.main()

        self.assertEqual(result, 0)
        self.assertEqual(
            [call.args[0] for call in api.get.call_args_list],
            [
                "/api/v1/projects",
                "/api/v1/projects/5/resources/databases",
                "/api/v1/floating-ips",
            ],
        )
        output = " ".join(call.args[0] for call in emit.call_args_list)
        self.assertIn("INVENTORY=OBSERVED total=1 unbound=1", output)
        self.assertIn("target=absent", output)
        self.assertIn(
            "RECOVERY=BLOCKED code=TIMEWEB_IPV4_TARGET_ABSENT",
            output,
        )
        for forbidden in (
            "8.8.8.8",
            "fixture-ip-2",
            "fixture-token",
            "=READY",
            "=PASS",
            "managed_unbound=",
            "target_bound=",
        ):
            self.assertNotIn(forbidden, output)

    def test_observer_target_absent_rejects_truncated_account_inventory(self) -> None:
        api = mock.Mock()
        api.get.side_effect = [{}, {}, {"ips": [], "meta": {"total": 1}}]
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
                return_value=None,
            ),
            mock.patch.object(observer.provider_base, "_emit") as emit,
        ):
            result = observer.main()

        self.assertEqual(result, 1)
        emit.assert_called_once_with(
            "TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED "
            "code=TIMEWEB_IPV4_INVENTORY_INCOMPLETE"
        )

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

    def test_guard_enforces_existing_only_transport_and_order(self) -> None:
        source = Path(provisioner.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        guard._validate_custody_order(tree)
        guard._validate_existing_only_transport(tree)
        guard._validate_provider_transition_order(tree)
        guard._validate_custody_probe(
            Path(observer.__file__).read_text(
                encoding="utf-8",
            ),
        )
        changed = source.replace(
            "    return selected.ip_address\n",
            "    _create_floating_ip(mutation, api)\n    return selected.ip_address\n",
            1,
        )
        changed_tree = ast.parse(changed)
        with self.assertRaisesRegex(RuntimeError, "EXISTING_ONLY_RESOLVER_INVALID"):
            guard._validate_existing_only_transport(changed_tree)
        changed = source.replace(
            "        _preflight_ipv4_custody(api, cluster_id, initial)\n",
            "",
            1,
        )
        changed_tree = ast.parse(changed)
        with self.assertRaisesRegex(RuntimeError, "ORDER_INVALID"):
            guard._validate_custody_order(changed_tree)

        changed = source.replace(
            "        try:\n            _verify_transport_scope(\n",
            "        try:\n"
            "            _ensure_rule(mutation, api, group_id, cidr)\n"
            "            _verify_transport_scope(\n",
            1,
        )
        changed_tree = ast.parse(changed)
        with self.assertRaisesRegex(
            RuntimeError,
            "POST_EXPOSURE_FIREWALL_MUTATION_FORBIDDEN",
        ):
            guard._validate_provider_transition_order(changed_tree)

    def test_guard_rejects_diagnostic_write_or_false_ready(self) -> None:
        source = Path(observer.__file__).read_text(encoding="utf-8")
        for changed in (
            source.replace(
                'api.get("/api/v1/floating-ips")',
                'api.post("/api/v1/floating-ips")',
            ),
            source + "\n# TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY\n",
            source.replace(
                "TIMEWEB_IPV4_TARGET_ABSENT",
                "TIMEWEB_IPV4_TARGET_NOT_FOUND",
            ),
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
            "target_absent_grants_custody",
            "target_absent_grants_mutation_authority",
        ):
            changed = copy.deepcopy(original)
            changed["ipv4_custody"][field] = True
            with self.subTest(field=field):
                with self.assertRaises(RuntimeError):
                    guard._validate_ipv4_custody_contract(changed)


if __name__ == "__main__":
    unittest.main()
