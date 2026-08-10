from __future__ import annotations

import json
import sys


def main() -> int:
    print(
        json.dumps(
            {
                "schema_version": "1",
                "work_package": "WP15",
                "status": "DEFERRED",
                "reason": "WP15_LIVE_ACCEPTANCE_DEFERRED_TO_WEB_PROVISIONING",
                "owner_action_required": False,
                "normal_broker_provisioning_surface": "WP17_AUTHENTICATED_WEB_SETTINGS",
                "block_d_credit_allowed": False,
                "wp18_real_data_acceptance_locked": True,
                "broker_write": False,
                "trading_methods": False,
                "real_trading_enabled": False,
            },
            sort_keys=True,
        )
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
