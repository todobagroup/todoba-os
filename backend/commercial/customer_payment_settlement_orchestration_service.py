from __future__ import annotations

from backend.commercial.customer_payment_settlement_activation_bridge import (
    CustomerPaymentSettlementActivationBridge,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementService,
    CustomerPaymentSettlementStatus,
    PaymentVerificationAssertion,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
)


class CustomerPaymentSettlementOrchestrationService:
    """
    Complete one already-verified payment through the existing
    settlement authority and settlement-gated activation bridge.

    Input authority:
        verification_assertion only

    This owner does not:
    - receive or publish payment evidence
    - verify provider-specific payment truth
    - accept caller-supplied customer/order/amount facts
    - reconcile bank transfers
    - handle PayPal webhooks or captures
    - perform network access
    - activate Setup except through the settlement-gated bridge
    """

    def __init__(
        self,
        *,
        settlement_service: CustomerPaymentSettlementService,
        activation_bridge: CustomerPaymentSettlementActivationBridge,
    ) -> None:
        if not isinstance(
            settlement_service,
            CustomerPaymentSettlementService,
        ):
            raise TypeError(
                "settlement_service must be "
                "CustomerPaymentSettlementService."
            )

        if not isinstance(
            activation_bridge,
            CustomerPaymentSettlementActivationBridge,
        ):
            raise TypeError(
                "activation_bridge must be "
                "CustomerPaymentSettlementActivationBridge."
            )

        self._settlement_service = settlement_service
        self._activation_bridge = activation_bridge

    def complete_verified_payment(
        self,
        *,
        verification_assertion: PaymentVerificationAssertion,
    ) -> CustomerSetupActivationResult:
        if not isinstance(
            verification_assertion,
            PaymentVerificationAssertion,
        ):
            raise TypeError(
                "verification_assertion must be "
                "PaymentVerificationAssertion."
            )

        settlement = self._settlement_service.settle(
            verification_assertion=verification_assertion,
        )

        if (
            settlement.status
            is not CustomerPaymentSettlementStatus.SETTLED
        ):
            raise ValueError(
                "Payment orchestration requires "
                "authoritative settled payment truth."
            )

        return self._activation_bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )