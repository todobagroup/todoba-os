"""
Owner tests for Customer Setup Package API.

Proves:
- one setup package GET route with handoff/continuation authority
- no caller-controlled commercial identity
- malformed/missing setup bearer returns 401
- R3 authorization failures return 401
- R3 infrastructure faults remain server faults
- ACTIVE but unbound setup returns 409
- BOUND deployment/customer identities must converge
- ACTIVE entitlement is mandatory
- publication is authoritative package state
- missing package returns 404
- corrupt/mismatched publication fails closed
- successful response exposes only EX5 bytes and filename
- no Customer Access Credential is issued or accepted
"""

from __future__ import annotations

import inspect
from datetime import datetime
from datetime import timezone

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPublishedPackage,
)
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationAuthorization,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
)
from backend.commercial.customer_setup_package_api import (
    create_customer_setup_package_router,
)


HANDOFF_ID = (
    "a" * 32
)

CONTINUATION_ID = (
    "c" * 32
)

CONTINUATION_CREDENTIAL = (
    f"tdbsc1.{CONTINUATION_ID}."
    "continuation-secret-value"
)

NOW = datetime(
    2026,
    9,
    1,
    4,
    41,
    53,
    tzinfo=timezone.utc,
)

SETUP_ACTIVATION_ID = (
    "setup-activation-001"
)

CUSTOMER_ID = (
    "customer-001"
)

DEPLOYMENT_ID = (
    "deployment-001"
)

ARTIFACT_SHA256 = (
    "b" * 64
)

ARTIFACT_CONTENT = (
    b"TODOBA TRUSTED AGENT TEST EX5"
)


def make_setup_authorization(
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str | None = DEPLOYMENT_ID,
) -> CustomerSetupHandoffAuthorization:
    return CustomerSetupHandoffAuthorization(
        handoff_id=HANDOFF_ID,
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=customer_id,
        deployment_id=deployment_id,
    )


def make_deployment(
    *,
    deployment_id: str = DEPLOYMENT_ID,
    customer_id: str = CUSTOMER_ID,
):
    return SimpleNamespace(
        deployment_id=deployment_id,
        customer_id=customer_id,
        agent_id="trusted-agent-001",
    )


def make_published(
    artifact: Path,
    *,
    deployment_id: str = DEPLOYMENT_ID,
) -> CustomerDeploymentPublishedPackage:
    return CustomerDeploymentPublishedPackage(
        deployment_id=deployment_id,
        artifact_path=artifact,
        artifact_sha256=(
            ARTIFACT_SHA256
        ),
        artifact_size_bytes=(
            artifact.stat().st_size
        ),
    )


def build_dependencies(
    tmp_path: Path,
    *,
    authorization=None,
    deployment=None,
    entitled=None,
    published=None,
):
    artifact = (
        tmp_path
        / "TODOBA_Trusted_Agent.ex5"
    )

    artifact.write_bytes(
        ARTIFACT_CONTENT
    )

    if authorization is None:
        authorization = (
            make_setup_authorization()
        )

    if deployment is None:
        deployment = (
            make_deployment()
        )

    if entitled is None:
        entitled = deployment

    if published is None:
        published = make_published(
            artifact
        )

    authorize_setup_handoff = Mock(
        return_value=authorization
    )

    authorize_deployment = Mock(
        return_value=deployment
    )

    authorize_entitlement = Mock(
        return_value=entitled
    )

    package_publication = Mock()

    package_publication.get_published_package.return_value = (
        published
    )

    return {
        "artifact": artifact,
        "authorization": authorization,
        "deployment": deployment,
        "authorize_setup_handoff": (
            authorize_setup_handoff
        ),
        "authorize_deployment": (
            authorize_deployment
        ),
        "authorize_entitlement": (
            authorize_entitlement
        ),
        "package_publication": (
            package_publication
        ),
    }


def make_router(
    environment,
):
    return create_customer_setup_package_router(
        authorize_setup_handoff=(
            environment[
                "authorize_setup_handoff"
            ]
        ),
        authorize_deployment=(
            environment[
                "authorize_deployment"
            ]
        ),
        authorize_entitlement=(
            environment[
                "authorize_entitlement"
            ]
        ),
        package_publication=(
            environment[
                "package_publication"
            ]
        ),
    )


def make_client(
    environment,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        make_router(
            environment
        )
    )

    return TestClient(
        app,
        raise_server_exceptions=False,
    )


def find_endpoint(
    environment,
):
    router = make_router(
        environment
    )

    matching = [
        route
        for route in router.routes
        if getattr(
            route,
            "path",
            None,
        )
        == "/customer/setup/package"
    ]

    assert len(
        matching
    ) == 1

    return matching[
        0
    ].endpoint


def bearer_header(
    credential: str = "tdbsh1.test.secret",
) -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {credential}"
        )
    }


def make_continuation_authorization(
    *,
    setup_activation_id: str = SETUP_ACTIVATION_ID,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
) -> CustomerSetupBuildContinuationAuthorization:
    return CustomerSetupBuildContinuationAuthorization(
        continuation_id=CONTINUATION_ID,
        setup_activation_id=setup_activation_id,
        customer_id=customer_id,
        deployment_id=deployment_id,
    )


def make_continuation_activation(
    *,
    status: str = "BOUND",
    setup_activation_id: str = SETUP_ACTIVATION_ID,
    customer_id: str = CUSTOMER_ID,
    deployment_id=DEPLOYMENT_ID,
):
    return SimpleNamespace(
        setup_activation_id=setup_activation_id,
        customer_id=customer_id,
        status=SimpleNamespace(
            value=status
        ),
        deployment_id=deployment_id,
    )


def make_continuation_router(
    environment,
    *,
    continuation_service,
    setup_activation_service,
    clock=lambda: NOW,
):
    return create_customer_setup_package_router(
        authorize_setup_handoff=(
            environment[
                "authorize_setup_handoff"
            ]
        ),
        authorize_deployment=(
            environment[
                "authorize_deployment"
            ]
        ),
        authorize_entitlement=(
            environment[
                "authorize_entitlement"
            ]
        ),
        package_publication=(
            environment[
                "package_publication"
            ]
        ),
        continuation_service=(
            continuation_service
        ),
        setup_activation_service=(
            setup_activation_service
        ),
        clock=clock,
    )


def make_continuation_client(
    environment,
    *,
    authorization_result=None,
    activation=None,
    clock=lambda: NOW,
):
    if authorization_result is None:
        authorization_result = (
            make_continuation_authorization()
        )

    if activation is None:
        activation = (
            make_continuation_activation()
        )

    continuation_service = Mock()
    continuation_service.authorize.return_value = (
        authorization_result
    )

    setup_activation_service = Mock()
    setup_activation_service.get.return_value = (
        activation
    )

    app = FastAPI()

    app.include_router(
        make_continuation_router(
            environment,
            continuation_service=(
                continuation_service
            ),
            setup_activation_service=(
                setup_activation_service
            ),
            clock=clock,
        )
    )

    return {
        "client": TestClient(
            app,
            raise_server_exceptions=False,
        ),
        "continuation_service": (
            continuation_service
        ),
        "setup_activation_service": (
            setup_activation_service
        ),
    }


def test_router_has_exact_setup_package_get_surface(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    router = make_router(
        environment
    )

    routes = [
        route
        for route in router.routes
        if getattr(
            route,
            "path",
            None,
        )
        == "/customer/setup/package"
    ]

    assert len(
        routes
    ) == 1

    route = routes[
        0
    ]

    assert route.methods == {
        "GET"
    }

    parameters = inspect.signature(
        route.endpoint
    ).parameters

    assert tuple(
        parameters
    ) == (
        "authorization",
    )


def test_success_downloads_authoritative_ex5(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 200
    assert response.content == ARTIFACT_CONTENT

    assert (
        response.headers[
            "content-type"
        ]
        == "application/octet-stream"
    )

    assert (
        "TODOBA_Trusted_Agent.ex5"
        in response.headers[
            "content-disposition"
        ]
    )

    environment[
        "authorize_setup_handoff"
    ].assert_called_once_with(
        "tdbsh1.test.secret"
    )

    environment[
        "authorize_deployment"
    ].assert_called_once()

    deployment_call = (
        environment[
            "authorize_deployment"
        ].call_args.kwargs
    )

    assert (
        deployment_call[
            "deployment_id"
        ]
        == DEPLOYMENT_ID
    )

    assert (
        deployment_call[
            "authenticated_customer"
        ].customer_id
        == CUSTOMER_ID
    )

    environment[
        "authorize_entitlement"
    ].assert_called_once_with(
        authorized_deployment=(
            environment[
                "deployment"
            ]
        )
    )

    environment[
        "package_publication"
    ].get_published_package.assert_called_once_with(
        deployment_id=(
            DEPLOYMENT_ID
        )
    )


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic abc",
        "Bearer",
        "Bearer ",
        "Bearer  token",
        "Bearer token ",
        "bearer token",
    ],
)
def test_missing_or_malformed_setup_bearer_returns_401(
    tmp_path: Path,
    authorization: str | None,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    client = make_client(
        environment
    )

    headers = {}

    if authorization is not None:
        headers[
            "Authorization"
        ] = authorization

    response = client.get(
        "/customer/setup/package",
        headers=headers,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Customer setup authentication failed."
        )
    }

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()


def test_invalid_setup_handoff_returns_401(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "authorize_setup_handoff"
    ].side_effect = ValueError(
        "invalid setup handoff"
    )

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 401

    environment[
        "authorize_deployment"
    ].assert_not_called()


def test_setup_handoff_infrastructure_fault_is_not_auth_failure(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "authorize_setup_handoff"
    ].side_effect = RuntimeError(
        "handoff store failure"
    )

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 500

    environment[
        "authorize_deployment"
    ].assert_not_called()


def test_invalid_handoff_authorization_result_fails_closed(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "authorize_setup_handoff"
    ].return_value = SimpleNamespace(
        customer_id=CUSTOMER_ID,
        deployment_id=DEPLOYMENT_ID,
    )

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Setup handoff authorizer returned "
            "invalid result"
        ),
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )


def test_active_unbound_setup_returns_409(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path,
        authorization=(
            make_setup_authorization(
                deployment_id=None
            )
        ),
    )

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Customer setup package is not ready."
        )
    }

    environment[
        "authorize_deployment"
    ].assert_not_called()

    environment[
        "authorize_entitlement"
    ].assert_not_called()

    environment[
        "package_publication"
    ].get_published_package.assert_not_called()


def test_bound_setup_missing_authoritative_deployment_fails_closed(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "authorize_deployment"
    ].return_value = None

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "deployment authorization "
            "did not converge"
        ),
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )

    environment[
        "authorize_entitlement"
    ].assert_not_called()


def test_bound_deployment_identity_must_match_handoff(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path,
        deployment=(
            make_deployment(
                deployment_id=(
                    "different-deployment"
                )
            )
        ),
    )

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match="deployment identity mismatch",
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )


def test_bound_customer_identity_must_match_handoff(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path,
        deployment=(
            make_deployment(
                customer_id=(
                    "different-customer"
                )
            )
        ),
    )

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match="customer identity mismatch",
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )


def test_missing_active_entitlement_returns_403(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "authorize_entitlement"
    ].return_value = None

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Customer deployment entitlement required."
        )
    }

    environment[
        "package_publication"
    ].get_published_package.assert_not_called()


def test_entitlement_authorizer_must_return_same_deployment(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "authorize_entitlement"
    ].return_value = make_deployment()

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "authorization returned different "
            "deployment state"
        ),
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )


def test_missing_published_package_returns_404(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "package_publication"
    ].get_published_package.return_value = None

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Customer setup package not found."
        )
    }


def test_invalid_publication_result_fails_closed(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "package_publication"
    ].get_published_package.return_value = (
        SimpleNamespace(
            deployment_id=DEPLOYMENT_ID,
            artifact_path=environment[
                "artifact"
            ],
        )
    )

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "publication returned invalid result"
        ),
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )


def test_publication_deployment_identity_must_match(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    environment[
        "package_publication"
    ].get_published_package.return_value = (
        make_published(
            environment[
                "artifact"
            ],
            deployment_id=(
                "different-deployment"
            ),
        )
    )

    endpoint = find_endpoint(
        environment
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "publication deployment identity "
            "mismatch"
        ),
    ):
        endpoint(
            authorization=(
                "Bearer tdbsh1.test.secret"
            )
        )


def test_success_response_does_not_serialize_internal_identity_or_paths(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    client = make_client(
        environment
    )

    response = client.get(
        "/customer/setup/package",
        headers=bearer_header(),
    )

    assert response.status_code == 200
    assert response.content == ARTIFACT_CONTENT

    for forbidden in (
        CUSTOMER_ID.encode(),
        DEPLOYMENT_ID.encode(),
        SETUP_ACTIVATION_ID.encode(),
        HANDOFF_ID.encode(),
        str(
            environment[
                "artifact"
            ]
        ).encode(),
    ):
        assert forbidden not in response.content


def test_router_factory_requires_all_authorization_owners(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match=(
            "authorize_setup_handoff "
            "must be callable"
        ),
    ):
        create_customer_setup_package_router(
            authorize_setup_handoff=None,
            authorize_deployment=(
                environment[
                    "authorize_deployment"
                ]
            ),
            authorize_entitlement=(
                environment[
                    "authorize_entitlement"
                ]
            ),
            package_publication=(
                environment[
                    "package_publication"
                ]
            ),
        )

    with pytest.raises(
        TypeError,
        match=(
            "authorize_deployment "
            "must be callable"
        ),
    ):
        create_customer_setup_package_router(
            authorize_setup_handoff=(
                environment[
                    "authorize_setup_handoff"
                ]
            ),
            authorize_deployment=None,
            authorize_entitlement=(
                environment[
                    "authorize_entitlement"
                ]
            ),
            package_publication=(
                environment[
                    "package_publication"
                ]
            ),
        )

    with pytest.raises(
        TypeError,
        match=(
            "authorize_entitlement "
            "must be callable"
        ),
    ):
        create_customer_setup_package_router(
            authorize_setup_handoff=(
                environment[
                    "authorize_setup_handoff"
                ]
            ),
            authorize_deployment=(
                environment[
                    "authorize_deployment"
                ]
            ),
            authorize_entitlement=None,
            package_publication=(
                environment[
                    "package_publication"
                ]
            ),
        )

    with pytest.raises(
        TypeError,
        match=(
            "package_publication must expose "
            "callable get_published_package"
        ),
    ):
        create_customer_setup_package_router(
            authorize_setup_handoff=(
                environment[
                    "authorize_setup_handoff"
                ]
            ),
            authorize_deployment=(
                environment[
                    "authorize_deployment"
                ]
            ),
            authorize_entitlement=(
                environment[
                    "authorize_entitlement"
                ]
            ),
            package_publication=object(),
        )



def test_continuation_bearer_without_optional_owners_returns_401(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    response = make_client(
        environment
    ).get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 401

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()

    environment[
        "authorize_entitlement"
    ].assert_not_called()

    environment[
        "package_publication"
    ].get_published_package.assert_not_called()


def test_bound_continuation_downloads_published_package(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 200

    assert (
        response.content
        == environment[
            "artifact"
        ].read_bytes()
    )

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    continuation[
        "continuation_service"
    ].authorize.assert_called_once_with(
        continuation_credential=(
            CONTINUATION_CREDENTIAL
        ),
        current_time=NOW,
    )

    continuation[
        "setup_activation_service"
    ].get.assert_called_once_with(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        )
    )

    environment[
        "authorize_deployment"
    ].assert_called_once()

    environment[
        "authorize_entitlement"
    ].assert_called_once()

    environment[
        "package_publication"
    ].get_published_package.assert_called_once_with(
        deployment_id=DEPLOYMENT_ID
    )


def test_active_continuation_setup_is_not_ready_for_delivery(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment,
            activation=(
                make_continuation_activation(
                    status="ACTIVE",
                    deployment_id=None,
                )
            ),
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Customer setup package is not ready."
        )
    }

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()

    environment[
        "authorize_entitlement"
    ].assert_not_called()

    environment[
        "package_publication"
    ].get_published_package.assert_not_called()


def test_suspended_continuation_setup_fails_closed(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment,
            activation=(
                make_continuation_activation(
                    status="SUSPENDED",
                )
            ),
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 401

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()

    environment[
        "authorize_entitlement"
    ].assert_not_called()

    environment[
        "package_publication"
    ].get_published_package.assert_not_called()


def test_invalid_continuation_returns_401_without_handoff_fallback(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment
        )
    )

    continuation[
        "continuation_service"
    ].authorize.side_effect = ValueError(
        "invalid continuation"
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 401

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    continuation[
        "setup_activation_service"
    ].get.assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()


def test_continuation_infrastructure_fault_is_not_auth_failure(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment
        )
    )

    continuation[
        "continuation_service"
    ].authorize.side_effect = RuntimeError(
        "continuation store failure"
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 500

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    continuation[
        "setup_activation_service"
    ].get.assert_not_called()


def test_invalid_continuation_authorization_result_fails_closed(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment
        )
    )

    continuation[
        "continuation_service"
    ].authorize.return_value = (
        SimpleNamespace(
            customer_id=CUSTOMER_ID,
            deployment_id=DEPLOYMENT_ID,
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 500

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    continuation[
        "setup_activation_service"
    ].get.assert_not_called()


def test_bound_continuation_activation_deployment_must_converge(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment,
            activation=(
                make_continuation_activation(
                    deployment_id=(
                        "different-deployment"
                    ),
                )
            ),
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 500

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()

    environment[
        "authorize_entitlement"
    ].assert_not_called()


def test_bound_continuation_activation_customer_must_converge(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment,
            activation=(
                make_continuation_activation(
                    customer_id=(
                        "different-customer"
                    ),
                )
            ),
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 500

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()

    environment[
        "authorize_entitlement"
    ].assert_not_called()


def test_continuation_dependencies_must_be_injected_as_pair(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match=(
            "continuation_service and "
            "setup_activation_service must be "
            "provided together"
        ),
    ):
        create_customer_setup_package_router(
            authorize_setup_handoff=(
                environment[
                    "authorize_setup_handoff"
                ]
            ),
            authorize_deployment=(
                environment[
                    "authorize_deployment"
                ]
            ),
            authorize_entitlement=(
                environment[
                    "authorize_entitlement"
                ]
            ),
            package_publication=(
                environment[
                    "package_publication"
                ]
            ),
            continuation_service=Mock(),
        )

    with pytest.raises(
        TypeError,
        match=(
            "continuation_service and "
            "setup_activation_service must be "
            "provided together"
        ),
    ):
        create_customer_setup_package_router(
            authorize_setup_handoff=(
                environment[
                    "authorize_setup_handoff"
                ]
            ),
            authorize_deployment=(
                environment[
                    "authorize_deployment"
                ]
            ),
            authorize_entitlement=(
                environment[
                    "authorize_entitlement"
                ]
            ),
            package_publication=(
                environment[
                    "package_publication"
                ]
            ),
            setup_activation_service=Mock(),
        )


def test_continuation_clock_must_be_timezone_aware(
    tmp_path: Path,
) -> None:
    environment = build_dependencies(
        tmp_path
    )

    continuation = (
        make_continuation_client(
            environment,
            clock=(
                lambda: datetime(
                    2026,
                    9,
                    1,
                    4,
                    41,
                    53,
                )
            ),
        )
    )

    response = continuation[
        "client"
    ].get(
        "/customer/setup/package",
        headers=bearer_header(
            CONTINUATION_CREDENTIAL
        ),
    )

    assert response.status_code == 500

    continuation[
        "continuation_service"
    ].authorize.assert_not_called()

    environment[
        "authorize_setup_handoff"
    ].assert_not_called()

    environment[
        "authorize_deployment"
    ].assert_not_called()


def test_api_source_has_no_customer_access_or_mutation_ownership(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_package_api.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "CustomerAccessCredentialRegistry",
        "CustomerAccessProvisioningService",
        "issue_for_request",
        "initialize_empty",
        "activate_bootstrap",
        "prepare_bootstrap",
        "build_package",
        "register_build_request",
        "setup_activation_service.bind",
    )

    for token in forbidden:
        assert token not in source

    assert (
        "/customer/setup/package"
        in source
    )

    assert (
        "/customer/deployments/{deployment_id}/package"
        not in source
    )
