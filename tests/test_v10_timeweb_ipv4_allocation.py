from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import unittest
from unittest import mock

from scripts import timeweb_ipv4_allocation as allocation
from scripts import timeweb_ipv4_custody as custody


MAIN = "3083e65f9e6dbc7a6f26de6649ae7ff40627ba5c"
OTHER = "514bfae805f7bdbd74dfc6610191d0ca211b4c94"
NOW = 1_800_468_000
CONTEXT = allocation.Context(MAIN, MAIN)
SNAPSHOT = allocation.Snapshot(
    account_scope="fixture-account",
    project_id="fixture-project",
    cluster_id=91,
    floating_id="fixture-ip",
    ip_address="8.8.4.4",
    comment="",
)
APPROVAL_REF = "fixture-owner-decision"


class JournalDouble:
    """Test-only serializable memory model. NOT evidence of durable production IO."""

    def __init__(self) -> None:
        self.entries: dict[str, allocation.Entry] = {}
        self.lock = threading.Lock()
        self.events: list[str] = []

    def create(self, plan: allocation.Plan) -> None:
        with self.lock:
            for entry in self.entries.values():
                same_target = (
                    entry.plan.snapshot.account_scope == plan.snapshot.account_scope
                    and entry.plan.snapshot.project_id == plan.snapshot.project_id
                    and entry.plan.snapshot.cluster_id == plan.snapshot.cluster_id
                )
                same_ip = (
                    entry.plan.snapshot.account_scope == plan.snapshot.account_scope
                    and entry.plan.snapshot.floating_id == plan.snapshot.floating_id
                )
                if same_target or same_ip:
                    raise RuntimeError("active scope")
            if plan.identifier in self.entries:
                raise RuntimeError("no overwrite")
            self.entries[plan.identifier] = allocation.Entry(
                plan,
                allocation.Phase.PLANNED,
            )
            self.events.append("PLAN_SAVED")

    def read(self, identifier: str) -> allocation.Entry:
        with self.lock:
            return self.entries[identifier]

    def claim(self, identifier: str, digest: str, approval_reference: str) -> bool:
        with self.lock:
            entry = self.entries[identifier]
            if (
                entry.phase is not allocation.Phase.PLANNED
                or entry.plan.digest != digest
            ):
                return False
            self.entries[identifier] = replace(
                entry,
                phase=allocation.Phase.ATTEMPTED,
                approval_reference=approval_reference,
            )
            self.events.append("ATTEMPT_DURABLE")
            return True

    def complete(self, identifier: str, digest: str) -> None:
        with self.lock:
            entry = self.entries[identifier]
            if (
                entry.phase is not allocation.Phase.ATTEMPTED
                or entry.plan.digest != digest
            ):
                raise RuntimeError("bad completion")
            self.entries[identifier] = replace(entry, phase=allocation.Phase.ALLOCATED)
            self.events.append("RECEIPT_SAVED")


class VerifierDouble:
    """Only explicit synthetic approval evidence exists in this test double."""

    def __init__(self) -> None:
        self.calls = 0
        self.changes: dict[str, object] = {}
        self.reject = False

    def verify(
        self, reference: str, plan: allocation.Plan, now: int
    ) -> allocation.OwnerApproval:
        self.calls += 1
        if self.reject or reference != APPROVAL_REF:
            raise RuntimeError("not an owner decision")
        approval = allocation.OwnerApproval(
            reference,
            plan.identifier,
            plan.digest,
            MAIN,
            plan.issued_at,
            plan.expires_at,
        )
        return replace(approval, **self.changes)


class ProviderDouble:
    def __init__(self) -> None:
        self.snapshot = SNAPSHOT
        self.writes: list[tuple[str, str]] = []
        self.read_count = 0
        self.journal: JournalDouble | None = None

    def read(self) -> allocation.Snapshot:
        self.read_count += 1
        return self.snapshot

    def assign_comment(self, identifier: str, marker: str) -> None:
        if self.journal is None or "ATTEMPT_DURABLE" not in self.journal.events:
            raise AssertionError("write before journal claim")
        self.writes.append((identifier, marker))
        self.snapshot = replace(self.snapshot, comment=marker)


def provider_row(snapshot: allocation.Snapshot) -> dict[str, object]:
    return {
        "id": snapshot.floating_id,
        "ip": snapshot.ip_address,
        "availability_zone": snapshot.zone,
        "is_ddos_guard": snapshot.ddos_enabled,
        "resource_type": snapshot.resource_type,
        "resource_id": snapshot.resource_id,
        "comment": snapshot.comment,
    }


class AllocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = ProviderDouble()
        self.journal = JournalDouble()
        self.provider.journal = self.journal
        self.verifier = VerifierDouble()
        self.clock = mock.Mock(return_value=NOW)
        self.sleep = mock.Mock()
        self.read_context = mock.Mock(return_value=CONTEXT)

    def prepare(self) -> str:
        return allocation.prepare(
            self.provider.read, self.journal, CONTEXT, clock=self.clock,
            read_context=self.read_context,
        )

    def apply(self, identifier: str, **overrides: object) -> allocation.Outcome:
        options = dict(
            identifier=identifier,
            approval_reference=APPROVAL_REF,
            confirmation=allocation.ALLOCATE_CONFIRMATION,
            read_snapshot=self.provider.read,
            write_comment_once=self.provider.assign_comment,
            journal=self.journal,
            verifier=self.verifier,
            context=CONTEXT,
            clock=self.clock,
            sleeper=self.sleep,
            read_context=self.read_context,
        )
        options.update(overrides)
        return allocation.apply(**options)

    def reconcile(self, identifier: str) -> allocation.Outcome:
        return allocation.reconcile(
            identifier, self.provider.read, self.journal, CONTEXT, sleeper=self.sleep
        )

    def test_plan_is_durable_before_handle_is_returned(self) -> None:
        identifier = self.prepare()
        entry = self.journal.read(identifier)
        self.assertEqual(entry.phase, allocation.Phase.PLANNED)
        self.assertEqual(entry.plan.snapshot, SNAPSHOT)
        self.assertEqual(entry.plan.expires_at, NOW + allocation.PLAN_TTL_SECONDS)
        self.assertEqual(self.provider.read_count, 2)
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(self.verifier.calls, 0)

    def test_plan_creation_failure_returns_no_handle_and_performs_no_write(
        self,
    ) -> None:
        with mock.patch.object(self.journal, "create", side_effect=OSError("private")):
            with self.assertRaisesRegex(allocation.AllocationStopped, "SAVE_UNPROVEN"):
                self.prepare()
        self.assertEqual(self.provider.writes, [])

    def test_noop_journal_does_not_prove_plan_save(self) -> None:
        with mock.patch.object(self.journal, "create"):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "JOURNAL_UNAVAILABLE",
            ):
                self.prepare()
        self.assertEqual(self.provider.writes, [])

    def test_duplicate_active_plan_scope_cannot_overwrite(self) -> None:
        identifier = self.prepare()
        original = self.journal.read(identifier)
        with self.assertRaisesRegex(allocation.AllocationStopped, "SAVE_UNPROVEN"):
            self.prepare()
        self.assertEqual(len(self.journal.entries), 1)
        self.assertEqual(self.journal.read(identifier), original)

    def test_two_planning_observations_must_agree(self) -> None:
        changed = replace(SNAPSHOT, floating_id="other-ip")
        with mock.patch.object(self.provider, "read", side_effect=[SNAPSHOT, changed]):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "OBSERVATION_DRIFT",
            ):
                self.prepare()
        self.assertEqual(self.journal.entries, {})
        self.assertEqual(self.provider.writes, [])

    def test_legacy_unmarked_state_is_still_rejected_by_ordinary_custody(self) -> None:
        row = provider_row(SNAPSHOT)
        parsed = custody.inventory([row])
        with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
            custody.select(parsed, 91, public_enabled=False)
        self.prepare()
        parsed = custody.inventory([row])
        with self.assertRaisesRegex(custody.CustodyStopped, "PROVENANCE_REQUIRED"):
            custody.select(parsed, 91, public_enabled=False)

    def test_actual_approved_allocation_uses_same_ip_and_existing_marker_protocol(
        self,
    ) -> None:
        identifier = self.prepare()
        result = self.apply(identifier)
        expected = custody.marker(91, custody.inventory([provider_row(SNAPSHOT)])[0])
        self.assertEqual(result, allocation.Outcome.ALLOCATED_VERIFIED)
        self.assertEqual(self.provider.writes, [(SNAPSHOT.floating_id, expected)])
        self.assertEqual(self.provider.snapshot.ip_address, SNAPSHOT.ip_address)
        self.assertFalse(self.provider.snapshot.public_enabled)
        self.assertIsNone(self.provider.snapshot.resource_id)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ALLOCATED,
        )
        self.assertEqual(self.verifier.calls, 3)
        self.assertEqual(
            self.journal.events,
            ["PLAN_SAVED", "ATTEMPT_DURABLE", "RECEIPT_SAVED"],
        )

    def test_allocated_ip_is_reusable_by_unchanged_custody_without_create_or_delete(
        self,
    ) -> None:
        identifier = self.prepare()
        self.apply(identifier)
        row = provider_row(self.provider.snapshot)
        no_write = mock.Mock(side_effect=AssertionError("unexpected mutation"))
        result = custody.resolve(
            lambda: [row], no_write, no_write, no_write, 91,
            public_enabled=False, emit=lambda _message: None,
        )
        self.assertEqual(result, (SNAPSHOT.floating_id, SNAPSHOT.ip_address, False))
        no_write.assert_not_called()

    def test_comment_classification_does_not_treat_foreign_text_as_empty(self) -> None:
        marker = allocation.expected_marker(SNAPSHOT)
        cases = (
            ("", allocation.CommentState.EMPTY),
            (marker, allocation.CommentState.MATCHING),
            (
                custody.MARKER_PREFIX + "wrong-target",
                allocation.CommentState.OTHER_TARGET,
            ),
            ("allocated to another system", allocation.CommentState.FOREIGN),
            (" ", allocation.CommentState.FOREIGN),
        )
        for comment, expected in cases:
            with self.subTest(state=expected):
                actual = allocation.comment_state(replace(SNAPSHOT, comment=comment))
                self.assertEqual(actual, expected)

    def test_existing_comments_of_any_kind_cannot_be_planned_for_overwrite(
        self,
    ) -> None:
        for comment in (
            " ",
            "foreign",
            custody.MARKER_PREFIX,
            allocation.expected_marker(SNAPSHOT),
        ):
            self.provider.snapshot = replace(SNAPSHOT, comment=comment)
            with self.subTest(comment_kind=comment[:8]):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "ASSOCIATION_FORBIDDEN",
                ):
                    self.prepare()
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(self.journal.entries, {})

    def test_confirmation_is_separate_from_cost_or_generic_development_approval(
        self,
    ) -> None:
        identifier = self.prepare()
        for confirmation in (
            "",
            "continue",
            "ENABLE_TIMEWEB_RU_PG_PUBLIC_IPV4_200_RUB_MONTH",
        ):
            with self.subTest(confirmation=confirmation):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "CONFIRMATION_REQUIRED",
                ):
                    self.apply(identifier, confirmation=confirmation)
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(self.verifier.calls, 0)

    def test_unknown_owner_decision_is_not_authority(self) -> None:
        identifier = self.prepare()
        with self.assertRaisesRegex(allocation.AllocationStopped, "APPROVAL_UNPROVEN"):
            self.apply(identifier, approval_reference="generic-development-approval")
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(self.journal.read(identifier).phase, allocation.Phase.PLANNED)

    def test_empty_or_malformed_decision_reference_is_rejected(self) -> None:
        identifier = self.prepare()
        for reference in (None, "", "x" * 257, "line\nbreak", " leading", "\u0430"):
            with self.subTest(reference_type=type(reference)):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "APPROVAL_REQUIRED",
                ):
                    self.apply(identifier, approval_reference=reference)
        self.assertEqual(self.provider.writes, [])

    def test_noop_or_boolean_verifier_cannot_approve(self) -> None:
        identifier = self.prepare()
        for result in (None, True, {}, "approved"):
            with self.subTest(result_type=type(result)):
                with mock.patch.object(self.verifier, "verify", return_value=result):
                    with self.assertRaisesRegex(
                        allocation.AllocationStopped,
                        "APPROVAL_UNPROVEN",
                    ):
                        self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_mismatched_or_revoked_approval_fields_are_rejected(self) -> None:
        identifier = self.prepare()
        cases = (
            {"reference": "another-approval"},
            {"plan_id": "f" * 32},
            {"plan_digest": "wrong-digest"},
            {"source_sha": OTHER},
            {"purpose": "COST_ONLY"},
            {"revoked": True},
            {"revoked": 0},
            {"approved_at": NOW - 1},
            {"approved_at": NOW + 1},
            {"approved_at": True},
            {"expires_at": NOW},
            {"expires_at": NOW + allocation.PLAN_TTL_SECONDS + 1},
            {"expires_at": False},
        )
        for changes in cases:
            self.verifier.changes = changes
            with self.subTest(fields=tuple(changes)):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "APPROVAL_UNPROVEN",
                ):
                    self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_expired_or_future_plan_cannot_mutate(self) -> None:
        identifier = self.prepare()
        for now in (NOW - 1, NOW + allocation.PLAN_TTL_SECONDS):
            self.clock.return_value = now
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "EXPIRED_OR_FUTURE",
            ):
                self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_expiry_while_reading_provider_is_checked_again(self) -> None:
        identifier = self.prepare()
        self.clock.side_effect = [NOW, NOW + allocation.PLAN_TTL_SECONDS]
        with self.assertRaisesRegex(allocation.AllocationStopped, "EXPIRED_OR_FUTURE"):
            self.apply(identifier)
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(self.journal.read(identifier).phase, allocation.Phase.PLANNED)

    def test_revocation_after_durable_claim_still_stops_before_write(self) -> None:
        identifier = self.prepare()
        real = self.verifier.verify
        calls = 0
        def verify(reference, plan, now):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("revoked")
            return real(reference, plan, now)
        with mock.patch.object(self.verifier, "verify", side_effect=verify):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "APPROVAL_UNPROVEN",
            ):
                self.apply(identifier)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )
        self.assertEqual(self.provider.writes, [])

    def test_source_drift_cannot_mutate(self) -> None:
        identifier = self.prepare()
        changed_context = allocation.Context(OTHER, OTHER)
        with self.assertRaisesRegex(allocation.AllocationStopped, "SOURCE_DRIFT"):
            self.apply(identifier, context=changed_context)
        self.assertEqual(self.provider.writes, [])

    def test_nonmain_wrong_repo_or_environment_context_is_rejected(self) -> None:
        identifier = self.prepare()
        for context in (
            replace(CONTEXT, current_main_sha=OTHER),
            replace(CONTEXT, repository="other/repo"),
            replace(CONTEXT, environment="production"),
            replace(CONTEXT, ref="refs/tags/main"),
            replace(CONTEXT, source_sha="g" * 40, current_main_sha="g" * 40),
            None,
        ):
            with self.subTest(context_type=type(context)):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "SOURCE_AUTHORITY_INVALID",
                ):
                    self.apply(identifier, context=context)
        self.assertEqual(self.provider.writes, [])

    def test_different_resource_or_target_with_identical_shape_is_not_selected(
        self,
    ) -> None:
        identifier = self.prepare()
        for changes in (
            {"account_scope": "other-account"},
            {"project_id": "other-project"},
            {"cluster_id": 92},
            {"floating_id": "other-ip"},
            {"ip_address": "1.1.1.1"},
            {"comment": "foreign"},
        ):
            self.provider.snapshot = replace(SNAPSHOT, **changes)
            with self.subTest(fields=tuple(changes)):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "RESOURCE_DRIFT",
                ):
                    self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_postclaim_drift_leaves_claim_for_reconciliation(self) -> None:
        identifier = self.prepare()
        changed = replace(SNAPSHOT, floating_id="replacement-ip")
        with mock.patch.object(
            self.provider,
            "read",
            side_effect=[SNAPSHOT, SNAPSHOT, changed],
        ):
            with self.assertRaisesRegex(allocation.AllocationStopped, "RESOURCE_DRIFT"):
                self.apply(identifier)
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )

    def test_shape_and_binding_anomalies_fail_closed(self) -> None:
        cases = (
            {"inventory_count": 0}, {"inventory_count": 2}, {"inventory_count": True},
            {"zone": "spb-3"}, {"ddos_enabled": True}, {"ddos_enabled": 0},
            {"target_name": "other-db"}, {"resource_type": "server"},
            {"resource_id": "91"}, {"public_enabled": True},
            {"public_enabled": None}, {"ipv6_enabled": True},
        )
        for changes in cases:
            self.provider.snapshot = replace(SNAPSHOT, **changes)
            with self.subTest(fields=tuple(changes)):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "SHAPE_OR_BINDING_DRIFT",
                ):
                    self.prepare()
        self.assertEqual(self.journal.entries, {})

    def test_malformed_snapshot_never_authorizes_anything(self) -> None:
        cases = (
            {"floating_id": "../escape"}, {"account_scope": None},
            {"project_id": 1}, {"cluster_id": True}, {"cluster_id": 0},
            {"ip_address": "127.0.0.1"}, {"ip_address": "::1"},
            {"ip_address": "8.8.004.4"}, {"ip_address": "bad"}, {"ip_address": 1},
            {"comment": None}, {"comment": []}, {"comment": "x" * 4097},
        )
        for changes in cases:
            self.provider.snapshot = replace(SNAPSHOT, **changes)
            with self.subTest(fields=tuple(changes)):
                with self.assertRaises(allocation.AllocationStopped):
                    self.prepare()
        with mock.patch.object(self.provider, "read", return_value=None):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "SNAPSHOT_INVALID",
            ):
                self.prepare()
        self.assertEqual(self.provider.writes, [])

    def test_unknown_get_response_is_not_an_empty_inventory(self) -> None:
        with mock.patch.object(
            self.provider,
            "read",
            side_effect=OSError("private-response"),
        ):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "OBSERVATION_UNAVAILABLE",
            ) as raised:
                self.prepare()
        self.assertNotIn("private-response", str(raised.exception))
        self.assertEqual(self.journal.entries, {})

    def test_plan_tampering_or_corruption_is_rejected(self) -> None:
        identifier = self.prepare()
        original = self.journal.read(identifier)
        for changes in (
            {"digest": "wrong"}, {"snapshot": replace(SNAPSHOT, floating_id="wrong")},
            {"expires_at": NOW + 7200}, {"issued_at": True},
            {"snapshot": replace(SNAPSHOT, comment="foreign")}, {"identifier": "bad"},
        ):
            self.journal.entries[identifier] = replace(
                original,
                plan=replace(original.plan, **changes),
            )
            with self.subTest(fields=tuple(changes)):
                with self.assertRaises(allocation.AllocationStopped):
                    self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_journal_wrong_identifier_is_not_accepted(self) -> None:
        identifier = self.prepare()
        original = self.journal.read(identifier)
        other = "e" * 32
        plan = original.plan
        changed = replace(
            plan, identifier=other,
            digest=allocation._private_digest(
                other,
                plan.context,
                plan.snapshot,
                plan.issued_at,
                plan.expires_at,
            ),
        )
        self.journal.entries[identifier] = replace(original, plan=changed)
        with self.assertRaisesRegex(allocation.AllocationStopped, "JOURNAL_ID_DRIFT"):
            self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_malformed_handle_stops_before_journal_lookup(self) -> None:
        for identifier in (None, "", "x" * 32, "0" * 31, "0" * 33, "../escape"):
            with self.subTest(kind=type(identifier)):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "PLAN_ID_INVALID",
                ):
                    self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_journal_unavailable_before_claim_never_mutates(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(self.journal, "read", side_effect=OSError("private")):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "JOURNAL_UNAVAILABLE",
            ):
                self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_ambiguous_journal_claim_never_authorizes_write(self) -> None:
        identifier = self.prepare()
        real = self.journal.claim
        def failed_claim(*args):
            real(*args)
            raise OSError("lost acknowledgement")
        with mock.patch.object(self.journal, "claim", side_effect=failed_claim):
            with self.assertRaisesRegex(allocation.AllocationStopped, "CLAIM_UNPROVEN"):
                self.apply(identifier)
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )

    def test_claim_must_be_literal_true_and_re_read_as_attempted(self) -> None:
        identifier = self.prepare()
        for result in (None, False, 1, True):
            with self.subTest(result=result):
                with mock.patch.object(self.journal, "claim", return_value=result):
                    with self.assertRaises(allocation.AllocationStopped):
                        self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_claim_reference_without_attempted_phase_cannot_authorize_write(
        self,
    ) -> None:
        identifier = self.prepare()
        def corrupt_claim(plan_id, digest, reference):
            entry = self.journal.read(plan_id)
            self.journal.entries[plan_id] = replace(
                entry, approval_reference=reference
            )
            return True
        with mock.patch.object(self.journal, "claim", side_effect=corrupt_claim):
            with mock.patch.object(self.provider, "assign_comment") as write:
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "CLAIM_UNPROVEN",
                ):
                    self.apply(identifier)
        write.assert_not_called()
        self.assertEqual(self.journal.read(identifier).phase, allocation.Phase.PLANNED)

    def test_lost_write_response_is_verified_by_get_without_repeating_patch(
        self,
    ) -> None:
        identifier = self.prepare()
        real = self.provider.assign_comment
        def lost(*args):
            real(*args)
            raise OSError("private lost response")
        with mock.patch.object(self.provider, "assign_comment", side_effect=lost):
            self.assertEqual(
                self.apply(identifier),
                allocation.Outcome.ALLOCATED_VERIFIED,
            )
        self.assertEqual(len(self.provider.writes), 1)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ALLOCATED,
        )

    def test_success_return_without_get_evidence_is_not_completion(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(self.provider, "assign_comment") as write:
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "OUTCOME_UNKNOWN",
            ):
                self.apply(identifier)
        write.assert_called_once()
        self.assertEqual(self.sleep.call_count, 3)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )

    def test_unknown_write_outcome_never_retries_on_reentry(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(
            self.provider,
            "assign_comment",
            side_effect=OSError("private"),
        ) as write:
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "OUTCOME_UNKNOWN",
            ):
                self.apply(identifier)
            for _attempt in range(10):
                with self.assertRaisesRegex(
                    allocation.AllocationStopped,
                    "ALREADY_ATTEMPTED",
                ):
                    self.apply(identifier)
        write.assert_called_once()
        with self.assertRaisesRegex(allocation.AllocationStopped, "OUTCOME_UNKNOWN"):
            self.reconcile(identifier)

    def test_restart_after_claim_before_write_is_reconciliation_only(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(
            self.provider,
            "read",
            side_effect=[SNAPSHOT, SNAPSHOT, SystemExit()],
        ):
            with self.assertRaises(SystemExit):
                self.apply(identifier)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )
        with self.assertRaisesRegex(allocation.AllocationStopped, "ALREADY_ATTEMPTED"):
            self.apply(identifier)
        with self.assertRaisesRegex(allocation.AllocationStopped, "OUTCOME_UNKNOWN"):
            self.reconcile(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_restart_after_provider_applied_comment_recovers_without_write(
        self,
    ) -> None:
        identifier = self.prepare()
        real = self.provider.assign_comment
        def killed(*args):
            real(*args)
            raise SystemExit()
        with mock.patch.object(self.provider, "assign_comment", side_effect=killed):
            with self.assertRaises(SystemExit):
                self.apply(identifier)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )
        self.assertEqual(
            self.reconcile(identifier),
            allocation.Outcome.RECEIPT_RECONCILED,
        )
        self.assertEqual(len(self.provider.writes), 1)

    def test_replay_completed_apply_is_blocked_but_receipt_can_be_reverified(
        self,
    ) -> None:
        identifier = self.prepare()
        self.apply(identifier)
        with self.assertRaisesRegex(allocation.AllocationStopped, "ALREADY_ATTEMPTED"):
            self.apply(identifier)
        self.assertEqual(
            self.reconcile(identifier),
            allocation.Outcome.RECEIPT_REVERIFIED,
        )
        self.assertEqual(len(self.provider.writes), 1)
        self.assertEqual(self.journal.events.count("RECEIPT_SAVED"), 1)

    def test_expired_attempt_can_only_be_observed_not_reapplied(self) -> None:
        identifier = self.prepare()
        real = self.provider.assign_comment
        def killed(*args):
            real(*args)
            raise SystemExit()
        with mock.patch.object(self.provider, "assign_comment", side_effect=killed):
            with self.assertRaises(SystemExit):
                self.apply(identifier)
        self.clock.return_value = NOW + 7200
        with self.assertRaisesRegex(allocation.AllocationStopped, "ALREADY_ATTEMPTED"):
            self.apply(identifier)
        self.assertEqual(
            self.reconcile(identifier),
            allocation.Outcome.RECEIPT_RECONCILED,
        )
        self.assertEqual(len(self.provider.writes), 1)

    def test_receipt_requires_two_agreeing_observations(self) -> None:
        identifier = self.prepare()
        expected = replace(SNAPSHOT, comment=allocation.expected_marker(SNAPSHOT))
        reads = [SNAPSHOT, SNAPSHOT, SNAPSHOT, expected, SNAPSHOT]
        with mock.patch.object(self.provider, "read", side_effect=reads):
            with self.assertRaisesRegex(allocation.AllocationStopped, "RECEIPT_DRIFT"):
                self.apply(identifier)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )
        self.assertEqual(len(self.provider.writes), 1)

    def test_wrong_postwrite_identity_does_not_become_success(self) -> None:
        identifier = self.prepare()
        def reassigned(*args):
            self.provider.snapshot = replace(SNAPSHOT, comment="foreign")
        with mock.patch.object(
            self.provider,
            "assign_comment",
            side_effect=reassigned,
        ) as write:
            with self.assertRaisesRegex(allocation.AllocationStopped, "RECEIPT_DRIFT"):
                self.apply(identifier)
        write.assert_called_once()
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )

    def test_completion_save_failure_stays_reconcilable(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(
            self.journal,
            "complete",
            side_effect=OSError("private"),
        ):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "RECEIPT_SAVE_UNPROVEN",
            ):
                self.apply(identifier)
        self.assertEqual(
            self.reconcile(identifier),
            allocation.Outcome.RECEIPT_RECONCILED,
        )
        self.assertEqual(len(self.provider.writes), 1)

    def test_noop_completion_cannot_claim_receipt_saved(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(self.journal, "complete"):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "RECEIPT_SAVE_UNPROVEN",
            ):
                self.apply(identifier)
        self.assertEqual(len(self.provider.writes), 1)

    def test_get_failure_after_write_retains_durable_claim(self) -> None:
        identifier = self.prepare()
        with mock.patch.object(
            self.provider,
            "read",
            side_effect=[SNAPSHOT, SNAPSHOT, SNAPSHOT, OSError("private")],
        ):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "OBSERVATION_UNAVAILABLE",
            ):
                self.apply(identifier)
        self.assertEqual(len(self.provider.writes), 1)
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )

    def test_unattempted_plan_cannot_be_reported_as_allocated_by_reconcile(
        self,
    ) -> None:
        identifier = self.prepare()
        self.provider.snapshot = replace(
            SNAPSHOT,
            comment=allocation.expected_marker(SNAPSHOT),
        )
        with self.assertRaisesRegex(allocation.AllocationStopped, "NOT_ATTEMPTED"):
            self.reconcile(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_missing_attempt_approval_receipt_is_not_trusted(self) -> None:
        identifier = self.prepare()
        self.journal.entries[identifier] = replace(
            self.journal.read(identifier),
            phase=allocation.Phase.ATTEMPTED,
        )
        with self.assertRaisesRegex(allocation.AllocationStopped, "CLAIM_UNPROVEN"):
            self.reconcile(identifier)

    def test_concurrent_apply_has_at_most_one_metadata_write(self) -> None:
        identifier = self.prepare()
        def call(_index):
            try:
                return self.apply(identifier)
            except allocation.AllocationStopped:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(call, range(24)))
        self.assertEqual(results.count(allocation.Outcome.ALLOCATED_VERIFIED), 1)
        self.assertEqual(len(self.provider.writes), 1)
        self.assertEqual(self.journal.events.count("ATTEMPT_DURABLE"), 1)

    def test_repr_and_safe_summary_contain_no_private_plan_values(self) -> None:
        identifier = self.prepare()
        entry = self.journal.read(identifier)
        summary = allocation.safe_summary(identifier, "OWNER_APPROVAL_REQUIRED")
        for obj in (entry, entry.plan, entry.plan.snapshot, entry.plan.context):
            for value in (
                SNAPSHOT.account_scope,
                SNAPSHOT.project_id,
                SNAPSHOT.floating_id,
                SNAPSHOT.ip_address,
                entry.plan.digest,
            ):
                self.assertNotIn(value, repr(obj))
                self.assertNotIn(value, summary)
        self.assertNotIn("=READY", summary)
        self.assertNotIn("=PASS", summary)
        self.assertIn("OWNER_APPROVAL_REQUIRED", summary)

    def test_unsafe_summary_state_or_identifier_cannot_be_emitted(self) -> None:
        identifier = self.prepare()
        for state in ("READY", "PASS", "foreign\nvalue", "", None):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "SUMMARY_INVALID",
            ):
                allocation.safe_summary(identifier, state)
        for bad in (None, "8.8.4.4", "id\nname"):
            with self.assertRaisesRegex(
                allocation.AllocationStopped,
                "SUMMARY_INVALID",
            ):
                allocation.safe_summary(bad, "OWNER_APPROVAL_REQUIRED")

    def test_clock_malformed_or_unavailable_is_not_approval(self) -> None:
        for value in (True, 0, -1, 1.5, "1700000000"):
            self.clock.return_value = value
            with self.assertRaisesRegex(allocation.AllocationStopped, "CLOCK_INVALID"):
                self.prepare()
        self.assertEqual(self.provider.writes, [])

    def test_latest_main_is_rechecked_after_claim_before_provider_write(self) -> None:
        identifier = self.prepare()
        self.read_context.side_effect = [CONTEXT, allocation.Context(OTHER, OTHER)]
        with self.assertRaisesRegex(allocation.AllocationStopped, "SOURCE_DRIFT"):
            self.apply(identifier)
        self.assertEqual(self.provider.writes, [])
        self.assertEqual(
            self.journal.read(identifier).phase,
            allocation.Phase.ATTEMPTED,
        )

    def test_current_main_read_failure_never_authorizes_write(self) -> None:
        identifier = self.prepare()
        self.read_context.side_effect = OSError("private GitHub metadata")
        with self.assertRaisesRegex(
            allocation.AllocationStopped,
            "MAIN_OBSERVATION_UNAVAILABLE",
        ) as raised:
            self.apply(identifier)
        self.assertEqual(self.provider.writes, [])
        self.assertNotIn("private", str(raised.exception))

    def test_malformed_closed_journal_payloads_fail_before_write(self) -> None:
        identifier = self.prepare()
        original = self.journal.read(identifier)
        payloads = (
            None,
            replace(original, phase=True),
            replace(original, plan=None),
        )
        for payload in payloads:
            with mock.patch.object(self.journal, "read", return_value=payload):
                with self.assertRaises(allocation.AllocationStopped):
                    self.apply(identifier)
        self.assertEqual(self.provider.writes, [])

    def test_plan_save_cannot_return_an_already_claimed_record(self) -> None:
        original_create = self.journal.create
        def wrong_phase(plan):
            original_create(plan)
            self.journal.entries[plan.identifier] = allocation.Entry(
                plan, allocation.Phase.ATTEMPTED, APPROVAL_REF
            )
        with mock.patch.object(self.journal, "create", side_effect=wrong_phase):
            with self.assertRaisesRegex(allocation.AllocationStopped, "SAVE_UNPROVEN"):
                self.prepare()
        self.assertEqual(self.provider.writes, [])

    def test_marker_protocol_is_reused_not_reimplemented(self) -> None:
        with mock.patch.object(custody, "marker", wraps=custody.marker) as marker:
            value = allocation.expected_marker(SNAPSHOT)
        marker.assert_called_once()
        self.assertEqual(marker.call_args.args[0], SNAPSHOT.cluster_id)
        row = marker.call_args.args[1]
        self.assertEqual(row.identifier, SNAPSHOT.floating_id)
        self.assertEqual(row.ip_address, SNAPSHOT.ip_address)
        self.assertEqual(value, custody.marker(SNAPSHOT.cluster_id, row))


if __name__ == "__main__":
    unittest.main()
