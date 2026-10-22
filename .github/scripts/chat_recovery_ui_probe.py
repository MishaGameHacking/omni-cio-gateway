"""Observe one accepted chat request recovered through GET after a lost reply."""
from __future__ import annotations

import re

from native_label_target import _ancestry, _display, _intersection, _visible_geometry
from profile_scroll import _bounds, _visible_app_node

PACKAGE = "ru.omnicio.app.debug"
UUID = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
SEND = "Отправить"
LOST_REPLY = "СИНТЕТИЧЕСКАЯ потеря ответа после принятия запроса. Сверьте сохранённый идентификатор."
HISTORY = "workspace-content"
USER_MESSAGE = "assistant-user-message"
QUESTION = "assistant-question"


def _tagged_nodes(tree, resource):
    names = {resource, f"{PACKAGE}:id/{resource}"}
    return [node for node in tree.iter("node")
            if _visible_app_node(node) and node.get("visible-to-user") == "true"
            and node.get("resource-id") in names]


def _single_tag(tree, resource):
    nodes = _tagged_nodes(tree, resource)
    if len(nodes) > 1:
        raise AssertionError("Ambiguous chat resource: " + resource)
    return nodes[0] if nodes else None


def recovered_composer(tree):
    """A cleared native editor is usable only after all recovery/job guards clear."""
    field = _single_tag(tree, QUESTION)
    display = _display(tree)
    if field is None or display is None:
        return None
    parents = {child: parent for parent in tree.iter() for child in parent}
    editors = [node for node in field.iter("node")
               if _visible_app_node(node) and node.get("visible-to-user") == "true"
               and node.get("editable") == "true"]
    if len(editors) != 1:
        return None
    editor = editors[0]
    if editor.get("text") != "" or any(node.get("enabled") != "true"
                                      for node in _ancestry(editor, parents)):
        return None
    return editor if _visible_geometry(editor, parents, display[0]) is not None else None


def persisted_user_message(tree):
    """Only the saved user-message text inside this history can prove delivery."""
    history = _single_tag(tree, HISTORY)
    display = _display(tree)
    if history is None or display is None:
        return None
    messages = [node for node in _tagged_nodes(history, USER_MESSAGE) if node.get("text") == "UIprobe"]
    if len(messages) > 1:
        raise AssertionError("Ambiguous recovered user message")
    if not messages:
        return None
    target = messages[0]
    parents = {child: parent for parent in tree.iter() for child in parent}
    bounds = _bounds(target)
    if _intersection(bounds, display[0]) != bounds or _intersection(bounds, _bounds(history)) != bounds:
        return None
    for ancestor in _ancestry(target, parents):
        if not _visible_app_node(ancestor):
            return None
        if ancestor.get("scrollable") == "true" and _intersection(bounds, _bounds(ancestor)) != bounds:
            return None
    return target


def reveal_persisted_user_message(probe):
    from profile_scroll import _reveal_target

    target = _reveal_target(
        probe.tree, probe._semantic_scroll_callback(HISTORY, "start"), persisted_user_message,
        "the recovered user message in chat history", resource_id=HISTORY,
        max_swipes=10, direction="start", layout_timeout=12,
    )
    if target is None:
        raise AssertionError("The recovered chat history is not visible")
    return target


def chat_counters(parts, requests, scenario):
    counts = {}
    for key in ("message-posts", "by-request-gets"):
        raw = parts.get(key, "")
        if re.fullmatch(r"\d+", raw) is None:
            raise AssertionError("Missing observed chat request counter: " + key)
        counts[key] = int(raw)
    if sum(counts.values()) > requests:
        raise AssertionError("Chat counters exceed all observed transport requests")
    message_id, recovered_id = parts.get("message-request-id"), parts.get("recovered-request-id")
    if counts["message-posts"] == 0:
        valid_message = message_id == "none"
    else:
        valid_message = isinstance(message_id, str) and UUID.fullmatch(message_id) is not None
    valid_recovered = _valid_recovered_id(recovered_id, scenario)
    if not valid_message or not valid_recovered or counts["by-request-gets"] == 0 and recovered_id != "none":
        raise AssertionError("Observed chat identifiers do not match their actual request counters")
    return {"message_posts": counts["message-posts"], "message_request_id": None if message_id == "none" else message_id,
            "by_request_gets": counts["by-request-gets"], "recovered_request_id": None if recovered_id == "none" else recovered_id}


def native_send_button(tree, *, enabled):
    """The native action owner's state controls repeat input."""
    from profile_ui_probe import button_label, node_bounds
    node = button_label(tree, SEND)
    if node is None or node.get("visible-to-user") != "true" \
            or node.get("enabled") != str(enabled).lower():
        return None
    if not any(SEND in [part.strip() for part in child.get("text", "").splitlines() + child.get("content-desc", "").splitlines()]
               for child in node.iter("node") if child.get("visible-to-user") == "true"):
        return None
    node_bounds(node)
    return node


def accepted_single_request(value):
    if value["message_posts"] == 0:
        return None
    if value["message_posts"] != 1 or value["by_request_gets"] != 0 or value["recovered_request_id"] is not None:
        raise AssertionError("The lost response repeated a message or recovered before the explicit user action")
    request_id = value["message_request_id"]
    if not isinstance(request_id, str) or UUID.fullmatch(request_id) is None:
        raise AssertionError("The accepted message has no canonical request identifier")
    return value


def recovered_single_request(value, request_id):
    if value["message_posts"] != 1 or value["message_request_id"] != request_id:
        raise AssertionError("Recovery issued another message POST or replaced its identifier")
    if value["by_request_gets"] == 0 or value["recovered_request_id"] is None:
        return None
    if value["by_request_gets"] != 1 or value["recovered_request_id"] != request_id:
        raise AssertionError("Recovery did not read the one already accepted request")
    return value


def exercise_chat_recovery(probe, observed):
    before = observed()
    if before["message_posts"] or before["by_request_gets"]:
        raise AssertionError("The unsent draft triggered a request before the user sent it")
    probe.tap_visible(SEND)
    probe.wait_for(lambda: accepted_single_request(observed()), "The server did not accept the one synthetic message POST")
    # Wait until the failure has reached production UI. Observing disabled Send
    # only during the still-running POST would miss the original regression.
    probe.reveal(LOST_REPLY, "workspace-content")
    probe.wait_for(lambda: native_send_button(probe.tree(), enabled=False),
                   "The uncertain request did not disable its native Send button")
    accepted = accepted_single_request(observed())
    request_id = accepted["message_request_id"]
    # This control must appear without remounting the screen. It performs GET,
    # reading the encrypted checkpoint written by the production request path.
    probe.tap_resource("recover-request-" + request_id, "workspace-content")
    recovered = probe.wait_for(lambda: recovered_single_request(observed(), request_id),
                              "The explicit recovery did not retrieve the same accepted UUID")
    # GET counters change before local acknowledgement is saved/applied. The
    # composer is cleared and usable only after recovery and the confirmed job
    # finish; its former draft must never stand in for a saved history message.
    probe.wait_for(lambda: recovered_composer(probe.tree()),
                   "Recovered chat did not clear its draft and release the native editor")
    reveal_persisted_user_message(probe)
    if recovered_composer(probe.tree()) is None:
        raise AssertionError("Recovered chat lost its cleared usable editor")
    completed = recovered_single_request(observed(), request_id)
    if completed is None:
        raise AssertionError("The completed message lost its recovery identity")
    return {"before": before, "accepted": accepted, "recovered": recovered, "completed": completed,
            "send_disabled_while_uncertain": True, "screen_remounted": False,
            "saved_user_message_visible": True, "composer_cleared_and_enabled": True,
            "recovery_method": "GET", "new_message_posts": completed["message_posts"] - before["message_posts"]}


def _valid_recovered_id(identifier, scenario):
    if identifier == "none":
        return True
    if not isinstance(identifier, str):
        return False
    return UUID.fullmatch(identifier) is not None or (scenario == "job" and identifier == "synthetic-request")
