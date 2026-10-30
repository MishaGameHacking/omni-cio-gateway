"""Guard real resource changes with fresh backups, current costs and fixed scope."""
from contextlib import closing
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import resize_local_ai_host as resize
spec = importlib.util.spec_from_file_location("pre_resize_backup", ROOT / "deploy/pre_resize_backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
OBSERVATION = json.loads((Path(__file__).with_name("local_ai_resize_cost_fixture.json")).read_text())
NOW = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)


def receipt():
    return {"status": "backup_verified", "server_id": 9417611, "source_commit": resize.BASE,
        "run_id": "41000000000", "sqlite_integrity": "ok", "source_files": 108,
        "services_enabled": True, "application_changed": False, "observed_at": NOW.isoformat()}


class ResizeTests(unittest.TestCase):
    def test_real_observed_tariff_fits_with_variable_cost_reserve(self):
        result = resize.plan(copy.deepcopy(OBSERVATION))
        self.assertEqual(result["target_base_monthly_estimate_rub"], "7760.00")
        self.assertEqual(result["target_with_unchanged_addons_estimate_rub"], "7960.00")
        self.assertEqual(result["account_conservative_31_day_estimate_rub"], "8399.41")
        self.assertTrue(result["price_is_estimate_not_quote"])
        self.assertFalse(result["disk_changed"])

    def test_unknown_or_changed_hardware_costs_and_tariff_are_blocked(self):
        mutations = [
            lambda x: x["server"].update(cpu=True),
            lambda x: x["server"].update(ram=16384),
            lambda x: x["server"].update(location="ru-4"),
            lambda x: x["server"].update(gpu=1),
            lambda x: x["server"]["disks"][0].update(size_reported=61440),
            lambda x: x["project"]["resource_counts"].update(servers=2),
            lambda x: x["budget"].update(verified=False),
            lambda x: x["budget"].update(conservative_31_day_rub="10000.00"),
            lambda x: x["service_costs"]["target_services"][0].update(base_cost_reported="4361.00"),
            lambda x: x["service_costs"]["target_services"][0].update(including_addons_reported=None),
            lambda x: x["configurator"]["current"]["requirements"].update(ram_max=4096),
            lambda x: x["configurator"]["current"]["requirements"].update(cpu_step=2),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                observation = copy.deepcopy(OBSERVATION)
                mutate(observation)
                with self.assertRaises(RuntimeError):
                    resize.plan(observation)

    def test_dry_plan_cannot_write(self):
        api = Mock()
        with patch.object(resize.inspection, "inspect", return_value=OBSERVATION):
            result = resize.execute(api, None, "41000000000", NOW)
        self.assertFalse(result["patch_sent"])
        api.patch.assert_not_called()

    def test_valid_backup_allows_only_one_fixed_patch(self):
        api = Mock()
        api.patch.return_value = 200
        with patch.object(resize.inspection, "inspect", return_value=OBSERVATION):
            result = resize.execute(api, receipt(), "41000000000", NOW, apply=True)
        api.patch.assert_called_once_with("/api/v1/servers/9417611", {"configurator": {"configurator_id": 153, "cpu": 4, "ram": 8192, "disk": 30720}})
        self.assertEqual(result["status"], "resize_requested")
        self.assertFalse(result["configuration_verified_after_reboot"])

    def test_stale_future_foreign_or_incomplete_backup_never_changes_resources(self):
        changes = [{"observed_at": (NOW - timedelta(seconds=301)).isoformat()},
            {"observed_at": (NOW + timedelta(seconds=1)).isoformat()},
            {"run_id": "41000000001"}, {"source_commit": "old"}, {"sqlite_integrity": "corrupt"},
            {"application_changed": True}, {"services_enabled": False}]
        for change in changes:
            with self.subTest(change=change):
                evidence = {**receipt(), **change}
                api = Mock()
                with patch.object(resize.inspection, "inspect", return_value=OBSERVATION), self.assertRaises(RuntimeError):
                    resize.execute(api, evidence, "41000000000", NOW, apply=True)
                api.patch.assert_not_called()

    def test_ambiguous_request_has_no_automatic_retry(self):
        api = Mock()
        api.patch.side_effect = RuntimeError("resize_outcome_unknown_read_provider_state_before_retry")
        with patch.object(resize.inspection, "inspect", return_value=OBSERVATION), self.assertRaisesRegex(RuntimeError, "outcome_unknown"):
            resize.execute(api, receipt(), "41000000000", NOW, apply=True)
        self.assertEqual(api.patch.call_count, 1)

    def test_patch_disallows_other_server_disk_os_and_create_actions(self):
        api = resize.ResizeAPI("test-not-real-token")
        api._opener = Mock()
        for path, body in [("/api/v1/servers/2", {"configurator": resize.TARGET}),
            (resize.PATH, {"configurator": {**resize.TARGET, "disk": 61440}}),
            (resize.PATH, {"configurator": resize.TARGET, "os_id": 1})]:
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "scope_invalid"):
                api.patch(path, body)
        api._opener.open.assert_not_called()

    def test_existing_target_is_idempotent_without_another_patch(self):
        observed = copy.deepcopy(OBSERVATION)
        observed["server"].update(cpu=4, ram=8192)
        observed["service_costs"]["target_services"][0].update(base_cost_reported="7760.00", including_addons_reported="7960.00", configuration={"cpu":4,"ram":8,"disk":30})
        observed["budget"].update(reported_monthly_cost_rub="7960", reported_monthly_fee_rub="7960", conservative_31_day_rub="8092")
        api = Mock()
        with patch.object(resize.inspection, "inspect", return_value=observed):
            result = resize.execute(api, None, "41000000000", NOW, apply=True)
        self.assertEqual(result["status"], "already_sized")
        api.patch.assert_not_called()


class BackupTests(unittest.TestCase):
    def test_wal_backup_is_complete_private_and_does_not_restore_live_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database, saved = root / "live.db", root / "saved.db"
            with closing(sqlite3.connect(database)) as live:
                live.execute("PRAGMA journal_mode=WAL")
                live.execute("CREATE TABLE evidence(value TEXT)")
                live.execute("INSERT INTO evidence VALUES ('committed fact')")
                live.commit()
                backup.snapshot(database, saved)
                live.execute("INSERT INTO evidence VALUES ('later fact')")
                live.commit()
                self.assertEqual(live.execute("SELECT count(*) FROM evidence").fetchone()[0], 2)
            with closing(sqlite3.connect(saved)) as restored:
                self.assertEqual(restored.execute("SELECT value FROM evidence").fetchall(), [("committed fact",)])
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)

    def test_existing_file_and_symlink_destinations_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "sentinel"
            sentinel.write_text("preserve")
            link = root / "link"
            link.symlink_to(sentinel)
            for destination in (sentinel, link):
                with self.subTest(destination=destination), self.assertRaisesRegex(RuntimeError, "destination_exists"):
                    backup.snapshot(root / "absent.db", destination)
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_private_credential_copy_is_not_world_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "configuration"
            backup.private_file(target, b"synthetic-only")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                backup.private_file(target, b"replacement")


if __name__ == "__main__":
    unittest.main()
