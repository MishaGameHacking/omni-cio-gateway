"""Operational PLAN/APPLY/RECONCILE entry point for RU-PG-B IPv4 allocation.

The runner exposes only non-secret handles and fixed states. Provider IDs,
addresses, plan digests, journal paths and credential values stay inside the
protected runner. Existing-IP allocation is metadata-only and never certifies
firewall, TLS, PostgreSQL parity or production cutover.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import time
from typing import Any

from scripts import timeweb_ipv4_allocation as allocation
from scripts import timeweb_ipv4_allocation_provider as provider


_MODES = frozenset({"INITIALIZE", "PLAN", "APPLY", "RECONCILE"})
_SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
_HANDLE = re.compile(r"[0-9a-f]{32}", re.ASCII)
_COMMENT_ID = re.compile(r"[1-9]\d{0,19}", re.ASCII)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_RUNTIME_INPUT_REQUIRED")
    return value


def _expected_head() -> str:
    expected = _required_env("EXPECTED_HEAD")
    if (
        _SHA.fullmatch(expected) is None
        or os.environ.get("GITHUB_SHA", "").strip() != expected
        or os.environ.get("GITHUB_REF", "").strip() != "refs/heads/main"
        or os.environ.get("GITHUB_REPOSITORY", "").strip() != allocation.REPOSITORY
    ):
        raise allocation.AllocationStopped(
            "TIMEWEB_ALLOCATION_SOURCE_AUTHORITY_INVALID"
        )
    return expected


def _context(verifier: Any, expected_head: str) -> allocation.Context:
    context = verifier.current_context(expected_head)
    allocation._context(context)
    if context.source_sha != expected_head or context.current_main_sha != expected_head:
        raise allocation.AllocationStopped(
            "TIMEWEB_ALLOCATION_SOURCE_AUTHORITY_INVALID"
        )
    return context


def _open_journal(*, initialize: bool) -> Any:
    try:
        from scripts.timeweb_ipv4_allocation_windows import open_journal

        return open_journal(initialize=initialize)
    except Exception:
        raise allocation.AllocationStopped(
            "TIMEWEB_ALLOCATION_JOURNAL_UNAVAILABLE"
        ) from None


def _verifier(token: str) -> Any:
    try:
        from scripts.timeweb_ipv4_allocation_github import GitHubApprovalVerifier

        return GitHubApprovalVerifier(token)
    except Exception:
        raise allocation.AllocationStopped(
            "TIMEWEB_ALLOCATION_GITHUB_UNAVAILABLE"
        ) from None


def _approval_body(plan: allocation.Plan) -> str:
    try:
        from scripts.timeweb_ipv4_allocation_github import approval_body

        return approval_body(plan)
    except Exception:
        raise allocation.AllocationStopped(
            "TIMEWEB_ALLOCATION_APPROVAL_TEMPLATE_UNAVAILABLE"
        ) from None


def _clock() -> int:
    return int(time.time())


def _summary_path() -> Path | None:
    raw = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    return Path(raw) if raw else None


def _write_summary(lines: list[str]) -> None:
    path = _summary_path()
    if path is None:
        return
    safe = "\n".join(lines) + "\n"
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(safe)
    except OSError:
        # Summary rendering is not an authority or mutation boundary. Stdout
        # remains the canonical safe result channel.
        return


def _emit(line: str) -> None:
    print(line)


def _validate_handle(value: str) -> str:
    if _HANDLE.fullmatch(value) is None:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_PLAN_ID_INVALID")
    return value


def _validate_comment_id(value: str) -> str:
    if _COMMENT_ID.fullmatch(value) is None:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_APPROVAL_REQUIRED")
    return value


def _initialize() -> None:
    _expected_head()
    _open_journal(initialize=True)
    line = "TIMEWEB_IPV4_ALLOCATION_JOURNAL=READY state=PERSISTENT_PROTECTED"
    _emit(line)
    _write_summary(["### RU-PG-B IPv4 allocation journal", "`" + line + "`"])


def _plan() -> None:
    expected = _expected_head()
    github = _verifier(_required_env("GITHUB_TOKEN"))
    context = _context(github, expected)
    journal = _open_journal(initialize=False)
    timeweb = provider.live_provider(
        _required_env("TIMEWEB_CLOUD_API_TOKEN"), allow_write=False
    )
    identifier = allocation.prepare(
        timeweb.snapshot,
        journal,
        context,
        clock=_clock,
        read_context=lambda: github.current_context(expected),
    )
    entry = journal.read(identifier)
    if not isinstance(entry, allocation.Entry) or entry.plan.identifier != identifier:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_INVALID")
    summary = allocation.safe_summary(identifier, "OWNER_APPROVAL_REQUIRED")
    body = _approval_body(entry.plan)
    _emit(summary)
    _emit("TIMEWEB_IPV4_ALLOCATION_OWNER_COMMENT_BEGIN")
    _emit(body)
    _emit("TIMEWEB_IPV4_ALLOCATION_OWNER_COMMENT_END")
    _write_summary(
        [
            "### RU-PG-B existing IPv4 allocation plan",
            "`" + summary + "`",
            "",
            "No provider mutation occurred. To authorize this exact plan, the "
            "repository owner must post this exact unedited comment on issue #559:",
            "",
            "```text",
            body,
            "```",
            "",
            "The comment must be authored directly by the OWNER account, not by "
            "a GitHub App/connector.",
        ]
    )


def _apply(plan_id: str, approval_reference: str, confirmation: str) -> None:
    expected = _expected_head()
    identifier = _validate_handle(plan_id)
    reference = _validate_comment_id(approval_reference)
    if confirmation != allocation.ALLOCATE_CONFIRMATION:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_CONFIRMATION_REQUIRED")
    github = _verifier(_required_env("GITHUB_TOKEN"))
    context = _context(github, expected)
    journal = _open_journal(initialize=False)
    timeweb = provider.live_provider(
        _required_env("TIMEWEB_CLOUD_API_TOKEN"), allow_write=True
    )
    result = allocation.apply(
        identifier,
        reference,
        confirmation,
        timeweb.snapshot,
        timeweb.write_comment_once,
        journal,
        github,
        context,
        clock=_clock,
        sleeper=time.sleep,
        read_context=lambda: github.current_context(expected),
    )
    if result is not allocation.Outcome.ALLOCATED_VERIFIED:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_OUTCOME_INVALID")
    line = allocation.safe_summary(
        identifier, "ALLOCATION_VERIFIED_TRANSPORT_NOT_VERIFIED"
    )
    _emit(line)
    _write_summary(
        [
            "### RU-PG-B existing IPv4 allocation",
            "`" + line + "`",
            "",
            "The existing IPv4 management association is verified. Firewall/TLS "
            "transport is **not** verified by this workflow.",
        ]
    )


def _reconcile(plan_id: str) -> None:
    expected = _expected_head()
    identifier = _validate_handle(plan_id)
    github = _verifier(_required_env("GITHUB_TOKEN"))
    context = _context(github, expected)
    journal = _open_journal(initialize=False)
    timeweb = provider.live_provider(
        _required_env("TIMEWEB_CLOUD_API_TOKEN"), allow_write=False
    )
    result = allocation.reconcile(
        identifier,
        timeweb.snapshot,
        journal,
        context,
        sleeper=time.sleep,
    )
    if result not in {
        allocation.Outcome.RECEIPT_RECONCILED,
        allocation.Outcome.RECEIPT_REVERIFIED,
    }:
        raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_OUTCOME_INVALID")
    line = allocation.safe_summary(
        identifier, "ALLOCATION_VERIFIED_TRANSPORT_NOT_VERIFIED"
    )
    _emit(line)
    _write_summary(
        [
            "### RU-PG-B existing IPv4 reconciliation",
            "`" + line + "`",
            "",
            "GET-only reconciliation verified the management association. "
            "No provider write was attempted.",
        ]
    )


def _validate_mode_inputs(args: argparse.Namespace) -> None:
    confirmation = args.confirmation
    if args.mode in {"INITIALIZE", "PLAN"}:
        if args.plan_id or args.approval_reference or confirmation not in {"", "NONE"}:
            raise allocation.AllocationStopped(
                "TIMEWEB_ALLOCATION_DISPATCH_INPUT_INVALID"
            )
        return
    if args.mode == "RECONCILE":
        if args.approval_reference or confirmation not in {"", "NONE"}:
            raise allocation.AllocationStopped(
                "TIMEWEB_ALLOCATION_DISPATCH_INPUT_INVALID"
            )
        _validate_handle(args.plan_id)
        return
    if args.mode == "APPLY":
        _validate_handle(args.plan_id)
        _validate_comment_id(args.approval_reference)
        if confirmation != allocation.ALLOCATE_CONFIRMATION:
            raise allocation.AllocationStopped(
                "TIMEWEB_ALLOCATION_CONFIRMATION_REQUIRED"
            )
        return
    raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_MODE_INVALID")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--mode", required=True, choices=sorted(_MODES))
    parser.add_argument(
        "--plan-id",
        default=os.environ.get("TIMEWEB_ALLOCATION_PLAN_ID", ""),
    )
    parser.add_argument(
        "--approval-reference",
        default=os.environ.get("TIMEWEB_ALLOCATION_APPROVAL_REFERENCE", ""),
    )
    parser.add_argument(
        "--confirmation",
        default=os.environ.get("TIMEWEB_ALLOCATION_CONFIRMATION", ""),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _validate_mode_inputs(args)
        if args.mode == "INITIALIZE":
            _initialize()
        elif args.mode == "PLAN":
            _plan()
        elif args.mode == "APPLY":
            _apply(args.plan_id, args.approval_reference, args.confirmation)
        elif args.mode == "RECONCILE":
            _reconcile(args.plan_id)
        else:
            raise allocation.AllocationStopped("TIMEWEB_ALLOCATION_MODE_INVALID")
    except allocation.AllocationStopped as exc:
        _emit(f"TIMEWEB_IPV4_ALLOCATION=STOPPED code={exc}")
        return 1
    except provider.ProviderStopped as exc:
        _emit(f"TIMEWEB_IPV4_ALLOCATION=STOPPED code={exc}")
        return 1
    except Exception:
        _emit(
            "TIMEWEB_IPV4_ALLOCATION=STOPPED "
            "code=TIMEWEB_ALLOCATION_UNEXPECTED_FAILURE"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
