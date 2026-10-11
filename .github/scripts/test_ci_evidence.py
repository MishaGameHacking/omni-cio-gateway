"""Verify complete, attributable evidence survives without GitHub artifact storage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

import ci_evidence as evidence


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "checkout"
        self.cache = Path(self.temporary.name) / "cache"
        self.root.mkdir()
        self.identity = {
            "run_id": "123", "attempt": "2", "source_sha": "a" * 40,
            "workflow_sha": "b" * 40, "runner": "test-runner", "outcome": "success",
        }

    def write(self, path: str, data: bytes) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def test_full_evidence_and_source_identity_survive_in_verified_archive(self) -> None:
        xml = b'<testsuites><testsuite tests="10" failures="0" errors="0"/></testsuites>'
        self.write("artifacts/postgres/pytest.xml", xml)
        self.write("artifacts/postgres/server.log", b"database stopped cleanly")
        result = evidence.archive(self.root, self.cache, "postgres", self.identity)
        archive = Path(result["archive"])
        self.assertEqual(result["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        with zipfile.ZipFile(archive) as saved:
            self.assertIsNone(saved.testzip())
            self.assertEqual(saved.read("artifacts/postgres/pytest.xml"), xml)
            manifest = json.loads(saved.read("manifest.json"))
            self.assertEqual(manifest["source_sha"], "a" * 40)
            self.assertEqual(manifest["workflow_sha"], "b" * 40)
            self.assertEqual(len(manifest["files"]), 2)
            for item in manifest["files"]:
                self.assertEqual(
                    item["sha256"], hashlib.sha256(saved.read(item["path"])).hexdigest(),
                )
        self.assertIn('"tests": "10"', evidence.report(result, self.root))

    def test_missing_success_evidence_fails_instead_of_creating_green_result(self) -> None:
        for kind in evidence.PATTERNS:
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "missing"):
                evidence.archive(self.root, self.cache, kind, self.identity)

    def test_failed_test_preserves_partial_diagnostics_and_failure_outcome(self) -> None:
        self.write("artifacts/frontend/failure-state.json", b'{"overflow": true}')
        result = evidence.archive(
            self.root, self.cache, "frontend", self.identity | {"outcome": "failure"},
        )
        self.assertEqual(result["outcome"], "failure")
        with zipfile.ZipFile(result["archive"]) as saved:
            self.assertIn("artifacts/frontend/failure-state.json", saved.namelist())

    def test_archive_paths_cannot_escape_cache(self) -> None:
        for field in ("run_id", "attempt", "source_sha", "workflow_sha"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.archive(self.root, self.cache, "frontend", self.identity | {field: "../x"})
        self.assertFalse(self.cache.exists())

    def test_unrelated_or_private_files_never_enter_archive(self) -> None:
        self.write("artifacts/frontend/public-320.png", b"screenshot")
        self.write("artifacts/frontend/secret.key", b"must not be retained")
        result = evidence.archive(
            self.root, self.cache, "frontend", self.identity | {"outcome": "failure"},
        )
        self.assertEqual([row["path"] for row in result["files"]],
                         ["artifacts/frontend/public-320.png"])

    def test_pruning_only_removes_expired_owned_cache_files(self) -> None:
        destination = self.cache / "omnicio-ci-evidence"
        destination.mkdir(parents=True)
        for name in ("postgres-1-1.zip", "android-2-1.zip", "owner-backup.zip"):
            (destination / name).write_bytes(b"old")
        expired = time.time() - evidence.RETENTION_SECONDS - 60
        for name in ("postgres-1-1.zip", "owner-backup.zip"):
            os.utime(destination / name, (expired, expired))
        evidence.archive(self.root, self.cache, "frontend", self.identity | {"outcome": "failure"})
        self.assertFalse((destination / "postgres-1-1.zip").exists())
        self.assertTrue((destination / "android-2-1.zip").exists())
        self.assertTrue((destination / "owner-backup.zip").exists())


if __name__ == "__main__":
    unittest.main()
