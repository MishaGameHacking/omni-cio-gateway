from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import re
import secrets
import sys
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from scripts import provision_v10_render_neon_preview as _base


NEON_API_BASE = _base.NEON_API_BASE
NEON_REGION = _base.NEON_REGION
RENDER_API_BASE = _base.RENDER_API_BASE
ProvisioningStopped = _base.ProvisioningStopped
NeonTarget = _base.NeonTarget
_NEON_ORG_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")
_ORG_SCOPE_423_RETRY_DELAYS_SECONDS = (1.0, 2.0)
Sleep = Callable[[float], None]


class OrgScopedNeonApi(_base.JsonApi):
    def __init__(
        self,
        token: str,
        organization_id: str,
        *,
        sleeper: Sleep = time.sleep,
    ) -> None:
        super().__init__(NEON_API_BASE, token, label="NEON")
        self.organization_id = _validate_neon_org_id(organization_id)
        self._sleeper = sleeper

    def _call_provider(
        self,
        method: str,
        path: str,
        *,
        body: object | None,
        expected: frozenset[int],
        timeout: float,
    ) -> Any:
        return super().request(
            method,
            path,
            body=body,
            expected=expected,
            timeout=timeout,
        )

    def _static_region_response(self, path: str) -> dict[str, object] | None:
        parsed = urlsplit(path)
        if parsed.path != "/regions":
            return None
        query = parse_qs(parsed.query)
        if query.get("org_id") != [self.organization_id]:
            raise ProvisioningStopped("NEON_REGION_ORGANIZATION_DRIFT")
        return {"regions": [{"region_id": NEON_REGION}]}

    @staticmethod
    def _attempt_count(method: str) -> int:
        if method == "GET":
            return len(_ORG_SCOPE_423_RETRY_DELAYS_SECONDS) + 1
        return 1

    @staticmethod
    def _raise_precise_auth_failure(exc: ProvisioningStopped) -> None:
        if exc.status == 401:
            raise ProvisioningStopped("NEON_API_KEY_INVALID", status=401) from None
        if exc.status == 403:
            raise ProvisioningStopped("NEON_API_KEY_INSUFFICIENT", status=403) from None

    @staticmethod
    def _should_retry_locked(
        method: str,
        exc: ProvisioningStopped,
        attempt: int,
        attempts: int,
    ) -> bool:
        return method == "GET" and exc.status == 423 and attempt + 1 < attempts

    def _request_provider_with_retry(
        self,
        method: str,
        path: str,
        *,
        body: object | None,
        expected: frozenset[int],
        timeout: float,
    ) -> Any:
        attempts = self._attempt_count(method)
        for attempt in range(attempts):
            try:
                return self._call_provider(
                    method,
                    path,
                    body=body,
                    expected=expected,
                    timeout=timeout,
                )
            except ProvisioningStopped as exc:
                self._raise_precise_auth_failure(exc)
                if not self._should_retry_locked(method, exc, attempt, attempts):
                    raise
                _base._emit(
                    f"NEON_API_HTTP_RETRY status=423 attempt={attempt + 2}/{attempts}"
                )
                self._sleeper(_ORG_SCOPE_423_RETRY_DELAYS_SECONDS[attempt])
        raise AssertionError("unreachable Neon org-scope request state")

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        safe_method = method.upper()
        safe_path = _base._safe_api_path(path, "NEON_API_PATH_INVALID")
        if safe_method == "GET":
            static_regions = self._static_region_response(safe_path)
            if static_regions is not None:
                return static_regions
        return self._request_provider_with_retry(
            safe_method,
            safe_path,
            body=body,
            expected=expected,
            timeout=timeout,
        )


def _validate_neon_org_id(value: str) -> str:
    if _NEON_ORG_ID_PATTERN.fullmatch(value) is None:
        raise ProvisioningStopped("NEON_ORG_ID_INVALID")
    return value


def _required_neon_org_id() -> str:
    value = os.environ.get("NEON_ORG_ID", "").strip()
    if not value:
        raise ProvisioningStopped("NEON_ORG_ID_REQUIRED")
    return _validate_neon_org_id(value)


def _neon_organization(api: OrgScopedNeonApi, organization_id: str) -> str:
    safe_org_id = _validate_neon_org_id(organization_id)
    payload = _base._json_object(
        api.request("GET", f"/organizations/{safe_org_id}"),
        "NEON_ORGANIZATION_RESPONSE_INVALID",
    )
    organization = _base._json_object(
        payload.get("organization", payload),
        "NEON_ORGANIZATION_RESPONSE_INVALID",
    )
    if organization.get("id") != safe_org_id:
        raise ProvisioningStopped("NEON_ORGANIZATION_ID_MISMATCH")
    plan = organization.get("plan")
    if not isinstance(plan, str) or plan.casefold() != "free":
        raise ProvisioningStopped("NEON_FREE_PLAN_REQUIRED")
    _base._emit("NEON_ORGANIZATION=FREE_VERIFIED")
    return safe_org_id


def _neon_target(api: OrgScopedNeonApi, organization_id: str) -> NeonTarget:
    return _base._neon_target(api, _validate_neon_org_id(organization_id))


def run(repo_root: Path, expected_sha: str) -> str:
    _base._exact_head(repo_root, expected_sha)
    render_key = _base._required_env("RENDER_API_KEY")
    neon_key = _base._required_env("NEON_API_KEY")
    organization_id = _required_neon_org_id()
    runtime_password = secrets.token_urlsafe(48)
    _base._mask(runtime_password)

    neon = OrgScopedNeonApi(neon_key, organization_id)
    render = _base.JsonApi(RENDER_API_BASE, render_key, label="RENDER")
    _neon_organization(neon, organization_id)
    target = _neon_target(neon, organization_id)
    runtime_uri = _base._bootstrap_database(repo_root, target, runtime_password)
    render_target = _base._render_target(render, runtime_uri, expected_sha)
    _base._external_probe(render_target.service_url, expected_sha)
    _base._write_output("preview_url", render_target.service_url)
    _base._write_output("render_service_id", render_target.service_id)
    _base._write_output("neon_project_id", target.project_id)
    _base._write_summary(
        [
            "### Omni-CIO V10 Phase 4 free preview",
            f"- exact release: `{expected_sha}`",
            "- Neon organization / free plan: PASS",
            "- Neon PostgreSQL 18 / Frankfurt: PASS",
            "- least-privilege runtime role / FORCE RLS: PASS",
            "- Render Free / Frankfurt: PASS",
            f"- public synthetic preview: {render_target.service_url}",
            "- real registration, broker credentials and private data: OFF",
            "- recurring authorized cost: 0",
        ]
    )
    return render_target.service_url


def main(argv: list[str] | None = None) -> int:
    args = _base._parse_args(sys.argv[1:] if argv is None else argv)
    try:
        url = run(Path(args.repo_root).resolve(), args.expected_sha.strip().lower())
    except ProvisioningStopped as exc:
        _base._emit(f"PHASE4_FREE_PREVIEW=STOPPED code={exc.code}")
        return 1
    _base._emit(f"PHASE4_FREE_PREVIEW=READY url={url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
