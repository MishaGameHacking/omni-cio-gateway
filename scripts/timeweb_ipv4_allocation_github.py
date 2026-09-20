"""Plan-bound OWNER evidence read from GitHub, never inferred from a chat actor.

Only an unedited owner-authored issue comment is accepted. App-authored comments,
including connector writes attributed to the owner, are rejected. This verifies
GitHub account authority, not physical presence, MFA, or historical IP creation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re
from typing import Any

from scripts import timeweb_ipv4_allocation as protocol


_PREFIX = "/repos/" + protocol.REPOSITORY
_ISSUE_URL = "https://api.github.com" + _PREFIX + "/issues/559"
_COMMENT_ID = re.compile(r"[1-9]\d{0,19}", re.ASCII)
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", re.ASCII)
ReadJson = Callable[[str], dict[str, Any]]


def approval_body(plan: protocol.Plan) -> str:
    protocol._plan(plan, plan.context)
    return (
        "APPROVE RU-PG-B EXISTING IPV4 ALLOCATION\n"
        f"plan={plan.identifier}\n"
        f"source={plan.context.source_sha}\n"
        f"expires={plan.expires_at}\n"
        "NO_CREATE NO_DELETE NO_NETWORK_ENABLE"
    )


def _timestamp(value: object) -> int:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise protocol.AllocationStopped("TIMEWEB_ALLOCATION_APPROVAL_TIME_INVALID")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return int(parsed.replace(tzinfo=timezone.utc).timestamp())


class GitHubApprovalVerifier:
    def __init__(self, token: str, *, read_json: ReadJson | None = None) -> None:
        if not isinstance(token, str) or not token:
            raise protocol.AllocationStopped("TIMEWEB_ALLOCATION_GITHUB_INPUT_REQUIRED")
        self._token = token
        self._reader = read_json or self._get

    def _get(self, path: str) -> dict[str, Any]:
        # Reuse accepted bounded GET/no-redirect/response-size transport.
        from scripts import verify_v10_timeweb_github_environment as environment

        return environment._request_json(path, self._token)

    def current_context(self, source_sha: str) -> protocol.Context:
        try:
            payload = self._reader(_PREFIX + "/git/ref/heads/main")
            if (
                payload.get("ref") != "refs/heads/main"
                or payload["object"]["type"] != "commit"
            ):
                raise ValueError("invalid ref")
            context = protocol.Context(source_sha, payload["object"]["sha"])
            protocol._context(context)
            return context
        except Exception:
            raise protocol.AllocationStopped(
                "TIMEWEB_ALLOCATION_MAIN_OBSERVATION_UNAVAILABLE"
            ) from None

    def verify(
        self,
        reference: str,
        plan: protocol.Plan,
        now: int,
    ) -> protocol.OwnerApproval:
        try:
            return self._verify(reference, plan, now)
        except Exception:
            raise protocol.AllocationStopped(
                "TIMEWEB_ALLOCATION_APPROVAL_UNPROVEN"
            ) from None

    def _verify(
        self,
        reference: str,
        plan: protocol.Plan,
        now: int,
    ) -> protocol.OwnerApproval:
        protocol._plan(plan, plan.context)
        protocol._fresh(plan, now)
        if not isinstance(reference, str) or _COMMENT_ID.fullmatch(reference) is None:
            raise ValueError("invalid reference")
        repository = self._reader(_PREFIX)
        owner = repository["owner"]
        if (
            repository.get("full_name") != protocol.REPOSITORY
            or repository.get("private") is not True
            or owner.get("type") != "User"
            or owner.get("login") != protocol.REPOSITORY.split("/")[0]
            or type(owner.get("id")) is not int
            or owner["id"] <= 0
        ):
            raise ValueError("repository identity mismatch")
        comment = self._reader(_PREFIX + "/issues/comments/" + reference)
        author = comment["user"]
        if (
            type(comment.get("id")) is not int
            or comment["id"] != int(reference)
            or comment.get("issue_url") != _ISSUE_URL
            or comment.get("author_association") != "OWNER"
            or author.get("type") != "User"
            or type(author.get("id")) is not int
            or author["id"] != owner["id"]
            or author.get("login") != owner["login"]
        ):
            raise ValueError("owner identity mismatch")
        if (
            "performed_via_github_app" not in comment
            or comment["performed_via_github_app"] is not None
            or comment.get("body") != approval_body(plan)
            or comment.get("updated_at") != comment.get("created_at")
        ):
            raise ValueError("approval changed or delegated")
        approved_at = _timestamp(comment.get("created_at"))
        if not plan.issued_at <= approved_at <= now < plan.expires_at:
            raise ValueError("approval expired or premature")
        self.current_context(plan.context.source_sha)
        return protocol.OwnerApproval(
            reference,
            plan.identifier,
            plan.digest,
            plan.context.source_sha,
            approved_at,
            plan.expires_at,
        )
