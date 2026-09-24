from pathlib import Path as _Path

_globals = globals()
for _part in sorted((_Path(__file__).parent / "_parts").glob("*.pyfrag")):
    _source = _part.read_text(encoding="utf-8")
    # The loader executes only checked-in fragments from this fixed package path.
    exec(compile(_source, str(_part), "exec"), _globals, _globals)  # nosec B102

# app.py invokes this package's assembled register_gateway hook before freezing
# its OpenAPI provider. Preserve that reviewed hook and attach explicitly enabled
# extensions here so disabled modes remain absent from the GPT Actions schema.
_register_broker_report_gateway = _globals["register_gateway"]

del _Path, _part, _source


def register_gateway(*, app, base, app_version):
    result = _register_broker_report_gateway(
        app=app,
        base=base,
        app_version=app_version,
    )

    from omni_cio.watchtower.routes_v1 import register_watchtower_routes
    from omni_cio.watchtower.runtime_v1 import WatchtowerEvidenceProviderRegistryV1

    watchtower_registry = getattr(app.state, "watchtower_provider_registry", None)
    if not isinstance(watchtower_registry, WatchtowerEvidenceProviderRegistryV1):
        watchtower_registry = WatchtowerEvidenceProviderRegistryV1()
        app.state.watchtower_provider_registry = watchtower_registry
    app.state.watchtower_route_registration = register_watchtower_routes(
        app,
        provider_registry=watchtower_registry,
    )

    from omni_cio.sandbox import maybe_register_sandbox_trading_gateway

    maybe_register_sandbox_trading_gateway(
        app=app,
        base=base,
        app_version=app_version,
    )

    from omni_cio.real_trading.routes_v1 import maybe_register_real_trading_gateway

    def expected_real_account_id():
        base.ensure_configured()
        with base.Client(base.TINVEST_TOKEN) as client:
            account_id, _ = base.get_open_account(client)
            return account_id

    def trusted_real_market_snapshot(instrument_uid):
        return base.market_snapshot(instrument_uid=instrument_uid, depth=1)

    maybe_register_real_trading_gateway(
        app=app,
        base=base,
        app_version=app_version,
        expected_account_id_provider=expected_real_account_id,
        market_snapshot_provider=trusted_real_market_snapshot,
    )
    return result


_globals["register_gateway"] = register_gateway
del _globals
