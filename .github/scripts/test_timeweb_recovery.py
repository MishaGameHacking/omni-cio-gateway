"""Backup controller contracts with lost provider responses and durable receipts."""

from __future__ import annotations

import copy
import json
import unittest
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import inplace_upgrade
import timeweb_auth_postgres as postgres
import timeweb_recovery as recovery

CLUSTER_ID = 4215095
RELEASE_SHA = "a" * 40


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
        self.post_changes: dict[str, Any] = {}
        self.post_response: Any = {}
        self.detail_changes: dict[int, dict[str, Any]] = {}
        self.created_at: datetime | None = None

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
                "created_at": (self.created_at or datetime.now(UTC)).isoformat(),
            } | self.post_changes)
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
            detail.update(self.detail_changes.get(int(detail["id"]), {}))
            if self.wrong_detail:
                detail["id"] += 100
            return {"backup": detail}
        else:
            raise AssertionError(f"Unexpected provider endpoint: {method} {path}")
        if method in self.lose_response:
            raise TimeoutError("operation applied, response lost")
        return copy.deepcopy(self.post_response) if method == "POST" else {}


class ControllerFixture(unittest.TestCase):
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

    def run_controller(self, *, release_sha: str | None = None) -> None:
        recovery.ensure_recovery_point(
            self.provider, self.remote, self.cluster, release_sha=release_sha,
        )

    def mutations(self, method: str) -> list[str]:
        return [path for verb, path in self.provider.calls if verb == method]


class RecoveryTests(ControllerFixture):
    def setUp(self) -> None:
        super().setUp()
        self.stack.enter_context(patch.object(
            recovery, "load_policy",
            return_value=replace(recovery.load_policy(), mode="managed_backups"),
        ))

    def test_first_copy_and_daily_schedule_are_verified_and_second_run_is_read_only(self) -> None:
        self.run_controller()
        self.run_controller()
        self.assertEqual(len(self.mutations("PATCH")), 1)
        self.assertEqual(len(self.mutations("POST")), 2)
        self.assertEqual(self.mutations("DELETE"), [])
        self.assertEqual(self.provider.schedule["copy_count"], 7)
        self.assertEqual(self.provider.schedule["day_of_week"], 1)
        self.assertEqual(self.state["provider_status"], "ok")
        # Coarse provider/OS clock precision can give both completed copies the same time.
        self.assertIn(self.state["latest_backup_id"], {1, 2})
        self.assertEqual(self.state["weekly_owned"][0]["id"], 2)

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

    def test_malformed_weekly_period_blocks_provider_mutations(self) -> None:
        for period in (None, 42, "bad", "2026-10-06"):
            with self.subTest(period=period):
                self.seed_weekly_history()
                self.state["weekly_owned"][0]["period"] = period
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller()
        self.assertEqual(self.mutations("POST"), [])
        self.assertEqual(self.mutations("DELETE"), [])

    def seed_release_history(self) -> None:
        now = datetime(2026, 10, 7, 1, tzinfo=UTC)
        self.clock = self.stack.enter_context(patch.object(recovery, "datetime", wraps=datetime))
        self.clock.now.return_value = now
        self.provider = Provider()
        self.provider.created_at = now
        self.provider.schedule = {
            "is_enabled": True, "interval": "day", "copy_count": 7,
            "creation_start_at": "2026-10-05",
        }
        self.provider.backups = [
            backup(10, kind="auto") | {"created_at": "2026-10-05T21:52:33Z"},
            backup(20) | {"created_at": "2026-10-05T05:08:09Z",
                          "comment": recovery.WEEKLY_PREFIX + "2026-10-05"},
        ]
        self.state = {
            "schema_version": 1, "cluster_id": CLUSTER_ID,
            "bootstrap_attempted": True, "retire_attempted": 1,
            recovery.WEEKLY_OWNED: [{"id": 20, "period": "2026-10-05"}],
            recovery.WEEKLY_CREATE: {"period": "2026-10-05", "confirmed_id": 20,
                                     "attempted_at": "2026-10-05T05:08:00Z"},
        }

    def test_prerelease_copy_is_confirmed_once_then_reused_without_delete(self) -> None:
        self.seed_release_history()
        self.provider.post_response = {"backup": {"id": 21}}
        self.run_controller(release_sha=RELEASE_SHA)
        self.run_controller(release_sha="b" * 40)
        self.run_controller()
        receipt = self.state[recovery.RELEASE_COPY]
        self.assertEqual(receipt["release_sha"], RELEASE_SHA)
        self.assertEqual(receipt["baseline_ids"], [10, 20])
        self.assertEqual(receipt["response_id"], 21)
        self.assertEqual(receipt["confirmed_id"], 21)
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertEqual(self.mutations("DELETE"), [])
        self.assertEqual(self.state["provider_status"], "ok")
        self.assertEqual(self.state["latest_backup_id"], 21)
        self.assertEqual(self.state["weekly_available_copies"], 1)

    def test_fresh_copy_needs_no_fallback_and_scheduled_stale_check_cannot_create_it(self) -> None:
        self.seed_release_history()
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller()
        self.assertEqual(self.mutations("POST"), [])
        self.provider.backups[0]["created_at"] = "2026-10-07T00:00:00Z"
        self.run_controller(release_sha=RELEASE_SHA)
        self.assertNotIn(recovery.RELEASE_COPY, self.state)
        self.assertEqual(self.mutations("POST"), [])

    def test_prerelease_creation_requires_settled_owned_inventory(self) -> None:
        for changes in (
            {"status": "create"}, {"status": "fail"}, {"size": 0},
            {"created_at": "2026-10-08T00:00:00Z"}, {"type": "other"},
            {"type": "manual", "comment": "operator"},
            {"comment": recovery.RELEASE_PREFIX + RELEASE_SHA},
        ):
            with self.subTest(changes=changes):
                self.seed_release_history()
                self.provider.backups[0].update(changes)
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha=RELEASE_SHA)
                self.assertEqual(self.mutations("POST"), [])

    def test_prerelease_creation_preserves_retention_and_rotation_spare(self) -> None:
        for extra_count in (7, 10):
            with self.subTest(extra_count=extra_count):
                self.seed_release_history()
                self.provider.backups.extend(
                    backup(index, kind="auto") | {"created_at": "2026-10-05T20:00:00Z"}
                    for index in range(30, 30 + extra_count)
                )
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha=RELEASE_SHA)
                self.assertEqual(self.mutations("POST"), [])
                self.assertEqual(self.mutations("DELETE"), [])

    def test_unresolved_bootstrap_and_weekly_receipts_block_prerelease_creation(self) -> None:
        for state_changes in (
            {"retire_attempted": None}, {recovery.WEEKLY_RETIRE: 20},
            {recovery.WEEKLY_CREATE: {"period": "2026-10-05"}},
        ):
            with self.subTest(state_changes=state_changes):
                self.seed_release_history()
                self.state.update(state_changes)
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha=RELEASE_SHA)
                self.assertEqual(self.mutations("POST"), [])
        self.seed_release_history()
        self.provider.backups.append(backup(1) | {"created_at": "2026-10-05T01:00:00Z"})
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller(release_sha=RELEASE_SHA)
        self.assertEqual(self.mutations("POST"), [])
        self.assertEqual(self.mutations("DELETE"), [])

    def test_prerelease_receipt_write_failure_precedes_provider_post(self) -> None:
        self.seed_release_history()
        self.write.side_effect = OSError("receipt unavailable")
        with self.assertRaises(OSError):
            self.run_controller(release_sha=RELEASE_SHA)
        self.assertEqual(self.mutations("POST"), [])

    def test_crash_between_receipt_and_post_cannot_create_after_restart_or_new_sha(self) -> None:
        self.seed_release_history()
        with (
            patch.object(recovery, "mutate_once", side_effect=SystemExit("stopped")),
            self.assertRaises(SystemExit),
        ):
            self.run_controller(release_sha=RELEASE_SHA)
        self.assertIn(recovery.RELEASE_COPY, self.state)
        self.provider.backups[0]["created_at"] = "2026-10-07T00:00:00Z"
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller(release_sha="b" * 40)
        self.assertEqual(self.mutations("POST"), [])

    def test_lost_create_response_is_reconciled_but_dropped_request_is_never_retried(self) -> None:
        self.seed_release_history()
        self.provider.lose_response = {"POST"}
        self.run_controller(release_sha=RELEASE_SHA)
        self.assertEqual(self.state[recovery.RELEASE_COPY]["confirmed_id"], 21)
        self.assertEqual(len(self.mutations("POST")), 1)
        self.seed_release_history()
        self.provider.drop_request = {"POST"}
        for sha in (RELEASE_SHA, "b" * 40, None):
            with self.subTest(sha=sha), self.assertRaises(recovery.RecoveryBlocked):
                self.run_controller(release_sha=sha)
        self.assertEqual(len(self.mutations("POST")), 1)
        self.assertNotIn("confirmed_id", self.state[recovery.RELEASE_COPY])

    def test_malformed_prerelease_receipts_block_without_provider_writes(self) -> None:
        self.seed_release_history()
        self.provider.drop_request = {"POST"}
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller(release_sha=RELEASE_SHA)
        receipt = copy.deepcopy(self.state[recovery.RELEASE_COPY])
        for changes in (
            {"cluster_id": CLUSTER_ID + 1}, {"release_sha": "bad"}, {"comment": "foreign"},
            {"attempted_at": "2026-10-08T00:00:00Z"}, {"baseline_ids": [10, 10]},
            {"confirmed_id": 10}, {"confirmed_id": True},
        ):
            with self.subTest(changes=changes):
                self.state[recovery.RELEASE_COPY] = receipt | changes
                self.provider.calls.clear()
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha="b" * 40)
                self.assertEqual(self.mutations("POST"), [])

    def test_returned_create_identity_is_bound_to_readback_and_null_is_supported(self) -> None:
        for response, expected_id in (
            ({"backup": None}, 21), ({"backup": {"id": 99}}, None),
            ({"backup": {"id": True}}, None), ({"backup": {"id": 10}}, None),
        ):
            with self.subTest(response=response):
                self.seed_release_history()
                self.provider.post_response = response
                if expected_id is not None:
                    self.run_controller(release_sha=RELEASE_SHA)
                    self.assertEqual(self.state[recovery.RELEASE_COPY]["confirmed_id"], expected_id)
                else:
                    with self.assertRaises(recovery.RecoveryBlocked):
                        self.run_controller(release_sha=RELEASE_SHA)
                    with self.assertRaises(recovery.RecoveryBlocked):
                        self.run_controller(release_sha="b" * 40)
                    self.assertNotIn("confirmed_id", self.state[recovery.RELEASE_COPY])
                self.assertEqual(len(self.mutations("POST")), 1)

    def test_malformed_post_response_shape_is_durably_blocked_without_retry(self) -> None:
        for response in ([], "private-provider-body", True):
            with self.subTest(response_type=type(response).__name__):
                self.seed_release_history()
                self.provider.post_response = response
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha=RELEASE_SHA)
                receipt = self.state[recovery.RELEASE_COPY]
                self.assertTrue(receipt["response_invalid"])
                self.assertNotIn("confirmed_id", receipt)
                self.assertEqual(self.state["provider_status"], "unavailable")
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha="b" * 40)
                self.assertEqual(len(self.mutations("POST")), 1)

    def test_candidate_and_independent_detail_must_both_match_recorded_operation(self) -> None:
        invalid = (
            {"id": 10}, {"type": "auto"}, {"comment": "foreign"}, {"size": 0},
            {"created_at": "2026-10-07T00:59:59Z"}, {"status": "fail"},
        )
        for boundary in ("inventory", "detail"):
            for changes in invalid:
                with self.subTest(boundary=boundary, changes=changes):
                    self.seed_release_history()
                    if boundary == "inventory":
                        self.provider.post_changes = changes
                    else:
                        self.provider.detail_changes[21] = changes
                    with self.assertRaises(recovery.RecoveryBlocked):
                        self.run_controller(release_sha=RELEASE_SHA)
                    self.assertNotIn("confirmed_id", self.state[recovery.RELEASE_COPY])
                    self.assertEqual(len(self.mutations("POST")), 1)

    def test_singleton_cannot_repeat_but_later_fresh_auto_is_independent(self) -> None:
        for remove_owned in (False, True):
            with self.subTest(remove_owned=remove_owned):
                self.seed_release_history()
                self.run_controller(release_sha=RELEASE_SHA)
                self.clock.now.return_value = datetime(2026, 10, 9, 1, tzinfo=UTC)
                if remove_owned:
                    self.provider.backups = [
                        row for row in self.provider.backups if row["id"] != 21
                    ]
                with self.assertRaises(recovery.RecoveryBlocked):
                    self.run_controller(release_sha="b" * 40)
                self.provider.backups.append(backup(22, kind="auto") | {
                    "created_at": "2026-10-09T00:00:00Z",
                })
                self.run_controller(release_sha="b" * 40)
                self.assertEqual(self.state["latest_backup_id"], 22)
                self.assertEqual(len(self.mutations("POST")), 1)
                self.assertEqual(self.mutations("DELETE"), [])

    def test_confirmed_prerelease_copy_does_not_skip_remaining_recovery_checks(self) -> None:
        self.seed_release_history()
        with (
            patch.object(
                recovery, "reconcile_weekly", side_effect=recovery.RecoveryBlocked("weekly"),
            ),
            self.assertRaises(recovery.RecoveryBlocked),
        ):
            self.run_controller(release_sha=RELEASE_SHA)
        self.assertEqual(self.state[recovery.RELEASE_COPY]["confirmed_id"], 21)
        self.assertEqual(self.state["provider_status"], "unavailable")
        self.assertNotIn("latest_backup_id", self.state)

    def test_fresh_auto_does_not_hide_a_retagged_newer_confirmed_copy(self) -> None:
        self.seed_release_history()
        self.run_controller(release_sha=RELEASE_SHA)
        self.provider.backups[0]["created_at"] = "2026-10-07T00:00:00Z"
        self.provider.backups[-1]["comment"] = "foreign"
        with self.assertRaises(recovery.RecoveryBlocked):
            self.run_controller(release_sha="b" * 40)
        self.assertEqual(self.state["provider_status"], "unavailable")
        self.assertEqual(len(self.mutations("POST")), 1)


class SingleDatabaseTests(ControllerFixture):
    def test_only_future_copy_schedule_is_stopped_and_existing_evidence_is_preserved(self) -> None:
        self.provider.schedule = {"is_enabled": True, "copy_count": 7, "interval": "day"}
        self.provider.backups = [backup(11, age=100), backup(12, kind="auto", age=50)]
        self.state = {"schema_version": 1, "cluster_id": CLUSTER_ID, "weekly_owned": [{"id": 11}],
                      "restore_verification": {"signature": "retained"}}
        old_backups, old_state = copy.deepcopy(self.provider.backups), copy.deepcopy(self.state)
        with patch.object(self.provider, "request", wraps=self.provider.request) as request:
            self.run_controller(release_sha=RELEASE_SHA)
            self.run_controller()
        mutations = [call for call in request.call_args_list if call.args[0] != "GET"]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0].args, ("PATCH", f"/dbs/{CLUSTER_ID}/auto-backups"))
        self.assertEqual(mutations[0].kwargs, {"payload": {"is_enabled": False}})
        self.assertEqual(self.provider.backups, old_backups)
        for key, value in old_state.items():
            self.assertEqual(self.state[key], value)
        self.assertEqual(self.state["provider_status"], "ok")
        self.assertEqual(self.state["existing_copy_count"], 2)
        self.assertEqual(self.state["latest_backup_id"], 12)
        self.assertIs(self.state["copy_creation_enabled"], False)

    def test_disabled_schedule_without_any_backups_does_not_create_one(self) -> None:
        self.run_controller(release_sha=RELEASE_SHA)
        self.assertIsNone(self.state["latest_backup_id"])
        self.assertIsNone(self.state["latest_backup_at"])
        self.assertTrue(all(method == "GET" for method, _ in self.provider.calls))
        report = recovery.inspect_provider_recovery(self.provider)
        self.assertTrue(report["schedule"]["matches_policy"])
        self.assertEqual(report["schedule"]["policy_mode"], recovery.SINGLE_DATABASE_MODE)
        self.assertFalse(report["restore_verified"])

    def test_stop_response_loss_reconciles_and_unconfirmed_request_is_never_repeated(self) -> None:
        for applied in (True, False):
            with self.subTest(applied=applied):
                self.provider, self.state = Provider(), {}
                self.provider.schedule = {"is_enabled": True}
                if applied:
                    self.provider.lose_response = {"PATCH"}
                    self.run_controller()
                    self.run_controller()
                else:
                    self.provider.drop_request = {"PATCH"}
                    for _ in range(2):
                        with self.assertRaises(recovery.RecoveryBlocked):
                            self.run_controller()
                self.assertEqual(len(self.mutations("PATCH")), 1)
                self.assertEqual(self.mutations("POST"), [])
                self.assertEqual(self.mutations("DELETE"), [])

    def test_changed_final_schedule_cannot_be_reported_disabled(self) -> None:
        with patch.object(recovery, "get_schedule", side_effect=[
            {"is_enabled": False}, {"is_enabled": True},
        ]), self.assertRaisesRegex(recovery.RecoveryBlocked, "changed during verification"):
            self.run_controller()
        self.assertEqual(self.state["provider_status"], "unavailable")
        self.assertNotIn("copy_creation_enabled", self.state)

    def test_missing_mode_never_defaults_to_paid_copy_creation(self) -> None:
        for upgrade in (None, {}, {"mode": "unknown"}, {"mode": []}):
            document = {"tool": {"omnicio": {"timeweb": {"backups": {}, "upgrade": upgrade}}}}
            with (self.subTest(upgrade=upgrade),
                  patch.object(recovery.tomllib, "load", return_value=document),
                  self.assertRaisesRegex(recovery.RecoveryBlocked, "Unknown production")):
                self.run_controller()
        self.assertEqual(self.provider.calls, [])

    def test_direct_mutation_cannot_create_delete_or_reconfigure_backups(self) -> None:
        for method, suffix, payload in (
            ("POST", "backups", {}), ("DELETE", "backups/11", {}),
            ("PATCH", "auto-backups", {"is_enabled": True}),
            ("PATCH", "auto-backups", {"is_enabled": False, "copy_count": 1}),
            ("PATCH", "auto-backups", {"is_enabled": 0}),
        ):
            with (self.subTest(method=method, payload=payload),
                  self.assertRaises(recovery.RecoveryBlocked)):
                recovery.mutate_once(self.provider, method, f"/dbs/{CLUSTER_ID}/{suffix}",
                                     payload=payload)
        self.assertEqual(self.provider.calls, [])

    def test_stop_receipt_must_persist_before_mutation(self) -> None:
        self.provider.schedule = {"is_enabled": True}
        self.write.side_effect = OSError("synthetic disk full")
        with self.assertRaises(OSError):
            self.run_controller()
        self.assertEqual(self.mutations("PATCH"), [])


class MigrationGateTests(unittest.TestCase):
    def test_new_release_cannot_use_historical_plan_before_provider_or_ssh_access(self) -> None:
        with self.assertRaisesRegex(
            inplace_upgrade.UpgradeBlocked, "^application_version_mismatch$",
        ):
            postgres.load_plan()
        client = Mock()
        desired = postgres.DesiredDatabase(
            "managed", "omnicio", "app", "18", "ru-3", "msk-1", Decimal(1110), 1, 2048, 20480
        )
        with (
            patch.object(postgres, "load_policy", return_value=replace(
                recovery.load_policy(), mode=recovery.SINGLE_DATABASE_MODE,
            )),
            patch.object(postgres, "EphemeralSsh") as ssh,
            self.assertRaisesRegex(
                inplace_upgrade.UpgradeBlocked, "^application_version_mismatch$",
            ),
        ):
            postgres.reconcile(
                client, desired=desired, server_name="server", server_comment="managed",
                vpc_name="private", migration_sqls=["SELECT 1;"], release_sha=RELEASE_SHA,
            )
        self.assertEqual(client.mock_calls, [])
        ssh.assert_not_called()

    def test_database_policy_guards_migrations_and_scheduled_checks_keep_runtime(self) -> None:
        desired = postgres.DesiredDatabase(
            "managed", "omnicio", "app", "18", "ru-3", "msk-1", Decimal(1110), 1, 2048, 20480
        )
        cases = [(single, scheduled, rejected) for single in (False, True)
                 for scheduled, rejected in ((False, True), (True, False), (False, False))]
        root = Path(__file__).resolve().parents[2]
        historical = json.loads(
            (root / "tests/fixtures/accepted_upgrade_1_3.json").read_text(encoding="utf-8"),
        )
        reviewed_plan = inplace_upgrade.validate_plan(historical["plan"])
        reviewed = [(root / "migrations" / name).read_text(encoding="utf-8") for name in (
            "0027_assistant_stream_memory.sql", "0028_notification_device_binding.sql",
        )]
        for single, backup_only, rejected in cases:
            with (self.subTest(single=single, scheduled=backup_only, rejected=rejected),
                  ExitStack() as stack):
                client = Mock()
                mocks: dict[str, Any] = {}
                values = {
                    # Only this historical controller scenario admits the frozen
                    # 1.3 plan; real load_plan must still block application 1.4.
                    "load_plan": reviewed_plan,
                    "load_policy": replace(recovery.load_policy(), mode=(
                        recovery.SINGLE_DATABASE_MODE if single else "managed_backups")),
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
                    "run_inplace_upgrade": None,
                    "add_summary": None,
                    "set_output": None,
                    "ensure_recovery_point": None,
                    "inspect_provider_recovery": {"complete": False, "recovery_verified": False},
                    "inspect_restore_capacity": None,
                }
                for name, value in values.items():
                    mocks[name] = stack.enter_context(
                        patch.object(postgres, name, return_value=value)
                    )
                ssh = stack.enter_context(patch.object(postgres, "EphemeralSsh"))
                order = Mock()
                order.attach_mock(mocks["inspect_provider_recovery"], "inspect")
                order.attach_mock(ssh.return_value.__enter__, "ssh")
                order.attach_mock(mocks["ensure_recovery_point"], "guard")
                client.get_vpc_services.return_value = [{}]
                if rejected:
                    mocks["ensure_recovery_point"].side_effect = recovery.RecoveryBlocked("no copy")
                kwargs = dict(
                    desired=desired,
                    server_name="server",
                    server_comment="managed",
                    vpc_name="private",
                    migration_sqls=reviewed if single else ["SELECT 1"],
                    backup_only=backup_only,
                    release_sha=None if backup_only else RELEASE_SHA,
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
                    self.assertEqual(mocks[name].call_count,
                                     int(not single and not backup_only and not rejected))
                self.assertEqual(mocks["run_inplace_upgrade"].call_count,
                                 int(single and not backup_only and not rejected))
                self.assertEqual(mocks["inspect_restore_capacity"].call_count,
                                 int(not single and not rejected))
                self.assertEqual(
                    [entry[0] for entry in order.mock_calls], ["inspect", "ssh", "guard"],
                )
                mocks["inspect_provider_recovery"].assert_called_once_with(client)
                self.assertEqual(
                    mocks["ensure_recovery_point"].call_args.kwargs,
                    {"release_sha": None if backup_only else RELEASE_SHA},
                )
                if rejected:
                    mocks["set_output"].assert_not_called()
                elif backup_only:
                    mocks["set_output"].assert_called_once_with(
                        "status",
                        "single_database_policy_ready" if single else "recovery_point_ready",
                    )
                client.create_database_cluster.assert_not_called()


class ProviderInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        policy = replace(recovery.load_policy(), mode="managed_backups")
        self.policy = patch.object(recovery, "load_policy", return_value=policy)
        self.policy.start()
        self.addCleanup(self.policy.stop)

    def test_metadata_is_get_only_and_never_certifies_recovery(self) -> None:
        provider = Provider()
        provider.schedule = {
            "is_enabled": True, "copy_count": 7, "interval": "day",
            "creation_start_at": "2026-01-01", "url": "credential-canary",
        }
        provider.backups = [backup(1), backup(2, age=25), backup(3, age=-1)]
        with (
            patch.object(recovery, "read_state") as read_state,
            patch.object(recovery, "write_state") as write_state,
        ):
            report = recovery.inspect_provider_recovery(provider)
        self.assertTrue(report["complete"])
        self.assertEqual(report["cluster_id"], CLUSTER_ID)
        self.assertFalse(report["recovery_verified"])
        self.assertFalse(report["restore_verified"])
        self.assertTrue(report["schedule"]["matches_policy"])
        self.assertEqual(
            [item["reason"] for item in report["inventory"]["items"]],
            ["fresh", "stale", "future_timestamp"],
        )
        self.assertEqual(
            [item["backup"]["eligible"] for item in report["details"]["items"]],
            [True, False, False],
        )
        self.assertTrue(all(method == "GET" for method, _ in provider.calls))
        self.assertTrue(all(path.startswith(f"/dbs/{CLUSTER_ID}/") for _, path in provider.calls))
        self.assertNotIn("credential-canary", json.dumps(report))
        read_state.assert_not_called()
        write_state.assert_not_called()

    def test_untrusted_fields_and_malformed_metadata_are_not_printed(self) -> None:
        provider = Provider()
        provider.schedule = {
            "is_enabled": True, "copy_count": "copy-canary", "interval": "interval-canary",
            "creation_start_at": "https://date-canary", "secret_key": "secret-canary",
        }
        provider.backups = [backup() | {
            "status": "status-canary", "type": "type-canary", "size": "size-canary",
            "created_at": "https://created-canary", "comment": "comment-canary",
            "url": "https://download-canary", "access_key": "access-canary",
        }]
        report = recovery.inspect_provider_recovery(provider)
        self.assertNotIn("canary", json.dumps(report))
        self.assertFalse(report["schedule"]["matches_policy"])
        item = report["inventory"]["items"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertEqual(item["comment_classification"], "other")
        self.assertFalse(item["eligible"])
        self.assertIsNone(item["created_at"])

    def test_pending_invalid_size_and_invalid_timestamp_have_explicit_reasons(self) -> None:
        provider = Provider()
        provider.backups = [
            backup(1) | {"status": "create"}, backup(2) | {"size": 0},
            backup(3) | {"created_at": "2026-10-05T01:00:00"},
            backup(4) | {"size": float("nan")}, backup(5) | {"size": 10 ** 1000},
        ]
        report = recovery.inspect_provider_recovery(provider)
        self.assertEqual(
            [item["reason"] for item in report["inventory"]["items"]],
            ["not_completed", "invalid_size", "invalid_timestamp", "invalid_size", "invalid_size"],
        )
        json.dumps(report, allow_nan=False)

    def test_empty_inventory_is_observed_without_creation(self) -> None:
        provider = Provider()
        report = recovery.inspect_provider_recovery(provider)
        self.assertTrue(report["complete"])
        self.assertEqual(report["inventory"]["count"], 0)
        self.assertEqual(report["details"]["items"], [])
        self.assertEqual(len(provider.calls), 2)
        self.assertTrue(all(method == "GET" for method, _ in provider.calls))

    def test_inventory_and_detail_output_are_bounded(self) -> None:
        provider = Provider()
        provider.backups = [backup(index) for index in range(1, 22)]
        report = recovery.inspect_provider_recovery(provider)
        self.assertTrue(report["inventory"]["complete"])
        self.assertEqual(report["inventory"]["count"], 21)
        self.assertEqual(report["inventory"]["returned_count"], 20)
        self.assertTrue(report["inventory"]["truncated"])
        self.assertEqual(len(report["inventory"]["items"]), 20)
        self.assertEqual(len(report["details"]["items"]), 20)
        self.assertFalse(report["details"]["complete"])
        self.assertFalse(report["complete"])
        self.assertEqual(len(provider.calls), 22)

    def test_partial_pages_are_not_claimed_complete_or_used_for_detail_reads(self) -> None:
        for response in (
            {"backups": [backup()], "meta": {"total": 2}},
            {"backups": [backup(), backup()]}, {"backups": [backup()], "meta": ["invalid"]},
        ):
            with self.subTest(response=response):
                provider = Mock()
                provider.request.side_effect = [{"auto_backups_settings": {"is_enabled": False}},
                                                response]
                report = recovery.inspect_provider_recovery(provider)
                self.assertFalse(report["inventory"]["complete"])
                self.assertFalse(report["complete"])
                self.assertEqual(report["details"]["items"], [])
                self.assertEqual(provider.request.call_count, 2)

    def test_provider_errors_are_safe_and_do_not_hide_other_observations(self) -> None:
        provider = Mock()
        provider.request.side_effect = [
            postgres.TimewebApiError(503, "private-canary", "credential-canary"),
            {"backups": [backup()]}, OSError("private-provider-response"),
        ]
        report = recovery.inspect_provider_recovery(provider)
        self.assertFalse(report["complete"])
        self.assertEqual(report["schedule"]["http_status"], 503)
        self.assertTrue(report["inventory"]["complete"])
        self.assertFalse(report["details"]["complete"])
        self.assertNotIn("canary", json.dumps(report))
        self.assertNotIn("private-provider-response", json.dumps(report))
        detail_call = provider.request.call_args
        self.assertEqual(detail_call.args, ("GET", f"/dbs/{CLUSTER_ID}/backups/1"))
        self.assertEqual(detail_call.kwargs, {"timeout": 10})

    def test_inventory_pagination_limit_stops_without_reading_details(self) -> None:
        provider = Mock()
        provider.request.side_effect = [
            {"auto_backups_settings": {"is_enabled": False}},
            *[{"backups": [backup(index) for index in range(offset + 1, offset + 101)]}
              for offset in range(0, 500, 100)],
        ]
        report = recovery.inspect_provider_recovery(provider)
        self.assertFalse(report["inventory"]["complete"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["details"]["items"], [])
        self.assertEqual(provider.request.call_count, 6)
        self.assertEqual(
            provider.request.call_args.args,
            ("GET", f"/dbs/{CLUSTER_ID}/backups?limit=100&offset=400"),
        )

    def test_detail_identity_must_match_and_detail_freshness_is_independent(self) -> None:
        for detail, detail_ok in ((backup(2), False), (backup(1, age=25), True)):
            with self.subTest(detail_ok=detail_ok):
                provider = Mock()
                provider.request.side_effect = [
                    {"auto_backups_settings": {"is_enabled": False}},
                    {"backups": [backup()]}, {"backup": detail},
                ]
                report = recovery.inspect_provider_recovery(provider)
                self.assertTrue(report["inventory"]["items"][0]["eligible"])
                self.assertEqual(report["details"]["complete"], detail_ok)
                if detail_ok:
                    self.assertFalse(report["details"]["items"][0]["backup"]["eligible"])

    def test_comment_tags_are_classified_without_claiming_ownership(self) -> None:
        provider = Provider()
        provider.backups = [
            backup(1), backup(2) | {"comment": recovery.WEEKLY_PREFIX + "2026-10-05"},
            backup(3) | {"comment": ""},
        ]
        report = recovery.inspect_provider_recovery(provider)
        self.assertEqual(
            [item["comment_classification"] for item in report["inventory"]["items"]],
            ["bootstrap_tag", "weekly_tag", "absent"],
        )
        self.assertNotIn(recovery.BOOTSTRAP_COMMENT, json.dumps(report))
        self.assertNotIn(recovery.WEEKLY_PREFIX, json.dumps(report))


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
