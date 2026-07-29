from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import APP_VERSION  # noqa: E402
from omni_cio.release import accept_live_read_only_release  # noqa: E402


DEFAULT_BASE_URL = "https://omni-cio-gateway.onrender.com"
APPROVED_HOSTS = frozenset({"omni-cio-gateway.onrender.com"})


def main() -> None:
    base_url = os.getenv("OMNI_LIVE_BASE_URL", DEFAULT_BASE_URL)
    acceptance = accept_live_read_only_release(
        base_url=base_url,
        expected_app_version=APP_VERSION,
        approved_hosts=APPROVED_HOSTS,
    )
    print(
        json.dumps(
            acceptance.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
