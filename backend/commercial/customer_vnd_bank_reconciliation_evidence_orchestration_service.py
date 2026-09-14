"""
TODOBA VND Bank Reconciliation Evidence Orchestration

Coordinates the already-authoritative VND bank reconciliation
boundary with trusted payment-evidence publication.

Authority boundary:

authenticated operator
    -> reconciliation_service.confirm(...)
    -> confirmed authoritative reconciliation
    -> evidence_publication_service.publish(...)
    -> trusted VND bank payment evidence

This owner deliberately does not:
- authenticate an operator
- receive HTTP input
- build PaymentVerificationAssertion
- settle payment
- activate Setup
- perform network access
- create or initialize durable stores
"""

from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceStatus,
    PaymentEvidenceSource,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationStatus,
)


class CustomerVndBankReconciliationEvidenceOrchestrationService:
    """
    Confirm authoritative VND reconciliation and publish its
    trusted normalized payment evidence.

    The underlying reconciliation and publication owners retain
    their own idempotency and persistence authority.
    """

    def __init__(
        self,
        *,
        reconciliation_service,
        evidence_publication_service,
    ) -> None:
        self._require_owner_method(
            reconciliation_service,
            owner_name="reconciliation_service",
            method_name="confirm",
        )

        self._require_owner_method(
            evidence_publication_service,
            owner_name="evidence_publication_service",
            method_name="publish",
        )

        self._reconciliation_service = reconciliation_service
        self._evidence_publication_service = evidence_publication_service

    def confirm(
        self,
        *,
        reconciliation_request_id: str,
        payment_intent_id: str,
        bank_reference: str,
        amount_minor: int,
        currency: str,
        operator_id: str,
    ) -> CustomerVndBankReconciliationRecord:
        reconciliation = self._reconciliation_service.confirm(
            reconciliation_request_id=reconciliation_request_id,
            payment_intent_id=payment_intent_id,
            bank_reference=bank_reference,
            amount_minor=amount_minor,
            currency=currency,
            operator_id=operator_id,
        )

        if not isinstance(
            reconciliation,
            CustomerVndBankReconciliationRecord,
        ):
            raise RuntimeError(
                "VND bank reconciliation service returned "
                "invalid reconciliation result."
            )

        if (
            reconciliation.status
            is not CustomerVndBankReconciliationStatus.CONFIRMED
        ):
            raise ValueError(
                "VND bank reconciliation must be confirmed "
                "before trusted evidence publication."
            )

        evidence = self._evidence_publication_service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

        self._require_evidence_convergence(
            reconciliation=reconciliation,
            evidence=evidence,
        )

        return reconciliation

    @staticmethod
    def _require_evidence_convergence(
        *,
        reconciliation: CustomerVndBankReconciliationRecord,
        evidence,
    ) -> None:
        if (
            getattr(
                evidence,
                "payment_intent_id",
                None,
            )
            != reconciliation.payment_intent_id
            or getattr(
                evidence,
                "evidence_source",
                None,
            )
            is not PaymentEvidenceSource.VND_BANK_TRANSFER
            or getattr(
                evidence,
                "external_evidence_id",
                None,
            )
            != reconciliation.bank_reference
            or getattr(
                evidence,
                "status",
                None,
            )
            is not CustomerPaymentEvidenceStatus.RECEIVED
        ):
            raise RuntimeError(
                "Published VND bank payment evidence did not "
                "converge to authoritative reconciliation."
            )

    @staticmethod
    def _require_owner_method(
        owner,
        *,
        owner_name: str,
        method_name: str,
    ) -> None:
        method = getattr(
            owner,
            method_name,
            None,
        )

        if not callable(method):
            raise TypeError(
                f"{owner_name} must expose callable "
                f"{method_name}()."
            )
