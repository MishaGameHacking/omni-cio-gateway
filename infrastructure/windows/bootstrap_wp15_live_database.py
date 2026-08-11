from __future__ import annotations

from omni_cio.persistence.migration import apply_migrations, connect_postgres


def main() -> int:
    connection = connect_postgres("")
    try:
        apply_migrations(connection)
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
