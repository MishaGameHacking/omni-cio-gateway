from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

TOKEN = os.environ.get("TIMEWEB_CLOUD_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("TIMEWEB_CLOUD_TOKEN is missing")


def decode_payload(raw: bytes, content_type: str) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()
    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        for line in text.splitlines():
            if line.startswith("data:"):
                candidate = line[5:].strip()
                if candidate and candidate != "[DONE]":
                    return json.loads(candidate)
        raise RuntimeError("MCP response did not contain a JSON data event")
    return json.loads(text) if text else None


def request_json(
    url: str,
    *,
    method: str = "POST",
    payload: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> tuple[int, dict[str, str], Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            raw = response.read()
            content_type = response_headers.get("content-type", "")
            return response.status, response_headers, decode_payload(raw, content_type)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        try:
            parsed = decode_payload(raw, content_type)
        except Exception:
            parsed = {"body": raw.decode("utf-8", errors="replace")[:1000]}
        return exc.code, {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}, parsed


def probe_gateway_token() -> None:
    url = "https://api.timeweb.ai/v1/models"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            ids = []
            for item in payload.get("data", []) if isinstance(payload, dict) else []:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    ids.append(item["id"])
            print("AI_GATEWAY_CLOUD_TOKEN_STATUS=authorized")
            print("AI_GATEWAY_MODELS_SAMPLE=" + json.dumps(ids[:20], ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        print(f"AI_GATEWAY_CLOUD_TOKEN_STATUS=http_{exc.code}")
    except Exception as exc:
        print(f"AI_GATEWAY_CLOUD_TOKEN_STATUS=error:{type(exc).__name__}")


def mcp_tools(endpoint: str) -> list[dict[str, Any]]:
    last_error: str | None = None
    for protocol_version in ("2025-06-18", "2025-03-26", "2024-11-05"):
        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "analyst-ai-bootstrap", "version": "1.0"},
            },
        }
        status, headers, payload = request_json(endpoint, payload=initialize)
        if status not in (200, 201):
            last_error = f"initialize HTTP {status}: {payload!r}"
            continue
        if isinstance(payload, dict) and payload.get("error"):
            last_error = f"initialize error: {payload['error']!r}"
            continue
        session_id = headers.get("mcp-session-id")
        initialized = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        request_json(endpoint, payload=initialized, session_id=session_id)
        status, _, tools_payload = request_json(
            endpoint,
            payload={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            session_id=session_id,
        )
        if status not in (200, 201):
            last_error = f"tools/list HTTP {status}: {tools_payload!r}"
            continue
        if not isinstance(tools_payload, dict):
            last_error = f"tools/list invalid response: {tools_payload!r}"
            continue
        result = tools_payload.get("result")
        tools = result.get("tools") if isinstance(result, dict) else None
        if isinstance(tools, list):
            print(f"MCP_PROTOCOL_VERSION={protocol_version}")
            print(f"MCP_SESSION_MODE={'stateful' if session_id else 'stateless'}")
            return [tool for tool in tools if isinstance(tool, dict)]
        last_error = f"tools/list missing tools: {tools_payload!r}"
    raise RuntimeError(last_error or "MCP initialization failed")


def main() -> None:
    probe_gateway_token()
    errors = []
    tools: list[dict[str, Any]] | None = None
    endpoint_used = None
    for endpoint in (
        "https://timeweb.cloud/api/v1/mcp",
        "https://api.timeweb.cloud/api/v1/mcp/search",
    ):
        try:
            tools = mcp_tools(endpoint)
            endpoint_used = endpoint
            break
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
    if tools is None:
        print("MCP_PROBE_ERRORS=" + json.dumps(errors, ensure_ascii=False))
        raise SystemExit(2)

    keywords = (
        "ai", "agent", "gateway", "model", "token", "key", "llm",
        "ии", "агент", "модел", "токен", "ключ",
    )
    filtered = []
    all_names = []
    for tool in tools:
        name = str(tool.get("name") or "")
        description = str(tool.get("description") or "")
        all_names.append(name)
        haystack = f"{name} {description}".lower()
        if any(keyword in haystack for keyword in keywords):
            filtered.append(
                {
                    "name": name,
                    "description": description[:500],
                    "inputSchema": tool.get("inputSchema") or tool.get("input_schema"),
                }
            )

    print("MCP_ENDPOINT=" + str(endpoint_used))
    print("MCP_TOOL_COUNT=" + str(len(tools)))
    print("MCP_AI_TOOLS=" + json.dumps(filtered, ensure_ascii=False, separators=(",", ":")))
    if not filtered:
        print("MCP_TOOL_NAMES=" + json.dumps(all_names, ensure_ascii=False))


if __name__ == "__main__":
    main()
