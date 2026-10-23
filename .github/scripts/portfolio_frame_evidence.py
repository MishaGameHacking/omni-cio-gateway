"""Read bounded debug-only source transcripts from fresh native UI frames.

This parser never invokes a source or infers a successful interaction. The runner
must verify the production screen and exact new calls before writing evidence.
"""
from __future__ import annotations

import json
import re

from profile_launch import PACKAGE, PORTFOLIO_CASES


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError("Ambiguous portfolio transcript field")
        result[key] = value
    return result


def _visible_node(node, resource_id):
    if node.get("package") != PACKAGE or node.get("visible-to-user") == "false":
        return False
    if node.get("resource-id") not in {resource_id, PACKAGE + ":id/" + resource_id}:
        return False
    match = re.fullmatch(r"\[(\d{1,6}),(\d{1,6})\]\[(\d{1,6}),(\d{1,6})\]", node.get("bounds", ""))
    return match is not None and int(match[3]) > int(match[1]) and int(match[4]) > int(match[2])


def _request_record(row, sequence):
    if not isinstance(row, dict) or set(row) != {"sequence", "method", "path", "parameters", "status"}:
        raise AssertionError("Invalid portfolio source request record")
    if type(row["sequence"]) is not int or row["sequence"] != sequence:
        raise AssertionError("Truncated or ambiguous portfolio request sequence")
    path, parameters, status = row["path"], row["parameters"], row["status"]
    if row["method"] not in {"GET", "POST", "PATCH", "DELETE"} \
            or not isinstance(path, str) or not path.startswith("/") or len(path) > 512 \
            or type(status) is not int or not 100 <= status <= 599:
        raise AssertionError("Invalid portfolio request identity or status")
    _request_parameters(parameters)
    return row


def _transcript(raw, route, scenario, run_id):
    if len(raw) > 512_000:
        raise AssertionError("Portfolio transcript exceeds the bounded fixture")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, TypeError) as error:
        raise AssertionError("Malformed portfolio source transcript") from error
    if not isinstance(value, dict) or value.get("route") != route or value.get("scenario") != scenario:
        return None
    if value.get("initialized") is not True or value.get("run_id") != run_id:
        return None
    errors, calls = value.get("contract_errors"), value.get("calls")
    if type(errors) is not int or errors != 0:
        raise AssertionError("Production portfolio screen submitted an invalid source contract")
    if not isinstance(calls, list) or len(calls) > 64:
        raise AssertionError("Invalid portfolio source request list")
    if type(value.get("request_count")) is not int or value["request_count"] != len(calls):
        return None
    for index, row in enumerate(calls, 1):
        _request_record(row, index)
    _transcript_destination(value)
    return value


def portfolio_observation(tree, route, scenario, run_id):
    """Require visible exact-case markers and matching observed request counts."""
    if (route, scenario) not in PORTFOLIO_CASES:
        raise ValueError("Unsupported portfolio fixture case")
    if not isinstance(run_id, str) or re.fullmatch(r"[a-f0-9]{32}", run_id) is None:
        raise ValueError("Invalid portfolio fixture run identity")
    markers, transcripts = _observed_markers(tree, route, scenario, run_id)
    if not markers or not transcripts:
        return None
    if any(item != markers[0] for item in markers) or any(item != transcripts[0] for item in transcripts):
        return None  # Read a new frame; mixed recomposition versions are not evidence.
    marker, transcript = markers[0], transcripts[0]
    if marker.get("run") != run_id or marker.get("initialized") != "true" \
            or marker.get("page") != transcript["current_page"]:
        return None
    if not re.fullmatch(r"\d{1,4}", marker.get("requests", "")) or marker.get("contract-errors") != "0":
        raise AssertionError("Invalid observed portfolio transport counters")
    if int(marker["requests"]) != len(transcript["calls"]):
        return None
    # Dossier/quotes begin on the real portfolio before the user opens a panel;
    # a zero count is valid readiness, never proof of a completed source request.
    return {**transcript, "requests": len(transcript["calls"]), "page": marker.get("page", "")}


def has_call(observed, path, parameters, *, status=200, after=0):
    """Compare one complete successful request; matching a prefix is insufficient."""
    expected = ("GET", path, parameters, status)
    return any((row["method"], row["path"], row["parameters"], row["status"]) == expected
               for row in observed["calls"][after:])


def _request_parameters(parameters):
    if not isinstance(parameters, dict) or len(parameters) > 24:
        raise AssertionError("Invalid portfolio request parameters")
    for key, value in parameters.items():
        if not isinstance(key, str) or not key or len(key) > 80:
            raise AssertionError("Invalid portfolio request parameter name")
        if value is not None and not (isinstance(value, str) and len(value) <= 4096) \
                and not (type(value) is int and -1_000_000 <= value <= 1_000_000):
            raise AssertionError("Invalid portfolio request parameter value")


def _transcript_destination(value):
    sources = value.get("opened_sources")
    if not isinstance(sources, list) or len(sources) > 64 \
            or not all(isinstance(source, str) and 1 <= len(source) <= 4096 for source in sources):
        raise AssertionError("Invalid observed portfolio source links")
    if not isinstance(value.get("destination"), dict) or len(value["destination"]) > 24:
        raise AssertionError("Invalid observed portfolio destination")
    if not isinstance(value.get("current_page"), str) or len(value["current_page"]) > 256:
        raise AssertionError("Invalid observed portfolio page")


def _observed_markers(tree, route, scenario, run_id):
    markers, transcripts = [], []
    for node in tree.iter("node"):
        raw = node.get("content-desc", "")
        if _visible_node(node, "portfolio-probe"):
            parts = _unique_object(part.split(":", 1) for part in raw.split(";") if ":" in part)
            if parts.get("portfolio-probe") == route + "/" + scenario and parts.get("transport") == "synthetic":
                markers.append(parts)
        elif _visible_node(node, "portfolio-probe-transcript"):
            transcript = _transcript(raw, route, scenario, run_id)
            if transcript is not None:
                transcripts.append(transcript)
    return markers, transcripts
