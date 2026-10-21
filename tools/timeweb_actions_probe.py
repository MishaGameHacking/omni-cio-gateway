"""Read-only hosting discovery; never log upstream bodies or credential values."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

BASE_URL = "https://api.timeweb.cloud"
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 20
ENDPOINTS = {
    "projects": "/api/v1/projects",
    "servers": "/api/v1/servers?limit=100&offset=0",
    "buckets": "/api/v1/storages/buckets",
}
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "integrations/timeweb/projects.openapi.json"


class ProbeError(RuntimeError):
    """Only fixed, non-secret diagnostics may cross this boundary."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError("redirect_refused")


def validated_token(value: str) -> str:
    token = value.strip()
    if not token:
        raise ProbeError("timeweb_token_missing")
    if len(token) > 16384 or any(ord(ch) < 33 or ord(ch) > 126 for ch in token):
        raise ProbeError("timeweb_token_format_invalid")
    return token


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError("duplicate_json_key")
        result[key] = value
    return result


def reject_constant(value):
    raise ProbeError("nonfinite_json_value")


def decode_response(raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise ProbeError("response_too_large")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                            parse_constant=reject_constant)
    except (ValueError, RecursionError):
        raise ProbeError("invalid_json") from None
    if type(result) is not dict:
        raise ProbeError("invalid_response_shape")
    return result


def read_resource(token: str, resource: str) -> dict:
    if resource not in ENDPOINTS:
        raise ProbeError("unapproved_endpoint")
    token = validated_token(token)
    request = urllib.request.Request(BASE_URL + ENDPOINTS[resource], headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }, method="GET")
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ProbeError("unexpected_http_status")
            if response.headers.get("Content-Encoding", "identity").lower() not in ("identity", ""):
                raise ProbeError("encoded_response_refused")
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise ProbeError("timeweb_http_" + str(error.code)) from None
    except OSError:
        raise ProbeError("timeweb_transport_error") from None
    return decode_response(raw)


def summarize(resource: str, document: dict) -> dict:
    items = document.get(resource)
    if type(items) is not list or len(items) > 2000:
        raise ProbeError("invalid_resource_collection")
    ids = []
    for item in items:
        if type(item) is not dict or type(item.get("id")) is not int or item["id"] <= 0:
            raise ProbeError("invalid_resource_identity")
        ids.append(item["id"])
    if len(ids) != len(set(ids)):
        raise ProbeError("duplicate_resource_identity")
    meta = document.get("meta")
    total = meta.get("total") if type(meta) is dict else None
    if total is not None and (type(total) is not int or total < len(ids)):
        raise ProbeError("invalid_collection_total")
    return {"returned_count": len(ids), "ids": ids, "reported_total": total,
            "complete": total == len(ids) if total is not None else False}


def inventory(token: str) -> dict:
    token = validated_token(token)
    resources = {name: summarize(name, read_resource(token, name)) for name in ENDPOINTS}
    return {"kind": "timeweb_actions_hosting_preflight", "resources": resources,
            "scope": "Only token-visible resources; completeness requires matching meta.total.",
            "resource_changes": False, "public_schema_published": False,
            "ready_for_import": False}


def validate_schema(path: Path = SCHEMA_PATH) -> dict:
    schema = decode_response(path.read_bytes())
    if schema.get("openapi") != "3.1.0" or schema.get("servers") != [{"url": BASE_URL}]:
        raise ProbeError("schema_server_or_version_invalid")
    if set(schema.get("paths", {})) != {"/api/v1/projects"}:
        raise ProbeError("unexpected_schema_path")
    methods = schema["paths"]["/api/v1/projects"]
    if set(methods) != {"get"}:
        raise ProbeError("schema_must_be_read_only")
    operation = methods["get"]
    if operation.get("operationId") != "listTimewebProjects" or operation.get("x-openai-isConsequential") is not False:
        raise ProbeError("schema_operation_invalid")
    components = schema.get("components", {})
    if type(components.get("schemas")) is not dict or not components["schemas"]:
        raise ProbeError("schema_definitions_missing")
    if schema.get("security") != [{"TimewebBearer": []}]:
        raise ProbeError("schema_auth_missing")
    if components.get("securitySchemes", {}).get("TimewebBearer") != {
        "type": "http", "scheme": "bearer", "bearerFormat": "JWT",
    }:
        raise ProbeError("schema_auth_invalid")
    validate_references(schema, schema)
    return {"schema_validated": True, "operation_count": 1, "read_only": True}


def validate_references(value, root):
    if type(value) is dict:
        for key, child in value.items():
            if key == "$ref":
                if not isinstance(child, str) or not child.startswith("#/components/schemas/"):
                    raise ProbeError("schema_external_or_invalid_reference")
                if child[len("#/components/schemas/"):] not in root["components"]["schemas"]:
                    raise ProbeError("schema_reference_missing")
            else:
                validate_references(child, root)
    elif type(value) is list:
        for child in value:
            validate_references(child, root)


def main() -> int:
    try:
        print("TIMEWEB_ACTIONS_SCHEMA=" + json.dumps(validate_schema(), sort_keys=True), flush=True)
        report = inventory(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        print("TIMEWEB_ACTIONS_PREFLIGHT=" + json.dumps(report, sort_keys=True), flush=True)
    except ProbeError as error:
        print("TIMEWEB_ACTIONS_ERROR=" + str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
