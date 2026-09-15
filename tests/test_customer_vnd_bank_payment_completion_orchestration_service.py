import inspect

import pytest

from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)


RECONCILIATION_ID = "vnd-bank-reconciliation-001"


def _assertion():
    return PaymentVerificationAssertion(
        verification_assertion_id=(
            "vnd-bank-verification-"
            f"{RECONCILIATION_ID}"
        ),
        payment_evidence_id="payment-evidence-001",
        payment_intent_id="payment-intent-001",
        order_id="order-001",
        customer_id="customer-001",
        amount_minor=2500000,
        currency="VND",
        evidence_source=(
            __import__(
                "backend.commercial.customer_payment_evidence_service",
                fromlist=["PaymentEvidenceSource"],
            ).PaymentEvidenceSource.VND_BANK_TRANSFER
        ),
        external_evidence_id="VCB-20260914-000001",
    )


class _VerificationAdapter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def build_assertion(
        self,
        *,
        reconciliation_id: str,
    ):
        self.calls.append(
            reconciliation_id
        )
        return self.result


class _SettlementOrchestration:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def complete_verified_payment(
        self,
        *,
        verification_assertion,
    ):
        self.calls.append(
            verification_assertion
        )
        return self.result


def _service(
    *,
    assertion=None,
    completion_result=None,
):
    from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    assertion = assertion or _assertion()

    verification_adapter = _VerificationAdapter(
        assertion
    )

    settlement_orchestration = _SettlementOrchestration(
        completion_result
    )

    service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=verification_adapter,
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    return (
        service,
        verification_adapter,
        settlement_orchestration,
        assertion,
    )


def test_reconciliation_builds_assertion_then_completes_verified_payment():
    completion_result = object()

    (
        service,
        verification_adapter,
        settlement_orchestration,
        assertion,
    ) = _service(
        completion_result=completion_result,
    )

    result = service.complete(
        reconciliation_id=RECONCILIATION_ID,
    )

    assert result is completion_result

    assert verification_adapter.calls == [
        RECONCILIATION_ID
    ]

    assert settlement_orchestration.calls == [
        assertion
    ]


def test_invalid_verification_result_never_reaches_settlement():
    (
        service,
        verification_adapter,
        settlement_orchestration,
        _,
    ) = _service(
        assertion=object(),
    )

    with pytest.raises(
        RuntimeError,
        match="verification assertion",
    ):
        service.complete(
            reconciliation_id=RECONCILIATION_ID,
        )

    assert verification_adapter.calls == [
        RECONCILIATION_ID
    ]

    assert settlement_orchestration.calls == []


def test_reconciliation_id_is_the_only_completion_input():
    from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    signature = inspect.signature(
        CustomerVndBankPaymentCompletionOrchestrationService.complete
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "reconciliation_id",
    )

    assert (
        signature.parameters[
            "reconciliation_id"
        ].kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_constructor_requires_build_assertion_owner():
    from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    with pytest.raises(TypeError):
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=object(),
            settlement_orchestration_service=(
                _SettlementOrchestration(
                    object()
                )
            ),
        )


def test_constructor_requires_verified_payment_completion_owner():
    from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    with pytest.raises(TypeError):
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=(
                _VerificationAdapter(
                    _assertion()
                )
            ),
            settlement_orchestration_service=object(),
        )


def test_owner_has_no_direct_settlement_activation_http_or_store_authority():
    from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    source = inspect.getsource(
        CustomerVndBankPaymentCompletionOrchestrationService
    )

    forbidden = (
        ".settle(",
        ".activate(",
        "activate_from_settlement(",
        "mark_paid(",
        "include_router(",
        "initialize_empty(",
        "CustomerPaymentSettlementStore(",
        "CustomerPaymentEvidenceStore(",
        "CustomerPaymentIntentStore(",
        "CustomerCommercialOrderStore(",
        "requests.",
        "httpx.",
    )

    for token in forbidden:
        assert token not in source


def test_owner_does_not_accept_client_payment_authority_fields():
    from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    signature = inspect.signature(
        CustomerVndBankPaymentCompletionOrchestrationService.complete
    )

    forbidden = (
        "customer_id",
        "order_id",
        "payment_intent_id",
        "payment_evidence_id",
        "amount_minor",
        "currency",
        "operator_id",
        "bank_reference",
        "verification_assertion",
    )

    for name in forbidden:
        assert name not in signature.parameters
