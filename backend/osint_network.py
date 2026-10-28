"""HTTPS-only bounded transport, pinned public DNS address and no ambient credentials."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

try:
    from .osint_catalogue import IntakeError, USER_AGENT, canonical_url
except ImportError:
    from osint_catalogue import IntakeError, USER_AGENT, canonical_url

TIMEOUT = 25
REDIRECTS = {301, 302, 303, 307, 308}


def public_addresses(host: str) -> list[str]:
    addresses = sorted({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)},
                       key=lambda address: (ipaddress.ip_address(address).version, address))
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise IntakeError("osint_address_not_public")
    return addresses


def _connect_address(addresses):
    for address in addresses[:3]:
        try:
            return socket.create_connection((address, 443), timeout=4)
        except OSError:
            continue
    raise IntakeError("osint_connection_unavailable")


def _connection(host: str):
    # The checked numeric address is also the address actually connected to.
    # TLS still verifies the original hostname; redirects get an independent check.
    addresses = public_addresses(host)
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    connection = http.client.HTTPSConnection(host, timeout=TIMEOUT, context=context)
    sock = _connect_address(addresses)
    sock.settimeout(TIMEOUT)
    try:
        connection.sock = context.wrap_socket(sock, server_hostname=host)
    except BaseException:
        sock.close()
        raise
    return connection


def _request_headers(headers):
    safe = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity",
            "Accept": "application/rss+xml,application/atom+xml,application/json,text/html,application/pdf,text/plain"}
    for name in ("If-None-Match", "If-Modified-Since"):
        value = (headers or {}).get(name)
        if isinstance(value, str) and len(value) <= 512 and "\r" not in value and "\n" not in value:
            safe[name] = value
    return safe


def _read_body(response, metadata, connection, deadline, maximum):
    if metadata.get("content-encoding", "identity").lower() not in {"", "identity"}:
        raise IntakeError("osint_encoding_not_supported")
    declared = metadata.get("content-length")
    if declared and (not declared.isdigit() or int(declared) > maximum):
        raise IntakeError("osint_response_too_large")
    chunks, size = [], 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise IntakeError("osint_response_deadline")
        if connection.sock is not None:
            connection.sock.settimeout(min(TIMEOUT, remaining))
        block = response.read(min(65536, maximum + 1 - size))
        if not block:
            break
        chunks.append(block)
        size += len(block)
        if size > maximum:
            raise IntakeError("osint_response_too_large")
    return b"".join(chunks)


def _fetch_once(current, safe, maximum, deadline):
    parts = urlsplit(current)
    if time.monotonic() >= deadline:
        raise IntakeError("osint_response_deadline")
    connection = _connection(parts.hostname)
    try:
        connection.request("GET", parts.path + ("?" + parts.query if parts.query else ""), headers=safe)
        response = connection.getresponse()
        metadata = {key.lower(): value for key, value in response.getheaders()}
        raw = _read_body(response, metadata, connection, deadline, maximum) if response.status == 200 else b""
        return response.status, metadata, raw
    finally:
        connection.close()


def request(url: str, hosts: tuple[str, ...], headers: dict | None = None, maximum: int = 2_097_152,
            *, before_request=None) -> tuple[int, dict, bytes, str]:
    current = canonical_url(url, hosts)
    deadline = time.monotonic() + 60
    safe = _request_headers(headers)
    for attempt in range(4):
        if before_request:
            before_request(current)
        status, metadata, raw = _fetch_once(current, safe, maximum, deadline)
        if status not in REDIRECTS:
            return status, metadata, raw, current
        if attempt == 3:
            raise IntakeError("osint_redirect_limit")
        current = canonical_url(urljoin(current, metadata.get("location", "")), hosts)
        safe.pop("If-None-Match", None)
        safe.pop("If-Modified-Since", None)
    raise IntakeError("osint_redirect_limit")


def retry_at(value: str | None, now: int, attempts: int, interval: int) -> int:
    deadline = now + min(86400, max(interval, 60) * 2 ** min(attempts, 8))
    if isinstance(value, str) and len(value) <= 128:
        try:
            seconds = int(value) if value.isdigit() else int(parsedate_to_datetime(value).timestamp()) - now
            deadline = max(deadline, now + max(0, min(seconds, 366 * 86400)))
        except (ValueError, TypeError, OverflowError):
            pass
    return deadline


def robots_decision(raw: str, url: str) -> tuple[bool, int]:
    parser = RobotFileParser()
    parser.parse(raw.splitlines())
    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 3
    rate = parser.request_rate(USER_AGENT) or parser.request_rate("*")
    if rate and rate.requests:
        delay = max(delay, (rate.seconds + rate.requests - 1) // rate.requests)
    return parser.can_fetch(USER_AGENT, url), max(3, int(delay))
