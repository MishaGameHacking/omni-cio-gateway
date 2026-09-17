from __future__ import annotations

from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import scripts.probe_v10_neon_egress_boundary as egress


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/v10-neon-egress-boundary.yml"


class NeonEgressBoundaryTests(unittest.TestCase):
    def test_media_family_is_bounded(self) -> None:
        cases = {
            None: "MISSING",
            "": "MISSING",
            "application/json": "JSON",
            "application/problem+json; charset=utf-8": "JSON",
            "text/html; charset=utf-8": "HTML",
            "text/plain": "TEXT",
            "application/octet-stream": "OTHER",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(egress._media_family(value), expected)

    def test_probe_uses_fixed_anonymous_https_curl_shape(self) -> None:
        executable = os.path.abspath(os.path.join("tools", "curl"))
        completed = Mock(returncode=0, stdout="401\napplication/json\n")
        sensitive_binding = "NEON_" + "API_" + "KEY"
        source_environment = {
            sensitive_binding: "fixture-only",
            "HTTPS_" + "PROXY": "http://proxy.invalid:8080",
            "PATH": "private-path-value",
            "SYSTEMROOT": "C:\\Windows",
        }
        with (
            patch.object(egress.shutil, "which", return_value=executable),
            patch.object(egress.subprocess, "run", return_value=completed) as run,
        ):
            evidence = egress.probe_egress_boundary(source_environment)

        self.assertEqual(evidence, egress.EgressProbeEvidence("401", "JSON"))
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual(command[0], executable)
        self.assertIn("--disable", command)
        self.assertEqual(command[command.index("--proto") + 1], "=https")
        self.assertIn("--tlsv1.2", command)
        self.assertIn("--http1.1", command)
        self.assertEqual(command[command.index("--noproxy") + 1], "*")
        self.assertEqual(command[command.index("--max-redirs") + 1], "0")
        self.assertEqual(command[command.index("--request") + 1], "GET")
        self.assertEqual(command[command.index("--output") + 1], os.devnull)
        self.assertEqual(
            command[-1],
            "https://console.neon.tech/api/v2/projects/"
            "omni-cio-v10-egress-control-invalid",
        )
        flattened = " ".join(command)
        self.assertNotIn("Authorization", flattened)
        self.assertNotIn("project-frankfurt-test", flattened)
        self.assertEqual(kwargs["env"], {"SYSTEMROOT": "C:\\Windows"})
        self.assertNotIn(sensitive_binding, kwargs["env"])
        self.assertIs(kwargs["stdin"], egress.subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], egress.subprocess.PIPE)
        self.assertIs(kwargs["stderr"], egress.subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], 25.0)

    def test_probe_parser_rejects_redirects_malformed_and_oversized_output(self) -> None:
        unavailable = egress.EgressProbeEvidence("UNAVAILABLE", "MISSING")
        bad_results = (
            (1, "000\n\n"),
            (0, "302\ntext/html\n"),
            (0, "403\ntext/html\nextra\n"),
            (0, "bad\ntext/html\n"),
            (0, "x" * 257),
        )
        for returncode, output in bad_results:
            with self.subTest(output=output[:16]):
                self.assertEqual(
                    egress._parse_probe_output(returncode, output),
                    unavailable,
                )

    def test_egress_classifier_distinguishes_changed_and_unchanged(self) -> None:
        denied = egress.EgressProbeEvidence("403", "HTML")
        api_denial = egress.EgressProbeEvidence("401", "JSON")
        self.assertEqual(
            egress.classify_egress_effect(denied, denied),
            "UNCHANGED",
        )
        self.assertEqual(
            egress.classify_egress_effect(denied, api_denial),
            "CHANGED",
        )
        self.assertEqual(
            egress.classify_egress_effect(
                denied,
                egress.EgressProbeEvidence("UNAVAILABLE", "MISSING"),
            ),
            "UNAVAILABLE",
        )

    def test_probe_command_writes_only_bounded_outputs(self) -> None:
        output = StringIO()
        with tempfile.TemporaryDirectory() as directory:
            github_output = Path(directory) / "github-output.txt"
            environment = {"GITHUB_OUTPUT": str(github_output)}
            with patch.object(
                egress,
                "probe_egress_boundary",
                return_value=egress.EgressProbeEvidence("403", "HTML"),
            ):
                status = egress._probe_command(output=output, environ=environment)
            self.assertEqual(status, 0)
            self.assertEqual(
                github_output.read_text(encoding="utf-8"),
                "status=403\nmedia=HTML\n",
            )
        self.assertEqual(
            output.getvalue().strip(),
            "CLOUDFLARE_NEON_EGRESS_CONTROL status=403 media=HTML",
        )

    def test_workflow_varies_egress_without_provider_secret_custody(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, Windows, X64, omni-cio-ci]", source)
        self.assertGreaterEqual(source.count("runs-on: ubuntu-24.04"), 2)
        self.assertIn("Neon egress boundary classification", source)
        self.assertIn("probe_v10_neon_egress_boundary probe", source)
        self.assertIn("probe_v10_neon_egress_boundary compare", source)
        self.assertNotIn("${{ secrets.", source)
        self.assertNotIn("uses: actions/checkout@", source)
        protected_bindings = (
            "NEON_" + "API_" + "KEY",
            "NEON_" + "ORG_" + "ID",
            "NEON_" + "PROJECT_" + "ID",
            "OMNI_V10_" + "POSTGRES_" + "DSN",
        )
        for binding in protected_bindings:
            with self.subTest(binding=binding):
                self.assertNotIn(binding, source)

    def test_compare_marker_contains_no_network_or_provider_identifier_detail(self) -> None:
        args = egress._parser().parse_args(
            [
                "compare",
                "--self-status",
                "403",
                "--self-media",
                "HTML",
                "--hosted-status",
                "401",
                "--hosted-media",
                "JSON",
            ]
        )
        output = StringIO()
        status = egress._compare_command(args, output=output)
        marker = output.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("egress_effect=CHANGED", marker)
        for forbidden in (
            "console.neon.tech",
            "https://",
            "project-",
            "request_id",
            "ip=",
        ):
            self.assertNotIn(forbidden, marker.casefold())


if __name__ == "__main__":
    unittest.main()
