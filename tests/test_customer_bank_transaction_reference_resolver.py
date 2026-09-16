from pathlib import Path

import pytest

from backend.commercial.customer_bank_transaction_reference_resolver import (
    CustomerBankTransactionReferenceResolver,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_payment_transfer_reference_codec import (
    encode_payment_transfer_reference,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationRecord,
    CustomerRegistrationStore,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationService,
    CustomerVndBankReconciliationStatus,
    CustomerVndBankReconciliationStore,
)


def _registered_identity_registry(
    storage_path: Path,
):
    registration_store = CustomerRegistrationStore(
        storage_path.with_name(
            "customer_registrations.json"
        )
    )
    registration_store.initialize_empty()

    class _RegisteredIdentityRegistry(
        CustomerIdentityRegistry
    ):
        def register(
            self,
            customer,
        ):
            identity = super().register(customer)

            existing = (
                registration_store.get_by_customer_id(
                    customer_id=identity.customer_id
                )
            )

            if existing is None:
                registration_store.register(
                    CustomerRegistrationRecord(
                        registration_request_id=(
                            "test-registration-"
                            f"{identity.customer_id}"
                        ),
                        customer_id=identity.customer_id,
                    )
                )

            return identity

    registry = _RegisteredIdentityRegistry(
        storage_path
    )
    registry.registration_store = registration_store
    return registry


def _build(tmp_path: Path):
    identity_registry = _registered_identity_registry(
        tmp_path / "customer-identities.json"
    )
    identity_registry.initialize_empty()

    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    order_store = CustomerCommercialOrderStore(
        storage_path=tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
        registration_store=(
            identity_registry.registration_store
        ),
    )

    intent_store = CustomerPaymentIntentStore(
        storage_path=tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    reconciliation_store = (
        CustomerVndBankReconciliationStore(
            storage_path=(
                tmp_path / "bank-reconciliations.json"
            )
        )
    )
    reconciliation_store.initialize_empty()

    reconciliation_service = (
        CustomerVndBankReconciliationService(
            reconciliation_store=(
                reconciliation_store
            ),
            payment_intent_store=intent_store,
            order_store=order_store,
        )
    )

    resolver = CustomerBankTransactionReferenceResolver(
        payment_intent_store=intent_store,
        reconciliation_service=(
            reconciliation_service
        ),
    )

    return (
        order_service,
        intent_service,
        resolver,
        reconciliation_store,
    )


def test_generic_transfer_reference_resolves_exact_intent_and_uses_existing_reconciliation(
    tmp_path,
):
    (
        order_service,
        intent_service,
        resolver,
        reconciliation_store,
    ) = _build(tmp_path)

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    transfer_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                intent.payment_intent_id
            )
        )
    )

    result = resolver.resolve_and_reconcile(
        transfer_reference=transfer_reference,
        reconciliation_request_id=(
            "generic-bank-transaction-001"
        ),
        bank_reference=(
            "GENERIC-BANK-REFERENCE-001"
        ),
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    assert (
        result.payment_intent_id
        == intent.payment_intent_id
    )
    assert result.order_id == order.order_id
    assert result.customer_id == order.customer_id
    assert (
        result.bank_reference
        == "GENERIC-BANK-REFERENCE-001"
    )
    assert (
        result.status
        is CustomerVndBankReconciliationStatus.CONFIRMED
    )

    assert (
        reconciliation_store.get(
            reconciliation_id=(
                result.reconciliation_id
            )
        )
        == result
    )


def test_malformed_transfer_reference_is_rejected(
    tmp_path,
):
    (
        _,
        _,
        resolver,
        reconciliation_store,
    ) = _build(tmp_path)

    with pytest.raises(ValueError):
        resolver.resolve_and_reconcile(
            transfer_reference="NOT TODOBA",
            reconciliation_request_id=(
                "generic-bank-transaction-001"
            ),
            bank_reference=(
                "GENERIC-BANK-REFERENCE-001"
            ),
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )

    assert reconciliation_store.size() == 0


def test_decoded_unknown_payment_intent_is_rejected(
    tmp_path,
):
    (
        _,
        _,
        resolver,
        reconciliation_store,
    ) = _build(tmp_path)

    unknown_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                "payment-intent-"
                "ffffffffffffffffffffffffffffffff"
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="not authoritative",
    ):
        resolver.resolve_and_reconcile(
            transfer_reference=unknown_reference,
            reconciliation_request_id=(
                "generic-bank-transaction-001"
            ),
            bank_reference=(
                "GENERIC-BANK-REFERENCE-001"
            ),
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )

    assert reconciliation_store.size() == 0


def test_paypal_intent_reference_is_rejected(
    tmp_path,
):
    (
        order_service,
        intent_service,
        resolver,
        reconciliation_store,
    ) = _build(tmp_path)

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    transfer_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                intent.payment_intent_id
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="not eligible",
    ):
        resolver.resolve_and_reconcile(
            transfer_reference=transfer_reference,
            reconciliation_request_id=(
                "generic-bank-transaction-001"
            ),
            bank_reference=(
                "GENERIC-BANK-REFERENCE-001"
            ),
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )

    assert reconciliation_store.size() == 0


def test_amount_mismatch_remains_owned_by_reconciliation(
    tmp_path,
):
    (
        order_service,
        intent_service,
        resolver,
        reconciliation_store,
    ) = _build(tmp_path)

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    transfer_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                intent.payment_intent_id
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="amount or currency",
    ):
        resolver.resolve_and_reconcile(
            transfer_reference=transfer_reference,
            reconciliation_request_id=(
                "generic-bank-transaction-001"
            ),
            bank_reference=(
                "GENERIC-BANK-REFERENCE-001"
            ),
            amount_minor=1,
            currency="VND",
            operator_id="operator-founder",
        )

    assert reconciliation_store.size() == 0


def test_bank_reference_replay_remains_owned_by_reconciliation(
    tmp_path,
):
    (
        order_service,
        intent_service,
        resolver,
        reconciliation_store,
    ) = _build(tmp_path)

    first_order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    first_intent = intent_service.create(
        payment_intent_request_id="intent-request-001",
        authorized_order=first_order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    first_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                first_intent.payment_intent_id
            )
        )
    )

    resolver.resolve_and_reconcile(
        transfer_reference=first_reference,
        reconciliation_request_id=(
            "generic-bank-transaction-001"
        ),
        bank_reference=(
            "GENERIC-BANK-REFERENCE-001"
        ),
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    second_order = order_service.create(
        order_request_id="order-request-002",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    second_intent = intent_service.create(
        payment_intent_request_id="intent-request-002",
        authorized_order=second_order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    second_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                second_intent.payment_intent_id
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="already reconciled",
    ):
        resolver.resolve_and_reconcile(
            transfer_reference=second_reference,
            reconciliation_request_id=(
                "generic-bank-transaction-002"
            ),
            bank_reference=(
                "GENERIC-BANK-REFERENCE-001"
            ),
            amount_minor=2500000,
            currency="VND",
            operator_id="operator-founder",
        )

    assert reconciliation_store.size() == 1


def test_public_api_does_not_accept_payment_authority_context():
    import inspect

    signature = inspect.signature(
        CustomerBankTransactionReferenceResolver
        .resolve_and_reconcile
    )

    assert list(signature.parameters) == [
        "self",
        "transfer_reference",
        "reconciliation_request_id",
        "bank_reference",
        "amount_minor",
        "currency",
        "operator_id",
    ]

    forbidden = {
        "payment_intent_id",
        "customer_id",
        "order_id",
        "settlement_id",
        "evidence_id",
        "bank_code",
        "account_number",
    }

    assert forbidden.isdisjoint(
        signature.parameters
    )


def test_resolver_source_does_not_scan_or_create_reference_mapping():
    import inspect

    source = inspect.getsource(
        CustomerBankTransactionReferenceResolver
    )

    forbidden = (
        ".all(",
        "get_by_payment_intent_request_id(",
        "reference_map",
        "reference_mapping",
        "BIDV",
        "bidv",
    )

    for token in forbidden:
        assert token not in source


def test_resolver_accepts_confirm_owner_wrapper_not_only_raw_reconciliation_service(
    tmp_path,
):
    (
        order_service,
        intent_service,
        _,
        _,
    ) = _build(tmp_path)

    order = order_service.create(
        order_request_id="order-request-wrapper-001",
        authorized_customer=CustomerIdentity(
            customer_id="customer-001",
        ),
        amount_minor=2500000,
        currency="VND",
    )

    intent = intent_service.create(
        payment_intent_request_id="intent-request-wrapper-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    class RecordingConfirmOwner:
        def __init__(self):
            self.calls = []

        def confirm(self, **kwargs):
            self.calls.append(kwargs)

            return CustomerVndBankReconciliationRecord(
                reconciliation_request_id=(
                    kwargs["reconciliation_request_id"]
                ),
                reconciliation_id=(
                    "vnd-bank-reconciliation-wrapper-001"
                ),
                payment_intent_id=(
                    kwargs["payment_intent_id"]
                ),
                order_id=order.order_id,
                customer_id=order.customer_id,
                bank_reference=(
                    kwargs["bank_reference"]
                ),
                amount_minor=(
                    kwargs["amount_minor"]
                ),
                currency=kwargs["currency"],
                operator_id=(
                    kwargs["operator_id"]
                ),
                status=(
                    CustomerVndBankReconciliationStatus.CONFIRMED
                ),
            )

    confirm_owner = RecordingConfirmOwner()

    resolver = CustomerBankTransactionReferenceResolver(
        payment_intent_store=(
            intent_service._payment_intent_store
        ),
        reconciliation_service=confirm_owner,
    )

    transfer_reference = (
        encode_payment_transfer_reference(
            payment_intent_id=(
                intent.payment_intent_id
            )
        )
    )

    result = resolver.resolve_and_reconcile(
        transfer_reference=transfer_reference,
        reconciliation_request_id=(
            "generic-wrapper-request-001"
        ),
        bank_reference=(
            "GENERIC-WRAPPER-BANK-001"
        ),
        amount_minor=2500000,
        currency="VND",
        operator_id="operator-founder",
    )

    assert (
        result.payment_intent_id
        == intent.payment_intent_id
    )

    assert confirm_owner.calls == [
        {
            "reconciliation_request_id": (
                "generic-wrapper-request-001"
            ),
            "payment_intent_id": (
                intent.payment_intent_id
            ),
            "bank_reference": (
                "GENERIC-WRAPPER-BANK-001"
            ),
            "amount_minor": 2500000,
            "currency": "VND",
            "operator_id": "operator-founder",
        }
    ]


def test_resolver_rejects_dependency_without_confirm_owner_contract(
    tmp_path,
):
    intent_store = CustomerPaymentIntentStore(
        storage_path=tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    with pytest.raises(
        TypeError,
        match="confirm",
    ):
        CustomerBankTransactionReferenceResolver(
            payment_intent_store=intent_store,
            reconciliation_service=object(),
        )
