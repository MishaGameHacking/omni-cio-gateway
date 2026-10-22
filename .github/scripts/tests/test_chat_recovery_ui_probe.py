"""Synthetic counter/identity adversaries, separate from actual emulator proof."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_recovery_ui_probe import chat_counters, accepted_single_request, recovered_single_request, native_send_button
import chat_recovery_ui_probe as recovery

REQUEST = "01234567-89ab-4cde-8fab-0123456789ab"
OTHER = "fedcba98-7654-4321-8abc-fedcba987654"


def parts(**changes):
    return {"message-posts": "1", "message-request-id": REQUEST,
            "by-request-gets": "0", "recovered-request-id": "none", **changes}


def chat_node(parent, bounds, **changes):
    values = {"package": recovery.PACKAGE, "visible-to-user": "true", "enabled": "true",
              "class": "android.view.View", "bounds": bounds, "text": ""}
    return ET.SubElement(parent, "node", values | changes)


def chat_frame(*, draft="", enabled=True, saved=True, message_tag=recovery.USER_MESSAGE):
    tree = ET.Element("hierarchy", {"display-width": "400", "display-height": "800", "active-window-id": "7"})
    app = chat_node(tree, "[0,0][400,800]")
    history = chat_node(app, "[0,100][400,500]", **{"resource-id": recovery.HISTORY, "scrollable": "true"})
    if saved:
        chat_node(history, "[20,220][190,250]", **{"resource-id": message_tag, "text": "UIprobe"})
    composer = chat_node(app, "[0,500][400,780]", scrollable="true")
    field = chat_node(composer, "[20,600][380,688]", **{"resource-id": recovery.QUESTION})
    chat_node(field, "[20,600][380,688]", **{"class": "android.widget.EditText", "editable": "true",
              "text": draft, "enabled": str(enabled).lower()})
    chat_node(composer, "[20,700][380,760]", **{"class": "android.widget.Button", "text": recovery.SEND, "enabled": "false"})
    return tree


def tagged(tree, resource):
    return next(node for node in tree.iter("node") if node.get("resource-id") == resource)


class RecoveryProbe:
    """GET acknowledgement can arrive while durable application is still pending."""
    def __init__(self, *, applied_after_reads=3, saved=True, stuck_draft="UIprobe", stuck_enabled=False):
        self.phase = "before"
        self.applied_after_reads = applied_after_reads
        self.saved = saved
        self.stuck_draft = stuck_draft
        self.stuck_enabled = stuck_enabled
        self.recovery_reads = 0
        self.scrolls = 0
        self.post_taps = 0
        self.get_taps = 0

    def observed(self):
        return {"message_posts": int(self.phase != "before"),
                "message_request_id": None if self.phase == "before" else REQUEST,
                "by_request_gets": int(self.phase == "get"),
                "recovered_request_id": REQUEST if self.phase == "get" else None}

    def tree(self):
        if self.phase == "get":
            self.recovery_reads += 1
        applied = (self.phase == "get" and self.applied_after_reads is not None
                   and self.recovery_reads >= self.applied_after_reads)
        return chat_frame(draft="" if applied else self.stuck_draft,
                          enabled=True if applied else self.stuck_enabled,
                          saved=applied and self.saved and self.scrolls > 0)

    def tap_visible(self, text):
        if text != recovery.SEND or self.phase != "before":
            raise AssertionError("Repeated message action")
        self.post_taps += 1
        self.phase = "post"

    def tap_resource(self, resource, area):
        if resource != "recover-request-" + REQUEST or area != recovery.HISTORY or self.phase != "post":
            raise AssertionError("Repeated or unrelated recovery action")
        self.get_taps += 1
        self.phase = "get"

    def reveal(self, text, area):
        if text != recovery.LOST_REPLY or area != recovery.HISTORY:
            raise AssertionError("A generic label search cannot prove saved delivery")

    def wait_for(self, read, message):
        for _ in range(4):
            value = read()
            if value is not None and value is not False:
                return value
        raise AssertionError(message)

    def _semantic_scroll_callback(self, area, direction):
        if area != recovery.HISTORY or direction != "start":
            raise AssertionError("The latest assistant reply follows the saved question")
        def scroll(*_coordinates):
            self.scrolls += 1
        return scroll


class ChatRecoveryEvidenceTests(unittest.TestCase):
    def test_matching_counters_prove_one_post_and_one_read(self):
        accepted = chat_counters(parts(), 5, "ready")
        self.assertEqual(accepted_single_request(accepted)["message_request_id"], REQUEST)
        self.assertIsNone(recovered_single_request(accepted, REQUEST))
        recovered = chat_counters(parts(**{"by-request-gets": "1", "recovered-request-id": REQUEST}), 6, "ready")
        self.assertEqual(recovered_single_request(recovered, REQUEST)["message_posts"], 1)

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
        self.assertEqual(chat_counters(seed, 3, "job")["recovered_request_id"], "synthetic-request")
        with self.assertRaises(AssertionError):
            chat_counters(seed, 3, "ready")

    def test_disabled_explanation_without_a_native_button_does_not_block_send(self):
        root = ET.Element("hierarchy")
        node = ET.SubElement(root, "node", {"package": "ru.omnicio.app.debug", "visible-to-user": "true",
                                           "class": "android.widget.TextView", "enabled": "false", "text": "Отправить",
                                           "bounds": "[20,100][300,160]"})
        self.assertIsNone(native_send_button(root, enabled=False))
        node.set("class", "android.widget.Button")
        self.assertIs(native_send_button(root, enabled=False), node)
        self.assertIsNone(native_send_button(root, enabled=True))
        node.set("enabled", "true")
        self.assertIsNone(native_send_button(root, enabled=False))
        self.assertIs(native_send_button(root, enabled=True), node)
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


class ChatRecoveryApplicationTests(unittest.TestCase):
    def test_history_matches_only_the_tagged_user_text_in_the_one_list(self):
        for resource in (recovery.USER_MESSAGE, recovery.PACKAGE + ":id/" + recovery.USER_MESSAGE):
            tree = chat_frame(message_tag=resource)
            with self.subTest(resource=resource):
                self.assertEqual(recovery.persisted_user_message(tree).get("text"), "UIprobe")

    def test_draft_and_assistant_answer_cannot_replace_a_saved_user_message(self):
        for tree in (chat_frame(saved=False, draft="UIprobe"),
                     chat_frame(message_tag="assistant-answer-text")):
            with self.subTest(tree=ET.tostring(tree)):
                self.assertIsNone(recovery.persisted_user_message(tree))
        tree = chat_frame()
        history = tagged(tree, recovery.HISTORY)
        message = tagged(tree, recovery.USER_MESSAGE)
        history.remove(message)
        tree[0].append(message)
        self.assertIsNone(recovery.persisted_user_message(tree))

    def test_foreign_hidden_mismatched_or_offscreen_message_does_not_prove_delivery(self):
        changes = ({"package": "other.app"}, {"visible-to-user": "false"},
                   {"text": "different question"}, {"bounds": "[20,490][190,520]"})
        for attributes in changes:
            tree = chat_frame()
            tagged(tree, recovery.USER_MESSAGE).attrib.update(attributes)
            with self.subTest(attributes=attributes):
                self.assertIsNone(recovery.persisted_user_message(tree))
        tree = chat_frame()
        tree[0].set("visible-to-user", "false")
        self.assertIsNone(recovery.persisted_user_message(tree))

    def test_ambiguous_history_or_recovered_message_is_rejected(self):
        for resource in (recovery.HISTORY, recovery.USER_MESSAGE):
            tree = chat_frame()
            selected = tagged(tree, resource)
            parent = tree[0] if resource == recovery.HISTORY else tagged(tree, recovery.HISTORY)
            parent.append(ET.fromstring(ET.tostring(selected)))
            with self.subTest(resource=resource), self.assertRaisesRegex(AssertionError, "Ambiguous"):
                recovery.persisted_user_message(tree)

    def test_cleared_enabled_native_editor_accepts_nested_and_merged_semantics(self):
        for merged in (False, True):
            tree = chat_frame()
            field = tagged(tree, recovery.QUESTION)
            if merged:
                native = field[0]
                field.attrib.update(native.attrib | {"resource-id": recovery.QUESTION})
                field.remove(native)
            with self.subTest(merged=merged):
                editor = recovery.recovered_composer(tree)
                self.assertIsNotNone(editor)
                self.assertEqual(editor.get("text"), "")
                self.assertEqual(editor.get("editable"), "true")

    def test_empty_label_non_native_disabled_or_nonempty_editor_is_not_ready(self):
        for attributes in ({"editable": "false"}, {"enabled": "false"}, {"text": "UIprobe"},
                           {"visible-to-user": "false"}, {"package": "other.app"},
                           {"bounds": "[20,775][380,799]"}):
            tree = chat_frame()
            tagged(tree, recovery.QUESTION)[0].attrib.update(attributes)
            with self.subTest(attributes=attributes):
                self.assertIsNone(recovery.recovered_composer(tree))

    def test_enabled_child_cannot_override_a_disabled_question_or_composer(self):
        for parent in ("field", "composer", "app"):
            tree = chat_frame()
            field = tagged(tree, recovery.QUESTION)
            owner = {"field": field, "composer": tree[0][1], "app": tree[0]}[parent]
            owner.set("enabled", "false")
            with self.subTest(parent=parent):
                self.assertIsNone(recovery.recovered_composer(tree))

    def test_unbound_or_duplicate_question_is_not_a_clear_composer(self):
        tree = chat_frame()
        tagged(tree, recovery.QUESTION).set("resource-id", "unrelated-editor")
        self.assertIsNone(recovery.recovered_composer(tree))
        tree = chat_frame()
        field = tagged(tree, recovery.QUESTION)
        tree[0].append(ET.fromstring(ET.tostring(field)))
        with self.assertRaisesRegex(AssertionError, "Ambiguous"):
            recovery.recovered_composer(tree)

    @patch("profile_scroll.time.sleep")
    def test_get_ack_waits_for_durable_application_then_reads_history_backward(self, _sleep):
        probe = RecoveryProbe()
        result = recovery.exercise_chat_recovery(probe, probe.observed)
        self.assertGreaterEqual(probe.recovery_reads, 3)
        self.assertEqual((probe.post_taps, probe.get_taps, probe.scrolls), (1, 1, 1))
        self.assertTrue(result["saved_user_message_visible"])
        self.assertTrue(result["composer_cleared_and_enabled"])
        self.assertFalse(result["screen_remounted"])

    def test_successful_get_without_applied_recovery_cannot_pass_on_the_draft(self):
        for draft, enabled in (("UIprobe", True), ("", False)):
            probe = RecoveryProbe(applied_after_reads=None, stuck_draft=draft, stuck_enabled=enabled)
            with self.subTest(draft=draft, enabled=enabled), self.assertRaisesRegex(AssertionError, "clear its draft"):
                recovery.exercise_chat_recovery(probe, probe.observed)
            self.assertEqual((probe.post_taps, probe.get_taps, probe.scrolls), (1, 1, 0))

    @patch("profile_scroll.time.sleep")
    def test_clear_composer_does_not_replace_the_saved_history_message(self, _sleep):
        probe = RecoveryProbe(applied_after_reads=1, saved=False)
        with self.assertRaisesRegex(AssertionError, "recovered user message"):
            recovery.exercise_chat_recovery(probe, probe.observed)
        self.assertEqual((probe.post_taps, probe.get_taps, probe.scrolls), (1, 1, 10))


if __name__ == "__main__":
    unittest.main()
