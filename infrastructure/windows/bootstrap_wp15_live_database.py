from __future__ import annotations

from pathlib import Path
import sys


def _bind_source_root() -> None:
    root = Path(__file__).resolve().parents[2]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def main() -> int:
    _bind_source_root()
    from omni_cio.persistence.migration import apply_migrations, connect_postgres

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
