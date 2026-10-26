"""Real local Git/file tamper fixtures for the laptop Android CI boundary.

These tests do not start Gradle, an emulator, a cloud operation or publication.
The repository's host suite must run them on the authorized Windows laptop.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile


MODULE = Path(__file__).resolve().parents[1] / "windows_android_ci.py"
SPEC = importlib.util.spec_from_file_location("windows_android_ci", MODULE)
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class ArchiveReferenceTests(unittest.TestCase):
    def archive(self, runner="actions-runner-2", run="1001", attempt="1"):
        return rf"C:\{runner}\_work\omni-cio-gateway\omni-cio-gateway\android-ci-build-{run}-{attempt}\handoff\ci-apk-inputs.zip"

    def test_four_existing_runner_roots_and_retained_previous_attempt(self):
        for runner in ci.RUNNER_NAMES:
            with self.subTest(runner=runner):
                value = self.archive(runner)
                self.assertEqual(ci.archive_reference(value, "1001", "1", "2"), PureWindowsPath(value))

    def test_foreign_run_machine_escape_unc_and_future_attempt_are_rejected(self):
        bad = (
            self.archive("actions-runner-1"), self.archive("actions-runner-5"),
            self.archive(run="1002"), self.archive().replace("handoff", "..\\handoff"),
            self.archive().replace("C:", "D:"), self.archive().replace("ci-apk-inputs.zip", "other.zip"),
            "\\\\server\\share\\ci-apk-inputs.zip", "relative\\ci-apk-inputs.zip",
        )
        for value in bad:
            with self.subTest(path=value), self.assertRaises(RuntimeError):
                ci.archive_reference(value, "1001", "1", "2")
        with self.assertRaisesRegex(RuntimeError, "invalid_build_attempt"):
            ci.archive_reference(self.archive(attempt="3"), "1001", "3", "2")

    def test_retained_runtime_is_separate_from_build_and_other_attempts(self):
        value = r"C:\actions-runner-4\_work\omni-cio-gateway\omni-cio-gateway\android-ci-runtime-1001-1\source"
        self.assertEqual(ci.runtime_reference(value, "1001", "1", "2"), PureWindowsPath(value))
        for wrong in (value.replace("runtime-", "build-"), value.replace("1001-", "1002-"),
                      value.replace("actions-runner-4", "actions-runner-5"), value + "\\..\\source"):
            with self.subTest(path=wrong), self.assertRaises(RuntimeError):
                ci.runtime_reference(wrong, "1001", "1", "2")


class SourceAndTransferTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="android-ci-contract-")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).resolve()
        self.root = self.base / "runtime-source"
        self.root.mkdir()
        self.assertIsNotNone(shutil.which("git"), "Git is required on the signing laptop")
        self.git("init", "--template=", "-b", "main")
        self.git("config", "user.name", "Synthetic CI contract")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        (self.root / "module.py").write_bytes(b"VALUE = 1\n")
        (self.root / "empty.py").write_bytes(b"")
        self.git("add", "--all")
        self.git("commit", "-m", "synthetic source")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.identity = {"repository": ci.REPOSITORY, "event": "workflow_dispatch", "tested_merge_sha": self.head,
                         "pr_head_sha": self.head, "pr_base_sha": self.head, "pr_number": "",
                         "run_id": "1001", "run_attempt": "2"}

    def git(self, *args, input=None):
        return subprocess.run(["git", *args], cwd=self.root, input=input, capture_output=True,
                              check=True, timeout=30).stdout

    def test_committed_source_and_zero_byte_file_are_attested(self):
        source = ci.source_identity(self.root, self.identity)
        self.assertEqual(set(source["files"]), {"module.py", "empty.py"})
        self.assertEqual(source["files"]["empty.py"]["bytes"], 0)
        self.assertEqual(source["files"]["empty.py"]["git_blob"], ci.git_blob(b""))

    def test_worktree_tamper_is_rejected_even_with_assume_unchanged(self):
        self.git("update-index", "--assume-unchanged", "module.py")
        (self.root / "module.py").write_bytes(b"VALUE = 2\n")
        self.assertEqual(self.git("status", "--porcelain"), b"")
        with self.assertRaisesRegex(RuntimeError, "source_bytes_differ_from_tested_commit"):
            ci.source_identity(self.root, self.identity)

    def test_skip_worktree_does_not_hide_modified_source(self):
        self.git("update-index", "--skip-worktree", "module.py")
        (self.root / "module.py").write_bytes(b"VALUE = 3\n")
        with self.assertRaisesRegex(RuntimeError, "source_bytes_differ_from_tested_commit"):
            ci.source_identity(self.root, self.identity)

    def test_untracked_executable_and_staged_changes_are_rejected(self):
        extra = self.root / "injected.py"
        extra.write_bytes(b"raise RuntimeError('synthetic')\n")
        with self.assertRaisesRegex(RuntimeError, "untracked_source_file"):
            ci.source_identity(self.root, self.identity)
        extra.unlink()
        (self.root / "module.py").write_bytes(b"VALUE = 4\n")
        self.git("add", "module.py")
        with self.assertRaisesRegex(RuntimeError, "index_differs_from_tested_commit"):
            ci.source_identity(self.root, self.identity)

    def test_raw_merge_parent_order_binds_base_and_head(self):
        base = self.head
        (self.root / "module.py").write_bytes(b"VALUE = 5\n")
        self.git("add", "module.py")
        self.git("commit", "-m", "synthetic PR head")
        head = self.git("rev-parse", "HEAD").decode().strip()
        tree = self.git("rev-parse", "HEAD^{tree}").decode().strip()
        merge = self.git("commit-tree", tree, "-p", base, "-p", head, input=b"synthetic merge\n").decode().strip()
        self.git("checkout", "--detach", merge)
        identity = {**self.identity, "event": "pull_request", "tested_merge_sha": merge,
                    "pr_head_sha": head, "pr_base_sha": base, "pr_number": "11"}
        self.assertEqual(ci.source_identity(self.root, identity)["merge_parents"], [base, head])
        with self.assertRaisesRegex(RuntimeError, "tested_merge_parents_differ"):
            ci.source_identity(self.root, {**identity, "pr_head_sha": base, "pr_base_sha": head})

    def transfer_fixture(self):
        source = ci.source_identity(self.root, self.identity)
        handoff = self.base / "build" / "handoff"
        handoff.mkdir(parents=True)
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("synthetic-input", b"fixed synthetic bytes")
        data = content.getvalue()
        archive = handoff / "ci-apk-inputs.zip"
        archive.write_bytes(data)
        receipt = {"schema": 1, "kind": "windows_android_ci_inputs", **self.identity, "run_attempt": "1",
                   "host": ci.HOST, "build_root": str(handoff.parent / "source"), "source": source,
                   "archive": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
                   "certificate_sha256": ci.CERTIFICATE_SHA256,
                   "build_controller": {"status": "passed", "owned_processes_after": 0}}
        receipt_path = handoff / "build-handoff.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        env = {"CI_INPUT_ARCHIVE": str(archive), "CI_INPUT_ATTEMPT": "1", "CI_INPUT_SHA256": receipt["archive"]["sha256"],
               "CI_INPUT_RECEIPT_SHA256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
        state = self.base / "runtime-state"
        state.mkdir()
        return archive, receipt_path, receipt, env, state, data

    def receive(self, archive, env, state):
        # Containment is tested separately against all four exact production
        # roots; use a real temporary file here to exercise the copy/hash boundary.
        with patch.dict(os.environ, env), patch.object(ci, "archive_reference", return_value=PureWindowsPath(str(archive))):
            return ci.receive_inputs(self.root, state, self.identity)

    def test_verified_archive_is_copied_to_new_runtime_state(self):
        archive, _, receipt, env, state, data = self.transfer_fixture()
        self.assertEqual(self.receive(archive, env, state), receipt)
        self.assertEqual((state / "ci-apk-inputs.zip").read_bytes(), data)
        self.assertEqual(ci.read_json(state / "build-handoff.json"), receipt)

    def test_modified_archive_never_creates_a_runtime_input(self):
        archive, _, _, env, state, data = self.transfer_fixture()
        archive.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        with self.assertRaisesRegex(RuntimeError, "build_archive_changed"):
            self.receive(archive, env, state)
        self.assertFalse((state / "ci-apk-inputs.zip").exists())

    def test_receipt_replacement_cannot_self_authorize_a_new_archive_hash(self):
        archive, receipt_path, receipt, env, state, _ = self.transfer_fixture()
        changed = b"a different synthetic archive"
        archive.write_bytes(changed)
        receipt["archive"] = {"bytes": len(changed), "sha256": hashlib.sha256(changed).hexdigest()}
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "build_receipt_changed"):
            self.receive(archive, env, state)
        self.assertFalse((state / "ci-apk-inputs.zip").exists())

    def test_exact_hashes_do_not_accept_wrong_source_or_live_owned_processes(self):
        archive, receipt_path, receipt, env, state, _ = self.transfer_fixture()
        for field, value, error in (("pr_head_sha", "a" * 40, "build_source_or_run_mismatch"),
                                    ("build_controller", {"status": "passed", "owned_processes_after": 1}, "build_cleanup_not_verified")):
            original = receipt[field]
            receipt[field] = value
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            env["CI_INPUT_RECEIPT_SHA256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, error):
                self.receive(archive, env, state)
            self.assertFalse((state / "ci-apk-inputs.zip").exists())
            receipt[field] = original

    def test_test_child_environment_removes_real_credentials_and_python_injection(self):
        home = self.base / "NetworkService"
        (home / ".gradle").mkdir(parents=True)
        (home / ".android").mkdir()
        original = dict(os.environ)
        for key in ("GRADLE_USER_HOME", "ANDROID_USER_HOME", "ANDROID_SDK_HOME"):
            original.pop(key, None)
        sensitive = {"GITHUB_TOKEN": "synthetic-job-secret", "GH_TOKEN": "synthetic-gh-secret",
                     "TIMEWEB_CLOUD_TOKEN": "synthetic-host-secret", "OPENAI_API_KEY": "synthetic-ai-secret",
                     "ACTIONS_RUNTIME_TOKEN": "synthetic-runtime-secret", "PYTHONPATH": "synthetic-module-injection",
                     "PYTHONHOME": "synthetic-python-home", "PYTHONOPTIMIZE": "1"}
        original.update(sensitive, USERPROFILE=str(home))
        with patch.dict(os.environ, original, clear=True):
            child, key = ci.test_environment(self.root, self.base)
        for name in sensitive:
            self.assertNotIn(name, child)
        self.assertEqual(child["AI_EXTERNAL_PROCESSING_APPROVED"], "false")
        self.assertEqual(child["RUN_PROFILE_UI_TESTS"], "1")
        self.assertEqual(child["FERNET_KEY"], "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        self.assertEqual(key, home / ".android/debug.keystore")

    def test_winapi_cleanup_error_still_closes_job_before_releasing_lease(self):
        state = self.base / "controller-state"
        state.mkdir()
        source = ci.source_identity(self.root, self.identity)
        ci.save(state / "source.json", source)
        ci.save(state / "identity.json", self.identity)
        scripts = self.root / ".github/scripts"
        scripts.mkdir(parents=True)
        (scripts / "emulator_lease.py").write_bytes((MODULE.parent / "emulator_lease.py").read_bytes())
        events = []

        class Lease:
            def __enter__(self):
                events.append("lease-acquired")

            def __exit__(self, *args):
                events.append("lease-released")

        class FailedJob:
            def attach(self, process):
                events.append("attached")

            def active(self):
                raise OSError("synthetic WinAPI accounting failure")

            def close(self):
                events.append("closed")

        process = Mock(pid=1234, returncode=0, stdin=io.BytesIO())
        process.poll.return_value = 0
        original_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        fake_lease = SimpleNamespace(exclusive_emulator=lambda: Lease())
        with patch.object(ci, "source_identity", return_value=source), \
             patch.object(ci, "test_environment", return_value=({}, None)), \
             patch.object(ci, "require_runtime_inputs"), \
             patch.object(ci, "OwnedJob", FailedJob), \
             patch.object(ci.subprocess, "Popen", return_value=process), \
             patch.dict(sys.modules, {"emulator_lease": fake_lease}):
            with self.assertRaisesRegex(OSError, "synthetic WinAPI"):
                ci.control(self.root, state, "validate", self.identity)
        self.assertEqual(events, ["lease-acquired", "attached", "closed", "lease-released"])
        result = ci.read_json(state / "validate-controller.json")
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["owned_processes_after"])
        process.kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
