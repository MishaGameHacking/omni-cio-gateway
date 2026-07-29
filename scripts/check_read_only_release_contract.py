from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app import APP_VERSION, ENTRYPOINT, app  # noqa: E402
from omni_cio.release import build_read_only_release_manifest  # noqa: E402


APPROVED_ACTION_HOSTS = frozenset({"omni-cio-gateway.onrender.com"})


def main() -> None:
    if ENTRYPOINT != "app:app":
        raise SystemExit("Stable entrypoint must remain app:app")
    app.openapi_schema = None
    manifest = build_read_only_release_manifest(
        app.openapi(),
        expected_app_version=APP_VERSION,
        approved_hosts=APPROVED_ACTION_HOSTS,
    )
    print(
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
