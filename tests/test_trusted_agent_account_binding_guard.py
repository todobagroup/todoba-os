import pytest

from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def test_missing_store_is_fail_closed(
    tmp_path,
):
    store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )

    guard = TrustedAgentAccountBindingGuard(
        store
    )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        guard.require_binding(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )


def test_missing_agent_binding_is_fail_closed(
    tmp_path,
):
    store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )

    store.initialize_empty()

    guard = TrustedAgentAccountBindingGuard(
        store
    )

    with pytest.raises(
        RuntimeError,
        match="no authoritative",
    ):
        guard.require_binding(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )


def test_matching_binding_is_accepted(
    tmp_path,
):
    store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    guard = TrustedAgentAccountBindingGuard(
        store
    )

    result = guard.require_binding(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert result == "account-a"


def test_conflicting_deployment_binding_is_rejected(
    tmp_path,
):
    store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    guard = TrustedAgentAccountBindingGuard(
        store
    )

    with pytest.raises(
        RuntimeError,
        match="does not match deployment",
    ):
        guard.require_binding(
            agent_id="trusted-agent-001",
            account_fingerprint="account-b",
        )


def test_expected_account_is_normalized(
    tmp_path,
):
    store = TrustedAgentAccountBindingStore(
        tmp_path / "bindings.json"
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    guard = TrustedAgentAccountBindingGuard(
        store
    )

    result = guard.require_binding(
        agent_id="trusted-agent-001",
        account_fingerprint="  account-a  ",
    )

    assert result == "account-a"