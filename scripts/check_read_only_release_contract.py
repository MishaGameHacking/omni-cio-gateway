from __future__ import annotations

import json

from app import APP_VERSION, ENTRYPOINT, app
from omni_cio.release import build_read_only_release_manifest


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
