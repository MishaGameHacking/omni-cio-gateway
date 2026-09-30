"""Offline support operations for OmniCIO accounts.

This module is intentionally not exposed through HTTP. It is designed for
authorized operator use on the managed server where DATABASE_URL is already
available.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .config import required
from .db import Database, UserRecord
from .security import SecurityValueError, format_public_id, parse_public_id


class SupportCommandError(RuntimeError):
    """Raised for invalid or impossible support operations."""


def validate_reason(value: str) -> str:
    reason = value.strip()
    if not 1 <= len(reason) <= 200:
        raise SupportCommandError("reason must contain between 1 and 200 characters")
    return reason


def serialize_user(user: UserRecord, *, changed: bool | None = None) -> str:
    payload: dict[str, object] = {
        "public_id": format_public_id(user.public_id),
        "status": user.status,
    }
    if changed is not None:
        payload["changed"] = changed
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def require_user(user: UserRecord | None) -> UserRecord:
    if user is None:
        raise SupportCommandError("profile ID was not found")
    return user


def run_command(database: Database, args: argparse.Namespace) -> str:
    public_id = parse_public_id(args.public_id)

    if args.command == "get":
        return serialize_user(
            require_user(database.support_user_by_public_id(public_id))
        )

    reason = validate_reason(args.reason)

    if args.command == "revoke-sessions":
        user = require_user(
            database.support_revoke_all_sessions(
                public_id=public_id,
                reason=reason,
            )
        )
        return serialize_user(user, changed=True)

    transitions = {
        "block": {
            "target_status": "blocked",
            "allowed_from": frozenset({"active"}),
            "event_type": "support_account_blocked",
            "revoke_sessions": True,
        },
        "unblock": {
            "target_status": "active",
            "allowed_from": frozenset({"blocked"}),
            "event_type": "support_account_unblocked",
            "revoke_sessions": False,
        },
        "mark-delete": {
            "target_status": "deletion_pending",
            "allowed_from": frozenset({"active", "blocked"}),
            "event_type": "support_deletion_requested",
            "revoke_sessions": True,
        },
    }
    transition = transitions[args.command]
    result = database.support_change_status(
        public_id=public_id,
        target_status=str(transition["target_status"]),
        allowed_from=transition["allowed_from"],
        event_type=str(transition["event_type"]),
        reason=reason,
        revoke_sessions=bool(transition["revoke_sessions"]),
    )
    if result is None:
        raise SupportCommandError("profile ID was not found")
    user, changed = result
    return serialize_user(user, changed=changed)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Authorized offline OmniCIO account support operations"
    )
    sub = root.add_subparsers(dest="command", required=True)

    get = sub.add_parser("get")
    get.add_argument("public_id")

    for name in ("block", "unblock", "revoke-sessions", "mark-delete"):
        command = sub.add_parser(name)
        command.add_argument("public_id")
        command.add_argument(
            "--reason",
            required=True,
            help="Short support case/reference; do not include secrets",
        )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    database = Database(required("DATABASE_URL"))
    database.open()
    try:
        print(run_command(database, args))
    except (SecurityValueError, SupportCommandError, PermissionError) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
