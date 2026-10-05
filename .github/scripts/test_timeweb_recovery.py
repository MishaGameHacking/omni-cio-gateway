"""Backup controller contracts with lost provider responses and durable receipts."""

from __future__ import annotations

import copy
import unittest
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import timeweb_auth_postgres as postgres
import timeweb_recovery as recovery

CLUSTER_ID = 4215095


def backup(backup_id: int = 1, *, kind: str = "manual", age: int = 1) -> dict[str, Any]:
    return {
        "id": backup_id,
        "type": kind,
        "status": "done",
        "size": 10,
        "created_at": (datetime.now(UTC) - timedelta(hours=age)).isoformat(),
        "comment": recovery.BOOTSTRAP_COMMENT if kind == "manual" else "",
    }


class Provider:
    def __init__(self) -> None:
        self.schedule: dict[str, Any] = {"is_enabled": False}
        self.backups: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str]] = []
        self.lose_response: set[str] = set()
        self.drop_request: set[str] = set()
        self.wrong_detail = False

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, path))
        if method in self.drop_request:
            raise OSError("connection lost before confirmation")
        if method == "PATCH" and path.endswith("/auto-backups"):
            self.schedule = copy.deepcopy(kwargs["payload"])
        elif method == "POST" and path.endswith("/backups"):
            next_id = max((item["id"] for item in self.backups), default=0) + 1
            self.backups.append(backup(next_id) | {
                "comment": kwargs["payload"]["comment"],
                "created_at": datetime.now(UTC).isoformat(),
            })
        elif method == "DELETE":
            target = int(path.rsplit("/", 1)[1])
            self.backups = [item for item in self.backups if item["id"] != target]
        elif method == "GET" and path.endswith("/auto-backups"):
            return {"auto_backups_settings": copy.deepcopy(self.schedule)}
        elif method == "GET" and "/backups?" in path:
            return {"backups": copy.deepcopy(self.backups)}
        elif method == "GET" and "/backups/" in path:
            item = next(item for item in self.backups if str(item["id"]) == path.rsplit("/", 1)[1])
            detail = copy.deepcopy(item)
            if self.wrong_detail:
                detail["id"] += 100
            return {"backup": detail}
        else:
            raise AssertionError(f"Unexpected provider endpoint: {method} {path}")
        if method in self.lose_response:
            raise TimeoutError("operation applied, response lost")
        return {}


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = Provider()
        self.state: dict[str, Any] = {}
        self.remote = Mock()
        self.cluster = {
            "id": CLUSTER_ID,
            "disk": {"size": 20 * 1024 * 1024},
            "disk_autoscaling": {"is_enabled": False},
        }
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(recovery.time, "sleep"))
        self.stack.enter_context(
            patch.object(recovery, "read_state", side_effect=lambda _: copy.deepcopy(self.state))
        )
        self.write = self.stack.enter_context(
            patch.object(recovery, "write_state", side_effect=self.save)
        )
        self.stack.enter_context(patch("builtins.print"))

    def save(self, _remote: Any, value: dict[str, Any]) -> None:
        self.state = copy.deepcopy(value)

    def run_controller(self) -> None:
        recovery.ensure_recovery_point(self.provider, self.remote, self.cluster)

    def mutations(self, method: str) -> list[str]:
        return [path for verb, path in self.provider.calls if verb == method]

    def test_first_copy_and_daily_schedule_are_verified_and_second_run_is_read_only(self) -> None:
        self.run_controller()
        self.run_controller()
        self.assertEqual(len(self.mutations("PATCH")), 1)
        self.assertEqual(len(self.mutations("POST")), 2)
        self.assertEqual(self.mutations("DELETE"), [])
        self.assertEqual(self.provider.schedule["copy_count"], 7)
        self.assertEqual(self.provider.schedule["day_of_week"], 1)
        self.assertEqual(self.state["provider_status"], "ok")
        self.assertEqual(self.state["latest_backup_id"], 2)

    def test_lost_applied_responses_are_reconciled_without_repeating_mutations(self) -> None:
        self.provider.lose_response = {"PATCH", "POST"}
        self.run_controller()
        self.assertEqual(len(self.mutations("PATCH")), 1)
        self.assertEqual(len(self.mutations("POST")), 2)
        self.assertEqual(self.state["provider_status"], "ok")

    def test_unconfirmed_mutation_is_not_repeated_after_process_restart(self) -> None:
        for method in ("PATCH", "POST"):
            with self.subTest(method=method):
                self.provider = Provider()
                self.state = {}
                self.provider.drop_request = {method}
                for _ in range(2):
                    with self.assertRaises(recovery.RecoveryBlocked):
                        self.run_controller()
                self.assertEqual(len(self.mutations(method)), 1)
                self.assertEqual(self.state["provider_status"], "unavailable")

    def test_receipt_must_persist_before_provider_mutation(self) -> None:
        self.write.side_effect = OSError("disk full")
        with self.assertRaises(OSError):
            self.run_controller()
        self.assertEqual(self.mutations("PATCH"), [])
        self.assertEqual(self.mutations("POST"), [])

    def test_approved_cluster_and_capacity_are_required_before_any_paid_operation(self) -> None:
        cases = (
            {"id": CLUSTER_ID + 1},
            {"disk": {"size": 21 * 1024 * 1024}},
            {"disk": {"size": -1}},
            {"disk_autoscaling": {"is_enabled": True}},
            {"disk_autoscaling": {}},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(recovery.RecoveryBlocked):
                recovery.ensure_recovery_point(self.provider, self.remote, self.cluster | changes)
        self.assertEqual(self.mutations("PATCH"), [])
        self.assertEqual(self.mutations("POST"), [])
        smaller_budget = recovery.BackupPolicy(CLUSTER_ID, 7, 20971520, 1500, 6, 4)
        with self.assertRaises(recovery.RecoveryBlocked):
            recovery.validate_budget(self.cluster, smaller_budget)

    def test_existing_retention_and_unknown_inventory_are_not_overwritten(self) -> None:
        self.provider.schedule = {"is_enabled": False, "copy_count": 30}
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("PATCH"), [])
        for response in ({}, {"backups": ["invalid"]}, {"backups": [{}] * 100}):
            provider = Mock(request=Mock(return_value=response))
            with (
                self.subTest(response_type=str(type(response))),
                self.assertRaises(recovery.RecoveryBlocked),
            ):
                recovery.get_backups(provider, CLUSTER_ID)

    def test_old_failed_or_in_progress_backup_does_not_create_more_copies(self) -> None:
        for item in (
            backup(age=25),
            backup() | {"status": "fail"},
            backup() | {"status": "create"},
        ):
            with self.subTest(status=item["status"]):
                self.provider.backups = [item]
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller()
        self.assertEqual(self.mutations("POST"), [])

    def test_invalid_timestamps_sizes_and_detail_identity_cannot_certify_a_copy(self) -> None:
        for changes in (
            {"created_at": "2026-10-05T01:00:00"},
            {"created_at": "missing"},
            {"size": 0},
            {"size": True},
            {"size": float("nan")},
            {"id": True},
        ):
            item, now = backup() | changes, datetime.now(UTC)
            with self.subTest(changes=changes), self.assertRaises(recovery.RecoveryBlocked):
                recovery.completed_backup(item, now)
        self.assertFalse(recovery.completed_backup(backup(age=-1), datetime.now(UTC)))
        self.provider.wrong_detail = True
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.state["provider_status"], "unavailable")

    def test_bootstrap_is_retired_only_after_newer_automatic_copy_is_reconfirmed(self) -> None:
        self.run_controller()
        self.provider.backups = [
            backup(1, age=2),
            backup(3, kind="auto"),
            backup(4) | {"comment": "operator"},
            self.provider.backups[1],
        ]
        self.provider.lose_response = {"DELETE"}
        self.run_controller()
        self.run_controller()
        self.assertEqual(self.mutations("DELETE"), [f"/dbs/{CLUSTER_ID}/backups/1"])
        self.assertEqual({item["id"] for item in self.provider.backups}, {2, 3, 4})
        calls = self.provider.calls
        self.assertLess(
            calls.index(("GET", f"/dbs/{CLUSTER_ID}/backups/3")),
            calls.index(("DELETE", f"/dbs/{CLUSTER_ID}/backups/1")),
        )

    def test_last_copy_wrong_detail_and_unconfirmed_delete_are_protected(self) -> None:
        self.run_controller()
        self.assertEqual(self.mutations("DELETE"), [])
        self.provider.backups = [backup(1, age=2), backup(3, kind="auto"),
                                 self.provider.backups[1]]
        self.provider.wrong_detail = True
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("DELETE"), [])
        self.provider.wrong_detail = False
        self.provider.drop_request = {"DELETE"}
        for _ in range(2):
            with self.assertRaises(recovery.RecoveryBlocked):
                self.run_controller()
        self.assertEqual(len(self.mutations("DELETE")), 1)

    def seed_weekly_history(self) -> list[int]:
        now = datetime.now(UTC)
        self.provider.schedule = {
            "is_enabled": True, "interval": "day", "copy_count": 7,
            "creation_start_at": now.isoformat(),
        }
        self.provider.backups = [backup(1, kind="auto")]
        records = []
        for age in range(1, 5):
            created = now - timedelta(weeks=age)
            period = recovery.weekly_period(created)
            record = {"id": 10 + age, "period": period}
            records.append(record)
            self.provider.backups.append(backup(record["id"]) | {
                "created_at": created.isoformat(),
                "comment": recovery.WEEKLY_PREFIX + period,
            })
        self.state = {"schema_version": 1, "cluster_id": CLUSTER_ID, "weekly_owned": records}
        return [record["id"] for record in records]

    def test_weekly_rotation_keeps_four_and_never_deletes_unowned_or_daily_copy(self) -> None:
        older_ids = self.seed_weekly_history()
        self.provider.backups.append(backup(50) | {"comment": "operator"})
        self.run_controller()
        self.run_controller()
        self.assertEqual(self.mutations("DELETE"), [f"/dbs/{CLUSTER_ID}/backups/{older_ids[-1]}"])
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertEqual({item["id"] for item in self.provider.backups}, {1, 11, 12, 13, 50, 51})
        self.assertEqual(self.state["weekly_available_copies"], 4)
        self.assertEqual(len(self.state["weekly_owned"]), 4)
        self.assertNotIn("weekly_retire_attempted", self.state)

    def test_weekly_failed_or_lost_create_cannot_multiply_paid_copies_after_restart(self) -> None:
        self.seed_weekly_history()
        self.provider.drop_request = {"POST"}
        for _ in range(2):
            with self.assertRaises(recovery.RecoveryBlocked):
                self.run_controller()
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertEqual(self.mutations("DELETE"), [])
        self.assertEqual(len(self.state["weekly_owned"]), 4)
        self.assertEqual(self.state["provider_status"], "unavailable")

    def test_weekly_lost_applied_create_and_delete_are_reconciled(self) -> None:
        self.seed_weekly_history()
        self.provider.lose_response = {"POST", "DELETE"}
        self.run_controller()
        self.run_controller()
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertEqual(len(self.mutations("DELETE")), 1)
        self.assertEqual(self.state["weekly_available_copies"], 4)

    def test_unknown_weekly_delete_does_not_delete_again_or_create_another_copy(self) -> None:
        self.seed_weekly_history()
        self.provider.drop_request = {"DELETE"}
        for _ in range(2):
            with self.assertRaises(recovery.RecoveryBlocked):
                self.run_controller()
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertEqual(len(self.mutations("DELETE")), 1)
        self.assertEqual(len(self.state["weekly_owned"]), 5)
        target = self.state["weekly_retire_attempted"]
        # Reconciliation may finish later; the next run observes absence, without a new DELETE.
        self.provider.backups = [row for row in self.provider.backups if row["id"] != target]
        self.run_controller()
        self.assertEqual(len(self.mutations("DELETE")), 1)
        self.assertEqual(self.state["weekly_available_copies"], 4)

    def test_deleted_or_unowned_weekly_copy_blocks_mutations(self) -> None:
        self.run_controller()
        self.provider.calls.clear()
        self.provider.backups = [row for row in self.provider.backups if row["id"] != 2]
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("POST"), [])
        self.assertEqual(self.mutations("DELETE"), [])
        self.state = {}
        self.provider.backups.append(backup(99) | {
            "created_at": datetime.now(UTC).isoformat(),
            "comment": recovery.WEEKLY_PREFIX + recovery.weekly_period(datetime.now(UTC)),
        })
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("POST"), [])
        self.assertEqual(self.mutations("DELETE"), [])

    def test_weekly_receipt_and_storage_ceiling_are_checked_before_create(self) -> None:
        self.seed_weekly_history()
        self.write.side_effect = OSError("durable receipt unavailable")
        with self.assertRaises(OSError):
            self.run_controller()
        self.assertEqual(self.mutations("POST"), [])
        self.write.side_effect = self.save
        self.provider.backups.extend(backup(value) | {"comment": "operator"}
                                     for value in range(20, 28))
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("POST"), [])

    def test_new_weekly_copy_is_not_a_restore_proof_or_four_existing_copies(self) -> None:
        self.run_controller()
        self.assertEqual(self.state["weekly_available_copies"], 1)
        self.assertEqual(self.state["weekly_retention_copies"], 4)
        self.assertNotIn("production_restore_verified", self.state)
        due = datetime.fromisoformat(self.state["weekly_next_due_at"])
        self.assertEqual((due.weekday(), due.hour), (0, 0))
        self.assertEqual(due.utcoffset(), timedelta(hours=3))

    def test_duplicate_inventory_or_retagged_owned_copy_is_not_accepted(self) -> None:
        self.seed_weekly_history()
        self.provider.backups.append(copy.deepcopy(self.provider.backups[-1]))
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.provider.backups.pop()
        self.provider.backups[-1]["comment"] = "operator now owns this"
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("POST"), [])
        self.assertEqual(self.mutations("DELETE"), [])

    def test_moscow_week_boundary_and_year_rollover_are_stable(self) -> None:
        self.assertEqual(recovery.weekly_period(datetime(2026, 10, 4, 20, 59, tzinfo=UTC)),
                         "2026-09-28")
        self.assertEqual(recovery.weekly_period(datetime(2026, 10, 4, 21, 0, tzinfo=UTC)),
                         "2026-10-05")
        self.assertEqual(recovery.weekly_period(datetime(2027, 1, 1, tzinfo=UTC)), "2026-12-28")


class MigrationGateTests(unittest.TestCase):
    def test_backup_gate_protects_migrations_and_scheduled_checks_keep_runtime(self) -> None:
        desired = postgres.DesiredDatabase(
            "managed", "omnicio", "app", "18", "ru-3", "msk-1", Decimal(1110), 1, 2048, 20480
        )
        for backup_only, rejected in ((False, True), (True, False), (False, False)):
            with self.subTest(backup_only=backup_only, rejected=rejected), ExitStack() as stack:
                client = Mock()
                mocks: dict[str, Any] = {}
                values = {
                    "find_managed_server": {"id": 9235089},
                    "find_vpc": {"id": "private"},
                    "find_vpc_service": {"local_ip": "10.77.0.4"},
                    "private_server_cidr": "10.77.0.4/24",
                    "select_postgres_type": "postgres18",
                    "select_database_preset": {"id": 1},
                    "find_database_cluster": {"id": CLUSTER_ID},
                    "public_ipv4": "192.0.2.1",
                    "wait_for_database_endpoint": ({"id": CLUSTER_ID}, Mock()),
                    "validate_existing_cluster": None,
                    "service_matches": True,
                    "load_or_create_server_secrets": {},
                    "ensure_server_private_network": None,
                    "write_runtime_env": None,
                    "run_schema_migration": None,
                    "add_summary": None,
                    "set_output": None,
                    "ensure_recovery_point": None,
                    "inspect_restore_capacity": None,
                }
                for name, value in values.items():
                    mocks[name] = stack.enter_context(
                        patch.object(postgres, name, return_value=value)
                    )
                stack.enter_context(patch.object(postgres, "EphemeralSsh"))
                client.get_vpc_services.return_value = [{}]
                if rejected:
                    mocks["ensure_recovery_point"].side_effect = recovery.RecoveryBlocked("no copy")
                kwargs = dict(
                    desired=desired,
                    server_name="server",
                    server_comment="managed",
                    vpc_name="private",
                    migration_sqls=["SELECT 1"],
                    backup_only=backup_only,
                )
                if rejected:
                    with self.assertRaises(recovery.RecoveryBlocked):
                        postgres.reconcile(client, **kwargs)
                else:
                    self.assertEqual(postgres.reconcile(client, **kwargs), 0)
                for name in (
                    "write_runtime_env",
                    "run_schema_migration",
                    "load_or_create_server_secrets",
                    "ensure_server_private_network",
                ):
                    self.assertEqual(mocks[name].call_count, int(not backup_only and not rejected))
                client.create_database_cluster.assert_not_called()


class RestoreCapacityTests(unittest.TestCase):
    def test_inventory_is_read_only_and_filters_storage_credentials(self) -> None:
        provider = Mock()
        provider.request.side_effect = [
            {"backups": []},
            {"buckets": [{"id": 1, "type": "private", "secret_key": "private-canary",
                          "access_key": "credential-canary", "name": "personal-name"}]},
        ]
        remote = Mock(run=Mock(return_value='{"disk_free_bytes":100}'))
        with patch("builtins.print") as output:
            recovery.inspect_restore_capacity(provider, remote, CLUSTER_ID)
        rendered = output.call_args.args[0]
        for secret in ("private-canary", "credential-canary", "personal-name"):
            self.assertNotIn(secret, rendered)
        self.assertIn('"restore_verified": false', rendered)
        self.assertTrue(all(call.args[0] == "GET" for call in provider.request.call_args_list))

    def test_unavailable_inventory_does_not_claim_success_or_print_provider_error(self) -> None:
        provider = Mock(request=Mock(side_effect=RuntimeError("sensitive-provider-response")))
        remote = Mock(run=Mock(return_value="{}"))
        with patch("builtins.print") as output:
            recovery.inspect_restore_capacity(provider, remote, CLUSTER_ID)
        self.assertNotIn("sensitive-provider-response", output.call_args.args[0])
        self.assertIn('"status": "unavailable"', output.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
