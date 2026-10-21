"""Synthetic counter/identity adversaries, separate from actual emulator proof."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_recovery_ui_probe import chat_counters, accepted_single_request, recovered_single_request, native_send_button

REQUEST = "01234567-89ab-4cde-8fab-0123456789ab"
OTHER = "fedcba98-7654-4321-8abc-fedcba987654"


def parts(**changes):
    return {"message-posts": "1", "message-request-id": REQUEST,
            "by-request-gets": "0", "recovered-request-id": "none", **changes}


class ChatRecoveryEvidenceTests(unittest.TestCase):
    def test_matching_counters_prove_one_post_and_one_read(self):
        accepted = chat_counters(parts(), 5, "ready")
        self.assertEqual(REQUEST, accepted_single_request(accepted)["message_request_id"])
        self.assertIsNone(recovered_single_request(accepted, REQUEST))
        recovered = chat_counters(parts(**{"by-request-gets": "1", "recovered-request-id": REQUEST}), 6, "ready")
        self.assertEqual(1, recovered_single_request(recovered, REQUEST)["message_posts"])

    def test_missing_inconsistent_and_unbound_counters_do_not_prove_recovery(self):
        for key in parts():
            changed = parts(); del changed[key]
            with self.subTest(missing=key), self.assertRaises(AssertionError):
                chat_counters(changed, 5, "ready")
        for changed in (parts(**{"message-posts": "-1"}), parts(**{"message-posts": "0"}),
                        parts(**{"message-request-id": "none"}), parts(**{"message-request-id": "arbitrary"}),
                        parts(**{"recovered-request-id": REQUEST}), parts(**{"by-request-gets": "6"})):
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                chat_counters(changed, 5, "ready")

    def test_second_post_or_different_uuid_is_never_a_successful_recovery(self):
        for count, sent, recovered in ((2, REQUEST, REQUEST), (1, OTHER, OTHER), (1, REQUEST, OTHER)):
            value = chat_counters(parts(**{"message-posts": str(count), "message-request-id": sent,
                                          "by-request-gets": "1", "recovered-request-id": recovered}), 8, "ready")
            with self.subTest(count=count, sent=sent, recovered=recovered), self.assertRaises(AssertionError):
                recovered_single_request(value, REQUEST)

    def test_get_before_explicit_recovery_action_is_rejected(self):
        value = chat_counters(parts(**{"by-request-gets": "1", "recovered-request-id": REQUEST}), 8, "ready")
        with self.assertRaises(AssertionError):
            accepted_single_request(value)

    def test_seeded_legacy_id_is_only_valid_for_the_job_case(self):
        seed = {"message-posts": "0", "message-request-id": "none", "by-request-gets": "1", "recovered-request-id": "synthetic-request"}
        self.assertEqual("synthetic-request", chat_counters(seed, 3, "job")["recovered_request_id"])
        with self.assertRaises(AssertionError):
            chat_counters(seed, 3, "ready")

    def test_disabled_explanation_without_a_native_button_does_not_block_send(self):
        root = ET.Element("hierarchy")
        node = ET.SubElement(root, "node", {"package": "ru.omnicio.app.debug", "visible-to-user": "true",
                                           "class": "android.widget.TextView", "enabled": "false", "text": "Отправить",
                                           "bounds": "[20,100][300,160]"})
        self.assertIsNone(native_send_button(root, enabled=False))
        node.set("class", "android.widget.Button")
        self.assertIs(node, native_send_button(root, enabled=False))
        self.assertIsNone(native_send_button(root, enabled=True))
        node.set("enabled", "true")
        self.assertIsNone(native_send_button(root, enabled=False))
        self.assertIs(node, native_send_button(root, enabled=True))
        node.set("package", "other.app")
        self.assertIsNone(native_send_button(root, enabled=True))

    def test_compose_send_reads_disabled_parent_not_enabled_role_child(self):
        control = ET.Element("node", {"package": "ru.omnicio.app.debug", "visible-to-user": "true",
                                      "class": "android.view.View", "clickable": "true", "enabled": "false",
                                      "bounds": "[20,100][300,160]"})
        ET.SubElement(control, "node", {"visible-to-user": "true", "text": "Отправить", "enabled": "true"})
        ET.SubElement(control, "node", {"package": "ru.omnicio.app.debug", "visible-to-user": "true",
                                       "class": "android.widget.Button", "clickable": "false", "enabled": "true"})
        self.assertIs(native_send_button(control, enabled=False), control)
        self.assertIsNone(native_send_button(control, enabled=True))


if __name__ == "__main__":
    unittest.main()
