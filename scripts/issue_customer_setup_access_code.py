from pathlib import Path

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeIssuance,
    CustomerSetupAccessCodeService,
    CustomerSetupAccessCodeStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationService,
    CustomerSetupActivationStore,
)


def issue_customer_setup_access_code(
    *,
    control_plane_root: Path,
    activation_request_id: str,
    customer_id: str,
    confirm_runtime_stopped: bool,
) -> CustomerSetupAccessCodeIssuance:
    """
    Issue one customer-visible Setup Activation Code through
    authoritative durable commercial state.

    This is an operator-only boundary. It must never initialize
    missing production state and must never silently rotate an
    already-active customer access code.
    """

    if not isinstance(control_plane_root, Path):
        raise TypeError(
            "control_plane_root must be Path."
        )

    if (
        not isinstance(activation_request_id, str)
        or not activation_request_id.strip()
    ):
        raise ValueError(
            "activation_request_id must be non-empty."
        )

    if (
        not isinstance(customer_id, str)
        or not customer_id.strip()
    ):
        raise ValueError(
            "customer_id must be non-empty."
        )

    if confirm_runtime_stopped is not True:
        raise RuntimeError(
            "Production runtime must be confirmed stopped "
            "before issuing a Setup Activation Code."
        )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    customer_identity_registry = (
        CustomerIdentityRegistry(
            commercial_root
            / "customer_identities.json"
        )
    )

    if not customer_identity_registry.is_ready():
        raise RuntimeError(
            "Customer identity registry is not provisioned."
        )

    if not customer_identity_registry.contains(
        customer_id=customer_id
    ):
        raise ValueError(
            "Customer identity is not registered."
        )

    deployment_registry = (
        CustomerDeploymentRegistry(
            commercial_root
            / "customer_deployments.json"
        )
    )

    if not deployment_registry.is_ready():
        raise RuntimeError(
            "Customer deployment registry is not provisioned."
        )

    activation_store = (
        CustomerSetupActivationStore(
            commercial_root
            / "customer_setup_activations.json"
        )
    )

    if not activation_store.is_ready():
        raise RuntimeError(
            "Customer setup activation store is not provisioned."
        )

    access_code_store = (
        CustomerSetupAccessCodeStore(
            commercial_root
            / "customer_setup_access_codes.json",
            setup_activation_store=activation_store,
        )
    )

    if not access_code_store.is_ready():
        raise RuntimeError(
            "Customer setup access code store is not provisioned."
        )

    activation_service = (
        CustomerSetupActivationService(
            activation_store=activation_store,
            customer_identity_registry=(
                customer_identity_registry
            ),
            deployment_registry=(
                deployment_registry
            ),
        )
    )

    activation = activation_service.activate(
        activation_request_id=(
            activation_request_id
        ),
        customer_id=customer_id,
    )

    existing_code = (
        access_code_store
        .get_active_by_setup_activation_id(
            setup_activation_id=(
                activation.setup_activation_id
            )
        )
    )

    if existing_code is not None:
        raise RuntimeError(
            "An active Setup Activation Code already exists "
            "for this Setup Activation; refusing rotation."
        )

    access_code_service = (
        CustomerSetupAccessCodeService(
            access_code_store=access_code_store,
            setup_activation_store=activation_store,
        )
    )

    return access_code_service.issue(
        setup_activation_id=(
            activation.setup_activation_id
        )
    )
