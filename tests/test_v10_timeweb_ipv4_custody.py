from __future__ import annotations

import copy
import unittest
from unittest import mock

from scripts import timeweb_ipv4_custody as custody


def address(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "synthetic-ip-1",
        "ip": "8.8.4.4",
        "availability_zone": "msk-1",
        "is_ddos_guard": False,
        "resource_type": None,
        "resource_id": None,
        "comment": "",
    }
    row.update(changes)
    return row


def managed(**changes: object) -> dict[str, object]:
    row = address(**changes)
    parsed = custody.inventory([row])[0]
    row["comment"] = custody.marker(91, parsed)
    return row


class ProviderDouble:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = copy.deepcopy(rows)
        self.creates = 0
        self.stamps = 0
        self.deletes = 0
        self.reads = 0
        self.output: list[str] = []

    def read(self) -> object:
        self.reads += 1
        return copy.deepcopy(self.rows)

    def create(self) -> tuple[str, str, bool]:
        self.creates += 1
        row = address()
        self.rows.append(row)
        return "synthetic-ip-1", "8.8.4.4", True

    def stamp(self, identifier: str, marker: str) -> None:
        self.stamps += 1
        for row in self.rows:
            if row["id"] == identifier:
                row["comment"] = marker

    def delete(self, identifier: str) -> None:
        self.deletes += 1
        self.rows = [row for row in self.rows if row["id"] != identifier]

    def resolve(self, *, public_enabled: bool = False) -> tuple[str, str, bool]:
        return custody.resolve(
            self.read,
            self.create,
            self.stamp,
            self.delete,
            91,
            public_enabled=public_enabled,
            emit=self.output.append,
            sleeper=lambda _delay: None,
        )


class TimewebIpv4CustodyTests(unittest.TestCase):
    def test_empty_inventory_creates_and_stamps_exactly_once(self) -> None:
        provider = ProviderDouble([])
        self.assertEqual(provider.resolve(), ("synthetic-ip-1", "8.8.4.4", True))
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                1,
                1,
                0,
            ),
        )
        actual = custody.inventory(provider.rows)[0]
        self.assertEqual(actual.comment, custody.marker(91, actual))

    def test_managed_orphan_recovers_without_purchase_stamp_or_delete(self) -> None:
        provider = ProviderDouble([managed()])
        self.assertEqual(provider.resolve(), ("synthetic-ip-1", "8.8.4.4", False))
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                0,
                0,
                0,
            ),
        )
        self.assertEqual(provider.reads, 2)

    def test_cross_run_recovery_uses_durable_association(self) -> None:
        first = ProviderDouble([])
        first.resolve()
        restarted = ProviderDouble(first.rows)
        self.assertEqual(restarted.resolve(), ("synthetic-ip-1", "8.8.4.4", False))
        self.assertEqual(restarted.creates, 0)
        self.assertEqual(restarted.stamps, 0)
        self.assertEqual(restarted.deletes, 0)

    def test_exact_bound_target_reuse_preserves_old_unstamped_binding(self) -> None:
        for kind in ("database", "dbaas"):
            with self.subTest(kind=kind):
                provider = ProviderDouble([address(resource_type=kind, resource_id=91)])
                self.assertEqual(
                    provider.resolve(public_enabled=True),
                    ("synthetic-ip-1", "8.8.4.4", False),
                )
                self.assertEqual(
                    (provider.creates, provider.stamps, provider.deletes),
                    (
                        0,
                        0,
                        0,
                    ),
                )

    def test_unmarked_current_orphan_remains_blocked_without_mutation(self) -> None:
        provider = ProviderDouble([address()])
        with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
            provider.resolve()
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                0,
                0,
                0,
            ),
        )
        self.assertIn("unproven_unbound=1", provider.output[0])

    def test_arbitrary_matching_shape_or_lookalike_comment_is_not_provenance(
        self,
    ) -> None:
        comments = (None, "", "omni-cio", custody.MARKER_PREFIX, "unrelated project")
        for comment in comments:
            with self.subTest(comment=comment):
                provider = ProviderDouble([address(comment=comment)])
                with self.assertRaisesRegex(
                    custody.CustodyStopped,
                    "PROVENANCE_REQUIRED",
                ):
                    provider.resolve()
                self.assertEqual(
                    (provider.creates, provider.stamps, provider.deletes),
                    (
                        0,
                        0,
                        0,
                    ),
                )

    def test_marker_is_target_and_resource_specific(self) -> None:
        row = custody.inventory([address()])[0]
        other_ip = custody.inventory([address(id="synthetic-ip-2")])[0]
        other_address = custody.inventory([address(ip="1.1.1.1")])[0]
        self.assertNotEqual(custody.marker(91, row), custody.marker(92, row))
        self.assertNotEqual(custody.marker(91, row), custody.marker(91, other_ip))
        self.assertNotEqual(custody.marker(91, row), custody.marker(91, other_address))
        transplanted = address(comment=custody.marker(92, row))
        provider = ProviderDouble([transplanted])
        with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
            provider.resolve()

    def test_multiple_free_rows_do_not_pick_first_managed_orphan(self) -> None:
        provider = ProviderDouble(
            [
                managed(),
                address(id="synthetic-ip-2", ip="1.1.1.1"),
            ],
        )
        with self.assertRaisesRegex(custody.CustodyStopped, "NOT_UNIQUE"):
            provider.resolve()
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                0,
                0,
                0,
            ),
        )

    def test_two_managed_resources_are_not_one_authority(self) -> None:
        first = managed(resource_type="database", resource_id=91)
        second = managed(id="synthetic-ip-2", ip="1.1.1.1")
        provider = ProviderDouble([first, second])
        with self.assertRaisesRegex(custody.CustodyStopped, "NOT_UNIQUE"):
            provider.resolve(public_enabled=True)

    def test_target_binding_and_different_managed_orphan_are_rejected(self) -> None:
        first = address(resource_type="database", resource_id=91)
        second = managed(id="synthetic-ip-2", ip="1.1.1.1")
        provider = ProviderDouble([first, second])
        with self.assertRaisesRegex(custody.CustodyStopped, "NOT_UNIQUE"):
            provider.resolve()

    def test_two_target_bindings_are_rejected(self) -> None:
        first = address(resource_type="database", resource_id=91)
        second = address(
            id="synthetic-ip-2",
            ip="1.1.1.1",
            resource_type="database",
            resource_id="91",
        )
        provider = ProviderDouble([first, second])
        with self.assertRaisesRegex(custody.CustodyStopped, "NOT_UNIQUE"):
            provider.resolve()

    def test_wrong_zone_and_ddos_are_not_recovery_candidates(self) -> None:
        for changes in ({"availability_zone": "spb-3"}, {"is_ddos_guard": True}):
            with self.subTest(changes=changes):
                provider = ProviderDouble([managed(**changes)])
                with self.assertRaisesRegex(custody.CustodyStopped, "SHAPE_DRIFT"):
                    provider.resolve()
                self.assertEqual(
                    (provider.creates, provider.stamps, provider.deletes),
                    (
                        0,
                        0,
                        0,
                    ),
                )

    def test_managed_resource_moved_to_another_service_is_not_stolen(self) -> None:
        row = managed()
        row.update(resource_type="server", resource_id=91)
        provider = ProviderDouble([row])
        with self.assertRaisesRegex(custody.CustodyStopped, "BOUND_ELSEWHERE"):
            provider.resolve()
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                0,
                0,
                0,
            ),
        )

    def test_unrelated_bound_service_does_not_become_target(self) -> None:
        provider = ProviderDouble(
            [
                address(
                    id="other-ip",
                    ip="1.1.1.1",
                    resource_type="server",
                    resource_id=91,
                ),
            ],
        )
        self.assertEqual(provider.resolve(), ("synthetic-ip-1", "8.8.4.4", True))
        self.assertEqual(provider.rows[0]["comment"], "")
        self.assertEqual(provider.rows[0]["resource_type"], "server")

    def test_public_network_without_exact_target_binding_stops_before_create(
        self,
    ) -> None:
        provider = ProviderDouble([])
        with self.assertRaisesRegex(custody.CustodyStopped, "WITHOUT_MANAGED_IPV4"):
            provider.resolve(public_enabled=True)
        self.assertEqual(provider.creates, 0)

    def test_disagreement_between_recovery_reads_never_mutates(self) -> None:
        provider = ProviderDouble([managed()])
        changed = managed()
        changed.update(resource_type="database", resource_id=91)
        with mock.patch.object(provider, "read", side_effect=[[managed()], [changed]]):
            with self.assertRaisesRegex(custody.CustodyStopped, "RECOVERY_DRIFT"):
                provider.resolve()
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                0,
                0,
                0,
            ),
        )

    def test_disappearing_recovery_row_does_not_fall_back_to_purchase(self) -> None:
        provider = ProviderDouble([managed()])
        with mock.patch.object(provider, "read", side_effect=[[managed()], []]):
            with self.assertRaisesRegex(custody.CustodyStopped, "RECOVERY_DRIFT"):
                provider.resolve()
        self.assertEqual(provider.creates, 0)

    def test_delayed_comment_visibility_uses_get_only(self) -> None:
        provider = ProviderDouble([])
        reads = [[], [address()], [address()], [managed()]]
        with mock.patch.object(provider, "read", side_effect=reads):
            self.assertEqual(provider.resolve(), ("synthetic-ip-1", "8.8.4.4", True))
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                1,
                1,
                0,
            ),
        )

    def test_unconfirmed_stamp_cleans_only_current_created_ip(self) -> None:
        provider = ProviderDouble([])
        with mock.patch.object(provider, "stamp") as stamp:
            with self.assertRaisesRegex(custody.CustodyStopped, "STAMP_UNPROVEN"):
                provider.resolve()
        stamp.assert_called_once()
        self.assertEqual(provider.creates, 1)
        self.assertEqual(provider.deletes, 1)
        self.assertEqual(provider.rows, [])

    def test_stamp_rejection_preserved_after_verified_cleanup(self) -> None:
        provider = ProviderDouble([])
        rejection = custody.CustodyStopped("TIMEWEB_FLOATING_IP_CUSTODY_STAMP_REJECTED")
        with mock.patch.object(provider, "stamp", side_effect=rejection):
            with self.assertRaisesRegex(custody.CustodyStopped, "STAMP_REJECTED"):
                provider.resolve()
        self.assertEqual(provider.deletes, 1)

    def test_ambiguous_cleanup_is_not_claimed_success_or_retried(self) -> None:
        provider = ProviderDouble([])
        with (
            mock.patch.object(provider, "stamp"),
            mock.patch.object(provider, "delete") as delete,
        ):
            with self.assertRaisesRegex(custody.CustodyStopped, "CLEANUP_UNPROVEN"):
                provider.resolve()
        delete.assert_called_once()
        self.assertEqual(provider.creates, 1)

    def test_resource_bound_during_stamp_is_never_deleted(self) -> None:
        provider = ProviderDouble([])

        def moved(_identifier: str, _marker: str) -> None:
            provider.rows[0].update(resource_type="server", resource_id=7)

        with mock.patch.object(provider, "stamp", side_effect=moved):
            with self.assertRaisesRegex(custody.CustodyStopped, "CLEANUP_UNPROVEN"):
                provider.resolve()
        self.assertEqual(provider.deletes, 0)

    def test_foreign_comment_during_stamp_is_never_overwritten_or_deleted(self) -> None:
        provider = ProviderDouble([])

        def moved(_identifier: str, _marker: str) -> None:
            provider.rows[0]["comment"] = "belongs to another operation"

        with mock.patch.object(provider, "stamp", side_effect=moved):
            with self.assertRaisesRegex(custody.CustodyStopped, "CLEANUP_UNPROVEN"):
                provider.resolve()
        self.assertEqual(provider.deletes, 0)

    def test_read_failure_does_not_authorize_creation(self) -> None:
        provider = ProviderDouble([])
        with mock.patch.object(provider, "read", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                provider.resolve()
        self.assertEqual(
            (provider.creates, provider.stamps, provider.deletes),
            (
                0,
                0,
                0,
            ),
        )

    def test_ambiguous_create_is_not_retried_or_stamped(self) -> None:
        provider = ProviderDouble([])
        with mock.patch.object(
            provider,
            "create",
            side_effect=OSError("unavailable"),
        ) as create:
            with self.assertRaises(OSError):
                provider.resolve()
        create.assert_called_once()
        self.assertEqual((provider.stamps, provider.deletes), (0, 0))

    def test_receipt_mismatch_does_not_stamp_arbitrary_resource(self) -> None:
        cases = (
            ("other", "8.8.4.4", True),
            ("synthetic-ip-1", "1.1.1.1", True),
            (
                "synthetic-ip-1",
                "8.8.4.4",
                False,
            ),
        )
        for receipt in cases:
            with self.subTest(receipt=receipt):
                provider = ProviderDouble([])

                def create() -> tuple[str, str, bool]:
                    provider.rows.append(address())
                    return receipt

                with mock.patch.object(provider, "create", side_effect=create):
                    with self.assertRaises(custody.CustodyStopped):
                        provider.resolve()
                self.assertEqual((provider.stamps, provider.deletes), (0, 0))

    def test_concurrent_creates_require_reconciliation_not_first_match(self) -> None:
        provider = ProviderDouble([])

        def create() -> tuple[str, str, bool]:
            provider.rows.extend([address(), address(id="other", ip="1.1.1.1")])
            return "synthetic-ip-1", "8.8.4.4", True

        with mock.patch.object(provider, "create", side_effect=create):
            with self.assertRaisesRegex(custody.CustodyStopped, "RECEIPT_NOT_UNIQUE"):
                provider.resolve()
        self.assertEqual((provider.stamps, provider.deletes), (0, 0))

    def test_existing_nonempty_comment_on_create_receipt_is_not_overwritten(
        self,
    ) -> None:
        provider = ProviderDouble([])

        def create() -> tuple[str, str, bool]:
            provider.rows.append(address(comment="foreign"))
            return "synthetic-ip-1", "8.8.4.4", True

        with mock.patch.object(provider, "create", side_effect=create):
            with self.assertRaisesRegex(custody.CustodyStopped, "COMMENT_NOT_EMPTY"):
                provider.resolve()
        self.assertEqual((provider.stamps, provider.deletes), (0, 0))

    def test_missing_fields_and_malformed_binding_fail_closed(self) -> None:
        rows = []
        for key in (
            "id",
            "ip",
            "availability_zone",
            "is_ddos_guard",
            "resource_type",
            "resource_id",
        ):
            row = address()
            del row[key]
            rows.append(row)
        for changes in (
            {"id": None},
            {"id": "../escape"},
            {"id": 1},
            {"ip": "127.0.0.1"},
            {"ip": "::1"},
            {"ip": "bad"},
            {"ip": 1},
            {"availability_zone": None},
            {"is_ddos_guard": 0},
            {"comment": []},
            {"comment": "x" * 4097},
            {"resource_id": False},
            {"resource_id": 0.0},
            {"resource_id": 91},
            {"resource_type": "server"},
            {"resource_type": "server", "resource_id": -1},
            {"resource_type": [], "resource_id": 91},
            {"resource_type": "server", "resource_id": 1.5},
            {"resource_type": "server", "resource_id": "../escape"},
        ):
            rows.append(address(**changes))
        for row in rows:
            payload = [row]
            with self.subTest(row=row):
                with self.assertRaises(custody.CustodyStopped):
                    custody.inventory(payload)

    def test_known_empty_binding_sentinels_only(self) -> None:
        for kind in (None, ""):
            for identifier in (None, "", 0):
                parsed = custody.inventory(
                    [
                        address(
                            resource_type=kind,
                            resource_id=identifier,
                        ),
                    ],
                )[0]
                self.assertTrue(parsed.unbound)

    def test_duplicate_and_non_list_inventory_rejected(self) -> None:
        payloads = (
            None,
            {},
            [None],
            [address(), address()],
            [
                address(),
                address(
                    id="other",
                ),
            ],
            [
                address(),
            ] * 1001,
        )
        for payload in payloads:
            with self.subTest(payload_type=type(payload)):
                with self.assertRaises(custody.CustodyStopped):
                    custody.inventory(payload)

    def test_invalid_target_and_unknown_public_state_are_rejected(self) -> None:
        for target in (True, 0, -1, "91"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(custody.CustodyStopped, "TARGET_INVALID"):
                    custody.select((), target, public_enabled=False)
        with self.assertRaisesRegex(custody.CustodyStopped, "PUBLIC_STATE_UNKNOWN"):
            custody.select((), 91, public_enabled=None)

    def test_evidence_never_contains_address_id_comment_or_hash(self) -> None:
        row = address(comment="do-not-log-private-text")
        parsed = custody.inventory([row])
        evidence = custody.observation(parsed, 91)
        for value in (
            row["id"],
            row["ip"],
            row["comment"],
            custody.marker(
                91,
                parsed[0],
            ),
        ):
            self.assertNotIn(value, evidence)
            self.assertNotIn(value, repr(parsed[0]))
        self.assertIn("unproven_unbound=1", evidence)
        self.assertNotIn("READY", evidence)

    def test_raw_inventory_checks_wrapper_and_complete_total(self) -> None:
        row = address()
        for payload in ({"ips": [row]}, {"ips": [row], "meta": {"total": 1}}):
            with self.subTest(with_meta="meta" in payload):
                self.assertEqual(custody.raw_inventory(payload), [row])
        malformed = (
            None,
            [],
            {},
            {"ips": [], "meta": {"total": 1}},
            {"ips": [], "meta": {"total": False}},
            {"ips": [], "meta": {}},
            {"ips": [], "meta": None},
        )
        for payload in malformed:
            with self.subTest(kind=type(payload)):
                with self.assertRaises(custody.CustodyStopped):
                    custody.raw_inventory(payload)

    def test_disposition_separates_observation_from_readiness(self) -> None:
        rows = custody.inventory([address()])
        self.assertEqual(
            custody.disposition(rows, 91, public_enabled=False),
            "TIMEWEB_RU_PG_IPV4_RECOVERY=BLOCKED "
            "code=TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED",
        )
        cases = (
            ([], "CREATE_ONCE"),
            ([managed()], "RECOVER_MANAGED"),
            ([address(resource_type="database", resource_id=91)], "REUSE_BOUND"),
        )
        for raw, action in cases:
            rows = custody.inventory(raw)
            with self.subTest(action=action):
                result = custody.disposition(rows, 91, public_enabled=False)
                self.assertEqual(
                    result, f"TIMEWEB_RU_PG_IPV4_RECOVERY=ELIGIBLE action={action}"
                )
                self.assertNotIn("=READY", result)
                self.assertNotIn("=PASS", result)

    def test_null_comment_does_not_prove_ownership(self) -> None:
        rows = custody.inventory([address(comment=None)])
        self.assertEqual(rows[0].comment, "")
        with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
            custody.select(rows, 91, public_enabled=False)

    def test_copied_comment_does_not_prove_another_address_identity(self) -> None:
        original = managed()
        modified = dict(original)
        modified["id"] = "copied-ip"
        modified["ip"] = "1.1.1.1"
        rows = custody.inventory([modified])
        with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
            custody.select(rows, 91, public_enabled=False)

    def test_strict_binding_helper_rejects_non_objects(self) -> None:
        with self.assertRaisesRegex(custody.CustodyStopped, "BINDING_STATE_UNKNOWN"):
            custody.is_unbound(None)

    def test_managed_row_alongside_target_binding_cannot_be_ignored(self) -> None:
        rows = custody.inventory(
            [
                address(resource_type="database", resource_id=91),
                managed(id="another-managed-ip", ip="1.1.1.1"),
            ]
        )
        with self.assertRaisesRegex(custody.CustodyStopped, "CUSTODY_NOT_UNIQUE"):
            custody.select(rows, 91, public_enabled=False)

    def test_success_receipt_waits_for_visibility_with_get_only(self) -> None:
        provider = ProviderDouble([])
        reads = [[], [], [address()], [managed()]]
        with mock.patch.object(provider, "read", side_effect=reads):
            actual = provider.resolve()
        self.assertEqual(actual, ("synthetic-ip-1", "8.8.4.4", True))
        self.assertEqual(provider.creates, 1)
        self.assertEqual(provider.stamps, 1)

    def test_invisible_receipt_cannot_stamp_or_delete_an_unknown_address(self) -> None:
        provider = ProviderDouble([])
        with mock.patch.object(provider, "read", return_value=[]):
            with self.assertRaisesRegex(custody.CustodyStopped, "RECEIPT_NOT_VISIBLE"):
                provider.resolve()
        self.assertEqual(provider.creates, 1)
        self.assertEqual(provider.stamps, 0)
        self.assertEqual(provider.deletes, 0)


if __name__ == "__main__":
    unittest.main()
