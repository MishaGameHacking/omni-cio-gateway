from pathlib import Path as _Path

_globals = globals()
for _part in sorted((_Path(__file__).parent / "_parts").glob("*.pyfrag")):
    _source = _part.read_text(encoding="utf-8")
    # The loader executes only checked-in fragments from this fixed package path.
    exec(compile(_source, str(_part), "exec"), _globals, _globals)  # nosec B102

del _Path, _globals, _part, _source

# app.py already invokes this package's register_gateway hook before freezing its
# OpenAPI provider. Keep the production default unchanged, but use that existing
# registration point for the explicitly enabled, isolated Sandbox extension.
# The sandbox module itself hard-binds all broker writes to the documented
# sandbox host and never receives TINVEST_TOKEN.
_register_broker_report_gateway = register_gateway


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
