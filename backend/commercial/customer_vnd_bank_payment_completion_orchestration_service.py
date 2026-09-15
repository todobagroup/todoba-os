"""
TODOBA VND Bank Payment Completion Orchestration

Read-only verification handoff followed by the existing
authoritative payment settlement / Setup activation orchestration.

Flow:

    reconciliation_id
        -> verification_adapter.build_assertion(...)
        -> PaymentVerificationAssertion
        -> settlement_orchestration_service.complete_verified_payment(...)

This owner deliberately does not:
- authenticate an operator
- accept client payment authority fields
- publish payment evidence
- settle payment directly
- activate Setup directly
- perform HTTP/network access
- create or initialize durable stores
"""

from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)


class CustomerVndBankPaymentCompletionOrchestrationService:
    """
    Complete an already-confirmed VND bank payment through the
    existing verification and settlement-gated activation owners.
    """

    def __init__(
        self,
        *,
        verification_adapter,
        settlement_orchestration_service,
    ) -> None:
        self._require_owner_method(
            verification_adapter,
            owner_name="verification_adapter",
            method_name="build_assertion",
        )

        self._require_owner_method(
            settlement_orchestration_service,
            owner_name="settlement_orchestration_service",
            method_name="complete_verified_payment",
        )

        self._verification_adapter = verification_adapter
        self._settlement_orchestration_service = (
            settlement_orchestration_service
        )

    def complete(
        self,
        *,
        reconciliation_id: str,
    ):
        verification_assertion = (
            self._verification_adapter.build_assertion(
                reconciliation_id=reconciliation_id,
            )
        )

        if not isinstance(
            verification_assertion,
            PaymentVerificationAssertion,
        ):
            raise RuntimeError(
                "VND bank verification adapter returned "
                "invalid verification assertion."
            )

        return (
            self._settlement_orchestration_service
            .complete_verified_payment(
                verification_assertion=verification_assertion,
            )
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
