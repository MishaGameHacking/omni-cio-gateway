"""Observe one accepted chat request recovered through GET after a lost reply."""
from __future__ import annotations

import re

PACKAGE = "ru.omnicio.app.debug"
UUID = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
SEND = "Отправить"
LOST_REPLY = "СИНТЕТИЧЕСКАЯ потеря ответа после принятия запроса. Сверьте сохранённый идентификатор."


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
    """The native Button state, not an explanatory label, controls repeat input."""
    from profile_ui_probe import node_bounds
    for node in tree.iter("node"):
        if node.get("package") != PACKAGE or node.get("visible-to-user") != "true" \
                or node.get("class") != "android.widget.Button" or node.get("enabled") != str(enabled).lower():
            continue
        if not any(SEND in [part.strip() for part in child.get("text", "").splitlines() + child.get("content-desc", "").splitlines()]
                   for child in node.iter("node") if child.get("visible-to-user") == "true"):
            continue
        node_bounds(node)
        return node
    return None


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
    probe.reveal("UIprobe", "workspace-content")
    completed = recovered_single_request(observed(), request_id)
    if completed is None:
        raise AssertionError("The completed message lost its recovery identity")
    return {"before": before, "accepted": accepted, "recovered": recovered, "completed": completed,
            "send_disabled_while_uncertain": True, "screen_remounted": False,
            "recovery_method": "GET", "new_message_posts": completed["message_posts"] - before["message_posts"]}


def _valid_recovered_id(identifier, scenario):
    if identifier == "none":
        return True
    if not isinstance(identifier, str):
        return False
    return UUID.fullmatch(identifier) is not None or (scenario == "job" and identifier == "synthetic-request")
