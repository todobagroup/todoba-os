from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)


_PAYMENT_TRANSFER_REFERENCE_PREFIX = "TODOBA SOFTWARE"
_PAYMENT_TRANSFER_REFERENCE_TOKEN_LENGTH = 16


def _build_payment_transfer_reference(
    *,
    payment_intent_id: str,
) -> str:
    if not isinstance(payment_intent_id, str):
        raise TypeError(
            "payment_intent_id must be str."
        )

    normalized_payment_intent_id = (
        payment_intent_id.strip()
    )

    if not normalized_payment_intent_id:
        raise ValueError(
            "payment_intent_id is required."
        )

    digest = hashlib.sha256(
        normalized_payment_intent_id.encode("utf-8")
    ).digest()

    token = base64.b32encode(
        digest
    ).decode("ascii")[
        :_PAYMENT_TRANSFER_REFERENCE_TOKEN_LENGTH
    ]

    return (
        f"{_PAYMENT_TRANSFER_REFERENCE_PREFIX} "
        f"{token}"
    )


@dataclass(frozen=True)
class CustomerVndBankPaymentDestination:
    bank_code: str
    account_number: str
    account_name: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.bank_code,
            str,
        ):
            raise TypeError(
                "bank_code must be str."
            )

        if not isinstance(
            self.account_number,
            str,
        ):
            raise TypeError(
                "account_number must be str."
            )

        if not isinstance(
            self.account_name,
            str,
        ):
            raise TypeError(
                "account_name must be str."
            )

        bank_code = self.bank_code.strip()
        account_number = self.account_number.strip()
        account_name = self.account_name.strip()

        if not bank_code:
            raise ValueError(
                "bank_code is required."
            )

        if not account_number:
            raise ValueError(
                "account_number is required."
            )

        if not account_name:
            raise ValueError(
                "account_name is required."
            )

        object.__setattr__(
            self,
            "bank_code",
            bank_code,
        )
        object.__setattr__(
            self,
            "account_number",
            account_number,
        )
        object.__setattr__(
            self,
            "account_name",
            account_name,
        )


@dataclass(frozen=True)
class CustomerVndBankPaymentInstructionResult:
    payment_intent_id: str
    order_id: str
    amount_minor: int
    currency: str
    payment_rail: PaymentRail
    bank_code: str
    account_number: str
    account_name: str
    transfer_reference: str


class CustomerVndBankPaymentInstructionService:
    def __init__(
        self,
        *,
        payment_intent_store: CustomerPaymentIntentStore,
        order_store: CustomerCommercialOrderStore,
        destination: CustomerVndBankPaymentDestination,
    ) -> None:
        if not isinstance(
            payment_intent_store,
            CustomerPaymentIntentStore,
        ):
            raise TypeError(
                "payment_intent_store must be "
                "CustomerPaymentIntentStore."
            )

        if not isinstance(
            order_store,
            CustomerCommercialOrderStore,
        ):
            raise TypeError(
                "order_store must be "
                "CustomerCommercialOrderStore."
            )

        if not isinstance(
            destination,
            CustomerVndBankPaymentDestination,
        ):
            raise TypeError(
                "destination must be "
                "CustomerVndBankPaymentDestination."
            )

        self._payment_intent_store = (
            payment_intent_store
        )
        self._order_store = order_store
        self._destination = destination

    def build(
        self,
        *,
        payment_intent_id: str,
    ) -> CustomerVndBankPaymentInstructionResult:
        if not isinstance(
            payment_intent_id,
            str,
        ):
            raise TypeError(
                "payment_intent_id must be str."
            )

        normalized_payment_intent_id = (
            payment_intent_id.strip()
        )

        if not normalized_payment_intent_id:
            raise ValueError(
                "payment_intent_id is required."
            )

        payment_intent = (
            self._payment_intent_store.get(
                payment_intent_id=(
                    normalized_payment_intent_id
                )
            )
        )

        if payment_intent is None:
            raise ValueError(
                "Payment intent does not exist."
            )

        if (
            payment_intent.payment_intent_id
            != normalized_payment_intent_id
        ):
            raise RuntimeError(
                "Payment intent identity mismatch."
            )

        if (
            payment_intent.status
            is not CustomerPaymentIntentStatus.PENDING
        ):
            raise ValueError(
                "Payment intent is not pending."
            )

        if (
            payment_intent.payment_rail
            is not PaymentRail.VND_BANK_TRANSFER
        ):
            raise ValueError(
                "Payment intent is not VND bank transfer."
            )

        order = self._order_store.get(
            order_id=payment_intent.order_id
        )

        if order is None:
            raise RuntimeError(
                "Authoritative commercial order does not exist."
            )

        if (
            order.order_id
            != payment_intent.order_id
        ):
            raise RuntimeError(
                "Payment intent/order identity mismatch."
            )

        if (
            order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "Commercial order is not pending."
            )

        if order.currency != "VND":
            raise ValueError(
                "Commercial order currency must be VND."
            )

        if (
            not isinstance(
                order.amount_minor,
                int,
            )
            or isinstance(
                order.amount_minor,
                bool,
            )
            or order.amount_minor <= 0
        ):
            raise RuntimeError(
                "Commercial order amount is invalid."
            )

        return CustomerVndBankPaymentInstructionResult(
            payment_intent_id=(
                payment_intent.payment_intent_id
            ),
            order_id=order.order_id,
            amount_minor=order.amount_minor,
            currency=order.currency,
            payment_rail=(
                payment_intent.payment_rail
            ),
            bank_code=(
                self._destination.bank_code
            ),
            account_number=(
                self._destination.account_number
            ),
            account_name=(
                self._destination.account_name
            ),
            transfer_reference=(
                _build_payment_transfer_reference(
                    payment_intent_id=(
                        payment_intent.payment_intent_id
                    )
                )
            ),
        )
