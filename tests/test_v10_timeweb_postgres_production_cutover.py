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
NETWORK_SCOPE_RELATIVE = Path("scripts/timeweb_postgres_production_network_scope.py")
TRANSPORT_KEY = "transport"
TRANSPORT_INVALID = "TIMEWEB_PG_CUTOVER_TRANSPORT_INVALID"
TEXT_ENCODING = "utf-8"
BOOTSTRAP_DSN = "bootstrap-dsn"
RUNTIME_DSN = "runtime-dsn"
DB_HOST = "db.example"
DBNAME_KEY = "dbname"
RECOVERY_KEY = "recovery"
HOSTED_RUNTIME_RELATIVE = "apps/api/hosted_runtime.py"
VERIFIED_HOSTADDR = "8.8.8.8"
PRIVATE_HOSTADDR = ".".join(("10", "23", "42", "10"))
PRIVATE_NETWORK_CIDR = ".".join(("10", "23", "42", "0")) + "/24"
BOOTSTRAP_USER = "bootstrap"
PREPARE_CONNECTION_DSNS_NAME = "_prepare_connection_dsns"

DEPENDENCIES = (
    "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json",
    "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md",
    "scripts/timeweb_postgres_production_cutover.py",
    HOSTED_RUNTIME_RELATIVE,
    "apps/api/timeweb_postgres_tls.py",
    NETWORK_SCOPE_RELATIVE.as_posix(),
    "scripts/discover_v10_ru_pg_verifier_ipv4.py",
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
                return_value=VERIFIED_HOSTADDR,
            ) as probe,
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "resolve_timeweb_postgres_dsn",
                side_effect=["bootstrap-prepared", "runtime-prepared"],
            ) as resolve,
        ):
            actual = cutover._prepare_connection_dsns(
                BOOTSTRAP_DSN,
                RUNTIME_DSN,
            )

        self.assertEqual(actual, ("bootstrap-prepared", "runtime-prepared"))
        probe.assert_called_once_with(BOOTSTRAP_DSN, ca_path)
        self.assertEqual(
            resolve.call_args_list,
            [
                mock.call(
                    BOOTSTRAP_DSN,
                    ca_path,
                    hostaddr=VERIFIED_HOSTADDR,
                ),
                mock.call(
                    RUNTIME_DSN,
                    ca_path,
                    hostaddr=VERIFIED_HOSTADDR,
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
            "host": DB_HOST,
            "port": "5432",
            DBNAME_KEY: "omni",
            "user": BOOTSTRAP_USER,
        }
        runtime = {
            "host": DB_HOST,
            "port": "5432",
            DBNAME_KEY: "omni",
            "user": cutover.RUNTIME_ROLE,
        }
        with (
            mock.patch.object(
                cutover,
                "_dsn",
                side_effect=[
                    (BOOTSTRAP_DSN, bootstrap),
                    (RUNTIME_DSN, runtime),
                ],
            ),
            mock.patch.object(
                cutover,
                PREPARE_CONNECTION_DSNS_NAME,
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
        prepare_dsns.assert_called_once_with(BOOTSTRAP_DSN, RUNTIME_DSN)
        observe.assert_called_once_with("bootstrap-connect", "runtime-connect")
        prepare.assert_not_called()
        verify_runtime.assert_not_called()

    def test_invalid_operation_stops_before_ca_materialization(self) -> None:
        expected_sha = "a" * 40
        bootstrap = {
            "host": DB_HOST,
            "port": "5432",
            DBNAME_KEY: "omni",
            "user": BOOTSTRAP_USER,
        }
        runtime = {
            "host": DB_HOST,
            "port": "5432",
            DBNAME_KEY: "omni",
            "user": cutover.RUNTIME_ROLE,
        }
        with (
            mock.patch.object(
                cutover,
                "_dsn",
                side_effect=[
                    (BOOTSTRAP_DSN, bootstrap),
                    (RUNTIME_DSN, runtime),
                ],
            ),
            mock.patch.object(cutover, PREPARE_CONNECTION_DSNS_NAME) as prepare_dsns,
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
            "host": DB_HOST,
            "port": "5432",
            DBNAME_KEY: "omni",
            "user": BOOTSTRAP_USER,
        }
        runtime = {
            "host": DB_HOST,
            "port": "5432",
            DBNAME_KEY: "omni",
            "user": cutover.RUNTIME_ROLE,
        }
        with (
            mock.patch.object(
                cutover,
                "_dsn",
                side_effect=[
                    (BOOTSTRAP_DSN, bootstrap),
                    (RUNTIME_DSN, runtime),
                ],
            ),
            mock.patch.object(cutover, PREPARE_CONNECTION_DSNS_NAME) as prepare_dsns,
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

    def test_p3_app_identity_accepts_timeweb_url_connection_metadata(self) -> None:
        row = {
            "name": cutover.app_release.CANONICAL_APP_NAME,
            "repository": {
                "full_name": (
                    "provider-account/" + cutover.app_release.CANONICAL_REPOSITORY
                ),
                "name": (
                    "provider-display/" + cutover.app_release.CANONICAL_REPOSITORY_NAME
                ),
                "url": (
                    f"https://github.com/{cutover.app_release.CANONICAL_REPOSITORY}.git"
                ),
            },
        }

        self.assertTrue(cutover._is_canonical_app_row(row))

        row["repository"]["url"] = "https://github.com/MishaGameHacking/other.git"
        self.assertFalse(cutover._is_canonical_app_row(row))

    def test_guard_rejects_p3_app_repository_identity_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            controller = root / "scripts/timeweb_postgres_production_cutover.py"
            source = controller.read_text(encoding=TEXT_ENCODING)
            mutated = source.replace(
                "and app_release.is_canonical_repository(value)",
                "and True",
                1,
            )
            self.assertNotEqual(mutated, source)
            controller.write_text(mutated, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_APP_REPOSITORY_IDENTITY_DRIFT",
            ):
                guard.validate(root)

    def test_app_binding_revalidates_private_database_route(self) -> None:
        expected_sha = "a" * 40
        binding_sha256 = "b" * 64
        envs = {
            cutover.app_release.POSTGRES_DSN_ENV: RUNTIME_DSN,
            cutover.app_release.POSTGRES_BINDING_SHA256_ENV: binding_sha256,
            cutover.app_release.RELEASE_SHA_ENV: expected_sha,
            cutover.app_release.PUBLIC_MULTI_USER_ENV: "false",
            cutover.app_release.TELEGRAM_LOGIN_ENV: "false",
            cutover.app_release.POSTGRES_PRIVATE_HOSTADDR_ENV: PRIVATE_HOSTADDR,
            cutover.app_release.POSTGRES_PRIVATE_NETWORK_CIDR_ENV: PRIVATE_NETWORK_CIDR,
        }
        api = object()
        with (
            mock.patch.dict(
                cutover.os.environ,
                {cutover.app_release.TOKEN_ENV: "token"},
                clear=False,
            ),
            mock.patch.object(
                cutover.app_release,
                "TimewebAppApi",
                return_value=api,
            ),
            mock.patch.object(cutover, "_app_envs", return_value=envs),
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "timeweb_postgres_binding_sha256",
                return_value=binding_sha256,
            ),
            mock.patch.object(
                cutover.app_release,
                "validate_private_route_env",
            ) as validate_private_route,
            mock.patch.object(cutover.app_release, "observe") as observe,
        ):
            cutover._verify_app_binding(expected_sha, RUNTIME_DSN)

        validate_private_route.assert_called_once_with(envs)
        observe.assert_called_once_with(
            api,
            expected_sha,
            runtime_mode=cutover.app_release.RUNTIME_MODE_PREACTIVATION,
        )

    def test_app_binding_accepts_provider_masked_dsn_with_exact_digest(self) -> None:
        expected_sha = "a" * 40
        binding_sha256 = "c" * 64
        envs = {
            cutover.app_release.POSTGRES_DSN_ENV: (
                cutover.app_release.TIMEWEB_HIDDEN_BY_API_KEY_POLICY
            ),
            cutover.app_release.POSTGRES_BINDING_SHA256_ENV: binding_sha256,
            cutover.app_release.RELEASE_SHA_ENV: expected_sha,
            cutover.app_release.PUBLIC_MULTI_USER_ENV: "false",
            cutover.app_release.TELEGRAM_LOGIN_ENV: "false",
            cutover.app_release.POSTGRES_PRIVATE_HOSTADDR_ENV: PRIVATE_HOSTADDR,
            cutover.app_release.POSTGRES_PRIVATE_NETWORK_CIDR_ENV: PRIVATE_NETWORK_CIDR,
        }
        api = object()
        with (
            mock.patch.dict(
                cutover.os.environ,
                {cutover.app_release.TOKEN_ENV: "token"},
                clear=False,
            ),
            mock.patch.object(cutover.app_release, "TimewebAppApi", return_value=api),
            mock.patch.object(cutover, "_app_envs", return_value=envs),
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "timeweb_postgres_binding_sha256",
                return_value=binding_sha256,
            ),
            mock.patch.object(cutover.app_release, "validate_private_route_env"),
            mock.patch.object(cutover.app_release, "observe") as observe,
        ):
            cutover._verify_app_binding(expected_sha, RUNTIME_DSN)

        observe.assert_called_once()

    def test_app_binding_rejects_masked_dsn_with_wrong_digest(self) -> None:
        expected_sha = "a" * 40
        envs = {
            cutover.app_release.POSTGRES_DSN_ENV: (
                cutover.app_release.TIMEWEB_HIDDEN_BY_API_KEY_POLICY
            ),
            cutover.app_release.POSTGRES_BINDING_SHA256_ENV: "d" * 64,
            cutover.app_release.RELEASE_SHA_ENV: expected_sha,
            cutover.app_release.PUBLIC_MULTI_USER_ENV: "false",
            cutover.app_release.TELEGRAM_LOGIN_ENV: "false",
            cutover.app_release.POSTGRES_PRIVATE_HOSTADDR_ENV: PRIVATE_HOSTADDR,
            cutover.app_release.POSTGRES_PRIVATE_NETWORK_CIDR_ENV: PRIVATE_NETWORK_CIDR,
        }
        with (
            mock.patch.dict(
                cutover.os.environ,
                {cutover.app_release.TOKEN_ENV: "token"},
                clear=False,
            ),
            mock.patch.object(
                cutover.app_release, "TimewebAppApi", return_value=object()
            ),
            mock.patch.object(cutover, "_app_envs", return_value=envs),
            mock.patch.object(
                cutover.timeweb_postgres_tls,
                "timeweb_postgres_binding_sha256",
                return_value="e" * 64,
            ),
            mock.patch.object(cutover.app_release, "validate_private_route_env"),
            self.assertRaisesRegex(
                cutover.CutoverStopped,
                "TIMEWEB_PG_PRODUCTION_APP_BINDING_SHA256_DRIFT",
            ),
        ):
            cutover._verify_app_binding(expected_sha, RUNTIME_DSN)

    def test_guard_rejects_mutation_in_observe_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            controller = root / "scripts/timeweb_postgres_production_cutover.py"
            source = controller.read_text(encoding=TEXT_ENCODING)
            controller.write_text(
                source.replace(
                    "_verify_runtime_role_identity(runtime)",
                    "apply_migrations(runtime)",
                    1,
                ),
                encoding=TEXT_ENCODING,
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
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[TRANSPORT_KEY]["canonical_sslrootcert"] = "C:/runner/root.crt"
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                TRANSPORT_INVALID,
            ):
                guard.validate(root)

    def test_rejects_disabled_transport_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[TRANSPORT_KEY]["credential_free_transport_preflight_required"] = (
                False
            )
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                TRANSPORT_INVALID,
            ):
                guard.validate(root)

    def test_rejects_authenticated_transport_control_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[TRANSPORT_KEY]["authenticated_libpq_gss_encryption_allowed"] = True
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                TRANSPORT_INVALID,
            ):
                guard.validate(root)

    def test_rejects_app_binding_without_private_route_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            controller = root / "scripts/timeweb_postgres_production_cutover.py"
            source = controller.read_text(encoding=TEXT_ENCODING)
            mutated = source.replace(
                "    app_release.validate_private_route_env(envs)\n",
                "",
                1,
            )
            self.assertNotEqual(mutated, source)
            controller.write_text(mutated, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_CONTROLLER_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_app_binding_without_live_candidate_route_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            controller = root / "scripts/timeweb_postgres_production_cutover.py"
            source = controller.read_text(encoding=TEXT_ENCODING)
            mutated = source.replace(
                "    app_release.observe(\n",
                "    # candidate observation intentionally removed\n",
                1,
            )
            self.assertNotEqual(mutated, source)
            controller.write_text(mutated, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_CONTROLLER_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_app_creation_before_p3_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload["orchestration"]["prepare_must_complete_before_app_creation"] = (
                False
            )
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_ORCHESTRATION_INVALID",
            ):
                guard.validate(root)

    def test_rejects_p3_accept_before_physical_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload["orchestration"]["accept_before_physical_candidate_allowed"] = True
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_ORCHESTRATION_INVALID",
            ):
                guard.validate(root)

    def test_rejects_private_route_firewall_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload["app_binding"][
                "runtime_private_route_firewall_dependency_allowed"
            ] = True
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_APP_BINDING_INVALID",
            ):
                guard.validate(root)

    def test_rejects_hosted_runtime_eager_ca_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / HOSTED_RUNTIME_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            eager_source = source.replace(
                "database_ca = _LazyTimewebPostgresCa()",
                "database_ca = install_timeweb_postgres_ca()",
                1,
            ).replace(
                "database_ca.resolve()",
                "database_ca",
                1,
            )
            self.assertNotEqual(eager_source, source)
            path.write_text(eager_source, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_HOSTED_RUNTIME_TLS_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_hosted_runtime_without_tls_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / HOSTED_RUNTIME_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            mutated = source.replace(
                "prepared_dsn = prepare_timeweb_postgres_private_target(",
                "prepared_dsn = prepare_timeweb_postgres_target(",
                1,
            )
            self.assertNotEqual(mutated, source)
            path.write_text(mutated, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_HOSTED_RUNTIME_TLS_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_hosted_runtime_without_private_route_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / HOSTED_RUNTIME_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            mutated = source.replace(
                "private_network_cidr=private_network_cidr,",
                "private_network_cidr=None,",
                1,
            )
            self.assertNotEqual(mutated, source)
            path.write_text(mutated, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_HOSTED_RUNTIME_TLS_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_hosted_runtime_direct_unprepared_connector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / HOSTED_RUNTIME_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            marker = "raw_connection = connect_prepared_timeweb_postgres("
            self.assertIn(marker, source)
            mutated = source.replace(
                marker,
                "raw_connection = connect_postgres(",
                1,
            )
            self.assertNotEqual(mutated, source)
            path.write_text(mutated, encoding=TEXT_ENCODING)
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
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload["target"]["synthetic_fixture_promotion_allowed"] = True
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
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
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload["runtime_role"]["controller_creates_login"] = True
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
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
            source = path.read_text(encoding=TEXT_ENCODING)
            path.write_text(
                source.replace(
                    "on:\n  workflow_dispatch:",
                    "on:\n  push:\n    branches: [main]\n  workflow_dispatch:",
                ),
                encoding=TEXT_ENCODING,
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
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload["protected_invariants"]["PUBLIC_MULTI_USER_ENABLED"] = True
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
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
            source = path.read_text(encoding=TEXT_ENCODING)
            path.write_text(
                source
                + "\n# ${{ secrets.OMNI_V10_TIMEWEB_PG_RECOVERY_ATTESTATION }}\n",
                encoding=TEXT_ENCODING,
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RECOVERY_ATTESTATION_SECRET_FORBIDDEN",
            ):
                guard.validate(root)

    def test_rejects_provider_token_outside_network_preflight_or_accept_scope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
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
                encoding=TEXT_ENCODING,
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_SECRET_SCOPE_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_missing_network_scope_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            mutated = source.replace(
                "python -m scripts.timeweb_postgres_production_network_scope",
                "python -m scripts.timeweb_postgres_production_cutover",
                1,
            )
            self.assertNotEqual(mutated, source)
            path.write_text(mutated, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_network_scope_after_database_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            network = "Verify production network scope before database authentication"
            observe = "Observe verified production database"
            self.assertIn(network, source)
            self.assertIn(observe, source)
            source = source.replace(network, "__NETWORK_SCOPE_STEP__", 1)
            source = source.replace(observe, network, 1)
            source = source.replace("__NETWORK_SCOPE_STEP__", observe, 1)
            path.write_text(source, encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_NETWORK_SCOPE_ORDER_INVALID",
            ):
                guard.validate(root)

    def test_rejects_network_scope_mutation_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / NETWORK_SCOPE_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            path.write_text(
                source
                + "\n\ndef _forbidden_network_mutation(provider: object) -> None:\n"
                + "    provider.patch('/api/v1/databases/1')\n",
                encoding=TEXT_ENCODING,
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_NETWORK_SCOPE_MUTATION_FORBIDDEN",
            ):
                guard.validate(root)

    def test_rejects_provider_network_concurrency_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            path.write_text(
                source.replace(
                    "group: v10-timeweb-postgres-public-ipv4-tls",
                    "group: v10-timeweb-postgres-production-cutover",
                    1,
                ),
                encoding=TEXT_ENCODING,
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_network_scope_stability_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[TRANSPORT_KEY]["provider_network_scope_stability_passes"] = 1
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                TRANSPORT_INVALID,
            ):
                guard.validate(root)

    def test_rejects_floating_ip_list_detail_contract_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[TRANSPORT_KEY]["public_ipv4_list_detail_consistency_required"] = (
                False
            )
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                TRANSPORT_INVALID,
            ):
                guard.validate(root)

    def test_rejects_database_project_identity_contract_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[TRANSPORT_KEY][
                "provider_network_scope_project_identity_required"
            ] = False
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                TRANSPORT_INVALID,
            ):
                guard.validate(root)

    def test_rejects_missing_network_scope_stability_witness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / NETWORK_SCOPE_RELATIVE
            source = path.read_text(encoding=TEXT_ENCODING)
            path.write_text(
                source.replace(
                    "TIMEWEB_PG_PRODUCTION_NETWORK_SNAPSHOT_DRIFT",
                    "TIMEWEB_PG_PRODUCTION_NETWORK_STATE_CHANGED",
                ),
                encoding=TEXT_ENCODING,
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_NETWORK_SCOPE_SOURCE_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_missing_recovery_evidence_digest_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding=TEXT_ENCODING))
            payload[RECOVERY_KEY]["recovery_evidence_sha256_required"] = False
            path.write_text(json.dumps(payload), encoding=TEXT_ENCODING)
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RECOVERY_DRIFT",
            ):
                guard.validate(root)

    def test_contract_keeps_recovery_and_app_promotion_external(self) -> None:
        payload = json.loads(_contract_path(ROOT).read_text(encoding=TEXT_ENCODING))
        self.assertTrue(payload[RECOVERY_KEY]["timeweb_physical_backup_required"])
        self.assertTrue(payload[RECOVERY_KEY]["separate_restore_rehearsal_required"])
        self.assertTrue(payload[RECOVERY_KEY]["recovery_evidence_sha256_required"])
        self.assertFalse(
            payload[RECOVERY_KEY]["actions_secret_for_recovery_attestation_allowed"]
        )
        self.assertFalse(
            payload["app_binding"]["runtime_dsn_promotion_by_controller_allowed"]
        )
        self.assertFalse(
            payload["app_binding"]["undocumented_timeweb_app_settings_api_allowed"]
        )


if __name__ == "__main__":
    unittest.main()
