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
MCP_ENDPOINT = "https://timeweb.cloud/api/v1/mcp"
CLOUD_API = "https://api.timeweb.cloud"
AGENT_API = "https://agent.timeweb.cloud"

if not TOKEN:
    raise SystemExit("TIMEWEB_CLOUD_TOKEN is missing")


AGENT_SPECS = (
    {
        "role": "fast",
        "name": "Analyst AI FAST v1",
        "description": "Дешёвая модель классификации и первичной фильтрации событий Analyst AI.",
        "model_name": "gemini/gemini-3.5-flash-lite",
        "money_limit": 10,
        "max_tokens": 900,
        "temperature": 0.1,
    },
    {
        "role": "standard",
        "name": "Analyst AI STANDARD v1",
        "description": "Основная модель утренних, вечерних и событийных обзоров Analyst AI.",
        "model_name": "deepseek/deepseek-v4-pro",
        "money_limit": 30,
        "max_tokens": 1400,
        "temperature": 0.1,
    },
    {
        "role": "premium",
        "name": "Analyst AI PREMIUM v1",
        "description": "Редкая сильная модель для критических и неоднозначных рисков Analyst AI.",
        "model_name": "openai/gpt-5.6-sol",
        "money_limit": 60,
        "max_tokens": 1800,
    },
)

SYSTEM_PROMPT = """Ты — закрытый серверный аналитический компонент Analyst AI, а не пользовательский чат.
Получай только структурированные факты, заранее проверенные сервером. Не придумывай котировки,
новости, причины движения цены, финансовые показатели или свойства активов. Не обещай доходность,
не отдавай торговые поручения и не проси пользователя сообщить секреты. При недостатке данных явно
указывай неопределённость. Возвращай только один JSON-объект без Markdown по схеме, которую сервер
передаёт в текущем запросе. Все доказательства должны ссылаться только на source_id из входного JSON.
"""


def decode_payload(raw: bytes, content_type: str) -> Any:
    text = raw.decode("utf-8", errors="replace").strip()
    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        candidates: list[Any] = []
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            candidate = line[5:].strip()
            if candidate and candidate != "[DONE]":
                candidates.append(json.loads(candidate))
        if not candidates:
            raise RuntimeError("MCP response contained no JSON data event")
        return candidates[-1]
    return json.loads(text) if text else None


def mcp_post(payload: dict[str, Any], session_id: str | None = None) -> tuple[dict[str, str], Any]:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(
        MCP_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response_headers, decode_payload(
                response.read(),
                response_headers.get("content-type", ""),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MCP HTTP {exc.code}: {raw[:2000]}") from exc


def initialize() -> str | None:
    headers, payload = mcp_post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "analyst-ai-bootstrap", "version": "1.0"},
            },
        }
    )
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"MCP initialize failed: {payload['error']!r}")
    session_id = headers.get("mcp-session-id")
    mcp_post(
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
        session_id,
    )
    return session_id


def parse_tool_result(payload: Any, name: str) -> Any:
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name}: invalid MCP response: {payload!r}")
    if payload.get("error"):
        raise RuntimeError(f"{name}: {payload['error']!r}")
    result = payload.get("result")
    if not isinstance(result, dict):
        return result
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
        if result.get("isError"):
            raise RuntimeError(f"{name}: {' '.join(texts)}")
        return {"text": "\n".join(texts)}
    if result.get("isError"):
        raise RuntimeError(f"{name}: tool error: {result!r}")
    return result


def call_tool(
    session_id: str | None,
    request_id: int,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    _, payload = mcp_post(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        session_id,
    )
    return parse_tool_result(payload, name)


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def find_string(value: Any, key: str) -> str | None:
    for item in walk(value):
        candidate = item.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def extract_agents(payload: Any) -> list[dict[str, Any]]:
    for item in walk(payload):
        agents = item.get("agents")
        if isinstance(agents, list):
            return [agent for agent in agents if isinstance(agent, dict)]
    return []


def extract_models(payload: Any) -> list[dict[str, Any]]:
    for item in walk(payload):
        models = item.get("models")
        if isinstance(models, list):
            return [model for model in models if isinstance(model, dict)]
    return []


def create_agent(
    session_id: str | None,
    request_id: int,
    spec: dict[str, Any],
    model_id: int,
) -> Any:
    arguments: dict[str, Any] = {
        "name": spec["name"],
        "description": spec["description"],
        "access_type": "private",
        "model_id": model_id,
        "money_limit": spec["money_limit"],
        "system_prompt": SYSTEM_PROMPT,
        "max_tokens": spec["max_tokens"],
        "refine_query": False,
    }
    if "temperature" in spec:
        arguments["temperature"] = spec["temperature"]

    preview = call_tool(session_id, request_id, "create_ai_agent", arguments)
    confirm_token = find_string(preview, "confirm_token")
    if not confirm_token:
        raise RuntimeError(
            f"create_ai_agent did not return confirm_token for {spec['name']}: {preview!r}"
        )
    summary = find_string(preview, "operation_summary") or "confirmation received"
    print(f"AI_AGENT_CREATE_PREVIEW_{spec['role'].upper()}={json.dumps(summary, ensure_ascii=True)}")

    confirmed = dict(arguments)
    confirmed["confirm_token"] = confirm_token
    return call_tool(session_id, request_id + 1, "create_ai_agent", confirmed)


def request_json(
    url: str,
    *,
    payload: dict[str, Any],
    bearer: str | None,
) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else None
            except ValueError:
                body = {"text": raw[:1000]}
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = {"text": raw[:1000]}
        return exc.code, body
    except Exception as exc:
        return 0, {"error": type(exc).__name__}


def runtime_probe(agent: dict[str, Any], role: str) -> None:
    access_id = agent.get("access_id") or agent.get("accessId") or agent.get("id")
    if access_id is None:
        print(f"AI_AGENT_RUNTIME_{role.upper()}=missing_access_id")
        return

    message = 'Верни только JSON-объект {"ok":true,"role":"' + role + '"}.'
    chat_payload = {
        "model": "ignored",
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 80,
        "stream": False,
    }
    chat_url = f"{AGENT_API}/api/v1/cloud-ai/agents/{access_id}/v1/chat/completions"
    status, body = request_json(chat_url, payload=chat_payload, bearer=TOKEN)
    print(f"AI_AGENT_CHAT_CLOUD_TOKEN_{role.upper()}=http_{status}")
    if status == 200:
        print(
            f"AI_AGENT_CHAT_MODEL_{role.upper()}="
            + json.dumps(str(body.get("model") if isinstance(body, dict) else ""), ensure_ascii=True)
        )
        return

    native_url = f"{CLOUD_API}/api/v1/cloud-ai/agents/{access_id}/call"
    native_status, _ = request_json(
        native_url,
        payload={"message": message, "parent_message_id": ""},
        bearer=TOKEN,
    )
    print(f"AI_AGENT_NATIVE_CLOUD_TOKEN_{role.upper()}=http_{native_status}")


def main() -> None:
    session_id = initialize()
    models_payload = call_tool(
        session_id,
        10,
        "list_ai_models",
        {"include_deprecated": False, "include_params_info": False},
    )
    models = extract_models(models_payload)
    model_by_name: dict[str, int] = {}
    for model in models:
        name = model.get("model_name") or model.get("name")
        model_id = model.get("id") or model.get("model_id")
        if isinstance(name, str) and isinstance(model_id, int):
            model_by_name[name] = model_id

    missing_models = [
        spec["model_name"]
        for spec in AGENT_SPECS
        if spec["model_name"] not in model_by_name
    ]
    if missing_models:
        raise RuntimeError(f"Selected Timeweb models are unavailable: {missing_models}")

    agents_payload = call_tool(session_id, 20, "list_ai_agents", {})
    agents = extract_agents(agents_payload)
    agents_by_name = {
        str(agent.get("name")): agent
        for agent in agents
        if isinstance(agent.get("name"), str)
    }

    request_id = 100
    for spec in AGENT_SPECS:
        if spec["name"] in agents_by_name:
            print(f"AI_AGENT_{spec['role'].upper()}=reused")
            continue
        created = create_agent(
            session_id,
            request_id,
            spec,
            model_by_name[spec["model_name"]],
        )
        print(
            f"AI_AGENT_{spec['role'].upper()}_CREATE_RESULT="
            + json.dumps(created, ensure_ascii=True, separators=(",", ":"))
        )
        request_id += 10

    final_payload = call_tool(session_id, 500, "list_ai_agents", {})
    final_agents = extract_agents(final_payload)
    final_by_name = {
        str(agent.get("name")): agent
        for agent in final_agents
        if isinstance(agent.get("name"), str)
    }

    config: dict[str, Any] = {}
    for spec in AGENT_SPECS:
        agent = final_by_name.get(spec["name"])
        if agent is None:
            raise RuntimeError(f"Agent was not found after creation: {spec['name']}")
        role = spec["role"]
        config[role] = {
            "id": agent.get("id"),
            "access_id": agent.get("access_id") or agent.get("accessId"),
            "model_id": agent.get("model_id"),
            "model_name": spec["model_name"],
            "status": agent.get("status"),
            "money_limit_rub_per_day": spec["money_limit"],
        }
        runtime_probe(agent, role)

    print("ANALYST_AI_TIMEWEB_CONFIG=" + json.dumps(config, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
