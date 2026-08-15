from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "infrastructure" / "windows" / "run_wp22a_private_remote_runtime.ps1"
EXTERNAL_ACCESS = ROOT / "omni_cio" / "web" / "external_access_v1.py"


def test_remote_runtime_disables_uvicorn_forwarded_address_rewrite() -> None:
    source = RUNTIME.read_text(encoding="utf-8")

    assert "--host 127.0.0.1" in source
    assert "--no-proxy-headers" in source
    assert "--proxy-headers" not in source.replace("--no-proxy-headers", "")
    assert "--forwarded-allow-ips" not in source
    assert "FORWARDED_ALLOW_IPS" not in source


def test_application_keeps_actual_loopback_proxy_peer_as_trust_boundary() -> None:
    source = EXTERNAL_ACCESS.read_text(encoding="utf-8")
    loopback = source[
        source.index("def _is_loopback") : source.index("def _local_host_matches")
    ]
    middleware = source[
        source.index("class ExternalAccessSecurityMiddlewareV1") : source.index(
            "def install_private_remote_access_v1"
        )
    ]

    assert "request.client" in loopback
    assert "ipaddress.ip_address(client.host).is_loopback" in loopback
    assert 'request.headers.get("x-forwarded-for"' not in loopback.lower()
    assert "if not _is_loopback(request):" in middleware
    assert '"UNTRUSTED_PROXY_PATH"' in middleware
    assert 'request.headers.get(TAILSCALE_LOGIN_HEADER, "")' in middleware
