from __future__ import annotations

from typing import Any
import unittest
from unittest.mock import patch

import apps.api.cloudflare_runtime as runtime


class _Result:
    def __init__(
        self,
        *,
        one: tuple[Any, ...] | None = None,
        rows: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self._one = one
        self._rows = [] if rows is None else rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._one

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _RuntimeProbeConnection:
    def __init__(self, role: str) -> None:
        self._role = role

    def execute(self, statement: str, params: object = None) -> _Result:
        del params
        if statement == "SHOW server_version_num":
            return _Result(one=("180000",))
        if "FROM pg_catalog.pg_roles" in statement:
            return _Result(
                one=(
                    self._role,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                )
            )
        if "FROM pg_catalog.pg_auth_members" in statement:
            return _Result(one=(0,))
        if "SELECT to_regclass" in statement:
            return _Result(
                one=(
                    "omni_cio_v10.tenants",
                    "omni_cio_v10.users",
                    "omni_cio_v10.web_sessions",
                )
            )
        if "FROM pg_catalog.pg_class" in statement:
            return _Result(
                rows=[
                    ("broker_accounts", True, True),
                    ("broker_connection_accounts", True, True),
                    ("broker_connections", True, True),
                ]
            )
        raise AssertionError(statement)


class CloudflareRuntimeDatabaseRoleTests(unittest.TestCase):
    def test_staging_runtime_role_is_accepted(self) -> None:
        runtime._probe_cloudflare_runtime_database(
            _RuntimeProbeConnection("omni_cio_cloudflare_staging"),
            expected_runtime_role="omni_cio_cloudflare_staging",
        )

    def test_production_runtime_role_is_accepted(self) -> None:
        runtime._probe_cloudflare_runtime_database(
            _RuntimeProbeConnection("omni_cio_cloudflare_prod"),
            expected_runtime_role="omni_cio_cloudflare_prod",
        )

    def test_historical_hosted_role_is_rejected_for_cloudflare(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RUNTIME_DATABASE_ROLE_DRIFT",
        ):
            runtime._probe_cloudflare_runtime_database(
                _RuntimeProbeConnection("omni_cio_hosted_api"),
                expected_runtime_role="omni_cio_cloudflare_staging",
            )

    def test_role_binding_accepts_only_cloudflare_roles(self) -> None:
        for role in (
            "omni_cio_cloudflare_staging",
            "omni_cio_cloudflare_prod",
        ):
            with self.subTest(role=role):
                with patch.dict(
                    runtime.os.environ,
                    {runtime._RUNTIME_ROLE_ENV_NAME: role},
                    clear=True,
                ):
                    self.assertEqual(runtime._runtime_database_role(), role)

    def test_role_binding_missing_fails_closed(self) -> None:
        with patch.dict(runtime.os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "OMNI_V10_POSTGRES_RUNTIME_ROLE_REQUIRED",
            ):
                runtime._runtime_database_role()

    def test_role_binding_historical_role_fails_closed(self) -> None:
        with patch.dict(
            runtime.os.environ,
            {runtime._RUNTIME_ROLE_ENV_NAME: "omni_cio_hosted_api"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_RUNTIME_DATABASE_ROLE_INVALID",
            ):
                runtime._runtime_database_role()

    def test_membership_regression_fails_closed(self) -> None:
        class MembershipConnection(_RuntimeProbeConnection):
            def execute(self, statement: str, params: object = None) -> _Result:
                if "FROM pg_catalog.pg_auth_members" in statement:
                    return _Result(one=(1,))
                return super().execute(statement, params)

        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RUNTIME_DATABASE_MEMBERSHIP_FORBIDDEN",
        ):
            runtime._probe_cloudflare_runtime_database(
                MembershipConnection("omni_cio_cloudflare_staging"),
                expected_runtime_role="omni_cio_cloudflare_staging",
            )

    def test_force_rls_regression_fails_closed(self) -> None:
        class RlsConnection(_RuntimeProbeConnection):
            def execute(self, statement: str, params: object = None) -> _Result:
                if "FROM pg_catalog.pg_class" in statement:
                    return _Result(
                        rows=[
                            ("broker_accounts", True, True),
                            ("broker_connection_accounts", True, False),
                            ("broker_connections", True, True),
                        ]
                    )
                return super().execute(statement, params)

        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RUNTIME_DATABASE_FORCE_RLS_REQUIRED",
        ):
            runtime._probe_cloudflare_runtime_database(
                RlsConnection("omni_cio_cloudflare_prod"),
                expected_runtime_role="omni_cio_cloudflare_prod",
            )


if __name__ == "__main__":
    unittest.main()
