from pathlib import Path
import inspect

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

def test_vnd_bank_destination_config_requires_all_server_owned_fields(
    monkeypatch,
):
    import backend.config as config

    monkeypatch.delenv(
        "TODOBA_VND_BANK_CODE",
        raising=False,
    )
    monkeypatch.delenv(
        "TODOBA_VND_BANK_ACCOUNT_NUMBER",
        raising=False,
    )
    monkeypatch.delenv(
        "TODOBA_VND_BANK_ACCOUNT_NAME",
        raising=False,
    )

    with pytest.raises(RuntimeError):
        config.get_vnd_bank_payment_destination()


def test_vnd_bank_destination_config_returns_exact_server_owned_values(
    monkeypatch,
):
    import backend.config as config

    monkeypatch.setenv(
        "TODOBA_VND_BANK_CODE",
        "TESTBANK",
    )
    monkeypatch.setenv(
        "TODOBA_VND_BANK_ACCOUNT_NUMBER",
        "0123456789",
    )
    monkeypatch.setenv(
        "TODOBA_VND_BANK_ACCOUNT_NAME",
        "TODOBA TEST",
    )

    destination = (
        config.get_vnd_bank_payment_destination()
    )

    assert destination.bank_code == "TESTBANK"
    assert destination.account_number == "0123456789"
    assert destination.account_name == "TODOBA TEST"


def test_payment_instruction_production_composition_uses_server_destination(
    monkeypatch,
    tmp_path,
):
    import importlib.util
    from pathlib import Path

    import backend.main as production

    from backend.commercial.customer_identity_registry import (
        CustomerIdentity,
        CustomerIdentityRegistry,
    )
    from backend.commercial.customer_commercial_order_service import (
        CustomerCommercialOrderService,
    )
    from backend.commercial.customer_payment_intent_service import (
        CustomerPaymentIntentService,
        PaymentRail,
    )
    from backend.commercial.customer_vnd_bank_payment_instruction_service import (
        CustomerVndBankPaymentInstructionService,
    )

    original_root = (
        production.TODOBA_CONTROL_PLANE_DATA_ROOT
    )

    for name, value in tuple(
        vars(production).items()
    ):
        if not isinstance(value, Path):
            continue

        try:
            relative = value.relative_to(
                original_root
            )
        except ValueError:
            continue

        monkeypatch.setattr(
            production,
            name,
            tmp_path / relative,
        )

    monkeypatch.setattr(
        production,
        "TODOBA_CONTROL_PLANE_DATA_ROOT",
        tmp_path,
    )

    identity_path = (
        production.CUSTOMER_IDENTITY_STORAGE_PATH
    )

    identity_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _registered_identity_registry(
        identity_path
    ).initialize_empty()

    provisioner_path = (
        Path(__file__).parents[1]
        / "scripts"
        / "provision_customer_setup_control_plane.py"
    )

    spec = importlib.util.spec_from_file_location(
        "p8f2d2_provisioner",
        provisioner_path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    module.provision_customer_setup_control_plane(
        control_plane_root=tmp_path,
        confirm_runtime_stopped=True,
    )

    monkeypatch.setenv(
        "TODOBA_VND_BANK_CODE",
        "TESTBANK",
    )
    monkeypatch.setenv(
        "TODOBA_VND_BANK_ACCOUNT_NUMBER",
        "0123456789",
    )
    monkeypatch.setenv(
        "TODOBA_VND_BANK_ACCOUNT_NAME",
        "TODOBA TEST",
    )

    monkeypatch.setattr(
        production,
        "_customer_setup_runtime_composed",
        False,
    )

    monkeypatch.setattr(
        production,
        "_customer_payment_runtime_composed",
        False,
    )

    production._compose_customer_setup_runtime(
        production.app
    )

    production._compose_customer_payment_runtime(
        production.app
    )

    service = (
        production
        .customer_vnd_bank_payment_instruction_service
    )

    assert isinstance(
        service,
        CustomerVndBankPaymentInstructionService,
    )

    registry = _registered_identity_registry(
        production.CUSTOMER_IDENTITY_STORAGE_PATH,
        registration_store=(
            production.customer_registration_store
        ),
    )

    customer = CustomerIdentity(
        customer_id="p8f2d2-customer"
    )

    registry.register(customer)

    order = CustomerCommercialOrderService(
        order_store=(
            production.customer_commercial_order_store
        ),
        customer_identity_registry=registry,

        registration_store=(registry.registration_store),).create(
        order_request_id="p8f2d2-order-request",
        authorized_customer=customer,
        amount_minor=10000,
        currency="VND",
    )

    intent = CustomerPaymentIntentService(
        payment_intent_store=(
            production.customer_payment_intent_store
        ),
        order_store=(
            production.customer_commercial_order_store
        ),
    ).create(
        payment_intent_request_id=(
            "p8f2d2-intent-request"
        ),
        authorized_order=order,
        payment_rail=(
            PaymentRail.VND_BANK_TRANSFER
        ),
    )

    result = service.build(
        payment_intent_id=(
            intent.payment_intent_id
        )
    )

    assert result.bank_code == "TESTBANK"
    assert result.account_number == "0123456789"
    assert result.account_name == "TODOBA TEST"
    assert result.amount_minor == 10000
    assert result.currency == "VND"
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


def test_payment_instruction_service_is_server_composed_not_client_supplied():
    import backend.main as production

    source = inspect.getsource(
        production._compose_customer_payment_runtime
    )

    assert (
        "CustomerVndBankPaymentInstructionService("
        in source
    )

    assert (
        "get_vnd_bank_payment_destination()"
        in source
    )

    forbidden = (
        "bank_code=",
        "account_number=",
        "account_name=",
    )

    # Destination values must not be literal client/runtime inputs
    # to the composition function.
    for token in forbidden:
        assert token not in inspect.signature(
            production._compose_customer_payment_runtime
        ).parameters
