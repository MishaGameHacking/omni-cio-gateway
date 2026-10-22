"""Protocol, isolation and failure-preservation tests; no Android pass is inferred."""
import importlib.util
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from contextlib import contextmanager
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("persistent_ui", SCRIPTS / "persistent_ui.py")
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)
XML = b'<?xml version="1.0"?><hierarchy><node package="ru.omnicio.app.debug" text="A"/></hierarchy>'


class Stream:
    def __init__(self, data):
        self.data = bytearray(data)
        self.sent = []
    def settimeout(self, value):
        if value <= 0:
            raise AssertionError("Deadline not bounded")
    def recv(self, size):
        size = min(size, 3, len(self.data))
        result = bytes(self.data[:size])
        del self.data[:size]
        return result
    def sendall(self, data):
        self.sent.append(data)


def packet(sequence=1, status=1, payload=XML):
    return struct.pack(">III", sequence, status, len(payload)) + payload


class FrameProtocolTests(unittest.TestCase):
    def test_native_fold_state_is_preserved_separately_from_duplicate_labels(self):
        tree = ET.Element("hierarchy")
        ET.SubElement(tree, "node", {"text": "Основания (1)", "resource-id": "answer-sources",
                                    "state-description": "Свёрнуто"})
        ET.SubElement(tree, "node", {"text": "Основания (1)", "resource-id": "channel-sources",
                                    "state-description": "Развёрнуто & <проверено>"})
        reader = frames.FrameReader(Stream(packet(payload=ET.tostring(tree, encoding="utf-8"))))
        observed = list(reader.ready_tree().iter("node"))
        self.assertEqual(observed[0].get("state-description"), "Свёрнуто")
        self.assertEqual(observed[1].get("state-description"), "Развёрнуто & <проверено>")
        self.assertEqual(observed[1].get("resource-id"), "channel-sources")

    def test_partial_reads_and_monotonic_fresh_requests(self):
        stream = Stream(packet() + packet(2, payload=XML.replace(b'"A"', b'"B"')))
        reader = frames.FrameReader(stream)
        self.assertEqual(next(reader.ready_tree().iter("node")).get("text"), "A")
        self.assertEqual(next(reader.ready_tree().iter("node")).get("text"), "B")
        self.assertEqual(stream.sent, [struct.pack(">I", 1), struct.pack(">I", 2)])

    def test_null_root_does_not_reuse_frame_or_disconnect(self):
        reader = frames.FrameReader(Stream(packet(status=0, payload=b"") + packet(2)))
        self.assertIsNone(reader.tree())
        self.assertFalse(reader.broken)
        self.assertEqual(reader.ready_tree().tag, "hierarchy")

    def test_stale_out_of_order_and_unknown_status_are_fatal(self):
        for data in (packet(0), packet(2), packet(status=9), packet(status=0)):
            with self.subTest(data=data[:12]):
                reader = frames.FrameReader(Stream(data))
                with self.assertRaises(ValueError):
                    reader.tree()
                with self.assertRaises(ConnectionError):
                    reader.tree()

    def test_oversized_payload_is_rejected_before_read(self):
        stream = Stream(struct.pack(">III", 1, 1, frames.MAX_FRAME_BYTES + 1))
        reader = frames.FrameReader(stream)
        with self.assertRaises(ValueError):
            reader.tree()

    def test_truncated_frame_and_timeout_cannot_return_success(self):
        reader = frames.FrameReader(Stream(packet()[:-1]))
        with self.assertRaises(ConnectionError):
            reader.tree()
        stream = Mock()
        stream.recv.side_effect = TimeoutError("frame timeout")
        reader = frames.FrameReader(stream)
        with self.assertRaises(TimeoutError):
            reader.tree()

    def test_empty_malformed_or_entity_xml_is_rejected(self):
        for xml in (b"", b"not xml", b"<hierarchy/>", b"<other><node/></other>",
                    b'<!DOCTYPE hierarchy [<!ENTITY x "bad">]><hierarchy><node/></hierarchy>'):
            reader = frames.FrameReader(Stream(packet(payload=xml)))
            with self.subTest(xml=xml), self.assertRaises((ValueError, ET.ParseError)):
                reader.tree()

    def test_deadline_is_global_not_reset_for_each_packet_fragment(self):
        stream = Stream(b"x")
        with patch.object(frames.time, "monotonic", return_value=2), self.assertRaises(TimeoutError):
            frames.read_exact(stream, 1, deadline=1)

    def test_disposable_check_refuses_physical_wrong_avd_or_api(self):
        for values in (("other-avd\nOK",), ("analyst-install-1-1\nOK", "0"),
                       ("analyst-install-1-1\nOK", "1", "34")):
            device = Mock(side_effect=[Mock(returncode=0, stdout=v) for v in values])
            with self.subTest(values=values), self.assertRaises(ValueError):
                frames.assert_disposable(device)
            self.assertFalse(any("install" in call.args for call in device.call_args_list))

    def test_disposable_check_accepts_owned_supported_api(self):
        values = ("analyst-install-123-2\nOK", "1", "37")
        device = Mock(side_effect=[Mock(returncode=0, stdout=value) for value in values])
        frames.assert_disposable(device)
        self.assertEqual(device.call_count, 3)

    def test_other_guest_versions_cannot_reuse_current_runtime_evidence(self):
        for api in ("35", "36", "38", "37.0", "", "unknown"):
            values = ("analyst-install-123-2\nOK", "1", api)
            device = Mock(side_effect=[Mock(returncode=0, stdout=value) for value in values])
            with self.subTest(api=api), self.assertRaises(ValueError):
                frames.assert_disposable(device)
            self.assertEqual(device.call_count, 3)
            self.assertFalse(any("install" in call.args for call in device.call_args_list))

    def test_checked_preserves_both_output_streams_and_code(self):
        device = Mock(return_value=Mock(returncode=7, stdout="stdout error", stderr="stderr error"))
        with self.assertRaisesRegex(RuntimeError, "7.*stdout error") as caught:
            frames.checked(device, "shell", "test")
        self.assertIn("stderr error", str(caught.exception))

    def test_cleanup_never_kills_app_or_global_adb_and_preserves_assertion(self):
        original = AssertionError("wrong screen")
        connection = Mock()
        connection.sendall.side_effect = ConnectionError("closed")
        device = Mock(side_effect=OSError("device lost"))
        frames.cleanup_session(device, connection, 53000, original)
        connection.close.assert_called_once()
        self.assertIn("CI frame cleanup failed", original.__notes__[0])
        self.assertEqual(device.call_args_list[0].args, ("shell", "am", "force-stop", frames.DRIVER_PACKAGE))
        self.assertEqual(device.call_args_list[1].args, ("forward", "--remove", "tcp:53000"))

    def test_cleanup_failure_blocks_an_otherwise_successful_pass(self):
        device = Mock(side_effect=OSError("stop failed"))
        with self.assertRaises(OSError):
            frames.cleanup_session(device, None, None, None)

    def test_bad_handshake_is_not_retried_as_ready(self):
        connection = Mock()
        connection.recv.return_value = struct.pack(">I", 99)
        with patch.object(frames.socket, "create_connection", return_value=connection), self.assertRaises(ValueError):
            frames.connect_session(53000, "a" * 64)
        connection.close.assert_called_once()


class FrameReadinessTests(unittest.TestCase):
    def test_dialog_transition_requires_new_frame_not_previous_tree(self):
        stream = Stream(packet() + packet(2, status=0, payload=b"")
                        + packet(3, payload=XML.replace(b'"A"', b'"B"')))
        reader = frames.FrameReader(stream)
        self.assertEqual(next(reader.ready_tree().iter("node")).get("text"), "A")
        with patch.object(frames.time, "sleep"):
            self.assertEqual(next(reader.ready_tree().iter("node")).get("text"), "B")
        self.assertEqual(stream.sent, [struct.pack(">I", n) for n in (1, 2, 3)])
        self.assertFalse(reader.broken)

    def test_permanent_null_root_fails_with_one_budget_not_per_poll(self):
        now = [0.0]
        reader = frames.FrameReader(Mock())
        def advance(seconds):
            now[0] += seconds
        with patch.object(frames, "FRAME_TIMEOUT", 0.25), \
                patch.object(frames.time, "monotonic", side_effect=lambda: now[0]), \
                patch.object(frames.time, "sleep", side_effect=advance), \
                patch.object(reader, "tree", return_value=None) as read, \
                self.assertRaisesRegex(RuntimeError, "not ready within"):
            reader.ready_tree()
        self.assertEqual(read.call_count, 3)
        self.assertTrue(all(call.kwargs == {"deadline": 0.25} for call in read.call_args_list))
        self.assertEqual(now[0], 0.25)

    def test_invalid_packet_after_null_is_not_retried(self):
        stream = Stream(packet(status=0, payload=b"") + packet(2, status=99) + packet(3))
        reader = frames.FrameReader(stream)
        with patch.object(frames.time, "sleep"), self.assertRaises(ValueError):
            reader.ready_tree()
        self.assertEqual(len(stream.sent), 2)
        self.assertTrue(reader.broken)

    def test_disconnect_after_null_is_not_retried(self):
        stream = Stream(packet(status=0, payload=b""))
        reader = frames.FrameReader(stream)
        with patch.object(frames.time, "sleep"), self.assertRaises(ConnectionError):
            reader.ready_tree()
        self.assertEqual(len(stream.sent), 2)
        self.assertTrue(reader.broken)

    def test_does_not_wait_for_desired_package_or_hide_wrong_screen(self):
        stream = Stream(packet(payload=XML.replace(b"ru.omnicio.app.debug", b"other.app")))
        reader = frames.FrameReader(stream)
        root = reader.ready_tree()
        self.assertEqual(next(root.iter("node")).get("package"), "other.app")
        self.assertEqual(len(stream.sent), 1)

    def test_expired_budget_sends_no_new_request(self):
        stream = Mock()
        reader = frames.FrameReader(stream)
        with patch.object(frames.time, "monotonic", return_value=10), self.assertRaises(TimeoutError):
            reader.tree(deadline=9)
        stream.sendall.assert_not_called()

    def test_socket_send_and_fragments_share_remaining_budget(self):
        stream = Stream(packet())
        stream.settimeout = Mock()
        reader = frames.FrameReader(stream)
        with patch.object(frames.time, "monotonic", return_value=5):
            self.assertEqual(reader.tree(deadline=7).tag, "hierarchy")
        self.assertGreater(stream.settimeout.call_count, 1)
        self.assertTrue(all(call.args == (2,) for call in stream.settimeout.call_args_list))

    def test_late_parsed_frame_cannot_pass_deadline(self):
        now = [0.0]
        reader = frames.FrameReader(Stream(packet()))
        real_parse = ET.fromstring
        def parse_late(payload):
            now[0] = 31.0
            return real_parse(payload)
        with patch.object(frames.time, "monotonic", side_effect=lambda: now[0]), \
                patch.object(frames.ET, "fromstring", side_effect=parse_late), \
                self.assertRaises(TimeoutError):
            reader.ready_tree()
        self.assertTrue(reader.broken)


class InstrumentationLaunchTests(unittest.TestCase):
    def test_launch_keeps_the_public_watcher_alive_and_redirects_descriptors(self):
        device = Mock(return_value=Mock(returncode=0, stdout=""))
        log = frames.start_instrumentation(device, "a" * 32, "b" * 64)
        args = device.call_args.args
        self.assertEqual(args[0], "shell")
        self.assertIn("am instrument -w -r", args[1])
        self.assertIn(frames.DRIVER_COMPONENT, args[1])
        self.assertTrue(args[1].endswith("2>&1 < /dev/null &"))
        self.assertIn(log, args[1])
        self.assertNotIn("kill-server", args[1])

    def test_interpolated_session_values_reject_shell_syntax(self):
        for session, token in ((";reboot", "b" * 64), ("a" * 32, "$(id)"), ("A" * 32, "b" * 64)):
            device = Mock()
            with self.subTest(session=session), self.assertRaises(ValueError):
                frames.start_instrumentation(device, session, token)
            device.assert_not_called()

    def test_unavailable_diagnostics_do_not_replace_an_assertion(self):
        original = AssertionError("bad UI")
        frames.report_session_failure(Mock(side_effect=OSError("gone")), "/data/local/tmp/test", "a" * 64, original)
        self.assertIn("diagnostics unavailable", original.__notes__[0])


class ProfileSessionTests(unittest.TestCase):
    def load_profile(self):
        spec = importlib.util.spec_from_file_location("frame_test_profile", SCRIPTS / "profile_ui_probe.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_missing_session_has_no_legacy_shell_fallback(self):
        profile = self.load_profile()
        device = Mock()
        probe = profile.ProfileProbe(device)
        with self.assertRaises(RuntimeError):
            probe.tree()
        device.assert_not_called()

    def test_existing_checks_are_wrapped_in_one_session(self):
        profile = self.load_profile()
        events = []
        reader = Mock()
        device = Mock()
        @contextmanager
        def session(target):
            self.assertIs(target, device)
            events.append("start")
            try:
                yield reader
            finally:
                events.append("end")
        with patch.object(frames, "frame_session", session), \
                patch.dict(sys.modules, {"persistent_ui": frames}), \
                patch.object(profile, "exercise_checks") as checks:
            profile.exercise(device)
        checks.assert_called_once_with(device, reader)
        self.assertEqual(events, ["start", "end"])

    def test_frame_session_cannot_swallow_a_real_ui_assertion(self):
        profile = self.load_profile()
        original = AssertionError("wrong palette")
        device = Mock()
        @contextmanager
        def session(target):
            yield Mock()
        with patch.object(frames, "frame_session", session), \
                patch.dict(sys.modules, {"persistent_ui": frames}), \
                patch.object(profile, "exercise_checks", side_effect=original), \
                self.assertRaises(AssertionError) as caught:
            profile.exercise(device)
        self.assertIs(caught.exception, original)


class DriverSourceTests(unittest.TestCase):
    def test_helper_is_separate_test_only_without_runtime_dependency(self):
        root = SCRIPTS.parents[1]
        manifest = (root / "ci-ui-driver/src/main/AndroidManifest.xml").read_text()
        build = (root / "ci-ui-driver/build.gradle.kts").read_text()
        java = (root / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java").read_text()
        self.assertIn('android:testOnly="true"', manifest)
        self.assertIn('android:targetPackage="ru.omnicio.ciframe"', manifest)
        self.assertNotIn("uses-permission", manifest)
        self.assertIn("minSdk = 37", build)
        self.assertIn("it.enable = false", build)
        self.assertIn("isMinifyEnabled = true", build)
        self.assertIn("isShrinkResources = true", build)
        self.assertEqual(java.count("getUiAutomation("), 1)
        self.assertIn("automation.clearCache()", java)
        self.assertIn("getRootInActiveWindow()", java)
        self.assertEqual(java.count("automation.getWindows()"), 1)
        self.assertIn("MessageDigest.isEqual", java)
        self.assertNotIn("waitForIdle", java)
        self.assertNotIn("executeShellCommand", java)
        self.assertNotIn("getDeclared", java)

    def test_real_java_ime_observation_preserves_visibility_beyond_diagnostic_cap(self):
        javac, java = shutil.which("javac"), shutil.which("java")
        if javac is None or java is None:
            self.skipTest("JDK required for the host IME-observation regression")
        source = (SCRIPTS.parents[1] / "ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java").read_text()
        # Compile the production observer verbatim with narrow public-API value
        # stubs. This checks its data handling, not Android's window enumeration.
        observer = source[source.index("    private record WindowObservation"):source.index("    private static void writeNode")]
        constant = re.search(r"private static final int MAX_IME_WINDOWS = \d+;", source).group()
        harness = """
import java.util.ArrayList;
import java.util.List;
public class ImeObservationTest {
    static final class Rect {
        int left, top, right, bottom;
        Rect() {}
        Rect(int l, int t, int r, int b) { left=l; top=t; right=r; bottom=b; }
        boolean isEmpty() { return left >= right || top >= bottom; }
        static boolean intersects(Rect a, Rect b) {
            return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
        }
    }
    static final class AccessibilityWindowInfo {
        static final int TYPE_INPUT_METHOD = 2;
        final int id, type, displayId;
        final Rect bounds;
        final boolean active, focused;
        int boundsReads;
        AccessibilityWindowInfo(int i, int t, int d, Rect b, boolean a, boolean f) {
            id=i; type=t; displayId=d; bounds=b; active=a; focused=f;
        }
        int getId() { return id; }
        int getType() { return type; }
        int getDisplayId() { return displayId; }
        boolean isActive() { return active; }
        boolean isFocused() { return focused; }
        void getBoundsInScreen(Rect out) {
            boundsReads++;
            out.left=bounds.left; out.top=bounds.top; out.right=bounds.right; out.bottom=bounds.bottom;
        }
    }
    static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        Rect display = new Rect(0, 0, 640, 320);
        AccessibilityWindowInfo app = new AccessibilityWindowInfo(73, 1, 0, display, true, true);
        AccessibilityWindowInfo ime = new AccessibilityWindowInfo(74, 2, 0, new Rect(0, 180, 640, 320), false, false);
        WindowObservation present = observeWindows(List.of(app, ime), display, 73);
        require(present.keyboardVisible(), "unfocused IME remains visible");
        require(present.rootPresent() && present.rootFocused(), "app window facts retained");
        require(present.windowCount() == 2 && present.imeCount() == 1, "separate total and IME counts");
        require(present.imeWindows().equals("[[74,0,2,0,180,640,320,false,false,true]]"), "exact bounded geometry metadata");
        require(ime.boundsReads == 1, "visibility and metadata use the same bounds read");
        require(app.boundsReads == 0, "non-IME bounds do not control keyboard visibility");

        AccessibilityWindowInfo outside = new AccessibilityWindowInfo(75, 2, 0, new Rect(640, 0, 740, 320), true, true);
        AccessibilityWindowInfo empty = new AccessibilityWindowInfo(76, 2, 0, new Rect(0, 0, 0, 320), true, true);
        WindowObservation absent = observeWindows(List.of(app, outside, empty), display, 73);
        require(!absent.keyboardVisible() && absent.imeCount() == 2, "outside and empty IME are observed but invisible");
        AccessibilityWindowInfo partial = new AccessibilityWindowInfo(77, 2, 9, new Rect(-10, -10, 1, 1), false, false);
        require(observeWindows(List.of(partial), display, 73).keyboardVisible(), "unchanged intersection-only predicate");

        List<AccessibilityWindowInfo> many = new ArrayList<>();
        for (int i=0; i<8; i++) many.add(new AccessibilityWindowInfo(100+i, 2, 0, new Rect(0, 320, 640, 400), false, false));
        many.add(ime);
        WindowObservation capped = observeWindows(many, display, 73);
        require(capped.keyboardVisible() && capped.imeCount() == 9, "ninth IME still controls visibility");
        require(!capped.rootPresent() && !capped.rootFocused(), "absent root is explicit");
        require(capped.imeWindows().split("\\\\[", -1).length == 10, "only eight window records retained");
        require(!capped.imeWindows().contains("[74,"), "ninth metadata omitted without hiding IME");
        WindowObservation none = observeWindows(List.of(), display, 73);
        require(!none.keyboardVisible() && none.imeCount() == 0 && none.imeWindows().equals("[]"), "no invented IME");
        System.out.println("IME_OBSERVATION_CASES=6");
    }
""" + constant + "\n" + observer + "\n}\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ImeObservationTest.java"
            path.write_text(harness)
            built = subprocess.run([javac, "--release", "17", "-d", directory, str(path)],
                                   capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([java, "-cp", directory, "ImeObservationTest"],
                                    capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("IME_OBSERVATION_CASES=6", result.stdout)


if __name__ == "__main__":
    unittest.main()
