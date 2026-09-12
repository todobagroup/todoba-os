import inspect

import pytest

from backend.commercial.customer_payment_settlement_activation_bridge import (
    CustomerPaymentSettlementActivationBridge,
)
from backend.commercial.customer_payment_settlement_orchestration_service import (
    CustomerPaymentSettlementOrchestrationService,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementRecord,
    CustomerPaymentSettlementService,
    CustomerPaymentSettlementStatus,
    PaymentVerificationAssertion,
)
from backend.commercial.customer_payment_evidence_service import (
    PaymentEvidenceSource,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
    CustomerSetupActivationStatus,
)


class _FakeSettlementService(
    CustomerPaymentSettlementService
):
    def __init__(self) -> None:
        self.calls = []

    def settle(
        self,
        *,
        verification_assertion,
    ):
        self.calls.append(verification_assertion)

        return CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                verification_assertion
                .verification_assertion_id
            ),
            settlement_id="payment-settlement-001",
            payment_evidence_id=(
                verification_assertion
                .payment_evidence_id
            ),
            payment_intent_id=(
                verification_assertion
                .payment_intent_id
            ),
            order_id=verification_assertion.order_id,
            customer_id=verification_assertion.customer_id,
            amount_minor=verification_assertion.amount_minor,
            currency=verification_assertion.currency,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )


class _FakeActivationBridge(
    CustomerPaymentSettlementActivationBridge
):
    def __init__(self) -> None:
        self.calls = []

    def activate_from_settlement(
        self,
        *,
        settlement_id,
    ):
        self.calls.append(settlement_id)

        return CustomerSetupActivationResult(
            activation_request_id=(
                "payment-settlement-activation-"
                f"{settlement_id}"
            ),
            setup_activation_id="setup-activation-001",
            customer_id="customer-001",
            status=CustomerSetupActivationStatus.ACTIVE,
        )


def _assertion():
    return PaymentVerificationAssertion(
        verification_assertion_id="verification-001",
        payment_evidence_id="evidence-001",
        payment_intent_id="payment-intent-001",
        order_id="order-001",
        customer_id="customer-001",
        amount_minor=2500000,
        currency="VND",
        evidence_source=(
            PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
        external_evidence_id="VCB-20260912-000001",
    )


def _build():
    settlement_service = _FakeSettlementService()
    activation_bridge = _FakeActivationBridge()

    service = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=settlement_service,
            activation_bridge=activation_bridge,
        )
    )

    return (
        service,
        settlement_service,
        activation_bridge,
    )


def test_verified_assertion_settles_then_activates():
    (
        service,
        settlement_service,
        activation_bridge,
    ) = _build()

    assertion = _assertion()

    result = service.complete_verified_payment(
        verification_assertion=assertion,
    )

    assert settlement_service.calls == [assertion]

    assert activation_bridge.calls == [
        "payment-settlement-001"
    ]

    assert result.activation_request_id == (
        "payment-settlement-activation-"
        "payment-settlement-001"
    )

    assert result.customer_id == "customer-001"

    assert (
        result.status
        is CustomerSetupActivationStatus.ACTIVE
    )


def test_activation_uses_only_returned_settlement_identity():
    (
        service,
        _,
        activation_bridge,
    ) = _build()

    service.complete_verified_payment(
        verification_assertion=_assertion(),
    )

    assert activation_bridge.calls == [
        "payment-settlement-001"
    ]


def test_retry_reuses_authoritative_downstream_owners():
    (
        service,
        settlement_service,
        activation_bridge,
    ) = _build()

    assertion = _assertion()

    first = service.complete_verified_payment(
        verification_assertion=assertion,
    )

    second = service.complete_verified_payment(
        verification_assertion=assertion,
    )

    assert second == first

    assert settlement_service.calls == [
        assertion,
        assertion,
    ]

    assert activation_bridge.calls == [
        "payment-settlement-001",
        "payment-settlement-001",
    ]


def test_constructor_requires_settlement_service():
    with pytest.raises(TypeError):
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=object(),
            activation_bridge=_FakeActivationBridge(),
        )


def test_constructor_requires_activation_bridge():
    with pytest.raises(TypeError):
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=_FakeSettlementService(),
            activation_bridge=object(),
        )


def test_public_surface_accepts_only_verification_assertion():
    signature = inspect.signature(
        CustomerPaymentSettlementOrchestrationService
        .complete_verified_payment
    )

    assert tuple(signature.parameters) == (
        "self",
        "verification_assertion",
    )


def test_orchestrator_exposes_no_provider_or_evidence_authority():
    forbidden_methods = (
        "receive",
        "receive_evidence",
        "publish",
        "build_assertion",
        "verify_webhook",
        "capture",
        "confirm",
        "reconcile",
        "activate",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            CustomerPaymentSettlementOrchestrationService,
            method_name,
        )


def test_orchestrator_source_has_no_network_or_provider_boundary():
    executable_source = (
        inspect.getsource(
            CustomerPaymentSettlementOrchestrationService.__init__
        )
        + inspect.getsource(
            CustomerPaymentSettlementOrchestrationService
            .complete_verified_payment
        )
    )

    forbidden_tokens = (
        "requests.",
        "httpx.",
        "paypal",
        "webhook",
        "bank_reference",
        "operator_id",
        "screenshot",
        "receipt",
        "customer_id=",
        "order_id=",
        "amount_minor=",
    )

    for token in forbidden_tokens:
        assert token not in executable_source


class _FailingSettlementService(
    CustomerPaymentSettlementService
):
    def __init__(self) -> None:
        self.calls = []

    def settle(
        self,
        *,
        verification_assertion,
    ):
        self.calls.append(verification_assertion)
        raise ValueError("settlement failed")


class _FailingActivationBridge(
    CustomerPaymentSettlementActivationBridge
):
    def __init__(self) -> None:
        self.calls = []

    def activate_from_settlement(
        self,
        *,
        settlement_id,
    ):
        self.calls.append(settlement_id)
        raise ValueError("activation failed")


class _NonSettledService(
    CustomerPaymentSettlementService
):
    def __init__(self) -> None:
        self.calls = []

    def settle(
        self,
        *,
        verification_assertion,
    ):
        self.calls.append(verification_assertion)

        record = CustomerPaymentSettlementRecord(
            verification_assertion_id=(
                verification_assertion
                .verification_assertion_id
            ),
            settlement_id="payment-settlement-pending",
            payment_evidence_id=(
                verification_assertion
                .payment_evidence_id
            ),
            payment_intent_id=(
                verification_assertion
                .payment_intent_id
            ),
            order_id=verification_assertion.order_id,
            customer_id=verification_assertion.customer_id,
            amount_minor=verification_assertion.amount_minor,
            currency=verification_assertion.currency,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )

        object.__setattr__(
            record,
            "status",
            "PENDING",
        )

        return record


def test_settlement_failure_prevents_activation():
    settlement_service = _FailingSettlementService()
    activation_bridge = _FakeActivationBridge()

    service = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=settlement_service,
            activation_bridge=activation_bridge,
        )
    )

    assertion = _assertion()

    with pytest.raises(
        ValueError,
        match="settlement failed",
    ):
        service.complete_verified_payment(
            verification_assertion=assertion,
        )

    assert settlement_service.calls == [assertion]
    assert activation_bridge.calls == []


def test_wrong_assertion_type_fails_before_downstream_calls():
    (
        service,
        settlement_service,
        activation_bridge,
    ) = _build()

    with pytest.raises(TypeError):
        service.complete_verified_payment(
            verification_assertion=object(),
        )

    assert settlement_service.calls == []
    assert activation_bridge.calls == []


def test_activation_failure_is_propagated_after_settlement():
    settlement_service = _FakeSettlementService()
    activation_bridge = _FailingActivationBridge()

    service = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=settlement_service,
            activation_bridge=activation_bridge,
        )
    )

    assertion = _assertion()

    with pytest.raises(
        ValueError,
        match="activation failed",
    ):
        service.complete_verified_payment(
            verification_assertion=assertion,
        )

    assert settlement_service.calls == [assertion]
    assert activation_bridge.calls == [
        "payment-settlement-001"
    ]


def test_orchestration_order_is_settle_then_activate():
    events = []

    class OrderedSettlementService(
        CustomerPaymentSettlementService
    ):
        def __init__(self) -> None:
            pass

        def settle(
            self,
            *,
            verification_assertion,
        ):
            events.append("settle")

            return CustomerPaymentSettlementRecord(
                verification_assertion_id=(
                    verification_assertion
                    .verification_assertion_id
                ),
                settlement_id="payment-settlement-ordered",
                payment_evidence_id=(
                    verification_assertion
                    .payment_evidence_id
                ),
                payment_intent_id=(
                    verification_assertion
                    .payment_intent_id
                ),
                order_id=verification_assertion.order_id,
                customer_id=verification_assertion.customer_id,
                amount_minor=verification_assertion.amount_minor,
                currency=verification_assertion.currency,
                status=(
                    CustomerPaymentSettlementStatus.SETTLED
                ),
            )

    class OrderedActivationBridge(
        CustomerPaymentSettlementActivationBridge
    ):
        def __init__(self) -> None:
            pass

        def activate_from_settlement(
            self,
            *,
            settlement_id,
        ):
            events.append("activate")

            return CustomerSetupActivationResult(
                activation_request_id=(
                    "payment-settlement-activation-"
                    f"{settlement_id}"
                ),
                setup_activation_id="setup-activation-ordered",
                customer_id="customer-001",
                status=(
                    CustomerSetupActivationStatus.ACTIVE
                ),
            )

    service = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=OrderedSettlementService(),
            activation_bridge=OrderedActivationBridge(),
        )
    )

    service.complete_verified_payment(
        verification_assertion=_assertion(),
    )

    assert events == [
        "settle",
        "activate",
    ]


def test_non_settled_result_never_reaches_activation():
    settlement_service = _NonSettledService()
    activation_bridge = _FakeActivationBridge()

    service = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=settlement_service,
            activation_bridge=activation_bridge,
        )
    )

    with pytest.raises(
        ValueError,
        match="settled",
    ):
        service.complete_verified_payment(
            verification_assertion=_assertion(),
        )

    assert activation_bridge.calls == []