"""Exercise the actual browser/legacy app in a fresh subprocess and database."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cryptography.fernet import Fernet

SCRIPT = r'''
import json
import os
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from backend.owner_app import create_app
from backend import telegram_browser_app as browser

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
jwk.update(kid="integration-test", alg="RS256", use="sig")
pinned = Path(os.environ["DATABASE_PATH"]).with_suffix(".jwks.json")
pinned.write_text(json.dumps({"keys": [jwk]}), encoding="utf-8")
browser.TELEGRAM_JWKS_PATH = pinned
app = create_app()

def login(client, subject):
    assert client.get("/auth/telegram/start").status_code == 200
    with closing(browser.legacy.connect()) as db:
        state, nonce = db.execute("SELECT state,verifier FROM login_transactions").fetchone()
    now = int(time.time())
    token = jwt.encode({"iss": browser.legacy.TELEGRAM_ISSUER,
        "aud": browser.legacy.TELEGRAM_CLIENT_ID, "sub": subject,
        "iat": now, "exp": now + 120, "nonce": nonce,
        "name": "Identical display name", "preferred_username": "same_name"},
        key, algorithm="RS256", headers={"kid": "integration-test"})
    return client.post("/auth/telegram/complete", json={"state": state, "id_token": token},
                       headers={"Origin": browser.legacy.BACKEND_PUBLIC_URL})

with TestClient(app) as client:
    for device in ("phone", "tablet"):
        response = login(client, "confirmed-owner")
        assert response.status_code == 200, response.status_code
        code = parse_qs(urlparse(response.json()["deep_link"]).query)["code"][0]
        response = client.post("/auth/session", json={"code": code, "device_name": device})
        assert response.status_code == 200, response.status_code
        user = browser.legacy.session_user("Bearer " + response.json()["access_token"])
        assert user["telegram_sub"] == "confirmed-owner"
        auth = {"Authorization": "Bearer " + response.json()["access_token"]}
        before = client.get("/workspace/live?wait=0", headers=auth)
        assert before.status_code == 200
        with closing(browser.legacy.connect()) as db:
            db.execute("INSERT INTO market_facts VALUES (?, 'fixture',NULL,'synthetic','{}','2026-01-01',NULL,1)", (device,))
            db.execute("INSERT INTO workspace_records VALUES (?,'note',?,'{}',1,1,1)", (user["id"], device))
            db.commit()
        after = client.get("/workspace/live?wait=0", headers=auth)
        assert after.status_code == 200
        assert before.json()["revision"] != after.json()["revision"]

        assert client.post("/auth/session", json={"code": code}).status_code == 401
    denied = login(client, "another-person")
    assert denied.status_code == 403, denied.status_code
    assert denied.json()["detail"] == "owner_access_denied"
    with closing(browser.legacy.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
print("OWNER_HTTP_INTEGRATION=passed")
'''


class OwnerEntrypointIntegrationTests(unittest.TestCase):
    def test_real_signed_login_session_replay_and_second_person(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "ANALYST_OWNER_TELEGRAM_SUB": "confirmed-owner",
                   "DATABASE_PATH": str(Path(directory) / "owner.db"),
                   "TELEGRAM_CLIENT_ID": "12345", "TELEGRAM_CLIENT_SECRET": "test-only-not-a-real-secret",
                   "FERNET_KEY": Fernet.generate_key().decode(),
                   "BACKEND_PUBLIC_URL": "https://analyst.invalid",
                   "ANALYSIS_SCHEDULER_ENABLED": "false"}
            result = subprocess.run([sys.executable, "-c", SCRIPT], env=env,
                                    cwd=Path(__file__).resolve().parents[2],
                                    capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr[-8000:])
        self.assertIn("OWNER_HTTP_INTEGRATION=passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
