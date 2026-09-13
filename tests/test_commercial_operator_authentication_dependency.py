import asyncio

import pytest
from fastapi import HTTPException
from fastapi import status

from backend.commercial.commercial_operator_authenticator import (
    CommercialOperatorAuthenticator,
)
from backend.commercial.commercial_operator_authentication_dependency import (
    create_commercial_operator_authentication_dependency,
)


def _build_dependency():
    authenticator = CommercialOperatorAuthenticator(
        operator_id="operator-founder",
        operator_secret="operator-secret-001",
    )

    return create_commercial_operator_authentication_dependency(
        authenticator
    )


def _call_dependency(
    dependency,
    *,
    operator_id,
    authorization,
):
    result = dependency(
        operator_id=operator_id,
        authorization=authorization,
    )

    if asyncio.iscoroutine(result):
        return asyncio.run(result)

    return result


def test_valid_credentials_deliver_authenticated_operator_identity():
    dependency = _build_dependency()

    authenticated_operator_id = _call_dependency(
        dependency,
        operator_id="operator-founder",
        authorization="Bearer operator-secret-001",
    )

    assert authenticated_operator_id == "operator-founder"


@pytest.mark.parametrize(
    ("operator_id", "authorization"),
    [
        (None, None),
        ("operator-founder", None),
        (None, "Bearer operator-secret-001"),
        ("operator-founder", ""),
        ("operator-founder", "operator-secret-001"),
        ("operator-founder", "Bearer"),
        ("operator-founder", "Bearer wrong-secret"),
        ("operator-forged", "Bearer operator-secret-001"),
    ],
)
def test_invalid_credentials_fail_closed_with_http_401(
    operator_id,
    authorization,
):
    dependency = _build_dependency()

    with pytest.raises(HTTPException) as exc_info:
        _call_dependency(
            dependency,
            operator_id=operator_id,
            authorization=authorization,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }


def test_dependency_requires_commercial_operator_authenticator():
    with pytest.raises(TypeError):
        create_commercial_operator_authentication_dependency(
            object()
        )


def test_dependency_exposes_no_payment_execution_authority():
    dependency = _build_dependency()

    forbidden_methods = (
        "confirm",
        "reconcile",
        "publish",
        "receive",
        "build_assertion",
        "verify_payment",
        "settle",
        "mark_paid",
        "activate_from_settlement",
        "activate_setup",
        "activate_entitlement",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            dependency,
            method_name,
        )
