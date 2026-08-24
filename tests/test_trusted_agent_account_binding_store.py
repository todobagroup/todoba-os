from pathlib import Path

import pytest

from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def test_missing_storage_is_fail_closed(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert store.is_ready() is False

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.get_account_fingerprint(
            agent_id="trusted-agent-001",
        )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.bind(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )


def test_explicit_empty_initialization_is_durable(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    assert store.is_ready() is True
    assert store.size() == 0

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.is_ready() is True
    assert restored.size() == 0


def test_first_binding_is_persisted(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    result = store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert result == "account-a"

    assert (
        store.get_account_fingerprint(
            agent_id="trusted-agent-001",
        )
        == "account-a"
    )

    assert store.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )


def test_identical_binding_retry_is_idempotent(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    first = store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    retry = store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert first == "account-a"
    assert retry == "account-a"
    assert store.size() == 1


def test_conflicting_rebinding_is_rejected(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    with pytest.raises(
        ValueError,
        match="already bound",
    ):
        store.bind(
            agent_id="trusted-agent-001",
            account_fingerprint="account-b",
        )

    assert (
        store.get_account_fingerprint(
            agent_id="trusted-agent-001",
        )
        == "account-a"
    )


def test_restart_restores_authoritative_binding(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    original = TrustedAgentAccountBindingStore(
        storage_path
    )

    original.initialize_empty()

    original.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="XMGlobal-MT5 9:336627882",
    )

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.is_ready() is True

    assert (
        restored.get_account_fingerprint(
            agent_id="trusted-agent-001",
        )
        == "XMGlobal-MT5 9:336627882"
    )

    assert restored.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="XMGlobal-MT5 9:336627882",
    )


def test_different_agents_have_independent_bindings(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    store.bind(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    assert store.size() == 2

    assert store.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    assert store.owns_account(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    assert not store.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-b",
    )


def test_persistence_failure_does_not_advance_ram_binding(
    tmp_path,
    monkeypatch,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    import backend.trading.execution.trusted_agent_account_binding_store as binding_module

    def fail_replace(
        source,
        destination,
    ):
        raise OSError(
            "simulated binding persistence failure"
        )

    monkeypatch.setattr(
        binding_module.os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        OSError,
        match="simulated binding persistence failure",
    ):
        store.bind(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )

    assert (
        store.get_account_fingerprint(
            agent_id="trusted-agent-001",
        )
        is None
    )

    assert store.size() == 0


@pytest.mark.parametrize(
    "agent_id,account_fingerprint",
    [
        ("", "account-a"),
        ("   ", "account-a"),
        ("trusted-agent-001", ""),
        ("trusted-agent-001", "   "),
    ],
)
def test_empty_binding_identity_is_rejected(
    tmp_path,
    agent_id,
    account_fingerprint,
):
    storage_path = (
        tmp_path
        / "agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    with pytest.raises(
        ValueError
    ):
        store.bind(
            agent_id=agent_id,
            account_fingerprint=account_fingerprint,
        )

def test_reverse_lookup_returns_authoritative_agent_owner(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    store.bind(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    assert (
        store.get_agent_id_for_account(
            account_fingerprint="account-a"
        )
        == "trusted-agent-001"
    )

    assert (
        store.get_agent_id_for_account(
            account_fingerprint="account-b"
        )
        == "trusted-agent-002"
    )

    assert (
        store.get_agent_id_for_account(
            account_fingerprint="account-missing"
        )
        is None
    )


def test_same_account_cannot_bind_to_second_agent(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    store.initialize_empty()

    store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    with pytest.raises(
        ValueError,
        match="different Trusted Agent",
    ):
        store.bind(
            agent_id="trusted-agent-002",
            account_fingerprint="account-a",
        )

    assert store.size() == 1

    assert (
        store.get_agent_id_for_account(
            account_fingerprint="account-a"
        )
        == "trusted-agent-001"
    )

    assert (
        store.get_account_fingerprint(
            agent_id="trusted-agent-002"
        )
        is None
    )

    restored = TrustedAgentAccountBindingStore(
        storage_path
    )

    assert restored.size() == 1

    assert restored.owns_account(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )


def test_restore_rejects_account_bound_to_multiple_agents(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "trusted_agent_account_bindings.json"
    )

    storage_path.write_text(
        (
            '{\n'
            '  "version": 1,\n'
            '  "bindings": [\n'
            '    {\n'
            '      "agent_id": "trusted-agent-001",\n'
            '      "account_fingerprint": "account-a"\n'
            '    },\n'
            '    {\n'
            '      "agent_id": "trusted-agent-002",\n'
            '      "account_fingerprint": "account-a"\n'
            '    }\n'
            '  ]\n'
            '}\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="multiple Trusted Agents",
    ):
        TrustedAgentAccountBindingStore(
            storage_path
        )
