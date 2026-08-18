import json

import pytest

from backend.trading.execution.persistent_replay_floor_store import (
    PersistentReplayFloorStore,
)


def test_missing_storage_is_fail_closed(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    store = PersistentReplayFloorStore(
        storage_path
    )

    assert store.is_ready() is False

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.commit_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
            security_sequence=1,
        )


def test_explicit_empty_initialization_is_durable(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    store = PersistentReplayFloorStore(
        storage_path
    )

    store.initialize_empty()

    assert store.is_ready() is True
    assert store.size() == 0

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 0
    )

    persisted = json.loads(
        storage_path.read_text(
            encoding="utf-8",
        )
    )

    assert persisted == {
        "version": 1,
        "floors": [],
    }

    restored = PersistentReplayFloorStore(
        storage_path
    )

    assert restored.is_ready() is True
    assert restored.size() == 0


def test_commit_is_monotonic_and_idempotent(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    store = PersistentReplayFloorStore(
        storage_path
    )

    store.initialize_empty()

    committed = store.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        security_sequence=41,
    )

    assert committed == 41

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 41
    )

    identical_retry = store.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        security_sequence=41,
    )

    assert identical_retry == 41

    with pytest.raises(
        ValueError,
        match="cannot move replay floor backwards",
    ):
        store.commit_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
            security_sequence=40,
        )

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 41
    )

    committed = store.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        security_sequence=42,
    )

    assert committed == 42

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 42
    )


def test_restart_restores_committed_floor(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    original = PersistentReplayFloorStore(
        storage_path
    )

    original.initialize_empty()

    original.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        security_sequence=168,
    )

    restored = PersistentReplayFloorStore(
        storage_path
    )

    assert restored.is_ready() is True

    assert (
        restored.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 168
    )


def test_agent_account_identities_are_isolated(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    store = PersistentReplayFloorStore(
        storage_path
    )

    store.initialize_empty()

    store.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        security_sequence=50,
    )

    store.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-b",
        security_sequence=7,
    )

    store.commit_floor(
        agent_id="trusted-agent-002",
        account_fingerprint="account-a",
        security_sequence=3,
    )

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 50
    )

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-b",
        )
        == 7
    )

    assert (
        store.get_floor(
            agent_id="trusted-agent-002",
            account_fingerprint="account-a",
        )
        == 3
    )

    assert store.size() == 3


def test_persistence_failure_does_not_advance_ram_floor(
    tmp_path,
    monkeypatch,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    store = PersistentReplayFloorStore(
        storage_path
    )

    store.initialize_empty()

    store.commit_floor(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        security_sequence=10,
    )

    import backend.trading.execution.persistent_replay_floor_store as replay_floor_module

    original_replace = (
        replay_floor_module.os.replace
    )

    def fail_replace(
        source,
        destination,
    ):
        raise OSError(
            "simulated durable replace failure"
        )

    monkeypatch.setattr(
        replay_floor_module.os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        OSError,
        match="simulated durable replace failure",
    ):
        store.commit_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
            security_sequence=11,
        )

    assert (
        store.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 10
    )

    monkeypatch.setattr(
        replay_floor_module.os,
        "replace",
        original_replace,
    )

    restored = PersistentReplayFloorStore(
        storage_path
    )

    assert (
        restored.get_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
        == 10
    )


@pytest.mark.parametrize(
    "security_sequence",
    [
        0,
        -1,
        True,
        1.5,
        "1",
    ],
)
def test_invalid_security_sequence_is_rejected(
    tmp_path,
    security_sequence,
):
    storage_path = (
        tmp_path
        / "replay_floor.json"
    )

    store = PersistentReplayFloorStore(
        storage_path
    )

    store.initialize_empty()

    expected_error = (
        TypeError
        if isinstance(
            security_sequence,
            (bool, float, str),
        )
        else ValueError
    )

    with pytest.raises(
        expected_error
    ):
        store.commit_floor(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
            security_sequence=security_sequence,
        )