from __future__ import annotations

import importlib.util
from pathlib import Path


def test_gpt_recovery_consistency() -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "check_gpt_recovery_consistency.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_gpt_recovery_consistency",
        script_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
