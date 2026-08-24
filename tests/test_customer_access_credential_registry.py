"""
TODOBA Customer Access Credential Registry Tests

Security proof:
- issued credentials are durable
- plaintext bearer secrets are never persisted
- bearer secrets are redacted from repr
- one customer may own multiple credentials
- unknown customer issuance fails with zero mutation
- credential ID collisions are retried
- verifier collisions are retried
- generation exhaustion fails closed
- failed durable issuance cannot advance RAM
- revocation is durable and idempotent
- unknown revocation fails closed
- failed durable revocation preserves active truth
- duplicate credential IDs fail closed on restore
- duplicate verifiers fail closed on restore
- unknown customer references fail closed on restore
- malformed persistence fails closed
- revoked state survives restart

All persistence is isolated beneath pytest tmp_path.
"""

import json
from pathlib import Path

import pytest

import backend.commercial.customer_access_credential_registry as credential_module
from backend.commercial.customer_access_credential_registry import (
    CUSTOMER_ACCESS_CREDENTIAL_PREFIX,
    CustomerAccessCredentialRegistry,
    CustomerAccessCredentialStatus,
    derive_customer_access_credential_verifier,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


def identity_storage_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_identities.json"
    )


def credential_storage_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_access_credentials.json"
    )


def build_identity_registry(
    tmp_path: Path,
    *customer_ids: str,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        identity_storage_path(
            tmp_path
        )
    )

    registry.initialize_empty()

    registry.register_many(
        CustomerIdentity(
            customer_id=customer_id
        )
        for customer_id in customer_ids
    )

    return registry


def build_credential_registry(
    tmp_path: Path,
    *customer_ids: str,
) -> tuple[
    CustomerAccessCredentialRegistry,
    CustomerIdentityRegistry,
]:
    identities = build_identity_registry(
        tmp_path,
        *customer_ids,
    )

    registry = CustomerAccessCredentialRegistry(
        credential_storage_path(
            tmp_path
        ),
        customer_identity_registry=identities,
    )

    registry.initialize_empty()

    return (
        registry,
        identities,
    )


def verifier_for(
    value: str,
) -> str:
    return (
        derive_customer_access_credential_verifier(
            value
        )
    )


def test_issue_is_durable_and_plaintext_is_not_persisted(
    tmp_path: Path,
) -> None:
    (
        registry,
        identities,
    ) = build_credential_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    assert issued.access_credential.startswith(
        f"{CUSTOMER_ACCESS_CREDENTIAL_PREFIX}."
    )

    record = registry.get(
        credential_id=issued.credential_id
    )

    assert record is not None

    assert (
        record.status
        is CustomerAccessCredentialStatus.ACTIVE
    )

    assert (
        record.customer_id
        == "customer-001"
    )

    assert (
        record.verifier_sha256
        == verifier_for(
            issued.access_credential
        )
    )

    persisted = path.read_text(
        encoding="utf-8"
    )

    secret_component = (
        issued.access_credential
        .rsplit(
            ".",
            1,
        )[-1]
    )

    assert (
        issued.access_credential
        not in persisted
    )

    assert (
        secret_component
        not in persisted
    )

    payload = json.loads(
        persisted
    )

    assert set(
        payload["credentials"][0]
    ) == {
        "credential_id",
        "customer_id",
        "verifier_sha256",
        "status",
    }

    restarted = CustomerAccessCredentialRegistry(
        path,
        customer_identity_registry=identities,
    )

    assert (
        restarted.get(
            credential_id=issued.credential_id
        )
        == record
    )


def test_one_customer_can_own_multiple_credentials(
    tmp_path: Path,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    first = registry.issue(
        customer_id="customer-001"
    )

    second = registry.issue(
        customer_id="customer-001"
    )

    assert (
        first.credential_id
        != second.credential_id
    )

    assert (
        first.access_credential
        != second.access_credential
    )

    records = registry.all_for_customer(
        customer_id="customer-001"
    )

    assert len(records) == 2

    assert all(
        record.status
        is CustomerAccessCredentialStatus.ACTIVE
        for record in records
    )


def test_unknown_customer_issuance_has_zero_mutation(
    tmp_path: Path,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-known",
        )
    )

    path = credential_storage_path(
        tmp_path
    )

    before = path.read_bytes()

    with pytest.raises(
        ValueError,
        match="Unknown customer identity",
    ):
        registry.issue(
            customer_id="customer-unknown"
        )

    assert registry.size() == 0
    assert path.read_bytes() == before


def test_issued_credential_repr_redacts_bearer_secret(
    tmp_path: Path,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    representation = repr(
        issued
    )

    secret_component = (
        issued.access_credential
        .rsplit(
            ".",
            1,
        )[-1]
    )

    assert (
        issued.access_credential
        not in representation
    )

    assert (
        secret_component
        not in representation
    )

    assert "access_credential" not in representation


def test_credential_id_collision_is_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    existing = registry.issue(
        customer_id="customer-001"
    )

    replacement_id = "f" * 32

    if replacement_id == existing.credential_id:
        replacement_id = "e" * 32

    credential_ids = iter(
        (
            existing.credential_id,
            replacement_id,
        )
    )

    secrets_generated = iter(
        (
            "collision-secret",
            "replacement-secret",
        )
    )

    monkeypatch.setattr(
        credential_module.secrets,
        "token_hex",
        lambda _size: next(
            credential_ids
        ),
    )

    monkeypatch.setattr(
        credential_module.secrets,
        "token_urlsafe",
        lambda _size: next(
            secrets_generated
        ),
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    assert (
        issued.credential_id
        == replacement_id
    )

    assert registry.size() == 2


def test_verifier_collision_is_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    existing = registry.issue(
        customer_id="customer-001"
    )

    existing_record = registry.get(
        credential_id=existing.credential_id
    )

    assert existing_record is not None

    candidates = [
        "a" * 32,
        "b" * 32,
        "c" * 32,
    ]

    fresh_ids = [
        value
        for value in candidates
        if value != existing.credential_id
    ]

    credential_ids = iter(
        fresh_ids[:2]
    )

    generated_secrets = iter(
        (
            "first-generated-secret",
            "second-generated-secret",
        )
    )

    original_derive = (
        credential_module
        .derive_customer_access_credential_verifier
    )

    calls = 0

    def derive_with_first_collision(
        access_credential: str,
    ) -> str:
        nonlocal calls

        calls += 1

        if calls == 1:
            return (
                existing_record.verifier_sha256
            )

        return original_derive(
            access_credential
        )

    monkeypatch.setattr(
        credential_module.secrets,
        "token_hex",
        lambda _size: next(
            credential_ids
        ),
    )

    monkeypatch.setattr(
        credential_module.secrets,
        "token_urlsafe",
        lambda _size: next(
            generated_secrets
        ),
    )

    monkeypatch.setattr(
        credential_module,
        "derive_customer_access_credential_verifier",
        derive_with_first_collision,
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    assert (
        issued.credential_id
        == fresh_ids[1]
    )

    assert registry.size() == 2

    issued_record = registry.get(
        credential_id=issued.credential_id
    )

    assert issued_record is not None

    assert (
        issued_record.verifier_sha256
        != existing_record.verifier_sha256
    )


def test_generation_exhaustion_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    existing = registry.issue(
        customer_id="customer-001"
    )

    path = credential_storage_path(
        tmp_path
    )

    before = path.read_bytes()

    monkeypatch.setattr(
        credential_module.secrets,
        "token_hex",
        lambda _size: (
            existing.credential_id
        ),
    )

    monkeypatch.setattr(
        credential_module.secrets,
        "token_urlsafe",
        lambda _size: (
            "forced-collision-secret"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to generate unique",
    ):
        registry.issue(
            customer_id="customer-001"
        )

    assert registry.size() == 1
    assert path.read_bytes() == before


def test_failed_issuance_durable_write_does_not_advance_ram(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    path = credential_storage_path(
        tmp_path
    )

    before = path.read_bytes()

    def fail_write(
        records,
    ) -> None:
        raise OSError(
            "simulated credential durable write failure"
        )

    monkeypatch.setattr(
        registry,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated credential durable write failure",
    ):
        registry.issue(
            customer_id="customer-001"
        )

    assert registry.size() == 0
    assert registry.all() == ()
    assert path.read_bytes() == before


def test_revocation_is_durable_and_idempotent(
    tmp_path: Path,
) -> None:
    (
        registry,
        identities,
    ) = build_credential_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    first = registry.revoke(
        credential_id=issued.credential_id
    )

    second = registry.revoke(
        credential_id=issued.credential_id
    )

    assert first == second

    assert (
        first.status
        is CustomerAccessCredentialStatus.REVOKED
    )

    restarted = CustomerAccessCredentialRegistry(
        path,
        customer_identity_registry=identities,
    )

    restored = restarted.get(
        credential_id=issued.credential_id
    )

    assert restored is not None

    assert (
        restored.status
        is CustomerAccessCredentialStatus.REVOKED
    )


def test_unknown_revocation_fails_closed_without_write(
    tmp_path: Path,
) -> None:
    registry, _ = (
        build_credential_registry(
            tmp_path,
            "customer-001",
        )
    )

    path = credential_storage_path(
        tmp_path
    )

    before = path.read_bytes()

    with pytest.raises(
        ValueError,
        match="Unknown customer access credential",
    ):
        registry.revoke(
            credential_id="f" * 32
        )

    assert registry.size() == 0
    assert path.read_bytes() == before


def test_failed_revocation_write_preserves_active_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        registry,
        identities,
    ) = build_credential_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    before = path.read_bytes()

    def fail_write(
        records,
    ) -> None:
        raise OSError(
            "simulated revocation durable write failure"
        )

    monkeypatch.setattr(
        registry,
        "_write_records",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated revocation durable write failure",
    ):
        registry.revoke(
            credential_id=issued.credential_id
        )

    current = registry.get(
        credential_id=issued.credential_id
    )

    assert current is not None

    assert (
        current.status
        is CustomerAccessCredentialStatus.ACTIVE
    )

    assert path.read_bytes() == before

    restarted = CustomerAccessCredentialRegistry(
        path,
        customer_identity_registry=identities,
    )

    restored = restarted.get(
        credential_id=issued.credential_id
    )

    assert restored is not None

    assert (
        restored.status
        is CustomerAccessCredentialStatus.ACTIVE
    )


def test_revoked_state_survives_multiple_restarts(
    tmp_path: Path,
) -> None:
    (
        registry,
        identities,
    ) = build_credential_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    issued = registry.issue(
        customer_id="customer-001"
    )

    registry.revoke(
        credential_id=issued.credential_id
    )

    first_restart = CustomerAccessCredentialRegistry(
        path,
        customer_identity_registry=identities,
    )

    second_restart = CustomerAccessCredentialRegistry(
        path,
        customer_identity_registry=identities,
    )

    for restarted in (
        first_restart,
        second_restart,
    ):
        record = restarted.get(
            credential_id=issued.credential_id
        )

        assert record is not None

        assert (
            record.status
            is CustomerAccessCredentialStatus.REVOKED
        )


def test_duplicate_credential_id_restore_fails_closed(
    tmp_path: Path,
) -> None:
    identities = build_identity_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    credential_id = "a" * 32

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "credentials": [
                    {
                        "credential_id": credential_id,
                        "customer_id": "customer-001",
                        "verifier_sha256": verifier_for(
                            "credential-one"
                        ),
                        "status": "ACTIVE",
                    },
                    {
                        "credential_id": credential_id,
                        "customer_id": "customer-001",
                        "verifier_sha256": verifier_for(
                            "credential-two"
                        ),
                        "status": "ACTIVE",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer access credential_id",
    ):
        CustomerAccessCredentialRegistry(
            path,
            customer_identity_registry=identities,
        )


def test_duplicate_verifier_restore_fails_closed(
    tmp_path: Path,
) -> None:
    identities = build_identity_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    verifier = verifier_for(
        "same-verifier-source"
    )

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "credentials": [
                    {
                        "credential_id": "a" * 32,
                        "customer_id": "customer-001",
                        "verifier_sha256": verifier,
                        "status": "ACTIVE",
                    },
                    {
                        "credential_id": "b" * 32,
                        "customer_id": "customer-001",
                        "verifier_sha256": verifier,
                        "status": "REVOKED",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer access credential verifier",
    ):
        CustomerAccessCredentialRegistry(
            path,
            customer_identity_registry=identities,
        )


def test_unknown_customer_reference_restore_fails_closed(
    tmp_path: Path,
) -> None:
    identities = build_identity_registry(
        tmp_path,
        "customer-known",
    )

    path = credential_storage_path(
        tmp_path
    )

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "credentials": [
                    {
                        "credential_id": "a" * 32,
                        "customer_id": "customer-unknown",
                        "verifier_sha256": verifier_for(
                            "unknown-customer-credential"
                        ),
                        "status": "ACTIVE",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="references unknown customer",
    ):
        CustomerAccessCredentialRegistry(
            path,
            customer_identity_registry=identities,
        )


@pytest.mark.parametrize(
    "payload",
    (
        [],
        {
            "version": 999,
            "credentials": [],
        },
        {
            "version": 1,
            "credentials": "not-a-list",
        },
        {
            "version": 1,
            "credentials": [
                "not-an-object",
            ],
        },
        {
            "version": 1,
            "credentials": [
                {
                    "credential_id": "a" * 32,
                    "customer_id": "customer-001",
                    "verifier_sha256": verifier_for(
                        "credential"
                    ),
                    "status": "ACTIVE",
                    "unexpected": "field",
                },
            ],
        },
        {
            "version": 1,
            "credentials": [
                {
                    "credential_id": "invalid-id",
                    "customer_id": "customer-001",
                    "verifier_sha256": verifier_for(
                        "credential"
                    ),
                    "status": "ACTIVE",
                },
            ],
        },
        {
            "version": 1,
            "credentials": [
                {
                    "credential_id": "a" * 32,
                    "customer_id": "customer-001",
                    "verifier_sha256": "invalid-verifier",
                    "status": "ACTIVE",
                },
            ],
        },
        {
            "version": 1,
            "credentials": [
                {
                    "credential_id": "a" * 32,
                    "customer_id": "customer-001",
                    "verifier_sha256": verifier_for(
                        "credential"
                    ),
                    "status": "INVALID",
                },
            ],
        },
    ),
)
def test_malformed_persistence_fails_closed(
    tmp_path: Path,
    payload,
) -> None:
    identities = build_identity_registry(
        tmp_path,
        "customer-001",
    )

    path = credential_storage_path(
        tmp_path
    )

    path.write_text(
        json.dumps(
            payload
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
    ):
        CustomerAccessCredentialRegistry(
            path,
            customer_identity_registry=identities,
        )
