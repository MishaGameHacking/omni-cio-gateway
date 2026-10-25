from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import io
import os
import stat
import sys
from types import SimpleNamespace
import zipfile

from backend.client_updates import ReleaseChannel, ReleaseUnavailable
from backend.installation_evidence import from_ci_reports
from backend.release_publication import publish
from backend.tests.android_runtime_fixtures import publication_report

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("workspace", Path(__file__).resolve().parents[1] / "timeweb_workspace.py")
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)

PUBLISH_SPEC = importlib.util.spec_from_file_location(
    "workspace_publisher",
    Path(__file__).resolve().parents[1] / "publish_timeweb_workspace.py",
)
publisher = importlib.util.module_from_spec(PUBLISH_SPEC)
PUBLISH_SPEC.loader.exec_module(publisher)



class WorkspaceEvidenceTests(unittest.TestCase):

    def test_workspace_and_public_service_share_release_directory(self):
        service = (
            Path(__file__).resolve().parents[1] / "public_updates.service"
        ).read_text()
        prefix = "Environment=ANDROID_RELEASE_DIR="
        paths = [line[len(prefix):] for line in service.splitlines()
                 if line.startswith(prefix)]
        self.assertEqual(paths, [str(workspace.PUBLIC_RELEASES)])


    def test_code_change_invalidates_passed_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "app.kt").write_text("before")
            state = root / ".git" / "checks"
            state.mkdir()
            with patch.object(workspace, "ROOT", root), patch.object(workspace, "STATE", state):
                before = workspace.source_hash()
                (state / "check-result.json").write_text(json.dumps({"status": "passed", "source_sha256": before}))
                workspace.previous("check", before)
                (root / "app.kt").write_text("after")
                with self.assertRaisesRegex(RuntimeError, "must_pass_for_current_sources"):
                    workspace.previous("check", workspace.source_hash())

    def test_failed_checks_do_not_authorize_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "check-result.json").write_text(json.dumps({"status": "failed", "source_sha256": "same"}))
            with patch.object(workspace, "STATE", state):
                with self.assertRaisesRegex(RuntimeError, "must_pass"):
                    workspace.previous("check", "same")

    def test_low_memory_stops_before_a_build(self):
        with patch.object(workspace, "memory_kib", return_value=1024 * 1024):
            for stage in ("build", "runtime"):
                with self.assertRaisesRegex(RuntimeError, "insufficient_physical_memory"):
                    workspace.require_capacity(stage)

    def test_documentation_does_not_change_build_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "app.kt").write_text("source")
            with patch.object(workspace, "ROOT", root):
                before = workspace.source_hash()
                (root / "AGENTS.md").write_text("updated operational record")
                (root / "docs").mkdir()
                (root / "docs" / "status.md").write_text("checks completed")
                self.assertEqual(before, workspace.source_hash())



class PublicUpgradePipelineTests(unittest.TestCase):
    """Synthetic files/receipts only; no Android run or real channel access."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.base.chmod(0o755)
        self.channel = self.base / "ota" / "releases"
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(
            patch.object(workspace, "PUBLIC_RELEASES", self.channel))
        original_lstat = Path.lstat

        def root_metadata(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == self.base or self.base in path.parents:
                fields = list(info)
                fields[4] = 0
                return os.stat_result(fields)
            return info

        self.stack.enter_context(patch.object(Path, "lstat", root_metadata))
        self.first = self.publish_current(37, b"synthetic public previous 37")

    def report(self, apk, version):
        raw = apk.read_bytes()
        return publication_report({
            "package": workspace.PREVIEW_PACKAGE,
            "version_code": version,
            "version_name": f"test-{version}",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "certificate_sha256": workspace.CERT,
            "signature_v2": True,
            "zipalign_16kb": True,
            "debuggable": False,
            "test_only": False,
        })

    def publish_current(self, version, content):
        source = self.base / f"input-{version}.apk"
        source.write_bytes(content)
        release = publish(
            self.channel, source, self.report(source, version),
            expected_certificate=workspace.CERT, now=100 + version,
        )
        for directory in (
            self.channel.parent, self.channel,
            self.channel / workspace.PREVIEW_PACKAGE,
        ):
            directory.chmod(0o755)
        return release

    def candidate_report(self, version=38, content=b"synthetic next candidate"):
        source = self.base / "candidate.apk"
        source.write_bytes(content)
        return self.report(source, version)

    def test_resolver_follows_current_without_a_version_pin(self):
        candidate = self.candidate_report(38)
        old, baseline = workspace.resolve_upgrade_baseline(
            candidate, candidate["sha256"])
        self.assertEqual(old.name, self.first.filename)
        self.assertEqual(baseline, workspace.public_release_identity(self.first))
        second = self.publish_current(38, b"synthetic public previous 38")
        candidate = self.candidate_report(39)
        old, baseline = workspace.resolve_upgrade_baseline(
            candidate, candidate["sha256"])
        self.assertEqual(old.name, second.filename)
        self.assertEqual(baseline, workspace.public_release_identity(second))

    def test_resolver_rejects_nonupgrade_and_changed_identity(self):
        for version in (36, 37, True, "38"):
            candidate = self.candidate_report(version)
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                workspace.resolve_upgrade_baseline(candidate, candidate["sha256"])
        for field, value in (
            ("package", "other.package"),
            ("certificate_sha256", "d" * 64),
            ("sha256", "e" * 64),
        ):
            candidate = self.candidate_report()
            digest = candidate["sha256"]
            candidate[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                workspace.resolve_upgrade_baseline(candidate, digest)
        candidate = self.candidate_report(
            38, content=b"synthetic public previous 37")
        with self.assertRaisesRegex(RuntimeError, "newer_distinct"):
            workspace.resolve_upgrade_baseline(candidate, candidate["sha256"])

    def test_resolver_verifies_actual_previous_bytes(self):
        path = self.channel / workspace.PREVIEW_PACKAGE / self.first.filename
        path.write_bytes(b"x" * self.first.apk_bytes)
        candidate = self.candidate_report()
        with self.assertRaises(ReleaseUnavailable):
            workspace.resolve_upgrade_baseline(candidate, candidate["sha256"])

    def test_public_path_guard_rejects_untrusted_or_unreadable_file(self):
        path = self.channel / workspace.PREVIEW_PACKAGE / self.first.filename
        for mode, uid, links in (
            (stat.S_IFREG | 0o644, 1, 1),
            (stat.S_IFREG | 0o646, 0, 1),
            (stat.S_IFREG | 0o640, 0, 1),
            (stat.S_IFLNK | 0o777, 0, 1),
            (stat.S_IFREG | 0o644, 0, 2),
        ):
            info = SimpleNamespace(st_mode=mode, st_uid=uid, st_nlink=links)
            with self.subTest(mode=mode, uid=uid, links=links):
                with patch.object(Path, "lstat", return_value=info):
                    with self.assertRaises(RuntimeError):
                        workspace.require_public_path(path)

    def test_actual_previous_receipt_must_match_frozen_baseline(self):
        baseline = workspace.public_release_identity(self.first)
        path = self.base / "install-results.json"
        valid = [{
            "test": "previous_clean_install",
            "success": True,
            "apk_sha256": self.first.apk_sha256,
        }]
        path.write_text(json.dumps(valid))
        workspace.require_upgrade_baseline_transcript(path, baseline)
        wrong = deepcopy(valid)
        wrong[0]["apk_sha256"] = "e" * 64
        failed = deepcopy(valid)
        failed[0]["success"] = False
        for rows in ([], valid + valid, wrong, failed):
            path.write_text(json.dumps(rows))
            with self.subTest(rows=rows), self.assertRaisesRegex(
                RuntimeError, "baseline_transcript"
            ):
                workspace.require_upgrade_baseline_transcript(path, baseline)

    def run_publisher(self, version, baseline):
        checkout = self.base / "checkout"
        out = checkout / "app/build/outputs/apk/preview"
        out.mkdir(parents=True, exist_ok=True)
        apk = out / "app-preview.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr(
                "classes.dex",
                b"synthetic fixture " + workspace.HOST.encode()
                + b" " + str(version).encode(),
            )
        report = self.report(apk, version)
        for run in report["installation_tests"]:
            for row in run["results"]:
                if row["test"] == "previous_clean_install":
                    row["apk_sha256"] = baseline["apk_sha256"]
        report["installation_evidence"] = from_ci_reports(
            report["installation_tests"], report["sha256"])
        (out / "apk-verification.json").write_text(json.dumps(report))
        state = self.base / "state"
        state.mkdir(exist_ok=True)
        source_digest = "d" * 64
        for stage in ("check", "build", "runtime"):
            receipt = {
                "status": "passed", "source_sha256": source_digest,
                "apk_sha256": report["sha256"],
            }
            if stage == "runtime":
                receipt["upgrade_baseline"] = baseline
            (state / f"{stage}-result.json").write_text(json.dumps(receipt))
        self.publish_calls = 0

        def fixture_channel(root):
            self.assertEqual(Path(root), self.channel,
                             "test refuses access to any non-fixture channel")
            return ReleaseChannel(root)

        def fixture_publish(root, *args, **kwargs):
            self.assertEqual(Path(root), self.channel,
                             "test refuses publication outside its fixture")
            self.publish_calls += 1
            return publish(root, *args, **kwargs)

        class Response(io.BytesIO):
            status = 200

        def fixture_http(request, timeout):
            url = request.full_url if hasattr(request, "full_url") else request
            channel = ReleaseChannel(self.channel)
            if url.startswith(workspace.HOST + "/client/update-policy?"):
                body = json.dumps(
                    channel.current(workspace.PREVIEW_PACKAGE).public()).encode()
            elif url.startswith(workspace.HOST + "/client/apk/"):
                filename = url.rsplit("/", 1)[1]
                release = channel.published(workspace.PREVIEW_PACKAGE, filename)
                body = channel.verified_file(release).read_bytes()
            else:
                self.fail("test refuses an unexpected HTTP target")
            return Response(body)

        spec = SimpleNamespace(
            loader=SimpleNamespace(exec_module=lambda module: None))
        saved_cwd, saved_path = os.getcwd(), list(sys.path)
        try:
            with ExitStack() as stack:
                for context in (
                    patch.object(publisher, "ROOT", checkout),
                    patch.object(publisher, "BACKUP", self.base / "backups"),
                    patch.object(workspace, "ROOT", checkout),
                    patch.object(workspace, "STATE", state),
                    patch.object(workspace, "source_hash",
                                 return_value=source_digest),
                    patch.object(publisher.os, "geteuid", return_value=0),
                    patch.object(publisher.importlib.util,
                                 "spec_from_file_location", return_value=spec),
                    patch.object(publisher.importlib.util,
                                 "module_from_spec", return_value=workspace),
                    patch("backend.client_updates.ReleaseChannel",
                          side_effect=fixture_channel),
                    patch("backend.release_publication.publish",
                          side_effect=fixture_publish),
                    patch.object(publisher.urllib.request, "urlopen",
                                 side_effect=fixture_http),
                    redirect_stdout(io.StringIO()),
                ):
                    stack.enter_context(context)
                publisher.main()
        finally:
            os.chdir(saved_cwd)
            sys.path[:] = saved_path

    def test_publisher_uses_shared_channel_and_keeps_public_artifacts_readable(self):
        self.run_publisher(
            38, workspace.public_release_identity(self.first))
        channel = ReleaseChannel(self.channel)
        current = channel.current(workspace.PREVIEW_PACKAGE)
        self.assertEqual(current.version_code, 38)
        self.assertEqual(self.publish_calls, 1)
        self.assertEqual(
            channel.published(workspace.PREVIEW_PACKAGE, self.first.filename),
            self.first,
        )
        directory = self.channel / workspace.PREVIEW_PACKAGE
        for name in (
            "current.json",
            self.first.filename,
            self.first.filename[:-4] + ".json",
            current.filename,
            current.filename[:-4] + ".json",
        ):
            self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode),
                             0o644)
        self.assertEqual(
            stat.S_IMODE((directory / ".publishing").stat().st_mode), 0o600)

    def test_publisher_rejects_changed_channel_before_publication(self):
        baseline = workspace.public_release_identity(self.first)
        second = self.publish_current(38, b"another verified public release")
        with self.assertRaisesRegex(RuntimeError, "changed_since_runtime"):
            self.run_publisher(39, baseline)
        self.assertEqual(self.publish_calls, 0)
        self.assertEqual(
            ReleaseChannel(self.channel).current(workspace.PREVIEW_PACKAGE),
            second,
        )


if __name__ == "__main__":
    unittest.main()
