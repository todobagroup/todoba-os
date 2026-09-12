from pathlib import Path

import pytest

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceService,
    CustomerPaymentEvidenceStore,
    CustomerPaymentEvidenceStatus,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
    CustomerPaymentIntentStatus,
    PaymentRail,
)
from backend.commercial.customer_vnd_bank_evidence_publication_service import (
    CustomerVndBankEvidencePublicationService,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationService,
    CustomerVndBankReconciliationStatus,
    CustomerVndBankReconciliationStore,
)


def _build(
    tmp_path: Path,
):
    identity_registry = CustomerIdentityRegistry(
        tmp_path / "customer-identities.json"
    )
    identity_registry.initialize_empty()

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
    )

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    evidence_store = CustomerPaymentEvidenceStore(
        tmp_path / "evidence.json"
    )
    evidence_store.initialize_empty()

    evidence_service = CustomerPaymentEvidenceService(
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
    )

    reconciliation_store = CustomerVndBankReconciliationStore(
        tmp_path / "reconciliations.json"
    )
    reconciliation_store.initialize_empty()

    reconciliation_service = CustomerVndBankReconciliationService(
        reconciliation_store=reconciliation_store,
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    publication_service = CustomerVndBankEvidencePublicationService(
        reconciliation_store=reconciliation_store,
        payment_evidence_service=evidence_service,
        payment_intent_service=intent_service,
        order_service=order_service,
    )

    return (
        publication_service,
        reconciliation_service,
        reconciliation_store,
        evidence_store,
        customer,
        order_service,
        intent_service,
    )


def _create_reconciliation(
    *,
    reconciliation_service,
    customer,
    order_service,
    intent_service,
):
    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=2_500_000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    reconciliation = reconciliation_service.confirm(
        reconciliation_request_id="reconcile-request-001",
        payment_intent_id=intent.payment_intent_id,
        bank_reference="VCB-20260912-000001",
        amount_minor=2_500_000,
        currency="VND",
        operator_id="operator-founder",
    )

    return (
        order,
        intent,
        reconciliation,
    )


def test_authoritative_reconciliation_publishes_vnd_evidence(
    tmp_path: Path,
) -> None:
    (
        service,
        reconciliation_service,
        _,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    order, intent, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    evidence = service.publish(
        reconciliation_id=reconciliation.reconciliation_id,
    )

    assert evidence.evidence_request_id == (
        "vnd-bank-evidence-"
        f"{reconciliation.reconciliation_id}"
    )
    assert evidence.payment_intent_id == intent.payment_intent_id
    assert (
        evidence.evidence_source
        is PaymentEvidenceSource.VND_BANK_TRANSFER
    )
    assert (
        evidence.external_evidence_id
        == reconciliation.bank_reference
    )
    assert evidence.status is CustomerPaymentEvidenceStatus.RECEIVED
    assert evidence_store.size() == 1

    assert order.order_id == reconciliation.order_id


def test_identical_publication_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    (
        service,
        reconciliation_service,
        _,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    first = service.publish(
        reconciliation_id=reconciliation.reconciliation_id,
    )
    second = service.publish(
        reconciliation_id=reconciliation.reconciliation_id,
    )

    assert second == first
    assert evidence_store.size() == 1


def test_unknown_reconciliation_is_rejected(
    tmp_path: Path,
) -> None:
    (
        service,
        _,
        _,
        evidence_store,
        _,
        _,
        _,
    ) = _build(tmp_path)

    with pytest.raises(
        ValueError,
        match="reconciliation",
    ):
        service.publish(
            reconciliation_id="missing-reconciliation",
        )

    assert evidence_store.size() == 0


def test_reconciliation_must_remain_confirmed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        reconciliation_store,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = reconciliation_store.get

    def forged_get(
        *,
        reconciliation_id: str,
    ):
        record = original_get(
            reconciliation_id=reconciliation_id
        )

        assert record is not None

        object.__setattr__(
            record,
            "status",
            object(),
        )

        return record

    monkeypatch.setattr(
        reconciliation_store,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0


def test_intent_must_remain_authoritative_vnd_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        _,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, intent, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = intent_service.get

    def forged_get(
        *,
        payment_intent_id: str,
    ):
        result = original_get(
            payment_intent_id=payment_intent_id
        )

        assert result is not None
        assert result.payment_intent_id == intent.payment_intent_id

        object.__setattr__(
            result,
            "payment_rail",
            PaymentRail.PAYPAL,
        )

        return result

    monkeypatch.setattr(
        intent_service,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0


def test_order_chain_must_match_reconciliation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        _,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    order, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = order_service.get

    def forged_get(
        *,
        order_id: str,
    ):
        result = original_get(
            order_id=order_id
        )

        assert result is not None
        assert result.order_id == order.order_id

        object.__setattr__(
            result,
            "amount_minor",
            result.amount_minor + 1,
        )

        return result

    monkeypatch.setattr(
        order_service,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0


def test_publication_surface_accepts_only_reconciliation_identity(
) -> None:
    import inspect

    signature = inspect.signature(
        CustomerVndBankEvidencePublicationService.publish
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "reconciliation_id",
    )


def test_p6c_exposes_no_settlement_activation_or_network_authority(
) -> None:
    import inspect

    source = inspect.getsource(
        CustomerVndBankEvidencePublicationService
    )

    forbidden = (
        "settle(",
        "activate(",
        "requests.",
        "httpx.",
        "operator_id",
        "screenshot",
        "receipt",
    )

    for token in forbidden:
        assert token not in source


@pytest.mark.parametrize(
    (
        "argument_name",
        "replacement",
    ),
    (
        (
            "reconciliation_store",
            object(),
        ),
        (
            "payment_evidence_service",
            object(),
        ),
        (
            "payment_intent_service",
            object(),
        ),
        (
            "order_service",
            object(),
        ),
    ),
)
def test_constructor_rejects_wrong_dependency_types(
    tmp_path: Path,
    argument_name: str,
    replacement,
) -> None:
    (
        _,
        _,
        reconciliation_store,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    evidence_service = CustomerPaymentEvidenceService(
        payment_evidence_store=evidence_store,
        payment_intent_store=(
            intent_service._payment_intent_store
        ),
    )

    kwargs = {
        "reconciliation_store": reconciliation_store,
        "payment_evidence_service": evidence_service,
        "payment_intent_service": intent_service,
        "order_service": order_service,
    }

    kwargs[argument_name] = replacement

    with pytest.raises(TypeError):
        CustomerVndBankEvidencePublicationService(
            **kwargs,
        )

    assert customer.customer_id == "customer-001"


def test_constructor_rejects_unready_reconciliation_store(
    tmp_path: Path,
) -> None:
    (
        _,
        _,
        _,
        evidence_store,
        _,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    unready_reconciliation_store = (
        CustomerVndBankReconciliationStore(
            tmp_path / "unready-reconciliations.json"
        )
    )

    evidence_service = CustomerPaymentEvidenceService(
        payment_evidence_store=evidence_store,
        payment_intent_store=(
            intent_service._payment_intent_store
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="reconciliation store",
    ):
        CustomerVndBankEvidencePublicationService(
            reconciliation_store=(
                unready_reconciliation_store
            ),
            payment_evidence_service=evidence_service,
            payment_intent_service=intent_service,
            order_service=order_service,
        )


def test_reconciliation_customer_must_match_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        reconciliation_store,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = reconciliation_store.get

    def forged_get(
        *,
        reconciliation_id: str,
    ):
        record = original_get(
            reconciliation_id=reconciliation_id
        )

        assert record is not None

        object.__setattr__(
            record,
            "customer_id",
            "customer-forged",
        )

        return record

    monkeypatch.setattr(
        reconciliation_store,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0


def test_reconciliation_currency_must_remain_vnd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        reconciliation_store,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = reconciliation_store.get

    def forged_get(
        *,
        reconciliation_id: str,
    ):
        record = original_get(
            reconciliation_id=reconciliation_id
        )

        assert record is not None

        object.__setattr__(
            record,
            "currency",
            "USD",
        )

        return record

    monkeypatch.setattr(
        reconciliation_store,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0


def test_order_status_must_remain_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        _,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = order_service.get

    def forged_get(
        *,
        order_id: str,
    ):
        result = original_get(
            order_id=order_id
        )

        assert result is not None

        object.__setattr__(
            result,
            "status",
            object(),
        )

        return result

    monkeypatch.setattr(
        order_service,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0


def test_intent_status_must_remain_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        service,
        reconciliation_service,
        _,
        evidence_store,
        customer,
        order_service,
        intent_service,
    ) = _build(tmp_path)

    _, _, reconciliation = _create_reconciliation(
        reconciliation_service=reconciliation_service,
        customer=customer,
        order_service=order_service,
        intent_service=intent_service,
    )

    original_get = intent_service.get

    def forged_get(
        *,
        payment_intent_id: str,
    ):
        result = original_get(
            payment_intent_id=payment_intent_id
        )

        assert result is not None

        object.__setattr__(
            result,
            "status",
            object(),
        )

        return result

    monkeypatch.setattr(
        intent_service,
        "get",
        forged_get,
    )

    with pytest.raises(ValueError):
        service.publish(
            reconciliation_id=reconciliation.reconciliation_id,
        )

    assert evidence_store.size() == 0
