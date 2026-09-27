
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
from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingRecord,
    CustomerCommercialOrderTermsBindingStore,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationService,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeService,
    CustomerSetupAccessCodeStore,
)
from backend.commercial.customer_setup_access_code_exchange_service import (
    CustomerSetupAccessCodeExchangeService,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationService,
    CustomerSetupBootstrapAuthorizationStore,
)
from backend.commercial.customer_setup_bootstrap_launch_grant_service import (
    CustomerSetupBootstrapLaunchGrantService,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchCredentialService,
    CustomerSetupLaunchCredentialStore,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationRecord,
    CustomerRegistrationStore,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffService,
    CustomerSetupHandoffStore,
)
from backend.commercial.customer_setup_handoff_authorizer import (
    CustomerSetupHandoffAuthorizer,
)
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationService,
    CustomerSetupBuildContinuationStore,
)
from backend.commercial.customer_setup_provisioning_api import (
    create_customer_setup_provisioning_router,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_setup_entry_grant_service import (
    CustomerSetupEntryGrantService,
)
from backend.commercial.customer_payment_settlement_entitlement_convergence_service import (
    CustomerPaymentSettlementEntitlementConvergenceService,
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
        "identity_registry": identity_registry,
        "customer": customer,
        "settlement_service": settlement_service,
        "verification_adapter": verification_adapter,
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

def test_vnd_commercial_real_activation_from_authoritative_settlement(
    tmp_path,
):
    """
    P8F2 proves the full authoritative VND payment chain reaches the
    real Setup activation owner rather than a recording test double.
    """

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f2-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "p8f2-entitlements.json"
    )
    entitlement_registry.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=entitlement_registry,
        )
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f2-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f2-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    real_activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    real_settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=real_activation_bridge,
        )
    )

    real_completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                real_settlement_orchestration
            ),
        )
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    assert activation_store.size() == 0
    assert entitlement_registry.size() == 0

    first = real_completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    assert (
        first.status
        is CustomerSetupActivationStatus.ACTIVE
    )

    assert first.customer_id == chain["order"].customer_id
    assert activation_store.size() == 1
    assert entitlement_registry.size() == 1

    second = real_completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    assert second == first
    assert activation_store.size() == 1
    assert entitlement_registry.size() == 1

def test_vnd_paid_activation_issues_authoritative_access_code(
    tmp_path,
):
    """
    P8F3 proves authoritative VND settlement can reach the real
    customer Access Code authority only through the real Setup
    activation identity created downstream of payment settlement.
    """

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f3-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "p8f3-entitlements.json"
    )
    entitlement_registry.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=entitlement_registry,
        )
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f3-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f3-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=activation_bridge,
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    access_code_store = CustomerSetupAccessCodeStore(
        tmp_path / "p8f3-access-codes.json",
        setup_activation_store=activation_store,
    )
    access_code_store.initialize_empty()

    access_code_service = CustomerSetupAccessCodeService(
        access_code_store=access_code_store,
        setup_activation_store=activation_store,
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    activation = completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    assert (
        activation.status
        is CustomerSetupActivationStatus.ACTIVE
    )

    assert (
        access_code_store.get_active_by_setup_activation_id(
            setup_activation_id=activation.setup_activation_id
        )
        is None
    )

    issued = access_code_service.issue(
        setup_activation_id=activation.setup_activation_id
    )

    authorized = access_code_service.authorize(
        activation_code=issued.activation_code
    )

    assert (
        authorized.setup_activation_id
        == activation.setup_activation_id
    )

    assert (
        authorized.customer_id
        == chain["order"].customer_id
    )

    persisted_record = (
        access_code_store.get_active_by_setup_activation_id(
            setup_activation_id=activation.setup_activation_id
        )
    )

    assert persisted_record is not None
    assert (
        persisted_record.access_code_id
        == issued.access_code_id
    )
    assert (
        persisted_record.setup_activation_id
        == activation.setup_activation_id
    )

    persisted = (
        access_code_store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert issued.activation_code not in persisted

def test_vnd_paid_access_code_reaches_real_setup_launch_credential(
    tmp_path,
):
    """
    P8F4 proves the authoritative paid customer path reaches a real
    Setup launch credential through the real Access Code exchange and
    bootstrap authorization owners without client-supplied identity.
    """

    import base64
    import hashlib
    from datetime import datetime, timezone

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f4-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "p8f4-entitlements.json"
    )
    entitlement_registry.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=entitlement_registry,
        )
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f4-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f4-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=activation_bridge,
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    access_code_store = CustomerSetupAccessCodeStore(
        tmp_path / "p8f4-access-codes.json",
        setup_activation_store=activation_store,
    )
    access_code_store.initialize_empty()

    access_code_service = CustomerSetupAccessCodeService(
        access_code_store=access_code_store,
        setup_activation_store=activation_store,
    )

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            tmp_path / "p8f4-bootstrap-authorizations.json",
            customer_identity_registry=(
                chain["identity_registry"]
            ),
        )
    )
    bootstrap_authorization_store.initialize_empty()

    bootstrap_authorization_service = (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=(
                bootstrap_authorization_store
            ),
            customer_identity_registry=(
                chain["identity_registry"]
            ),
        )
    )

    launch_store = CustomerSetupLaunchCredentialStore(
        tmp_path / "p8f4-launch-credentials.json",
        customer_identity_registry=(
            chain["identity_registry"]
        ),
    )
    launch_store.initialize_empty()

    launch_service = CustomerSetupLaunchCredentialService(
        launch_store=launch_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
    )

    now = datetime(
        2026,
        9,
        27,
        8,
        0,
        tzinfo=timezone.utc,
    )

    exchange_service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            access_code_service.authorize
        ),
        issue_bootstrap_authorization=(
            bootstrap_authorization_service.issue
        ),
        clock=lambda: now,
    )

    launch_grant_service = (
        CustomerSetupBootstrapLaunchGrantService(
            bootstrap_authorization_service=(
                bootstrap_authorization_service
            ),
            launch_credential_service=launch_service,
        )
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    activation = completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    assert (
        activation.status
        is CustomerSetupActivationStatus.ACTIVE
    )

    issued_access = access_code_service.issue(
        setup_activation_id=activation.setup_activation_id
    )

    code_verifier = "A" * 43

    code_challenge_s256 = (
        base64.urlsafe_b64encode(
            hashlib.sha256(
                code_verifier.encode("ascii")
            ).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )

    exchange = exchange_service.exchange(
        activation_code=issued_access.activation_code,
        code_challenge_s256=code_challenge_s256,
    )

    assert launch_store.size() == 0

    grant = launch_grant_service.grant(
        authorization_code=exchange.authorization_code,
        code_verifier=code_verifier,
        current_time=now,
    )

    assert (
        grant.customer_id
        == chain["order"].customer_id
    )

    authorization_record = (
        bootstrap_authorization_store.get(
            authorization_id=grant.authorization_id
        )
    )

    assert authorization_record is not None
    assert (
        authorization_record.customer_id
        == chain["order"].customer_id
    )
    assert (
        authorization_record.setup_activation_id
        == activation.setup_activation_id
    )

    assert launch_store.size() == 1

    launch_authorization = launch_service.authorize(
        launch_credential=grant.setup_launch_credential,
        current_time=now,
    )

    assert (
        launch_authorization.customer_id
        == chain["order"].customer_id
    )

def test_vnd_paid_setup_launch_unlocks_authoritative_entry(
    tmp_path,
):
    """
    P8F5 proves that the launch credential originating from an
    authoritative VND-paid activation reaches the real Setup Entry
    owner, resolves the same setup activation through launch
    correlation, and issues a real handoff credential without
    client-supplied customer or activation authority.
    """

    import base64
    import hashlib
    from datetime import datetime, timezone

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f5-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "p8f5-entitlements.json"
    )
    entitlement_registry.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=entitlement_registry,
        )
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f5-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f5-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=activation_bridge,
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    access_code_store = CustomerSetupAccessCodeStore(
        tmp_path / "p8f5-access-codes.json",
        setup_activation_store=activation_store,
    )
    access_code_store.initialize_empty()

    access_code_service = CustomerSetupAccessCodeService(
        access_code_store=access_code_store,
        setup_activation_store=activation_store,
    )

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            tmp_path / "p8f5-bootstrap-authorizations.json",
            customer_identity_registry=(
                chain["identity_registry"]
            ),
        )
    )
    bootstrap_authorization_store.initialize_empty()

    bootstrap_authorization_service = (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=(
                bootstrap_authorization_store
            ),
            customer_identity_registry=(
                chain["identity_registry"]
            ),
        )
    )

    launch_store = CustomerSetupLaunchCredentialStore(
        tmp_path / "p8f5-launch-credentials.json",
        customer_identity_registry=(
            chain["identity_registry"]
        ),
    )
    launch_store.initialize_empty()

    launch_service = CustomerSetupLaunchCredentialService(
        launch_store=launch_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
    )

    registration_store = CustomerRegistrationStore(
        tmp_path / "p8f5-registrations.json"
    )
    registration_store.initialize_empty()

    registration_store.register(
        CustomerRegistrationRecord(
            registration_request_id=(
                "p8f5-authoritative-registration"
            ),
            customer_id=chain["order"].customer_id,
        )
    )

    handoff_store = CustomerSetupHandoffStore(
        tmp_path / "p8f5-handoffs.json"
    )
    handoff_store.initialize_empty()

    handoff_service = CustomerSetupHandoffService(
        handoff_store=handoff_store,
        setup_activation_store=activation_store,
    )

    now = datetime(
        2026,
        9,
        27,
        8,
        0,
        tzinfo=timezone.utc,
    )

    exchange_service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            access_code_service.authorize
        ),
        issue_bootstrap_authorization=(
            bootstrap_authorization_service.issue
        ),
        clock=lambda: now,
    )

    launch_grant_service = (
        CustomerSetupBootstrapLaunchGrantService(
            bootstrap_authorization_service=(
                bootstrap_authorization_service
            ),
            launch_credential_service=launch_service,
        )
    )

    entry_grant_service = CustomerSetupEntryGrantService(
        registration_store=registration_store,
        setup_activation_service=activation_service,
        handoff_service=handoff_service,
        resolve_setup_activation_id=(
            launch_grant_service.resolve_setup_activation_id
        ),
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    activation = completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    assert (
        activation.status
        is CustomerSetupActivationStatus.ACTIVE
    )

    issued_access = access_code_service.issue(
        setup_activation_id=activation.setup_activation_id
    )

    code_verifier = "A" * 43

    code_challenge_s256 = (
        base64.urlsafe_b64encode(
            hashlib.sha256(
                code_verifier.encode("ascii")
            ).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )

    exchange = exchange_service.exchange(
        activation_code=issued_access.activation_code,
        code_challenge_s256=code_challenge_s256,
    )

    launch_grant = launch_grant_service.grant(
        authorization_code=exchange.authorization_code,
        code_verifier=code_verifier,
        current_time=now,
    )

    launch_authorization = launch_service.authorize(
        launch_credential=(
            launch_grant.setup_launch_credential
        ),
        current_time=now,
    )

    assert (
        launch_authorization.customer_id
        == chain["order"].customer_id
    )

    entry_grant = entry_grant_service.grant(
        grant_request_id=(
            launch_authorization.launch_id
        ),
        customer_id=(
            launch_authorization.customer_id
        ),
        current_time=now,
    )

    assert (
        entry_grant.customer_id
        == chain["order"].customer_id
    )
    assert (
        entry_grant.setup_activation_id
        == activation.setup_activation_id
    )

    authoritative_activation = activation_service.get(
        setup_activation_id=(
            entry_grant.setup_activation_id
        )
    )

    assert authoritative_activation is not None
    assert (
        authoritative_activation.customer_id
        == chain["order"].customer_id
    )

    handoff_record = handoff_store.get(
        handoff_id=entry_grant.handoff_id
    )

    assert handoff_record is not None
    assert (
        handoff_record.setup_activation_id
        == activation.setup_activation_id
    )

    handoff_authorization = handoff_service.authorize(
        handoff_credential=(
            entry_grant.handoff_credential
        ),
        current_time=now,
    )

    assert handoff_authorization is not None

def test_vnd_paid_handoff_converges_to_build_continuation_authority(
    tmp_path,
):
    """
    P8F6 proves that the handoff credential originating from the
    authoritative paid Setup Entry path is authorized by the real
    handoff authority owner and converges into the real build
    continuation owner without client-supplied customer or setup
    activation identity.
    """

    import base64
    import hashlib
    from datetime import datetime, timezone

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f6-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "p8f6-entitlements.json"
    )
    entitlement_registry.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=entitlement_registry,
        )
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f6-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f6-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=activation_bridge,
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    access_code_store = CustomerSetupAccessCodeStore(
        tmp_path / "p8f6-access-codes.json",
        setup_activation_store=activation_store,
    )
    access_code_store.initialize_empty()

    access_code_service = CustomerSetupAccessCodeService(
        access_code_store=access_code_store,
        setup_activation_store=activation_store,
    )

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            tmp_path / "p8f6-bootstrap-authorizations.json",
            customer_identity_registry=(
                chain["identity_registry"]
            ),
        )
    )
    bootstrap_authorization_store.initialize_empty()

    bootstrap_authorization_service = (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=(
                bootstrap_authorization_store
            ),
            customer_identity_registry=(
                chain["identity_registry"]
            ),
        )
    )

    launch_store = CustomerSetupLaunchCredentialStore(
        tmp_path / "p8f6-launch-credentials.json",
        customer_identity_registry=(
            chain["identity_registry"]
        ),
    )
    launch_store.initialize_empty()

    launch_service = CustomerSetupLaunchCredentialService(
        launch_store=launch_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
    )

    registration_store = CustomerRegistrationStore(
        tmp_path / "p8f6-registrations.json"
    )
    registration_store.initialize_empty()

    registration_store.register(
        CustomerRegistrationRecord(
            registration_request_id=(
                "p8f6-authoritative-registration"
            ),
            customer_id=chain["order"].customer_id,
        )
    )

    handoff_store = CustomerSetupHandoffStore(
        tmp_path / "p8f6-handoffs.json"
    )
    handoff_store.initialize_empty()

    handoff_service = CustomerSetupHandoffService(
        handoff_store=handoff_store,
        setup_activation_store=activation_store,
    )

    now = datetime(
        2026,
        9,
        27,
        9,
        0,
        tzinfo=timezone.utc,
    )

    handoff_authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=handoff_service,
        clock=lambda: now,
    )

    exchange_service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            access_code_service.authorize
        ),
        issue_bootstrap_authorization=(
            bootstrap_authorization_service.issue
        ),
        clock=lambda: now,
    )

    launch_grant_service = (
        CustomerSetupBootstrapLaunchGrantService(
            bootstrap_authorization_service=(
                bootstrap_authorization_service
            ),
            launch_credential_service=launch_service,
        )
    )

    entry_grant_service = CustomerSetupEntryGrantService(
        registration_store=registration_store,
        setup_activation_service=activation_service,
        handoff_service=handoff_service,
        resolve_setup_activation_id=(
            launch_grant_service.resolve_setup_activation_id
        ),
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    activation = completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    issued_access = access_code_service.issue(
        setup_activation_id=activation.setup_activation_id
    )

    code_verifier = "A" * 43

    code_challenge_s256 = (
        base64.urlsafe_b64encode(
            hashlib.sha256(
                code_verifier.encode("ascii")
            ).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )

    exchange = exchange_service.exchange(
        activation_code=issued_access.activation_code,
        code_challenge_s256=code_challenge_s256,
    )

    launch_grant = launch_grant_service.grant(
        authorization_code=exchange.authorization_code,
        code_verifier=code_verifier,
        current_time=now,
    )

    launch_authorization = launch_service.authorize(
        launch_credential=(
            launch_grant.setup_launch_credential
        ),
        current_time=now,
    )

    entry_grant = entry_grant_service.grant(
        grant_request_id=(
            launch_authorization.launch_id
        ),
        customer_id=(
            launch_authorization.customer_id
        ),
        current_time=now,
    )

    handoff_authorization = (
        handoff_authorizer.authorize(
            entry_grant.handoff_credential
        )
    )

    assert (
        handoff_authorization.customer_id
        == chain["order"].customer_id
    )
    assert (
        handoff_authorization.setup_activation_id
        == activation.setup_activation_id
    )

    deployment_id = "deployment-p8f6"
    account_fingerprint = "P8F6-Test:100001"

    build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            tmp_path / "p8f6-build-requests"
        )
    )
    build_request_store.initialize_empty()

    build_request_store.register(
        CustomerDeploymentPackageBuildRequest(
            deployment_id=deployment_id,
            bootstrap_request_id=(
                activation.setup_activation_id
            ),
        )
    )

    continuation_store = (
        CustomerSetupBuildContinuationStore(
            tmp_path / "p8f6-continuations.json"
        )
    )
    continuation_store.initialize_empty()

    continuation_service = (
        CustomerSetupBuildContinuationService(
            continuation_store=continuation_store,
            setup_activation_store=activation_store,
            build_request_store=build_request_store,
        )
    )

    issued_continuation = continuation_service.issue(
        setup_activation_id=(
            handoff_authorization.setup_activation_id
        ),
        deployment_id=deployment_id,
        account_fingerprint=account_fingerprint,
        current_time=now,
    )

    authorized_continuation = (
        continuation_service.authorize(
            continuation_credential=(
                issued_continuation.continuation_credential
            ),
            account_fingerprint=account_fingerprint,
            current_time=now,
        )
    )

    assert (
        authorized_continuation.customer_id
        == chain["order"].customer_id
    )
    assert (
        authorized_continuation.setup_activation_id
        == activation.setup_activation_id
    )
    assert (
        authorized_continuation.deployment_id
        == deployment_id
    )

def test_authoritative_handoff_crosses_real_provisioning_http_boundary(
    tmp_path,
):
    """
    P8F7 proves that a real authoritative Setup handoff credential
    crosses the actual FastAPI provisioning boundary, derives
    customer/setup identity from server-owned handoff authority,
    registers the immutable build request, and returns real build
    continuation authority without client-supplied identity.
    """

    from datetime import datetime, timezone
    from unittest.mock import Mock

    from backend.commercial.customer_deployment_bootstrap_service import (
        CustomerDeploymentBootstrapPreparationResult,
    )
    from backend.commercial.customer_deployment_registry import (
        CustomerDeployment,
    )
    from backend.commercial.customer_deployment_secret_store import (
        CustomerDeploymentSecrets,
    )

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f7-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f7-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f7-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    entitlement_registry = CustomerCommercialEntitlementRegistry(
        tmp_path / "p8f7-entitlements.json"
    )
    entitlement_registry.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=entitlement_registry,
        )
    )

    activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=activation_bridge,
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    now = datetime(
        2026,
        9,
        27,
        9,
        30,
        tzinfo=timezone.utc,
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    activation = completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    handoff_store = CustomerSetupHandoffStore(
        tmp_path / "p8f7-handoffs.json"
    )
    handoff_store.initialize_empty()

    handoff_service = CustomerSetupHandoffService(
        handoff_store=handoff_store,
        setup_activation_store=activation_store,
    )

    issued_handoff = handoff_service.issue(
        issuance_request_id="p8f7-handoff-request",
        setup_activation_id=activation.setup_activation_id,
        current_time=now,
    )

    handoff_authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=handoff_service,
        clock=lambda: now,
    )

    account_fingerprint = "P8F7-Test:100001"
    deployment_id = "deployment-p8f7"

    build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            tmp_path / "p8f7-build-requests"
        )
    )
    build_request_store.initialize_empty()

    continuation_store = (
        CustomerSetupBuildContinuationStore(
            tmp_path / "p8f7-continuations.json"
        )
    )
    continuation_store.initialize_empty()

    continuation_service = (
        CustomerSetupBuildContinuationService(
            continuation_store=continuation_store,
            setup_activation_store=activation_store,
            build_request_store=build_request_store,
        )
    )

    prepared = CustomerDeploymentBootstrapPreparationResult(
        enrollment_request_id=(
            activation.setup_activation_id
        ),
        deployment=CustomerDeployment(
            customer_id=chain["order"].customer_id,
            deployment_id=deployment_id,
            agent_id="trusted-agent-p8f7",
        ),
        secrets=CustomerDeploymentSecrets(
            deployment_id=deployment_id,
            agent_secret="p8f7-agent-secret",
            execution_mission_signing_secret=(
                "p8f7-execution-secret"
            ),
            control_mission_signing_secret=(
                "p8f7-control-secret"
            ),
        ),
        account_fingerprint=account_fingerprint,
    )

    bootstrap_service = Mock()
    bootstrap_service.prepare_bootstrap.return_value = (
        prepared
    )

    package_publication = Mock()
    package_publication.get_published_package.return_value = (
        None
    )

    # Pending path must not activate deployment entitlement
    # or bind the already-authoritative paid activation.
    http_entitlement_registry = Mock()

    router = create_customer_setup_provisioning_router(
        authorize_setup_handoff=(
            handoff_authorizer.authorize
        ),
        bootstrap_service=bootstrap_service,
        build_request_store=build_request_store,
        package_publication=package_publication,
        entitlement_registry=http_entitlement_registry,
        setup_activation_service=activation_service,
        continuation_service=continuation_service,
        clock=lambda: now,
    )

    app = FastAPI()
    app.include_router(router)

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.post(
        "/customer/setup/provision",
        headers={
            "Authorization": (
                "Bearer "
                + issued_handoff.handoff_credential
            )
        },
        json={
            "account_fingerprint": account_fingerprint
        },
    )

    assert response.status_code == 202

    payload = response.json()

    assert payload["status"] == "build_pending"
    assert "continuation_credential" in payload
    assert "continuation_expires_at" in payload

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"

    registered = build_request_store.get(
        deployment_id=deployment_id
    )

    assert registered is not None
    assert registered.deployment_id == deployment_id
    assert (
        registered.bootstrap_request_id
        == activation.setup_activation_id
    )

    bootstrap_service.prepare_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            activation.setup_activation_id
        ),
        customer_id=chain["order"].customer_id,
        account_fingerprint=account_fingerprint,
    )

    authorized_continuation = (
        continuation_service.authorize(
            continuation_credential=(
                payload["continuation_credential"]
            ),
            account_fingerprint=account_fingerprint,
            current_time=now,
        )
    )

    assert (
        authorized_continuation.customer_id
        == chain["order"].customer_id
    )
    assert (
        authorized_continuation.setup_activation_id
        == activation.setup_activation_id
    )
    assert (
        authorized_continuation.deployment_id
        == deployment_id
    )

    http_entitlement_registry.activate.assert_not_called()

    activation_after_pending = activation_service.get(
        setup_activation_id=activation.setup_activation_id
    )

    assert activation_after_pending is not None
    assert activation_after_pending.status.value == "ACTIVE"
    assert activation_after_pending.deployment_id is None

def test_paid_continuation_reaches_ready_and_binds_activation(
    tmp_path,
):
    """
    P8F8 proves that real continuation authority derived from a
    server-authoritative paid setup activation crosses the actual
    /customer/setup/continue HTTP boundary, recovers the existing
    build, consumes a real published package, activates deployment
    entitlement, binds the paid activation, and returns ready.
    """

    from datetime import datetime, timezone
    from unittest.mock import Mock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.commercial.customer_deployment_bootstrap_service import (
        CustomerDeploymentBootstrapPreparationResult,
        CustomerDeploymentBootstrapResult,
    )
    from backend.commercial.customer_deployment_entitlement_registry import (
        CustomerDeploymentEntitlementRegistry,
    )
    from backend.commercial.customer_deployment_package_publication import (
        CustomerDeploymentPackagePublication,
    )
    from backend.commercial.customer_deployment_registry import (
        CustomerDeployment,
    )
    from backend.commercial.customer_deployment_secret_store import (
        CustomerDeploymentSecrets,
    )

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "p8f8-deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "p8f8-activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=(
            chain["identity_registry"]
        ),
        deployment_registry=deployment_registry,
    )

    terms_store = CustomerCommercialOrderTermsBindingStore(
        tmp_path / "p8f8-order-terms.json"
    )
    terms_store.initialize_empty()

    terms_store.register(
        CustomerCommercialOrderTermsBindingRecord(
            order_id=chain["order"].order_id,
            customer_id=chain["order"].customer_id,
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
        )
    )

    commercial_entitlements = (
        CustomerCommercialEntitlementRegistry(
            tmp_path / "p8f8-commercial-entitlements.json"
        )
    )
    commercial_entitlements.initialize_empty()

    entitlement_convergence_service = (
        CustomerPaymentSettlementEntitlementConvergenceService(
            settlement_store=chain["settlement_store"],
            order_store=chain["order_store"],
            order_terms_store=terms_store,
            entitlement_registry=commercial_entitlements,
        )
    )

    activation_bridge = (
        CustomerPaymentSettlementActivationBridge(
            entitlement_convergence_service=(
                entitlement_convergence_service
            ),
            setup_activation_service=activation_service,
        )
    )

    settlement_orchestration = (
        CustomerPaymentSettlementOrchestrationService(
            settlement_service=chain["settlement_service"],
            activation_bridge=activation_bridge,
        )
    )

    completion_service = (
        CustomerVndBankPaymentCompletionOrchestrationService(
            verification_adapter=chain["verification_adapter"],
            settlement_orchestration_service=(
                settlement_orchestration
            ),
        )
    )

    reconciliation = _confirm_authoritative_vnd_payment(
        chain
    )

    activation = completion_service.complete(
        reconciliation_id=reconciliation.reconciliation_id
    )

    now = datetime(
        2026,
        9,
        27,
        10,
        0,
        tzinfo=timezone.utc,
    )

    deployment_id = "deployment-p8f8"
    account_fingerprint = "P8F8-Test:100002"

    deployment = CustomerDeployment(
        customer_id=chain["order"].customer_id,
        deployment_id=deployment_id,
        agent_id="trusted-agent-p8f8",
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret="p8f8-agent-secret",
        execution_mission_signing_secret=(
            "p8f8-execution-secret"
        ),
        control_mission_signing_secret=(
            "p8f8-control-secret"
        ),
    )

    prepared = CustomerDeploymentBootstrapPreparationResult(
        enrollment_request_id=(
            activation.setup_activation_id
        ),
        deployment=deployment,
        secrets=secrets,
        account_fingerprint=account_fingerprint,
    )

    activated = CustomerDeploymentBootstrapResult(
        enrollment_request_id=(
            activation.setup_activation_id
        ),
        deployment=deployment,
        secrets=secrets,
        account_fingerprint=account_fingerprint,
        projected_deployment_count=1,
    )

    build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            tmp_path / "p8f8-build-requests"
        )
    )
    build_request_store.initialize_empty()

    build_request_store.register(
        CustomerDeploymentPackageBuildRequest(
            deployment_id=deployment_id,
            bootstrap_request_id=(
                activation.setup_activation_id
            ),
        )
    )

    continuation_store = (
        CustomerSetupBuildContinuationStore(
            tmp_path / "p8f8-continuations.json"
        )
    )
    continuation_store.initialize_empty()

    continuation_service = (
        CustomerSetupBuildContinuationService(
            continuation_store=continuation_store,
            setup_activation_store=activation_store,
            build_request_store=build_request_store,
        )
    )

    issued_continuation = continuation_service.issue(
        setup_activation_id=(
            activation.setup_activation_id
        ),
        deployment_id=deployment_id,
        account_fingerprint=account_fingerprint,
        current_time=now,
    )

    bootstrap_service = Mock()
    bootstrap_service.recover_prepared_bootstrap.return_value = (
        prepared
    )

    def activate_bootstrap(**kwargs):
        assert kwargs == {
            "enrollment_request_id": (
                activation.setup_activation_id
            ),
            "customer_id": chain["order"].customer_id,
            "account_fingerprint": account_fingerprint,
        }

        deployment_registry.register(
            deployment
        )

        return activated

    bootstrap_service.activate_bootstrap.side_effect = (
        activate_bootstrap
    )

    package_root = tmp_path / "p8f8-packages"

    package_publication = (
        CustomerDeploymentPackagePublication(
            package_root=package_root
        )
    )

    package_directory = (
        package_publication.package_directory(
            deployment_id=deployment_id
        )
    )
    package_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    artifact = package_publication.artifact_path(
        deployment_id=deployment_id
    )
    artifact.write_bytes(
        b"P8F8-READY-EX5"
    )

    published = (
        package_publication.get_published_package(
            deployment_id=deployment_id
        )
    )

    assert published is not None
    assert published.deployment_id == deployment_id

    deployment_entitlements = (
        CustomerDeploymentEntitlementRegistry(
            tmp_path / "p8f8-deployment-entitlements.json",
            deployment_registry=deployment_registry,
        )
    )
    deployment_entitlements.initialize_empty()

    router = create_customer_setup_provisioning_router(
        authorize_setup_handoff=Mock(
            side_effect=AssertionError(
                "Handoff authority must not be used by continuation."
            )
        ),
        bootstrap_service=bootstrap_service,
        build_request_store=build_request_store,
        package_publication=package_publication,
        entitlement_registry=deployment_entitlements,
        setup_activation_service=activation_service,
        continuation_service=continuation_service,
        clock=lambda: now,
    )

    app = FastAPI()
    app.include_router(router)

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.post(
        "/customer/setup/continue",
        headers={
            "Authorization": (
                "Bearer "
                + issued_continuation.continuation_credential
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "status": "ready",
        "artifact_sha256": published.artifact_sha256,
        "artifact_size_bytes": (
            published.artifact_size_bytes
        ),
    }

    assert deployment_entitlements.is_active(
        deployment_id=deployment_id
    )

    bound = activation_service.get(
        setup_activation_id=activation.setup_activation_id
    )

    assert bound is not None
    assert bound.status.value == "BOUND"
    assert bound.customer_id == chain["order"].customer_id
    assert bound.deployment_id == deployment_id

    bootstrap_service.recover_prepared_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            activation.setup_activation_id
        )
    )

    bootstrap_service.activate_bootstrap.assert_called_once()

    assert (
        build_request_store.get(
            deployment_id=deployment_id
        ).bootstrap_request_id
        == activation.setup_activation_id
    )

    # Same continuation after successful bind must be read-only.
    bootstrap_service.reset_mock()

    retry = client.post(
        "/customer/setup/continue",
        headers={
            "Authorization": (
                "Bearer "
                + issued_continuation.continuation_credential
            )
        },
    )

    assert retry.status_code == 200
    assert retry.json() == payload

    bootstrap_service.recover_prepared_bootstrap.assert_not_called()
    bootstrap_service.activate_bootstrap.assert_not_called()

    rebound = activation_service.get(
        setup_activation_id=activation.setup_activation_id
    )

    assert rebound is not None
    assert rebound.status.value == "BOUND"
    assert rebound.deployment_id == deployment_id

def test_payment_setup_security_boundaries_converge_fail_closed(
    tmp_path,
):
    """
    P8F9 closes the payment-to-Setup security convergence:
    payment mismatch/replay cannot manufacture downstream authority,
    client-supplied Setup identity is rejected at the HTTP boundary,
    and forged continuation authority cannot reach bootstrap recovery.
    """

    from datetime import datetime, timezone
    from unittest.mock import Mock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    chain = _build_dynamic_vnd_commercial_chain(
        tmp_path
    )

    # Payment amount mismatch must die before trusted evidence,
    # settlement, or activation authority exists.
    with pytest.raises(ValueError):
        _confirm_authoritative_vnd_payment(
            chain,
            reconciliation_request_id=(
                "p8f9-wrong-amount"
            ),
            bank_reference="VCB-P8F9-WRONG-AMOUNT",
            amount_minor=1,
        )

    assert _store_size(
        chain["evidence_store"]
    ) == 0

    assert _store_size(
        chain["settlement_store"]
    ) == 0

    assert chain["activation_bridge"].calls == []

    # One authoritative reconciliation may succeed.
    first = _confirm_authoritative_vnd_payment(
        chain,
        reconciliation_request_id=(
            "p8f9-authoritative-payment"
        ),
        bank_reference="VCB-P8F9-REPLAY",
    )

    assert first is not None

    assert _store_size(
        chain["evidence_store"]
    ) == 1

    # The same external bank reference cannot create a second
    # reconciliation/evidence path under another request id.
    with pytest.raises(ValueError):
        _confirm_authoritative_vnd_payment(
            chain,
            reconciliation_request_id=(
                "p8f9-replayed-payment"
            ),
            bank_reference="VCB-P8F9-REPLAY",
        )

    assert _store_size(
        chain["evidence_store"]
    ) == 1

    # Setup provisioning HTTP must reject customer-controlled
    # authority before any server authorizer is reached.
    authorizer = Mock()
    bootstrap_service = Mock()
    build_request_store = Mock()
    package_publication = Mock()
    entitlement_registry = Mock()
    setup_activation_service = Mock()

    router = create_customer_setup_provisioning_router(
        authorize_setup_handoff=authorizer,
        bootstrap_service=bootstrap_service,
        build_request_store=build_request_store,
        package_publication=package_publication,
        entitlement_registry=entitlement_registry,
        setup_activation_service=(
            setup_activation_service
        ),
        continuation_service=None,
        clock=lambda: datetime(
            2026,
            9,
            27,
            10,
            30,
            tzinfo=timezone.utc,
        ),
    )

    app = FastAPI()
    app.include_router(router)

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    forged = client.post(
        "/customer/setup/provision",
        headers={
            "Authorization": "Bearer forged-handoff"
        },
        json={
            "account_fingerprint": "P8F9-Test:100003",
            "customer_id": "forged-customer",
            "setup_activation_id": "forged-activation",
            "deployment_id": "forged-deployment",
            "agent_id": "forged-agent",
        },
    )

    assert forged.status_code == 422
    authorizer.assert_not_called()
    bootstrap_service.prepare_bootstrap.assert_not_called()
    build_request_store.register.assert_not_called()

    # A continuation owner exists, but forged continuation material
    # must fail before any bootstrap state can be recovered.
    continuation_service = Mock()
    continuation_service.authorize.side_effect = (
        ValueError("invalid continuation")
    )

    guarded_router = (
        create_customer_setup_provisioning_router(
            authorize_setup_handoff=Mock(),
            bootstrap_service=bootstrap_service,
            build_request_store=build_request_store,
            package_publication=package_publication,
            entitlement_registry=entitlement_registry,
            setup_activation_service=(
                setup_activation_service
            ),
            continuation_service=continuation_service,
            clock=lambda: datetime(
                2026,
                9,
                27,
                10,
                31,
                tzinfo=timezone.utc,
            ),
        )
    )

    guarded_app = FastAPI()
    guarded_app.include_router(
        guarded_router
    )

    guarded_client = TestClient(
        guarded_app,
        raise_server_exceptions=False,
    )

    invalid_continue = guarded_client.post(
        "/customer/setup/continue",
        headers={
            "Authorization": (
                "Bearer forged-continuation"
            )
        },
    )

    assert invalid_continue.status_code == 401

    bootstrap_service.recover_prepared_bootstrap.assert_not_called()
    bootstrap_service.activate_bootstrap.assert_not_called()
    build_request_store.register.assert_not_called()
    entitlement_registry.activate.assert_not_called()
    setup_activation_service.bind.assert_not_called()
