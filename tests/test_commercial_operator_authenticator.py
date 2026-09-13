import pytest

from backend.commercial.commercial_operator_authenticator import (
    CommercialOperatorAuthenticator,
)


def test_valid_operator_credentials_authenticate_server_side_identity():
    authenticator = CommercialOperatorAuthenticator(
        operator_id="operator-founder",
        operator_secret="operator-secret-001",
    )

    authenticated_operator_id = authenticator.authenticate(
        operator_id="operator-founder",
        authorization="Bearer operator-secret-001",
    )

    assert authenticated_operator_id == "operator-founder"


@pytest.mark.parametrize(
    ("operator_id", "authorization"),
    [
        ("operator-founder", None),
        ("operator-founder", ""),
        ("operator-founder", "operator-secret-001"),
        ("operator-founder", "Bearer"),
        ("operator-founder", "Bearer wrong-secret"),
        ("operator-forged", "Bearer operator-secret-001"),
        (None, "Bearer operator-secret-001"),
        ("", "Bearer operator-secret-001"),
    ],
)
def test_unverified_caller_cannot_become_operator(
    operator_id,
    authorization,
):
    authenticator = CommercialOperatorAuthenticator(
        operator_id="operator-founder",
        operator_secret="operator-secret-001",
    )

    assert (
        authenticator.authenticate(
            operator_id=operator_id,
            authorization=authorization,
        )
        is None
    )


def test_operator_authenticator_exposes_no_payment_authority():
    authenticator = CommercialOperatorAuthenticator(
        operator_id="operator-founder",
        operator_secret="operator-secret-001",
    )

    forbidden_methods = (
        "confirm",
        "reconcile",
        "publish",
        "receive",
        "build_assertion",
        "verify_payment",
        "settle",
        "activate_setup",
        "activate_entitlement",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            authenticator,
            method_name,
        )
