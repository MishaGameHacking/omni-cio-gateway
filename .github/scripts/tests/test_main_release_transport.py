"""Offline safety regressions; these are not a substitute for Android UI tests."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adb = load("isolated_adb")
snapshot = load("profile_snapshot")
installation = load("test_apk_installation")
profile = load("profile_ui_probe")


class PrivateAdbTests(unittest.TestCase):
    def test_private_endpoint_disables_phone_autoconnect(self):
        env = adb.private_environment(56001)
        self.assertEqual(env["ADB_SERVER_SOCKET"], "tcp:127.0.0.1:56001")
        self.assertEqual(env["ANDROID_ADB_SERVER_PORT"], "56001")
        self.assertEqual(env["ADB_MDNS_AUTO_CONNECT"], "")
        self.assertNotIn("ANDROID_SERIAL", env)

    def test_default_privileged_or_invalid_ports_rejected(self):
        for port in (5037, 0, 1023, 65536, True, "56001"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                adb.private_environment(port)

    def test_context_restores_environment_and_stops_only_owned_process(self):
        process = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "adb"
            executable.write_text("offline test")
            with patch.dict(os.environ, {"ANDROID_SERIAL": "physical-phone", "ADB_SERVER_SOCKET": "original"}), \
                    patch.object(adb, "unused_server_port", return_value=56001), \
                    patch.object(adb.subprocess, "Popen", return_value=process) as start, \
                    patch.object(adb, "wait_for_private_server"), \
                    patch.object(adb, "stop_owned_server") as stop:
                before = dict(os.environ)
                with adb.isolated_adb_server(executable, Path(tmp)):
                    self.assertEqual(os.environ["ANDROID_ADB_SERVER_PORT"], "56001")
                    self.assertNotIn("ANDROID_SERIAL", os.environ)
                self.assertEqual(dict(os.environ), before)
                stop.assert_called_once_with(process)
                command = start.call_args.args[0]
                self.assertIn("--one-device", command)
                self.assertIn("nodaemon", command)
                self.assertNotIn("kill-server", command)
                self.assertNotIn("physical-phone", command)

    def test_start_failure_restores_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "adb"
            executable.touch()
            before = dict(os.environ)
            with patch.object(adb, "unused_server_port", return_value=56001), \
                    patch.object(adb.subprocess, "Popen", side_effect=OSError("start failed")), \
                    self.assertRaises(OSError):
                with adb.isolated_adb_server(executable, Path(tmp)):
                    self.fail("Server did not start")
            self.assertEqual(dict(os.environ), before)

    def test_cleanup_cannot_replace_body_assertion(self):
        original = AssertionError("bad UI")
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "adb"
            executable.touch()
            with patch.object(adb, "unused_server_port", return_value=56001), \
                    patch.object(adb.subprocess, "Popen"), \
                    patch.object(adb, "wait_for_private_server"), \
                    patch.object(adb, "stop_owned_server", side_effect=OSError("cleanup")), \
                    self.assertRaises(AssertionError) as raised:
                with adb.isolated_adb_server(executable, Path(tmp)):
                    raise original
            self.assertIs(raised.exception, original)

    def test_dead_server_is_not_a_readiness_pass(self):
        with self.assertRaises(RuntimeError):
            adb.wait_for_private_server(Mock(poll=Mock(return_value=1)), 56001)

    def test_smart_socket_response_can_arrive_in_parts(self):
        connection = Mock()
        connection.recv.side_effect = [b"OK", b"AY"]
        context = Mock()
        context.__enter__ = Mock(return_value=connection)
        context.__exit__ = Mock(return_value=False)
        with patch.object(adb.socket, "create_connection", return_value=context):
            adb.wait_for_private_server(Mock(poll=Mock(return_value=None)), 56001)
        connection.sendall.assert_called_once_with(b"000chost:version")

    def test_readiness_deadline_is_finite(self):
        with self.assertRaises(TimeoutError):
            adb.wait_for_private_server(Mock(poll=Mock(return_value=None)), 56001, seconds=0)

    def test_stop_does_not_kill_an_exited_process(self):
        process = Mock(poll=Mock(return_value=0))
        adb.stop_owned_server(process)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_termination_escalates_only_after_owned_process_deadline(self):
        process = Mock(poll=Mock(return_value=None))
        process.wait.side_effect = [subprocess.TimeoutExpired("owned", 10), 0]
        adb.stop_owned_server(process)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_connected_transport_requires_exact_independent_state(self):
        for code, output, expected in ((0, "device\n", True), (0, "offline", False), (1, "device", False), (0, "", False)):
            with self.subTest(output=output), patch.object(installation, "run", return_value=Mock(returncode=code, stdout=output)) as run:
                self.assertEqual(installation.adb_transport_connected("adb", "emulator-5600"), expected)
                run.assert_called_once_with(["adb", "-s", "emulator-5600", "get-state"], timeout=5)

    def test_transport_probe_timeout_is_not_connected(self):
        with patch.object(installation, "run", side_effect=subprocess.TimeoutExpired("get-state", 5)):
            self.assertFalse(installation.adb_transport_connected("adb", "emulator-5600"))


class SnapshotTests(unittest.TestCase):
    XML = '<?xml version="1.0"?><hierarchy><node package="ru.omnicio.app.debug" text="Ready"/></hierarchy>'

    def test_each_read_requires_a_new_confirmed_file(self):
        paths = []
        def command(*args, **kwargs):
            if args[1] == "uiautomator":
                paths.append(args[-1])
                self.assertEqual(kwargs["timeout"], 45)
                return "UI hierchary dumped to: " + args[-1]
            self.assertEqual(args, ("shell", "cat", paths[-1]))
            return self.XML
        for _ in range(2):
            self.assertEqual(snapshot.fresh_tree(command).tag, "hierarchy")
        self.assertNotEqual(paths[0], paths[1])

    def test_null_root_or_old_filename_cannot_trigger_stale_read(self):
        for output in ("ERROR: null root node", "UI hierchary dumped to: /sdcard/analyst-ui-test.xml", ""):
            command = Mock(return_value=output)
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                snapshot.fresh_tree(command)
            self.assertEqual(command.call_count, 1)

    def test_malformed_empty_or_oversized_trees_do_not_pass(self):
        for xml in ("not xml", '<?xml version="1.0"?><hierarchy/>', '<?xml version="1.0"?><other><node/></other>', "x" * (snapshot.MAX_TREE_BYTES + 1)):
            def command(*args, **kwargs):
                return args[-1] if args[1] == "uiautomator" else xml
            with self.subTest(size=len(xml)), self.assertRaises((ValueError, ET.ParseError)):
                snapshot.fresh_tree(command)

    def test_tree_timeout_propagates(self):
        command = Mock(side_effect=subprocess.TimeoutExpired("tree", 45))
        with self.assertRaises(subprocess.TimeoutExpired):
            snapshot.fresh_tree(command)
        self.assertEqual(command.call_count, 1)

    def test_cleanup_preserves_primary_error_and_attempts_both_settings(self):
        original = AssertionError("bad frame")
        command = Mock(side_effect=installation.EmulatorTransportLost("offline"))
        snapshot.restore_device_settings(command, "1.0", "auto", original)
        self.assertEqual(command.call_count, 2)
        self.assertIn("EmulatorTransportLost", original.__notes__[0])

    def test_cleanup_error_still_fails_an_otherwise_successful_test(self):
        first = OSError("cannot restore")
        command = Mock(side_effect=[first, None])
        with self.assertRaises(OSError) as caught:
            snapshot.restore_device_settings(command, "1.0", "auto")
        self.assertIs(caught.exception, first)
        self.assertEqual(command.call_count, 2)

    def test_exercise_cannot_retry_app_assertion_as_cleanup_transport_loss(self):
        original = AssertionError("bad screen")
        driver = Mock()
        driver.command.side_effect = ["Night mode: auto", "1.0", installation.EmulatorTransportLost("offline"), None]
        driver.dashboards.side_effect = original
        with patch.object(profile, "ProfileProbe", return_value=driver), \
                patch.dict(sys.modules, {"profile_snapshot": snapshot}), \
                self.assertRaises(AssertionError) as caught:
            profile.exercise(Mock())
        self.assertIs(caught.exception, original)
        driver.profile_preflight.assert_not_called()

    def test_simultaneous_labels_use_one_fresh_frame(self):
        driver = profile.ProfileProbe(Mock())
        driver.tree = Mock(return_value=ET.fromstring('<hierarchy><node text="A"/><node text="B"/></hierarchy>'))
        self.assertEqual(len(driver.find_all(("A", "B"))), 2)
        driver.tree.assert_called_once()

    def test_missing_label_still_fails(self):
        driver = profile.ProfileProbe(Mock())
        driver.tree = Mock(return_value=ET.fromstring('<hierarchy><node text="A"/></hierarchy>'))
        with patch.object(profile.time, "monotonic", side_effect=[0, 0, 13]), \
                patch.object(profile.time, "sleep"), self.assertRaises(AssertionError):
            driver.find_all(("A", "B"))


if __name__ == "__main__":
    unittest.main()
