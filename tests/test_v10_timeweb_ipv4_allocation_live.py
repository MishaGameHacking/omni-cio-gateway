from __future__ import annotations

import argparse
import copy
from unittest import mock
import unittest

from scripts import probe_v10_timeweb_postgres_control_plane as read_only
from scripts import run_v10_timeweb_ipv4_allocation as runner
from scripts import timeweb_ipv4_allocation as allocation
from scripts import timeweb_ipv4_allocation_provider as provider


class _ReadApi:
    def __init__(self, payloads: dict[str, object]) -> None:
        self._payloads = payloads
        self.calls: list[str] = []

    def get(self, path: str, *, timeout: float = 30.0) -> object:
        del timeout
        self.calls.append(path)
        value = self._payloads[path]
        if isinstance(value, BaseException):
            raise value
        return copy.deepcopy(value)


class _MutationApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def mutate_once(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        body: dict[str, object] | None = None,
        expected_statuses: frozenset[int],
        reconcile_statuses: frozenset[int] = frozenset(),
        timeout: float = 30.0,
    ) -> object:
        del timeout
        self.calls.append(
            (
                method,
                path,
                {
                    "operation": operation,
                    "body": body,
                    "expected_statuses": expected_statuses,
                    "reconcile_statuses": reconcile_statuses,
                },
            )
        )
        return {"ip": {}}


def _floating_row(comment: str = "") -> dict[str, object]:
    return {
        "id": "float-1",
        "ip": "8.8.8.8",
        "availability_zone": allocation.ZONE,
        "is_ddos_guard": False,
        "resource_type": None,
        "resource_id": None,
        "comment": comment,
        "ptr": "",
    }


def _provider_payloads(comment: str = "") -> dict[str, object]:
    row = _floating_row(comment)
    return {
        "/api/v1/projects": {
            "projects": [
                {
                    "id": "project-1",
                    "account_id": "account-1",
                    "name": provider.TARGET_PROJECT_NAME,
                }
            ],
            "meta": {"total": 1},
        },
        "/api/v1/projects/project-1/resources/databases": {
            "databases": [{"id": 123, "name": allocation.TARGET_NAME}],
            "meta": {"total": 1},
        },
        "/api/v1/databases/123": {
            "db": {
                "id": 123,
                "name": allocation.TARGET_NAME,
                "location": provider.TARGET_LOCATION,
                "availability_zone": allocation.ZONE,
                "cpu": provider.TARGET_CPU,
                "ram": provider.TARGET_RAM_MB,
                "status": "started",
                "is_autobackups_enabled": False,
                "is_backup_schedule_enabled": False,
                "port": provider.POSTGRES_PORT,
                "disk": {"size": provider.TARGET_DISK_KB},
                "disk_autoscaling": {"is_enabled": False},
                "replica_list": [{"db_id": 123}],
                "is_enabled_public_network": False,
                "is_enabled_public_ipv6": False,
                "project_id": "project-1",
            }
        },
        "/api/v1/floating-ips": {"ips": [row], "meta": {"total": 1}},
        "/api/v1/floating-ips/float-1": {"ip": row},
    }


def _snapshot(comment: str = "") -> allocation.Snapshot:
    return allocation.Snapshot(
        account_scope="account-1",
        project_id="project-1",
        cluster_id=123,
        floating_id="float-1",
        ip_address="8.8.8.8",
        comment=comment,
    )


class TimewebAllocationProviderTests(unittest.TestCase):
    def test_snapshot_reads_complete_exact_state(self) -> None:
        api = _ReadApi(_provider_payloads())
        adapter = provider.TimewebAllocationProvider(api)

        observed = adapter.snapshot()

        self.assertEqual(observed, _snapshot())
        self.assertEqual(
            api.calls,
            [
                "/api/v1/projects",
                "/api/v1/projects/project-1/resources/databases",
                "/api/v1/databases/123",
                "/api/v1/floating-ips",
                "/api/v1/floating-ips/float-1",
            ],
        )

    def test_transport_snapshot_accepts_exact_target_bound_public_state(self) -> None:
        payloads = _provider_payloads(allocation.expected_marker(_snapshot()))
        inventory = payloads["/api/v1/floating-ips"]
        assert isinstance(inventory, dict)
        rows = inventory["ips"]
        assert isinstance(rows, list)
        row = rows[0]
        assert isinstance(row, dict)
        row["resource_type"] = "dbaas"
        row["resource_id"] = "123"
        payloads["/api/v1/floating-ips/float-1"] = {"ip": copy.deepcopy(row)}
        cluster = payloads["/api/v1/databases/123"]
        assert isinstance(cluster, dict)
        db = cluster["db"]
        assert isinstance(db, dict)
        db["is_enabled_public_network"] = True
        adapter = provider.TimewebAllocationProvider(_ReadApi(payloads))

        observed = adapter.transport_snapshot()

        self.assertEqual(observed.resource_type, "dbaas")
        self.assertEqual(observed.resource_id, "123")
        self.assertTrue(observed.public_enabled)
        with self.assertRaisesRegex(
            provider.ProviderStopped,
            "TIMEWEB_ALLOCATION_SNAPSHOT_INVALID",
        ):
            adapter.snapshot()

    def test_snapshot_rejects_list_detail_drift(self) -> None:
        payloads = _provider_payloads()
        detail = copy.deepcopy(payloads["/api/v1/floating-ips/float-1"])
        assert isinstance(detail, dict)
        assert isinstance(detail["ip"], dict)
        detail["ip"]["comment"] = "foreign"
        payloads["/api/v1/floating-ips/float-1"] = detail
        adapter = provider.TimewebAllocationProvider(_ReadApi(payloads))

        with self.assertRaisesRegex(
            provider.ProviderStopped,
            "TIMEWEB_ALLOCATION_IPV4_LIST_DETAIL_DRIFT",
        ):
            adapter.snapshot()

    def test_snapshot_rejects_existing_ptr_metadata(self) -> None:
        payloads = _provider_payloads()
        inventory_payload = payloads["/api/v1/floating-ips"]
        assert isinstance(inventory_payload, dict)
        rows = inventory_payload["ips"]
        assert isinstance(rows, list)
        row = copy.deepcopy(rows[0])
        assert isinstance(row, dict)
        row["ptr"] = "ptr.example.invalid"
        payloads["/api/v1/floating-ips"] = {"ips": [row], "meta": {"total": 1}}
        payloads["/api/v1/floating-ips/float-1"] = {"ip": row}
        adapter = provider.TimewebAllocationProvider(_ReadApi(payloads))

        with self.assertRaisesRegex(
            provider.ProviderStopped,
            "TIMEWEB_ALLOCATION_IPV4_PTR_PRESENT",
        ):
            adapter.snapshot()

    def test_snapshot_rejects_boolean_or_fractional_cpu(self) -> None:
        for value in (True, 1.5):
            payloads = _provider_payloads()
            cluster = payloads["/api/v1/databases/123"]
            assert isinstance(cluster, dict)
            row = cluster["db"]
            assert isinstance(row, dict)
            row["cpu"] = value
            adapter = provider.TimewebAllocationProvider(_ReadApi(payloads))

            with self.subTest(value=value), self.assertRaisesRegex(
                provider.ProviderStopped,
                "TIMEWEB_ALLOCATION_CLUSTER_CPU_INVALID",
            ):
                adapter.snapshot()

    def test_snapshot_uses_project_account_scope_not_cluster_account_field(self) -> None:
        payloads = _provider_payloads()
        cluster = payloads["/api/v1/databases/123"]
        assert isinstance(cluster, dict)
        row = cluster["db"]
        assert isinstance(row, dict)
        self.assertNotIn("account_id", row)

        observed = provider.TimewebAllocationProvider(_ReadApi(payloads)).snapshot()

        self.assertEqual(observed.account_scope, "account-1")
        self.assertEqual(observed.project_id, "project-1")

    def test_snapshot_rejects_cluster_project_drift(self) -> None:
        payloads = _provider_payloads()
        cluster = payloads["/api/v1/databases/123"]
        assert isinstance(cluster, dict)
        row = cluster["db"]
        assert isinstance(row, dict)
        row["project_id"] = "project-2"

        with self.assertRaisesRegex(
            provider.ProviderStopped,
            "TIMEWEB_ALLOCATION_CLUSTER_PROJECT_DRIFT",
        ):
            provider.TimewebAllocationProvider(_ReadApi(payloads)).snapshot()

    def test_provider_stop_is_a_sanitized_protocol_stop(self) -> None:
        self.assertTrue(
            issubclass(provider.ProviderStopped, allocation.AllocationStopped)
        )

    def test_comment_writer_is_one_exact_patch(self) -> None:
        mutation = _MutationApi()
        adapter = provider.TimewebAllocationProvider(
            _ReadApi(_provider_payloads()),
            mutation,
        )
        marker = allocation.expected_marker(_snapshot())

        adapter.write_comment_once("float-1", marker)

        self.assertEqual(len(mutation.calls), 1)
        method, path, kwargs = mutation.calls[0]
        self.assertEqual(method, "PATCH")
        self.assertEqual(path, "/api/v1/floating-ips/float-1")
        self.assertEqual(kwargs["operation"], "FLOATING_IP_ALLOCATION_COMMENT_PATCH")
        self.assertEqual(kwargs["body"], {"comment": marker})
        self.assertEqual(kwargs["expected_statuses"], frozenset({200}))
        self.assertEqual(kwargs["reconcile_statuses"], frozenset({409, 423}))

    def test_comment_writer_rejects_nonempty_existing_comment_without_mutation(
        self,
    ) -> None:
        mutation = _MutationApi()
        adapter = provider.TimewebAllocationProvider(
            _ReadApi(_provider_payloads("foreign")),
            mutation,
        )
        marker = allocation.expected_marker(_snapshot())

        with self.assertRaisesRegex(
            provider.ProviderStopped,
            "TIMEWEB_ALLOCATION_PREWRITE_RESOURCE_DRIFT",
        ):
            adapter.write_comment_once("float-1", marker)

        self.assertEqual(mutation.calls, [])

    def test_read_failure_is_sanitized(self) -> None:
        payloads = _provider_payloads()
        payloads["/api/v1/projects"] = RuntimeError("provider-private-payload")
        adapter = provider.TimewebAllocationProvider(_ReadApi(payloads))

        with self.assertRaisesRegex(
            provider.ProviderStopped,
            "TIMEWEB_ALLOCATION_PROVIDER_READ_FAILED",
        ) as raised:
            adapter.snapshot()
        self.assertNotIn("provider-private-payload", str(raised.exception))


    def test_write_capable_live_provider_preserves_safe_auth_rejection(self) -> None:
        cases = (
            (401, read_only.AUTHENTICATION_REJECTED_CODE),
            (403, read_only.AUTHORIZATION_REJECTED_CODE),
        )
        for status, code in cases:
            with self.subTest(status=status):
                reader = mock.Mock()
                failure = read_only._provider_base.ProvisioningStopped(
                    code,
                    status=status,
                )
                with (
                    mock.patch(
                        "scripts.probe_v10_timeweb_postgres_control_plane.TimewebReadOnlyApi",
                        return_value=reader,
                    ),
                    mock.patch(
                        "scripts.probe_v10_timeweb_postgres_control_plane.verify_credential_health",
                        side_effect=failure,
                    ),
                    mock.patch(
                        "scripts.provision_v10_timeweb_postgres_public_ipv4_tls.TimewebMutationApi"
                    ) as writer,
                ):
                    with self.assertRaisesRegex(
                        provider.ProviderStopped,
                        code,
                    ) as raised:
                        provider.live_provider("synthetic-token", allow_write=True)
                self.assertNotIn("status=", str(raised.exception))
                writer.assert_not_called()

    def test_read_only_live_provider_does_not_construct_writer(self) -> None:
        reader = mock.Mock()
        with (
            mock.patch(
                "scripts.probe_v10_timeweb_postgres_control_plane.TimewebReadOnlyApi",
                return_value=reader,
            ),
            mock.patch(
                "scripts.probe_v10_timeweb_postgres_control_plane.verify_credential_health"
            ) as preflight,
            mock.patch(
                "scripts.provision_v10_timeweb_postgres_public_ipv4_tls.TimewebMutationApi"
            ) as writer,
        ):
            adapter = provider.live_provider("synthetic-token", allow_write=False)
        self.assertIsInstance(adapter, provider.TimewebAllocationProvider)
        preflight.assert_not_called()
        writer.assert_not_called()


class AllocationRunnerTests(unittest.TestCase):
    def test_mode_inputs_keep_apply_authority_distinct(self) -> None:
        apply_args = argparse.Namespace(
            mode="APPLY",
            plan_id="1" * 32,
            approval_reference="17",
            confirmation="NONE",
        )
        with self.assertRaisesRegex(
            allocation.AllocationStopped,
            "TIMEWEB_ALLOCATION_CONFIRMATION_REQUIRED",
        ):
            runner._validate_mode_inputs(apply_args)

        reconcile_args = argparse.Namespace(
            mode="RECONCILE",
            plan_id="1" * 32,
            approval_reference="17",
            confirmation="NONE",
        )
        with self.assertRaisesRegex(
            allocation.AllocationStopped,
            "TIMEWEB_ALLOCATION_DISPATCH_INPUT_INVALID",
        ):
            runner._validate_mode_inputs(reconcile_args)

    def test_parser_reads_dispatch_values_from_environment_without_shell(self) -> None:
        plan_id = "1" * 32
        with mock.patch.dict(
            runner.os.environ,
            {
                "TIMEWEB_ALLOCATION_PLAN_ID": plan_id,
                "TIMEWEB_ALLOCATION_APPROVAL_REFERENCE": "17",
                "TIMEWEB_ALLOCATION_CONFIRMATION": allocation.ALLOCATE_CONFIRMATION,
            },
            clear=False,
        ):
            args = runner._parser().parse_args(["--mode", "APPLY"])

        self.assertEqual(args.plan_id, plan_id)
        self.assertEqual(args.approval_reference, "17")
        self.assertEqual(args.confirmation, allocation.ALLOCATE_CONFIRMATION)
        runner._validate_mode_inputs(args)

    def test_plan_constructs_read_only_provider(self) -> None:
        source = "a" * 40
        context = allocation.Context(source, source)
        plan = allocation.Plan(
            "1" * 32,
            context,
            _snapshot(),
            1_700_000_000,
            1_700_003_600,
            "0" * 64,
        )
        journal = mock.Mock()
        journal.read.return_value = allocation.Entry(plan, allocation.Phase.PLANNED)
        github = mock.Mock()
        github.current_context.return_value = context
        timeweb = mock.Mock()
        with (
            mock.patch.object(runner, "_expected_head", return_value=source),
            mock.patch.object(
                runner, "_required_env", return_value="synthetic-token"
            ),
            mock.patch.object(runner, "_verifier", return_value=github),
            mock.patch.object(runner, "_context", return_value=context),
            mock.patch.object(runner, "_open_journal", return_value=journal),
            mock.patch.object(
                runner.provider, "live_provider", return_value=timeweb
            ) as live_provider,
            mock.patch.object(
                runner.allocation, "prepare", return_value=plan.identifier
            ),
            mock.patch.object(
                runner, "_approval_body", return_value="safe approval body"
            ),
            mock.patch.object(
                runner.allocation,
                "safe_summary",
                return_value=(
                    "TIMEWEB_IPV4_ALLOCATION_PLAN=handle "
                    "state=OWNER_APPROVAL_REQUIRED"
                ),
            ),
            mock.patch.object(runner, "_emit"),
            mock.patch.object(runner, "_write_summary"),
        ):
            runner._plan()

        live_provider.assert_called_once_with("synthetic-token", allow_write=False)

    def test_apply_constructs_write_capable_provider_only_for_apply(self) -> None:
        source = "a" * 40
        context = allocation.Context(source, source)
        github = mock.Mock()
        timeweb = mock.Mock()
        with (
            mock.patch.object(runner, "_expected_head", return_value=source),
            mock.patch.object(
                runner, "_required_env", return_value="synthetic-token"
            ),
            mock.patch.object(runner, "_verifier", return_value=github),
            mock.patch.object(runner, "_context", return_value=context),
            mock.patch.object(runner, "_open_journal", return_value=mock.Mock()),
            mock.patch.object(
                runner.provider, "live_provider", return_value=timeweb
            ) as live_provider,
            mock.patch.object(
                runner.allocation,
                "apply",
                return_value=allocation.Outcome.ALLOCATED_VERIFIED,
            ) as apply_call,
            mock.patch.object(runner, "_emit"),
            mock.patch.object(runner, "_write_summary"),
        ):
            runner._apply(
                "1" * 32,
                "17",
                allocation.ALLOCATE_CONFIRMATION,
            )

        live_provider.assert_called_once_with("synthetic-token", allow_write=True)
        self.assertEqual(apply_call.call_count, 1)

    def test_reconcile_constructs_read_only_provider(self) -> None:
        source = "a" * 40
        context = allocation.Context(source, source)
        github = mock.Mock()
        timeweb = mock.Mock()
        with (
            mock.patch.object(runner, "_expected_head", return_value=source),
            mock.patch.object(
                runner, "_required_env", return_value="synthetic-token"
            ),
            mock.patch.object(runner, "_verifier", return_value=github),
            mock.patch.object(runner, "_context", return_value=context),
            mock.patch.object(runner, "_open_journal", return_value=mock.Mock()),
            mock.patch.object(
                runner.provider, "live_provider", return_value=timeweb
            ) as live_provider,
            mock.patch.object(
                runner.allocation,
                "reconcile",
                return_value=allocation.Outcome.RECEIPT_RECONCILED,
            ) as reconcile_call,
            mock.patch.object(runner, "_emit"),
            mock.patch.object(runner, "_write_summary"),
        ):
            runner._reconcile("1" * 32)

        live_provider.assert_called_once_with("synthetic-token", allow_write=False)
        self.assertEqual(reconcile_call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
