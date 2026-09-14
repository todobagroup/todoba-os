import pytest

from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceStatus,
    PaymentEvidenceSource,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationStatus,
)


def _record():
    return CustomerVndBankReconciliationRecord(
        reconciliation_request_id="reconciliation-request-001",
        reconciliation_id="vnd-bank-reconciliation-001",
        payment_intent_id="payment-intent-001",
        order_id="order-001",
        customer_id="customer-001",
        bank_reference="VCB-20260914-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
        status=CustomerVndBankReconciliationStatus.CONFIRMED,
    )


class _ReconciliationService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def confirm(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class _Evidence:
    def __init__(self, reconciliation):
        self.payment_intent_id = reconciliation.payment_intent_id
        self.evidence_source = PaymentEvidenceSource.VND_BANK_TRANSFER
        self.external_evidence_id = reconciliation.bank_reference
        self.status = CustomerPaymentEvidenceStatus.RECEIVED


class _EvidencePublicationService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def publish(self, *, reconciliation_id):
        self.calls.append(
            reconciliation_id
        )
        return self.result


def _service(
    *,
    reconciliation=None,
    evidence=None,
):
    from backend.commercial.customer_vnd_bank_reconciliation_evidence_orchestration_service import (
        CustomerVndBankReconciliationEvidenceOrchestrationService,
    )

    reconciliation = reconciliation or _record()
    evidence = evidence or _Evidence(reconciliation)

    reconciliation_service = _ReconciliationService(
        reconciliation
    )

    publication_service = _EvidencePublicationService(
        evidence
    )

    service = (
        CustomerVndBankReconciliationEvidenceOrchestrationService(
            reconciliation_service=reconciliation_service,
            evidence_publication_service=publication_service,
        )
    )

    return (
        service,
        reconciliation_service,
        publication_service,
        reconciliation,
        evidence,
    )


def _confirm(service):
    return service.confirm(
        reconciliation_request_id="reconciliation-request-001",
        payment_intent_id="payment-intent-001",
        bank_reference="VCB-20260914-000001",
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )


def test_confirm_then_publish_trusted_evidence():
    (
        service,
        reconciliation_service,
        publication_service,
        reconciliation,
        _,
    ) = _service()

    result = _confirm(service)

    assert result is reconciliation

    assert reconciliation_service.calls == [
        {
            "reconciliation_request_id": (
                "reconciliation-request-001"
            ),
            "payment_intent_id": "payment-intent-001",
            "bank_reference": "VCB-20260914-000001",
            "amount_minor": 2500000,
            "currency": "VND",
            "operator_id": "operator-founder",
        }
    ]

    assert publication_service.calls == [
        reconciliation.reconciliation_id
    ]


def test_unconfirmed_reconciliation_is_never_published():
    reconciliation = _record()

    object.__setattr__(
        reconciliation,
        "status",
        object(),
    )

    (
        service,
        _,
        publication_service,
        _,
        _,
    ) = _service(
        reconciliation=reconciliation,
    )

    with pytest.raises(
        ValueError,
        match="confirmed",
    ):
        _confirm(service)

    assert publication_service.calls == []


def test_invalid_reconciliation_result_is_rejected():
    from backend.commercial.customer_vnd_bank_reconciliation_evidence_orchestration_service import (
        CustomerVndBankReconciliationEvidenceOrchestrationService,
    )

    reconciliation_service = _ReconciliationService(
        object()
    )

    publication_service = _EvidencePublicationService(
        object()
    )

    service = (
        CustomerVndBankReconciliationEvidenceOrchestrationService(
            reconciliation_service=reconciliation_service,
            evidence_publication_service=publication_service,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="reconciliation",
    ):
        _confirm(service)

    assert publication_service.calls == []


@pytest.mark.parametrize(
    (
        "field",
        "replacement",
    ),
    (
        (
            "payment_intent_id",
            "payment-intent-forged",
        ),
        (
            "external_evidence_id",
            "BANK-FORGED",
        ),
        (
            "status",
            object(),
        ),
        (
            "evidence_source",
            PaymentEvidenceSource.PAYPAL,
        ),
    ),
)
def test_published_evidence_must_converge_to_reconciliation(
    field,
    replacement,
):
    reconciliation = _record()
    evidence = _Evidence(
        reconciliation
    )

    setattr(
        evidence,
        field,
        replacement,
    )

    (
        service,
        _,
        publication_service,
        _,
        _,
    ) = _service(
        reconciliation=reconciliation,
        evidence=evidence,
    )

    with pytest.raises(
        RuntimeError,
        match="evidence",
    ):
        _confirm(service)

    assert publication_service.calls == [
        reconciliation.reconciliation_id
    ]


def test_identical_retry_delegates_to_idempotent_owners():
    (
        service,
        reconciliation_service,
        publication_service,
        reconciliation,
        _,
    ) = _service()

    first = _confirm(service)
    second = _confirm(service)

    assert first is reconciliation
    assert second is reconciliation

    assert len(
        reconciliation_service.calls
    ) == 2

    assert publication_service.calls == [
        reconciliation.reconciliation_id,
        reconciliation.reconciliation_id,
    ]


def test_constructor_requires_confirm_and_publish_owners():
    from backend.commercial.customer_vnd_bank_reconciliation_evidence_orchestration_service import (
        CustomerVndBankReconciliationEvidenceOrchestrationService,
    )

    with pytest.raises(TypeError):
        CustomerVndBankReconciliationEvidenceOrchestrationService(
            reconciliation_service=object(),
            evidence_publication_service=(
                _EvidencePublicationService(
                    object()
                )
            ),
        )

    with pytest.raises(TypeError):
        CustomerVndBankReconciliationEvidenceOrchestrationService(
            reconciliation_service=(
                _ReconciliationService(
                    _record()
                )
            ),
            evidence_publication_service=object(),
        )


def test_owner_has_no_assertion_settlement_activation_or_network_authority():
    import inspect

    from backend.commercial.customer_vnd_bank_reconciliation_evidence_orchestration_service import (
        CustomerVndBankReconciliationEvidenceOrchestrationService,
    )

    source = inspect.getsource(
        CustomerVndBankReconciliationEvidenceOrchestrationService
    )

    forbidden = (
        "build_assertion(",
        "settle(",
        "activate(",
        "activate_from_settlement(",
        "complete_verified_payment(",
        "requests.",
        "httpx.",
        "include_router(",
    )

    for token in forbidden:
        assert token not in source
