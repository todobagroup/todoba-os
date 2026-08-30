from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_registration_api import (
    CustomerRegistrationRequest,
    CustomerRegistrationResponse,
    create_customer_registration_router,
)
from backend.commercial.customer_registration_service import (
    CustomerRegistrationResult,
)


class RegistrationServiceStub:
    def __init__(
        self,
    ) -> None:
        self.calls: list[str] = []

    def register(
        self,
        *,
        registration_request_id: str,
    ) -> CustomerRegistrationResult:
        self.calls.append(
            registration_request_id
        )

        return CustomerRegistrationResult(
            registration_request_id=(
                registration_request_id
            ),
            customer_id="customer-001",
        )


def build_client(
    service=None,
) -> tuple[
    TestClient,
    RegistrationServiceStub,
]:
    if service is None:
        service = RegistrationServiceStub()

    app = FastAPI()

    app.include_router(
        create_customer_registration_router(
            registration_service=service,
        )
    )

    return (
        TestClient(app),
        service,
    )


def test_request_contract_contains_only_registration_request_id(
) -> None:
    assert set(
        CustomerRegistrationRequest.model_fields
    ) == {
        "registration_request_id",
    }


def test_response_contract_contains_only_safe_identity_fields(
) -> None:
    assert set(
        CustomerRegistrationResponse.model_fields
    ) == {
        "registration_request_id",
        "customer_id",
    }


def test_router_requires_registration_owner(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "registration_service must expose callable "
            "register"
        ),
    ):
        create_customer_registration_router(
            registration_service=object(),
        )


def test_registration_returns_authoritative_customer_identity(
) -> None:
    client, service = build_client()

    response = client.post(
        "/customer/register",
        json={
            "registration_request_id": (
                "registration-001"
            ),
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "registration_request_id": (
            "registration-001"
        ),
        "customer_id": "customer-001",
    }

    assert service.calls == [
        "registration-001",
    ]


def test_registration_normalizes_request_identity(
) -> None:
    client, service = build_client()

    response = client.post(
        "/customer/register",
        json={
            "registration_request_id": (
                "  registration-001  "
            ),
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "registration_request_id": (
            "registration-001"
        ),
        "customer_id": "customer-001",
    }

    assert service.calls == [
        "registration-001",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
    ],
)
def test_registration_rejects_empty_request_identity(
    value: str,
) -> None:
    client, service = build_client()

    response = client.post(
        "/customer/register",
        json={
            "registration_request_id": value,
        },
    )

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
    ),
    [
        (
            "customer_id",
            "customer-attacker",
        ),
        (
            "payment_id",
            "payment-001",
        ),
        (
            "subscription_id",
            "subscription-001",
        ),
        (
            "setup_activation_id",
            "setup-activation-001",
        ),
        (
            "handoff_credential",
            "secret",
        ),
        (
            "deployment_id",
            "deployment-001",
        ),
        (
            "entitlement",
            "ACTIVE",
        ),
        (
            "account_fingerprint",
            "fingerprint-001",
        ),
        (
            "package_path",
            "artifact.ex5",
        ),
    ],
)
def test_registration_rejects_non_owned_customer_fields(
    field_name: str,
    field_value: str,
) -> None:
    client, service = build_client()

    response = client.post(
        "/customer/register",
        json={
            "registration_request_id": (
                "registration-001"
            ),
            field_name: field_value,
        },
    )

    assert response.status_code == 422
    assert service.calls == []


def test_router_rejects_invalid_owner_result(
) -> None:
    class InvalidService:
        def register(
            self,
            *,
            registration_request_id: str,
        ):
            return object()

    client, _ = build_client(
        InvalidService()
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer registration service returned "
            "invalid result"
        ),
    ):
        client.post(
            "/customer/register",
            json={
                "registration_request_id": (
                    "registration-001"
                ),
            },
        )


def test_router_rejects_nonconverged_request_identity(
) -> None:
    class MismatchedService:
        def register(
            self,
            *,
            registration_request_id: str,
        ) -> CustomerRegistrationResult:
            return CustomerRegistrationResult(
                registration_request_id=(
                    "registration-other"
                ),
                customer_id="customer-001",
            )

    client, _ = build_client(
        MismatchedService()
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Customer registration request identity "
            "did not converge"
        ),
    ):
        client.post(
            "/customer/register",
            json={
                "registration_request_id": (
                    "registration-001"
                ),
            },
        )


def test_router_factory_surface_is_registration_only(
) -> None:
    parameters = inspect.signature(
        create_customer_registration_router
    ).parameters

    assert set(
        parameters
    ) == {
        "registration_service",
    }


def test_api_has_registration_only_commercial_surface(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "backend"
        / "commercial"
        / "customer_registration_api.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    commercial_imports: set[
        tuple[str, str]
    ] = set()

    called_attributes: list[str] = []

    for node in ast.walk(
        tree
    ):
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
            "customer_registration_service",
            "CustomerRegistrationResult",
        ),
    }

    assert (
        called_attributes.count(
            "register"
        )
        == 1
    )

    forbidden_business_actions = {
        "activate",
        "issue",
        "bind",
        "suspend",
        "reactivate",
        "revoke",
        "provision",
        "prepare_bootstrap",
        "activate_bootstrap",
        "build_package",
        "get_published_package",
    }

    assert (
        forbidden_business_actions.intersection(
            called_attributes
        )
        == set()
    )

    forbidden_surface_terms = {
        "CustomerSetupActivationService",
        "CustomerSetupHandoffService",
        "CustomerAccessCredentialRegistry",
        "CustomerDeploymentEntitlementRegistry",
        "CustomerDeploymentBootstrapService",
        "CustomerDeploymentPackageService",
        "MetaEditor",
        "subprocess",
        "payment_id",
        "subscription_id",
    }

    for term in forbidden_surface_terms:
        assert term not in source
