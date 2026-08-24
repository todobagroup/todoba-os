"""
TODOBA Customer Authenticator Tests

Security proof:
- valid credential resolves authoritative CustomerIdentity
- caller never supplies customer_id or deployment_id
- malformed credentials fail closed
- unknown credentials fail closed
- wrong secrets fail closed
- credentials cannot be swapped across customers
- revoked credentials fail closed
- revocation survives restart
- verifier comparison uses compare_digest
- missing authoritative identity fails closed

All durable state is isolated beneath pytest tmp_path.
"""

from inspect import signature
from pathlib import Path

import pytest

import backend.commercial.customer_authenticator as authenticator_module
from backend.commercial.customer_access_credential_registry import (
    CUSTOMER_ACCESS_CREDENTIAL_PREFIX,
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_authenticator import (
    CustomerAuthenticator,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


def build_identity_registry(
    tmp_path: Path,
    *customer_ids: str,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        tmp_path / "customer_identities.json"
    )

    registry.initialize_empty()

    registry.register_many(
        CustomerIdentity(
            customer_id=customer_id
        )
        for customer_id in customer_ids
    )

    return registry


def build_auth_stack(
    tmp_path: Path,
    *customer_ids: str,
) -> tuple[
    CustomerAuthenticator,
    CustomerAccessCredentialRegistry,
    CustomerIdentityRegistry,
]:
    identities = build_identity_registry(
        tmp_path,
        *customer_ids,
    )

    credentials = CustomerAccessCredentialRegistry(
        tmp_path / "customer_access_credentials.json",
        customer_identity_registry=identities,
    )

    credentials.initialize_empty()

    authenticator = CustomerAuthenticator(
        credential_registry=credentials
    )

    return (
        authenticator,
        credentials,
        identities,
    )


def test_authenticate_signature_accepts_only_access_credential() -> None:
    parameters = tuple(
        signature(
            CustomerAuthenticator.authenticate
        ).parameters
    )

    assert parameters == (
        "self",
        "access_credential",
    )

    assert "customer_id" not in parameters
    assert "deployment_id" not in parameters
    assert "agent_id" not in parameters


def test_constructor_requires_customer_credential_registry() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerAccessCredentialRegistry",
    ):
        CustomerAuthenticator(
            credential_registry=object()
        )


def test_constructor_requires_ready_credential_registry(
    tmp_path: Path,
) -> None:
    identities = build_identity_registry(
        tmp_path,
        "customer-001",
    )

    credentials = CustomerAccessCredentialRegistry(
        tmp_path / "customer_access_credentials.json",
        customer_identity_registry=identities,
    )

    assert not credentials.is_ready()

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        CustomerAuthenticator(
            credential_registry=credentials
        )


def test_valid_credential_returns_authoritative_customer_identity(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        identities,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    expected = identities.get(
        customer_id="customer-001"
    )

    authenticated = authenticator.authenticate(
        issued.access_credential
    )

    assert expected is not None
    assert authenticated == expected
    assert isinstance(
        authenticated,
        CustomerIdentity,
    )


def test_outer_whitespace_does_not_change_valid_credential_identity(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    authenticated = authenticator.authenticate(
        f"  {issued.access_credential}  "
    )

    assert authenticated == CustomerIdentity(
        customer_id="customer-001"
    )


@pytest.mark.parametrize(
    "credential",
    (
        None,
        "",
        "   ",
        "not-a-customer-credential",
        "wrong-prefix." + ("a" * 32) + ".secret",
        CUSTOMER_ACCESS_CREDENTIAL_PREFIX + "..secret",
        CUSTOMER_ACCESS_CREDENTIAL_PREFIX
        + "."
        + ("a" * 32)
        + ".",
        CUSTOMER_ACCESS_CREDENTIAL_PREFIX
        + ".invalid-id.secret",
        CUSTOMER_ACCESS_CREDENTIAL_PREFIX
        + "."
        + ("a" * 32)
        + ".secret.extra",
    ),
)
def test_malformed_credentials_fail_closed(
    tmp_path: Path,
    credential,
) -> None:
    (
        authenticator,
        _,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    assert authenticator.authenticate(
        credential
    ) is None


def test_unknown_credential_id_fails_closed(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        _,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    unknown = (
        f"{CUSTOMER_ACCESS_CREDENTIAL_PREFIX}."
        f"{'f' * 32}."
        "unknown-secret"
    )

    assert authenticator.authenticate(
        unknown
    ) is None


def test_wrong_secret_fails_closed(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    parts = issued.access_credential.split(
        "."
    )

    wrong = (
        f"{parts[0]}."
        f"{parts[1]}."
        "wrong-secret"
    )

    assert authenticator.authenticate(
        wrong
    ) is None


def test_each_customer_credential_resolves_only_its_owner(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-A",
        "customer-B",
    )

    issued_a = credentials.issue(
        customer_id="customer-A"
    )

    issued_b = credentials.issue(
        customer_id="customer-B"
    )

    authenticated_a = authenticator.authenticate(
        issued_a.access_credential
    )

    authenticated_b = authenticator.authenticate(
        issued_b.access_credential
    )

    assert authenticated_a == CustomerIdentity(
        customer_id="customer-A"
    )

    assert authenticated_b == CustomerIdentity(
        customer_id="customer-B"
    )

    assert authenticated_a != authenticated_b


def test_credential_id_and_secret_cannot_be_swapped_between_customers(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-A",
        "customer-B",
    )

    issued_a = credentials.issue(
        customer_id="customer-A"
    )

    issued_b = credentials.issue(
        customer_id="customer-B"
    )

    parts_a = issued_a.access_credential.split(
        "."
    )

    parts_b = issued_b.access_credential.split(
        "."
    )

    forged_a_id_b_secret = (
        f"{parts_a[0]}."
        f"{parts_a[1]}."
        f"{parts_b[2]}"
    )

    forged_b_id_a_secret = (
        f"{parts_b[0]}."
        f"{parts_b[1]}."
        f"{parts_a[2]}"
    )

    assert authenticator.authenticate(
        forged_a_id_b_secret
    ) is None

    assert authenticator.authenticate(
        forged_b_id_a_secret
    ) is None


def test_revoked_credential_fails_closed(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    assert authenticator.authenticate(
        issued.access_credential
    ) is not None

    credentials.revoke(
        credential_id=issued.credential_id
    )

    assert authenticator.authenticate(
        issued.access_credential
    ) is None


def test_revoked_credential_fails_after_restart(
    tmp_path: Path,
) -> None:
    (
        _,
        credentials,
        identities,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    credentials.revoke(
        credential_id=issued.credential_id
    )

    restarted_credentials = (
        CustomerAccessCredentialRegistry(
            tmp_path
            / "customer_access_credentials.json",
            customer_identity_registry=identities,
        )
    )

    restarted_authenticator = CustomerAuthenticator(
        credential_registry=restarted_credentials
    )

    assert restarted_authenticator.authenticate(
        issued.access_credential
    ) is None


def test_valid_verifier_comparison_uses_compare_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    calls = []

    original_compare_digest = (
        authenticator_module.compare_digest
    )

    def recording_compare_digest(
        supplied: str,
        expected: str,
    ) -> bool:
        calls.append(
            (
                supplied,
                expected,
            )
        )

        return original_compare_digest(
            supplied,
            expected,
        )

    monkeypatch.setattr(
        authenticator_module,
        "compare_digest",
        recording_compare_digest,
    )

    authenticated = authenticator.authenticate(
        issued.access_credential
    )

    assert authenticated == CustomerIdentity(
        customer_id="customer-001"
    )

    assert len(calls) == 1

    supplied, expected = calls[0]

    assert len(supplied) == 64
    assert len(expected) == 64

    assert issued.access_credential not in supplied
    assert issued.access_credential not in expected


def test_wrong_secret_still_uses_compare_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    parts = issued.access_credential.split(
        "."
    )

    wrong = (
        f"{parts[0]}."
        f"{parts[1]}."
        "wrong-secret"
    )

    calls = 0

    original_compare_digest = (
        authenticator_module.compare_digest
    )

    def recording_compare_digest(
        supplied: str,
        expected: str,
    ) -> bool:
        nonlocal calls

        calls += 1

        return original_compare_digest(
            supplied,
            expected,
        )

    monkeypatch.setattr(
        authenticator_module,
        "compare_digest",
        recording_compare_digest,
    )

    assert authenticator.authenticate(
        wrong
    ) is None

    assert calls == 1


def test_compare_digest_result_is_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    monkeypatch.setattr(
        authenticator_module,
        "compare_digest",
        lambda _supplied, _expected: False,
    )

    assert authenticator.authenticate(
        issued.access_credential
    ) is None


def test_missing_authoritative_customer_identity_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        authenticator,
        credentials,
        identities,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    monkeypatch.setattr(
        identities,
        "get",
        lambda *, customer_id: None,
    )

    assert authenticator.authenticate(
        issued.access_credential
    ) is None


def test_authenticator_does_not_mutate_credential_state(
    tmp_path: Path,
) -> None:
    (
        authenticator,
        credentials,
        _,
    ) = build_auth_stack(
        tmp_path,
        "customer-001",
    )

    issued = credentials.issue(
        customer_id="customer-001"
    )

    path = (
        tmp_path
        / "customer_access_credentials.json"
    )

    before = path.read_bytes()

    assert authenticator.authenticate(
        issued.access_credential
    ) is not None

    assert path.read_bytes() == before

    parts = issued.access_credential.split(
        "."
    )

    wrong = (
        f"{parts[0]}."
        f"{parts[1]}."
        "wrong-secret"
    )

    assert authenticator.authenticate(
        wrong
    ) is None

    assert path.read_bytes() == before
