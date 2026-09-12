from __future__ import annotations

from pathlib import Path

import scripts.check_ci_security_baseline as baseline


_CF_D_METADATA_PATHS = (
    "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json",
    "scripts/deploy_v10_cloudflare_neon_bootstrap_function.py",
    "tests/test_v10_cloudflare_neon_function_deployment.py",
)


def _write_lines(root: Path, relative: str, lines: list[str]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_cf_d_neon_authority_metadata_allowlist_is_exact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    results: dict[str, list[dict[str, object]]] = {}
    for relative in _CF_D_METADATA_PATHS:
        lines = sorted(baseline.APPROVED_KEYWORD_LINES[relative])
        _write_lines(tmp_path, relative, lines)
        results[relative] = [
            {"type": "Secret Keyword", "line_number": index}
            for index in range(1, len(lines) + 1)
        ]

    failures: list[str] = []
    baseline.validate_detect_secrets_report({"results": results}, failures)
    assert failures == []


def test_cf_d_neon_authority_metadata_allowlist_rejects_changed_line(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    relative = _CF_D_METADATA_PATHS[0]
    approved = sorted(baseline.APPROVED_KEYWORD_LINES[relative])[0]
    _write_lines(tmp_path, relative, [approved + " altered"])

    failures: list[str] = []
    baseline.validate_detect_secrets_report(
        {
            "results": {
                relative: [{"type": "Secret Keyword", "line_number": 1}],
            }
        },
        failures,
    )
    assert failures == [f"potential secret: {relative}:1 (Secret Keyword)"]
