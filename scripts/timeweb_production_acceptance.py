from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


CANONICAL_ORIGIN = "https://omnicio.ru"
CANONICAL_CALLBACK = "https://omnicio.ru/api/v10/web/auth/telegram/callback"
ACCEPT_CONFIRMATION = "ACCEPT_TIMEWEB_PRODUCTION_RELEASE"
MAX_RESPONSE_BYTES = 1024 * 1024
_JSON_CONTENT_TYPE = "application/json"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


class ProductionAcceptanceStopped(RuntimeError):
    pass


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects)


def _stop(code: str) -> NoReturn:
    raise ProductionAcceptanceStopped(code)


def _sha(value: str, code: str) -> str:
    normalized = value.strip().lower()
    if _SHA_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _digest(value: str, code: str) -> str:
    normalized = value.strip().lower()
    if _DIGEST_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _stop(code)
    return value


def _headers(response: object) -> dict[str, str]:
    try:
        return {
            str(key).casefold(): str(value) for key, value in response.headers.items()
        }
    except AttributeError:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_HEADERS_INVALID")


def _read_json(path: str, *, opener: Any | None = None) -> object:
    allowed_paths = {"/livez", "/healthz", "/api/v10/web/auth/providers"}
    if path not in allowed_paths:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_PATH_INVALID")
    request = Request(
        CANONICAL_ORIGIN + path,
        headers={
            "Accept": _JSON_CONTENT_TYPE,
            "User-Agent": "omni-cio-v10-timeweb-production-acceptance",
        },
        method="GET",
    )
    active = opener or _NO_REDIRECT_OPENER
    try:
        with active.open(request, timeout=30.0) as response:
            if int(response.status) != 200:
                _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_HTTP_STATUS_INVALID")
            headers = _headers(response)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        _stop(f"TIMEWEB_PRODUCTION_ACCEPTANCE_HTTP_ERROR:{int(exc.code)}")
    except OSError:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_TRANSPORT_FAILED")
    if len(raw) > MAX_RESPONSE_BYTES:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_RESPONSE_TOO_LARGE")
    content_type = headers.get("content-type", "").partition(";")[0].strip().casefold()
    if content_type != _JSON_CONTENT_TYPE:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_CONTENT_TYPE_INVALID")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_JSON_INVALID")


def _release_sha(payload: dict[str, Any]) -> str:
    return _sha(
        str(payload.get("release_sha", "")),
        "TIMEWEB_PRODUCTION_ACCEPTANCE_SHA_INVALID",
    )


def _probe_release(expected_sha: str, *, opener: Any | None = None) -> None:
    live = _mapping(
        _read_json("/livez", opener=opener),
        "TIMEWEB_PRODUCTION_ACCEPTANCE_LIVEZ_INVALID",
    )
    if live.get("status") != "ok":
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_LIVEZ_INVALID")
    if _release_sha(live) != expected_sha:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_RELEASE_SHA_DRIFT")

    health = _mapping(
        _read_json("/healthz", opener=opener),
        "TIMEWEB_PRODUCTION_ACCEPTANCE_HEALTHZ_INVALID",
    )
    if (
        health.get("status") != "ok"
        or health.get("database") != "READY"
        or health.get("synthetic_preview") is not False
    ):
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_HEALTHZ_INVALID")
    if _release_sha(health) != expected_sha:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_RELEASE_SHA_DRIFT")


def _probe_provider(*, opener: Any | None = None) -> None:
    payload = _read_json("/api/v10/web/auth/providers", opener=opener)
    if not isinstance(payload, list) or len(payload) != 1:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_PROVIDER_SURFACE_INVALID")
    row = _mapping(
        payload[0],
        "TIMEWEB_PRODUCTION_ACCEPTANCE_PROVIDER_SURFACE_INVALID",
    )
    if row != {"provider": "telegram", "enabled": True}:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_PROVIDER_SURFACE_INVALID")


def _validated_evidence(
    *,
    p2_candidate_evidence_sha256: str,
    p3_cutover_evidence_sha256: str,
    p4_ingress_evidence_sha256: str,
    p5_readiness_sha256: str,
    p5_live_evidence_sha256: str,
    rollback_release_sha: str,
    rollback_evidence_sha256: str,
) -> dict[str, str]:
    return {
        "p2_candidate_evidence_sha256": _digest(
            p2_candidate_evidence_sha256,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_P2_EVIDENCE_INVALID",
        ),
        "p3_cutover_evidence_sha256": _digest(
            p3_cutover_evidence_sha256,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_P3_EVIDENCE_INVALID",
        ),
        "p4_ingress_evidence_sha256": _digest(
            p4_ingress_evidence_sha256,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_P4_EVIDENCE_INVALID",
        ),
        "p5_readiness_sha256": _digest(
            p5_readiness_sha256,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_P5_READINESS_INVALID",
        ),
        "p5_live_evidence_sha256": _digest(
            p5_live_evidence_sha256,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_P5_LIVE_EVIDENCE_INVALID",
        ),
        "rollback_release_sha": _sha(
            rollback_release_sha,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_SHA_INVALID",
        ),
        "rollback_evidence_sha256": _digest(
            rollback_evidence_sha256,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_EVIDENCE_INVALID",
        ),
    }


def production_acceptance_seal(
    expected_sha: str,
    evidence: dict[str, str],
) -> str:
    payload = {
        "schema": "omni-cio.v10.timeweb-production-acceptance-seal.v1",
        "expected_sha": expected_sha,
        "canonical_origin": CANONICAL_ORIGIN,
        "canonical_callback": CANONICAL_CALLBACK,
        **evidence,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _probe_live_product(expected_sha: str, *, opener: Any | None = None) -> None:
    _probe_release(expected_sha, opener=opener)
    _probe_provider(opener=opener)


def run(
    *,
    operation: str,
    expected_sha: str,
    observed_main_sha: str,
    confirmation: str = "",
    p2_candidate_evidence_sha256: str = "",
    p3_cutover_evidence_sha256: str = "",
    p4_ingress_evidence_sha256: str = "",
    p5_readiness_sha256: str = "",
    p5_live_evidence_sha256: str = "",
    rollback_release_sha: str = "",
    rollback_evidence_sha256: str = "",
    opener: Any | None = None,
) -> str | None:
    expected = _sha(expected_sha, "TIMEWEB_PRODUCTION_ACCEPTANCE_SHA_INVALID")
    observed = _sha(
        observed_main_sha,
        "TIMEWEB_PRODUCTION_ACCEPTANCE_MAIN_SHA_INVALID",
    )
    if expected != observed:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_MAIN_SHA_DRIFT")

    evidence_values = (
        p2_candidate_evidence_sha256,
        p3_cutover_evidence_sha256,
        p4_ingress_evidence_sha256,
        p5_readiness_sha256,
        p5_live_evidence_sha256,
        rollback_release_sha,
        rollback_evidence_sha256,
    )
    if operation == "observe":
        if confirmation or any(evidence_values):
            _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_UNEXPECTED_EVIDENCE")
        _probe_live_product(expected, opener=opener)
        print(
            "TIMEWEB_PRODUCTION_ACCEPTANCE=OBSERVED "
            f"sha={expected} origin={CANONICAL_ORIGIN}"
        )
        return None

    if operation != "accept":
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_OPERATION_INVALID")
    if confirmation != ACCEPT_CONFIRMATION:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_CONFIRMATION_REQUIRED")

    evidence = _validated_evidence(
        p2_candidate_evidence_sha256=p2_candidate_evidence_sha256,
        p3_cutover_evidence_sha256=p3_cutover_evidence_sha256,
        p4_ingress_evidence_sha256=p4_ingress_evidence_sha256,
        p5_readiness_sha256=p5_readiness_sha256,
        p5_live_evidence_sha256=p5_live_evidence_sha256,
        rollback_release_sha=rollback_release_sha,
        rollback_evidence_sha256=rollback_evidence_sha256,
    )
    if evidence["rollback_release_sha"] == expected:
        _stop("TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_SHA_COLLISION")

    _probe_live_product(expected, opener=opener)
    seal = production_acceptance_seal(expected, evidence)
    print(
        "TIMEWEB_PRODUCTION_ACCEPTANCE=ACCEPTED "
        f"sha={expected} acceptance_seal_sha256={seal} "
        f"rollback_release_sha={evidence['rollback_release_sha']}"
    )
    return seal


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=("observe", "accept"), required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--p2-candidate-evidence-sha256", default="")
    parser.add_argument("--p3-cutover-evidence-sha256", default="")
    parser.add_argument("--p4-ingress-evidence-sha256", default="")
    parser.add_argument("--p5-readiness-sha256", default="")
    parser.add_argument("--p5-live-evidence-sha256", default="")
    parser.add_argument("--rollback-release-sha", default="")
    parser.add_argument("--rollback-evidence-sha256", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        run(
            operation=args.operation,
            expected_sha=args.expected_sha,
            observed_main_sha=args.observed_main_sha,
            confirmation=args.confirmation,
            p2_candidate_evidence_sha256=args.p2_candidate_evidence_sha256,
            p3_cutover_evidence_sha256=args.p3_cutover_evidence_sha256,
            p4_ingress_evidence_sha256=args.p4_ingress_evidence_sha256,
            p5_readiness_sha256=args.p5_readiness_sha256,
            p5_live_evidence_sha256=args.p5_live_evidence_sha256,
            rollback_release_sha=args.rollback_release_sha,
            rollback_evidence_sha256=args.rollback_evidence_sha256,
        )
    except ProductionAcceptanceStopped as exc:
        print(f"TIMEWEB_PRODUCTION_ACCEPTANCE=STOPPED code={exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
