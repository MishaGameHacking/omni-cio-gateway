"""GET-only IPv4 custody observation; successful observation is not activation."""

from __future__ import annotations

from scripts import probe_v10_timeweb_postgres_control_plane as read_only
from scripts import provision_v10_render_neon_preview as provider_base
from scripts import timeweb_ipv4_custody as custody


def observe() -> None:
    token = provider_base._required_env(read_only.TOKEN_ENV)
    api = read_only.TimewebReadOnlyApi(token)
    project_id = read_only._select_project(api.get("/api/v1/projects"))
    project_path = f"/api/v1/projects/{project_id}/resources/databases"
    cluster_id = read_only._target_cluster_id(api.get(project_path))
    if cluster_id is None:
        raise custody.CustodyStopped("TIMEWEB_IPV4_TARGET_NOT_FOUND")
    payload = provider_base._json_object(
        api.get(f"/api/v1/databases/{cluster_id}"),
        "TIMEWEB_IPV4_TARGET_RESPONSE_INVALID",
    )
    target = provider_base._json_object(
        payload.get("db"),
        "TIMEWEB_IPV4_TARGET_RESPONSE_INVALID",
    )
    if target.get("name") != read_only.TARGET_CLUSTER_NAME:
        raise custody.CustodyStopped("TIMEWEB_IPV4_TARGET_IDENTITY_DRIFT")
    if type(target.get("is_enabled_public_network")) is not bool:
        raise custody.CustodyStopped("TIMEWEB_IPV4_PUBLIC_STATE_UNKNOWN")
    rows = custody.inventory(custody.raw_inventory(api.get("/api/v1/floating-ips")))
    provider_base._emit(custody.observation(rows, int(cluster_id)))
    provider_base._emit(
        custody.disposition(
            rows,
            int(cluster_id),
            public_enabled=target["is_enabled_public_network"],
        )
    )


def main() -> int:
    try:
        observe()
    except custody.CustodyStopped as exc:
        provider_base._emit(f"TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED code={exc}")
        return 1
    except provider_base.ProvisioningStopped as exc:
        provider_base._emit(f"TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED code={exc.code}")
        return 1
    except Exception:
        provider_base._emit(
            "TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED "
            "code=TIMEWEB_IPV4_OBSERVATION_UNAVAILABLE"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
