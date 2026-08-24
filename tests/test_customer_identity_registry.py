"""
TODOBA Customer Identity Registry Tests

Proof:
- single customer registration is durable
- identical retry is idempotent
- bulk legacy adoption is durable
- duplicate bulk identities converge
- invalid bulk request causes zero partial write
- failed durable write cannot advance RAM
- malformed persistence fails closed
- duplicate durable customer identity fails closed
- restart restores deterministic customer truth

All persistence is isolated beneath pytest tmp_path.
"""

import json
from pathlib import Path

import pytest

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


def storage_path(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "customer_identities.json"
    )


def initialized_registry(
    tmp_path: Path,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        storage_path(
            tmp_path
        )
    )

    registry.initialize_empty()

    return registry


def test_single_registration_is_durable(
    tmp_path: Path,
) -> None:
    path = storage_path(
        tmp_path
    )

    registry = (
        initialized_registry(
            tmp_path
        )
    )

    identity = CustomerIdentity(
        customer_id="customer-001"
    )

    result = registry.register(
        identity
    )

    assert result == identity
    assert registry.size() == 1

    assert registry.contains(
        customer_id="customer-001"
    )

    restored = CustomerIdentityRegistry(
        path
    )

    assert restored.is_ready()
    assert restored.size() == 1

    assert (
        restored.get(
            customer_id="customer-001"
        )
        == identity
    )


def test_identical_registration_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    registry = (
        initialized_registry(
            tmp_path
        )
    )

    first = registry.register(
        CustomerIdentity(
            customer_id="customer-001"
        )
    )

    retry = registry.register(
        CustomerIdentity(
            customer_id="customer-001"
        )
    )

    assert first == retry
    assert registry.size() == 1

    assert registry.all() == (
        CustomerIdentity(
            customer_id="customer-001"
        ),
    )


def test_bulk_legacy_adoption_is_durable(
    tmp_path: Path,
) -> None:
    path = storage_path(
        tmp_path
    )

    registry = (
        initialized_registry(
            tmp_path
        )
    )

    adopted = registry.register_many(
        (
            CustomerIdentity(
                customer_id="legacy-customer-001"
            ),
            CustomerIdentity(
                customer_id="legacy-customer-002"
            ),
            CustomerIdentity(
                customer_id="legacy-customer-003"
            ),
        )
    )

    assert adopted == (
        CustomerIdentity(
            customer_id="legacy-customer-001"
        ),
        CustomerIdentity(
            customer_id="legacy-customer-002"
        ),
        CustomerIdentity(
            customer_id="legacy-customer-003"
        ),
    )

    assert registry.size() == 3

    restored = CustomerIdentityRegistry(
        path
    )

    assert restored.size() == 3

    assert restored.all() == adopted


def test_duplicate_bulk_identities_converge(
    tmp_path: Path,
) -> None:
    registry = (
        initialized_registry(
            tmp_path
        )
    )

    result = registry.register_many(
        (
            CustomerIdentity(
                customer_id="customer-002"
            ),
            CustomerIdentity(
                customer_id="customer-001"
            ),
            CustomerIdentity(
                customer_id="customer-002"
            ),
            CustomerIdentity(
                customer_id="customer-001"
            ),
        )
    )

    assert result == (
        CustomerIdentity(
            customer_id="customer-001"
        ),
        CustomerIdentity(
            customer_id="customer-002"
        ),
    )

    assert registry.size() == 2


def test_invalid_bulk_request_causes_zero_partial_write(
    tmp_path: Path,
) -> None:
    path = storage_path(
        tmp_path
    )

    registry = (
        initialized_registry(
            tmp_path
        )
    )

    existing = registry.register(
        CustomerIdentity(
            customer_id="customer-existing"
        )
    )

    before_disk = path.read_bytes()

    with pytest.raises(
        TypeError,
        match="CustomerIdentity",
    ):
        registry.register_many(
            (
                CustomerIdentity(
                    customer_id="customer-candidate"
                ),
                object(),
            )
        )

    assert path.read_bytes() == before_disk

    assert registry.size() == 1

    assert registry.all() == (
        existing,
    )

    assert not registry.contains(
        customer_id="customer-candidate"
    )


def test_failed_durable_write_does_not_advance_ram(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = storage_path(
        tmp_path
    )

    registry = (
        initialized_registry(
            tmp_path
        )
    )

    registry.register(
        CustomerIdentity(
            customer_id="customer-existing"
        )
    )

    before_disk = path.read_bytes()

    def fail_write(
        customers,
    ) -> None:
        raise OSError(
            "simulated durable write failure"
        )

    monkeypatch.setattr(
        registry,
        "_write_customers",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated durable write failure",
    ):
        registry.register_many(
            (
                CustomerIdentity(
                    customer_id="customer-new-001"
                ),
                CustomerIdentity(
                    customer_id="customer-new-002"
                ),
            )
        )

    assert registry.size() == 1

    assert registry.contains(
        customer_id="customer-existing"
    )

    assert not registry.contains(
        customer_id="customer-new-001"
    )

    assert not registry.contains(
        customer_id="customer-new-002"
    )

    assert path.read_bytes() == before_disk


@pytest.mark.parametrize(
    "payload",
    (
        [],
        {
            "version": 999,
            "customers": [],
        },
        {
            "version": 1,
            "customers": "not-a-list",
        },
        {
            "version": 1,
            "customers": [
                {
                    "customer_id": "customer-001",
                    "unexpected": "field",
                }
            ],
        },
    ),
)
def test_malformed_persistence_fails_closed(
    tmp_path: Path,
    payload,
) -> None:
    path = storage_path(
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
        CustomerIdentityRegistry(
            path
        )


def test_duplicate_durable_customer_identity_fails_closed(
    tmp_path: Path,
) -> None:
    path = storage_path(
        tmp_path
    )

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "customers": [
                    {
                        "customer_id": (
                            "customer-001"
                        ),
                    },
                    {
                        "customer_id": (
                            "customer-001"
                        ),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer identity",
    ):
        CustomerIdentityRegistry(
            path
        )


def test_restart_restores_deterministic_customer_truth(
    tmp_path: Path,
) -> None:
    path = storage_path(
        tmp_path
    )

    first = (
        initialized_registry(
            tmp_path
        )
    )

    first.register_many(
        (
            CustomerIdentity(
                customer_id="customer-003"
            ),
            CustomerIdentity(
                customer_id="customer-001"
            ),
            CustomerIdentity(
                customer_id="customer-002"
            ),
        )
    )

    expected = (
        CustomerIdentity(
            customer_id="customer-001"
        ),
        CustomerIdentity(
            customer_id="customer-002"
        ),
        CustomerIdentity(
            customer_id="customer-003"
        ),
    )

    assert first.all() == expected

    restarted = CustomerIdentityRegistry(
        path
    )

    assert restarted.is_ready()
    assert restarted.all() == expected
    assert restarted.size() == 3

    second_restart = (
        CustomerIdentityRegistry(
            path
        )
    )

    assert (
        second_restart.all()
        == expected
    )
