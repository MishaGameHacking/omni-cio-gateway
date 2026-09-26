from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from scripts import timeweb_postgres_production_cutover as cutover


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_timeweb_postgres_production_cutover.py"
SPEC = importlib.util.spec_from_file_location(
    "check_v10_timeweb_postgres_production_cutover",
    SCRIPT,
)
assert SPEC is not None
assert SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

WORKFLOW_RELATIVE = Path(
    ".github/workflows/v10-timeweb-postgres-production-cutover.yml"
)

DEPENDENCIES = (
    "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json",
    "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md",
    "scripts/timeweb_postgres_production_cutover.py",
    "apps/api/hosted_runtime.py",
    "apps/api/timeweb_postgres_tls.py",
    WORKFLOW_RELATIVE.as_posix(),
    "infrastructure/postgres/hosted-postgres-runtime-contract.json",
    "infrastructure/postgres/hosted-recovery-contract.json",
)


def _copy(root: Path) -> None:
    for relative in DEPENDENCIES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _contract_path(root: Path) -> Path:
    return root / (
        "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json"
    )


class TimewebPostgresProductionCutoverGuardTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        guard.validate(ROOT)

    def test_prepare_connection_dsns_probes_transport_before_auth(self) -> None:
        ca_path = Path("ca.crt")
        with (
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "install_timeweb_postgres_ca",
                return_value=ca_path,
            ),
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "probe_timeweb_postgres_transport",
                return_value="8.8.8.8",
            ) as probe,
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "resolve_timeweb_postgres_dsn",
                side_effect=["bootstrap-prepared", "runtime-prepared"],
            ) as resolve,
        ):
            actual = cutover._prepare_connection_dsns(
                "bootstrap-dsn",
                "runtime-dsn",
            )

        self.assertEqual(actual, ("bootstrap-prepared", "runtime-prepared"))
        probe.assert_called_once_with("bootstrap-dsn", ca_path)
        self.assertEqual(
            resolve.call_args_list,
            [
                mock.call(
                    "bootstrap-dsn",
                    ca_path,
                    hostaddr="8.8.8.8",
                ),
                mock.call(
                    "runtime-dsn",
                    ca_path,
                    hostaddr="8.8.8.8",
                ),
            ],
        )

    def test_connect_maps_adapter_failure_to_cutover_stop(self) -> None:
        with (
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "connect_prepared_timeweb_postgres",
                side_effect=cutover.timeweb_postgres_tls.TimewebPostgresTlsError(
                    "TIMEWEB_PG_PRODUCTION_BOOTSTRAP_TIMEOUT"
                ),
            ) as connect,
            self.assertRaisesRegex(
                cutover.CutoverStopped,
                "TIMEWEB_PG_PRODUCTION_BOOTSTRAP_TIMEOUT",
            ),
        ):
            cutover._connect(
                "prepared-dsn",
                code="TIMEWEB_PG_PRODUCTION_BOOTSTRAP_CONNECTION_FAILED",
            )

        connect.assert_called_once_with(
            "prepared-dsn",
            failure_prefix="TIMEWEB_PG_PRODUCTION_BOOTSTRAP",
            autocommit=True,
            retry_delays=cutover._PRODUCTION_CONNECT_RETRY_DELAYS,
        )

    def test_observe_is_read_only_and_does_not_require_prepared_schema(self) -> None:
        expected_sha = "a" * 40
        bootstrap = {
            "host": "db.example",
            "port": "5432",
            "dbname": "omni",
            "user": "bootstrap",
        }
        runtime = {
            "host": "db.example",
            "port": "5432",
            "dbname": "omni",
            "user": cutover.RUNTIME_ROLE,
        }
        with (
            mock.patch.object(
                cutover,
                "_dsn",
                side_effect=[
                    ("bootstrap-dsn", bootstrap),
                    ("runtime-dsn", runtime),
                ],
            ),
            mock.patch.object(
                cutover,
                "_prepare_connection_dsns",
                return_value=("bootstrap-connect", "runtime-connect"),
            ) as prepare_dsns,
            mock.patch.object(cutover, "_observe_database") as observe,
            mock.patch.object(cutover, "_prepare_database") as prepare,
            mock.patch.object(cutover, "_verify_runtime_database") as verify_runtime,
        ):
            cutover.run(
                operation="observe",
                expected_sha=expected_sha,
                observed_main_sha=expected_sha,
            )
        prepare_dsns.assert_called_once_with("bootstrap-dsn", "runtime-dsn")
        observe.assert_called_once_with("bootstrap-connect", "runtime-connect")
        prepare.assert_not_called()
        verify_runtime.assert_not_called()

    def test_invalid_operation_stops_before_ca_materialization(self) -> None:
        expected_sha = "a" * 40
        bootstrap = {
            "host": "db.example",
            "port": "5432",
            "dbname": "omni",
            "user": "bootstrap",
        }
        runtime = {
            "host": "db.example",
            "port": "5432",
            "dbname": "omni",
            "user": cutover.RUNTIME_ROLE,
        }
        with (
            mock.patch.object(
                cutover,
                "_dsn",
                side_effect=[
                    ("bootstrap-dsn", bootstrap),
                    ("runtime-dsn", runtime),
                ],
            ),
            mock.patch.object(cutover, "_prepare_connection_dsns") as prepare_dsns,
            self.assertRaisesRegex(
                cutover.CutoverStopped,
                "TIMEWEB_PG_PRODUCTION_OPERATION_INVALID",
            ),
        ):
            cutover.run(
                operation="invalid",
                expected_sha=expected_sha,
                observed_main_sha=expected_sha,
            )
        prepare_dsns.assert_not_called()

    def test_prepare_confirmation_stops_before_ca_materialization(self) -> None:
        expected_sha = "a" * 40
        bootstrap = {
            "host": "db.example",
            "port": "5432",
            "dbname": "omni",
            "user": "bootstrap",
        }
        runtime = {
            "host": "db.example",
            "port": "5432",
            "dbname": "omni",
            "user": cutover.RUNTIME_ROLE,
        }
        with (
            mock.patch.object(
                cutover,
                "_dsn",
                side_effect=[
                    ("bootstrap-dsn", bootstrap),
                    ("runtime-dsn", runtime),
                ],
            ),
            mock.patch.object(cutover, "_prepare_connection_dsns") as prepare_dsns,
            self.assertRaisesRegex(
                cutover.CutoverStopped,
                "TIMEWEB_PG_PRODUCTION_PREPARE_CONFIRMATION_REQUIRED",
            ),
        ):
            cutover.run(
                operation="prepare",
                expected_sha=expected_sha,
                observed_main_sha=expected_sha,
            )
        prepare_dsns.assert_not_called()

    def test_guard_rejects_mutation_in_observe_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            controller = root / "scripts/timeweb_postgres_production_cutover.py"
            source = controller.read_text(encoding="utf-8")
            controller.write_text(
                source.replace(
                    "_verify_runtime_role_identity(runtime)",
                    "apply_migrations(runtime)",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_OBSERVE_MUTATION_PATH",
            ):
                guard.validate(root)

    def test_rejects_nonportable_ca_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["transport"]["canonical_sslrootcert"] = "C:/runner/root.crt"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_TRANSPORT_INVALID",
            ):
                guard.validate(root)

    def test_rejects_disabled_transport_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["transport"]["credential_free_transport_preflight_required"] = False
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_TRANSPORT_INVALID",
            ):
                guard.validate(root)

    def test_rejects_hosted_runtime_without_tls_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / "apps/api/hosted_runtime.py"
            source = path.read_text(encoding="utf-8")
            mutated = source.replace(
                "prepared_dsn = prepare_timeweb_postgres_target("
                "external_database_dsn, ca_path)",
                "prepared_dsn = external_database_dsn",
                1,
            )
            self.assertNotEqual(mutated, source)
            path.write_text(mutated, encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_HOSTED_RUNTIME_TLS_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_synthetic_fixture_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["target"]["synthetic_fixture_promotion_allowed"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_TARGET_INVALID",
            ):
                guard.validate(root)

    def test_rejects_controller_login_creation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runtime_role"]["controller_creates_login"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_WIDENED",
            ):
                guard.validate(root)

    def test_rejects_automatic_workflow_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    "on:\n  workflow_dispatch:",
                    "on:\n  push:\n    branches: [main]\n  workflow_dispatch:",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_AUTO_TRIGGER_FORBIDDEN",
            ):
                guard.validate(root)

    def test_rejects_public_activation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["protected_invariants"]["PUBLIC_MULTI_USER_ENABLED"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_AUTHORITY_WIDENED",
            ):
                guard.validate(root)

    def test_rejects_recovery_attestation_as_actions_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source
                + "\n# ${{ secrets.OMNI_V10_TIMEWEB_PG_RECOVERY_ATTESTATION }}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RECOVERY_ATTESTATION_SECRET_FORBIDDEN",
            ):
                guard.validate(root)

    def test_rejects_provider_token_outside_accept_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding="utf-8")
            marker = (
                "      - name: Observe verified production database\n"
                "        if: ${{ inputs.operation == 'observe' }}\n"
                "        shell: bash\n"
                "        env:\n"
            )
            self.assertIn(marker, source)
            path.write_text(
                source.replace(
                    marker,
                    marker
                    + "          TIMEWEB_CLOUD_API_TOKEN: "
                    + "${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}\n",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_SECRET_SCOPE_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_missing_recovery_evidence_digest_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["recovery"]["recovery_evidence_sha256_required"] = False
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RECOVERY_DRIFT",
            ):
                guard.validate(root)

    def test_contract_keeps_recovery_and_app_promotion_external(self) -> None:
        payload = json.loads(_contract_path(ROOT).read_text(encoding="utf-8"))
        self.assertTrue(payload["recovery"]["timeweb_physical_backup_required"])
        self.assertTrue(payload["recovery"]["separate_restore_rehearsal_required"])
        self.assertTrue(payload["recovery"]["recovery_evidence_sha256_required"])
        self.assertFalse(
            payload["recovery"]["actions_secret_for_recovery_attestation_allowed"]
        )
        self.assertFalse(
            payload["app_binding"]["runtime_dsn_promotion_by_controller_allowed"]
        )
        self.assertFalse(
            payload["app_binding"]["undocumented_timeweb_app_settings_api_allowed"]
        )


if __name__ == "__main__":
    unittest.main()
