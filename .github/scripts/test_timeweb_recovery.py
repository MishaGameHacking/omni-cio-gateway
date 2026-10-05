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
            self.backups.append(backup())
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
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertEqual(self.mutations("DELETE"), [])
        self.assertEqual(self.provider.schedule["copy_count"], 7)
        self.assertEqual(self.provider.schedule["day_of_week"], 1)
        self.assertEqual(self.state["provider_status"], "ok")
        self.assertEqual(self.state["latest_backup_id"], 1)

    def test_lost_applied_responses_are_reconciled_without_repeating_mutations(self) -> None:
        self.provider.lose_response = {"PATCH", "POST"}
        self.run_controller()
        self.assertEqual(len(self.mutations("PATCH")), 1)
        self.assertEqual(len(self.mutations("POST")), 1)
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
        smaller_budget = recovery.BackupPolicy(CLUSTER_ID, 7, 20971520, 900, 6)
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
            backup(2, kind="auto"),
            backup(3) | {"comment": "operator"},
        ]
        self.provider.lose_response = {"DELETE"}
        self.run_controller()
        self.run_controller()
        self.assertEqual(self.mutations("DELETE"), [f"/dbs/{CLUSTER_ID}/backups/1"])
        self.assertEqual({item["id"] for item in self.provider.backups}, {2, 3})
        calls = self.provider.calls
        self.assertLess(
            calls.index(("GET", f"/dbs/{CLUSTER_ID}/backups/2")),
            calls.index(("DELETE", f"/dbs/{CLUSTER_ID}/backups/1")),
        )

    def test_last_copy_wrong_detail_and_unconfirmed_delete_are_protected(self) -> None:
        self.run_controller()
        self.assertEqual(self.mutations("DELETE"), [])
        self.provider.backups = [backup(1, age=2), backup(2, kind="auto")]
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


if __name__ == "__main__":
    unittest.main()
