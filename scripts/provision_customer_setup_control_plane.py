"""
Offline first-provisioning owner for TODOBA customer setup
control-plane durable state.

This script exists only to initialize the authoritative
durable domains required by the customer setup and customer
package-build flow:

- customer_registrations.json
- customer_setup_activations.json
- customer_setup_access_codes.json
- customer_vps_connect_grants.json
- customer_setup_handoffs.json
- customer_setup_launch_credentials.json
- customer_setup_bootstrap_authorizations.json
- customer_deployment_bootstraps.json
- customer_deployment_package_build_requests/
- customer_commercial_orders.json
- customer_payment_intents.json
- customer_payment_evidence.json
- customer_payment_settlements.json
- customer_paypal_order_bindings.json
- customer_vnd_bank_reconciliations.json

Safety contract:
- runtime must be explicitly confirmed stopped
- existing valid durable state is preserved
- missing stores are initialized empty
- retries are idempotent
- no customer registration is created
- no setup activation is granted
- no setup handoff credential is issued
- no setup launch credential is issued
- no setup bootstrap authorization is issued
- no customer package build request is registered
- no customer, deployment, account, payment record, package,
  secret, entitlement, or runtime state is created or mutated
- payment provisioning creates only empty durable substrate
- package-build lock state is not provisioned here because it
  is synchronization state owned by the lock manager
- cloud runtime must never call this provisioning helper
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStore,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceStore,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementStore,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingStore,
)
from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationStore,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeStore,
)
from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantStore,
)
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationStore,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffStore,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationStore,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchCredentialStore,
)


_CUSTOMER_IDENTITY_FILENAME = (
    "customer_identities.json"
)

_CUSTOMER_REGISTRATION_FILENAME = (
    "customer_registrations.json"
)

_CUSTOMER_SETUP_ACTIVATION_FILENAME = (
    "customer_setup_activations.json"
)

_CUSTOMER_SETUP_ACCESS_CODE_FILENAME = (
    "customer_setup_access_codes.json"
)

_CUSTOMER_VPS_CONNECT_GRANT_FILENAME = (
    "customer_vps_connect_grants.json"
)

_CUSTOMER_SETUP_HANDOFF_FILENAME = (
    "customer_setup_handoffs.json"
)

_CUSTOMER_SETUP_BUILD_CONTINUATION_FILENAME = (
    "customer_setup_build_continuations.json"
)

_CUSTOMER_SETUP_LAUNCH_CREDENTIAL_FILENAME = (
    "customer_setup_launch_credentials.json"
)

_CUSTOMER_SETUP_BOOTSTRAP_AUTHORIZATION_FILENAME = (
    "customer_setup_bootstrap_authorizations.json"
)

_CUSTOMER_DEPLOYMENT_BOOTSTRAP_FILENAME = (
    "customer_deployment_bootstraps.json"
)

_CUSTOMER_PACKAGE_BUILD_REQUEST_DIRECTORY = (
    "customer_deployment_package_build_requests"
)

_CUSTOMER_COMMERCIAL_ORDER_FILENAME = (
    "customer_commercial_orders.json"
)

_CUSTOMER_PAYMENT_INTENT_FILENAME = (
    "customer_payment_intents.json"
)

_CUSTOMER_PAYMENT_EVIDENCE_FILENAME = (
    "customer_payment_evidence.json"
)

_CUSTOMER_PAYMENT_SETTLEMENT_FILENAME = (
    "customer_payment_settlements.json"
)

_CUSTOMER_PAYPAL_ORDER_BINDING_FILENAME = (
    "customer_paypal_order_bindings.json"
)

_CUSTOMER_VND_BANK_RECONCILIATION_FILENAME = (
    "customer_vnd_bank_reconciliations.json"
)


def provision_customer_setup_control_plane(
    *,
    control_plane_root: Path,
    confirm_runtime_stopped: bool,
) -> tuple[
    Path,
    Path,
    Path,
    Path,
    Path,
]:
    """
    Initialize missing customer setup durable stores and the
    immutable customer package-build request queue.

    Existing valid state is loaded and preserved.

    This function does not create setup rights, credentials,
    or package-build requests.
    """

    if not isinstance(
        control_plane_root,
        Path,
    ):
        raise TypeError(
            "control_plane_root must be Path."
        )

    if confirm_runtime_stopped is not True:
        raise RuntimeError(
            "Customer setup control-plane provisioning "
            "requires explicit confirmation that TODOBA "
            "runtime is stopped."
        )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    identity_storage_path = (
        commercial_root
        / _CUSTOMER_IDENTITY_FILENAME
    )

    registration_storage_path = (
        commercial_root
        / _CUSTOMER_REGISTRATION_FILENAME
    )

    activation_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_ACTIVATION_FILENAME
    )

    access_code_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_ACCESS_CODE_FILENAME
    )

    vps_connect_grant_storage_path = (
        commercial_root
        / _CUSTOMER_VPS_CONNECT_GRANT_FILENAME
    )

    handoff_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_HANDOFF_FILENAME
    )

    continuation_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_BUILD_CONTINUATION_FILENAME
    )

    launch_credential_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_LAUNCH_CREDENTIAL_FILENAME
    )

    bootstrap_authorization_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_BOOTSTRAP_AUTHORIZATION_FILENAME
    )

    bootstrap_storage_path = (
        commercial_root
        / _CUSTOMER_DEPLOYMENT_BOOTSTRAP_FILENAME
    )

    package_build_request_storage_root = (
        commercial_root
        / _CUSTOMER_PACKAGE_BUILD_REQUEST_DIRECTORY
    )

    commercial_order_storage_path = (
        commercial_root
        / _CUSTOMER_COMMERCIAL_ORDER_FILENAME
    )

    payment_intent_storage_path = (
        commercial_root
        / _CUSTOMER_PAYMENT_INTENT_FILENAME
    )

    payment_evidence_storage_path = (
        commercial_root
        / _CUSTOMER_PAYMENT_EVIDENCE_FILENAME
    )

    payment_settlement_storage_path = (
        commercial_root
        / _CUSTOMER_PAYMENT_SETTLEMENT_FILENAME
    )

    paypal_order_binding_storage_path = (
        commercial_root
        / _CUSTOMER_PAYPAL_ORDER_BINDING_FILENAME
    )

    vnd_bank_reconciliation_storage_path = (
        commercial_root
        / _CUSTOMER_VND_BANK_RECONCILIATION_FILENAME
    )

    customer_identity_registry = (
        CustomerIdentityRegistry(
            identity_storage_path
        )
    )

    if not customer_identity_registry.is_ready():
        raise RuntimeError(
            "Customer identity registry must already "
            "exist before customer setup control-plane "
            "provisioning."
        )

    registration_store = (
        CustomerRegistrationStore(
            registration_storage_path
        )
    )

    activation_store = (
        CustomerSetupActivationStore(
            activation_storage_path
        )
    )

    handoff_store = (
        CustomerSetupHandoffStore(
            handoff_storage_path
        )
    )

    continuation_store = (
        CustomerSetupBuildContinuationStore(
            continuation_storage_path
        )
    )

    launch_credential_store = (
        CustomerSetupLaunchCredentialStore(
            launch_credential_storage_path,
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            bootstrap_authorization_storage_path,
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            bootstrap_storage_path
        )
    )

    package_build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            package_build_request_storage_root
        )
    )

    commercial_order_store = CustomerCommercialOrderStore(
        commercial_order_storage_path
    )

    payment_intent_store = CustomerPaymentIntentStore(
        payment_intent_storage_path
    )

    payment_evidence_store = CustomerPaymentEvidenceStore(
        payment_evidence_storage_path
    )

    payment_settlement_store = CustomerPaymentSettlementStore(
        payment_settlement_storage_path
    )

    paypal_order_binding_store = CustomerPayPalOrderBindingStore(
        paypal_order_binding_storage_path
    )

    vnd_bank_reconciliation_store = (
        CustomerVndBankReconciliationStore(
            vnd_bank_reconciliation_storage_path
        )
    )

    if not registration_store.is_ready():
        registration_store.initialize_empty()

    if not activation_store.is_ready():
        activation_store.initialize_empty()

    access_code_store = (
        CustomerSetupAccessCodeStore(
            access_code_storage_path,
            setup_activation_store=(
                activation_store
            ),
        )
    )

    if not access_code_store.is_ready():
        access_code_store.initialize_empty()

    vps_connect_grant_store = (
        CustomerVPSConnectGrantStore(
            vps_connect_grant_storage_path
        )
    )

    if vps_connect_grant_storage_path.exists():
        vps_connect_grant_store.open_existing()
    else:
        vps_connect_grant_store.initialize_empty()

    if not vps_connect_grant_store.is_ready():
        raise RuntimeError(
            "Customer VPS Connect grant store did not "
            "become ready."
        )

    if not handoff_store.is_ready():
        handoff_store.initialize_empty()

    if not continuation_store.is_ready:
        continuation_store.initialize_empty()

    if launch_credential_storage_path.exists():
        launch_credential_store.open_existing()
    else:
        launch_credential_store.initialize_empty()

    if bootstrap_authorization_storage_path.exists():
        bootstrap_authorization_store.open_existing()
    else:
        bootstrap_authorization_store.initialize_empty()

    if not bootstrap_store.is_ready():
        bootstrap_store.initialize_empty()

    if not package_build_request_store.is_ready():
        package_build_request_store.initialize_empty()

    if not commercial_order_store.is_ready():
        commercial_order_store.initialize_empty()

    if not payment_intent_store.is_ready():
        payment_intent_store.initialize_empty()

    if not payment_evidence_store.is_ready():
        payment_evidence_store.initialize_empty()

    if not payment_settlement_store.is_ready():
        payment_settlement_store.initialize_empty()

    if not paypal_order_binding_store.is_ready():
        paypal_order_binding_store.initialize_empty()

    if vnd_bank_reconciliation_storage_path.exists():
        vnd_bank_reconciliation_store.open_existing()
    else:
        vnd_bank_reconciliation_store.initialize_empty()

    if not registration_store.is_ready():
        raise RuntimeError(
            "Customer registration store did not "
            "become ready."
        )

    if not activation_store.is_ready():
        raise RuntimeError(
            "Customer setup activation store did not "
            "become ready."
        )

    if not access_code_store.is_ready():
        raise RuntimeError(
            "Customer setup access code store did not "
            "become ready."
        )

    if not handoff_store.is_ready():
        raise RuntimeError(
            "Customer setup handoff store did not "
            "become ready."
        )

    if not continuation_store.is_ready:
        raise RuntimeError(
            "Customer setup build continuation store "
            "did not become ready."
        )

    if not launch_credential_store.is_ready():
        raise RuntimeError(
            "Customer setup launch credential store did "
            "not become ready."
        )

    if not bootstrap_authorization_store.is_ready():
        raise RuntimeError(
            "Customer setup bootstrap authorization "
            "store did not become ready."
        )

    if not bootstrap_store.is_ready():
        raise RuntimeError(
            "Customer deployment bootstrap store did not "
            "become ready."
        )

    if not package_build_request_store.is_ready():
        raise RuntimeError(
            "Customer deployment package build request "
            "store did not become ready."
        )

    if not commercial_order_store.is_ready():
        raise RuntimeError(
            "Customer commercial order store did not become ready."
        )

    if not payment_intent_store.is_ready():
        raise RuntimeError(
            "Customer payment intent store did not become ready."
        )

    if not payment_evidence_store.is_ready():
        raise RuntimeError(
            "Customer payment evidence store did not become ready."
        )

    if not payment_settlement_store.is_ready():
        raise RuntimeError(
            "Customer payment settlement store did not become ready."
        )

    if not paypal_order_binding_store.is_ready():
        raise RuntimeError(
            "Customer PayPal order binding store did not become ready."
        )

    if not vnd_bank_reconciliation_store.is_ready():
        raise RuntimeError(
            "Customer VND bank reconciliation store did not become ready."
        )

    return (
        activation_storage_path,
        handoff_storage_path,
        bootstrap_storage_path,
        package_build_request_storage_root,
        registration_storage_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision TODOBA customer setup durable "
            "control-plane state."
        )
    )

    parser.add_argument(
        "--control-plane-root",
        required=True,
        type=Path,
        help=(
            "TODOBA control-plane data root containing "
            "the commercial directory."
        ),
    )

    parser.add_argument(
        "--confirm-runtime-stopped",
        action="store_true",
        required=True,
        help=(
            "Explicit operator confirmation that TODOBA "
            "runtime is stopped."
        ),
    )

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    (
        activation_storage_path,
        handoff_storage_path,
        bootstrap_storage_path,
        package_build_request_storage_root,
        registration_storage_path,
    ) = provision_customer_setup_control_plane(
        control_plane_root=(
            args.control_plane_root
        ),
        confirm_runtime_stopped=(
            args.confirm_runtime_stopped
        ),
    )

    print(
        "CUSTOMER_REGISTRATION_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_ACTIVATION_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_ACCESS_CODE_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_HANDOFF_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_BUILD_CONTINUATION_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_LAUNCH_CREDENTIAL_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_BOOTSTRAP_AUTHORIZATION_STORE=READY"
    )

    print(
        "CUSTOMER_DEPLOYMENT_BOOTSTRAP_STORE=READY"
    )

    print(
        "CUSTOMER_PACKAGE_BUILD_REQUEST_STORE=READY"
    )

    print(
        "CUSTOMER_REGISTRATION_PATH="
        f"{registration_storage_path}"
    )

    print(
        "CUSTOMER_SETUP_ACTIVATION_PATH="
        f"{activation_storage_path}"
    )

    access_code_storage_path = (
        args.control_plane_root
        / "commercial"
        / _CUSTOMER_SETUP_ACCESS_CODE_FILENAME
    )

    print(
        "CUSTOMER_SETUP_ACCESS_CODE_PATH="
        f"{access_code_storage_path}"
    )

    print(
        "CUSTOMER_SETUP_HANDOFF_PATH="
        f"{handoff_storage_path}"
    )

    continuation_storage_path = (
        args.control_plane_root
        / "commercial"
        / _CUSTOMER_SETUP_BUILD_CONTINUATION_FILENAME
    )

    print(
        "CUSTOMER_SETUP_BUILD_CONTINUATION_PATH="
        f"{continuation_storage_path}"
    )

    launch_credential_storage_path = (
        args.control_plane_root
        / "commercial"
        / _CUSTOMER_SETUP_LAUNCH_CREDENTIAL_FILENAME
    )

    print(
        "CUSTOMER_SETUP_LAUNCH_CREDENTIAL_PATH="
        f"{launch_credential_storage_path}"
    )

    bootstrap_authorization_storage_path = (
        args.control_plane_root
        / "commercial"
        / _CUSTOMER_SETUP_BOOTSTRAP_AUTHORIZATION_FILENAME
    )

    print(
        "CUSTOMER_SETUP_BOOTSTRAP_AUTHORIZATION_PATH="
        f"{bootstrap_authorization_storage_path}"
    )

    print(
        "CUSTOMER_DEPLOYMENT_BOOTSTRAP_PATH="
        f"{bootstrap_storage_path}"
    )

    print(
        "CUSTOMER_PACKAGE_BUILD_REQUEST_ROOT="
        f"{package_build_request_storage_root}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
