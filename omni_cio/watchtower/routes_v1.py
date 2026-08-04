from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from threading import RLock
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request

from .engine_v1 import PortfolioWatchtowerV1, WatchtowerError
from .journal_v1 import WatchtowerJournalError
from .qstash_v1 import QStashSignatureError, QStashSignatureVerifierV1
from .runtime_v1 import (
    WatchtowerCallbackVerifierV1,
    WatchtowerEvidenceProviderRegistryV1,
    WatchtowerRuntimeError,
    WatchtowerScheduledRequestV1,
    WatchtowerScheduledRunnerV1,
)
from .upstash_journal_v1 import UpstashWatchtowerJournalV1


_RUN_PATH = "/internal/watchtower/run"
_CALLBACK_PATH = "/internal/watchtower/callback"
_FAILURE_CALLBACK_PATH = "/internal/watchtower/failure-callback"


class WatchtowerRouteConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WatchtowerRouteRegistrationV1:
    run_path: str = _RUN_PATH
    callback_path: str = _CALLBACK_PATH
    failure_callback_path: str = _FAILURE_CALLBACK_PATH
    include_in_schema: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


@dataclass(frozen=True)
class WatchtowerRouteSettingsV1:
    enabled: bool
    public_base_url: str
    schedule_id: str
    qstash_current_signing_key: str
    qstash_next_signing_key: str
    upstash_rest_url: str
    upstash_rest_token: str
    journal_secret: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> WatchtowerRouteSettingsV1:
        source = environment if environment is not None else os.environ
        enabled = source.get("WATCHTOWER_ENABLED", "false").strip().lower() == "true"
        base_url = source.get("WATCHTOWER_PUBLIC_BASE_URL", "").strip() or source.get(
            "RENDER_EXTERNAL_URL", ""
        ).strip()
        schedule_id = source.get(
            "WATCHTOWER_QSTASH_SCHEDULE_ID",
            "omni-cio-watchtower-primary-v1",
        ).strip()
        values = cls(
            enabled=enabled,
            public_base_url=base_url.rstrip("/"),
            schedule_id=schedule_id,
            qstash_current_signing_key=source.get(
                "QSTASH_CURRENT_SIGNING_KEY", ""
            ).strip(),
            qstash_next_signing_key=source.get("QSTASH_NEXT_SIGNING_KEY", "").strip(),
            upstash_rest_url=source.get("UPSTASH_REDIS_REST_URL", "").strip(),
            upstash_rest_token=source.get("UPSTASH_REDIS_REST_TOKEN", "").strip(),
            journal_secret=source.get("WATCHTOWER_JOURNAL_SECRET", "").strip(),
        )
        if not enabled:
            return values
        parsed = urlparse(values.public_base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}:
            raise WatchtowerRouteConfigurationError(
                "WATCHTOWER_PUBLIC_BASE_URL_MUST_BE_BARE_HTTPS_ORIGIN"
            )
        if not values.schedule_id.startswith("omni-cio-watchtower-"):
            raise WatchtowerRouteConfigurationError("WATCHTOWER_SCHEDULE_ID_INVALID")
        required = (
            values.qstash_current_signing_key,
            values.qstash_next_signing_key,
            values.upstash_rest_url,
            values.upstash_rest_token,
            values.journal_secret,
        )
        if not all(required):
            raise WatchtowerRouteConfigurationError("WATCHTOWER_REQUIRED_SECRET_MISSING")
        return values

    def url(self, path: str) -> str:
        return f"{self.public_base_url}{path}"


class _LazyWatchtowerRouteRuntimeV1:
    def __init__(
        self,
        *,
        provider_registry: WatchtowerEvidenceProviderRegistryV1,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._providers = provider_registry
        self._environment = environment
        self._lock = RLock()
        self._settings: WatchtowerRouteSettingsV1 | None = None
        self._runner: WatchtowerScheduledRunnerV1 | None = None
        self._callback: WatchtowerCallbackVerifierV1 | None = None

    def _build(
        self,
    ) -> tuple[
        WatchtowerRouteSettingsV1,
        WatchtowerScheduledRunnerV1,
        WatchtowerCallbackVerifierV1,
    ]:
        settings = WatchtowerRouteSettingsV1.from_environment(self._environment)
        if not settings.enabled:
            raise WatchtowerRouteConfigurationError("WATCHTOWER_DISABLED")
        with self._lock:
            if self._runner is not None and self._callback is not None:
                assert self._settings is not None
                return self._settings, self._runner, self._callback
            verifier = QStashSignatureVerifierV1(
                current_signing_key=settings.qstash_current_signing_key,
                next_signing_key=settings.qstash_next_signing_key,
            )
            journal = UpstashWatchtowerJournalV1(
                settings.upstash_rest_url,
                settings.upstash_rest_token,
                journal_secret=settings.journal_secret,
            )
            watchtower = PortfolioWatchtowerV1(journal=journal)
            runner = WatchtowerScheduledRunnerV1(
                verifier=verifier,
                watchtower=watchtower,
                provider_registry=self._providers,
                expected_schedule_id=settings.schedule_id,
            )
            callback = WatchtowerCallbackVerifierV1(verifier)
            self._settings = settings
            self._runner = runner
            self._callback = callback
            return settings, runner, callback

    def components(
        self,
    ) -> tuple[
        WatchtowerRouteSettingsV1,
        WatchtowerScheduledRunnerV1,
        WatchtowerCallbackVerifierV1,
    ]:
        return self._build()


def _header(request: Request, name: str) -> str:
    value = request.headers.get(name, "").strip()
    if not value:
        raise HTTPException(status_code=401, detail="WATCHTOWER_QSTASH_HEADER_MISSING")
    return value


def _retried(request: Request) -> int:
    raw = request.headers.get("Upstash-Retried", "0").strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="WATCHTOWER_RETRY_HEADER_INVALID") from exc


async def _raw_body(request: Request) -> str:
    body = await request.body()
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="WATCHTOWER_BODY_NOT_UTF8") from exc


def _runtime_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, QStashSignatureError):
        return HTTPException(status_code=401, detail="WATCHTOWER_QSTASH_SIGNATURE_INVALID")
    if isinstance(exc, WatchtowerRouteConfigurationError):
        status = 404 if str(exc) == "WATCHTOWER_DISABLED" else 503
        return HTTPException(status_code=status, detail=str(exc))
    if isinstance(exc, (WatchtowerRuntimeError, WatchtowerError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, WatchtowerJournalError):
        return HTTPException(status_code=503, detail="WATCHTOWER_DURABLE_STATE_UNAVAILABLE")
    return HTTPException(status_code=503, detail="WATCHTOWER_RUNTIME_UNAVAILABLE")


def register_watchtower_routes(
    app: FastAPI,
    *,
    provider_registry: WatchtowerEvidenceProviderRegistryV1,
    environment: Mapping[str, str] | None = None,
) -> WatchtowerRouteRegistrationV1:
    runtime = _LazyWatchtowerRouteRuntimeV1(
        provider_registry=provider_registry,
        environment=environment,
    )

    @app.post(_RUN_PATH, include_in_schema=False)
    async def watchtower_run(request: Request) -> dict[str, object]:
        try:
            settings, runner, _ = runtime.components()
            raw = await _raw_body(request)
            return runner.run(
                WatchtowerScheduledRequestV1(
                    raw_body=raw,
                    signature=_header(request, "Upstash-Signature"),
                    destination_url=settings.url(_RUN_PATH),
                    message_id=_header(request, "Upstash-Message-Id"),
                    schedule_id=_header(request, "Upstash-Schedule-Id"),
                    retried=_retried(request),
                )
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _runtime_failure(exc) from exc

    async def callback(request: Request, path: str) -> dict[str, object]:
        try:
            settings, _, verifier = runtime.components()
            raw = await _raw_body(request)
            return verifier.acknowledge(
                raw_body=raw,
                signature=_header(request, "Upstash-Signature"),
                destination_url=settings.url(path),
                message_id=_header(request, "Upstash-Message-Id"),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _runtime_failure(exc) from exc

    @app.post(_CALLBACK_PATH, include_in_schema=False)
    async def watchtower_callback(request: Request) -> dict[str, object]:
        return await callback(request, _CALLBACK_PATH)

    @app.post(_FAILURE_CALLBACK_PATH, include_in_schema=False)
    async def watchtower_failure_callback(request: Request) -> dict[str, object]:
        return await callback(request, _FAILURE_CALLBACK_PATH)

    return WatchtowerRouteRegistrationV1()
