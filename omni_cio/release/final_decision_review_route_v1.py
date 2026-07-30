from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import RLock
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_handler_shadow import (
    FinalDecisionReviewHandlerErrorCode,
    FinalDecisionReviewHandlerHttpStatus,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputStatus,
    FinalDecisionReviewReadOnlyQueryV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.release.final_decision_review_handler_shadow_v1 import (
    evaluate_final_decision_review_handler_shadow,
)


FINAL_REVIEW_PATH = "/decision/final-review"
FINAL_REVIEW_OPERATION_ID = "getFinalDecisionReview"
FINAL_REVIEW_SECURITY_SCHEME = "ApiKeyAuth"
FINAL_REVIEW_REGISTRY_TTL_SECONDS = 15 * 60
FINAL_REVIEW_REGISTRY_MAX_ENTRIES = 64
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"


class FinalDecisionReviewRouteError(ValueError):
    """The production final-review route cannot be registered safely."""


class FinalDecisionReviewSourceLookupStatus(StrEnum):
    FOUND = "found"
    EMPTY = "empty"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class PublishedFinalDecisionReviewSourceV1:
    route_plan: FinalDecisionReviewRouteImplementationPlanV1
    input_binding: FinalDecisionReviewInputBindingV1
    published_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewSourceLookupV1:
    status: FinalDecisionReviewSourceLookupStatus
    source: PublishedFinalDecisionReviewSourceV1 | None
    active_source_count: int


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewRouteError(
            "FINAL_DECISION_REVIEW_ROUTE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _context_key(
    *,
    account: str,
    requested_option_id: str,
    final_option_id: str,
    intent_fingerprint: str,
    instrument_count: int,
    instrument_keys: tuple[str, ...],
) -> tuple[str, str, str, str, int, tuple[str, ...]]:
    return (
        account,
        requested_option_id,
        final_option_id,
        intent_fingerprint,
        instrument_count,
        instrument_keys,
    )


def _query_context_key(
    query: FinalDecisionReviewReadOnlyQueryV1,
) -> tuple[str, str, str, str, int, tuple[str, ...]]:
    return _context_key(
        account=query.account.masked_id,
        requested_option_id=query.requested_option_id,
        final_option_id=query.final_option_id,
        intent_fingerprint=query.intent_fingerprint,
        instrument_count=query.instrument_count,
        instrument_keys=query.instrument_keys,
    )


class FinalDecisionReviewSourceRegistryV1:
    """Bounded in-memory registry for already reviewed read-only responses.

    The registry has no HTTP publication method and stores no credentials. Producers
    inside the process may publish only a route plan and input binding that already
    passed the PR-56 through PR-59 contracts.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = FINAL_REVIEW_REGISTRY_TTL_SECONDS,
        max_entries: int = FINAL_REVIEW_REGISTRY_MAX_ENTRIES,
    ) -> None:
        if ttl_seconds < 1 or ttl_seconds > 60 * 60:
            raise FinalDecisionReviewRouteError(
                "FINAL_DECISION_REVIEW_REGISTRY_TTL_OUT_OF_RANGE"
            )
        if max_entries < 1 or max_entries > 1_000:
            raise FinalDecisionReviewRouteError(
                "FINAL_DECISION_REVIEW_REGISTRY_CAPACITY_OUT_OF_RANGE"
            )
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_entries = max_entries
        self._sources: OrderedDict[
            tuple[str, str, str, str, int, tuple[str, ...]],
            PublishedFinalDecisionReviewSourceV1,
        ] = OrderedDict()
        self._lock = RLock()

    def _prune(self, now: datetime) -> None:
        expired = [
            key for key, source in self._sources.items() if source.expires_at <= now
        ]
        for key in expired:
            self._sources.pop(key, None)

    def publish(
        self,
        route_plan: FinalDecisionReviewRouteImplementationPlanV1,
        input_binding: FinalDecisionReviewInputBindingV1,
        *,
        published_at: datetime | None = None,
    ) -> PublishedFinalDecisionReviewSourceV1:
        now = _aware_utc(published_at)
        source_binding = route_plan.readiness_dossier.input_binding
        plan_ready = (
            route_plan.status
            is FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
            and route_plan.ready_for_implementation_review
            and not route_plan.blockers
        )
        binding_valid = (
            input_binding.status is FinalDecisionReviewInputStatus.VALID
            and input_binding.input_valid
            and not input_binding.blockers
        )
        identity_valid = (
            input_binding.query == source_binding.query
            and input_binding.query_sha256 == source_binding.query_sha256
            and input_binding.response_sha256 == source_binding.response_sha256
            and input_binding.action_candidate_sha256
            == source_binding.action_candidate_sha256
        )
        if not plan_ready:
            raise FinalDecisionReviewRouteError(
                "FINAL_DECISION_REVIEW_ROUTE_PLAN_NOT_READY"
            )
        if not binding_valid:
            raise FinalDecisionReviewRouteError(
                "FINAL_DECISION_REVIEW_INPUT_BINDING_NOT_VALID"
            )
        if not identity_valid:
            raise FinalDecisionReviewRouteError(
                "FINAL_DECISION_REVIEW_SOURCE_IDENTITY_MISMATCH"
            )

        source = PublishedFinalDecisionReviewSourceV1(
            route_plan=route_plan,
            input_binding=input_binding,
            published_at=now,
            expires_at=now + self._ttl,
        )
        key = _query_context_key(input_binding.query)
        with self._lock:
            self._prune(now)
            self._sources[key] = source
            self._sources.move_to_end(key)
            while len(self._sources) > self._max_entries:
                self._sources.popitem(last=False)
        return source

    def lookup(
        self,
        *,
        account: str,
        requested_option_id: str,
        final_option_id: str,
        intent_fingerprint: str,
        instrument_count: int,
        instrument_keys: tuple[str, ...],
        requested_at: datetime | None = None,
    ) -> FinalDecisionReviewSourceLookupV1:
        now = _aware_utc(requested_at)
        key = _context_key(
            account=account,
            requested_option_id=requested_option_id,
            final_option_id=final_option_id,
            intent_fingerprint=intent_fingerprint,
            instrument_count=instrument_count,
            instrument_keys=instrument_keys,
        )
        with self._lock:
            self._prune(now)
            source = self._sources.get(key)
            active_count = len(self._sources)
            if source is not None:
                self._sources.move_to_end(key)
                return FinalDecisionReviewSourceLookupV1(
                    status=FinalDecisionReviewSourceLookupStatus.FOUND,
                    source=source,
                    active_source_count=active_count,
                )
            return FinalDecisionReviewSourceLookupV1(
                status=(
                    FinalDecisionReviewSourceLookupStatus.EMPTY
                    if active_count == 0
                    else FinalDecisionReviewSourceLookupStatus.CONFLICT
                ),
                source=None,
                active_source_count=active_count,
            )

    def clear(self) -> None:
        with self._lock:
            self._sources.clear()

    def active_source_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._sources)


def _error_response(
    *,
    status: FinalDecisionReviewHandlerHttpStatus,
    code: FinalDecisionReviewHandlerErrorCode,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=int(status),
        content={
            "error": {"code": code.value, "message": message},
            "trading_methods": False,
        },
    )


def _binding_for_query(
    source: FinalDecisionReviewInputBindingV1,
    query: FinalDecisionReviewReadOnlyQueryV1,
) -> FinalDecisionReviewInputBindingV1:
    if query == source.query:
        return source
    return source.model_copy(
        update={
            "query": query,
            "query_sha256": _canonical_sha256(query.model_dump(mode="json")),
        }
    )


def patch_final_decision_review_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Make the production operation match the reviewed PR-55 Action candidate."""

    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes[FINAL_REVIEW_SECURITY_SCHEME] = {
        "type": "http",
        "scheme": "bearer",
    }
    operation = (
        schema.get("paths", {}).get(FINAL_REVIEW_PATH, {}).get("get")
    )
    if not isinstance(operation, dict):
        raise FinalDecisionReviewRouteError(
            "FINAL_DECISION_REVIEW_OPENAPI_OPERATION_MISSING"
        )
    operation["security"] = [{FINAL_REVIEW_SECURITY_SCHEME: []}]
    return schema


def register_final_decision_review_gateway(
    *,
    app: FastAPI,
    base: Any,
    app_version: str,
    registry: FinalDecisionReviewSourceRegistryV1 | None = None,
) -> FinalDecisionReviewSourceRegistryV1:
    """Register exactly one private read-only production GET route."""

    existing = [
        route
        for route in app.routes
        if getattr(route, "operation_id", None) == FINAL_REVIEW_OPERATION_ID
    ]
    if existing:
        stored = getattr(app.state, "final_decision_review_registry", None)
        if isinstance(stored, FinalDecisionReviewSourceRegistryV1):
            return stored
        raise FinalDecisionReviewRouteError(
            "FINAL_DECISION_REVIEW_ROUTE_ALREADY_REGISTERED_WITHOUT_REGISTRY"
        )

    source_registry = registry or FinalDecisionReviewSourceRegistryV1()
    app.state.final_decision_review_registry = source_registry
    app.state.final_decision_review_route_version = "1.0"
    app.state.final_decision_review_trading_methods = False

    @app.get(
        FINAL_REVIEW_PATH,
        operation_id=FINAL_REVIEW_OPERATION_ID,
        summary="Get the final read-only decision review",
        response_model=FinalDecisionReviewResponseV1,
        dependencies=[Depends(base.require_gateway_key)],
        responses={
            400: {"description": "Invalid canonical request"},
            401: {"description": "Private authentication required"},
            409: {"description": "Reviewed source identity conflict"},
            422: {"description": "Query schema validation failed"},
            503: {"description": "Reviewed source unavailable"},
        },
    )
    def get_final_decision_review(
        account: Annotated[str, Query(min_length=4, max_length=64)],
        requested_option_id: Annotated[str, Query(min_length=3, max_length=256)],
        final_option_id: Annotated[str, Query(min_length=3, max_length=256)],
        intent_fingerprint: Annotated[str, Query(pattern=_DIGEST_PATTERN)],
        instrument_count: Annotated[int, Query(ge=1, le=1_000)],
        instrument_keys: Annotated[list[str], Query(min_length=1)],
        response_sha256: Annotated[str, Query(pattern=_DIGEST_PATTERN)],
        action_candidate_sha256: Annotated[str, Query(pattern=_DIGEST_PATTERN)],
        correlation_id: Annotated[
            str | None,
            Header(alias="X-Correlation-ID", min_length=8, max_length=128),
        ] = None,
        request_id: Annotated[
            str | None,
            Header(alias="X-Request-ID", min_length=8, max_length=128),
        ] = None,
    ) -> Any:
        handled_at = datetime.now(timezone.utc)
        correlation = correlation_id or f"corr:{uuid4().hex}"
        try:
            AccountReference(masked_id=account)
        except ValidationError:
            base.logger.warning(
                "final_review_route rejected code=%s correlation_id=%s account=%s",
                FinalDecisionReviewHandlerErrorCode.INVALID_REQUEST.value,
                correlation,
                account[:64],
            )
            return _error_response(
                status=FinalDecisionReviewHandlerHttpStatus.BAD_REQUEST,
                code=FinalDecisionReviewHandlerErrorCode.INVALID_REQUEST,
                message="Canonical query parameters are invalid",
            )

        lookup = source_registry.lookup(
            account=account,
            requested_option_id=requested_option_id,
            final_option_id=final_option_id,
            intent_fingerprint=intent_fingerprint,
            instrument_count=instrument_count,
            instrument_keys=tuple(instrument_keys),
            requested_at=handled_at,
        )
        if lookup.source is None:
            code = (
                FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
                if lookup.status is FinalDecisionReviewSourceLookupStatus.EMPTY
                else FinalDecisionReviewHandlerErrorCode.SOURCE_CONFLICT
            )
            status_code = (
                FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
                if code is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
                else FinalDecisionReviewHandlerHttpStatus.CONFLICT
            )
            base.logger.warning(
                "final_review_route rejected code=%s correlation_id=%s account=%s active_sources=%s",
                code.value,
                correlation,
                account,
                lookup.active_source_count,
            )
            return _error_response(
                status=status_code,
                code=code,
                message=(
                    "Reviewed route plan or response source is unavailable"
                    if code is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
                    else "Reviewed input identity does not reconcile"
                ),
            )

        source = lookup.source
        try:
            query = FinalDecisionReviewReadOnlyQueryV1(
                account=AccountReference(
                    masked_id=account,
                    account_type=source.input_binding.query.account.account_type,
                ),
                requested_option_id=requested_option_id,
                final_option_id=final_option_id,
                intent_fingerprint=intent_fingerprint,
                instrument_count=instrument_count,
                instrument_keys=tuple(instrument_keys),
                response_sha256=response_sha256,
                action_candidate_sha256=action_candidate_sha256,
            )
        except ValidationError:
            return _error_response(
                status=FinalDecisionReviewHandlerHttpStatus.BAD_REQUEST,
                code=FinalDecisionReviewHandlerErrorCode.INVALID_REQUEST,
                message="Canonical query parameters are invalid",
            )

        shadow = evaluate_final_decision_review_handler_shadow(
            source.route_plan,
            _binding_for_query(source.input_binding, query),
            authentication_confirmed=True,
            source_available=True,
            correlation_id=correlation,
            request_id=request_id,
            handled_at=handled_at,
        )
        base.logger.info(
            "final_review_route_event=%s",
            json.dumps(
                shadow.observability_event.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        if shadow.response is not None:
            return JSONResponse(
                status_code=int(FinalDecisionReviewHandlerHttpStatus.OK),
                content=shadow.response.model_dump(mode="json"),
            )
        assert shadow.error_code is not None
        assert shadow.error_message is not None
        return _error_response(
            status=shadow.http_status,
            code=shadow.error_code,
            message=shadow.error_message,
        )

    if "final_decision_review" not in base.CAPABILITIES:
        base.CAPABILITIES.append("final_decision_review")
    if app.version != app_version:
        app.version = app_version
    app.openapi_schema = None
    return source_registry
