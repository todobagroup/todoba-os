import inspect

import pytest

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStore,
)
from scripts.issue_customer_setup_access_code import (
    issue_customer_setup_access_code,
)


def _provision_empty_control_plane(root):
    commercial_root = root / "commercial"
    commercial_root.mkdir(parents=True)

    identity_registry = CustomerIdentityRegistry(
        commercial_root / "customer_identities.json"
    )
    identity_registry.initialize_empty()

    deployment_registry = CustomerDeploymentRegistry(
        commercial_root / "customer_deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        commercial_root / "customer_setup_activations.json"
    )
    activation_store.initialize_empty()

    access_code_store = CustomerSetupAccessCodeStore(
        commercial_root / "customer_setup_access_codes.json",
        setup_activation_store=activation_store,
    )
    access_code_store.initialize_empty()

    return identity_registry


def _open_authoritative_stores(root):
    commercial_root = root / "commercial"

    activation_store = CustomerSetupActivationStore(
        commercial_root / "customer_setup_activations.json"
    )

    access_code_store = CustomerSetupAccessCodeStore(
        commercial_root / "customer_setup_access_codes.json",
        setup_activation_store=activation_store,
    )

    return activation_store, access_code_store


def test_operator_access_code_issuer_has_narrow_authority_surface():
    signature = inspect.signature(
        issue_customer_setup_access_code
    )

    assert tuple(signature.parameters) == (
        "control_plane_root",
        "activation_request_id",
        "customer_id",
        "confirm_runtime_stopped",
    )


def test_runtime_stop_confirmation_is_required_before_any_state_access(
    tmp_path,
):
    with pytest.raises(
        RuntimeError,
        match="runtime must be confirmed stopped",
    ):
        issue_customer_setup_access_code(
            control_plane_root=tmp_path,
            activation_request_id="activation-request-runtime",
            customer_id="customer-runtime",
            confirm_runtime_stopped=False,
        )

    assert not (tmp_path / "commercial").exists()


def test_unknown_customer_fails_without_creating_authority(
    tmp_path,
):
    _provision_empty_control_plane(tmp_path)

    with pytest.raises(
        ValueError,
        match="Customer identity is not registered",
    ):
        issue_customer_setup_access_code(
            control_plane_root=tmp_path,
            activation_request_id="activation-request-unknown",
            customer_id="customer-unknown",
            confirm_runtime_stopped=True,
        )

    activation_store, access_code_store = (
        _open_authoritative_stores(tmp_path)
    )

    assert activation_store.size() == 0
    assert len(access_code_store.all()) == 0


def test_fresh_customer_issues_durable_access_code_without_plaintext_persistence(
    tmp_path,
):
    identity_registry = _provision_empty_control_plane(
        tmp_path
    )
    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-fresh",
        )
    )

    issuance = issue_customer_setup_access_code(
        control_plane_root=tmp_path,
        activation_request_id="activation-request-fresh",
        customer_id="customer-fresh",
        confirm_runtime_stopped=True,
    )

    assert issuance.customer_id == "customer-fresh"
    assert issuance.activation_code

    activation_store, access_code_store = (
        _open_authoritative_stores(tmp_path)
    )

    activation = (
        activation_store.get_by_activation_request_id(
            activation_request_id="activation-request-fresh"
        )
    )
    assert activation is not None
    assert (
        activation.setup_activation_id
        == issuance.setup_activation_id
    )

    active_code = (
        access_code_store
        .get_active_by_setup_activation_id(
            setup_activation_id=(
                issuance.setup_activation_id
            )
        )
    )
    assert active_code is not None
    assert active_code.access_code_id == issuance.access_code_id

    access_code_path = (
        tmp_path
        / "commercial"
        / "customer_setup_access_codes.json"
    )
    assert (
        issuance.activation_code
        not in access_code_path.read_text(
            encoding="utf-8"
        )
    )


def test_retry_refuses_rotation_and_preserves_original_active_code(
    tmp_path,
):
    identity_registry = _provision_empty_control_plane(
        tmp_path
    )
    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-retry",
        )
    )

    first = issue_customer_setup_access_code(
        control_plane_root=tmp_path,
        activation_request_id="activation-request-retry",
        customer_id="customer-retry",
        confirm_runtime_stopped=True,
    )

    with pytest.raises(
        RuntimeError,
        match="refusing rotation",
    ):
        issue_customer_setup_access_code(
            control_plane_root=tmp_path,
            activation_request_id="activation-request-retry",
            customer_id="customer-retry",
            confirm_runtime_stopped=True,
        )

    activation_store, access_code_store = (
        _open_authoritative_stores(tmp_path)
    )

    activation = (
        activation_store.get_by_activation_request_id(
            activation_request_id="activation-request-retry"
        )
    )
    assert activation is not None

    active_code = (
        access_code_store
        .get_active_by_setup_activation_id(
            setup_activation_id=(
                activation.setup_activation_id
            )
        )
    )

    assert active_code is not None
    assert active_code.access_code_id == first.access_code_id
    assert activation_store.size() == 1
    assert len(access_code_store.all()) == 1

