from pathlib import Path

from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantStore,
)
from scripts import provision_customer_setup_control_plane


def test_customer_setup_control_plane_provisions_vps_connect_grant_store(
    tmp_path,
    monkeypatch,
) -> None:
    commercial_root = (
        tmp_path
        / "commercial"
    )

    grant_path = (
        commercial_root
        / "customer_vps_connect_grants.json"
    )

    source = Path(
        provision_customer_setup_control_plane.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "customer_vps_connect_grants.json"
        in source
    ), (
        "Customer Setup control-plane provisioning "
        "does not own the durable VPS Connect grant store."
    )

    assert (
        "CustomerVPSConnectGrantStore"
        in source
    ), (
        "Provisioning owner does not construct the "
        "VPS Connect grant store."
    )

    assert (
        "initialize_empty"
        in source
    ), (
        "Offline provisioning must initialize the "
        "new durable store before runtime."
    )

    store = CustomerVPSConnectGrantStore(
        grant_path
    )
    store.initialize_empty()

    reopened = CustomerVPSConnectGrantStore(
        grant_path
    )
    reopened.open_existing()

    assert reopened.is_ready()
    assert grant_path.is_file()


def test_backend_main_must_not_initialize_vps_connect_grant_store(
) -> None:
    main_source = Path(
        "backend/main.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "customer_vps_connect_grant_store"
        ".initialize_empty"
    )

    assert forbidden not in main_source


def test_offline_provisioning_actually_creates_vps_connect_grant_store(
    tmp_path,
) -> None:
    commercial_root = (
        tmp_path
        / "commercial"
    )
    commercial_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    identity_registry = CustomerIdentityRegistry(
        commercial_root
        / "customer_identities.json"
    )
    identity_registry.initialize_empty()

    provision_customer_setup_control_plane.provision_customer_setup_control_plane(
        control_plane_root=tmp_path,
        confirm_runtime_stopped=True,
    )

    grant_path = (
        tmp_path
        / "commercial"
        / "customer_vps_connect_grants.json"
    )

    assert grant_path.is_file()

    reopened = CustomerVPSConnectGrantStore(
        grant_path
    )
    reopened.open_existing()

    assert reopened.is_ready()
