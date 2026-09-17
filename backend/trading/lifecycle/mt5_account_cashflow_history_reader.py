"""
TODOBA Authoritative MT5 Account Cashflow Evidence Reader.

Reads account-level non-trading cashflow evidence from
MetaTrader 5 deal history.

This owner preserves broker evidence only.

It does NOT classify evidence as:
- customer external deposit
- customer external withdrawal
- commercial funding
- licensed-cap excess
- grace eligible
- upgrade required

Those are downstream commercial responsibilities.

Trading BUY / SELL deals and canceled trade deals are excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from typing import Literal

import MetaTrader5 as mt5


MT5AccountCashflowKind = Literal[
    "balance",
    "credit",
    "charge",
    "correction",
    "bonus",
    "commission",
    "commission_daily",
    "commission_monthly",
    "commission_agent_daily",
    "commission_agent_monthly",
    "interest",
]


@dataclass(
    frozen=True,
)
class MT5AccountCashflowEvidence:
    """
    Immutable normalized evidence for one MT5 account-level deal.
    """

    deal_ticket: int
    deal_time_msc: int

    observed_at: datetime

    cashflow_kind: MT5AccountCashflowKind
    raw_deal_type: int

    amount: Decimal

    # Raw broker attribution context.
    #
    # These fields preserve MT5 evidence only.
    # They do not classify customer funding.
    order_ticket: int = 0
    deal_entry: int = 0
    magic: int = 0
    position_id: int = 0
    deal_reason: int = 0
    volume: float = 0.0
    price: float = 0.0
    symbol: str = ""
    external_id: str = ""

    comment: str = ""

    def __post_init__(
        self,
    ) -> None:
        if (
            isinstance(
                self.deal_ticket,
                bool,
            )
            or not isinstance(
                self.deal_ticket,
                int,
            )
            or self.deal_ticket <= 0
        ):
            raise ValueError(
                "deal_ticket must be a positive int."
            )

        if (
            isinstance(
                self.deal_time_msc,
                bool,
            )
            or not isinstance(
                self.deal_time_msc,
                int,
            )
            or self.deal_time_msc < 0
        ):
            raise ValueError(
                "deal_time_msc must be a non-negative int."
            )

        if not isinstance(
            self.observed_at,
            datetime,
        ):
            raise TypeError(
                "observed_at must be datetime."
            )

        if (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError(
                "observed_at must be timezone-aware."
            )

        object.__setattr__(
            self,
            "observed_at",
            self.observed_at.astimezone(
                UTC
            ),
        )

        allowed_kinds = {
            "balance",
            "credit",
            "charge",
            "correction",
            "bonus",
            "commission",
            "commission_daily",
            "commission_monthly",
            "commission_agent_daily",
            "commission_agent_monthly",
            "interest",
        }

        if self.cashflow_kind not in allowed_kinds:
            raise ValueError(
                "Unsupported cashflow_kind."
            )

        if (
            isinstance(
                self.raw_deal_type,
                bool,
            )
            or not isinstance(
                self.raw_deal_type,
                int,
            )
        ):
            raise TypeError(
                "raw_deal_type must be int."
            )

        if not isinstance(
            self.amount,
            Decimal,
        ):
            raise TypeError(
                "amount must be Decimal."
            )

        if not self.amount.is_finite():
            raise ValueError(
                "amount must be finite."
            )

        if not isinstance(
            self.comment,
            str,
        ):
            raise TypeError(
                "comment must be str."
            )


class MT5AccountCashflowHistoryReader:
    """
    Read authoritative non-trading account cashflow deals from MT5.
    """

    def __init__(
        self,
        mt5_module=mt5,
    ) -> None:
        self.mt5 = mt5_module

    def read(
        self,
        *,
        observed_from: datetime,
        observed_to: datetime,
    ) -> tuple[
        MT5AccountCashflowEvidence,
        ...,
    ]:
        normalized_from = self._normalize_datetime(
            observed_from,
            name="observed_from",
        )

        normalized_to = self._normalize_datetime(
            observed_to,
            name="observed_to",
        )

        if normalized_to <= normalized_from:
            raise ValueError(
                "observed_to must be later than observed_from."
            )

        deals = self.mt5.history_deals_get(
            normalized_from,
            normalized_to,
        )

        if deals is None:
            raise RuntimeError(
                "MT5 history_deals_get failed: "
                f"{self._read_last_error()}"
            )

        kind_by_type = self._kind_by_deal_type()

        evidence = []

        for deal in deals:
            deal_type = getattr(
                deal,
                "type",
                None,
            )

            cashflow_kind = kind_by_type.get(
                deal_type
            )

            if cashflow_kind is None:
                continue

            evidence.append(
                MT5AccountCashflowEvidence(
                    deal_ticket=self._required_positive_int(
                        getattr(
                            deal,
                            "ticket",
                            None,
                        ),
                        name="deal ticket",
                    ),
                    deal_time_msc=self._non_negative_int(
                        getattr(
                            deal,
                            "time_msc",
                            0,
                        ),
                        name="deal time_msc",
                    ),
                    observed_at=self._timestamp_to_utc(
                        getattr(
                            deal,
                            "time",
                            None,
                        )
                    ),
                    cashflow_kind=cashflow_kind,
                    raw_deal_type=self._required_int(
                        deal_type,
                        name="deal type",
                    ),
                    amount=self._exact_decimal(
                        getattr(
                            deal,
                            "profit",
                            None,
                        )
                    ),
                    order_ticket=self._non_negative_int(
                        getattr(
                            deal,
                            "order",
                            0,
                        ),
                        name="deal order",
                    ),
                    deal_entry=self._non_negative_int(
                        getattr(
                            deal,
                            "entry",
                            0,
                        ),
                        name="deal entry",
                    ),
                    magic=self._non_negative_int(
                        getattr(
                            deal,
                            "magic",
                            0,
                        ),
                        name="deal magic",
                    ),
                    position_id=self._non_negative_int(
                        getattr(
                            deal,
                            "position_id",
                            0,
                        ),
                        name="deal position_id",
                    ),
                    deal_reason=self._non_negative_int(
                        getattr(
                            deal,
                            "reason",
                            0,
                        ),
                        name="deal reason",
                    ),
                    volume=self._finite_float(
                        getattr(
                            deal,
                            "volume",
                            0.0,
                        ),
                        name="deal volume",
                    ),
                    price=self._finite_float(
                        getattr(
                            deal,
                            "price",
                            0.0,
                        ),
                        name="deal price",
                    ),
                    symbol=str(
                        getattr(
                            deal,
                            "symbol",
                            "",
                        )
                    ),
                    external_id=str(
                        getattr(
                            deal,
                            "external_id",
                            "",
                        )
                    ),
                    comment=str(
                        getattr(
                            deal,
                            "comment",
                            "",
                        )
                    ),
                )
            )

        evidence.sort(
            key=lambda item: (
                item.deal_time_msc,
                item.observed_at,
                item.deal_ticket,
            )
        )

        return tuple(
            evidence
        )

    def _kind_by_deal_type(
        self,
    ) -> dict[
        int,
        MT5AccountCashflowKind,
    ]:
        return {
            self.mt5.DEAL_TYPE_BALANCE: "balance",
            self.mt5.DEAL_TYPE_CREDIT: "credit",
            self.mt5.DEAL_TYPE_CHARGE: "charge",
            self.mt5.DEAL_TYPE_CORRECTION: "correction",
            self.mt5.DEAL_TYPE_BONUS: "bonus",
            self.mt5.DEAL_TYPE_COMMISSION: "commission",
            self.mt5.DEAL_TYPE_COMMISSION_DAILY: (
                "commission_daily"
            ),
            self.mt5.DEAL_TYPE_COMMISSION_MONTHLY: (
                "commission_monthly"
            ),
            self.mt5.DEAL_TYPE_COMMISSION_AGENT_DAILY: (
                "commission_agent_daily"
            ),
            self.mt5.DEAL_TYPE_COMMISSION_AGENT_MONTHLY: (
                "commission_agent_monthly"
            ),
            self.mt5.DEAL_TYPE_INTEREST: "interest",
        }

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

    @staticmethod
    def _required_positive_int(
        value,
        *,
        name: str,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise TypeError(
                f"{name} must be int."
            )

        if value <= 0:
            raise ValueError(
                f"{name} must be positive."
            )

        return value

    @staticmethod
    def _non_negative_int(
        value,
        *,
        name: str,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise TypeError(
                f"{name} must be int."
            )

        if value < 0:
            raise ValueError(
                f"{name} must be non-negative."
            )

        return value

    @staticmethod
    def _required_int(
        value,
        *,
        name: str,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise TypeError(
                f"{name} must be int."
            )

        return value

    @staticmethod
    def _finite_float(
        value,
        *,
        name: str,
    ) -> float:
        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"{name} must be numeric."
            )

        if not isinstance(
            value,
            (
                int,
                float,
                Decimal,
            ),
        ):
            raise TypeError(
                f"{name} must be numeric."
            )

        normalized = float(
            value
        )

        if not Decimal(
            str(
                normalized
            )
        ).is_finite():
            raise ValueError(
                f"{name} must be finite."
            )

        return normalized

    @staticmethod
    def _timestamp_to_utc(
        value,
    ) -> datetime:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise TypeError(
                "deal time must be int."
            )

        if value < 0:
            raise ValueError(
                "deal time must be non-negative."
            )

        return datetime.fromtimestamp(
            value,
            tz=UTC,
        )

    @staticmethod
    def _exact_decimal(
        value,
    ) -> Decimal:
        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                "deal amount must be numeric."
            )

        if not isinstance(
            value,
            (
                int,
                float,
                Decimal,
            ),
        ):
            raise TypeError(
                "deal amount must be numeric."
            )

        decimal_value = Decimal(
            str(
                value
            )
        )

        if not decimal_value.is_finite():
            raise ValueError(
                "deal amount must be finite."
            )

        return decimal_value

    def _read_last_error(
        self,
    ):
        last_error = getattr(
            self.mt5,
            "last_error",
            None,
        )

        if callable(
            last_error
        ):
            return last_error()

        return "unknown"
