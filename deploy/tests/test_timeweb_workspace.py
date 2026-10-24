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


class WorkspaceEvidenceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
