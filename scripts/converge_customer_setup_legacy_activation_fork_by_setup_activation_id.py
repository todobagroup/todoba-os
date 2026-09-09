from pathlib import Path

from scripts.converge_customer_setup_legacy_activation_fork import (
    CustomerDeploymentBootstrapStore,
    CustomerDeploymentRegistry,
    CustomerIdentityRegistry,
    CustomerSetupAccessCodeStore,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
    CustomerSetupBootstrapAuthorizationStore,
    CustomerSetupLaunchCredentialStore,
    CustomerSetupLegacyActivationForkConvergenceResult,
    _require_store_ready,
    derive_customer_setup_bootstrap_launch_issuance_request_id,
)


def converge_customer_setup_legacy_activation_fork_by_setup_activation_id(
    *,
    control_plane_root: Path,
    setup_activation_id: str,
    confirm_runtime_stopped: bool,
) -> CustomerSetupLegacyActivationForkConvergenceResult:
    """
    Converge one provable legacy Setup activation fork using the
    authoritative durable Setup Activation identity.

    This operator-only recovery boundary exists for cases where the
    original plaintext Access Code is no longer available. It still
    requires an ACTIVE durable Access Code binding for the supplied
    Setup Activation and derives every other identity from production
    state.
    """

    if not isinstance(control_plane_root, Path):
        raise TypeError("control_plane_root must be Path.")

    if (
        not isinstance(setup_activation_id, str)
        or not setup_activation_id.strip()
    ):
        raise ValueError("setup_activation_id must be non-empty.")

    normalized_setup_activation_id = setup_activation_id.strip()

    if normalized_setup_activation_id != setup_activation_id:
        raise ValueError("setup_activation_id must be normalized.")

    # Must happen before any production state is opened.
    if confirm_runtime_stopped is not True:
        raise RuntimeError(
            "Production runtime must be confirmed stopped "
            "before legacy Setup activation convergence."
        )

    commercial_root = control_plane_root / "commercial"

    customer_identity_registry = CustomerIdentityRegistry(
        commercial_root / "customer_identities.json"
    )
    _require_store_ready(
        customer_identity_registry,
        owner_name="Customer identity registry",
    )

    deployment_registry = CustomerDeploymentRegistry(
        commercial_root / "customer_deployments.json"
    )
    _require_store_ready(
        deployment_registry,
        owner_name="Customer deployment registry",
    )

    activation_store = CustomerSetupActivationStore(
        commercial_root / "customer_setup_activations.json"
    )
    _require_store_ready(
        activation_store,
        owner_name="Customer setup activation store",
    )

    access_code_store = CustomerSetupAccessCodeStore(
        commercial_root / "customer_setup_access_codes.json",
        setup_activation_store=activation_store,
    )
    _require_store_ready(
        access_code_store,
        owner_name="Customer setup access code store",
    )

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            commercial_root
            / "customer_setup_bootstrap_authorizations.json",
            customer_identity_registry=customer_identity_registry,
        )
    )
    _require_store_ready(
        bootstrap_authorization_store,
        owner_name="Customer setup bootstrap authorization store",
    )

    launch_store = CustomerSetupLaunchCredentialStore(
        commercial_root / "customer_setup_launch_credentials.json",
        customer_identity_registry=customer_identity_registry,
    )
    _require_store_ready(
        launch_store,
        owner_name="Customer setup launch credential store",
    )

    deployment_bootstrap_store = CustomerDeploymentBootstrapStore(
        commercial_root / "customer_deployment_bootstraps.json"
    )
    _require_store_ready(
        deployment_bootstrap_store,
        owner_name="Customer deployment bootstrap store",
    )

    authoritative_activation = activation_store.get(
        setup_activation_id=normalized_setup_activation_id
    )
    if authoritative_activation is None:
        raise RuntimeError(
            "Authoritative Setup Activation does not exist."
        )

    active_access_code = (
        access_code_store.get_active_by_setup_activation_id(
            setup_activation_id=normalized_setup_activation_id
        )
    )
    if active_access_code is None:
        raise RuntimeError(
            "Authoritative Setup Activation has no active "
            "durable Access Code binding."
        )

    customer_id = authoritative_activation.customer_id

    if not customer_identity_registry.contains(
        customer_id=customer_id
    ):
        raise RuntimeError(
            "Authorized customer identity does not exist."
        )

    if authoritative_activation.status not in {
        CustomerSetupActivationStatus.ACTIVE,
        CustomerSetupActivationStatus.BOUND,
    }:
        raise RuntimeError(
            "Authoritative Setup Activation is not eligible "
            "for legacy convergence."
        )

    candidates = []

    for bootstrap_authorization in (
        bootstrap_authorization_store.all()
    ):
        if bootstrap_authorization.setup_activation_id is not None:
            continue
        if bootstrap_authorization.customer_id != customer_id:
            continue

        launch_issuance_request_id = (
            derive_customer_setup_bootstrap_launch_issuance_request_id(
                bootstrap_authorization.authorization_id
            )
        )
        launch = launch_store.get_by_issuance_request_id(
            issuance_request_id=launch_issuance_request_id
        )
        if launch is None:
            continue
        if launch.customer_id != customer_id:
            raise RuntimeError(
                "Legacy launch customer identity did not converge."
            )

        legacy_activation = (
            activation_store.get_by_activation_request_id(
                activation_request_id=launch.launch_id
            )
        )
        if legacy_activation is None:
            continue
        if (
            legacy_activation.setup_activation_id
            == authoritative_activation.setup_activation_id
        ):
            continue
        if legacy_activation.customer_id != customer_id:
            raise RuntimeError(
                "Legacy Setup Activation customer identity "
                "did not converge."
            )
        if legacy_activation.status not in {
            CustomerSetupActivationStatus.BOUND,
            CustomerSetupActivationStatus.SUPERSEDED,
        }:
            continue

        deployment_id = legacy_activation.deployment_id
        if deployment_id is None:
            raise RuntimeError(
                "Legacy consumed Setup Activation has no "
                "deployment identity."
            )

        deployment = deployment_registry.get(
            deployment_id=deployment_id
        )
        if deployment is None:
            raise RuntimeError(
                "Legacy Setup deployment does not exist."
            )
        if deployment.customer_id != customer_id:
            raise RuntimeError(
                "Legacy deployment customer identity "
                "did not converge."
            )

        deployment_bootstrap = deployment_bootstrap_store.get(
            enrollment_request_id=legacy_activation.setup_activation_id
        )
        if deployment_bootstrap is None:
            continue
        if (
            deployment_bootstrap.customer_id != customer_id
            or deployment_bootstrap.deployment_id != deployment_id
            or deployment_bootstrap.agent_id != deployment.agent_id
        ):
            raise RuntimeError(
                "Legacy deployment bootstrap identity "
                "did not converge."
            )

        current_owner = activation_store.get_by_deployment_id(
            deployment_id=deployment_id
        )
        if current_owner is None:
            raise RuntimeError(
                "Deployment has no Setup Activation owner."
            )
        if current_owner.setup_activation_id not in {
            legacy_activation.setup_activation_id,
            authoritative_activation.setup_activation_id,
        }:
            raise RuntimeError(
                "Deployment is owned by an unrelated "
                "Setup Activation."
            )

        candidates.append(
            (
                bootstrap_authorization,
                launch,
                legacy_activation,
                deployment,
            )
        )

    if not candidates:
        raise RuntimeError(
            "No provable legacy Setup activation fork was "
            "found for this Setup Activation."
        )

    if len(candidates) != 1:
        raise RuntimeError(
            "Legacy Setup activation fork lineage is ambiguous."
        )

    (
        bootstrap_authorization,
        launch,
        legacy_activation,
        deployment,
    ) = candidates[0]

    converged = activation_store.converge_legacy_fork(
        authoritative_setup_activation_id=(
            authoritative_activation.setup_activation_id
        ),
        superseded_setup_activation_id=(
            legacy_activation.setup_activation_id
        ),
        deployment_id=deployment.deployment_id,
    )

    if (
        converged.status is not CustomerSetupActivationStatus.BOUND
        or converged.deployment_id != deployment.deployment_id
    ):
        raise RuntimeError(
            "Legacy Setup activation convergence did not "
            "finish BOUND."
        )

    return CustomerSetupLegacyActivationForkConvergenceResult(
        customer_id=customer_id,
        authoritative_setup_activation_id=(
            authoritative_activation.setup_activation_id
        ),
        superseded_setup_activation_id=(
            legacy_activation.setup_activation_id
        ),
        deployment_id=deployment.deployment_id,
        authorization_id=bootstrap_authorization.authorization_id,
        launch_id=launch.launch_id,
    )
