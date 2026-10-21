"""Endpoint access is observed separately, not guessed from one denied read."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_actions_probe as probe

TOKEN = "test-only-credential-not-a-real-token"


def reply(token, name):
    if name == "projects":
        raise probe.ProbeError("timeweb_http_403")
    return {name: [], "meta": {"total": 0}}


class AccessResultTests(unittest.TestCase):
    def test_denied_projects_still_observes_servers_and_buckets(self):
        with patch.object(probe, "read_resource", side_effect=reply) as read:
            report = probe.inventory(TOKEN)
        self.assertEqual([call.args[1] for call in read.call_args_list], list(probe.ENDPOINTS))
        self.assertEqual(report["failed_resources"], {"projects": "timeweb_http_403"})
        self.assertEqual(set(report["resources"]), {"servers", "buckets"})
        self.assertTrue(report["resources"]["servers"]["complete"])

    def test_denied_collections_are_not_reported_as_empty(self):
        with patch.object(probe, "read_resource", side_effect=probe.ProbeError("timeweb_http_403")):
            report = probe.inventory(TOKEN)
        self.assertEqual(report["resources"], {})
        self.assertEqual(set(report["failed_resources"]), set(probe.ENDPOINTS))
        self.assertFalse(report["ready_for_import"])

    def test_partial_failure_returns_failed_exit_and_safe_report(self):
        output = io.StringIO()
        with patch.dict(probe.os.environ, {"TIMEWEB_CLOUD_TOKEN": TOKEN}):
            with patch.object(probe, "read_resource", side_effect=reply), redirect_stdout(output):
                result = probe.main()
        self.assertEqual(result, 1)
        self.assertIn('"projects": "timeweb_http_403"', output.getvalue())
        self.assertNotIn(TOKEN, output.getvalue())

    def test_bad_shape_does_not_discard_other_results(self):
        documents = {name: {name: [], "meta": {"total": 0}} for name in probe.ENDPOINTS}
        documents["servers"] = {"servers": None}
        with patch.object(probe, "read_resource", side_effect=lambda token, name: documents[name]):
            report = probe.inventory(TOKEN)
        self.assertEqual(report["failed_resources"], {"servers": "invalid_resource_collection"})
        self.assertEqual(set(report["resources"]), {"projects", "buckets"})


if __name__ == "__main__":
    unittest.main()
