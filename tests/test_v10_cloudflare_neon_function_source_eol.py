from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_ATTRIBUTES = _ROOT / ".gitattributes"
_FUNCTION_SOURCE = _ROOT / "infrastructure/cloudflare/cf_d_neon_bootstrap"
_EOL_RULE = "infrastructure/cloudflare/cf_d_neon_bootstrap/*.mjs text eol=lf"


def test_cf_d_function_sources_are_pinned_to_lf() -> None:
    lines = {
        line.strip()
        for line in _ATTRIBUTES.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert _EOL_RULE in lines


@pytest.mark.parametrize("name", ["index.mjs", "provenance_wrapper.mjs"])
def test_cf_d_function_source_checkout_bytes_are_lf_only(name: str) -> None:
    payload = (_FUNCTION_SOURCE / name).read_bytes()
    assert payload
    assert b"\r\n" not in payload
