"""Offline regression tests for the strictly read-only Actions preflight."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_actions_probe as probe

TOKEN = "test-only-credential-not-a-real-token"


class Reply(io.BytesIO):
    def __init__(self, raw=b'{"projects":[]}', status=200, encoding="identity"):
        super().__init__(raw)
        self.status = status
        self.headers = {"Content-Encoding": encoding}


class ProbeTests(unittest.TestCase):
    def test_schema_has_explicit_definitions_and_only_the_project_read_action(self):
        result = probe.validate_schema()
        self.assertEqual(result, {"schema_validated": True, "operation_count": 1, "read_only": True})

    def test_every_internal_schema_reference_resolves(self):
        schema = json.loads(probe.SCHEMA_PATH.read_text(encoding="utf-8"))
        probe.validate_references(schema, schema)
        self.assertIn("Project", schema["components"]["schemas"])

    def test_schema_file_never_contains_a_real_credential_or_request_header(self):
        text = probe.SCHEMA_PATH.read_text(encoding="utf-8")
        self.assertNotIn(TOKEN, text)
        self.assertNotIn("Authorization", text)
        self.assertNotIn("api_key", text)

    def test_changed_server_or_write_method_cannot_pass_validation(self):
        original = json.loads(probe.SCHEMA_PATH.read_text(encoding="utf-8"))
        for mutation in ("server", "write", "definitions", "security", "reference"):
            schema = copy.deepcopy(original)
            if mutation == "server":
                schema["servers"] = [{"url": "https://example.invalid"}]
            elif mutation == "write":
                schema["paths"]["/api/v1/projects"]["post"] = {}
            elif mutation == "definitions":
                schema["components"]["schemas"] = None
            elif mutation == "security":
                schema["security"] = []
            else:
                schema["components"]["schemas"]["Broken"] = {"$ref": "https://example.invalid/secret"}
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "schema.json"
                path.write_text(json.dumps(schema), encoding="utf-8")
                with self.subTest(mutation=mutation), self.assertRaises(probe.ProbeError):
                    probe.validate_schema(path)

    def test_missing_internal_reference_is_rejected(self):
        root = {"components": {"schemas": {}}}
        value = {"$ref": "#/components/schemas/Absent"}
        with self.assertRaises(probe.ProbeError):
            probe.validate_references(value, root)

    def test_valid_token_strips_outer_whitespace(self):
        self.assertEqual(probe.validated_token(" \n" + TOKEN + "\n"), TOKEN)

    def test_invalid_tokens_never_reach_network(self):
        for token in ("", " ", "x\ry", "x\ny", "x y", "\u0442\u043e\u043a\u0435\u043d", "x" * 16385):
            with self.subTest(length=len(token)), patch.object(probe.urllib.request, "build_opener") as build:
                with self.assertRaises(probe.ProbeError):
                    probe.read_resource(token, "projects")
                build.assert_not_called()

    def test_unknown_endpoint_never_reaches_network(self):
        with patch.object(probe.urllib.request, "build_opener") as build:
            with self.assertRaises(probe.ProbeError):
                probe.read_resource(TOKEN, "https://example.invalid/")
            build.assert_not_called()

    def test_request_is_fixed_https_get_with_bounded_read_and_timeout(self):
        with patch.object(probe.urllib.request, "build_opener") as build:
            response = Reply()
            build.return_value.open.return_value = response
            result = probe.read_resource(TOKEN, "projects")
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, probe.BASE_URL + "/api/v1/projects")
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
            self.assertEqual(request.get_header("Accept-encoding"), "identity")
            self.assertEqual(build.return_value.open.call_args.kwargs["timeout"], 20)
            self.assertEqual(result, {"projects": []})
            self.assertTrue(response.closed)

    def test_redirect_cannot_forward_the_authorization_header(self):
        handler = probe.NoRedirect()
        with self.assertRaisesRegex(probe.ProbeError, "redirect_refused"):
            handler.redirect_request(None, None, 302, "secret", {}, "https://example.invalid/")

    def test_http_error_does_not_emit_response_body(self):
        error = urllib.error.HTTPError(probe.BASE_URL, 403, TOKEN, {}, io.BytesIO(TOKEN.encode()))
        with patch.object(probe.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(probe.ProbeError) as caught:
                probe.read_resource(TOKEN, "servers")
        self.assertEqual(str(caught.exception), "timeweb_http_403")
        self.assertTrue(caught.exception.__suppress_context__)

    def test_transport_error_hides_raw_exception(self):
        with patch.object(probe.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = urllib.error.URLError(TOKEN)
            with self.assertRaises(probe.ProbeError) as caught:
                probe.read_resource(TOKEN, "servers")
        self.assertEqual(str(caught.exception), "timeweb_transport_error")

    def test_compressed_response_is_not_decompressed(self):
        with patch.object(probe.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = Reply(b"secret", encoding="gzip")
            with self.assertRaisesRegex(probe.ProbeError, "encoded_response_refused"):
                probe.read_resource(TOKEN, "projects")

    def test_non200_success_like_response_is_rejected(self):
        with patch.object(probe.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = Reply(status=201)
            with self.assertRaisesRegex(probe.ProbeError, "unexpected_http_status"):
                probe.read_resource(TOKEN, "projects")

    def test_size_limit_is_enforced_before_json_parse(self):
        raw = b" " * (probe.MAX_BYTES + 1)
        with self.assertRaisesRegex(probe.ProbeError, "response_too_large"):
            probe.decode_response(raw)

    def test_invalid_unicode_json_and_top_level_arrays_fail(self):
        for raw in (b"\xff", b"{bad", b"[]", b"null"):
            with self.subTest(raw=raw), self.assertRaises(probe.ProbeError):
                probe.decode_response(raw)

    def test_duplicate_json_keys_are_rejected(self):
        raw = b'{"projects": [], "projects": [{"id": 1}]}'
        with self.assertRaisesRegex(probe.ProbeError, "duplicate_json_key"):
            probe.decode_response(raw)

    def test_nonfinite_numbers_are_rejected(self):
        for raw in (b'{"x": NaN}', b'{"x": Infinity}', b'{"x": -Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(probe.ProbeError):
                probe.decode_response(raw)

    def test_only_numeric_ids_and_counts_are_reported(self):
        document = {"servers": [{"id": 12, "name": TOKEN, "root_pass": TOKEN,
                                  "secret": {"token": TOKEN}}], "meta": {"total": 1}, "token": TOKEN}
        result = probe.summarize("servers", document)
        self.assertEqual(result, {"returned_count": 1, "ids": [12], "reported_total": 1, "complete": True})
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_missing_total_does_not_claim_complete_inventory(self):
        result = probe.summarize("servers", {"servers": []})
        self.assertFalse(result["complete"])
        self.assertIsNone(result["reported_total"])

    def test_larger_total_keeps_partial_inventory_explicit(self):
        result = probe.summarize("servers", {"servers": [{"id": 1}], "meta": {"total": 10}})
        self.assertFalse(result["complete"])
        self.assertEqual(result["reported_total"], 10)

    def test_invalid_collections_and_duplicate_ids_fail(self):
        documents = ({}, {"servers": None}, {"servers": [None]}, {"servers": [{"id": True}]},
                     {"servers": [{"id": 0}]}, {"servers": [{"id": "1"}]},
                     {"servers": [{"id": 1}, {"id": 1}]}, {"servers": [{}] * 2001})
        for document in documents:
            with self.subTest(size=len(str(document))), self.assertRaises(probe.ProbeError):
                probe.summarize("servers", document)

    def test_invalid_totals_are_rejected(self):
        for total in (True, "1", -1, 0, 1.0):
            document = {"servers": [{"id": 1}], "meta": {"total": total}}
            with self.subTest(total=total), self.assertRaises(probe.ProbeError):
                probe.summarize("servers", document)

    def test_inventory_never_claims_publication_or_mutation(self):
        documents = {name: {name: [], "meta": {"total": 0}} for name in probe.ENDPOINTS}
        with patch.object(probe, "read_resource", side_effect=lambda token, name: documents[name]) as read:
            result = probe.inventory(TOKEN)
        self.assertEqual(read.call_count, 3)
        self.assertFalse(result["resource_changes"])
        self.assertFalse(result["public_schema_published"])
        self.assertFalse(result["ready_for_import"])

    def test_missing_token_exits_failed_without_network(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(probe.os.environ, {"TIMEWEB_CLOUD_TOKEN": ""}), patch.object(probe, "read_resource") as read:
            with redirect_stdout(output), redirect_stderr(errors):
                result = probe.main()
        self.assertEqual(result, 1)
        self.assertIn("timeweb_token_missing", errors.getvalue())
        read.assert_not_called()

    def test_success_output_contains_no_token(self):
        documents = {name: {name: [], "meta": {"total": 0}} for name in probe.ENDPOINTS}
        output = io.StringIO()
        with patch.dict(probe.os.environ, {"TIMEWEB_CLOUD_TOKEN": TOKEN}):
            with patch.object(probe, "read_resource", side_effect=lambda token, name: documents[name]):
                with redirect_stdout(output):
                    result = probe.main()
        self.assertEqual(result, 0)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertIn("TIMEWEB_ACTIONS_PREFLIGHT=", output.getvalue())


if __name__ == "__main__":
    unittest.main()
