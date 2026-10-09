"""Public release assets share the installed version, build and active palette."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from omnicio import __version__, web_assets

BUILD = "a1b2c3d4e5f6"
SHA = BUILD + "0" * 28
WEB_SOURCE = Path(__file__).resolve().parents[1] / "web"
PUBLIC_PATHS = {
    "index.html", "offline.html", "sw.js", "manifest.webmanifest", "version.js",
    "assets/config.js", "assets/i18n.js", "assets/workspace.js", "assets/app.js",
    "assets/tokens.css", "assets/app.css",
}


@pytest.fixture
def public_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    shutil.copytree(WEB_SOURCE, source)
    return source


def release_metadata(body: str) -> dict[str, str]:
    match = re.fullmatch(r"window\.OMNICIO_RELEASE = (\{.*\});\n", body)
    assert match is not None
    return json.loads(match.group(1))


def replace_token(source: Path, token: str, replacement: str) -> None:
    palette = source / "tokens.css"
    content, count = re.subn(
        rf"(?m)^\s*{re.escape(token)}\s*:\s*#[0-9a-fA-F]{{6}}\s*;",
        replacement, palette.read_text(encoding="utf-8"),
    )
    assert count == 1
    palette.write_text(content, encoding="utf-8")


def test_actual_templates_render_one_package_and_build_identity() -> None:
    rendered = web_assets.render_web_assets(WEB_SOURCE, BUILD)
    assert set(rendered) == PUBLIC_PATHS
    assert release_metadata(rendered["version.js"]) == {"version": __version__, "build": BUILD}
    versions = re.findall(r'data-release-version[^>]*>([^<]+)<', rendered["index.html"])
    assert versions
    assert set(versions) == {__version__}
    for path, body in rendered.items():
        assert "__OMNICIO_" not in body, path
        if path != "manifest.webmanifest":
            assert BUILD in body, path
    assert f"/assets/tokens.css?build={BUILD}" in rendered["index.html"]
    assert f"/assets/tokens.css?build={BUILD}" in rendered["offline.html"]
    assert f'const build = "{BUILD}";' in rendered["sw.js"]


def test_version_build_and_palette_change_together(public_source: Path) -> None:
    replace_token(public_source, "--browser-theme-dark", "  --browser-theme-dark: #123456;")
    replace_token(public_source, "--browser-theme-light", "  --browser-theme-light: #abcdef;")
    rendered = web_assets.render_web_assets(public_source, "browser-contract", version="2.4.6-rc.1")
    assert release_metadata(rendered["version.js"]) == {
        "version": "2.4.6-rc.1", "build": "browser-contract",
    }
    manifest = json.loads(rendered["manifest.webmanifest"])
    assert manifest["theme_color"] == manifest["background_color"] == "#123456"
    for document in ("index.html", "offline.html"):
        assert '<meta name="theme-color" content="#123456">' in rendered[document]
    assert "--browser-theme-light: #abcdef;" in rendered["assets/tokens.css"]
    assert "data-release-version data-app-version>2.4.6-rc.1<" in rendered["index.html"]


@pytest.mark.parametrize("value", ["", "../release", 'x\"</script>', "x\ny", "a" * 65])
@pytest.mark.parametrize("field", ["build", "version"])
def test_unsafe_release_values_are_rejected_before_rendering(value: str, field: str) -> None:
    arguments = {"build": BUILD, "version": __version__, field: value}
    with pytest.raises(ValueError, match="Invalid public release"):
        web_assets.render_web_assets(WEB_SOURCE, **arguments)


@pytest.mark.parametrize("token", ["--browser-theme-dark", "--browser-theme-light"])
@pytest.mark.parametrize("definition", ["", "{token}: red;", "{token}: #123;",
                                          "{token}: #123456;\n{token}: #abcdef;",
                                          "{token}: #123456; {token}: #abcdef;"])
def test_missing_invalid_or_duplicate_palette_definition_blocks_rendering(
    public_source: Path, token: str, definition: str,
) -> None:
    replace_token(public_source, token, definition.format(token=token))
    with pytest.raises(ValueError, match="browser theme token"):
        web_assets.render_web_assets(public_source, BUILD)


@pytest.mark.parametrize("token", ["--browser-theme-dark", "--browser-theme-light"])
def test_commented_palette_definition_cannot_certify_active_browser_theme(
    public_source: Path, token: str,
) -> None:
    replace_token(public_source, token, f"/* removed theme:\n{token}: #123456;\n*/")
    with pytest.raises(ValueError, match="browser theme token"):
        web_assets.render_web_assets(public_source, BUILD)


@pytest.mark.parametrize("name", ["config.js", "i18n.js", "workspace.js", "app.js",
                                   "index.html", "offline.html", "sw.js", "tokens.css"])
def test_a_stale_asset_without_build_marker_cannot_join_a_release(
    public_source: Path, name: str,
) -> None:
    asset = public_source / name
    asset.write_text(asset.read_text(encoding="utf-8").replace("__OMNICIO_BUILD__", "old-build"),
                     encoding="utf-8")
    with pytest.raises(ValueError, match="Missing build marker"):
        web_assets.render_web_assets(public_source, BUILD)


def test_literal_old_index_version_is_rejected(public_source: Path) -> None:
    index = public_source / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("__OMNICIO_VERSION__", "0.0.1"),
                     encoding="utf-8")
    with pytest.raises(ValueError, match="Missing package version marker"):
        web_assets.render_web_assets(public_source, BUILD)


@pytest.mark.parametrize("manifest", ["{broken", "[]", '{"theme_color":"#ffffff"}'])
def test_invalid_or_inconsistent_manifest_blocks_all_publication(
    public_source: Path, tmp_path: Path, manifest: str,
) -> None:
    (public_source / "manifest.webmanifest").write_text(manifest, encoding="utf-8")
    destination = tmp_path / "unpublished"
    destination.mkdir()
    sentinel = destination / "index.html"
    sentinel.write_text("existing unpublished asset", encoding="utf-8")
    with pytest.raises(ValueError):
        web_assets.write_web_assets(public_source, destination, BUILD)
    assert sentinel.read_text(encoding="utf-8") == "existing unpublished asset"
    assert list(destination.iterdir()) == [sentinel]


def test_write_emits_the_same_complete_release_and_preserves_templates(
    public_source: Path, tmp_path: Path,
) -> None:
    original = (public_source / "index.html").read_bytes()
    expected = web_assets.render_web_assets(public_source, BUILD)
    destination = tmp_path / "release"
    web_assets.write_web_assets(public_source, destination, BUILD)
    actual = {path.relative_to(destination).as_posix(): path.read_text(encoding="utf-8")
              for path in destination.rglob("*") if path.is_file()}
    assert actual == expected
    assert (public_source / "index.html").read_bytes() == original


def test_write_rejects_its_source_as_the_publication_directory(public_source: Path) -> None:
    with pytest.raises(ValueError, match="differ from the source"):
        web_assets.write_web_assets(public_source, public_source / ".", BUILD)


@pytest.mark.parametrize("sha", ["main", BUILD, SHA.upper(), "f" * 41])
def test_cli_requires_exact_lowercase_accepted_commit(
    public_source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sha: str,
) -> None:
    destination = tmp_path / "release"
    monkeypatch.setattr(sys, "argv", ["web_assets", str(public_source), str(destination), sha])
    with pytest.raises(SystemExit) as error:
        web_assets.main()
    assert error.value.code == 2
    assert not destination.exists()


def test_cli_derives_the_public_build_from_the_accepted_commit(
    public_source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "release"
    monkeypatch.setattr(sys, "argv", ["web_assets", str(public_source), str(destination), SHA])
    web_assets.main()
    assert release_metadata((destination / "version.js").read_text(encoding="utf-8")) == {
        "version": __version__, "build": BUILD,
    }
