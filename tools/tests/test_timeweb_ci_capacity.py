"""Real request boundaries, ownership and cleanup regressions for disposable CI."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_ci_capacity as capacity

TOKEN = "synthetic-capacity-token"
NAME = "analyst-ci-123-1"


def server(**changes):
    return {"id": 17, "name": NAME, "comment": capacity.OWNER_MARKER,
            "preset_id": capacity.PRESET_ID, **changes}


class CapacityTests(unittest.TestCase):
    def test_error_details_never_echo_message_or_secret_fields(self):
        raw = json.dumps({"error_code": "invalid_request", "message": {"cloud_init": TOKEN},
                          "root_pass": TOKEN}).encode()
        self.assertEqual(capacity.error_details(raw), {
            "error_code": "invalid_request", "mentioned_fields": ["cloud_init"],
            "balance_mentioned": False})

    def test_cloud_keys_are_isolated_and_password_login_is_disabled(self):
        config = json.loads(capacity.cloud_config("client-public", "host-private", "host-public").split("\n", 1)[1])
        self.assertFalse(config["ssh_pwauth"])
        self.assertTrue(config["disable_root"])
        self.assertEqual(config["ssh_keys"]["ed25519_public"], "host-public")
        self.assertEqual(config["users"][0]["ssh_authorized_keys"], ["client-public"])
        self.assertNotIn(TOKEN, json.dumps(config))

    def test_unknown_method_host_or_server_path_cannot_use_credentials(self):
        cases = [("PATCH", "/api/v1/servers/17"), ("GET", "/api/v1/account"),
                 ("DELETE", "/api/v1/servers/0"), ("POST", "https://other.invalid")]
        with patch.object(capacity.urllib.request, "build_opener") as opener:
            for method, path in cases:
                with self.subTest(method=method, path=path), self.assertRaises(capacity.ProbeError):
                    capacity.request(TOKEN, method, path)
        opener.assert_not_called()

    def test_error_body_and_credential_never_escape(self):
        error = urllib.error.HTTPError(capacity.BASE_URL, 403, TOKEN, {}, io.BytesIO(TOKEN.encode()))
        with patch.object(capacity.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(capacity.ProbeError, "^timeweb_http_403$"):
                capacity.request(TOKEN, "POST", "/api/v1/servers", {"name": NAME})

    def test_existing_or_mismatched_server_is_not_owned(self):
        cases = [server(name="production"), server(comment="other"),
                 server(preset_id=1), server(id=True)]
        for value in cases:
            with self.subTest(server_id=value["id"]), self.assertRaises(capacity.ProbeError):
                capacity.owned_server({"server": value}, NAME)

    def test_public_address_is_selected_without_private_network(self):
        value = server(networks=[
            {"type": "private", "ips": [{"type": "ipv4", "ip": "10.0.0.1"}]},
            {"type": "public", "ips": [{"type": "ipv4", "ip": "1.1.1.1"}]},
        ])
        self.assertEqual(capacity.public_ipv4(value), "1.1.1.1")

    def test_changed_price_stops_before_creation(self):
        offer = {"id": capacity.PRESET_ID, "price": capacity.MAX_MONTHLY_RUB + 1}
        projects = {"projects": [{"id": capacity.PROJECT_ID}], "meta": {"total": 1}}
        with patch.object(capacity, "read_resource", return_value=projects), \
                patch.object(capacity, "read_catalog", return_value={}), \
                patch.object(capacity, "candidate_presets", return_value=[offer]), \
                patch.object(capacity, "request") as request:
            with self.assertRaisesRegex(capacity.ProbeError, "over_budget"):
                capacity.validate_offer(TOKEN)
        request.assert_not_called()

    def test_cleanup_reconciles_ambiguous_creation_and_requires_404(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({"name": NAME, "server_id": None}))
            listing = {"servers": [server(), server(id=18, name="production")], "meta": {"total": 2}}
            with patch.object(capacity, "state_path", return_value=state), \
                    patch.object(capacity, "identity", return_value=NAME), \
                    patch.object(capacity, "read_resource", return_value=listing), \
                    patch.object(capacity, "request", side_effect=[{}, capacity.ProbeError("timeweb_http_404")]) as request:
                capacity.cleanup(TOKEN)
            self.assertFalse(state.exists())
            self.assertEqual([call.args[1:] for call in request.call_args_list], [
                ("DELETE", "/api/v1/servers/17"), ("GET", "/api/v1/servers/17")])

    def test_pending_delete_keeps_recovery_state_and_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({"name": NAME, "server_id": 17}))
            listing = {"servers": [server()], "meta": {"total": 1}}
            with patch.object(capacity, "state_path", return_value=state), \
                    patch.object(capacity, "identity", return_value=NAME), \
                    patch.object(capacity, "read_resource", return_value=listing), \
                    patch.object(capacity, "request", return_value={"confirmation_required": True}), \
                    patch.object(capacity.time, "sleep"):
                with self.assertRaisesRegex(capacity.ProbeError, "deletion_not_confirmed"):
                    capacity.cleanup(TOKEN)
            self.assertTrue(state.exists())


if __name__ == "__main__":
    unittest.main()
