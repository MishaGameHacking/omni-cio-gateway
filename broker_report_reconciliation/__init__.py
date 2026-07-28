from pathlib import Path as _Path

_globals = globals()
for _part in sorted((_Path(__file__).parent / "_parts").glob("*.pyfrag")):
    _source = _part.read_text(encoding="utf-8")
    # The loader executes only checked-in fragments from this fixed package path.
    exec(compile(_source, str(_part), "exec"), _globals, _globals)  # nosec B102

del _Path, _globals, _part, _source
