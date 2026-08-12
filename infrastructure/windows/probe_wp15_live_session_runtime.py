from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1


EXIT_CONNECTION = 71
EXIT_CREATE = 72
EXIT_RESOLVE = 73
EXIT_REVOKE = 74
EXIT_CLEANUP = 75


def _cleanup_probe_session(connection: Any, digest: str) -> bool:
    if not digest:
        return True
    try:
        with connection.transaction():
            connection.execute(
                "DELETE FROM omni_cio_v10.web_sessions WHERE token_sha256 = %s",
                (digest,),
            )
    except Exception:
        return False
    return True


def main() -> int:
    connection = None
    token = ""
    digest = ""
    result = EXIT_CONNECTION
    try:
        try:
            connection = connect_postgres("")
            connection.autocommit = True  # type: ignore[attr-defined]
            if getattr(connection, "autocommit", None) is not True:
                return EXIT_CONNECTION
        except Exception:
            return EXIT_CONNECTION

        registry = PostgresWebSessionRegistryV1(connection)
        now = datetime.now(timezone.utc)
        try:
            token, scope = registry.create(
                user_id=OWNER_USER_ID,
                tenant_id=OWNER_TENANT_ID,
                now=now,
            )
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        except Exception:
            result = EXIT_CREATE
        else:
            try:
                resolved = registry.resolve(token, now=now)
                if (
                    resolved is None
                    or resolved.user_id != scope.user_id
                    or resolved.tenant_id != scope.tenant_id
                ):
                    result = EXIT_RESOLVE
                else:
                    result = 0
            except Exception:
                result = EXIT_RESOLVE

            if result == 0:
                try:
                    if not registry.revoke(token, now=now):
                        result = EXIT_REVOKE
                except Exception:
                    result = EXIT_REVOKE

        if not _cleanup_probe_session(connection, digest):
            result = EXIT_CLEANUP
    finally:
        token = ""
        digest = ""
        if connection is not None:
            close = getattr(connection, "close", None)
            if callable(close):
                close()

    if result == 0:
        print("WP15_LIVE_SESSION_RUNTIME_PROBE_PASS")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
