"""Render public web assets from one package version and one reviewed palette.

The production deployer and browser fixtures use this same renderer. It prepares
only public assets; legal identities, secrets and user data never enter this map.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import __version__

SCRIPT_ASSETS = ("config.js", "i18n.js", "workspace.js", "app.js")
INDEX_ASSET = "index.html"
PALETTE_ASSET = "tokens.css"
STYLE_ASSETS = (PALETTE_ASSET, "app.css")
DOCUMENT_ASSETS = (INDEX_ASSET, "offline.html", "sw.js", "manifest.webmanifest")
VERSION_MARKER = "__OMNICIO_VERSION__"
BUILD_MARKER = "__OMNICIO_BUILD__"
THEME_MARKERS = {
    "__OMNICIO_THEME_COLOR__": "--browser-theme-dark",
    "__OMNICIO_THEME_COLOR_LIGHT__": "--browser-theme-light",
}
# These values are inserted into HTML, JavaScript and URLs without new authority.
# Keep their alphabet bounded so package metadata cannot become active markup.
RELEASE_VALUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}")
RELEASE_SHA_RE = re.compile(r"[0-9a-f]{40}")


def _theme_replacements(palette: str) -> dict[str, str]:
    """Read the two browser chrome colors; each must have one literal definition."""
    # Commented examples cannot supply a missing live token or hide a duplicate.
    active_palette = re.sub(r"/\*.*?\*/", "", palette, flags=re.S)
    replacements: dict[str, str] = {}
    for marker, token in THEME_MARKERS.items():
        colors = re.findall(
            rf"(?<![-\w]){re.escape(token)}\s*:\s*([^;{{}}]+);",
            active_palette,
        )
        if len(colors) != 1 or re.fullmatch(r"#[0-9a-fA-F]{6}", colors[0].strip()) is None:
            raise ValueError(f"Expected one hexadecimal browser theme token: {token}")
        replacements[marker] = colors[0].strip()
    return replacements


def _render_template(template: str, replacements: dict[str, str]) -> str:
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    if re.search(r"__OMNICIO_(?:VERSION|BUILD|THEME_COLOR(?:_LIGHT)?)__", template):
        raise ValueError("A public web asset contains an unresolved release marker")
    return template


def render_web_assets(
    source: Path, build: str, *, version: str = __version__,
) -> dict[str, str]:
    """Render a complete public release in memory before any files are published.

    Production supplies the accepted commit's first 12 hexadecimal characters.
    Isolated browser fixtures may supply a descriptive build name. The optional
    version argument exists for contract tests; the CLI always uses package metadata.
    """
    if not RELEASE_VALUE_RE.fullmatch(build) or not RELEASE_VALUE_RE.fullmatch(version):
        raise ValueError("Invalid public release version or build identifier")
    replacements = {
        VERSION_MARKER: version,
        BUILD_MARKER: build,
        **_theme_replacements((source / PALETTE_ASSET).read_text(encoding="utf-8")),
    }
    paths = {name: name for name in DOCUMENT_ASSETS}
    paths.update({f"assets/{name}": name for name in (*SCRIPT_ASSETS, *STYLE_ASSETS)})
    rendered: dict[str, str] = {}
    for destination, name in paths.items():
        template = (source / name).read_text(encoding="utf-8")
        if (name in (*SCRIPT_ASSETS, INDEX_ASSET, "offline.html", "sw.js", PALETTE_ASSET)
                and BUILD_MARKER not in template):
            raise ValueError(f"Missing build marker in public asset: {name}")
        if name == INDEX_ASSET and VERSION_MARKER not in template:
            raise ValueError("Missing package version marker in public index")
        content = _render_template(template, replacements)
        if name in STYLE_ASSETS:
            # Styles also expose their release identity to post-deploy readback.
            content = f"/* OMNICIO build: {build} */\n" + content
        rendered[destination] = content
    manifest = json.loads(rendered["manifest.webmanifest"])
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != replacements["__OMNICIO_THEME_COLOR__"]
        for key in ("theme_color", "background_color")
    ):
        raise ValueError("Web manifest colors do not match the canonical dark theme")
    rendered["version.js"] = (
        "window.OMNICIO_RELEASE = "
        + json.dumps({"version": version, "build": build}, separators=(",", ":"))
        + ";\n"
    )
    return rendered


def write_web_assets(source: Path, destination: Path, build: str) -> None:
    """Write validated assets into the deployer's unpublished release directory."""
    if source.resolve() == destination.resolve():
        raise ValueError("The public release directory must differ from the source")
    rendered = render_web_assets(source, build)
    for relative, content in rendered.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        target.chmod(0o644)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("release_sha")
    args = parser.parse_args()
    if not RELEASE_SHA_RE.fullmatch(args.release_sha):
        parser.error("release_sha must identify the exact accepted 40-character commit")
    write_web_assets(args.source, args.destination, args.release_sha[:12])


if __name__ == "__main__":
    main()
