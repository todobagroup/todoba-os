"""
P9B2 ? Vietcombank Official USD/VND FX Adapter.

Provider-specific network + XML parsing boundary.

This capability does NOT:
- persist authoritative snapshots
- schedule refresh
- define freshness TTL
- calculate commercial order amounts
- verify payments
"""

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from urllib.error import URLError

import pytest

import backend.commercial.customer_commercial_vietcombank_fx_adapter as module

from backend.commercial.customer_commercial_vietcombank_fx_adapter import (
    VIETCOMBANK_FX_SOURCE_ID,
    VietcombankFXAdapter,
    VietcombankFXResult,
)


FETCHED_AT = datetime(
    2026,
    9,
    17,
    8,
    30,
    tzinfo=UTC,
)


VALID_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ExrateList>
    <DateTime>09/17/2026 3:30:00 PM</DateTime>
    <Exrate
        CurrencyCode="EUR"
        CurrencyName="EURO"
        Buy="30000"
        Transfer="30100"
        Sell="30200"
    />
    <Exrate
        CurrencyCode="USD"
        CurrencyName="US DOLLAR"
        Buy="26200"
        Transfer="26230"
        Sell="26500"
    />
</ExrateList>
"""


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
    ) -> None:
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def read(self) -> bytes:
        return self._body


def clock():
    return FETCHED_AT


def install_response(
    monkeypatch,
    body: bytes,
):
    seen = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        seen["request"] = request
        seen["timeout"] = timeout
        return FakeResponse(body)

    monkeypatch.setattr(
        module,
        "urlopen",
        fake_urlopen,
    )

    return seen


def adapter():
    return VietcombankFXAdapter(
        timeout_seconds=5.0,
        clock=clock,
    )


def test_fetch_returns_exact_official_usd_sell_rate(
    monkeypatch,
):
    seen = install_response(
        monkeypatch,
        VALID_XML,
    )

    result = adapter().fetch()

    assert isinstance(
        result,
        VietcombankFXResult,
    )

    assert result.source_id == VIETCOMBANK_FX_SOURCE_ID
    assert result.source_id == "vietcombank-official"
    assert result.base_currency == "USD"
    assert result.quote_currency == "VND"

    assert result.usd_vnd_rate == Decimal(
        "26500"
    )

    assert result.fetched_at == FETCHED_AT

    assert result.published_at == datetime(
        2026,
        9,
        17,
        15,
        30,
        tzinfo=module.VIETNAM_TIMEZONE,
    ).astimezone(
        UTC
    )

    request = seen["request"]

    assert request.full_url == (
        "https://portal.vietcombank.com.vn/"
        "Usercontrols/TVPortal.TyGia/pXML.aspx"
    )

    assert seen["timeout"] == 5.0


def test_adapter_uses_sell_not_buy_or_transfer(
    monkeypatch,
):
    install_response(
        monkeypatch,
        VALID_XML,
    )

    result = adapter().fetch()

    assert result.usd_vnd_rate == Decimal(
        "26500"
    )

    assert result.usd_vnd_rate != Decimal(
        "26200"
    )

    assert result.usd_vnd_rate != Decimal(
        "26230"
    )


def test_transport_failure_fails_closed(
    monkeypatch,
):
    def fail_urlopen(
        request,
        *,
        timeout,
    ):
        raise URLError(
            "offline"
        )

    monkeypatch.setattr(
        module,
        "urlopen",
        fail_urlopen,
    )

    with pytest.raises(
        RuntimeError,
        match="transport",
    ):
        adapter().fetch()


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not xml",
        b"<ExrateList>",
    ],
)
def test_invalid_xml_fails_closed(
    monkeypatch,
    body,
):
    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="schema",
    ):
        adapter().fetch()


def test_missing_provider_datetime_fails_closed(
    monkeypatch,
):
    body = VALID_XML.replace(
        b"<DateTime>09/17/2026 3:30:00 PM</DateTime>",
        b"",
    )

    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="schema",
    ):
        adapter().fetch()


def test_invalid_provider_datetime_fails_closed(
    monkeypatch,
):
    body = VALID_XML.replace(
        b"09/17/2026 3:30:00 PM",
        b"not-a-provider-time",
    )

    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="schema",
    ):
        adapter().fetch()


def test_missing_usd_row_fails_closed(
    monkeypatch,
):
    body = VALID_XML.replace(
        b'CurrencyCode="USD"',
        b'CurrencyCode="GBP"',
    )

    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="USD",
    ):
        adapter().fetch()


def test_duplicate_usd_rows_fail_closed(
    monkeypatch,
):
    duplicate = b"""
    <Exrate
        CurrencyCode="USD"
        CurrencyName="US DOLLAR DUPLICATE"
        Buy="26200"
        Transfer="26230"
        Sell="26500"
    />
"""

    body = VALID_XML.replace(
        b"</ExrateList>",
        duplicate + b"</ExrateList>",
    )

    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="USD",
    ):
        adapter().fetch()


@pytest.mark.parametrize(
    "sell",
    [
        b"",
        b"abc",
        b"0",
        b"-1",
        b"NaN",
        b"Infinity",
    ],
)
def test_invalid_usd_sell_rate_fails_closed(
    monkeypatch,
    sell,
):
    body = VALID_XML.replace(
        b'Sell="26500"',
        b'Sell="' + sell + b'"',
    )

    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="Sell",
    ):
        adapter().fetch()


def test_missing_usd_sell_attribute_fails_closed(
    monkeypatch,
):
    body = VALID_XML.replace(
        b' Sell="26500"',
        b"",
    )

    install_response(
        monkeypatch,
        body,
    )

    with pytest.raises(
        RuntimeError,
        match="Sell",
    ):
        adapter().fetch()


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        True,
        "5",
    ],
)
def test_timeout_must_be_positive_number(
    timeout,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        VietcombankFXAdapter(
            timeout_seconds=timeout,
            clock=clock,
        )


def test_clock_must_return_timezone_aware_datetime(
    monkeypatch,
):
    install_response(
        monkeypatch,
        VALID_XML,
    )

    instance = VietcombankFXAdapter(
        timeout_seconds=5.0,
        clock=lambda: datetime(
            2026,
            9,
            17,
            8,
            30,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="timezone-aware",
    ):
        instance.fetch()


def test_result_is_provider_neutral_shape(
    monkeypatch,
):
    install_response(
        monkeypatch,
        VALID_XML,
    )

    result = adapter().fetch()

    assert set(
        result.__dataclass_fields__
    ) == {
        "source_id",
        "base_currency",
        "quote_currency",
        "usd_vnd_rate",
        "published_at",
        "fetched_at",
    }


def test_adapter_has_no_snapshot_or_order_authority():
    forbidden = (
        "snapshot_store",
        "freshness_ttl",
        "amount_vnd",
        "amount_due",
        "order_id",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
    )

    for name in forbidden:
        assert not hasattr(
            VietcombankFXAdapter,
            name,
        )
