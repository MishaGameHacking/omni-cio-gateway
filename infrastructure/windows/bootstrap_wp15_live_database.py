from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


def _bind_source_root() -> None:
    root = Path(__file__).resolve().parents[2]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _read_owner_identity(connection: Any) -> tuple[Any | None, Any | None]:
    from omni_cio.contracts.v1.domain import (
        OWNER_TENANT_ID,
        OWNER_USER_ID,
        TenantMode,
        TenantV1,
        UserRole,
        UserV1,
    )
    from omni_cio.persistence.repository import model_record_sha256

    tenant_row = connection.execute(
        "SELECT tenant_id, schema_version, identity_version, mode, created_at, "
        "record_sha256 FROM omni_cio_v10.tenants WHERE tenant_id = %s",
        (OWNER_TENANT_ID,),
    ).fetchone()
    user_row = connection.execute(
        "SELECT user_id, tenant_id, schema_version, identity_version, role, "
        "created_at, record_sha256 FROM omni_cio_v10.users WHERE user_id = %s",
        (OWNER_USER_ID,),
    ).fetchone()

    tenant = None
    if tenant_row is not None:
        tenant_identity = (
            str(tenant_row[0]),
            str(tenant_row[1]),
            int(tenant_row[2]),
            str(tenant_row[3]),
        )
        if tenant_identity != (
            OWNER_TENANT_ID,
            "1.0",
            1,
            TenantMode.OWNER_PERSONAL.value,
        ):
            raise RuntimeError("WP15_LIVE_OWNER_TENANT_IDENTITY_INVALID")
        tenant = TenantV1(created_at=tenant_row[4])
        if str(tenant_row[5]) != model_record_sha256(tenant):
            raise RuntimeError("WP15_LIVE_OWNER_TENANT_INTEGRITY_INVALID")

    user = None
    if user_row is not None:
        user_identity = (
            str(user_row[0]),
            str(user_row[1]),
            str(user_row[2]),
            int(user_row[3]),
            str(user_row[4]),
        )
        if user_identity != (
            OWNER_USER_ID,
            OWNER_TENANT_ID,
            "1.0",
            1,
            UserRole.OWNER.value,
        ):
            raise RuntimeError("WP15_LIVE_OWNER_USER_IDENTITY_INVALID")
        user = UserV1(created_at=user_row[5])
        if str(user_row[6]) != model_record_sha256(user):
            raise RuntimeError("WP15_LIVE_OWNER_USER_INTEGRITY_INVALID")

    return tenant, user


def _ensure_owner_identity(connection: Any) -> None:
    from omni_cio.contracts.v1.domain import (
        CanonicalDomainCatalogV1,
        TenantV1,
        UserV1,
    )
    from omni_cio.persistence.repository import PostgresDomainRepository

    tenant, user = _read_owner_identity(connection)
    if tenant is None and user is not None:
        raise RuntimeError("WP15_LIVE_OWNER_IDENTITY_RELATIONSHIP_INVALID")
    if tenant is not None and user is not None:
        return

    now = datetime.now(timezone.utc)
    canonical_tenant = tenant or TenantV1(created_at=now)
    canonical_user = user or UserV1(created_at=now)
    catalog = CanonicalDomainCatalogV1(
        generated_at=now,
        tenants=(canonical_tenant,),
        users=(canonical_user,),
    )
    PostgresDomainRepository(connection).persist_catalog(catalog)

    verified_tenant, verified_user = _read_owner_identity(connection)
    if verified_tenant is None or verified_user is None:
        raise RuntimeError("WP15_LIVE_OWNER_IDENTITY_BOOTSTRAP_FAILED")


def main() -> int:
    _bind_source_root()
    from omni_cio.persistence.migration import apply_migrations, connect_postgres

    connection = connect_postgres("")
    try:
        apply_migrations(connection)
        _ensure_owner_identity(connection)
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
