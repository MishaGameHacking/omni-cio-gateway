"""Fail-closed checks for the exact Moscow Telegram-auth deployment."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError


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
    def test_staged_preflight_initializes_workspace_and_preserves_existing_user(self) -> None:
        shell = REMOTE.read_text(encoding="utf-8")
        marker = 'DATABASE_PATH="$PREFLIGHT_DB" STAGED_BACKEND="$STAGING/backend" "$VENV_PYTHON" - <<\'PY\'\n'
        preflight = shell.split(marker, 1)[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "preflight.sqlite3"
            environment = {key: value for key, value in os.environ.items()
                           if key.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH"}}
            environment.update(
                DATABASE_PATH=str(database), STAGED_BACKEND=str(ROOT / "backend"),
                TELEGRAM_CLIENT_ID="123456", TELEGRAM_CLIENT_SECRET="synthetic-preflight-only",
                FERNET_KEY="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                BACKEND_PUBLIC_URL="https://example.invalid", ANALYSIS_SCHEDULER_ENABLED="false",
                AI_EXTERNAL_PROCESSING_APPROVED="false",
            )
            subprocess.run([sys.executable, "-c", preflight], env=environment, check=True, timeout=30)
            with sqlite3.connect(database) as db:
                db.execute("INSERT INTO users(telegram_sub,telegram_id,created_at,updated_at) VALUES ('preflight-user','1',1,1)")
                db.execute("INSERT INTO workspace_records VALUES (1,'note','owned','{}',1,1,1)")
                db.commit()
            subprocess.run([sys.executable, "-c", preflight], env=environment, check=True, timeout=30)
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute("SELECT telegram_sub FROM users").fetchone()[0], "preflight-user")
                self.assertEqual(db.execute("SELECT id FROM workspace_records WHERE user_id=1").fetchone()[0], "owned")
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_workspace_probe_requires_authentication_for_every_read_route(self) -> None:
        observed = []

        def unauthenticated(request, timeout):
            observed.append(request.full_url)
            self.assertNotIn("Authorization", request.headers)
            self.assertIsNone(request.data)
            self.assertEqual(timeout, 15)
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

        with patch.object(module.urllib.request, "urlopen", side_effect=unauthenticated):
            module.verify_workspace_authentication()
        self.assertEqual(observed, [module.PUBLIC_URL + path for path in module.WORKSPACE_READ_PATHS])

    def test_workspace_probe_blocks_missing_routes_and_unexpected_status(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(module.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "Workspace authentication probe failed"):
                module.verify_workspace_authentication()
        for status in (403, 404, 500):
            with self.subTest(status=status):
                failure = HTTPError(module.PUBLIC_URL + "/workspace", status, "Unexpected", {}, None)
                with patch.object(module.urllib.request, "urlopen", side_effect=failure):
                    with self.assertRaisesRegex(RuntimeError, "Workspace authentication probe failed"):
                        module.verify_workspace_authentication()

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

    def test_remote_script_normalizer_removes_all_carriage_returns(self) -> None:
        source = b"#!/usr/bin/env bash\r\nset -euo pipefail\r\necho ready\r\n"
        expected = b"#!/usr/bin/env bash\nset -euo pipefail\necho ready\n"
        self.assertEqual(normalizer.normalize_bytes(source), expected)
        self.assertNotIn(b"\r", normalizer.normalize_bytes(REMOTE.read_bytes()))

    def test_remote_script_normalizer_rejects_unexpected_input(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unexpected shebang"):
            normalizer.normalize_bytes(b"set -euo pipefail\r\n")
        with self.assertRaisesRegex(RuntimeError, "fail-closed shell options"):
            normalizer.normalize_bytes(b"#!/usr/bin/env bash\r\necho unsafe\r\n")

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

    def test_child_python_env_does_not_reassign_readonly_shell_constants(self) -> None:
        source = REMOTE.read_text(encoding="utf-8")
        unsafe_unit = 'UNIT_FILE="$UNIT_FILE" OLD_EXEC="$OLD_EXEC" NEW_EXEC="$NEW_EXEC"'
        safe_unit = 'PY_UNIT_FILE="$UNIT_FILE" PY_OLD_EXEC="$OLD_EXEC" PY_NEW_EXEC="$NEW_EXEC"'
        safe_body = 'PY_BODY_FILE="$BODY_FILE" "$VENV_PYTHON"'
        self.assertNotIn(unsafe_unit, source)
        self.assertIn(safe_unit, source)
        self.assertIn(safe_body, source)
        self.assertIn('os.environ["PY_UNIT_FILE"]', source)
        self.assertIn('os.environ["PY_OLD_EXEC"]', source)
        self.assertIn('os.environ["PY_NEW_EXEC"]', source)
        self.assertIn('os.environ["PY_BODY_FILE"]', source)
        module.validate_remote_readonly_assignments(source)

    def test_readonly_assignment_validator_rejects_late_direct_or_child_env_assignment(self) -> None:
        safe = 'VALUE="before"\nreadonly VALUE\nPY_VALUE="$VALUE" python -V\n'
        module.validate_remote_readonly_assignments(safe)
        for unsafe in (
            'VALUE="before"\nreadonly VALUE\nVALUE="after"\n',
            'readonly VALUE="before"\nVALUE="$VALUE" python -V\n',
        ):
            with self.subTest(source=unsafe):
                with self.assertRaisesRegex(RuntimeError, "readonly shell constant VALUE"):
                    module.validate_remote_readonly_assignments(unsafe)

    def test_remote_repair_has_valid_bash_syntax_when_bash_is_available(self) -> None:
        candidates = [shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"]
        bash = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
        if bash is None:
            self.skipTest("Git Bash is unavailable")
        subprocess.run([bash, "-n", str(REMOTE)], check=True)

    def test_workflow_is_explicitly_gated_and_normalizes_before_cloud_access(self) -> None:
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
