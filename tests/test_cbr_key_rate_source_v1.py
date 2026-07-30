from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.macro import (
    CbrKeyRateSnapshotV1,
    KeyRateObservationV1,
    MacroDataErrorCode,
    MacroDataStatus,
)
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority
from omni_cio.market.cbr_key_rate_v1 import (
    CBR_KEY_RATE_ENDPOINT,
    CBR_KEY_RATE_SOAP_ACTION,
    CbrKeyRateSourceError,
    build_cbr_key_rate_soap_request,
    fetch_cbr_key_rate,
    parse_cbr_key_rate_xml,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
DATE_FROM = date(2025, 7, 30)
DATE_TO = date(2026, 7, 30)


def _nested_soap(*, conflicting_duplicate: bool = False) -> bytes:
    duplicate = (
        "<KR><DT>2026-07-23T00:00:00</DT><Rate>17.00</Rate></KR>"
        if conflicting_duplicate
        else ""
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><KeyRateXMLResponse xmlns="http://web.cbr.ru/">'
        "<KeyRateXMLResult><KeyRate>"
        "<KR><DT>2025-12-01T00:00:00</DT><Rate>19,00</Rate></KR>"
        "<KR><DT>2026-07-23T00:00:00</DT><Rate>18.00</Rate></KR>"
        f"{duplicate}"
        "</KeyRate></KeyRateXMLResult>"
        "</KeyRateXMLResponse></soap:Body></soap:Envelope>"
    ).encode()


def _escaped_soap() -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><KeyRateXMLResponse xmlns="http://web.cbr.ru/">'
        "<KeyRateXMLResult>"
        "&lt;KeyRate&gt;"
        "&lt;KR&gt;&lt;DT&gt;23.07.2026&lt;/DT&gt;"
        "&lt;Rate&gt;18,00&lt;/Rate&gt;&lt;/KR&gt;"
        "&lt;/KeyRate&gt;"
        "</KeyRateXMLResult>"
        "</KeyRateXMLResponse></soap:Body></soap:Envelope>"
    ).encode()


def _official_source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Bank of Russia DailyInfo",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id="DailyInfo.KeyRateXML",
    )


def test_available_snapshot_contract_requires_latest_current_row() -> None:
    first = KeyRateObservationV1(
        effective_date=date(2025, 12, 1),
        rate_percent=Decimal("19"),
    )
    latest = KeyRateObservationV1(
        effective_date=date(2026, 7, 23),
        rate_percent=Decimal("18"),
    )
    snapshot = CbrKeyRateSnapshotV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=NOW,
        status=MacroDataStatus.AVAILABLE,
        source=_official_source(),
        observations=(first, latest),
        current=latest,
    )

    assert snapshot.current == latest
    assert snapshot.raw_xml_stored is False
    assert snapshot.trading_methods is False

    with pytest.raises(ValidationError):
        CbrKeyRateSnapshotV1(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
            status=MacroDataStatus.AVAILABLE,
            source=_official_source(),
            observations=(first, latest),
            current=first,
        )


def test_unavailable_snapshot_contract_requires_redacted_error() -> None:
    snapshot = CbrKeyRateSnapshotV1(
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=NOW,
        status=MacroDataStatus.UNAVAILABLE,
        error_code=MacroDataErrorCode.NETWORK_ERROR,
    )

    assert snapshot.source is None
    assert snapshot.observations == ()

    with pytest.raises(ValidationError):
        CbrKeyRateSnapshotV1(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
            status=MacroDataStatus.UNAVAILABLE,
        )


def test_build_request_uses_fixed_operation_and_dates() -> None:
    request = build_cbr_key_rate_soap_request(DATE_FROM, DATE_TO).decode()

    assert "<KeyRateXML" in request
    assert "2025-07-30T00:00:00" in request
    assert "2026-07-30T23:59:59" in request
    assert "Authorization" not in request


def test_parse_nested_official_xml_sorts_and_normalizes_rows() -> None:
    snapshot = parse_cbr_key_rate_xml(
        _nested_soap(),
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=NOW,
    )

    assert snapshot.status is MacroDataStatus.AVAILABLE
    assert snapshot.source is not None
    assert snapshot.source.authority is SourceAuthority.OFFICIAL
    assert tuple(row.effective_date for row in snapshot.observations) == (
        date(2025, 12, 1),
        date(2026, 7, 23),
    )
    assert snapshot.current is not None
    assert snapshot.current.rate_percent == Decimal("18.00")


def test_parse_escaped_xml_document() -> None:
    snapshot = parse_cbr_key_rate_xml(
        _escaped_soap(),
        requested_from=DATE_FROM,
        requested_to=DATE_TO,
        retrieved_at=NOW,
    )

    assert snapshot.current is not None
    assert snapshot.current.effective_date == date(2026, 7, 23)
    assert snapshot.current.rate_percent == Decimal("18.00")


def test_parse_rejects_conflicting_duplicate_date() -> None:
    with pytest.raises(
        CbrKeyRateSourceError,
        match=MacroDataErrorCode.DUPLICATE_CONFLICT.value,
    ):
        parse_cbr_key_rate_xml(
            _nested_soap(conflicting_duplicate=True),
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
        )


def test_parse_rejects_rows_outside_requested_range() -> None:
    with pytest.raises(
        CbrKeyRateSourceError,
        match=MacroDataErrorCode.RANGE_MISMATCH.value,
    ):
        parse_cbr_key_rate_xml(
            _nested_soap(),
            requested_from=date(2026, 1, 1),
            requested_to=DATE_TO,
            retrieved_at=NOW,
        )


def test_parse_rejects_doctype_and_soap_fault() -> None:
    malicious = b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo/>'
    with pytest.raises(
        CbrKeyRateSourceError,
        match=MacroDataErrorCode.XML_INVALID.value,
    ):
        parse_cbr_key_rate_xml(
            malicious,
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
        )

    fault = (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body><soap:Fault><faultcode>server</faultcode>"
        "<faultstring>sensitive upstream text</faultstring>"
        "</soap:Fault></soap:Body></soap:Envelope>"
    ).encode()
    with pytest.raises(
        CbrKeyRateSourceError,
        match=MacroDataErrorCode.SOAP_FAULT.value,
    ):
        parse_cbr_key_rate_xml(
            fault,
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
        )


def test_fetch_success_uses_fixed_https_endpoint_without_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == CBR_KEY_RATE_ENDPOINT
        assert request.headers["soapaction"] == f'"{CBR_KEY_RATE_SOAP_ACTION}"'
        assert "authorization" not in request.headers
        assert "2026-07-30T23:59:59" in request.content.decode()
        return httpx.Response(
            200,
            headers={"content-type": "text/xml; charset=utf-8"},
            content=_nested_soap(),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = fetch_cbr_key_rate(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
            client=client,
        )

    assert snapshot.status is MacroDataStatus.AVAILABLE
    assert snapshot.current is not None
    assert snapshot.current.rate_percent == Decimal("18.00")


def test_fetch_network_http_content_type_size_and_redirect_fail_closed() -> None:
    def network_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private failure", request=request)

    cases: tuple[
        tuple[Callable[[httpx.Request], httpx.Response], MacroDataErrorCode, int],
        ...,
    ] = (
        (network_failure, MacroDataErrorCode.NETWORK_ERROR, 1_000_000),
        (
            lambda request: httpx.Response(503, request=request),
            MacroDataErrorCode.HTTP_ERROR,
            1_000_000,
        ),
        (
            lambda request: httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/html"},
                content=b"<html>not xml</html>",
            ),
            MacroDataErrorCode.CONTENT_TYPE_INVALID,
            1_000_000,
        ),
        (
            lambda request: httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/xml"},
                content=b"x" * 2_000,
            ),
            MacroDataErrorCode.RESPONSE_TOO_LARGE,
            1_024,
        ),
        (
            lambda request: httpx.Response(
                302,
                request=request,
                headers={"location": "https://example.invalid"},
            ),
            MacroDataErrorCode.HTTP_ERROR,
            1_000_000,
        ),
    )

    for handler, expected, limit in cases:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            snapshot = fetch_cbr_key_rate(
                requested_from=DATE_FROM,
                requested_to=DATE_TO,
                retrieved_at=NOW,
                client=client,
                max_response_bytes=limit,
            )
        assert snapshot.status is MacroDataStatus.UNAVAILABLE
        assert snapshot.error_code is expected
        assert snapshot.current is None
        assert snapshot.raw_xml_stored is False


def test_fetch_invalid_xml_is_redacted_and_input_guards_precede_network() -> None:
    def invalid_xml(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/xml"},
            content=b"<not-soap/>",
        )

    with httpx.Client(transport=httpx.MockTransport(invalid_xml)) as client:
        snapshot = fetch_cbr_key_rate(
            requested_from=DATE_FROM,
            requested_to=DATE_TO,
            retrieved_at=NOW,
            client=client,
        )
    assert snapshot.error_code is MacroDataErrorCode.XML_INVALID
    assert "not-soap" not in " ".join(snapshot.warnings)

    called = False

    def must_not_call(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request)

    with httpx.Client(transport=httpx.MockTransport(must_not_call)) as client:
        with pytest.raises(CbrKeyRateSourceError):
            fetch_cbr_key_rate(
                requested_from=DATE_TO,
                requested_to=DATE_FROM,
                retrieved_at=NOW,
                client=client,
            )
    assert called is False


def test_source_module_has_no_http_route_or_broker_write_surface() -> None:
    import omni_cio.market.cbr_key_rate_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
