from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.commercial.customer_setup_access_code_issuance_admin_api import (
    create_customer_setup_access_code_issuance_admin_router,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeIssuance,
)


_PATH = "/internal/commercial/setup/access-codes"


class RecordingAccessCodeService:
    def __init__(self):
        self.calls = []

    def issue_once(
        self,
        *,
        setup_activation_id,
    ):
        self.calls.append(setup_activation_id)

        return CustomerSetupAccessCodeIssuance(
            access_code_id="access-code-server-owned",
            setup_activation_id=setup_activation_id,
            customer_id="customer-server-owned",
            activation_code="TDAC.server-owned.secret",
        )


def _build_client(
    *,
    authentication_error=None,
    service=None,
):
    owner = (
        service
        if service is not None
        else RecordingAccessCodeService()
    )

    def require_operator():
        if authentication_error is not None:
            raise authentication_error

        return "operator-server-owned"

    router = (
        create_customer_setup_access_code_issuance_admin_router(
            commercial_operator_authentication_dependency=(
                require_operator
            ),
            access_code_service=owner,
        )
    )

    app = FastAPI()
    app.include_router(router)

    return TestClient(app), owner


def test_authenticated_operator_issues_from_activation_identity_only():
    client, service = _build_client()

    response = client.post(
        _PATH,
        json={
            "setup_activation_id": (
                "setup-activation-paid-001"
            ),
        },
    )

    assert response.status_code == 200

    assert service.calls == [
        "setup-activation-paid-001",
    ]

    assert response.json() == {
        "setup_activation_id": (
            "setup-activation-paid-001"
        ),
        "activation_code": (
            "TDAC.server-owned.secret"
        ),
    }


def test_authentication_failure_blocks_issuance():
    client, service = _build_client(
        authentication_error=HTTPException(
            status_code=401,
            detail=(
                "Commercial operator authentication "
                "failed."
            ),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )
    )

    response = client.post(
        _PATH,
        json={
            "setup_activation_id": (
                "setup-activation-paid-001"
            ),
        },
    )

    assert response.status_code == 401
    assert service.calls == []


def test_caller_cannot_supply_downstream_authority():
    forbidden_fields = {
        "operator_id": "operator-forged",
        "customer_id": "customer-forged",
        "access_code_id": "access-code-forged",
        "activation_code": "code-forged",
        "deployment_id": "deployment-forged",
        "payment_intent_id": "payment-forged",
        "settlement_id": "settlement-forged",
        "status": "ACTIVE",
    }

    for field_name, field_value in forbidden_fields.items():
        client, service = _build_client()

        response = client.post(
            _PATH,
            json={
                "setup_activation_id": (
                    "setup-activation-paid-001"
                ),
                field_name: field_value,
            },
        )

        assert response.status_code == 422
        assert service.calls == []


def test_response_exposes_only_activation_code_and_identity():
    client, _ = _build_client()

    response = client.post(
        _PATH,
        json={
            "setup_activation_id": (
                "setup-activation-paid-001"
            ),
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "setup_activation_id",
        "activation_code",
    }


def test_router_requires_authentication_dependency():
    try:
        create_customer_setup_access_code_issuance_admin_router(
            commercial_operator_authentication_dependency=(
                object()
            ),
            access_code_service=(
                RecordingAccessCodeService()
            ),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Non-callable authentication dependency "
            "was accepted."
        )


def test_router_requires_replay_safe_issuance_owner():
    class IssueOnlyOwner:
        def issue(self, *, setup_activation_id):
            raise AssertionError(
                "Unsafe issue() must not be used."
            )

    try:
        create_customer_setup_access_code_issuance_admin_router(
            commercial_operator_authentication_dependency=(
                lambda: "operator-server-owned"
            ),
            access_code_service=IssueOnlyOwner(),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Owner without issue_once() was accepted."
        )
