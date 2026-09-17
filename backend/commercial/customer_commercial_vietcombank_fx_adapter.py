"""
TODOBA Vietcombank Official FX Adapter.

P9B2 owns only the provider-specific read boundary:

    Vietcombank official XML endpoint
        -> exact provider timestamp
        -> exact USD row
        -> exact Sell rate
        -> provider-neutral result

Security / authority boundary:

- fixed HTTPS endpoint
- GET only
- finite positive timeout
- no credentials
- no configurable arbitrary provider URL
- no fallback provider
- malformed or ambiguous provider data fails closed
- only USD/VND is published
- only the provider Sell field becomes the USD/VND rate

P9B2 deliberately does not:

- persist FX snapshots
- schedule refreshes
- define freshness or stale policy
- calculate order amounts
- create or mutate orders
- verify payment
- own settlement or entitlement authority
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


VIETCOMBANK_FX_SOURCE_ID = "vietcombank-official"

VIETCOMBANK_FX_ENDPOINT = (
    "https://portal.vietcombank.com.vn/"
    "Usercontrols/TVPortal.TyGia/pXML.aspx"
)

VIETNAM_TIMEZONE = timezone(
    timedelta(
        hours=7,
    ),
    name="Asia/Ho_Chi_Minh",
)

_GENERIC_TRANSPORT_ERROR = (
    "Vietcombank FX transport failed."
)

_GENERIC_SCHEMA_ERROR = (
    "Vietcombank FX response has invalid schema."
)

_USD_SCHEMA_ERROR = (
    "Vietcombank FX response must contain "
    "exactly one USD row."
)

_USD_SELL_ERROR = (
    "Vietcombank USD Sell rate is invalid."
)


@dataclass(
    frozen=True,
)
class VietcombankFXResult:
    """
    Provider-neutral authoritative result from Vietcombank.
    """

    source_id: str
    base_currency: str
    quote_currency: str
    usd_vnd_rate: Decimal
    published_at: datetime
    fetched_at: datetime

    def __post_init__(
        self,
    ) -> None:
        if self.source_id != VIETCOMBANK_FX_SOURCE_ID:
            raise ValueError(
                "source_id must identify Vietcombank official FX."
            )

        if (
            self.base_currency != "USD"
            or self.quote_currency != "VND"
        ):
            raise ValueError(
                "Vietcombank FX result must be USD/VND."
            )

        if not isinstance(
            self.usd_vnd_rate,
            Decimal,
        ):
            raise TypeError(
                "usd_vnd_rate must be Decimal."
            )

        if (
            not self.usd_vnd_rate.is_finite()
            or self.usd_vnd_rate <= Decimal("0")
        ):
            raise ValueError(
                "usd_vnd_rate must be positive and finite."
            )

        object.__setattr__(
            self,
            "published_at",
            self._normalize_datetime(
                self.published_at,
                name="published_at",
            ),
        )

        object.__setattr__(
            self,
            "fetched_at",
            self._normalize_datetime(
                self.fetched_at,
                name="fetched_at",
            ),
        )

    @staticmethod
    def _normalize_datetime(
        value: datetime,
        *,
        name: str,
    ) -> datetime:
        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                f"{name} must be datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                f"{name} must be timezone-aware."
            )

        return value.astimezone(
            UTC
        )


class VietcombankFXAdapter:
    """
    Synchronous server-side adapter for official Vietcombank FX XML.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float,
        clock: Callable[
            [],
            datetime,
        ],
    ) -> None:
        if isinstance(
            timeout_seconds,
            bool,
        ):
            raise TypeError(
                "timeout_seconds must be numeric."
            )

        if not isinstance(
            timeout_seconds,
            (
                int,
                float,
            ),
        ):
            raise TypeError(
                "timeout_seconds must be numeric."
            )

        normalized_timeout = float(
            timeout_seconds
        )

        if (
            not math.isfinite(
                normalized_timeout
            )
            or normalized_timeout <= 0
        ):
            raise ValueError(
                "timeout_seconds must be positive and finite."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self._timeout_seconds = (
            normalized_timeout
        )
        self._clock = clock

    def fetch(
        self,
    ) -> VietcombankFXResult:
        fetched_at = self._read_clock()

        request = Request(
            VIETCOMBANK_FX_ENDPOINT,
            method="GET",
            headers={
                "Accept": "application/xml,text/xml",
                "User-Agent": "TODOBA-FX/1",
            },
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                status = getattr(
                    response,
                    "status",
                    200,
                )

                if status != 200:
                    raise RuntimeError(
                        _GENERIC_TRANSPORT_ERROR
                    )

                raw_body = response.read()

        except RuntimeError:
            raise

        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
        ):
            raise RuntimeError(
                _GENERIC_TRANSPORT_ERROR
            ) from None

        root = self._parse_xml(
            raw_body
        )

        published_at = (
            self._parse_published_at(
                root
            )
        )

        usd_row = self._require_usd_row(
            root
        )

        rate = self._parse_usd_sell(
            usd_row
        )

        return VietcombankFXResult(
            source_id=(
                VIETCOMBANK_FX_SOURCE_ID
            ),
            base_currency="USD",
            quote_currency="VND",
            usd_vnd_rate=rate,
            published_at=published_at,
            fetched_at=fetched_at,
        )

    def _read_clock(
        self,
    ) -> datetime:
        value = self._clock()

        if not isinstance(
            value,
            datetime,
        ):
            raise RuntimeError(
                "FX clock must return "
                "timezone-aware datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise RuntimeError(
                "FX clock must return "
                "timezone-aware datetime."
            )

        return value.astimezone(
            UTC
        )

    @staticmethod
    def _parse_xml(
        raw_body: bytes,
    ) -> ET.Element:
        if not isinstance(
            raw_body,
            bytes,
        ):
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            )

        try:
            decoded = raw_body.decode(
                "utf-8"
            )

            root = ET.fromstring(
                decoded
            )

        except (
            UnicodeDecodeError,
            ET.ParseError,
        ):
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            ) from None

        if root.tag != "ExrateList":
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            )

        return root

    @staticmethod
    def _parse_published_at(
        root: ET.Element,
    ) -> datetime:
        matches = root.findall(
            "DateTime"
        )

        if len(
            matches
        ) != 1:
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            )

        raw = matches[
            0
        ].text

        if not isinstance(
            raw,
            str,
        ):
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            )

        normalized = raw.strip()

        if not normalized:
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            )

        try:
            parsed = datetime.strptime(
                normalized,
                "%m/%d/%Y %I:%M:%S %p",
            )
        except ValueError:
            raise RuntimeError(
                _GENERIC_SCHEMA_ERROR
            ) from None

        return parsed.replace(
            tzinfo=VIETNAM_TIMEZONE
        ).astimezone(
            UTC
        )

    @staticmethod
    def _require_usd_row(
        root: ET.Element,
    ) -> ET.Element:
        matches = []

        for element in root.findall(
            "Exrate"
        ):
            currency_code = element.attrib.get(
                "CurrencyCode"
            )

            if currency_code == "USD":
                matches.append(
                    element
                )

        if len(
            matches
        ) != 1:
            raise RuntimeError(
                _USD_SCHEMA_ERROR
            )

        return matches[
            0
        ]

    @staticmethod
    def _parse_usd_sell(
        usd_row: ET.Element,
    ) -> Decimal:
        raw = usd_row.attrib.get(
            "Sell"
        )

        if not isinstance(
            raw,
            str,
        ):
            raise RuntimeError(
                _USD_SELL_ERROR
            )

        normalized = raw.strip()

        if not normalized:
            raise RuntimeError(
                _USD_SELL_ERROR
            )

        # Provider values are expected as plain decimal
        # numbers. Thousands separators or alternate
        # formatting are not guessed.
        try:
            value = Decimal(
                normalized
            )
        except (
            InvalidOperation,
            ValueError,
        ):
            raise RuntimeError(
                _USD_SELL_ERROR
            ) from None

        if (
            not value.is_finite()
            or value <= Decimal("0")
        ):
            raise RuntimeError(
                _USD_SELL_ERROR
            )

        return value
