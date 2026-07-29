from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import ValidationError

from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.final_decision_review import FinalDecisionReviewResponseV1
from omni_cio.contracts.v1.final_decision_review_handler_shadow import (
    FinalDecisionReviewHandlerErrorCode,
    FinalDecisionReviewHandlerHttpStatus,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewReadOnlyQueryV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewRouteImplementationPlanV1,
)
from omni_cio.release.final_decision_review_handler_shadow_v1 import (
    evaluate_final_decision_review_handler_shadow,
)


TEST_APP_VERSION = "final-review-candidate-1.0"
TEST_APP_SERVER = "https://omni-cio-gateway.onrender.com"
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_API_KEY_HEADER = APIKeyHeader(
    name="X-Gateway-API-Key",
    scheme_name="ApiKeyAuth",
    auto_error=False,
)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _error_response(
    *,
    status: FinalDecisionReviewHandlerHttpStatus,
    code: FinalDecisionReviewHandlerErrorCode,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=int(status),
        content={
            "error": {
                "code": code.value,
                "message": message,
            },
            "trading_methods": False,
        },
    )


def _binding_for_query(
    source: FinalDecisionReviewInputBindingV1,
    query: FinalDecisionReviewReadOnlyQueryV1,
) -> FinalDecisionReviewInputBindingV1:
    query_sha = _canonical_sha256(query.model_dump(mode="json"))
    return source.model_copy(
        update={
            "query": query,
            "query_sha256": query_sha,
        }
    )


def build_isolated_final_decision_review_test_app(
    route_plan: FinalDecisionReviewRouteImplementationPlanV1,
    input_binding: FinalDecisionReviewInputBindingV1,
    *,
    authentication_validator: Callable[[str | None], bool],
    source_available: bool = True,
) -> FastAPI:
    """Build a test-only FastAPI app without importing or mutating production app."""

    app = FastAPI(
        title="Omni-CIO Final Review Isolated Candidate",
        version=TEST_APP_VERSION,
        servers=[{"url": TEST_APP_SERVER}],
    )
    app.state.isolated_candidate = True
    app.state.production_app_imported = False
    app.state.production_app_mutated = False
    app.state.trading_methods = False

    @app.get(
        "/decision/final-review",
        operation_id="getFinalDecisionReview",
        response_model=FinalDecisionReviewResponseV1,
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
        gateway_key: Annotated[str | None, Security(_API_KEY_HEADER)],
        correlation_id: Annotated[
            str | None,
            Header(alias="X-Correlation-ID", min_length=8, max_length=128),
        ] = None,
        request_id: Annotated[
            str | None,
            Header(alias="X-Request-ID", min_length=8, max_length=128),
        ] = None,
    ) -> Any:
        try:
            query = FinalDecisionReviewReadOnlyQueryV1(
                account=AccountReference(
                    masked_id=account,
                    account_type=input_binding.query.account.account_type,
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

        request_binding = _binding_for_query(input_binding, query)
        shadow = evaluate_final_decision_review_handler_shadow(
            route_plan,
            request_binding,
            authentication_confirmed=authentication_validator(gateway_key),
            source_available=source_available,
            correlation_id=correlation_id or f"corr:{uuid4().hex}",
            request_id=request_id,
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

    return app
