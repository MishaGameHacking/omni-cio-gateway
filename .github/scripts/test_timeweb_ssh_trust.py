"""Regress server impersonation and missing trust before provider mutations."""

from __future__ import annotations

import base64
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import timeweb_auth_postgres as postgres
import timeweb_domain_tls as tls
from timeweb_ssh_trust import (
    managed_server_identity,
    ssh_base_args,
    trusted_host_entry,
    trusted_host_fingerprint,
)

SERVER = "194.87.151.244"
KEY = base64.b64encode(
    b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes(range(32))
).decode("ascii")
ENTRY = f"{SERVER} ssh-ed25519 {KEY}"


class SshTrustTests(unittest.TestCase):
    def test_preflight_cli_blocks_missing_or_wrong_key_without_echoing_input(self) -> None:
        script = pathlib.Path(__file__).with_name("timeweb_ssh_trust.py")
        cases = (("", 1), (ENTRY.replace(SERVER, "203.0.113.10"), 1), (ENTRY, 0))
        for value, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                result = subprocess.run(
                    [sys.executable, str(script)],
                    env={"TIMEWEB_SSH_KNOWN_HOSTS": value},
                    check=False, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, expected_status)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(KEY, result.stderr)
                self.assertEqual(bool(result.stderr), bool(expected_status))

    def test_invalid_managed_target_fails_closed(self) -> None:
        invalid = (
            {}, {"server-id": True, "ipv4": SERVER},
            {"server-id": 0, "ipv4": SERVER},
            {"server-id": 1, "ipv4": "127.0.0.1"},
            {"server-id": 1, "ipv4": "::1"},
            {"server-id": 1, "ipv4": "not-an-address"},
        )
        for target in invalid:
            with self.subTest(target=target), patch(
                "timeweb_ssh_trust.tomllib.load",
                return_value={"tool": {"omnicio": {"timeweb": target}}},
            ), self.assertRaises(ValueError):
                managed_server_identity()

    def test_exact_key_round_trip(self) -> None:
        self.assertEqual(trusted_host_entry(ENTRY + "\n", SERVER), ENTRY + "\n")

    def test_rejects_missing_malformed_or_other_host_trust(self) -> None:
        invalid = [
            "", " " * 20, ENTRY * 100,
            ENTRY.replace(SERVER, "203.0.113.10"),
            ENTRY.replace(SERVER, "*"),
            ENTRY.replace("ssh-ed25519", "ssh-rsa"),
            ENTRY + "\n" + ENTRY,
            ENTRY + " comment",
            f"{SERVER} ssh-ed25519 invalid!",
            f"{SERVER} ssh-ed25519 YWJj",
            f"{SERVER} ssh-ed25519 " + base64.b64encode(bytes(51)).decode("ascii"),
        ]
        for value in invalid:
            with self.subTest(value=value[:30]), self.assertRaises(ValueError):
                trusted_host_entry(value, SERVER)

    def test_both_consumers_fail_before_key_generation_or_provider_access(self) -> None:
        for value in ("", ENTRY.replace(SERVER, "203.0.113.10")):
            with self.subTest(value=value), patch.dict(
                os.environ, {"TIMEWEB_SSH_KNOWN_HOSTS": value},
            ), patch.object(subprocess, "run") as command:
                client = Mock()
                session = postgres.EphemeralSsh(
                    client=client, server_id=9235089, server_ip=SERVER,
                )
                with self.assertRaises(postgres.InfraError):
                    session.__enter__()
                with self.assertRaises(tls.DeploymentError):
                    tls.configure_with_ephemeral_key(client=client, server_id=9235089)
                command.assert_not_called()
                self.assertEqual(client.mock_calls, [])

    def test_verified_host_fingerprint_is_deterministic(self) -> None:
        self.assertEqual(
            trusted_host_fingerprint(ENTRY, SERVER),
            "SHA256:ZkAslGjFiUHdGf/WUL8rQvkib4PTvQatUV0OUQSncCA",
        )

    def test_postgres_host_key_mismatch_fails_immediately_and_cleans_up(self) -> None:
        ssh_calls = 0
        observed = "SHA256:networkPresentedFingerprint1234567890+/"

        def execute(
            args: list[str], **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            nonlocal ssh_calls
            if args[0] == "/usr/bin/ssh-keygen":
                private_key = pathlib.Path(args[args.index("-f") + 1])
                private_key.with_suffix(".pub").write_text("synthetic-public-key")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

            ssh_calls += 1
            return subprocess.CompletedProcess(
                args,
                255,
                stdout="",
                stderr=(
                    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                    "@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\n"
                    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                    "The fingerprint for the ED25519 key sent by the remote host is\n"
                    f"{observed}.\n"
                ),
            )

        with patch.dict(
            os.environ, {"TIMEWEB_SSH_KNOWN_HOSTS": ENTRY},
        ), patch.object(
            subprocess, "run", side_effect=execute,
        ), patch.object(
            postgres.time, "sleep",
        ) as sleep:
            client = Mock()
            client.create_ssh_key.return_value = 123
            session = postgres.EphemeralSsh(
                client=client, server_id=9235089, server_ip=SERVER,
            )
            with self.assertRaises(postgres.InfraError) as error:
                session.__enter__()

        message = str(error.exception)
        self.assertIn("SSH host key mismatch", message)
        self.assertIn(
            "SHA256:ZkAslGjFiUHdGf/WUL8rQvkib4PTvQatUV0OUQSncCA",
            message,
        )
        self.assertIn(observed, message)
        self.assertNotIn(KEY, message)
        self.assertEqual(ssh_calls, 1)
        sleep.assert_not_called()
        client.detach_ssh_key.assert_called_once_with(9235089, 123)
        client.delete_ssh_key.assert_called_once_with(123)
        self.assertIsNone(session._tmp)

    def test_postgres_uses_configured_key_without_network_key_discovery(self) -> None:
        self._exercise_consumer("postgres")

    def test_tls_uses_configured_key_without_network_key_discovery(self) -> None:
        self._exercise_consumer("tls")

    def _exercise_consumer(self, consumer: str) -> None:
        paths: list[pathlib.Path] = []
        ssh_calls: list[list[str]] = []

        def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if args[0] == "/usr/bin/ssh-keygen":
                private_key = pathlib.Path(args[args.index("-f") + 1])
                private_key.with_suffix(".pub").write_text("synthetic-public-key")
            else:
                self.assertEqual(args[0], "/usr/bin/ssh")
                option = next(arg for arg in args if arg.startswith("UserKnownHostsFile="))
                path = pathlib.Path(option.split("=", 1)[1])
                paths.append(path)
                self.assertEqual(path.read_text(), ENTRY + "\n")
                self.assertIn("StrictHostKeyChecking=yes", args)
                ssh_calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with self.subTest(consumer=consumer), patch.dict(
            os.environ, {"TIMEWEB_SSH_KNOWN_HOSTS": ENTRY},
        ), patch.object(subprocess, "run", side_effect=execute):
            client = Mock()
            client.create_ssh_key.return_value = 123
            if consumer == "postgres":
                with postgres.EphemeralSsh(
                    client=client, server_id=9235089, server_ip=SERVER,
                ) as session:
                    session.run("true")
            else:
                tls.configure_with_ephemeral_key(client=client, server_id=9235089)
            self.assertEqual(len(ssh_calls), 2)
            client.attach_ssh_key.assert_called_once_with(9235089, 123)
            client.detach_ssh_key.assert_called_once_with(9235089, 123)
            client.delete_ssh_key.assert_called_once_with(123)
            self.assertTrue(all(not path.exists() for path in paths))

    def test_production_ssh_mutations_share_one_serial_queue(self) -> None:
        workflows = (
            "timeweb-domain-tls.yml",
            "auth-private-network.yml",
            "auth-postgres.yml",
            "auth-app-deploy.yml",
        )
        workflow_dir = pathlib.Path(__file__).resolve().parent.parent / "workflows"
        for filename in workflows:
            with self.subTest(filename=filename):
                content = (workflow_dir / filename).read_text()
                self.assertIn("group: omnicio-production-ssh", content)
                self.assertIn("queue: max", content)
                self.assertIn("cancel-in-progress: false", content)

    def test_postgres_tolerates_slow_provider_key_propagation(self) -> None:
        ssh_attempts = 0

        def execute(
            args: list[str], **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            nonlocal ssh_attempts
            if args[0] == "/usr/bin/ssh-keygen":
                private_key = pathlib.Path(args[args.index("-f") + 1])
                private_key.with_suffix(".pub").write_text("synthetic-public-key")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

            ssh_attempts += 1
            if ssh_attempts <= 18:
                return subprocess.CompletedProcess(
                    args,
                    255,
                    stdout="",
                    stderr=f"root@{SERVER}: Permission denied (publickey).",
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with patch.dict(
            os.environ, {"TIMEWEB_SSH_KNOWN_HOSTS": ENTRY},
        ), patch.object(
            subprocess, "run", side_effect=execute,
        ), patch.object(
            postgres.time, "sleep",
        ) as sleep:
            client = Mock()
            client.create_ssh_key.return_value = 123
            with postgres.EphemeralSsh(
                client=client, server_id=9235089, server_ip=SERVER,
            ):
                pass

        self.assertEqual(ssh_attempts, 19)
        self.assertEqual(sleep.call_count, 18)
        client.attach_ssh_key.assert_called_once_with(9235089, 123)
        client.detach_ssh_key.assert_called_once_with(9235089, 123)
        client.delete_ssh_key.assert_called_once_with(123)

    def test_key_generation_failure_cleans_postgres_temporary_directory(self) -> None:
        with patch.dict(os.environ, {"TIMEWEB_SSH_KNOWN_HOSTS": ENTRY}), patch.object(
            subprocess, "run", side_effect=subprocess.CalledProcessError(1, "keygen"),
        ):
            client = Mock()
            session = postgres.EphemeralSsh(
                client=client, server_id=9235089, server_ip=SERVER,
            )
            with self.assertRaises(subprocess.CalledProcessError):
                session.__enter__()
            self.assertIsNone(session._tmp)
            self.assertEqual(client.mock_calls, [])

    def test_openssh_resolves_only_pinned_trust_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            args = ssh_base_args(root / "identity", root / "known_hosts")
            result = subprocess.run(
                args + ["-G", f"root@{SERVER}"],
                check=True, capture_output=True, text=True, timeout=10,
            )
            config = dict(line.split(" ", 1) for line in result.stdout.splitlines())
            self.assertEqual(config["stricthostkeychecking"], "true")
            self.assertEqual(config["userknownhostsfile"], str(root / "known_hosts"))
            self.assertEqual(config["globalknownhostsfile"], "/dev/null")
            self.assertEqual(config["hostkeyalgorithms"], "ssh-ed25519")
            self.assertEqual(config["identityagent"], "none")
            self.assertEqual(config["passwordauthentication"], "no")
            self.assertEqual(config["updatehostkeys"], "false")


if __name__ == "__main__":
    unittest.main()
