from __future__ import annotations

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
    CustomerCommercialOrderStatus,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceRecord,
    CustomerPaymentEvidenceService,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStatus,
    PaymentRail,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationStatus,
    CustomerVndBankReconciliationStore,
)


class CustomerVndBankEvidencePublicationService:
    """
    Publish trusted VND bank reconciliation truth into the
    normalized payment evidence boundary.

    This owner does not reconcile payments, settle payments,
    activate Setup, authenticate operators, or call networks.
    """

    def __init__(
        self,
        *,
        reconciliation_store: CustomerVndBankReconciliationStore,
        payment_evidence_service: CustomerPaymentEvidenceService,
        payment_intent_service: CustomerPaymentIntentService,
        order_service: CustomerCommercialOrderService,
    ) -> None:
        if not isinstance(
            reconciliation_store,
            CustomerVndBankReconciliationStore,
        ):
            raise TypeError(
                "reconciliation_store must be "
                "CustomerVndBankReconciliationStore."
            )

        if not isinstance(
            payment_evidence_service,
            CustomerPaymentEvidenceService,
        ):
            raise TypeError(
                "payment_evidence_service must be "
                "CustomerPaymentEvidenceService."
            )

        if not isinstance(
            payment_intent_service,
            CustomerPaymentIntentService,
        ):
            raise TypeError(
                "payment_intent_service must be "
                "CustomerPaymentIntentService."
            )

        if not isinstance(
            order_service,
            CustomerCommercialOrderService,
        ):
            raise TypeError(
                "order_service must be "
                "CustomerCommercialOrderService."
            )

        if not reconciliation_store.is_ready():
            raise RuntimeError(
                "VND bank reconciliation store "
                "is not initialized."
            )

        self._reconciliation_store = reconciliation_store
        self._payment_evidence_service = payment_evidence_service
        self._payment_intent_service = payment_intent_service
        self._order_service = order_service

    def publish(
        self,
        *,
        reconciliation_id: str,
    ) -> CustomerPaymentEvidenceRecord:
        normalized_reconciliation_id = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                reconciliation_id,
                name="reconciliation_id",
            )
        )

        reconciliation = self._reconciliation_store.get(
            reconciliation_id=normalized_reconciliation_id
        )

        if reconciliation is None:
            raise ValueError(
                "VND bank reconciliation is not authoritative."
            )

        if (
            reconciliation.reconciliation_id
            != normalized_reconciliation_id
            or reconciliation.status
            is not CustomerVndBankReconciliationStatus.CONFIRMED
        ):
            raise ValueError(
                "VND bank reconciliation is not confirmed "
                "authoritative truth."
            )

        intent = self._payment_intent_service.get(
            payment_intent_id=(
                reconciliation.payment_intent_id
            )
        )

        if intent is None:
            raise ValueError(
                "Payment intent is not authoritative."
            )

        if (
            intent.payment_intent_id
            != reconciliation.payment_intent_id
            or intent.order_id
            != reconciliation.order_id
            or intent.payment_rail
            is not PaymentRail.VND_BANK_TRANSFER
            or intent.status
            is not CustomerPaymentIntentStatus.PENDING
        ):
            raise ValueError(
                "VND bank reconciliation does not match "
                "authoritative payment intent."
            )

        order = self._order_service.get(
            order_id=reconciliation.order_id
        )

        if order is None:
            raise ValueError(
                "Commercial order is not authoritative."
            )

        if (
            order.order_id
            != reconciliation.order_id
            or order.order_id
            != intent.order_id
            or order.customer_id
            != reconciliation.customer_id
            or order.amount_minor
            != reconciliation.amount_minor
            or order.currency
            != reconciliation.currency
            or order.currency
            != "VND"
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "VND bank reconciliation does not match "
                "authoritative commercial order."
            )

        return self._payment_evidence_service.receive(
            evidence_request_id=(
                "vnd-bank-evidence-"
                f"{reconciliation.reconciliation_id}"
            ),
            authorized_payment_intent=intent,
            evidence_source=(
                PaymentEvidenceSource.VND_BANK_TRANSFER
            ),
            external_evidence_id=(
                reconciliation.bank_reference
            ),
        )
