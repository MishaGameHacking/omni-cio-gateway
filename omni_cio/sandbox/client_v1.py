from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
from typing import Any, Callable

import httpx

from omni_cio.tbank_tls import TBankTlsCaUnavailable, build_tbank_ssl_context


SANDBOX_REST_BASE_URL = "https://sandbox-invest-public-api.tbank.ru/rest"
SANDBOX_SERVICE = "tinkoff.public.invest.api.contract.v1.SandboxService"

_ALLOWED_METHODS = frozenset(
    {
        "OpenSandboxAccount",
        "GetSandboxAccounts",
        "SandboxPayIn",
        "GetSandboxPortfolio",
        "GetSandboxPositions",
        "GetSandboxMaxLots",
        "GetSandboxOrderPrice",
        "PostSandboxOrder",
        "GetSandboxOrderState",
        "CancelSandboxOrder",
    }
)


@dataclass(frozen=True, slots=True)
class SandboxApiFailure(Exception):
    code: str
    message: str
    http_status: int = 502
    ambiguous_submission: bool = False
    tracking_id: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _bounded_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]


def _extract_error(response: httpx.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return "TINVEST_SANDBOX_HTTP_ERROR", _bounded_text(response.text)

    if not isinstance(payload, dict):
        return "TINVEST_SANDBOX_HTTP_ERROR", _bounded_text(payload)

    code = _bounded_text(payload.get("code") or "TINVEST_SANDBOX_HTTP_ERROR", 120)
    message = _bounded_text(
        payload.get("message")
        or payload.get("description")
        or payload.get("detail")
        or response.reason_phrase
    )
    return code, message


def _sandbox_ssl_context() -> ssl.SSLContext:
    try:
        return build_tbank_ssl_context()
    except TBankTlsCaUnavailable as exc:
        raise SandboxApiFailure(
            code="SANDBOX_TLS_CA_UNAVAILABLE",
            message=str(exc),
            http_status=503,
        ) from exc


class SandboxRestClientV1:
    """Minimal client that cannot be redirected to the production T-Invest host."""

    def __init__(
        self,
        token: str,
        *,
        timeout_seconds: float = 12.0,
        transport: httpx.BaseTransport | None = None,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        token = token.strip()
        if not token:
            raise SandboxApiFailure(
                code="SANDBOX_TOKEN_NOT_CONFIGURED",
                message="TINVEST_SANDBOX_TOKEN is not configured.",
                http_status=503,
            )
        self._token = token
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport
        self._client_factory = client_factory
        self._ssl_context = ssl_context or _sandbox_ssl_context()

    @property
    def base_url(self) -> str:
        return SANDBOX_REST_BASE_URL

    def _url(self, method: str) -> str:
        if method not in _ALLOWED_METHODS:
            raise SandboxApiFailure(
                code="SANDBOX_METHOD_NOT_ALLOWED",
                message=f"Method is outside the sandbox allowlist: {method}",
                http_status=400,
            )
        return f"{SANDBOX_REST_BASE_URL}/{SANDBOX_SERVICE}/{method}"

    def post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._url(method)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "omni-cio-sandbox-trading/1",
        }
        kwargs: dict[str, Any] = {
            "timeout": self._timeout,
            "follow_redirects": False,
            "trust_env": False,
            "verify": self._ssl_context,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport

        try:
            with self._client_factory(**kwargs) as client:
                response = client.post(url, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            ambiguous = method == "PostSandboxOrder"
            raise SandboxApiFailure(
                code=(
                    "SANDBOX_TRANSPORT_AMBIGUOUS"
                    if ambiguous
                    else "SANDBOX_TRANSPORT_ERROR"
                ),
                message=type(exc).__name__,
                http_status=503,
                ambiguous_submission=ambiguous,
            ) from exc
        except httpx.HTTPError as exc:
            ambiguous = method == "PostSandboxOrder"
            raise SandboxApiFailure(
                code=(
                    "SANDBOX_TRANSPORT_AMBIGUOUS"
                    if ambiguous
                    else "SANDBOX_TRANSPORT_ERROR"
                ),
                message=type(exc).__name__,
                http_status=502,
                ambiguous_submission=ambiguous,
            ) from exc

        tracking_id = response.headers.get("x-tracking-id")
        if response.status_code < 200 or response.status_code >= 300:
            code, message = _extract_error(response)
            ambiguous = method == "PostSandboxOrder" and response.status_code >= 500
            raise SandboxApiFailure(
                code=code,
                message=message,
                http_status=response.status_code,
                ambiguous_submission=ambiguous,
                tracking_id=tracking_id,
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise SandboxApiFailure(
                code="SANDBOX_RESPONSE_NOT_JSON",
                message="T-Invest Sandbox returned a non-JSON success response.",
                http_status=502,
                ambiguous_submission=(method == "PostSandboxOrder"),
                tracking_id=tracking_id,
            ) from exc

        if not isinstance(data, dict):
            raise SandboxApiFailure(
                code="SANDBOX_RESPONSE_INVALID",
                message="T-Invest Sandbox response must be a JSON object.",
                http_status=502,
                ambiguous_submission=(method == "PostSandboxOrder"),
                tracking_id=tracking_id,
            )
        return data
