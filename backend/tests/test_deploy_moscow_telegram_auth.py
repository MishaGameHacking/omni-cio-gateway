"""Fail-closed checks for the exact Moscow Telegram-auth deployment."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".github" / "scripts"
DEPLOY = SCRIPTS / "deploy_moscow_telegram_browser_auth.py"
NORMALIZER = SCRIPTS / "normalize_moscow_telegram_deploy_shell.py"
REMOTE = SCRIPTS / "deploy_moscow_telegram_browser_auth_remote.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-moscow-telegram-auth.yml"

sys.path.insert(0, str(SCRIPTS))
deploy_spec = importlib.util.spec_from_file_location("telegram_auth_deploy", DEPLOY)
assert deploy_spec is not None
assert deploy_spec.loader is not None
module = importlib.util.module_from_spec(deploy_spec)
deploy_spec.loader.exec_module(module)

normalizer_spec = importlib.util.spec_from_file_location("telegram_auth_normalizer", NORMALIZER)
assert normalizer_spec is not None
assert normalizer_spec.loader is not None
normalizer = importlib.util.module_from_spec(normalizer_spec)
normalizer_spec.loader.exec_module(normalizer)


class TelegramAuthDeploymentTests(unittest.TestCase):
    def test_checked_in_source_and_pinned_jwks_validate(self) -> None:
        metadata = module.validate_source()
        self.assertRegex(metadata["jwks_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(metadata["requirements_sha256"], r"^[0-9a-f]{64}$")

    def test_archive_is_bounded_to_backend_and_contains_browser_login(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "backend.tgz"
            module.create_archive(archive_path)
            with tarfile.open(archive_path, "r:gz") as archive:
                names = archive.getnames()
        self.assertIn("backend/telegram_browser_app.py", names)
        self.assertIn("backend/telegram_jwks.json", names)
        self.assertTrue(all(name == "backend" or name.startswith("backend/") for name in names))
        self.assertFalse(any(".." in Path(name).parts for name in names))

    def test_remote_script_materializer_normalizes_and_namespaces_bindings(self) -> None:
        source = (
            b"#!/usr/bin/env bash\r\n"
            b"set -euo pipefail\r\n"
            b'UNIT_FILE="$UNIT_FILE" OLD_EXEC="$OLD_EXEC" NEW_EXEC="$NEW_EXEC" '
            b'"$VENV_PYTHON" - <<\'PY\'\r\n'
            b'path = Path(os.environ["UNIT_FILE"])\r\n'
            b'old = os.environ["OLD_EXEC"]\r\n'
            b'new = os.environ["NEW_EXEC"]\r\n'
            b"PY\r\n"
        )
        materialized = normalizer.normalize_bytes(source)
        self.assertNotIn(b"\r", materialized)
        self.assertIn(b'UNIT_FILE_PATH="$UNIT_FILE"', materialized)
        self.assertIn(b'OLD_EXEC_VALUE="$OLD_EXEC"', materialized)
        self.assertIn(b'NEW_EXEC_VALUE="$NEW_EXEC"', materialized)
        self.assertIn(b'os.environ["UNIT_FILE_PATH"]', materialized)
        self.assertNotIn(b'UNIT_FILE="$UNIT_FILE"', materialized)
        self.assertEqual(normalizer.normalize_bytes(materialized), materialized)

    def test_checked_in_remote_script_materializes_without_readonly_assignment(self) -> None:
        materialized = normalizer.normalize_bytes(REMOTE.read_bytes())
        self.assertNotIn(b"\r", materialized)
        self.assertNotIn(b'UNIT_FILE="$UNIT_FILE"', materialized)
        self.assertNotIn(b'OLD_EXEC="$OLD_EXEC"', materialized)
        self.assertNotIn(b'NEW_EXEC="$NEW_EXEC"', materialized)
        self.assertIn(b'UNIT_FILE_PATH="$UNIT_FILE"', materialized)

    def test_remote_script_materializer_rejects_unexpected_input(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unexpected shebang"):
            normalizer.normalize_bytes(b"set -euo pipefail\r\n")
        with self.assertRaisesRegex(RuntimeError, "fail-closed shell options"):
            normalizer.normalize_bytes(b"#!/usr/bin/env bash\r\necho unsafe\r\n")
        with self.assertRaisesRegex(RuntimeError, "unexpected environment binding"):
            normalizer.normalize_bytes(b"#!/usr/bin/env bash\nset -euo pipefail\necho incomplete\n")

    def test_remote_repair_has_exact_entrypoint_and_rollback(self) -> None:
        source = REMOTE.read_text(encoding="utf-8")
        self.assertIn("uvicorn telegram_browser_app:app", source)
        self.assertIn("--rollback-after-public-check", source)
        self.assertIn("TELEGRAM_AUTH_ROLLBACK=healthy", source)
        self.assertIn('$BACKEND_ROOT/rollback/telegram-auth-$RUN_ID', source)
        self.assertIn('/root/analyst-ai-deploy/$RUN_ID', source)
        self.assertNotIn('/tmp/analyst-ai-telegram-auth-', source)
        self.assertNotIn("/var/lib/analyst-ai/backend.db", source)
        self.assertNotIn("rm -rf /var/lib/analyst-ai", source)

    def test_remote_repair_has_valid_bash_syntax_when_bash_is_available(self) -> None:
        candidates = [shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"]
        bash = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
        if bash is None:
            self.skipTest("Git Bash is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            materialized = Path(temporary) / "deploy.sh"
            materialized.write_bytes(normalizer.normalize_bytes(REMOTE.read_bytes()))
            subprocess.run([bash, "-n", str(materialized)], check=True)

    def test_workflow_is_explicitly_gated_and_materializes_before_cloud_access(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        marker = "normalize_moscow_telegram_deploy_shell.py"
        deployment = "deploy_moscow_telegram_browser_auth.py"
        self.assertIn("[deploy-telegram-auth]", source)
        self.assertIn("workflow_dispatch", source)
        self.assertIn("TIMEWEB_CLOUD_TOKEN", source)
        self.assertIn(marker, source)
        self.assertLess(source.index(marker), source.index(deployment + " --check"))
        self.assertIn(deployment, source)


if __name__ == "__main__":
    unittest.main()
