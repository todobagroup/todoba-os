from __future__ import annotations

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceStatus,
    CustomerPaymentEvidenceStore,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationStatus,
    CustomerVndBankReconciliationStore,
)


class CustomerVndBankReconciliationVerificationAdapter:
    """
    Read-only adapter from authoritative VND bank reconciliation
    truth to PaymentVerificationAssertion.

    This owner does not reconcile, receive evidence, settle
    payment, or activate Setup.
    """

    def __init__(
        self,
        *,
        reconciliation_store: CustomerVndBankReconciliationStore,
        payment_evidence_store: CustomerPaymentEvidenceStore,
        payment_intent_store: CustomerPaymentIntentStore,
        order_store: CustomerCommercialOrderStore,
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
            payment_evidence_store,
            CustomerPaymentEvidenceStore,
        ):
            raise TypeError(
                "payment_evidence_store must be "
                "CustomerPaymentEvidenceStore."
            )

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

        self._reconciliation_store = reconciliation_store
        self._payment_evidence_store = payment_evidence_store
        self._payment_intent_store = payment_intent_store
        self._order_store = order_store

    def build_assertion(
        self,
        *,
        reconciliation_id: str,
    ) -> PaymentVerificationAssertion:
        normalized_reconciliation_id = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                reconciliation_id,
                name="reconciliation_id",
            )
        )

        self._require_sources_ready()

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

        intent = self._payment_intent_store.get(
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

        evidence = (
            self._payment_evidence_store
            .get_by_replay_identity(
                evidence_source=(
                    PaymentEvidenceSource.VND_BANK_TRANSFER
                ),
                external_evidence_id=(
                    reconciliation.bank_reference
                ),
            )
        )

        if evidence is None:
            raise ValueError(
                "VND bank payment evidence is not authoritative."
            )

        if (
            evidence.payment_intent_id
            != reconciliation.payment_intent_id
            or evidence.evidence_source
            is not PaymentEvidenceSource.VND_BANK_TRANSFER
            or evidence.external_evidence_id
            != reconciliation.bank_reference
            or evidence.status
            is not CustomerPaymentEvidenceStatus.RECEIVED
        ):
            raise ValueError(
                "VND bank payment evidence does not match "
                "authoritative reconciliation."
            )

        order = self._order_store.get(
            order_id=reconciliation.order_id
        )

        if order is None:
            raise ValueError(
                "Commercial order is not authoritative."
            )

        if (
            order.order_id != reconciliation.order_id
            or order.customer_id != reconciliation.customer_id
            or order.amount_minor != reconciliation.amount_minor
            or order.currency != reconciliation.currency
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "VND bank reconciliation does not match "
                "authoritative commercial order."
            )

        if (
            order.order_id != intent.order_id
            or reconciliation.currency != "VND"
        ):
            raise ValueError(
                "VND bank verification chain is inconsistent."
            )

        return PaymentVerificationAssertion(
            verification_assertion_id=(
                "vnd-bank-verification-"
                f"{reconciliation.reconciliation_id}"
            ),
            payment_evidence_id=evidence.payment_evidence_id,
            payment_intent_id=intent.payment_intent_id,
            order_id=order.order_id,
            customer_id=order.customer_id,
            amount_minor=order.amount_minor,
            currency=order.currency,
            evidence_source=(
                PaymentEvidenceSource.VND_BANK_TRANSFER
            ),
            external_evidence_id=(
                reconciliation.bank_reference
            ),
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._reconciliation_store.is_ready():
            raise RuntimeError(
                "VND bank reconciliation store "
                "is not initialized."
            )

        if not self._payment_evidence_store.is_ready():
            raise RuntimeError(
                "Payment evidence store is not initialized."
            )

        if not self._payment_intent_store.is_ready():
            raise RuntimeError(
                "Payment intent store is not initialized."
            )

        if not self._order_store.is_ready():
            raise RuntimeError(
                "Commercial order store is not initialized."
            )
