"""
TODOBA Customer HTTP Authentication Dependency Tests

Security proof:
- Authorization Bearer is the only customer credential transport
- valid credential delivers authoritative CustomerIdentity
- malformed, unknown, wrong, and revoked credentials fail closed
- authentication failures converge on one HTTP 401 contract
- query and body credentials are not accepted
- dependency passes only the extracted bearer credential to
  CustomerAuthenticator
- authentication does not mutate credential durable state
- customer_id, deployment_id, and agent_id are not caller auth inputs

All durable state is isolated beneath pytest tmp_path.
"""

from inspect import signature
from pathlib import Path

from fastapi import Depends
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.commercial.customer_access_credential_registry import (
    CUSTOMER_ACCESS_CREDENTIAL_PREFIX,
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_authentication_dependency import (
    create_customer_authentication_dependency,
)
from backend.commercial.customer_authenticator import (
    CustomerAuthenticator,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


def build_stack(
    tmp_path: Path,
) -> tuple[
    TestClient,
    CustomerAuthenticator,
    CustomerAccessCredentialRegistry,
    CustomerIdentity,
]:
    identities = CustomerIdentityRegistry(
        tmp_path
        / "customer_identities.json"
    )

    identities.initialize_empty()

    identity = CustomerIdentity(
        customer_id="customer-http-001"
    )

    identities.register(
        identity
    )

    credentials = CustomerAccessCredentialRegistry(
        tmp_path
        / "customer_access_credentials.json",
        customer_identity_registry=identities,
    )

    credentials.initialize_empty()

    authenticator = CustomerAuthenticator(
        credential_registry=credentials
    )

    require_customer = (
        create_customer_authentication_dependency(
            authenticator
        )
    )

    app = FastAPI()

    @app.get("/customer-proof")
    def customer_proof(
        authenticated_customer: CustomerIdentity = Depends(
            require_customer
        ),
    ):
        return {
            "customer_id": (
                authenticated_customer.customer_id
            )
        }

    @app.post("/customer-proof")
    def customer_proof_post(
        authenticated_customer: CustomerIdentity = Depends(
            require_customer
        ),
    ):
        return {
            "customer_id": (
                authenticated_customer.customer_id
            )
        }

    return (
        TestClient(app),
        authenticator,
        credentials,
        identity,
    )


def assert_authentication_failure(
    response,
) -> None:
    assert response.status_code == 401

    assert response.json() == {
        "detail": "Customer authentication failed."
    }

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )


def test_factory_requires_customer_authenticator() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerAuthenticator",
    ):
        create_customer_authentication_dependency(
            object()
        )


def test_dependency_signature_accepts_only_authorization_header(
    tmp_path: Path,
) -> None:
    (
        _,
        authenticator,
        _,
        _,
    ) = build_stack(
        tmp_path
    )

    dependency = (
        create_customer_authentication_dependency(
            authenticator
        )
    )

    parameters = tuple(
        signature(
            dependency
        ).parameters
    )

    assert parameters == (
        "authorization",
    )

    assert "customer_id" not in parameters
    assert "deployment_id" not in parameters
    assert "agent_id" not in parameters
    assert "access_credential" not in parameters
    assert "token" not in parameters


def test_valid_bearer_returns_authoritative_customer_identity(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {issued.access_credential}"
            )
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "customer_id": identity.customer_id
    }


def test_extra_space_after_bearer_does_not_change_identity(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                "Bearer    "
                f"{issued.access_credential}   "
            )
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "customer_id": identity.customer_id
    }


@pytest.mark.parametrize(
    "authorization",
    (
        "",
        "   ",
        "Bearer",
        "Bearer ",
        "Basic anything",
        "bearer anything",
        "Token anything",
    ),
)
def test_missing_or_invalid_authorization_scheme_fails_closed(
    tmp_path: Path,
    authorization: str,
) -> None:
    (
        client,
        _,
        _,
        _,
    ) = build_stack(
        tmp_path
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": authorization
        },
    )

    assert_authentication_failure(
        response
    )


def test_missing_authorization_header_fails_closed(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        _,
        _,
    ) = build_stack(
        tmp_path
    )

    response = client.get(
        "/customer-proof"
    )

    assert_authentication_failure(
        response
    )


def test_malformed_customer_credential_fails_closed(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        _,
        _,
    ) = build_stack(
        tmp_path
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                "Bearer not-a-customer-credential"
            )
        },
    )

    assert_authentication_failure(
        response
    )


def test_unknown_customer_credential_id_fails_closed(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        _,
        _,
    ) = build_stack(
        tmp_path
    )

    credential = (
        f"{CUSTOMER_ACCESS_CREDENTIAL_PREFIX}."
        f"{'f' * 32}."
        "unknown-secret"
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {credential}"
            )
        },
    )

    assert_authentication_failure(
        response
    )


def test_wrong_customer_credential_secret_fails_closed(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    parts = issued.access_credential.split(
        "."
    )

    wrong = (
        f"{parts[0]}."
        f"{parts[1]}."
        "wrong-secret"
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {wrong}"
            )
        },
    )

    assert_authentication_failure(
        response
    )

    assert (
        issued.access_credential
        not in response.text
    )

    assert wrong not in response.text


def test_revoked_customer_credential_fails_closed(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    credentials.revoke(
        credential_id=issued.credential_id
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {issued.access_credential}"
            )
        },
    )

    assert_authentication_failure(
        response
    )


def test_query_credential_is_not_accepted(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    response = client.get(
        "/customer-proof",
        params={
            "access_credential": (
                issued.access_credential
            )
        },
    )

    assert_authentication_failure(
        response
    )


def test_body_credential_is_not_accepted(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    response = client.post(
        "/customer-proof",
        json={
            "access_credential": (
                issued.access_credential
            )
        },
    )

    assert_authentication_failure(
        response
    )


def test_query_and_body_cannot_replace_authorization_header(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    response = client.post(
        "/customer-proof",
        params={
            "customer_id": (
                identity.customer_id
            ),
            "deployment_id": (
                "deployment-forged"
            ),
        },
        json={
            "access_credential": (
                issued.access_credential
            ),
            "customer_id": (
                identity.customer_id
            ),
        },
    )

    assert_authentication_failure(
        response
    )


@pytest.mark.parametrize(
    "authorization",
    (
        None,
        "Basic invalid",
        "Bearer malformed",
        (
            "Bearer "
            + CUSTOMER_ACCESS_CREDENTIAL_PREFIX
            + "."
            + ("f" * 32)
            + ".unknown"
        ),
    ),
)
def test_http_authentication_failures_share_one_contract(
    tmp_path: Path,
    authorization: str | None,
) -> None:
    (
        client,
        _,
        _,
        _,
    ) = build_stack(
        tmp_path
    )

    headers = {}

    if authorization is not None:
        headers[
            "Authorization"
        ] = authorization

    response = client.get(
        "/customer-proof",
        headers=headers,
    )

    assert_authentication_failure(
        response
    )


def test_dependency_passes_only_extracted_credential_to_authenticator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        client,
        authenticator,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    supplied = []

    original_authenticate = (
        authenticator.authenticate
    )

    def recording_authenticate(
        access_credential: str | None,
    ):
        supplied.append(
            access_credential
        )

        return original_authenticate(
            access_credential
        )

    monkeypatch.setattr(
        authenticator,
        "authenticate",
        recording_authenticate,
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {issued.access_credential}"
            )
        },
    )

    assert response.status_code == 200

    assert supplied == [
        issued.access_credential
    ]


def test_authenticator_rejection_maps_to_http_401(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        client,
        authenticator,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    monkeypatch.setattr(
        authenticator,
        "authenticate",
        lambda _access_credential: None,
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {issued.access_credential}"
            )
        },
    )

    assert_authentication_failure(
        response
    )


def test_valid_http_authentication_does_not_expose_bearer_secret(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    response = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {issued.access_credential}"
            )
        },
    )

    assert response.status_code == 200

    assert (
        issued.access_credential
        not in response.text
    )


def test_http_authentication_does_not_mutate_credential_truth(
    tmp_path: Path,
) -> None:
    (
        client,
        _,
        credentials,
        identity,
    ) = build_stack(
        tmp_path
    )

    issued = credentials.issue(
        customer_id=identity.customer_id
    )

    storage_path = (
        tmp_path
        / "customer_access_credentials.json"
    )

    before = storage_path.read_bytes()

    valid = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {issued.access_credential}"
            )
        },
    )

    assert valid.status_code == 200
    assert storage_path.read_bytes() == before

    parts = issued.access_credential.split(
        "."
    )

    wrong = (
        f"{parts[0]}."
        f"{parts[1]}."
        "wrong-secret"
    )

    invalid = client.get(
        "/customer-proof",
        headers={
            "Authorization": (
                f"Bearer {wrong}"
            )
        },
    )

    assert_authentication_failure(
        invalid
    )

    assert storage_path.read_bytes() == before
