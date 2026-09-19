from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import check_v10_ru_postgres_data_residency_migration as guard


_SINGLE_FILES = (
    guard.CONTRACT,
    guard.AMENDMENT,
    guard.INDEX,
    guard.PLATFORM_CONTRACT,
    guard.LEGAL_GATES,
    guard.WRANGLER,
    guard.RUNTIME_SQL,
    guard.NEON_RUNTIME,
)


def _copy_fixture(root: Path) -> None:
    for source in _SINGLE_FILES:
        relative = source.relative_to(guard.ROOT)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    migrations = root / guard.MIGRATIONS.relative_to(guard.ROOT)
    migrations.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(guard.MIGRATIONS, migrations)


class RuPostgresDataResidencyMigrationTests(unittest.TestCase):
    def test_current_repository_contract_is_valid(self) -> None:
        guard.validate()

    def test_minimum_tier_cannot_be_silently_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT.relative_to(guard.ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["candidate"]["minimum_1cpu_1gb_8gb_tier_accepted"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "RU_POSTGRES_CANDIDATE_INVALID",
            ):
                guard.validate(root)

    def test_execution_order_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT.relative_to(guard.ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["execution_sequence"][1:3] = list(
                reversed(payload["execution_sequence"][1:3])
            )
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "RU_POSTGRES_SEQUENCE_INVALID",
            ):
                guard.validate(root)

    def test_application_migrations_must_stay_provider_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = (
                root
                / guard.MIGRATIONS.relative_to(guard.ROOT)
                / "0005_browser_bound_provider_auth.sql"
            )
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source + "\n-- timeweb provider coupling\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "RU_POSTGRES_MIGRATION_PROVIDER_COUPLING",
            ):
                guard.validate(root)

    def test_runtime_force_rls_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.RUNTIME_SQL.relative_to(guard.ROOT)
            source = path.read_text(encoding="utf-8").replace(
                "FORCE ROW LEVEL SECURITY",
                "ENABLE ROW LEVEL SECURITY",
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "RU_POSTGRES_RUNTIME_BOUNDARY_DRIFT",
            ):
                guard.validate(root)

    def test_public_activation_cannot_hitchhike_on_database_migration(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.WRANGLER.relative_to(guard.ROOT)
            source = path.read_text(encoding="utf-8").replace(
                '"PUBLIC_MULTI_USER_ENABLED": "false"',
                '"PUBLIC_MULTI_USER_ENABLED": "true"',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "RU_POSTGRES_PRODUCTION_FLAGS_INVALID",
            ):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
