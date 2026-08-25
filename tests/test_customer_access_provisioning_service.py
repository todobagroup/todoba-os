import inspect
import json
from pathlib import Path

import pytest

from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
    derive_customer_access_credential_verifier,
)
from backend.commercial.customer_access_provisioning_service import (
    CustomerAccessProvisioningRecord,
    CustomerAccessProvisioningService,
    CustomerAccessProvisioningStore,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)


def identity_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_identities.json"
    )


def credential_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_access_credentials.json"
    )


def deployment_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_deployments.json"
    )


def entitlement_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_deployment_entitlements.json"
    )


def provisioning_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_access_provisioning.json"
    )


def build_access_provisioning(
    tmp_path: Path,
):
    deployment_registry = (
        CustomerDeploymentRegistry(
            deployment_path(
                tmp_path
            )
        )
    )

    deployment_registry.initialize_empty()

    deployment_registry.register(
        CustomerDeployment(
            customer_id="customer-001",
            deployment_id="deployment-001",
            agent_id="trusted-agent-001",
        )
    )

    customer_identity_registry = (
        CustomerIdentityRegistry(
            identity_path(
                tmp_path
            )
        )
    )

    customer_identity_registry.initialize_empty()

    credential_registry = (
        CustomerAccessCredentialRegistry(
            credential_path(
                tmp_path
            ),
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    credential_registry.initialize_empty()

    entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            entitlement_path(
                tmp_path
            ),
            deployment_registry=(
                deployment_registry
            ),
        )
    )

    entitlement_registry.initialize_empty()

    provisioning_store = (
        CustomerAccessProvisioningStore(
            provisioning_path(
                tmp_path
            )
        )
    )

    provisioning_store.initialize_empty()

    service = CustomerAccessProvisioningService(
        provisioning_store=(
            provisioning_store
        ),
        customer_identity_registry=(
            customer_identity_registry
        ),
        credential_registry=(
            credential_registry
        ),
        deployment_registry=(
            deployment_registry
        ),
        entitlement_registry=(
            entitlement_registry
        ),
    )

    return (
        service,
        provisioning_store,
        customer_identity_registry,
        credential_registry,
        deployment_registry,
        entitlement_registry,
    )


def test_provisioning_record_normalizes_identity() -> None:
    record = CustomerAccessProvisioningRecord(
        provisioning_request_id=(
            "  request-001  "
        ),
        customer_id="  customer-001  ",
        deployment_id=(
            "  deployment-001  "
        ),
    )

    assert (
        record.provisioning_request_id
        == "request-001"
    )

    assert (
        record.customer_id
        == "customer-001"
    )

    assert (
        record.deployment_id
        == "deployment-001"
    )


def test_provisioning_store_persists_and_restores(
    tmp_path: Path,
) -> None:
    path = provisioning_path(
        tmp_path
    )

    store = CustomerAccessProvisioningStore(
        path
    )

    store.initialize_empty()

    record = CustomerAccessProvisioningRecord(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    stored = store.register(
        record
    )

    assert stored == record
    assert store.size() == 1

    restarted = CustomerAccessProvisioningStore(
        path
    )

    assert restarted.is_ready()

    assert (
        restarted.get(
            provisioning_request_id=(
                "request-001"
            )
        )
        == record
    )


def test_provisioning_store_rejects_conflicting_request_reuse(
    tmp_path: Path,
) -> None:
    store = CustomerAccessProvisioningStore(
        provisioning_path(
            tmp_path
        )
    )

    store.initialize_empty()

    store.register(
        CustomerAccessProvisioningRecord(
            provisioning_request_id=(
                "request-001"
            ),
            customer_id="customer-001",
            deployment_id=(
                "deployment-001"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "already bound to different "
            "commercial identity"
        ),
    ):
        store.register(
            CustomerAccessProvisioningRecord(
                provisioning_request_id=(
                    "request-001"
                ),
                customer_id=(
                    "customer-001"
                ),
                deployment_id=(
                    "deployment-002"
                ),
            )
        )

    assert store.size() == 1


def test_provision_success_creates_access_and_entitlement(
    tmp_path: Path,
) -> None:
    (
        service,
        provisioning_store,
        customer_identity_registry,
        credential_registry,
        _,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    result = service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    assert (
        result.provisioning_request_id
        == "request-001"
    )

    assert (
        result.customer_id
        == "customer-001"
    )

    assert (
        result.deployment_id
        == "deployment-001"
    )

    assert result.credential_id
    assert result.access_credential

    assert (
        result.access_credential
        not in repr(
            result
        )
    )

    assert (
        "access_credential=<redacted>"
        in repr(
            result
        )
    )

    assert provisioning_store.size() == 1

    assert (
        customer_identity_registry.contains(
            customer_id="customer-001"
        )
    )

    assert credential_registry.size() == 1

    credential_record = (
        credential_registry.get(
            credential_id=(
                result.credential_id
            )
        )
    )

    assert credential_record is not None

    assert (
        credential_record.customer_id
        == "customer-001"
    )

    assert (
        credential_record.issuance_request_id
        == "request-001"
    )

    assert (
        credential_record.verifier_sha256
        == derive_customer_access_credential_verifier(
            result.access_credential
        )
    )

    assert entitlement_registry.is_active(
        deployment_id="deployment-001"
    )

    persisted = (
        provisioning_path(
            tmp_path
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        result.access_credential
        not in persisted
    )

    assert (
        result.credential_id
        not in persisted
    )

    payload = json.loads(
        persisted
    )

    assert set(
        payload["records"][0]
    ) == {
        "provisioning_request_id",
        "customer_id",
        "deployment_id",
    }


def test_unknown_deployment_fails_before_any_mutation(
    tmp_path: Path,
) -> None:
    (
        service,
        provisioning_store,
        customer_identity_registry,
        credential_registry,
        _,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unknown customer deployment"
        ),
    ):
        service.provision(
            provisioning_request_id=(
                "request-001"
            ),
            customer_id="customer-001",
            deployment_id=(
                "deployment-missing"
            ),
        )

    assert provisioning_store.size() == 0

    assert not (
        customer_identity_registry.contains(
            customer_id="customer-001"
        )
    )

    assert credential_registry.size() == 0

    assert not entitlement_registry.is_active(
        deployment_id=(
            "deployment-missing"
        )
    )


def test_cross_customer_deployment_fails_before_any_mutation(
    tmp_path: Path,
) -> None:
    (
        service,
        provisioning_store,
        customer_identity_registry,
        credential_registry,
        _,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match=(
            "Customer does not own deployment"
        ),
    ):
        service.provision(
            provisioning_request_id=(
                "request-001"
            ),
            customer_id="customer-002",
            deployment_id="deployment-001",
        )

    assert provisioning_store.size() == 0

    assert not (
        customer_identity_registry.contains(
            customer_id="customer-002"
        )
    )

    assert credential_registry.size() == 0

    assert not entitlement_registry.is_active(
        deployment_id="deployment-001"
    )


def test_same_request_retry_reuses_credential_id_and_rotates_plaintext(
    tmp_path: Path,
) -> None:
    (
        service,
        provisioning_store,
        customer_identity_registry,
        credential_registry,
        _,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    first = service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    second = service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    assert (
        first.credential_id
        == second.credential_id
    )

    assert (
        first.access_credential
        != second.access_credential
    )

    assert provisioning_store.size() == 1

    assert (
        len(
            customer_identity_registry.all()
        )
        == 1
    )

    assert credential_registry.size() == 1

    record = credential_registry.get(
        credential_id=(
            first.credential_id
        )
    )

    assert record is not None

    assert (
        record.verifier_sha256
        == derive_customer_access_credential_verifier(
            second.access_credential
        )
    )

    assert (
        record.verifier_sha256
        != derive_customer_access_credential_verifier(
            first.access_credential
        )
    )

    assert entitlement_registry.is_active(
        deployment_id="deployment-001"
    )


def test_request_cannot_be_rebound_to_another_deployment(
    tmp_path: Path,
) -> None:
    (
        service,
        provisioning_store,
        _,
        credential_registry,
        deployment_registry,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    deployment_registry.register(
        CustomerDeployment(
            customer_id="customer-001",
            deployment_id="deployment-002",
            agent_id="trusted-agent-002",
        )
    )

    first = service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    with pytest.raises(
        ValueError,
        match=(
            "already bound to different "
            "commercial identity"
        ),
    ):
        service.provision(
            provisioning_request_id=(
                "request-001"
            ),
            customer_id="customer-001",
            deployment_id=(
                "deployment-002"
            ),
        )

    assert provisioning_store.size() == 1
    assert credential_registry.size() == 1

    record = credential_registry.get(
        credential_id=(
            first.credential_id
        )
    )

    assert record is not None

    assert entitlement_registry.is_active(
        deployment_id="deployment-001"
    )

    assert not entitlement_registry.is_active(
        deployment_id="deployment-002"
    )


def test_request_binding_is_durable_before_identity_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        provisioning_store,
        customer_identity_registry,
        credential_registry,
        _,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    def fail_identity_registration(
        identity,
    ):
        raise RuntimeError(
            "simulated identity failure"
        )

    monkeypatch.setattr(
        customer_identity_registry,
        "register",
        fail_identity_registration,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated identity failure",
    ):
        service.provision(
            provisioning_request_id=(
                "request-001"
            ),
            customer_id="customer-001",
            deployment_id=(
                "deployment-001"
            ),
        )

    stored = provisioning_store.get(
        provisioning_request_id=(
            "request-001"
        )
    )

    assert stored is not None

    assert (
        stored.customer_id
        == "customer-001"
    )

    assert (
        stored.deployment_id
        == "deployment-001"
    )

    assert credential_registry.size() == 0

    assert not entitlement_registry.is_active(
        deployment_id="deployment-001"
    )


def test_retry_recovers_after_entitlement_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        provisioning_store,
        _,
        credential_registry,
        _,
        entitlement_registry,
    ) = build_access_provisioning(
        tmp_path
    )

    original_activate = (
        entitlement_registry.activate
    )

    def fail_entitlement_activation(
        *,
        deployment_id: str,
    ):
        raise RuntimeError(
            "simulated entitlement failure"
        )

    monkeypatch.setattr(
        entitlement_registry,
        "activate",
        fail_entitlement_activation,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "simulated entitlement failure"
        ),
    ):
        service.provision(
            provisioning_request_id=(
                "request-001"
            ),
            customer_id="customer-001",
            deployment_id=(
                "deployment-001"
            ),
        )

    assert provisioning_store.size() == 1
    assert credential_registry.size() == 1

    first_record = (
        credential_registry.all()[0]
    )

    first_credential_id = (
        first_record.credential_id
    )

    first_verifier = (
        first_record.verifier_sha256
    )

    assert not entitlement_registry.is_active(
        deployment_id="deployment-001"
    )

    monkeypatch.setattr(
        entitlement_registry,
        "activate",
        original_activate,
    )

    recovered = service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    assert (
        recovered.credential_id
        == first_credential_id
    )

    current_record = (
        credential_registry.get(
            credential_id=(
                first_credential_id
            )
        )
    )

    assert current_record is not None

    assert (
        current_record.verifier_sha256
        != first_verifier
    )

    assert (
        current_record.verifier_sha256
        == derive_customer_access_credential_verifier(
            recovered.access_credential
        )
    )

    assert entitlement_registry.is_active(
        deployment_id="deployment-001"
    )


def test_retry_after_full_restart_converges_safely(
    tmp_path: Path,
) -> None:
    (
        service,
        _,
        _,
        _,
        _,
        _,
    ) = build_access_provisioning(
        tmp_path
    )

    first = service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    restarted_deployments = (
        CustomerDeploymentRegistry(
            deployment_path(
                tmp_path
            )
        )
    )

    assert restarted_deployments.is_ready()

    restarted_identities = (
        CustomerIdentityRegistry(
            identity_path(
                tmp_path
            )
        )
    )

    assert restarted_identities.is_ready()

    restarted_credentials = (
        CustomerAccessCredentialRegistry(
            credential_path(
                tmp_path
            ),
            customer_identity_registry=(
                restarted_identities
            ),
        )
    )

    assert restarted_credentials.is_ready()

    restarted_entitlements = (
        CustomerDeploymentEntitlementRegistry(
            entitlement_path(
                tmp_path
            ),
            deployment_registry=(
                restarted_deployments
            ),
        )
    )

    assert restarted_entitlements.is_ready()

    restarted_store = (
        CustomerAccessProvisioningStore(
            provisioning_path(
                tmp_path
            )
        )
    )

    assert restarted_store.is_ready()

    restarted_service = (
        CustomerAccessProvisioningService(
            provisioning_store=(
                restarted_store
            ),
            customer_identity_registry=(
                restarted_identities
            ),
            credential_registry=(
                restarted_credentials
            ),
            deployment_registry=(
                restarted_deployments
            ),
            entitlement_registry=(
                restarted_entitlements
            ),
        )
    )

    second = restarted_service.provision(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    assert (
        second.credential_id
        == first.credential_id
    )

    assert (
        second.access_credential
        != first.access_credential
    )

    assert restarted_store.size() == 1
    assert restarted_credentials.size() == 1

    record = restarted_credentials.get(
        credential_id=(
            second.credential_id
        )
    )

    assert record is not None

    assert (
        record.verifier_sha256
        == derive_customer_access_credential_verifier(
            second.access_credential
        )
    )

    assert (
        record.verifier_sha256
        != derive_customer_access_credential_verifier(
            first.access_credential
        )
    )

    assert restarted_entitlements.is_active(
        deployment_id="deployment-001"
    )


def test_duplicate_provisioning_requests_fail_closed_on_restore(
    tmp_path: Path,
) -> None:
    path = provisioning_path(
        tmp_path
    )

    store = CustomerAccessProvisioningStore(
        path
    )

    store.initialize_empty()

    record = CustomerAccessProvisioningRecord(
        provisioning_request_id=(
            "request-001"
        ),
        customer_id="customer-001",
        deployment_id="deployment-001",
    )

    store.register(
        record
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload["records"].append(
        dict(
            payload["records"][0]
        )
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Duplicate customer access "
            "provisioning request"
        ),
    ):
        CustomerAccessProvisioningStore(
            path
        )


def test_service_requires_ready_provisioning_store(
    tmp_path: Path,
) -> None:
    (
        _,
        _,
        identities,
        credentials,
        deployments,
        entitlements,
    ) = build_access_provisioning(
        tmp_path
    )

    unready_store = (
        CustomerAccessProvisioningStore(
            tmp_path
            / "unready-provisioning.json"
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "provisioning store is not initialized"
        ),
    ):
        CustomerAccessProvisioningService(
            provisioning_store=(
                unready_store
            ),
            customer_identity_registry=(
                identities
            ),
            credential_registry=(
                credentials
            ),
            deployment_registry=(
                deployments
            ),
            entitlement_registry=(
                entitlements
            ),
        )


def test_provision_signature_exposes_only_commercial_identity_inputs(
) -> None:
    signature = inspect.signature(
        CustomerAccessProvisioningService.provision
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "provisioning_request_id",
        "customer_id",
        "deployment_id",
    )

    forbidden = {
        "credential_id",
        "access_credential",
        "payment_id",
        "subscription_id",
        "agent_id",
        "package_root",
        "http_request",
    }

    assert not (
        forbidden
        & set(
            signature.parameters
        )
    )
