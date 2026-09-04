from __future__ import annotations

import ast
from pathlib import Path

from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStore,
)
from scripts.provision_customer_setup_control_plane import (
    provision_customer_setup_control_plane,
)


_IDENTITY_FILENAME = "customer_identities.json"
_ACTIVATION_FILENAME = "customer_setup_activations.json"
_ACCESS_CODE_FILENAME = "customer_setup_access_codes.json"


def _prepare_identity_registry(
    control_plane_root: Path,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        control_plane_root
        / "commercial"
        / _IDENTITY_FILENAME
    )

    registry.initialize_empty()

    return registry


def test_offline_provisioning_creates_ready_empty_access_code_store(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    _prepare_identity_registry(
        control_plane_root
    )

    provision_customer_setup_control_plane(
        control_plane_root=(
            control_plane_root
        ),
        confirm_runtime_stopped=True,
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    activation_path = (
        commercial_root
        / _ACTIVATION_FILENAME
    )

    access_code_path = (
        commercial_root
        / _ACCESS_CODE_FILENAME
    )

    assert activation_path.is_file()
    assert access_code_path.is_file()

    activation_store = (
        CustomerSetupActivationStore(
            activation_path
        )
    )

    assert activation_store.is_ready()

    access_code_store = (
        CustomerSetupAccessCodeStore(
            access_code_path,
            setup_activation_store=(
                activation_store
            ),
        )
    )

    assert access_code_store.is_ready()
    assert len(
        access_code_store.all()
    ) == 0


def test_access_code_store_provisioning_is_byte_for_byte_idempotent(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    _prepare_identity_registry(
        control_plane_root
    )

    provision_customer_setup_control_plane(
        control_plane_root=(
            control_plane_root
        ),
        confirm_runtime_stopped=True,
    )

    access_code_path = (
        control_plane_root
        / "commercial"
        / _ACCESS_CODE_FILENAME
    )

    first_bytes = (
        access_code_path.read_bytes()
    )

    provision_customer_setup_control_plane(
        control_plane_root=(
            control_plane_root
        ),
        confirm_runtime_stopped=True,
    )

    assert (
        access_code_path.read_bytes()
        == first_bytes
    )


def test_provisioner_imports_store_only_and_owns_no_access_code_issuance(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "provision_customer_setup_control_plane.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imported_access_code_names = set()

    for node in ast.walk(tree):
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
            == (
                "backend.commercial."
                "customer_setup_access_code_service"
            )
        ):
            imported_access_code_names.update(
                alias.name
                for alias in node.names
            )

    assert imported_access_code_names == {
        "CustomerSetupAccessCodeStore",
    }

    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
        )
    }

    assert not {
        "issue",
        "authorize",
        "revoke",
    }.intersection(
        called_attributes
    )


def test_runtime_main_does_not_initialize_access_code_state(
) -> None:
    main_source = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "backend"
        / "main.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "access_code_store.initialize_empty()"
        not in main_source
    )

    assert (
        "customer_setup_access_code_store.initialize_empty()"
        not in main_source
    )
