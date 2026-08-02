from pathlib import Path as _Path

_globals = globals()
for _part in sorted((_Path(__file__).parent / "_parts").glob("*.pyfrag")):
    _source = _part.read_text(encoding="utf-8")
    # The loader executes only checked-in fragments from this fixed package path.
    exec(compile(_source, str(_part), "exec"), _globals, _globals)  # nosec B102

# app.py already invokes this package's dynamically assembled register_gateway
# hook before freezing its OpenAPI provider. Preserve that reviewed hook and add
# the explicitly enabled Sandbox extension after broker-report registration.
_register_broker_report_gateway = _globals["register_gateway"]

del _Path, _part, _source


def register_gateway(*, app, base, app_version):
    result = _register_broker_report_gateway(
        app=app,
        base=base,
        app_version=app_version,
    )
    from omni_cio.sandbox import maybe_register_sandbox_trading_gateway

    maybe_register_sandbox_trading_gateway(
        app=app,
        base=base,
        app_version=app_version,
    )
    return result


_globals["register_gateway"] = register_gateway
del _globals
