from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
from typing import Any, Callable

import httpx

from omni_cio.tbank_tls import TBankTlsCaUnavailable, build_tbank_ssl_context


REAL_REST_BASE_URL = "https://invest-public-api.tbank.ru/rest"
USERS_SERVICE = "tinkoff.public.invest.api.contract.v1.UsersService"
ORDERS_SERVICE = "tinkoff.public.invest.api.contract.v1.OrdersService"

_ALLOWED_METHODS: dict[str, str] = {
    "GetAccounts": USERS_SERVICE,
    "GetMaxLots": ORDERS_SERVICE,
    "GetOrderPrice": ORDERS_SERVICE,
    "PostOrder": ORDERS_SERVICE,
    "GetOrderState": ORDERS_SERVICE,
    "GetOrders": ORDERS_SERVICE,
}


@dataclass(frozen=True, slots=True)
class RealTradingApiFailure(Exception):
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
        return "TINVEST_REAL_HTTP_ERROR", _bounded_text(response.text)

    if not isinstance(payload, dict):
        return "TINVEST_REAL_HTTP_ERROR", _bounded_text(payload)

    code = _bounded_text(payload.get("code") or "TINVEST_REAL_HTTP_ERROR", 120)
    message = _bounded_text(
        payload.get("message")
        or payload.get("description")
        or payload.get("detail")
        or response.reason_phrase
    )
    return code, message


def _real_ssl_context() -> ssl.SSLContext:
    try:
        return build_tbank_ssl_context()
    except TBankTlsCaUnavailable as exc:
        raise RealTradingApiFailure(
            code="REAL_TRADING_TLS_CA_UNAVAILABLE",
            message=str(exc),
            http_status=503,
        ) from exc


class RealTradingRestClientV1:
    """Minimal allowlisted production REST client for the future trading token.

    The constructor accepts the dedicated trading token explicitly and never
    reads environment variables. In particular, it has no fallback to the
    existing production read-only token.
    """

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
            raise RealTradingApiFailure(
                code="REAL_TRADING_TOKEN_NOT_CONFIGURED",
                message="Dedicated real-trading token is not configured.",
                http_status=503,
            )
        self._token = token
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport
        self._client_factory = client_factory
        self._ssl_context = ssl_context or _real_ssl_context()

    @property
    def base_url(self) -> str:
        return REAL_REST_BASE_URL

    def _url(self, method: str) -> str:
        service = _ALLOWED_METHODS.get(method)
        if service is None:
            raise RealTradingApiFailure(
                code="REAL_TRADING_METHOD_NOT_ALLOWED",
                message=f"Method is outside the real-trading v1 allowlist: {method}",
                http_status=400,
            )
        return f"{REAL_REST_BASE_URL}/{service}/{method}"

    def post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._url(method)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "omni-cio-real-trading/1",
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
            ambiguous = method == "PostOrder"
            raise RealTradingApiFailure(
                code=(
                    "REAL_TRADING_TRANSPORT_AMBIGUOUS"
                    if ambiguous
                    else "REAL_TRADING_TRANSPORT_ERROR"
                ),
                message=type(exc).__name__,
                http_status=503,
                ambiguous_submission=ambiguous,
            ) from exc
        except httpx.HTTPError as exc:
            ambiguous = method == "PostOrder"
            raise RealTradingApiFailure(
                code=(
                    "REAL_TRADING_TRANSPORT_AMBIGUOUS"
                    if ambiguous
                    else "REAL_TRADING_TRANSPORT_ERROR"
                ),
                message=type(exc).__name__,
                http_status=502,
                ambiguous_submission=ambiguous,
            ) from exc

        tracking_id = response.headers.get("x-tracking-id")
        if response.status_code < 200 or response.status_code >= 300:
            code, message = _extract_error(response)
            ambiguous = method == "PostOrder" and response.status_code >= 500
            raise RealTradingApiFailure(
                code=code,
                message=message,
                http_status=response.status_code,
                ambiguous_submission=ambiguous,
                tracking_id=tracking_id,
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise RealTradingApiFailure(
                code="REAL_TRADING_RESPONSE_NOT_JSON",
                message="T-Invest real trading returned a non-JSON success response.",
                http_status=502,
                ambiguous_submission=(method == "PostOrder"),
                tracking_id=tracking_id,
            ) from exc

        if not isinstance(data, dict):
            raise RealTradingApiFailure(
                code="REAL_TRADING_RESPONSE_INVALID",
                message="T-Invest real trading response must be a JSON object.",
                http_status=502,
                ambiguous_submission=(method == "PostOrder"),
                tracking_id=tracking_id,
            )
        return data
