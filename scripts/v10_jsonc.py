from __future__ import annotations

import json
from typing import Any


def _copy_json_string(source: str, start: int, output: list[str]) -> int:
    output.append('"')
    index = start + 1
    escaped = False
    while index < len(source):
        character = source[index]
        output.append(character)
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            return index + 1
        index += 1
    raise ValueError("unterminated JSON string")


def _skip_line_comment(source: str, start: int) -> int:
    index = start + 2
    while index < len(source) and source[index] not in "\r\n":
        index += 1
    return index


def _skip_block_comment(source: str, start: int, output: list[str]) -> int:
    closing = source.find("*/", start + 2)
    if closing < 0:
        raise ValueError("unterminated JSONC block comment")
    segment = source[start : closing + 2]
    output.extend("\n" if character == "\n" else " " for character in segment)
    return closing + 2


def _strip_jsonc_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(source):
        if source[index] == '"':
            index = _copy_json_string(source, index, output)
        elif source.startswith("//", index):
            index = _skip_line_comment(source, index)
        elif source.startswith("/*", index):
            index = _skip_block_comment(source, index, output)
        else:
            output.append(source[index])
            index += 1
    return "".join(output)


def _next_non_whitespace(source: str, start: int) -> str | None:
    index = start
    while index < len(source):
        if not source[index].isspace():
            return source[index]
        index += 1
    return None


def _strip_trailing_commas(source: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character == '"':
            index = _copy_json_string(source, index, output)
            continue
        if character == "," and _next_non_whitespace(source, index + 1) in {"]", "}"}:
            index += 1
            continue
        output.append(character)
        index += 1
    return "".join(output)


def loads_jsonc(source: str) -> Any:
    return json.loads(_strip_trailing_commas(_strip_jsonc_comments(source)))
