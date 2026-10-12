from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

TOKEN = os.environ.get("TIMEWEB_CLOUD_TOKEN", "").strip()
ENDPOINT = "https://timeweb.cloud/api/v1/mcp"
if not TOKEN:
    raise SystemExit("TIMEWEB_CLOUD_TOKEN is missing")


def decode_payload(raw: bytes, content_type: str) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()
    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        candidates = []
        for line in text.splitlines():
            if line.startswith("data:"):
                candidate = line[5:].strip()
                if candidate and candidate != "[DONE]":
                    candidates.append(json.loads(candidate))
        if not candidates:
            raise RuntimeError("MCP response contained no JSON data event")
        return candidates[-1]
    return json.loads(text) if text else None


def post(payload: dict[str, Any], session_id: str | None = None) -> tuple[dict[str, str], Any]:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            return response_headers, decode_payload(
                response.read(),
                response_headers.get("content-type", ""),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(
            f"HTTP {exc.code}: {raw.decode('utf-8', errors='replace')[:2000]}"
        ) from exc


def initialize() -> str | None:
    headers, payload = post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "analyst-ai-inspector", "version": "1.0"},
            },
        }
    )
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"initialize failed: {payload['error']!r}")
    session_id = headers.get("mcp-session-id")
    post(
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
        session_id,
    )
    return session_id


def call_tool(session_id: str | None, request_id: int, name: str, arguments: dict[str, Any]) -> Any:
    _, payload = post(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        session_id,
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name}: invalid MCP response: {payload!r}")
    if payload.get("error"):
        raise RuntimeError(f"{name}: {payload['error']!r}")
    result = payload.get("result")
    if isinstance(result, dict):
        if result.get("isError"):
            content = result.get("content")
            message = None
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        message = item["text"]
                        break
            raise RuntimeError(f"{name}: {message or result!r}")
        structured = result.get("structuredContent") or result.get("structured_content")
        if structured is not None:
            return structured
        content = result.get("content")
        if isinstance(content, list):
            texts = [
                item.get("text")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            for text in texts:
                try:
                    return json.loads(text)
                except (TypeError, ValueError):
                    continue
            return {"text": "\n".join(texts)}
    return result


def safe_call(
    session_id: str | None,
    request_id: int,
    name: str,
    arguments: dict[str, Any],
) -> tuple[Any | None, str | None]:
    try:
        return call_tool(session_id, request_id, name, arguments), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def summarize_models(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    seen = set()
    for item in walk(payload):
        raw_id = item.get("id") or item.get("model_id")
        name = item.get("name") or item.get("model_name") or item.get("title")
        if not isinstance(raw_id, (int, str)) or not isinstance(name, str):
            continue
        key = (str(raw_id), name)
        if key in seen:
            continue
        seen.add(key)
        summary = {
            key_name: item.get(key_name)
            for key_name in (
                "id", "model_id", "name", "model_name", "title", "type",
                "provider", "provider_id", "description", "is_deprecated",
                "is_stopped", "context_length", "max_tokens", "price",
                "input_price", "output_price", "ingoing_price", "outgoing_price",
                "price_input", "price_output", "params_info",
            )
            if key_name in item
        }
        candidates.append(summary)
    return candidates


def main() -> None:
    session_id = initialize()
    llm_models, llm_error = safe_call(
        session_id,
        11,
        "list_ai_models",
        {"type": "llm", "include_deprecated": False, "include_params_info": True},
    )
    hosted_models, hosted_error = safe_call(
        session_id,
        12,
        "list_ai_models",
        {"type": "hosted-llm", "include_deprecated": False, "include_params_info": True},
    )
    agents, agents_error = safe_call(session_id, 13, "list_ai_agents", {})

    print("TIMEWEB_AI_AGENTS_ERROR=" + json.dumps(agents_error, ensure_ascii=True))
    if agents is not None:
        print("TIMEWEB_AI_AGENTS=" + json.dumps(agents, ensure_ascii=True, separators=(",", ":")))

    print("TIMEWEB_AI_LLM_MODELS_ERROR=" + json.dumps(llm_error, ensure_ascii=True))
    print("TIMEWEB_AI_HOSTED_MODELS_ERROR=" + json.dumps(hosted_error, ensure_ascii=True))
    models = summarize_models(llm_models) + summarize_models(hosted_models)
    print("TIMEWEB_AI_MODEL_COUNT=" + str(len(models)))
    print("TIMEWEB_AI_MODELS=" + json.dumps(models, ensure_ascii=True, separators=(",", ":")))

    if agents_error and llm_error and hosted_error:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
