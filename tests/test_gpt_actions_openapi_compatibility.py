from __future__ import annotations

import os

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

import app as gateway_module
from omni_cio.release.final_decision_review_route_v1 import (
    FINAL_REVIEW_PATH,
    FINAL_REVIEW_SECURITY_SCHEME,
)


HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)


def test_gpt_actions_openapi_uses_exactly_one_bearer_security_scheme() -> None:
    gateway_module.app.openapi_schema = None
    schema = gateway_module.app.openapi()

    security_schemes = schema["components"]["securitySchemes"]
    assert security_schemes == {
        FINAL_REVIEW_SECURITY_SCHEME: {
            "type": "http",
            "scheme": "bearer",
        }
    }

    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            security = operation.get("security")
            if security:
                assert security == [{FINAL_REVIEW_SECURITY_SCHEME: []}]


def test_gpt_actions_openapi_omits_unsupported_final_review_trace_headers() -> None:
    gateway_module.app.openapi_schema = None
    schema = gateway_module.app.openapi()
    operation = schema["paths"][FINAL_REVIEW_PATH]["get"]

    header_parameters = {
        parameter["name"]
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "header"
    }
    assert "X-Correlation-ID" not in header_parameters
    assert "X-Request-ID" not in header_parameters


def test_gpt_actions_openapi_preserves_exact_read_only_surface() -> None:
    gateway_module.app.openapi_schema = None
    schema = gateway_module.app.openapi()

    operations = [
        (method.lower(), operation["operationId"])
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method.lower() in HTTP_METHODS
        and isinstance(operation, dict)
        and "operationId" in operation
    ]

    assert len(operations) == 14
    assert all(method == "get" for method, _ in operations)
    assert len({operation_id for _, operation_id in operations}) == 14
