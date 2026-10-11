"""Static publication preserves the existing API, legal versions and rollback route."""
from __future__ import annotations

import base64
import contextlib
import io
import json
import re
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/timeweb_public_site.py"
# The deployment scripts already share their stdlib-only import boundary.
sys.path.insert(0, str(SCRIPT.parent))
MODULE = runpy.run_path(str(SCRIPT))


@pytest.mark.parametrize("fail_readback", [False, True])
def test_remote_publication_readback_and_rollback_without_api_mutation(tmp_path, fail_readback):
    base = tmp_path / "releases"
    previous = base / ("a" * 40)
    previous.mkdir(parents=True)
    (previous / "legal").mkdir()
    for name in ("privacy.html", "terms.html", "consent.html"):
        (previous / "legal" / name).write_text("current-running-api-legal-version")
    site = tmp_path / "nginx.conf"
    original = (f"root {previous.as_posix()};\n"
                'add_header X-Omnicio-Build "aaaaaaaaaaaa";\n'
                'location /api/ { proxy_pass http://127.0.0.1:8001; }')
    site.write_text(original)
    sha = "b" * 40
    root = SCRIPT.parents[2]
    payload = json.loads(MODULE["public_payload"](root, sha))
    program = MODULE["REMOTE_PUBLISH"].replace(
        "pathlib.Path('/var/www/omnicio.ru/releases')", f"pathlib.Path({str(base)!r})")
    program = program.replace("pathlib.Path('/etc/nginx/sites-available/omnicio.ru')",
                              f"pathlib.Path({str(site)!r})")
    compiled_program = compile(program, "remote-publication", "exec")
    commands = []

    def command(args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0)

    @contextlib.contextmanager
    def fetch(url, **kwargs):
        path = url.removeprefix("https://omnicio.ru")
        if path == "/api/auth/config":
            body = b'{"release":{"version":"1.3.0","build":"aaaaaaaaaaaa"}}'
        elif path.startswith("/health/"):
            body = b'{"status":"ok"}'
        else:
            current = Path(re.search(r"root (.+);", site.read_text())[1])
            body = (current / (path.lstrip("/") or "index.html")).read_bytes()
            if fail_readback and path.endswith("app.js"):
                body = b"incorrect public asset"
        result = io.BytesIO(body)
        result.headers = {"X-Omnicio-Build": sha[:12]}
        yield result

    with (patch("sys.stdin", io.StringIO(json.dumps(payload))),
          patch("subprocess.run", side_effect=command),
          patch("urllib.request.urlopen", side_effect=fetch),
          contextlib.redirect_stdout(io.StringIO()) as output):
        if fail_readback:
            with pytest.raises(ValueError, match="public_asset_mismatch"):
                exec(compiled_program, {})
        else:
            exec(compiled_program, {})
            assert json.loads(output.getvalue())["api_unchanged"] is True
    assert site.read_text() == (original if fail_readback else original.replace(
        previous.as_posix(), (base / (sha + "-public")).as_posix(),
    ).replace("aaaaaaaaaaaa", sha[:12]))
    assert set(tuple(command) for command in commands) == {
        ("nginx", "-t"), ("systemctl", "reload", "nginx"),
    }
    assert (base / (sha + "-public") / "legal/privacy.html").read_text() == (
        "current-running-api-legal-version"
    )


def test_public_payload_contains_no_account_client_or_private_configuration():
    payload = json.loads(MODULE["public_payload"](SCRIPT.parents[2], "c" * 40))
    paths = set(payload["files"])
    assert "downloads/android.json" in paths
    assert not paths.intersection({"assets/workspace.js", "assets/config.js", "assets/i18n.js"})
    assert not any(path.startswith(("src/", "migrations/", "legal/")) for path in paths)
    assert json.loads(base64.b64decode(payload["files"]["downloads/android.json"])) == {
        "status": "unpublished",
    }
    with pytest.raises(MODULE["InfraError"]):
        MODULE["public_payload"](SCRIPT.parents[2], "main")


def test_only_existing_named_server_is_eligible():
    client = Mock()
    client.get_servers.return_value = [{"id": 999, "name": "named", "comment": "managed"}]
    with pytest.raises(RuntimeError, match="unexpected_public_server"):
        MODULE["publish_public_site"](client, root=SCRIPT.parents[2], sha="d" * 40,
                                      server_name="named", server_comment="managed")
    client.get_server.assert_not_called()
