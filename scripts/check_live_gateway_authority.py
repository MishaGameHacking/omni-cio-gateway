from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import APP_VERSION  # noqa: E402
from omni_cio.release.live_authority_v1 import (  # noqa: E402
    accept_live_gateway_authority,
)


DEFAULT_BASE_URL = "https://omni-cio-gateway.onrender.com"
APPROVED_HOSTS = frozenset({"omni-cio-gateway.onrender.com"})


def main() -> None:
    base_url = os.getenv("OMNI_LIVE_BASE_URL", DEFAULT_BASE_URL)
    acceptance = accept_live_gateway_authority(
        base_url=base_url,
        expected_app_version=APP_VERSION,
        approved_hosts=APPROVED_HOSTS,
    )
    print(
        json.dumps(
            {
                "checked_at": acceptance.checked_at.isoformat(),
                "base_url": acceptance.base_url,
                "app_version": acceptance.app_version,
                "operation_ids": acceptance.operation_ids,
                "sandbox_enabled": acceptance.sandbox_enabled,
                "real_status_exposed": acceptance.real_status_exposed,
                "real_execution_ready_surface": acceptance.real_execution_ready_surface,
                "live_http_verified": True,
                "broker_mutation_called": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
