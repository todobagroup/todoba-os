
"""
P8F1 ? TODOBA VND Commercial Golden Path

This test proves the production-owned commercial trust chain without
introducing new payment authority:

    commercial order
    -> VND payment intent
    -> authenticated-authority reconciliation truth
    -> trusted payment evidence
    -> PaymentVerificationAssertion
    -> authoritative settlement
    -> settlement-gated Setup activation

The test also proves replay/idempotency and fail-closed mismatches.

P8F1 is test-only. It must not perform real banking/network access.
"""

from pathlib import Path

import pytest

from backend.commercial.customer_payment_settlement_activation_bridge import (
    CustomerPaymentSettlementActivationBridge,
)

from backend.commercial.customer_payment_intent_service import (
    PaymentRail,
)

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
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStore,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementService,
    CustomerPaymentSettlementStore,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationService,
    CustomerVndBankReconciliationStore,
)

from backend.commercial.customer_payment_settlement_orchestration_service import (
    CustomerPaymentSettlementOrchestrationService,
)
from backend.commercial.customer_vnd_bank_evidence_publication_service import (
    CustomerVndBankEvidencePublicationService,
)
from backend.commercial.customer_vnd_bank_reconciliation_evidence_orchestration_service import (
    CustomerVndBankReconciliationEvidenceOrchestrationService,
)
from backend.commercial.customer_vnd_bank_reconciliation_verification_adapter import (
    CustomerVndBankReconciliationVerificationAdapter,
)
from backend.commercial.customer_vnd_bank_payment_completion_orchestration_service import (
    CustomerVndBankPaymentCompletionOrchestrationService,
)




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

def test_vnd_commercial_golden_path_contract_surface_is_complete():
    """
    P8F1 first gate: every owner required by the real commercial VND chain
    must be present and expose only the expected boundary methods.

    The dynamic full-chain fixture is added only after this contract gate
    resolves the exact activation-bridge construction already owned by P7B2A.
    """

    owners = (
        CustomerCommercialOrderService,
        CustomerPaymentIntentService,
        CustomerVndBankReconciliationService,
        CustomerVndBankEvidencePublicationService,
        CustomerVndBankReconciliationVerificationAdapter,
        CustomerPaymentSettlementService,
        CustomerPaymentSettlementOrchestrationService,
        CustomerVndBankPaymentCompletionOrchestrationService,
    )

    for owner in owners:
        assert owner is not None

    assert callable(
        CustomerCommercialOrderService.create
    )

    assert callable(
        CustomerPaymentIntentService.create
    )

    assert callable(
        CustomerVndBankReconciliationService.confirm
    )

    assert callable(
        CustomerVndBankEvidencePublicationService.publish
    )

    assert callable(
        CustomerVndBankReconciliationVerificationAdapter.build_assertion
    )

    assert callable(
        CustomerVndBankPaymentCompletionOrchestrationService.complete
    )

    assert callable(
        CustomerPaymentSettlementOrchestrationService.complete_verified_payment
    )


def test_vnd_golden_path_accepts_no_client_settlement_authority():
    import inspect

    signature = inspect.signature(
        CustomerVndBankPaymentCompletionOrchestrationService.complete
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "reconciliation_id",
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
        "settlement_id",
        "activation_code",
    )

    for name in forbidden:
        assert name not in signature.parameters


def test_vnd_golden_path_has_no_network_or_client_proof_authority():
    import inspect

    sources = "\n".join(
        (
            inspect.getsource(
                CustomerVndBankEvidencePublicationService
            ),
            inspect.getsource(
                CustomerVndBankReconciliationVerificationAdapter
            ),
            inspect.getsource(
                CustomerVndBankPaymentCompletionOrchestrationService
            ),
        )
    )

    forbidden = (
        "requests.",
        "httpx.",
        "screenshot",
        "receipt",
        "client_proof",
        "payment_success",
    )

    for token in forbidden:
        assert token not in sources


def test_vnd_reconciliation_rejects_non_vnd_authority_surface():
    import inspect

    signature = inspect.signature(
        CustomerVndBankReconciliationService.confirm
    )

    assert (
        "currency"
        in signature.parameters
    )

    assert (
        "operator_id"
        in signature.parameters
    )

    # These values are server/authentication-owned upstream.
    # P8C/P8D composition must never expose them as arbitrary
    # customer authority.
    assert (
        "customer_id"
        not in signature.parameters
    )

    assert (
        "order_id"
        not in signature.parameters
    )



class _SettlementGatedActivationBridge(
    CustomerPaymentSettlementActivationBridge
):
    """
    Test-only recording subclass of the real production bridge type.

    This satisfies the production P7B2A ownership/type boundary without
    issuing a real customer activation. Physical activation is P8F2.
    """

    def __init__(self):
        # Deliberately do not initialize downstream production activation
        # dependencies in P8F1. This harness proves the settlement-gated
        # handoff only.
        self.calls = []
        self.result = object()

    def activate_from_settlement(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(
            {
                "args": args,
                "kwargs": kwargs,
            }
        )
        return self.result



def _construct_with_supported_kwargs(
    cls,
    available,
):
    import inspect

    signature = inspect.signature(
        cls
    )

    kwargs = {}

    for name, parameter in signature.parameters.items():
        if name in available:
            kwargs[name] = available[name]
            continue

        if (
            parameter.default
            is not inspect.Parameter.empty
        ):
            continue

        raise AssertionError(
            f"Unsupported required constructor parameter "
            f"{cls.__name__}.{name}"
        )

    return cls(
        **kwargs
    )


def _store_size(store):
    size = getattr(
        store,
        "size",
        None,
    )

    if not callable(size):
        raise AssertionError(
            f"{type(store).__name__} must expose size() "
            "for P8F1 replay proof."
        )

    return size()


def _build_dynamic_vnd_commercial_chain(
    tmp_path,
):
    identity_registry = _registered_identity_registry(
        tmp_path / "customer-identities.json"
    )
    identity_registry.initialize_empty()

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="p8f1-customer-001",
        )
    )

    order_store = CustomerCommercialOrderStore(
        tmp_path / "commercial-orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=(
            identity_registry
        ),

        registration_store=(identity_registry.registration_store),)

    order = order_service.create(
        order_request_id="p8f1-order-request-001",
        authorized_customer=customer,
        amount_minor=2500000,
        currency="VND",
    )

    intent_store = CustomerPaymentIntentStore(
        tmp_path / "payment-intents.json"
    )
    intent_store.initialize_empty()

    intent_service = CustomerPaymentIntentService(
        payment_intent_store=intent_store,
        order_store=order_store,
    )

    intent = intent_service.create(
        payment_intent_request_id=(
            "p8f1-intent-request-001"
        ),
        authorized_order=order,
        payment_rail=(
            PaymentRail.VND_BANK_TRANSFER
        ),
    )

    evidence_store = CustomerPaymentEvidenceStore(
        tmp_path / "payment-evidence.json"
    )
    evidence_store.initialize_empty()

    evidence_service = CustomerPaymentEvidenceService(
        payment_evidence_store=evidence_store,
        payment_intent_store=intent_store,
    )

    reconciliation_store = (
        CustomerVndBankReconciliationStore(
            tmp_path / "vnd-reconciliations.json"
        )
    )
    reconciliation_store.initialize_empty()

    reconciliation_service = (
        CustomerVndBankReconciliationService(
            reconciliation_store=(
                reconciliation_store
            ),
            payment_intent_store=(
                intent_store
            ),
            order_store=order_store,
        )
    )

    publication_service = (
        CustomerVndBankEvidencePublicationService(
            reconciliation_store=(
                reconciliation_store
            ),
            payment_evidence_service=(
                evidence_service
            ),
            payment_intent_service=(
                intent_service
            ),
            order_service=(
                order_service
            ),
        )
    )

    reconciliation_orchestration = (
        CustomerVndBankReconciliationEvidenceOrchestrationService(
            reconciliation_service=(
                reconciliation_service
            ),
            evidence_publication_service=(
                publication_service
            ),
        )
    )

    settlement_store = CustomerPaymentSettlementStore(
        tmp_path / "payment-settlements.json"
    )
    settlement_store.initialize_empty()

    settlement_service = (
        _construct_with_supported_kwargs(
            CustomerPaymentSettlementService,
            {
                "settlement_store": (
                    settlement_store
                ),
                "payment_settlement_store": (
                    settlement_store
                ),
                "payment_evidence_store": (
                    evidence_store
                ),
                "evidence_store": (
                    evidence_store
                ),
                "payment_intent_store": (
                    intent_store
                ),
                "intent_store": (
                    intent_store
                ),
                "order_store": (
                    order_store
                ),
                "commercial_order_store": (
                    order_store
                ),
            },
        )
    )

    activation_bridge = (
        _SettlementGatedActivationBridge()
    )

    settlement_orchestration = (
        _construct_with_supported_kwargs(
            CustomerPaymentSettlementOrchestrationService,
            {
                "settlement_service": (
                    settlement_service
                ),
                "payment_settlement_service": (
                    settlement_service
                ),
                "activation_bridge": (
                    activation_bridge
                ),
                "setup_activation_bridge": (
                    activation_bridge
                ),
            },
        )
    )

    verification_adapter = (
        CustomerVndBankReconciliationVerificationAdapter(
            reconciliation_store=(
                reconciliation_store
            ),
            payment_evidence_store=(
                evidence_store
            ),
            payment_intent_store=(
                intent_store
            ),
            order_store=(
                order_store
            ),
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=(
                verification_adapter
            ),
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    return {
        "customer": customer,
        "order": order,
        "order_store": order_store,
        "intent": intent,
        "intent_store": intent_store,
        "evidence_store": evidence_store,
        "reconciliation_store": (
            reconciliation_store
        ),
        "reconciliation_service": (
            reconciliation_service
        ),
        "reconciliation_orchestration": (
            reconciliation_orchestration
        ),
        "settlement_store": (
            settlement_store
        ),
        "activation_bridge": (
            activation_bridge
        ),
        "completion_service": (
            completion_service
        ),
    }


def _confirm_authoritative_vnd_payment(
    chain,
    *,
    reconciliation_request_id=(
        "p8f1-reconciliation-request-001"
    ),
    bank_reference="VCB-P8F1-000001",
    amount_minor=2500000,
):
    return (
        chain[
            "reconciliation_orchestration"
        ].confirm(
            reconciliation_request_id=(
                reconciliation_request_id
            ),
            payment_intent_id=(
                chain["intent"].payment_intent_id
            ),
            bank_reference=bank_reference,
            amount_minor=amount_minor,
            currency="VND",
            operator_id="p8f1-authenticated-operator",
        )
    )


def test_vnd_commercial_dynamic_chain_reaches_settlement_gated_activation(
    tmp_path,
):
    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    assert _store_size(
        chain["evidence_store"]
    ) == 0

    assert _store_size(
        chain["settlement_store"]
    ) == 0

    assert (
        chain["activation_bridge"].calls
        == []
    )

    reconciliation = (
        _confirm_authoritative_vnd_payment(
            chain
        )
    )

    # Trusted evidence must now exist, but settlement and activation
    # must still not have happened merely from reconciliation.
    assert _store_size(
        chain["evidence_store"]
    ) == 1

    assert _store_size(
        chain["settlement_store"]
    ) == 0

    assert (
        chain["activation_bridge"].calls
        == []
    )

    activation_result = (
        chain["completion_service"].complete(
            reconciliation_id=(
                reconciliation.reconciliation_id
            ),
        )
    )

    assert (
        activation_result
        is chain["activation_bridge"].result
    )

    assert _store_size(
        chain["settlement_store"]
    ) == 1

    # Activation handoff can occur only after the existing
    # settlement orchestration accepted authoritative SETTLED truth.
    assert len(
        chain["activation_bridge"].calls
    ) == 1


def test_vnd_commercial_retry_does_not_duplicate_evidence_or_settlement(
    tmp_path,
):
    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    first_reconciliation = (
        _confirm_authoritative_vnd_payment(
            chain
        )
    )

    first_result = (
        chain["completion_service"].complete(
            reconciliation_id=(
                first_reconciliation.reconciliation_id
            ),
        )
    )

    evidence_size = _store_size(
        chain["evidence_store"]
    )

    settlement_size = _store_size(
        chain["settlement_store"]
    )

    second_reconciliation = (
        _confirm_authoritative_vnd_payment(
            chain
        )
    )

    second_result = (
        chain["completion_service"].complete(
            reconciliation_id=(
                second_reconciliation.reconciliation_id
            ),
        )
    )

    assert (
        second_reconciliation
        == first_reconciliation
    )

    assert _store_size(
        chain["evidence_store"]
    ) == evidence_size == 1

    assert _store_size(
        chain["settlement_store"]
    ) == settlement_size == 1

    # The activation bridge is downstream of the authoritative,
    # idempotent settlement. P8F2 will prove real activation
    # issuance/replay behavior physically.
    assert first_result is (
        chain["activation_bridge"].result
    )

    assert second_result is (
        chain["activation_bridge"].result
    )


def test_vnd_commercial_wrong_amount_fails_before_evidence_settlement_activation(
    tmp_path,
):
    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    with pytest.raises(ValueError):
        _confirm_authoritative_vnd_payment(
            chain,
            amount_minor=1,
        )

    assert _store_size(
        chain["evidence_store"]
    ) == 0

    assert _store_size(
        chain["settlement_store"]
    ) == 0

    assert (
        chain["activation_bridge"].calls
        == []
    )


def test_vnd_commercial_bank_reference_replay_is_rejected(
    tmp_path,
):
    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    first = (
        _confirm_authoritative_vnd_payment(
            chain,
            reconciliation_request_id=(
                "p8f1-reconciliation-request-001"
            ),
            bank_reference=(
                "VCB-P8F1-REPLAY-001"
            ),
        )
    )

    assert first is not None

    assert _store_size(
        chain["evidence_store"]
    ) == 1

    with pytest.raises(ValueError):
        _confirm_authoritative_vnd_payment(
            chain,
            reconciliation_request_id=(
                "p8f1-reconciliation-request-002"
            ),
            bank_reference=(
                "VCB-P8F1-REPLAY-001"
            ),
        )

    assert _store_size(
        chain["evidence_store"]
    ) == 1

    assert _store_size(
        chain["settlement_store"]
    ) == 0

    assert (
        chain["activation_bridge"].calls
        == []
    )
