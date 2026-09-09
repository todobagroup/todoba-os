from dataclasses import dataclass
from pathlib import Path

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_access_code_exchange_service import (
    CustomerSetupAccessCodeExchangeService,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeService,
    CustomerSetupAccessCodeStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationStore,
)
from backend.commercial.customer_setup_bootstrap_launch_grant_service import (
    derive_customer_setup_bootstrap_launch_issuance_request_id,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchCredentialStore,
)


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupLegacyActivationForkConvergenceResult:
    customer_id: str
    authoritative_setup_activation_id: str
    superseded_setup_activation_id: str
    deployment_id: str
    authorization_id: str
    launch_id: str


def _require_store_ready(
    store,
    *,
    owner_name: str,
) -> None:
    if store.is_ready():
        return

    open_existing = getattr(
        store,
        "open_existing",
        None,
    )

    if callable(open_existing):
        open_existing()

    if not store.is_ready():
        raise RuntimeError(
            f"{owner_name} is not provisioned."
        )


def converge_customer_setup_legacy_activation_fork(
    *,
    control_plane_root: Path,
    activation_code: str,
    confirm_runtime_stopped: bool,
) -> CustomerSetupLegacyActivationForkConvergenceResult:
    """
    Converge one historically forked Setup activation through
    authoritative durable lineage.

    This is an operator-only recovery boundary.

    The caller supplies no customer, activation, launch, or
    deployment identity. Those identities are derived and
    cross-checked from existing durable commercial state.
    """

    if not isinstance(
        control_plane_root,
        Path,
    ):
        raise TypeError(
            "control_plane_root must be Path."
        )

    if (
        not isinstance(
            activation_code,
            str,
        )
        or not activation_code.strip()
    ):
        raise ValueError(
            "activation_code must be non-empty."
        )

    normalized_activation_code = (
        activation_code.strip()
    )

    if (
        normalized_activation_code
        != activation_code
    ):
        raise ValueError(
            "activation_code must be normalized."
        )

    # Must happen before any production state is opened.
    if confirm_runtime_stopped is not True:
        raise RuntimeError(
            "Production runtime must be confirmed stopped "
            "before legacy Setup activation convergence."
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

    _require_store_ready(
        customer_identity_registry,
        owner_name="Customer identity registry",
    )

    deployment_registry = (
        CustomerDeploymentRegistry(
            commercial_root
            / "customer_deployments.json"
        )
    )

    _require_store_ready(
        deployment_registry,
        owner_name="Customer deployment registry",
    )

    activation_store = (
        CustomerSetupActivationStore(
            commercial_root
            / "customer_setup_activations.json"
        )
    )

    _require_store_ready(
        activation_store,
        owner_name="Customer setup activation store",
    )

    access_code_store = (
        CustomerSetupAccessCodeStore(
            commercial_root
            / "customer_setup_access_codes.json",
            setup_activation_store=(
                activation_store
            ),
        )
    )

    _require_store_ready(
        access_code_store,
        owner_name="Customer setup access code store",
    )

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            commercial_root
            / "customer_setup_bootstrap_authorizations.json",
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    _require_store_ready(
        bootstrap_authorization_store,
        owner_name=(
            "Customer setup bootstrap authorization store"
        ),
    )

    launch_store = (
        CustomerSetupLaunchCredentialStore(
            commercial_root
            / "customer_setup_launch_credentials.json",
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    _require_store_ready(
        launch_store,
        owner_name=(
            "Customer setup launch credential store"
        ),
    )

    deployment_bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            commercial_root
            / "customer_deployment_bootstraps.json"
        )
    )

    _require_store_ready(
        deployment_bootstrap_store,
        owner_name=(
            "Customer deployment bootstrap store"
        ),
    )

    access_code_service = (
        CustomerSetupAccessCodeService(
            access_code_store=(
                access_code_store
            ),
            setup_activation_store=(
                activation_store
            ),
        )
    )

    access_authorization = (
        access_code_service.authorize(
            activation_code=(
                normalized_activation_code
            )
        )
    )

    authoritative_activation = (
        activation_store.get(
            setup_activation_id=(
                access_authorization
                .setup_activation_id
            )
        )
    )

    if authoritative_activation is None:
        raise RuntimeError(
            "Authorized Setup Activation does not exist."
        )

    customer_id = (
        authoritative_activation.customer_id
    )

    if (
        access_authorization.customer_id
        != customer_id
    ):
        raise RuntimeError(
            "Access Code customer identity did not "
            "converge."
        )

    if not customer_identity_registry.contains(
        customer_id=customer_id
    ):
        raise RuntimeError(
            "Authorized customer identity does not exist."
        )

    if (
        authoritative_activation.status
        not in {
            CustomerSetupActivationStatus.ACTIVE,
            CustomerSetupActivationStatus.BOUND,
        }
    ):
        raise RuntimeError(
            "Authoritative Setup Activation is not "
            "eligible for legacy convergence."
        )

    candidates = []

    for bootstrap_authorization in (
        bootstrap_authorization_store.all()
    ):
        # This recovery owner handles only records created
        # before setup_activation_id continuity existed.
        if (
            bootstrap_authorization
            .setup_activation_id
            is not None
        ):
            continue

        if (
            bootstrap_authorization.customer_id
            != customer_id
        ):
            continue

        expected_request_id = (
            CustomerSetupAccessCodeExchangeService
            ._derive_authorization_request_id(
                activation_code=(
                    normalized_activation_code
                ),
                code_challenge_s256=(
                    bootstrap_authorization
                    .code_challenge_s256
                ),
            )
        )

        if (
            expected_request_id
            != bootstrap_authorization
            .authorization_request_id
        ):
            continue

        launch_issuance_request_id = (
            derive_customer_setup_bootstrap_launch_issuance_request_id(
                bootstrap_authorization
                .authorization_id
            )
        )

        launch = (
            launch_store
            .get_by_issuance_request_id(
                issuance_request_id=(
                    launch_issuance_request_id
                )
            )
        )

        if launch is None:
            continue

        if (
            launch.customer_id
            != customer_id
        ):
            raise RuntimeError(
                "Legacy launch customer identity "
                "did not converge."
            )

        legacy_activation = (
            activation_store
            .get_by_activation_request_id(
                activation_request_id=(
                    launch.launch_id
                )
            )
        )

        if legacy_activation is None:
            continue

        if (
            legacy_activation.setup_activation_id
            == authoritative_activation
            .setup_activation_id
        ):
            continue

        if (
            legacy_activation.customer_id
            != customer_id
        ):
            raise RuntimeError(
                "Legacy Setup Activation customer "
                "identity did not converge."
            )

        if (
            legacy_activation.status
            not in {
                CustomerSetupActivationStatus.BOUND,
                CustomerSetupActivationStatus.SUPERSEDED,
            }
        ):
            # Historical launch may have created an
            # activation that never reached provisioning.
            continue

        deployment_id = (
            legacy_activation.deployment_id
        )

        if deployment_id is None:
            raise RuntimeError(
                "Legacy consumed Setup Activation has no "
                "deployment identity."
            )

        deployment = (
            deployment_registry.get(
                deployment_id=deployment_id
            )
        )

        if deployment is None:
            raise RuntimeError(
                "Legacy Setup deployment does not exist."
            )

        if (
            deployment.customer_id
            != customer_id
        ):
            raise RuntimeError(
                "Legacy deployment customer identity "
                "did not converge."
            )

        deployment_bootstrap = (
            deployment_bootstrap_store.get(
                enrollment_request_id=(
                    legacy_activation
                    .setup_activation_id
                )
            )
        )

        if deployment_bootstrap is None:
            continue

        if (
            deployment_bootstrap.customer_id
            != customer_id
            or deployment_bootstrap.deployment_id
            != deployment_id
            or deployment_bootstrap.agent_id
            != deployment.agent_id
        ):
            raise RuntimeError(
                "Legacy deployment bootstrap identity "
                "did not converge."
            )

        current_owner = (
            activation_store
            .get_by_deployment_id(
                deployment_id=deployment_id
            )
        )

        if current_owner is None:
            raise RuntimeError(
                "Deployment has no Setup Activation owner."
            )

        if (
            current_owner.setup_activation_id
            not in {
                legacy_activation.setup_activation_id,
                authoritative_activation.setup_activation_id,
            }
        ):
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
            "No provable legacy Setup activation fork "
            "was found for this Activation Code."
        )

    if len(candidates) != 1:
        raise RuntimeError(
            "Legacy Setup activation fork lineage is "
            "ambiguous."
        )

    (
        bootstrap_authorization,
        launch,
        legacy_activation,
        deployment,
    ) = candidates[0]

    converged = (
        activation_store
        .converge_legacy_fork(
            authoritative_setup_activation_id=(
                authoritative_activation
                .setup_activation_id
            ),
            superseded_setup_activation_id=(
                legacy_activation
                .setup_activation_id
            ),
            deployment_id=(
                deployment.deployment_id
            ),
        )
    )

    if (
        converged.status
        is not CustomerSetupActivationStatus.BOUND
        or converged.deployment_id
        != deployment.deployment_id
    ):
        raise RuntimeError(
            "Legacy Setup activation convergence did "
            "not finish BOUND."
        )

    return (
        CustomerSetupLegacyActivationForkConvergenceResult(
            customer_id=customer_id,
            authoritative_setup_activation_id=(
                authoritative_activation
                .setup_activation_id
            ),
            superseded_setup_activation_id=(
                legacy_activation
                .setup_activation_id
            ),
            deployment_id=(
                deployment.deployment_id
            ),
            authorization_id=(
                bootstrap_authorization
                .authorization_id
            ),
            launch_id=launch.launch_id,
        )
    )
