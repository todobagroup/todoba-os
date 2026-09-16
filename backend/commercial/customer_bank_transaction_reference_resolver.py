"""
TODOBA generic bank transaction reference resolver.

Resolves one canonical TODOBA transfer reference to its exact
authoritative payment intent, then delegates reconciliation to the
existing VND bank reconciliation authority.

This owner:
- does not scan payment-intent storage
- does not maintain reference mappings
- does not implement bank-specific parsing
- does not treat the transfer reference as payment authority
- does not own reconciliation, settlement, evidence, or activation
"""

from __future__ import annotations

from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_payment_transfer_reference_codec import (
    decode_payment_transfer_reference,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
)


class CustomerBankTransactionReferenceResolver:
    """
    Resolve a generic bank transaction memo to one exact authoritative
    payment intent and delegate confirmation to existing reconciliation.
    """

    def __init__(
        self,
        *,
        payment_intent_store: CustomerPaymentIntentStore,
        reconciliation_service,
    ) -> None:
        if not isinstance(
            payment_intent_store,
            CustomerPaymentIntentStore,
        ):
            raise TypeError(
                "payment_intent_store must be "
                "CustomerPaymentIntentStore."
            )

        confirm = getattr(
            reconciliation_service,
            "confirm",
            None,
        )

        if not callable(confirm):
            raise TypeError(
                "reconciliation_service must expose callable confirm()."
            )

        if not payment_intent_store.is_ready():
            raise RuntimeError(
                "Customer payment intent store is not initialized."
            )

        self._payment_intent_store = payment_intent_store
        self._reconciliation_service = reconciliation_service

    def resolve_and_reconcile(
        self,
        *,
        transfer_reference: str,
        reconciliation_request_id: str,
        bank_reference: str,
        amount_minor: int,
        currency: str,
        operator_id: str,
    ) -> CustomerVndBankReconciliationRecord:
        payment_intent_id = decode_payment_transfer_reference(
            transfer_reference=transfer_reference
        )

        intent = self._payment_intent_store.get(
            payment_intent_id=payment_intent_id
        )

        if intent is None:
            raise ValueError(
                "Payment intent is not authoritative."
            )

        if (
            intent.payment_intent_id != payment_intent_id
            or intent.payment_rail
            is not PaymentRail.VND_BANK_TRANSFER
            or intent.status
            is not CustomerPaymentIntentStatus.PENDING
        ):
            raise ValueError(
                "Payment intent is not eligible for "
                "VND bank reconciliation."
            )

        return self._reconciliation_service.confirm(
            reconciliation_request_id=(
                reconciliation_request_id
            ),
            payment_intent_id=payment_intent_id,
            bank_reference=bank_reference,
            amount_minor=amount_minor,
            currency=currency,
            operator_id=operator_id,
        )
