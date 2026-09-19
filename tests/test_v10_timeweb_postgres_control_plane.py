from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
from unittest import mock
import unittest
from urllib.error import HTTPError

from scripts import check_v10_timeweb_postgres_control_plane as guard
from scripts import probe_v10_timeweb_postgres_control_plane as probe
from scripts import verify_v10_timeweb_github_environment as environment_gate


class _Response:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self._raw
        return self._raw[:amount]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        del args


class _Opener:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> _Response:
        del timeout
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, _Response)
        return outcome


class TimewebControlPlaneTests(unittest.TestCase):
    def test_source_contract_is_valid(self) -> None:
        guard.validate()

    def test_contract_references_are_secret_scan_safe(self) -> None:
        source = guard.CONTRACT.read_text(encoding="utf-8")
        payload = json.loads(source)
        expected_parts = [
            "3a1bd050",
            "d596b2e0",
            "5f73a72f",
            "93199f4e",
            "2944f94b",
        ]
        self.assertNotIn("".join(expected_parts), source)
        self.assertEqual(payload["accepted_base_sha_parts"], expected_parts)
        self.assertEqual(
            payload["environment_gate"]["environment_variable_parts"],
            ["TIMEWEB_CLOUD_API_", "TOKEN"],
        )
        self.assertFalse(payload["environment_gate"]["environment_hardening_accepted"])
        self.assertTrue(
            payload["environment_gate"]["machine_api_hardening_evidence_required"]
        )
        self.assertFalse(
            payload["environment_gate"]["owner_ui_hardening_evidence_required"]
        )
        self.assertEqual(
            payload["environment_gate"]["exact_custom_branch_patterns"],
            ["main"],
        )

    def test_live_workflow_is_manual_main_only_and_read_only(self) -> None:
        source = guard.LIVE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("actions: read", source)
        self.assertIn("environment-policy-proof:", source)
        self.assertIn("needs: environment-policy-proof", source)
        self.assertIn("if: github.ref == 'refs/heads/main'", source)
        self.assertIn("environment: timeweb-synthetic", source)
        self.assertEqual(
            source.count("python -m scripts.verify_v10_timeweb_github_environment"),
            2,
        )
        self.assertIn(
            "TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}",
            source,
        )
        self.assertNotIn("pull_request:", source)
        self.assertNotIn("schedule:", source)

    @staticmethod
    def _environment_payload() -> dict[str, object]:
        return {
            "name": environment_gate.ENVIRONMENT_NAME,
            "protection_rules": [{"id": 1, "type": "branch_policy"}],
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
        }

    @staticmethod
    def _main_policy_payload() -> dict[str, object]:
        return {
            "total_count": 1,
            "branch_policies": [{"id": 7, "name": "main", "type": "branch"}],
        }

    def test_environment_machine_gate_accepts_exact_main_policy(self) -> None:
        opener = _Opener(
            [
                _Response(self._environment_payload()),
                _Response(self._main_policy_payload()),
            ]
        )
        environment_gate.verify_environment_policy(
            "synthetic-token",
            "MishaGameHacking/omni-cio-gateway",
            opener=opener,
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(len(opener.requests), 2)
        self.assertTrue(
            opener.requests[0].full_url.endswith(
                "/environments/timeweb-synthetic"
            )
        )
        self.assertTrue(
            opener.requests[1].full_url.endswith(
                "/deployment-branch-policies?per_page=100&page=1"
            )
        )

    def test_environment_machine_gate_rejects_unrestricted_mode(self) -> None:
        payload = self._environment_payload()
        payload["deployment_branch_policy"] = None
        opener = _Opener([_Response(payload)])
        with self.assertRaisesRegex(
            environment_gate.EnvironmentGateError,
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_SELECTION_MODE_INVALID",
        ):
            environment_gate.verify_environment_policy(
                "synthetic-token",
                "MishaGameHacking/omni-cio-gateway",
                opener=opener,
                sleeper=lambda _seconds: None,
            )

    def test_environment_machine_gate_rejects_extra_policy(self) -> None:
        policies = self._main_policy_payload()
        policies["total_count"] = 2
        policies["branch_policies"] = [
            {"id": 7, "name": "main", "type": "branch"},
            {"id": 8, "name": "release/*", "type": "branch"},
        ]
        opener = _Opener([_Response(self._environment_payload()), _Response(policies)])
        with self.assertRaisesRegex(
            environment_gate.EnvironmentGateError,
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_COUNT_INVALID",
        ):
            environment_gate.verify_environment_policy(
                "synthetic-token",
                "MishaGameHacking/omni-cio-gateway",
                opener=opener,
                sleeper=lambda _seconds: None,
            )

    def test_environment_machine_gate_rejects_wrong_pattern(self) -> None:
        policies = self._main_policy_payload()
        policies["branch_policies"] = [
            {"id": 7, "name": "release/*", "type": "branch"}
        ]
        opener = _Opener([_Response(self._environment_payload()), _Response(policies)])
        with self.assertRaisesRegex(
            environment_gate.EnvironmentGateError,
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_PATTERN_INVALID",
        ):
            environment_gate.verify_environment_policy(
                "synthetic-token",
                "MishaGameHacking/omni-cio-gateway",
                opener=opener,
                sleeper=lambda _seconds: None,
            )

    def test_environment_machine_gate_rejects_tag_type_if_exposed(self) -> None:
        policies = self._main_policy_payload()
        policies["branch_policies"] = [{"id": 7, "name": "main", "type": "tag"}]
        opener = _Opener([_Response(self._environment_payload()), _Response(policies)])
        with self.assertRaisesRegex(
            environment_gate.EnvironmentGateError,
            "TIMEWEB_GITHUB_ENVIRONMENT_GATE_POLICY_TYPE_INVALID",
        ):
            environment_gate.verify_environment_policy(
                "synthetic-token",
                "MishaGameHacking/omni-cio-gateway",
                opener=opener,
                sleeper=lambda _seconds: None,
            )

    def test_environment_machine_gate_retries_transient_get_once(self) -> None:
        transient = HTTPError(
            "https://api.github.com/environment",
            503,
            "service unavailable",
            {},
            io.BytesIO(b"provider detail"),
        )
        opener = _Opener(
            [
                transient,
                _Response(self._environment_payload()),
                _Response(self._main_policy_payload()),
            ]
        )
        sleeps: list[float] = []
        environment_gate.verify_environment_policy(
            "synthetic-token",
            "MishaGameHacking/omni-cio-gateway",
            opener=opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(len(opener.requests), 3)

    def test_timeweb_secret_scope_rejects_second_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "v10-timeweb-postgres-readonly-proof.yml").write_text(
                "TIMEWEB_CLOUD_API_TOKEN: ${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}\n",
                encoding="utf-8",
            )
            (workflows / "other.yml").write_text(
                "# TIMEWEB_CLOUD_API_TOKEN\n",
                encoding="utf-8",
            )
            with mock.patch.object(guard, "WORKFLOWS", workflows), mock.patch.object(
                guard,
                "LIVE_WORKFLOW",
                workflows / "v10-timeweb-postgres-readonly-proof.yml",
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "TIMEWEB_CONTROL_PLANE_SECRET_SCOPE_TOO_BROAD",
                ):
                    guard._validate_timeweb_secret_scope()

    def test_project_id_rejects_non_ascii_digits(self) -> None:
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_PROJECT_ID_INVALID",
        ):
            probe._project_id("١٢٣")

    def test_project_selection_is_exact_and_unique(self) -> None:
        payload = {
            "projects": [
                {"id": 1, "name": "Other"},
                {"id": 2, "name": probe.TARGET_PROJECT_NAME},
            ]
        }
        self.assertEqual(probe._select_project(payload), "2")

    def test_postgres18_type_is_discovered_not_hardcoded(self) -> None:
        payload = {
            "types": [
                {
                    "name": "PostgreSQL",
                    "version": "18",
                    "type": "pg_current_18",
                    "is_deprecated": False,
                }
            ]
        }
        self.assertEqual(probe._select_postgres18_type(payload), "pg_current_18")

    def test_deprecated_postgres18_type_is_rejected(self) -> None:
        payload = {
            "types": [
                {
                    "name": "PostgreSQL",
                    "version": 18,
                    "type": "postgres18",
                    "is_deprecated": True,
                }
            ]
        }
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_POSTGRES18_TYPE_NOT_UNIQUE",
        ):
            probe._select_postgres18_type(payload)

    def test_beta_preset_requires_exact_resources_and_price(self) -> None:
        payload = {
            "databases_presets": [
                {
                    "id": 777,
                    "type": "postgres",
                    "location": "ru-3",
                    "cpu": 1,
                    "ram": 2048,
                    "disk": 20480,
                    "price": 790,
                }
            ]
        }
        probe._select_target_preset(payload, "postgres18")

    def test_beta_preset_price_drift_fails_closed(self) -> None:
        payload = {
            "databases_presets": [
                {
                    "id": 777,
                    "type": "postgres",
                    "location": "ru-3",
                    "cpu": 1,
                    "ram": 2048,
                    "disk": 20480,
                    "price": 791,
                }
            ]
        }
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_BETA_PRESET_NOT_UNIQUE_OR_PRICE_DRIFT",
        ):
            probe._select_target_preset(payload, "postgres18")

    def test_existing_target_cluster_fails_closed(self) -> None:
        payload = {"databases": [{"id": 99, "name": probe.TARGET_CLUSTER_NAME}]}
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_TARGET_CLUSTER_ALREADY_EXISTS",
        ):
            probe._verify_cluster_name_available(payload)

    def test_read_only_api_masks_auth_failure(self) -> None:
        request = HTTPError(
            "https://api.timeweb.cloud/api/v1/projects",
            403,
            "forbidden",
            {},
            io.BytesIO(b'{"detail":"do not emit"}'),
        )
        opener = _Opener([request])
        api = probe.TimewebReadOnlyApi("synthetic-token", opener=opener)
        with self.assertRaisesRegex(
            probe._provider_base.ProvisioningStopped,
            "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT",
        ):
            api.get("/api/v1/projects")

    def test_transient_get_retry_is_bounded(self) -> None:
        first = HTTPError(
            "https://api.timeweb.cloud/api/v1/projects",
            429,
            "rate limited",
            {},
            io.BytesIO(b"provider detail"),
        )
        opener = _Opener([first, _Response({"projects": []})])
        sleeps: list[float] = []
        api = probe.TimewebReadOnlyApi(
            "synthetic-token",
            opener=opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(api.get("/api/v1/projects"), {"projects": []})
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(len(opener.requests), 2)

    def test_request_is_get_only_and_token_is_not_emitted(self) -> None:
        opener = _Opener([_Response({"projects": []})])
        api = probe.TimewebReadOnlyApi("synthetic-token", opener=opener)
        with mock.patch("builtins.print") as output:
            api.get("/api/v1/projects")
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("Bearer synthetic-token", request.headers.values())
        rendered = " ".join(str(call) for call in output.call_args_list)
        self.assertNotIn("synthetic-token", rendered)


if __name__ == "__main__":
    unittest.main()
