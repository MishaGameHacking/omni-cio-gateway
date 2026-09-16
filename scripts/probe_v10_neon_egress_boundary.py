from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import shutil
import subprocess
import sys
from typing import Mapping, TextIO


_NEON_API_HOST = "console.neon.tech"
_NEON_API_PREFIX = "/api/v2"
_SYNTHETIC_PROJECT_ID = "omni-cio-v10-egress-control-invalid"
_USER_AGENT = "curl/8.0"
_TIMEOUT_SECONDS = 20
_PROCESS_TIMEOUT_SECONDS = 25.0
_MAX_OUTPUT_CHARS = 256
_STATUS_UNAVAILABLE = "UNAVAILABLE"
_MEDIA_JSON = "JSON"
_MEDIA_HTML = "HTML"
_MEDIA_TEXT = "TEXT"
_MEDIA_OTHER = "OTHER"
_MEDIA_MISSING = "MISSING"
_ALLOWED_MEDIA = frozenset({_MEDIA_JSON, _MEDIA_HTML, _MEDIA_TEXT, _MEDIA_OTHER, _MEDIA_MISSING})
_EFFECT_CHANGED = "CHANGED"
_EFFECT_UNCHANGED = "UNCHANGED"
_EFFECT_UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class EgressProbeEvidence:
    status: str
    media: str


def _media_family(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        return _MEDIA_MISSING
    media_type = value.split(";", 1)[0].strip().casefold()
    if media_type == "application/json" or media_type.endswith("+json"):
        return _MEDIA_JSON
    if media_type == "text/html":
        return _MEDIA_HTML
    if media_type == "text/plain":
        return _MEDIA_TEXT
    return _MEDIA_OTHER


def _sanitized_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if environ is None else environ
    result: dict[str, str] = {}
    for name in ("SYSTEMROOT", "WINDIR"):
        value = source.get(name)
        if isinstance(value, str) and value:
            result[name] = value
    return result


def _unavailable() -> EgressProbeEvidence:
    return EgressProbeEvidence(_STATUS_UNAVAILABLE, _MEDIA_MISSING)


def _parse_probe_output(returncode: int, output: object) -> EgressProbeEvidence:
    if returncode != 0 or not isinstance(output, str) or len(output) > _MAX_OUTPUT_CHARS:
        return _unavailable()
    lines = output.splitlines()
    if len(lines) != 2:
        return _unavailable()
    status = lines[0].strip()
    if len(status) != 3 or not status.isdecimal():
        return _unavailable()
    status_code = int(status)
    if not 200 <= status_code <= 599 or 300 <= status_code < 400:
        return _unavailable()
    return EgressProbeEvidence(status, _media_family(lines[1].strip() or None))


def probe_egress_boundary(
    environ: Mapping[str, str] | None = None,
) -> EgressProbeEvidence:
    executable = shutil.which("curl")
    if not executable or not os.path.isabs(executable):
        return _unavailable()
    target = f"https://{_NEON_API_HOST}{_NEON_API_PREFIX}/projects/{_SYNTHETIC_PROJECT_ID}"
    command = [
        executable,
        "--disable",
        "--silent",
        "--output",
        os.devnull,
        "--write-out",
        "%{http_code}\n%{content_type}\n",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--http1.1",
        "--noproxy",
        "*",
        "--user-agent",
        _USER_AGENT,
        "--connect-timeout",
        "10",
        "--max-time",
        str(_TIMEOUT_SECONDS),
        "--max-redirs",
        "0",
        "--request",
        "GET",
        "--header",
        "Accept: application/json",
        target,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=_PROCESS_TIMEOUT_SECONDS,
            env=_sanitized_environment(environ),
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return _unavailable()
    return _parse_probe_output(completed.returncode, completed.stdout)


def _valid_evidence(status: str, media: str) -> bool:
    if status == _STATUS_UNAVAILABLE:
        return media == _MEDIA_MISSING
    return (
        len(status) == 3
        and status.isdecimal()
        and 200 <= int(status) <= 599
        and not 300 <= int(status) < 400
        and media in _ALLOWED_MEDIA
    )


def classify_egress_effect(
    self_hosted: EgressProbeEvidence,
    github_hosted: EgressProbeEvidence,
) -> str:
    if not _valid_evidence(self_hosted.status, self_hosted.media):
        return _EFFECT_UNAVAILABLE
    if not _valid_evidence(github_hosted.status, github_hosted.media):
        return _EFFECT_UNAVAILABLE
    if _STATUS_UNAVAILABLE in {self_hosted.status, github_hosted.status}:
        return _EFFECT_UNAVAILABLE
    if self_hosted == github_hosted:
        return _EFFECT_UNCHANGED
    return _EFFECT_CHANGED


def _write_github_output(evidence: EgressProbeEvidence, environ: Mapping[str, str]) -> None:
    path = environ.get("GITHUB_OUTPUT", "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"status={evidence.status}\n")
        stream.write(f"media={evidence.media}\n")


def _probe_command(*, output: TextIO, environ: Mapping[str, str]) -> int:
    evidence = probe_egress_boundary(environ)
    print(
        " ".join(
            (
                "CLOUDFLARE_NEON_EGRESS_CONTROL",
                f"status={evidence.status}",
                f"media={evidence.media}",
            )
        ),
        file=output,
    )
    _write_github_output(evidence, environ)
    return 78 if evidence.status == _STATUS_UNAVAILABLE else 0


def _compare_command(args: argparse.Namespace, *, output: TextIO) -> int:
    self_hosted = EgressProbeEvidence(args.self_status, args.self_media)
    github_hosted = EgressProbeEvidence(args.hosted_status, args.hosted_media)
    effect = classify_egress_effect(self_hosted, github_hosted)
    print(
        " ".join(
            (
                "CLOUDFLARE_NEON_EGRESS_BOUNDARY",
                f"self_hosted_status={self_hosted.status}",
                f"self_hosted_media={self_hosted.media}",
                f"github_hosted_status={github_hosted.status}",
                f"github_hosted_media={github_hosted.media}",
                f"egress_effect={effect}",
            )
        ),
        file=output,
    )
    return 78 if effect == _EFFECT_UNAVAILABLE else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("probe")
    compare = subparsers.add_parser("compare")
    compare.add_argument("--self-status", required=True)
    compare.add_argument("--self-media", required=True)
    compare.add_argument("--hosted-status", required=True)
    compare.add_argument("--hosted-media", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "probe":
        return _probe_command(output=sys.stdout, environ=os.environ)
    return _compare_command(args, output=sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
