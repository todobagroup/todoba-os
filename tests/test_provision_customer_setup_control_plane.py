from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStore,
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
from scripts.provision_customer_setup_control_plane import (
    provision_customer_setup_control_plane,
)


IDENTITY_FILENAME = (
    "customer_identities.json"
)

REGISTRATION_FILENAME = (
    "customer_registrations.json"
)

ACTIVATION_FILENAME = (
    "customer_setup_activations.json"
)

ACCESS_CODE_FILENAME = "customer_setup_access_codes.json"

HANDOFF_FILENAME = (
    "customer_setup_handoffs.json"
)

CONTINUATION_FILENAME = (
    "customer_setup_build_continuations.json"
)

LAUNCH_CREDENTIAL_FILENAME = (
    "customer_setup_launch_credentials.json"
)

BOOTSTRAP_AUTHORIZATION_FILENAME = (
    "customer_setup_bootstrap_authorizations.json"
)

BOOTSTRAP_FILENAME = (
    "customer_deployment_bootstraps.json"
)

PACKAGE_BUILD_REQUEST_DIRECTORY = (
    "customer_deployment_package_build_requests"
)


def _prepare_authoritative_identity_store(
    control_plane_root: Path,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        control_plane_root
        / "commercial"
        / IDENTITY_FILENAME
    )
    registry.initialize_empty()
    return registry


def test_requires_path_control_plane_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="control_plane_root must be Path",
    ):
        provision_customer_setup_control_plane(
            control_plane_root=str(
                tmp_path / "control-plane"
            ),
            confirm_runtime_stopped=True,
        )


def test_requires_explicit_runtime_stopped_confirmation(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "requires explicit confirmation that TODOBA "
            "runtime is stopped"
        ),
    ):
        provision_customer_setup_control_plane(
            control_plane_root=control_plane_root,
            confirm_runtime_stopped=False,
        )

    assert not control_plane_root.exists()


def test_requires_existing_authoritative_identity_store(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    with pytest.raises(
        RuntimeError,
        match="Customer identity registry must already exist",
    ):
        provision_customer_setup_control_plane(
            control_plane_root=control_plane_root,
            confirm_runtime_stopped=True,
        )

    assert not control_plane_root.exists()


def test_first_provisioning_creates_only_required_ready_state(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    identity_registry = (
        _prepare_authoritative_identity_store(
            control_plane_root
        )
    )

    (
        activation_path,
        handoff_path,
        bootstrap_path,
        package_build_request_root,
        registration_path,
    ) = provision_customer_setup_control_plane(
        control_plane_root=control_plane_root,
        confirm_runtime_stopped=True,
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    assert registration_path == (
        commercial_root
        / REGISTRATION_FILENAME
    )

    assert activation_path == (
        commercial_root
        / ACTIVATION_FILENAME
    )

    assert handoff_path == (
        commercial_root
        / HANDOFF_FILENAME
    )

    continuation_path = (
        commercial_root
        / CONTINUATION_FILENAME
    )

    launch_credential_path = (
        commercial_root
        / LAUNCH_CREDENTIAL_FILENAME
    )

    bootstrap_authorization_path = (
        commercial_root
        / BOOTSTRAP_AUTHORIZATION_FILENAME
    )

    assert bootstrap_path == (
        commercial_root
        / BOOTSTRAP_FILENAME
    )

    assert package_build_request_root == (
        commercial_root
        / PACKAGE_BUILD_REQUEST_DIRECTORY
    )

    assert registration_path.is_file()
    assert activation_path.is_file()
    assert handoff_path.is_file()
    assert continuation_path.is_file()
    assert launch_credential_path.is_file()
    assert bootstrap_authorization_path.is_file()
    assert bootstrap_path.is_file()

    assert (
        package_build_request_root.is_dir()
    )

    files = {
        path.name
        for path in commercial_root.iterdir()
        if path.is_file()
    }

    assert files == {
        IDENTITY_FILENAME,
        REGISTRATION_FILENAME,
        ACTIVATION_FILENAME,
        ACCESS_CODE_FILENAME,
        HANDOFF_FILENAME,
        CONTINUATION_FILENAME,
        LAUNCH_CREDENTIAL_FILENAME,
        BOOTSTRAP_AUTHORIZATION_FILENAME,
        BOOTSTRAP_FILENAME,
    }

    directories = {
        path.name
        for path in commercial_root.iterdir()
        if path.is_dir()
    }

    assert directories == {
        PACKAGE_BUILD_REQUEST_DIRECTORY,
    }

    registration_store = (
        CustomerRegistrationStore(
            registration_path
        )
    )

    activation_store = (
        CustomerSetupActivationStore(
            activation_path
        )
    )

    handoff_store = (
        CustomerSetupHandoffStore(
            handoff_path
        )
    )

    continuation_store = (
        CustomerSetupBuildContinuationStore(
            continuation_path
        )
    )

    launch_credential_store = (
        CustomerSetupLaunchCredentialStore(
            launch_credential_path,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )
    launch_credential_store.open_existing()

    bootstrap_authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            bootstrap_authorization_path,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )
    bootstrap_authorization_store.open_existing()

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            bootstrap_path
        )
    )

    package_build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            package_build_request_root
        )
    )

    assert registration_store.is_ready()
    assert registration_store.size() == 0

    assert activation_store.is_ready()
    assert handoff_store.is_ready()

    assert continuation_store.is_ready
    assert len(continuation_store.all()) == 0

    assert launch_credential_store.is_ready()
    assert launch_credential_store.size() == 0

    assert bootstrap_authorization_store.is_ready()

    assert bootstrap_store.is_ready()

    assert (
        package_build_request_store.is_ready()
    )

    assert (
        package_build_request_store.size()
        == 0
    )


def test_retry_is_byte_for_byte_and_queue_idempotent(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    identity_registry = (
        _prepare_authoritative_identity_store(
            control_plane_root
        )
    )
    identity_path = identity_registry.storage_path
    first_identity_bytes = identity_path.read_bytes()

    first_result = (
        provision_customer_setup_control_plane(
            control_plane_root=control_plane_root,
            confirm_runtime_stopped=True,
        )
    )

    first_activation_bytes = (
        first_result[0].read_bytes()
    )

    first_handoff_bytes = (
        first_result[1].read_bytes()
    )

    continuation_path = (
        control_plane_root
        / "commercial"
        / CONTINUATION_FILENAME
    )

    first_continuation_bytes = (
        continuation_path.read_bytes()
    )

    launch_credential_path = (
        control_plane_root
        / "commercial"
        / LAUNCH_CREDENTIAL_FILENAME
    )
    first_launch_bytes = (
        launch_credential_path.read_bytes()
    )

    bootstrap_authorization_path = (
        control_plane_root
        / "commercial"
        / BOOTSTRAP_AUTHORIZATION_FILENAME
    )
    first_bootstrap_authorization_bytes = (
        bootstrap_authorization_path.read_bytes()
    )

    first_bootstrap_bytes = (
        first_result[2].read_bytes()
    )

    first_queue_entries = tuple(
        first_result[3].iterdir()
    )

    first_registration_bytes = (
        first_result[4].read_bytes()
    )

    second_result = (
        provision_customer_setup_control_plane(
            control_plane_root=control_plane_root,
            confirm_runtime_stopped=True,
        )
    )

    assert second_result == first_result

    assert (
        second_result[0].read_bytes()
        == first_activation_bytes
    )

    assert (
        second_result[1].read_bytes()
        == first_handoff_bytes
    )

    assert (
        continuation_path.read_bytes()
        == first_continuation_bytes
    )

    assert (
        launch_credential_path.read_bytes()
        == first_launch_bytes
    )

    assert (
        bootstrap_authorization_path.read_bytes()
        == first_bootstrap_authorization_bytes
    )

    assert (
        identity_path.read_bytes()
        == first_identity_bytes
    )

    assert (
        second_result[2].read_bytes()
        == first_bootstrap_bytes
    )

    assert tuple(
        second_result[3].iterdir()
    ) == first_queue_entries

    assert (
        second_result[4].read_bytes()
        == first_registration_bytes
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    commercial_files = {
        path.name
        for path in commercial_root.iterdir()
        if path.is_file()
    }

    assert commercial_files == {
        IDENTITY_FILENAME,
        REGISTRATION_FILENAME,
        ACTIVATION_FILENAME,
        ACCESS_CODE_FILENAME,
        HANDOFF_FILENAME,
        CONTINUATION_FILENAME,
        LAUNCH_CREDENTIAL_FILENAME,
        BOOTSTRAP_AUTHORIZATION_FILENAME,
        BOOTSTRAP_FILENAME,
    }

    commercial_directories = {
        path.name
        for path in commercial_root.iterdir()
        if path.is_dir()
    }

    assert commercial_directories == {
        PACKAGE_BUILD_REQUEST_DIRECTORY,
    }


def test_provisioner_has_store_only_commercial_surface() -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "provision_customer_setup_control_plane.py"
    )

    tree = ast.parse(
        source_path.read_text(
            encoding="utf-8"
        )
    )

    commercial_imports: set[
        tuple[str, str]
    ] = set()

    called_attributes: list[str] = []

    for node in ast.walk(tree):
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
            and node.module.startswith(
                "backend.commercial."
            )
        ):
            for alias in node.names:
                commercial_imports.add(
                    (
                        node.module,
                        alias.name,
                    )
                )

        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
        ):
            called_attributes.append(
                node.func.attr
            )

    assert commercial_imports == {
        (
            "backend.commercial."
            "customer_deployment_bootstrap_service",
            "CustomerDeploymentBootstrapStore",
        ),
        (
            "backend.commercial."
            "customer_deployment_package_build_request_store",
            "CustomerDeploymentPackageBuildRequestStore",
        ),
        (
            "backend.commercial."
            "customer_identity_registry",
            "CustomerIdentityRegistry",
        ),
        (
            "backend.commercial."
            "customer_registration_service",
            "CustomerRegistrationStore",
        ),
        (
            "backend.commercial."
            "customer_setup_access_code_service",
            "CustomerSetupAccessCodeStore",
        ),
        (
            "backend.commercial."
            "customer_setup_activation_service",
            "CustomerSetupActivationStore",
        ),
        (
            "backend.commercial."
            "customer_setup_build_continuation_service",
            "CustomerSetupBuildContinuationStore",
        ),
        (
            "backend.commercial."
            "customer_setup_handoff_service",
            "CustomerSetupHandoffStore",
        ),
        (
            "backend.commercial."
            "customer_setup_bootstrap_authorization_service",
            "CustomerSetupBootstrapAuthorizationStore",
        ),
        (
            "backend.commercial."
            "customer_setup_launch_credential_service",
            "CustomerSetupLaunchCredentialStore",
        ),
    }

    assert (
        called_attributes.count(
            "initialize_empty"
        )
        == 9
    )

    forbidden_business_actions = {
        "grant",
        "issue",
        "bind",
        "suspend",
        "reactivate",
        "revoke",
        "register",
        "enroll",
        "onboard",
        "build_package",
        "acquire",
    }

    assert (
        forbidden_business_actions
        .intersection(
            called_attributes
        )
        == set()
    )
