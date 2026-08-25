import inspect
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_authentication_dependency import (
    create_customer_authentication_dependency,
)
from backend.commercial.customer_authenticator import (
    CustomerAuthenticator,
)
from backend.commercial.customer_deployment_authorizer import (
    CustomerDeploymentAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_package_api import (
    create_customer_deployment_package_router,
)
from backend.commercial.customer_deployment_package_publication import (
    CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME,
    CustomerDeploymentPackagePublication,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


def build_customer_package_api(
    tmp_path: Path,
):
    identity_registry = (
        CustomerIdentityRegistry(
            tmp_path
            / "customer_identities.json"
        )
    )
    identity_registry.initialize_empty()

    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001"
        )
    )
    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-002"
        )
    )

    credential_registry = (
        CustomerAccessCredentialRegistry(
            tmp_path
            / "customer_access_credentials.json",
            customer_identity_registry=(
                identity_registry
            ),
        )
    )
    credential_registry.initialize_empty()

    customer_001_credential = (
        credential_registry.issue_for_request(
            customer_id="customer-001",
            issuance_request_id=(
                "package-api-access-001"
            ),
        )
    )

    customer_002_credential = (
        credential_registry.issue_for_request(
            customer_id="customer-002",
            issuance_request_id=(
                "package-api-access-002"
            ),
        )
    )

    authenticator = CustomerAuthenticator(
        credential_registry=(
            credential_registry
        )
    )

    authentication_dependency = (
        create_customer_authentication_dependency(
            authenticator
        )
    )

    deployment_registry = (
        CustomerDeploymentRegistry(
            tmp_path
            / "customer_deployments.json"
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

    deployment_authorizer = (
        CustomerDeploymentAuthorizer(
            deployment_registry=(
                deployment_registry
            )
        )
    )

    entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            tmp_path
            / "customer_deployment_entitlements.json",
            deployment_registry=(
                deployment_registry
            ),
        )
    )
    entitlement_registry.initialize_empty()

    entitlement_authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=(
                entitlement_registry
            )
        )
    )

    package_root = (
        tmp_path
        / "published-customer-packages"
    )

    package_publication = (
        CustomerDeploymentPackagePublication(
            package_root=package_root
        )
    )

    app = FastAPI()

    app.include_router(
        create_customer_deployment_package_router(
            customer_authentication_dependency=(
                authentication_dependency
            ),
            deployment_authorizer=(
                deployment_authorizer
            ),
            entitlement_authorizer=(
                entitlement_authorizer
            ),
            package_publication=(
                package_publication
            ),
        )
    )

    return {
        "client": TestClient(app),
        "entitlement_registry": (
            entitlement_registry
        ),
        "package_publication": (
            package_publication
        ),
        "customer_001_credential": (
            customer_001_credential
            .access_credential
        ),
        "customer_002_credential": (
            customer_002_credential
            .access_credential
        ),
    }


def authorization_header(
    credential: str,
) -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {credential}"
        )
    }


def publish_valid_package(
    *,
    publication: CustomerDeploymentPackagePublication,
    deployment_id: str = "deployment-001",
    content: bytes = b"TODOBA EX5 TEST ARTIFACT",
) -> Path:
    package_directory = (
        publication.package_directory(
            deployment_id=deployment_id
        )
    )

    package_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact = (
        package_directory
        / CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
    )

    artifact.write_bytes(
        content
    )

    return artifact


def test_customer_package_route_requires_authentication(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package"
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Customer authentication failed."
        )
    }

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )


def test_unknown_deployment_returns_not_found(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-missing/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Customer deployment not found."
        )
    }


def test_cross_customer_deployment_converges_on_same_not_found(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_002_credential"
            ]
        ),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Customer deployment not found."
        )
    }


def test_missing_entitlement_returns_forbidden(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Customer deployment entitlement required."
        )
    }


def test_suspended_entitlement_returns_forbidden(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    entitlement_registry = environment[
        "entitlement_registry"
    ]

    entitlement_registry.activate(
        deployment_id="deployment-001"
    )

    entitlement_registry.suspend(
        deployment_id="deployment-001"
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Customer deployment entitlement required."
        )
    }


def test_active_entitlement_with_missing_package_returns_not_found(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    environment[
        "entitlement_registry"
    ].activate(
        deployment_id="deployment-001"
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Customer deployment package not found."
        )
    }


def test_corrupt_published_package_returns_server_error(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    environment[
        "entitlement_registry"
    ].activate(
        deployment_id="deployment-001"
    )

    publication = environment[
        "package_publication"
    ]

    publish_valid_package(
        publication=publication
    )

    package_directory = (
        publication.package_directory(
            deployment_id="deployment-001"
        )
    )

    (
        package_directory
        / "unexpected-material.txt"
    ).write_text(
        "invalid",
        encoding="utf-8",
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "Customer deployment package "
            "publication is invalid."
        )
    }


def test_empty_published_ex5_returns_server_error(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    environment[
        "entitlement_registry"
    ].activate(
        deployment_id="deployment-001"
    )

    publish_valid_package(
        publication=(
            environment[
                "package_publication"
            ]
        ),
        content=b"",
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "Customer deployment package "
            "publication is invalid."
        )
    }


def test_authorized_entitled_customer_receives_exact_ex5(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    environment[
        "entitlement_registry"
    ].activate(
        deployment_id="deployment-001"
    )

    artifact_content = (
        b"TODOBA SECURE EX5 PACKAGE"
    )

    publish_valid_package(
        publication=(
            environment[
                "package_publication"
            ]
        ),
        content=artifact_content,
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 200

    assert response.content == artifact_content

    assert (
        response.headers[
            "content-type"
        ]
        == "application/octet-stream"
    )

    content_disposition = (
        response.headers[
            "content-disposition"
        ]
    )

    assert (
        "attachment"
        in content_disposition.lower()
    )

    assert (
        CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
        in content_disposition
    )

    assert (
        int(
            response.headers[
                "content-length"
            ]
        )
        == len(
            artifact_content
        )
    )


def test_package_delivery_does_not_expose_package_path_to_customer(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    environment[
        "entitlement_registry"
    ].activate(
        deployment_id="deployment-001"
    )

    artifact = publish_valid_package(
        publication=(
            environment[
                "package_publication"
            ]
        )
    )

    response = environment[
        "client"
    ].get(
        "/customer/deployments/deployment-001/package",
        headers=authorization_header(
            environment[
                "customer_001_credential"
            ]
        ),
    )

    assert response.status_code == 200

    assert (
        str(
            artifact
        ).encode(
            "utf-8"
        )
        not in response.content
    )

    assert (
        str(
            artifact
        )
        not in str(
            response.headers
        )
    )


def test_router_factory_requires_authoritative_dependencies(
    tmp_path: Path,
) -> None:
    environment = build_customer_package_api(
        tmp_path
    )

    publication = environment[
        "package_publication"
    ]

    try:
        create_customer_deployment_package_router(
            customer_authentication_dependency=(
                lambda: None
            ),
            deployment_authorizer=None,
            entitlement_authorizer=None,
            package_publication=publication,
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Router factory accepted invalid "
            "authorization owners."
        )


def test_customer_package_route_accepts_only_deployment_and_authenticated_customer(
) -> None:
    source_signature = inspect.signature(
        create_customer_deployment_package_router
    )

    assert tuple(
        source_signature.parameters
    ) == (
        "customer_authentication_dependency",
        "deployment_authorizer",
        "entitlement_authorizer",
        "package_publication",
    )

    forbidden_factory_inputs = {
        "customer_id",
        "agent_id",
        "credential",
        "payment_id",
        "subscription_id",
        "package_path",
        "package_root",
    }

    assert not (
        forbidden_factory_inputs
        & set(
            source_signature.parameters
        )
    )
