from pathlib import Path
import pytest




def _registered_identity_registry(
    storage_path: Path,
    *,
    registration_store=None,
):
    """
    Test-only identity registry preserving the production invariant:
    every authoritative identity registered here also owns one
    authoritative customer registration.
    """
    from backend.commercial.customer_identity_registry import (
        CustomerIdentityRegistry,
    )
    from backend.commercial.customer_registration_service import (
        CustomerRegistrationRecord,
        CustomerRegistrationStore,
    )

    if registration_store is None:
        registration_store = CustomerRegistrationStore(
            storage_path.with_name("customer_registrations.json")
        )

        if not registration_store.is_ready():
            registration_store.initialize_empty()

    elif not isinstance(
        registration_store,
        CustomerRegistrationStore,
    ):
        raise TypeError(
            "registration_store must be CustomerRegistrationStore."
        )

    if not registration_store.is_ready():
        raise RuntimeError(
            "Customer registration store is not initialized."
        )

    class _RegisteredIdentityRegistry(
        CustomerIdentityRegistry
    ):
        def register(
            self,
            customer,
        ):
            identity = super().register(customer)

            existing = registration_store.get_by_customer_id(
                customer_id=identity.customer_id
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

    registry = _RegisteredIdentityRegistry(storage_path)
    registry.registration_store = registration_store
    return registry

def test_vnd_payment_instruction_service_contract_exists():
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
        CustomerVndBankPaymentInstructionResult,
        CustomerVndBankPaymentInstructionService,
    )

    assert CustomerVndBankPaymentDestination is not None
    assert CustomerVndBankPaymentInstructionResult is not None
    assert CustomerVndBankPaymentInstructionService is not None


def test_vnd_payment_instruction_contract_has_server_owned_destination_and_no_client_amount():
    from dataclasses import fields

    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
        CustomerVndBankPaymentInstructionResult,
    )

    destination_fields = {
        field.name
        for field in fields(
            CustomerVndBankPaymentDestination
        )
    }

    assert destination_fields == {
        "bank_code",
        "account_number",
        "account_name",
    }

    result_fields = {
        field.name
        for field in fields(
            CustomerVndBankPaymentInstructionResult
        )
    }

    assert result_fields == {
        "payment_intent_id",
        "order_id",
        "amount_minor",
        "currency",
        "payment_rail",
        "bank_code",
        "account_number",
        "account_name",
        "transfer_reference",
    }


def test_vnd_payment_instruction_service_public_build_accepts_only_payment_intent_id():
    import inspect

    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentInstructionService,
    )

    signature = inspect.signature(
        CustomerVndBankPaymentInstructionService.build
    )

    public_parameters = [
        parameter
        for name, parameter
        in signature.parameters.items()
        if name != "self"
    ]

    assert len(public_parameters) == 1

    parameter = public_parameters[0]

    assert parameter.name == "payment_intent_id"
    assert (
        parameter.kind
        is inspect.Parameter.KEYWORD_ONLY
    )


def test_vnd_payment_instruction_destination_rejects_blank_authority():
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVndBankPaymentDestination(
            bank_code="",
            account_number="123456789",
            account_name="TODOBA",
        )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVndBankPaymentDestination(
            bank_code="VCB",
            account_number="",
            account_name="TODOBA",
        )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVndBankPaymentDestination(
            bank_code="VCB",
            account_number="123456789",
            account_name="",
        )


def test_vnd_payment_instruction_uses_authoritative_order_and_intent_only(
    tmp_path,
):
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
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
        CustomerVndBankPaymentInstructionService,
    )

    identity_path = (
        tmp_path / "customer_identities.json"
    )
    order_path = (
        tmp_path / "customer_commercial_orders.json"
    )
    intent_path = (
        tmp_path / "customer_payment_intents.json"
    )

    identity_registry = _registered_identity_registry(
        identity_path
    )
    identity_registry.initialize_empty()

    order_store = CustomerCommercialOrderStore(
        order_path
    )
    order_store.initialize_empty()

    intent_store = CustomerPaymentIntentStore(
        intent_path
    )
    intent_store.initialize_empty()

    customer = CustomerIdentity(
        customer_id="instruction-customer-001"
    )
    identity_registry.register(customer)

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,

        registration_store=(identity_registry.registration_store),)

    order = order_service.create(
        order_request_id="instruction-order-request-001",
        authorized_customer=customer,
        amount_minor=10000,
        currency="VND",
    )

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    intent = intent_service.create(
        payment_intent_request_id=(
            "instruction-intent-request-001"
        ),
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    destination = CustomerVndBankPaymentDestination(
        bank_code="TESTBANK",
        account_number="0123456789",
        account_name="TODOBA TEST",
    )

    service = CustomerVndBankPaymentInstructionService(
        payment_intent_store=intent_store,
        order_store=order_store,
        destination=destination,
    )

    result = service.build(
        payment_intent_id=intent.payment_intent_id
    )

    assert (
        result.payment_intent_id
        == intent.payment_intent_id
    )
    assert result.order_id == order.order_id
    assert result.amount_minor == 10000
    assert result.currency == "VND"
    assert (
        result.payment_rail
        is PaymentRail.VND_BANK_TRANSFER
    )

    assert result.bank_code == "TESTBANK"
    assert result.account_number == "0123456789"
    assert result.account_name == "TODOBA TEST"

    # Transfer reference is server-owned and deterministic.
    import base64
    import hashlib

    expected_reference_token = base64.b32encode(
        hashlib.sha256(
            intent.payment_intent_id.encode("utf-8")
        ).digest()
    ).decode("ascii")[:16]

    assert result.transfer_reference == (
        f"TODOBA SOFTWARE {expected_reference_token}"
    )
    assert (
        intent.payment_intent_id
        not in result.transfer_reference
    )

    retry = service.build(
        payment_intent_id=intent.payment_intent_id
    )

    assert retry == result


def test_vnd_payment_instruction_rejects_non_vnd_rail(
    tmp_path,
):
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
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
        CustomerVndBankPaymentInstructionService,
    )

    identity_path = tmp_path / "identities.json"
    order_path = tmp_path / "orders.json"
    intent_path = tmp_path / "intents.json"

    identity_registry = _registered_identity_registry(
        identity_path
    )
    identity_registry.initialize_empty()

    order_store = CustomerCommercialOrderStore(
        order_path
    )
    order_store.initialize_empty()

    intent_store = CustomerPaymentIntentStore(
        intent_path
    )
    intent_store.initialize_empty()

    customer = CustomerIdentity(
        customer_id="instruction-customer-paypal"
    )
    identity_registry.register(customer)

    order = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,

        registration_store=(identity_registry.registration_store),).create(
        order_request_id="instruction-order-paypal",
        authorized_customer=customer,
        amount_minor=10000,
        currency="VND",
    )

    intent = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    ).create(
        payment_intent_request_id=(
            "instruction-intent-paypal"
        ),
        authorized_order=order,
        payment_rail=PaymentRail.PAYPAL,
    )

    service = CustomerVndBankPaymentInstructionService(
        payment_intent_store=intent_store,
        order_store=order_store,
        destination=CustomerVndBankPaymentDestination(
            bank_code="TESTBANK",
            account_number="0123456789",
            account_name="TODOBA TEST",
        ),
    )

    with pytest.raises(
        (ValueError, RuntimeError),
    ):
        service.build(
            payment_intent_id=intent.payment_intent_id
        )


def test_vnd_payment_instruction_rejects_non_vnd_currency(
    tmp_path,
):
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
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
        CustomerVndBankPaymentInstructionService,
    )

    identity_registry = _registered_identity_registry(
        tmp_path / "identities.json"
    )
    identity_registry.initialize_empty()

    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    customer = CustomerIdentity(
        customer_id="instruction-customer-usd"
    )
    identity_registry.register(customer)

    order = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,

        registration_store=(identity_registry.registration_store),).create(
        order_request_id="instruction-order-usd",
        authorized_customer=customer,
        amount_minor=10000,
        currency="USD",
    )

    intent = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    ).create(
        payment_intent_request_id=(
            "instruction-intent-usd"
        ),
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    service = CustomerVndBankPaymentInstructionService(
        payment_intent_store=intent_store,
        order_store=order_store,
        destination=CustomerVndBankPaymentDestination(
            bank_code="TESTBANK",
            account_number="0123456789",
            account_name="TODOBA TEST",
        ),
    )

    with pytest.raises(
        (ValueError, RuntimeError),
    ):
        service.build(
            payment_intent_id=intent.payment_intent_id
        )


def test_vnd_payment_instruction_projects_global_todoba_software_reference(
    tmp_path,
):
    import base64
    import hashlib

    from backend.commercial.customer_commercial_order_service import (
        CustomerCommercialOrderService,
        CustomerCommercialOrderStore,
    )
    from backend.commercial.customer_identity_registry import (
        CustomerIdentity,
    )
    from backend.commercial.customer_payment_intent_service import (
        CustomerPaymentIntentService,
        CustomerPaymentIntentStore,
        PaymentRail,
    )
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentDestination,
        CustomerVndBankPaymentInstructionService,
    )

    identity_registry = _registered_identity_registry(
        tmp_path / "identities.json"
    )
    identity_registry.initialize_empty()

    customer = CustomerIdentity(
        customer_id="customer-reference-001"
    )
    identity_registry.register(customer)

    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
        registration_store=identity_registry.registration_store,
    )

    order = order_service.create(
        order_request_id="reference-order-request-001",
        authorized_customer=customer,
        amount_minor=10000,
        currency="VND",
    )

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "intents.json"
    )
    intent_store.initialize_empty()

    intent = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    ).create(
        payment_intent_request_id="reference-intent-request-001",
        authorized_order=order,
        payment_rail=PaymentRail.VND_BANK_TRANSFER,
    )

    service = CustomerVndBankPaymentInstructionService(
        payment_intent_store=intent_store,
        order_store=order_store,
        destination=CustomerVndBankPaymentDestination(
            bank_code="TESTBANK",
            account_number="0123456789",
            account_name="TODOBA TEST",
        ),
    )

    result = service.build(
        payment_intent_id=intent.payment_intent_id
    )

    expected_reference = base64.b32encode(
        hashlib.sha256(
            intent.payment_intent_id.encode("utf-8")
        ).digest()
    ).decode("ascii")[:16]

    assert result.transfer_reference == (
        f"TODOBA SOFTWARE {expected_reference}"
    )

    assert result.transfer_reference != intent.payment_intent_id

    assert len(expected_reference) == 16
    assert expected_reference.isalnum()
    assert expected_reference == expected_reference.upper()

    retry = service.build(
        payment_intent_id=intent.payment_intent_id
    )

    assert retry.transfer_reference == result.transfer_reference


def test_vnd_payment_instruction_reference_changes_with_payment_intent(
    tmp_path,
):
    import base64
    import hashlib

    first = "payment-intent-00000000000000000000000000000001"
    second = "payment-intent-00000000000000000000000000000002"

    def project(payment_intent_id: str) -> str:
        token = base64.b32encode(
            hashlib.sha256(
                payment_intent_id.encode("utf-8")
            ).digest()
        ).decode("ascii")[:16]

        return f"TODOBA SOFTWARE {token}"

    assert project(first) != project(second)


def test_vnd_payment_instruction_public_build_still_accepts_only_payment_intent_id():
    import inspect

    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentInstructionService,
    )

    signature = inspect.signature(
        CustomerVndBankPaymentInstructionService.build
    )

    public_parameters = [
        parameter
        for name, parameter in signature.parameters.items()
        if name != "self"
    ]

    assert len(public_parameters) == 1
    assert public_parameters[0].name == "payment_intent_id"
    assert (
        public_parameters[0].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
