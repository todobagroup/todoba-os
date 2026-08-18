from pathlib import Path

import pytest

from scripts.provision_trusted_agent_account_binding import (
    provision_trusted_agent_account_binding,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def test_missing_store_is_explicitly_provisioned(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    result = provision_trusted_agent_account_binding(
        storage_path=storage_path,
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert result == "account-a"
    assert storage_path.exists()

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.is_ready()

    assert restored.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )


def test_identical_provisioning_is_idempotent(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    first = provision_trusted_agent_account_binding(
        storage_path=storage_path,
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    second = provision_trusted_agent_account_binding(
        storage_path=storage_path,
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert first == "account-a"
    assert second == "account-a"

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.size() == 1


def test_conflicting_rebinding_is_rejected(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    provision_trusted_agent_account_binding(
        storage_path=storage_path,
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    with pytest.raises(
        ValueError,
        match="already bound",
    ):
        provision_trusted_agent_account_binding(
            storage_path=storage_path,
            agent_id="trusted-agent-001",
            account_fingerprint="account-b",
        )

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert not restored.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-b",
    )


def test_agents_have_independent_bindings(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    provision_trusted_agent_account_binding(
        storage_path=storage_path,
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    provision_trusted_agent_account_binding(
        storage_path=storage_path,
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.size() == 2

    assert restored.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert restored.owns_account(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )