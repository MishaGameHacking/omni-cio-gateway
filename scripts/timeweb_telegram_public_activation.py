from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


CANONICAL_ORIGIN = "https://omnicio.ru"
CANONICAL_CALLBACK = "https://omnicio.ru/api/v10/web/auth/telegram/callback"
READY_CONFIRMATION = "READY_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION"
ACCEPT_CONFIRMATION = "ACCEPT_TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION"
MAX_RESPONSE_BYTES = 1024 * 1024
_JSON_CONTENT_TYPE = "application/json"
_SHA_LENGTH = 40
_DIGEST_LENGTH = 64
_PREACTIVATION_REASON = "PUBLIC_MULTI_USER_DISABLED"
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_PUBLIC_PROBE_RETRY_DELAYS = (1.0, 2.0, 5.0, 10.0, 20.0)


class TelegramActivationStopped(RuntimeError):
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


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


def _stop(code: str) -> NoReturn:
    raise TelegramActivationStopped(code)


def _hex(value: str, *, length: int, code: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != length or not normalized.isascii():
        _stop(code)
    if any(character not in "0123456789abcdef" for character in normalized):
        _stop(code)
    return normalized


def _sha(value: str, code: str) -> str:
    return _hex(value, length=_SHA_LENGTH, code=code)


def _digest(value: str, code: str) -> str:
    return _hex(value, length=_DIGEST_LENGTH, code=code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _stop(code)
    return value


def _headers(response: Any) -> dict[str, str]:
    try:
        return {
            str(name).casefold(): str(value).strip()
            for name, value in response.headers.items()
        }
    except AttributeError:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_HEADERS_INVALID")


def _read_json_attempt(
    active: Any,
    request: Request,
) -> tuple[dict[str, str] | None, bytes | None, str | None]:
    try:
        with active.open(request, timeout=30.0) as response:
            status = int(response.status)
            if status in _TRANSIENT_HTTP_STATUSES:
                return None, None, "TIMEWEB_TELEGRAM_ACTIVATION_HTTP_STATUS_INVALID"
            if status != 200:
                _stop("TIMEWEB_TELEGRAM_ACTIVATION_HTTP_STATUS_INVALID")
            return _headers(response), response.read(MAX_RESPONSE_BYTES + 1), None
    except HTTPError as exc:
        status = int(exc.code)
        if status in _TRANSIENT_HTTP_STATUSES:
            return None, None, f"TIMEWEB_TELEGRAM_ACTIVATION_HTTP_ERROR:{status}"
        _stop(f"TIMEWEB_TELEGRAM_ACTIVATION_HTTP_ERROR:{status}")
    except OSError:
        return None, None, "TIMEWEB_TELEGRAM_ACTIVATION_TRANSPORT_FAILED"


def _read_json(path: str, *, opener: Any | None = None) -> object:
    if not path.startswith("/") or ".." in path or "\\" in path:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_PATH_INVALID")
    request = Request(
        CANONICAL_ORIGIN + path,
        headers={
            "Accept": _JSON_CONTENT_TYPE,
            "User-Agent": "omni-cio-v10-timeweb-telegram-activation",
        },
        method="GET",
    )
    active = opener or _NO_REDIRECT_OPENER
    headers: dict[str, str] | None = None
    raw: bytes | None = None
    for attempt in range(len(_PUBLIC_PROBE_RETRY_DELAYS) + 1):
        headers, raw, failure = _read_json_attempt(active, request)
        if failure is None:
            break
        if attempt >= len(_PUBLIC_PROBE_RETRY_DELAYS):
            _stop(failure)
        time.sleep(_PUBLIC_PROBE_RETRY_DELAYS[attempt])
    if headers is None or raw is None:
        raise AssertionError("bounded public probe exhausted")
    if len(raw) > MAX_RESPONSE_BYTES:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_RESPONSE_TOO_LARGE")
    content_type = headers.get("content-type", "").partition(";")[0].strip().casefold()
    if content_type != _JSON_CONTENT_TYPE:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_CONTENT_TYPE_INVALID")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_JSON_INVALID")


def _probe_release(expected_sha: str, *, opener: Any | None = None) -> None:
    live = _mapping(
        _read_json("/livez", opener=opener),
        "TIMEWEB_TELEGRAM_ACTIVATION_LIVEZ_INVALID",
    )
    if live.get("status") != "ok":
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_LIVEZ_INVALID")
    live_sha = _sha(
        str(live.get("release_sha", "")),
        "TIMEWEB_TELEGRAM_ACTIVATION_SHA_INVALID",
    )
    if live_sha != expected_sha:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_RELEASE_SHA_DRIFT")

    health = _mapping(
        _read_json("/healthz", opener=opener),
        "TIMEWEB_TELEGRAM_ACTIVATION_HEALTHZ_INVALID",
    )
    if (
        health.get("status") != "ok"
        or health.get("database") != "READY"
        or health.get("synthetic_preview") is not False
    ):
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_HEALTHZ_INVALID")
    health_sha = _sha(
        str(health.get("release_sha", "")),
        "TIMEWEB_TELEGRAM_ACTIVATION_SHA_INVALID",
    )
    if health_sha != expected_sha:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_RELEASE_SHA_DRIFT")


def _provider_state(*, opener: Any | None = None) -> str:
    payload = _read_json("/api/v10/web/auth/providers", opener=opener)
    if not isinstance(payload, list) or len(payload) != 1:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_PROVIDER_SURFACE_INVALID")
    row = _mapping(payload[0], "TIMEWEB_TELEGRAM_ACTIVATION_PROVIDER_SURFACE_INVALID")
    if row.get("provider") != "telegram" or not isinstance(row.get("enabled"), bool):
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_PROVIDER_SURFACE_INVALID")
    if row["enabled"]:
        if set(row) != {"provider", "enabled"}:
            _stop("TIMEWEB_TELEGRAM_ACTIVATION_PROVIDER_SURFACE_INVALID")
        return "TELEGRAM_LIVE"
    reason = row.get("reason")
    if reason == _PREACTIVATION_REASON:
        return "PREACTIVATION_READY"
    if reason == "NOT_CONFIGURED":
        return "CREDENTIALS_NOT_CONFIGURED"
    if reason == "PROVIDER_ACTIVATION_DISABLED":
        return "ACTIVATION_PAIR_INVALID"
    _stop("TIMEWEB_TELEGRAM_ACTIVATION_PROVIDER_STATE_INVALID")


def _require_runtime_state(
    expected_sha: str,
    *,
    expected_state: str,
    opener: Any | None = None,
) -> None:
    _probe_release(expected_sha, opener=opener)
    if _provider_state(opener=opener) != expected_state:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_STATE_MISMATCH")


def _prerequisite_evidence(
    *,
    p3_acceptance_evidence_sha256: str,
    p4_acceptance_evidence_sha256: str,
    external_readiness_evidence_sha256: str,
    rollback_release_sha: str,
    rollback_evidence_sha256: str,
) -> dict[str, str]:
    return {
        "p3_acceptance_evidence_sha256": _digest(
            p3_acceptance_evidence_sha256,
            "TIMEWEB_TELEGRAM_ACTIVATION_P3_EVIDENCE_INVALID",
        ),
        "p4_acceptance_evidence_sha256": _digest(
            p4_acceptance_evidence_sha256,
            "TIMEWEB_TELEGRAM_ACTIVATION_P4_EVIDENCE_INVALID",
        ),
        "external_readiness_evidence_sha256": _digest(
            external_readiness_evidence_sha256,
            "TIMEWEB_TELEGRAM_ACTIVATION_EXTERNAL_EVIDENCE_INVALID",
        ),
        "rollback_release_sha": _sha(
            rollback_release_sha,
            "TIMEWEB_TELEGRAM_ACTIVATION_ROLLBACK_SHA_INVALID",
        ),
        "rollback_evidence_sha256": _digest(
            rollback_evidence_sha256,
            "TIMEWEB_TELEGRAM_ACTIVATION_ROLLBACK_EVIDENCE_INVALID",
        ),
    }


def readiness_seal(expected_sha: str, evidence: dict[str, str]) -> str:
    payload = {
        "schema": "omni-cio.v10.timeweb-telegram-activation-readiness-seal.v1",
        "expected_sha": expected_sha,
        "canonical_origin": CANONICAL_ORIGIN,
        "canonical_callback": CANONICAL_CALLBACK,
        **evidence,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_distinct_rollback(expected_sha: str, evidence: dict[str, str]) -> None:
    if evidence["rollback_release_sha"] == expected_sha:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_ROLLBACK_SHA_COLLISION")


def run(
    *,
    operation: str,
    expected_sha: str,
    observed_main_sha: str,
    confirmation: str = "",
    p3_acceptance_evidence_sha256: str = "",
    p4_acceptance_evidence_sha256: str = "",
    external_readiness_evidence_sha256: str = "",
    rollback_release_sha: str = "",
    rollback_evidence_sha256: str = "",
    readiness_sha256: str = "",
    live_acceptance_evidence_sha256: str = "",
    opener: Any | None = None,
) -> None:
    expected = _sha(expected_sha, "TIMEWEB_TELEGRAM_ACTIVATION_SHA_INVALID")
    observed = _sha(
        observed_main_sha,
        "TIMEWEB_TELEGRAM_ACTIVATION_MAIN_SHA_INVALID",
    )
    if observed != expected:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_MAIN_SHA_DRIFT")

    evidence_values = (
        p3_acceptance_evidence_sha256,
        p4_acceptance_evidence_sha256,
        external_readiness_evidence_sha256,
        rollback_release_sha,
        rollback_evidence_sha256,
        readiness_sha256,
        live_acceptance_evidence_sha256,
    )
    if operation == "observe":
        if confirmation or any(evidence_values):
            _stop("TIMEWEB_TELEGRAM_ACTIVATION_UNEXPECTED_EVIDENCE")
        _probe_release(expected, opener=opener)
        state = _provider_state(opener=opener)
        print(
            f"TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION=OBSERVED sha={expected} state={state}"
        )
        return

    prerequisites = _prerequisite_evidence(
        p3_acceptance_evidence_sha256=p3_acceptance_evidence_sha256,
        p4_acceptance_evidence_sha256=p4_acceptance_evidence_sha256,
        external_readiness_evidence_sha256=external_readiness_evidence_sha256,
        rollback_release_sha=rollback_release_sha,
        rollback_evidence_sha256=rollback_evidence_sha256,
    )
    _assert_distinct_rollback(expected, prerequisites)
    seal = readiness_seal(expected, prerequisites)

    if operation == "ready":
        if confirmation != READY_CONFIRMATION:
            _stop("TIMEWEB_TELEGRAM_ACTIVATION_READY_CONFIRMATION_REQUIRED")
        if readiness_sha256 or live_acceptance_evidence_sha256:
            _stop("TIMEWEB_TELEGRAM_ACTIVATION_PREMATURE_LIVE_EVIDENCE")
        _require_runtime_state(
            expected,
            expected_state="PREACTIVATION_READY",
            opener=opener,
        )
        print(
            "TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION=READY_TO_ACTIVATE "
            f"sha={expected} readiness_sha256={seal} public_users=false"
        )
        return

    if operation != "accept":
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_OPERATION_INVALID")
    if confirmation != ACCEPT_CONFIRMATION:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_ACCEPT_CONFIRMATION_REQUIRED")
    supplied_seal = _digest(
        readiness_sha256,
        "TIMEWEB_TELEGRAM_ACTIVATION_READINESS_SEAL_INVALID",
    )
    if supplied_seal != seal:
        _stop("TIMEWEB_TELEGRAM_ACTIVATION_READINESS_SEAL_DRIFT")
    live_digest = _digest(
        live_acceptance_evidence_sha256,
        "TIMEWEB_TELEGRAM_ACTIVATION_LIVE_EVIDENCE_INVALID",
    )
    _require_runtime_state(
        expected,
        expected_state="TELEGRAM_LIVE",
        opener=opener,
    )
    print(
        "TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION=LIVE_OPERABLE "
        f"sha={expected} readiness_sha256={seal} "
        f"live_acceptance_evidence_sha256={live_digest}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--operation",
        choices=("observe", "ready", "accept"),
        required=True,
    )
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--p3-acceptance-evidence-sha256", default="")
    parser.add_argument("--p4-acceptance-evidence-sha256", default="")
    parser.add_argument("--external-readiness-evidence-sha256", default="")
    parser.add_argument("--rollback-release-sha", default="")
    parser.add_argument("--rollback-evidence-sha256", default="")
    parser.add_argument("--readiness-sha256", default="")
    parser.add_argument("--live-acceptance-evidence-sha256", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        run(
            operation=args.operation,
            expected_sha=args.expected_sha,
            observed_main_sha=args.observed_main_sha,
            confirmation=args.confirmation,
            p3_acceptance_evidence_sha256=args.p3_acceptance_evidence_sha256,
            p4_acceptance_evidence_sha256=args.p4_acceptance_evidence_sha256,
            external_readiness_evidence_sha256=args.external_readiness_evidence_sha256,
            rollback_release_sha=args.rollback_release_sha,
            rollback_evidence_sha256=args.rollback_evidence_sha256,
            readiness_sha256=args.readiness_sha256,
            live_acceptance_evidence_sha256=args.live_acceptance_evidence_sha256,
        )
    except TelegramActivationStopped as exc:
        print(f"TIMEWEB_TELEGRAM_PUBLIC_ACTIVATION=STOPPED code={exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
