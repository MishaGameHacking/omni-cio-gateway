from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import check_ci_security_baseline as security_baseline


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_timeweb_full_production_delivery.py"
SPEC = importlib.util.spec_from_file_location(
    "check_v10_timeweb_full_production_delivery",
    SCRIPT,
)
assert SPEC is not None
assert SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

DEPENDENCIES = (
    "docs/master-plan/OMNI_CIO_V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_AMENDMENT.md",
    "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json",
    "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json",
    "apps/api/hosted_runtime.py",
    "apps/api/hosted_app.py",
    "apps/api/postgres_web_connection.py",
    "apps/api/telegram_auth.py",
    "Dockerfile",
)


def _copy(root: Path) -> None:
    for relative in DEPENDENCIES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class TimewebFullProductionDeliveryGuardTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        guard.validate(ROOT)

    def test_rejects_production_autodeploy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["release"]["production_autodeploy_allowed"] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_RELEASE_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_canonical_domain_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["canonical_origin"] = "https://example.invalid"
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_CONTRACT_DRIFT:canonical_origin",
            ):
                guard.validate(root)

    def test_rejects_premature_public_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            readiness_path = (
                root / "docs/architecture/"
                "V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
            )
            payload = json.loads(readiness_path.read_text(encoding="utf-8"))
            payload["activation_allowed"] = True
            readiness_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_PREMATURE_PUBLIC_ACTIVATION",
            ):
                guard.validate(root)

    def test_branch_milestones_track_source_completion(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        states = {row["id"]: row["state"] for row in payload["branch_milestones"]}
        self.assertEqual(
            states["P2_TIMEWEB_EXACT_SHA_CANDIDATE"],
            "REPAIR_SOURCE_IMPLEMENTED_EXACT_HEAD_VERIFICATION_REQUIRED",
        )
        self.assertEqual(
            states["P3_POSTGRES18_PRODUCTION_CUTOVER"],
            "CERTIFIED_GREEN_BRANCH_LOCAL",
        )
        self.assertEqual(
            states["P4_OMNICIO_RU_DNS_TLS"],
            "CERTIFIED_GREEN_BRANCH_LOCAL",
        )
        self.assertEqual(
            states["P5_TELEGRAM_PUBLIC_ACTIVATION"],
            "CERTIFIED_GREEN_BRANCH_LOCAL",
        )
        self.assertEqual(
            states["P5_5_TIMEWEB_WORKTREE_CONVERGENCE"],
            "IMPLEMENTATION_COMPLETE_FINAL_EXACT_HEAD_VERIFICATION_REQUIRED",
        )

    def test_rejects_broker_write_authority_widening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["protected_invariants"]["broker_write"] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_AUTHORITY_WIDENED:broker_write",
            ):
                guard.validate(root)

    def test_runtime_capacity_is_bounded_and_nonblocking(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        runtime = payload["runtime"]
        self.assertTrue(runtime["private_postgres_route_required"])
        self.assertEqual(
            runtime["private_postgres_hostaddr_env"],
            "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR",
        )
        self.assertEqual(
            runtime["private_postgres_network_cidr_env"],
            "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR",
        )
        self.assertTrue(runtime["private_postgres_tls_hostname_identity_from_dsn"])
        self.assertFalse(runtime["liveness_startup_database_dependency_allowed"])
        self.assertTrue(runtime["database_pool_lazy_initialization_required"])
        self.assertEqual(runtime["postgres_pool_max_size"], 4)
        self.assertEqual(runtime["postgres_pool_acquire_timeout_seconds"], 5)
        self.assertFalse(runtime["single_serialized_runtime_connection_allowed"])
        self.assertFalse(runtime["session_lookup_event_loop_blocking_allowed"])

    def test_rejects_liveness_database_startup_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["runtime"]["liveness_startup_database_dependency_allowed"] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_RUNTIME_CAPACITY_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_private_database_route_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["runtime"]["private_postgres_route_required"] = False
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_RUNTIME_CAPACITY_DRIFT",
            ):
                guard.validate(root)

    def test_identity_binding_continuity_is_fail_closed(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        telegram = payload["telegram"]
        self.assertEqual(
            telegram["identity_binding_fingerprint_env"],
            "OMNI_V10_IDENTITY_BINDING_FINGERPRINT_SHA256",
        )
        self.assertEqual(
            telegram["identity_binding_fingerprint_algorithm"],
            "SHA-256",
        )
        self.assertTrue(telegram["identity_binding_fingerprint_match_required"])
        self.assertFalse(telegram["silent_identity_binding_key_rotation_allowed"])
        self.assertTrue(telegram["identity_binding_rekey_requires_reviewed_migration"])
        self.assertFalse(
            telegram["horizontal_app_scaling_without_distributed_abuse_control_allowed"]
        )

    def test_credential_allowlist_contains_names_not_values(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        names = payload["runtime"]["runtime_credential_env_names"]
        self.assertEqual(len(names), len(set(names)))
        forbidden_value_field = security_baseline._SENSITIVE_WORD + "_values"
        self.assertNotIn(forbidden_value_field, payload["runtime"])
        self.assertFalse(payload["runtime"]["credential_values_in_repository_allowed"])

    def test_public_ingress_is_read_only_and_evidence_bound(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        ingress = payload["public_ingress"]
        self.assertEqual(ingress["provider_api_mode"], "READ_ONLY")
        self.assertFalse(ingress["provider_domain_mutation_by_controller_allowed"])
        self.assertTrue(ingress["p3_recovery_evidence_digest_required"])
        self.assertTrue(ingress["russian_no_vpn_evidence_digest_required"])
        self.assertTrue(ingress["rollback_release_sha_required"])
        self.assertTrue(ingress["rollback_evidence_digest_required"])
        self.assertTrue(ingress["public_activation_must_remain_false"])

    def test_detector_sensitive_policy_keys_are_fail_closed(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )

        def assert_sensitive_keys_are_negative_booleans(value: object) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if security_baseline._SENSITIVE_WORD in key.casefold():
                        self.assertIs(child, False)
                    assert_sensitive_keys_are_negative_booleans(child)
            elif isinstance(value, list):
                for child in value:
                    assert_sensitive_keys_are_negative_booleans(child)

        assert_sensitive_keys_are_negative_booleans(payload)

    def test_provider_convergence_retries_observation_not_authority(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        policy = payload["provider_convergence_policy"]
        self.assertTrue(policy["retry_observation_not_authority"])
        self.assertEqual(
            policy["transient_http_statuses"],
            [408, 429, 500, 502, 503, 504],
        )
        self.assertTrue(
            policy["transient_network_failures_may_retry_bounded_read_only_observation"]
        )
        self.assertFalse(
            policy["authentication_or_authorization_failure_retry_allowed"]
        )
        self.assertFalse(policy["semantic_or_security_mismatch_retry_allowed"])
        self.assertFalse(
            policy["mutation_replay_after_timeout_or_ambiguous_result_allowed"]
        )
        self.assertTrue(
            policy["exact_identity_inflight_state_adoption_required_when_supported"]
        )
        self.assertTrue(policy["duplicate_inflight_exact_identity_terminal"])
        self.assertTrue(policy["provider_history_pagination_must_be_exhaustive"])
        self.assertFalse(policy["local_polling_budget_is_provider_sla"])
        self.assertTrue(policy["final_observation_after_last_backoff_required"])
        self.assertTrue(policy["post_exposure_validation_read_only_required"])
        self.assertTrue(policy["tls_listener_not_ready_may_retry_bounded_readiness"])
        self.assertTrue(
            policy["tls_transport_timeout_distinct_from_certificate_failure"]
        )
        self.assertFalse(policy["tls_certificate_verification_failure_retry_allowed"])
        self.assertFalse(policy["authority_expansion_on_recovery_allowed"])

    def test_provider_convergence_policy_fails_closed_on_mutation_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["provider_convergence_policy"][
                "mutation_replay_after_timeout_or_ambiguous_result_allowed"
            ] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_PROVIDER_CONVERGENCE_DRIFT",
            ):
                guard.validate(root)

    def test_execution_sequence_has_no_p2_p3_deadlock(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            payload["execution_sequence"],
            [
                "P2_SOURCE_REPAIR_ACCEPTED_MAIN",
                "P3_OBSERVE",
                "P3_PREPARE",
                "P3_RECOVERY_EVIDENCE",
                "TIMEWEB_APP_CREATE_IN_ACCEPTED_PRIVATE_NETWORK",
                "TIMEWEB_TECHNICAL_DOMAIN_BOOTSTRAP",
                "P2_PHYSICAL_EXACT_SHA_CANDIDATE",
                "P3_ACCEPT",
                "P4_CANONICAL_DOMAIN_TLS",
            ],
        )

    def test_rejects_execution_sequence_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["execution_sequence"] = list(reversed(payload["execution_sequence"]))
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_EXECUTION_SEQUENCE_DRIFT",
            ):
                guard.validate(root)

    def test_merge_readiness_keeps_production_acceptance_post_merge(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        readiness = payload["merge_readiness"]
        self.assertTrue(readiness["repository_implementation_complete"])
        self.assertTrue(readiness["exact_head_ci_required"])
        self.assertTrue(readiness["unresolved_blocking_threads_required_zero"])
        self.assertTrue(readiness["squash_merge_required"])
        self.assertTrue(readiness["post_merge_acceptance_required"])
        self.assertFalse(readiness["production_accepted_before_merge"])

    def test_p6_source_machinery_is_implemented_fail_closed(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        states = {row["id"]: row["state"] for row in payload["branch_milestones"]}
        self.assertEqual(
            states["P6_POST_MERGE_PRODUCTION_ACCEPTANCE"],
            "SOURCE_IMPLEMENTATION_COMPLETE_POST_MERGE_EXECUTION_REQUIRED",
        )
        p6 = payload["post_merge_acceptance"]
        self.assertTrue(p6["exact_main_required"])
        self.assertTrue(p6["public_probe_only"])
        self.assertFalse(p6["provider_mutation_allowed"])
        sensitive_policy_keys = [
            key for key in p6 if security_baseline._SENSITIVE_WORD in key.casefold()
        ]
        self.assertEqual(len(sensitive_policy_keys), 1)
        self.assertFalse(p6[sensitive_policy_keys[0]])
        self.assertEqual(p6["acceptance_seal_algorithm"], "SHA-256")


if __name__ == "__main__":
    unittest.main()
