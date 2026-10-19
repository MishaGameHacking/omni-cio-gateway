"""Bound untrusted model JSON before decoding, independently of Python recursion.

These are application limits, not restrictions of the JSON specification. The
same UTF-8 byte and container-depth budgets apply to envelope and content text.
This module has no network, credentials, database or interpreter-setting effects.
"""
from __future__ import annotations

MAX_MODEL_JSON_BYTES = 512_000
MAX_MODEL_JSON_DEPTH = 64
_CLOSING = {"[": "]", "{": "}"}


class ModelJsonLimitError(ValueError):
    """A fixed, non-sensitive rejection code for an exceeded parser budget."""


def _utf8_text(value: str | bytes | bytearray) -> str:
    if not isinstance(value, (str, bytes, bytearray)):
        raise TypeError("JSON input must be text or bytes")
    # Bound allocation before decoding or encoding an already large input.
    if len(value) > MAX_MODEL_JSON_BYTES:
        raise ModelJsonLimitError("ai_response_too_large")
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_MODEL_JSON_BYTES:
            raise ModelJsonLimitError("ai_response_too_large")
        return value
    return value.decode("utf-8")


def _after_string(text: str, start: int) -> int:
    index = start + 1
    while index < len(text):
        character = text[index]
        if character == '"':
            return index + 1
        index += 2 if character == "\\" else 1
    raise ValueError("Unterminated JSON string")


def _check_containers(text: str) -> None:
    expected: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == '"':
            index = _after_string(text, index)
            continue
        if character in _CLOSING:
            expected.append(_CLOSING[character])
            if len(expected) > MAX_MODEL_JSON_DEPTH:
                raise ModelJsonLimitError("ai_json_nesting_exceeded")
        elif character in "]}":
            if not expected or expected.pop() != character:
                raise ValueError("Mismatched JSON container")
        index += 1
    if expected:
        raise ValueError("Unclosed JSON container")


def checked_model_json_text(value: str | bytes | bytearray) -> str:
    """Perform a bounded linear preflight; json.loads still checks JSON grammar."""
    text = _utf8_text(value)
    _check_containers(text)
    return text
