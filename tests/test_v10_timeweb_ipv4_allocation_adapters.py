from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from scripts import timeweb_ipv4_allocation as protocol
from scripts import timeweb_ipv4_allocation_github as github
from scripts import timeweb_ipv4_allocation_journal as storage
from scripts import timeweb_ipv4_allocation_windows as windows


NOW = 1_800_468_000
CONTEXT = protocol.Context("a" * 40, "a" * 40)


def make_plan(identifier: str = "1" * 32, *, issued_at: int = NOW) -> protocol.Plan:
    snapshot = protocol.Snapshot(
        "fixture-account",
        "fixture-project",
        91,
        "fixture-ip",
        "8.8.4.4",
        "",
    )
    expires_at = issued_at + protocol.PLAN_TTL_SECONDS
    digest = protocol._private_digest(
        identifier,
        CONTEXT,
        snapshot,
        issued_at,
        expires_at,
    )
    return protocol.Plan(identifier, CONTEXT, snapshot, issued_at, expires_at, digest)


def fake_codec(value: bytes) -> bytes:
    """Test-only reversible codec; never production encryption evidence."""
    return value[::-1]


class JournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "allocation.sqlite3"
        self.plan = make_plan()
        self.journal = self.open(initialize=True)

    def open(self, *, initialize: bool = False) -> storage.SqliteJournal:
        return storage.SqliteJournal(
            self.path, protect=fake_codec, unprotect=fake_codec,
            verify_location=lambda: None, initialize=initialize,
        )

    def test_restart_preserves_attempt_and_receipt(self) -> None:
        self.journal.create(self.plan)
        self.assertTrue(self.open().claim(self.plan.identifier, self.plan.digest, "7"))
        reopened = self.open()
        self.assertIs(
            reopened.read(self.plan.identifier).phase,
            protocol.Phase.ATTEMPTED,
        )
        self.assertFalse(reopened.claim(self.plan.identifier, self.plan.digest, "8"))
        reopened.complete(self.plan.identifier, self.plan.digest)
        saved = self.open().read(self.plan.identifier)
        self.assertIs(saved.phase, protocol.Phase.ALLOCATED)
        self.assertEqual(saved.approval_reference, "7")

    def test_independent_connections_have_one_claim_winner(self) -> None:
        self.journal.create(self.plan)
        with ThreadPoolExecutor(max_workers=4) as pool:
            answers = list(pool.map(
                lambda _: self.open().claim(
                    self.plan.identifier,
                    self.plan.digest,
                    "7",
                ),
                range(4),
            ))
        self.assertEqual(answers.count(True), 1)
        self.assertEqual(answers.count(False), 3)

    def test_expired_attempt_still_blocks_new_plan(self) -> None:
        self.journal.create(self.plan)
        self.journal.claim(self.plan.identifier, self.plan.digest, "7")
        later = make_plan("2" * 32, issued_at=self.plan.expires_at + 1)
        reopened = self.open()
        with self.assertRaises(storage.JournalError):
            reopened.create(later)
        self.assertIs(
            self.open().read(self.plan.identifier).phase,
            protocol.Phase.ATTEMPTED,
        )

    def test_expired_unattempted_plan_can_be_replanned_without_overwrite(self) -> None:
        self.journal.create(self.plan)
        later = make_plan("2" * 32, issued_at=self.plan.expires_at + 1)
        self.open().create(later)
        self.assertEqual(self.open().read(self.plan.identifier).plan, self.plan)
        self.assertEqual(self.open().read(later.identifier).plan, later)

    def test_superseded_plan_cannot_be_claimed_after_clock_rollback(self) -> None:
        self.journal.create(self.plan)
        later = make_plan("2" * 32, issued_at=self.plan.expires_at + 1)
        self.journal.create(later)
        reopened = self.open()
        with self.assertRaises(storage.JournalError):
            reopened.claim(self.plan.identifier, self.plan.digest, "7")
        self.assertTrue(self.open().claim(later.identifier, later.digest, "8"))

    def test_existing_empty_store_is_not_silently_reinitialized(self) -> None:
        self.path.write_bytes(b"")
        with self.assertRaises(storage.JournalError):
            self.open(initialize=True)

    def test_live_plan_conflict_and_duplicate_id_are_rejected(self) -> None:
        self.journal.create(self.plan)
        for candidate in (self.plan, make_plan("2" * 32)):
            with self.subTest(identifier=candidate.identifier):
                reopened = self.open()
                with self.assertRaises(storage.JournalError):
                    reopened.create(candidate)

    def test_completion_without_claim_or_with_wrong_digest_is_rejected(self) -> None:
        self.journal.create(self.plan)
        with self.assertRaises(storage.JournalError):
            self.journal.complete(self.plan.identifier, self.plan.digest)
        with self.assertRaises(storage.JournalError):
            self.journal.claim(self.plan.identifier, "wrong", "7")
        self.journal.claim(self.plan.identifier, self.plan.digest, "7")
        with self.assertRaises(storage.JournalError):
            self.journal.complete(self.plan.identifier, "wrong")

    def test_unknown_id_missing_store_and_corrupt_record_fail_closed(self) -> None:
        reopened = self.open()
        with self.assertRaises(storage.JournalError):
            reopened.read("2" * 32)
        other = self.path.with_name("missing.sqlite3")
        with self.assertRaises(storage.JournalError):
            storage.SqliteJournal(other, verify_location=lambda: None)
        self.assertFalse(other.exists())
        self.journal.create(self.plan)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE allocation SET sealed=?", (b"corrupt",))
        with self.assertRaises(storage.JournalError):
            self.open()

    def test_cipher_failure_does_not_commit_claim(self) -> None:
        self.journal.create(self.plan)
        with mock.patch.object(
            self.journal,
            "_protect",
            side_effect=OSError("private"),
        ):
            with self.assertRaises(storage.JournalError) as error:
                self.journal.claim(self.plan.identifier, self.plan.digest, "7")
        self.assertNotIn("private", str(error.exception))
        self.assertIs(
            self.open().read(self.plan.identifier).phase,
            protocol.Phase.PLANNED,
        )

    def test_location_rechecked_before_each_transaction(self) -> None:
        self.journal.create(self.plan)
        self.journal._verify_location = mock.Mock(side_effect=OSError("unsafe"))
        with self.assertRaises(storage.JournalError):
            self.journal.claim(self.plan.identifier, self.plan.digest, "7")
        self.assertIs(
            self.open().read(self.plan.identifier).phase,
            protocol.Phase.PLANNED,
        )

    def test_mismatched_ciphertext_handle_is_rejected(self) -> None:
        self.journal.create(self.plan)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE allocation SET handle=?", ("2" * 32,))
        with self.assertRaises(storage.JournalError):
            self.open()

    def test_claim_requires_nonempty_approval_reference(self) -> None:
        self.journal.create(self.plan)
        with self.assertRaises(storage.JournalError):
            self.journal.claim(self.plan.identifier, self.plan.digest, "")
        self.assertIs(
            self.open().read(self.plan.identifier).phase,
            protocol.Phase.PLANNED,
        )

    @unittest.skipUnless(os.name == "nt", "Windows native DPAPI/ACL proof")
    def test_native_dpapi_acl_restart_and_tamper_rejection(self) -> None:
        root = Path(self.directory.name) / "native"
        journal = storage.SqliteJournal(
            root / "allocation.sqlite3",
            verify_location=lambda: windows.verify_directory(root),
            initialize=True,
        )
        journal.create(self.plan)
        reopened = storage.SqliteJournal(
            root / "allocation.sqlite3",
            verify_location=lambda: windows.verify_directory(root),
        )
        self.assertEqual(reopened.read(self.plan.identifier).plan, self.plan)
        on_disk = (root / "allocation.sqlite3").read_bytes()
        for private in (
            b"fixture-account",
            b"fixture-project",
            b"fixture-ip",
            b"8.8.4.4",
        ):
            self.assertNotIn(private, on_disk)
        sealed = storage.dpapi(b"synthetic-private-record")
        self.assertEqual(
            storage.dpapi(sealed, decrypt=True),
            b"synthetic-private-record",
        )
        corrupted = bytes([sealed[0] ^ 1]) + sealed[1:]
        with self.assertRaises(storage.JournalError):
            storage.dpapi(corrupted, decrypt=True)


class GitHubApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = make_plan()
        timestamp = datetime.fromtimestamp(
            NOW,
            timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.repo = {
            "full_name": protocol.REPOSITORY,
            "private": True,
            "owner": {"type": "User", "id": 7, "login": "MishaGameHacking"},
        }
        self.comment = {
            "id": 17, "issue_url": github._ISSUE_URL, "author_association": "OWNER",
            "user": self.repo["owner"].copy(), "performed_via_github_app": None,
            "body": github.approval_body(self.plan), "created_at": timestamp,
            "updated_at": timestamp,
        }
        self.ref = {
            "ref": "refs/heads/main",
            "object": {"type": "commit", "sha": CONTEXT.source_sha},
        }
        self.paths: list[str] = []
        self.verifier = github.GitHubApprovalVerifier(
            "fixture-token",
            read_json=self.read,
        )

    def read(self, path: str) -> dict:
        self.paths.append(path)
        if path == github._PREFIX:
            return copy.deepcopy(self.repo)
        if path == github._PREFIX + "/issues/comments/17":
            return copy.deepcopy(self.comment)
        if path == github._PREFIX + "/git/ref/heads/main":
            return copy.deepcopy(self.ref)
        raise AssertionError("unapproved endpoint")

    def test_owner_evidence_binds_plan_source_purpose_and_expiry(self) -> None:
        proof = self.verifier.verify("17", self.plan, NOW + 1)
        self.assertEqual(proof.plan_digest, self.plan.digest)
        self.assertEqual(proof.source_sha, CONTEXT.source_sha)
        self.assertEqual(proof.expires_at, self.plan.expires_at)
        self.assertEqual(proof.purpose, protocol.ALLOCATE_CONFIRMATION)
        self.assertEqual(len(self.paths), 3)

    def test_connector_comment_attributed_to_owner_is_not_approval(self) -> None:
        self.comment["performed_via_github_app"] = {"slug": "chatgpt-codex-connector"}
        with self.assertRaises(protocol.AllocationStopped):
            self.verifier.verify("17", self.plan, NOW + 1)

    def test_missing_app_attribution_is_not_assumed_human(self) -> None:
        del self.comment["performed_via_github_app"]
        with self.assertRaises(protocol.AllocationStopped):
            self.verifier.verify("17", self.plan, NOW + 1)

    def test_changed_body_author_scope_or_identity_is_rejected(self) -> None:
        changes = (
            {"body": "approve development"}, {"id": True}, {"id": 18},
            {"author_association": "MEMBER"}, {"issue_url": github._ISSUE_URL + "0"},
            {"updated_at": "2026-09-20T19:00:00Z"},
            {"user": {"type": "User", "id": 8, "login": "MishaGameHacking"}},
            {"user": {"type": "Bot", "id": 7, "login": "MishaGameHacking"}},
        )
        original = copy.deepcopy(self.comment)
        for change in changes:
            self.comment = original | change
            with self.subTest(change=change):
                with self.assertRaises(protocol.AllocationStopped):
                    self.verifier.verify("17", self.plan, NOW + 1)

    def test_edited_deleted_or_expired_approval_is_rechecked(self) -> None:
        self.verifier.verify("17", self.plan, NOW + 1)
        self.comment["body"] = "REVOKED"
        with self.assertRaises(protocol.AllocationStopped):
            self.verifier.verify("17", self.plan, NOW + 1)
        with self.assertRaises(protocol.AllocationStopped):
            self.verifier.verify("17", self.plan, self.plan.expires_at)
        with mock.patch.object(
            self.verifier,
            "_reader",
            side_effect=OSError("private-token"),
        ):
            with self.assertRaises(protocol.AllocationStopped) as error:
                self.verifier.verify("17", self.plan, NOW + 1)
        self.assertNotIn("private-token", str(error.exception))

    def test_main_drift_wrong_repo_and_malformed_reference_are_rejected(self) -> None:
        for reference in ("0", "017", "../17", "17\n", "1\u0667"):
            with self.subTest(reference=reference):
                with self.assertRaises(protocol.AllocationStopped):
                    self.verifier.verify(reference, self.plan, NOW + 1)
        self.ref["object"]["sha"] = "b" * 40
        with self.assertRaises(protocol.AllocationStopped):
            self.verifier.verify("17", self.plan, NOW + 1)
        self.repo["private"] = False
        with self.assertRaises(protocol.AllocationStopped):
            self.verifier.verify("17", self.plan, NOW + 1)

    def test_approval_text_contains_no_private_snapshot_or_digest(self) -> None:
        text = github.approval_body(self.plan)
        for value in (
            self.plan.digest,
            self.plan.snapshot.account_scope,
            self.plan.snapshot.floating_id,
            self.plan.snapshot.ip_address,
        ):
            self.assertNotIn(value, text)
        with self.assertRaises(protocol.AllocationStopped):
            github.GitHubApprovalVerifier("")


if __name__ == "__main__":
    unittest.main()
