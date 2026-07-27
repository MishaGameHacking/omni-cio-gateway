from pathlib import Path as _Path

_globals = globals()
for _part in sorted((_Path(__file__).parent / "_parts").glob("*.pyfrag")):
    _source = _part.read_text(encoding="utf-8")
    exec(compile(_source, str(_part), "exec"), _globals, _globals)

del _Path, _globals, _part, _source
