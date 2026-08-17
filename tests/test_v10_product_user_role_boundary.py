from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md"
)
AMENDMENTS_INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
MASTER_PLAN_README = ROOT / "docs/master-plan/README.md"
WP22_SYSTEM_CONTRACT = ROOT / "docs/architecture/V10_WP22_SYSTEM_ADMIN_UI_CONTRACT.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_owner_is_not_a_special_product_role() -> None:
    text = _read(AMENDMENT)

    assert "PROJECT OWNER using Omni-CIO == ordinary USER using Omni-CIO" in text
    assert "`PROJECT OWNER` is **not** an Omni-CIO product RBAC role." in text
    assert (
        "engineering authority to publish/operate the service != product authority to read/use a tenant"
        in text
    )
    assert "WP22A — External Web Access / Product Authentication Security Gate" in text
    assert "Block F must implement a **USER-scoped Telegram companion**" in text


def test_active_amendment_index_uses_user_scoped_product_language() -> None:
    text = _read(AMENDMENTS_INDEX)

    assert "### 9. Product User / Engineering Authority Boundary" in text
    assert "Telegram is a private **USER-scoped** companion interface" in text
    assert (
        "Real execution remains cash-only BUY/SELL after immutable authenticated USER approval"
        in text
    )
    assert "Telegram is an OWNER-only private companion interface" not in text
    assert "proposal rejection/revision creates a bounded OWNER dialogue" not in text


def test_master_plan_navigation_surfaces_role_separation() -> None:
    text = _read(MASTER_PLAN_README)

    assert (
        "OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md"
        in text
    )
    assert "PROJECT OWNER is not a special Omni-CIO product role" in text
    assert "GitHub/provider/Windows authority stays outside product identity" in text


def test_wp22_system_surface_is_user_diagnostics_not_owner_admin_cabinet() -> None:
    text = _read(WP22_SYSTEM_CONTRACT)

    assert "USER-facing local/private **System / Diagnostics**" in text
    assert "`/system` is not a cross-tenant operator console" in text
    assert "must not become an unrestricted administrator shell" in text
    assert "single OWNER-facing local/private operating surface" not in text
