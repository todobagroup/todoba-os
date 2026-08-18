import json

import pytest

from backend.trading.execution.persistent_security_sequence_binding_store import (
    PersistentSecuritySequenceBindingStore,
)


def test_binding_store_creates_new_binding(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "security_sequence_bindings.json"
    )

    store = PersistentSecuritySequenceBindingStore(
        storage_path
    )

    result = store.bind(
        mission_id="mission-001",
        payload_fingerprint="fingerprint-a",
        security_sequence=1,
    )

    assert result == 1

    assert store.get(
        "mission-001"
    ) == (
        "fingerprint-a",
        1,
    )


def test_binding_store_reuses_identical_binding(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "security_sequence_bindings.json"
    )

    store = PersistentSecuritySequenceBindingStore(
        storage_path
    )

    first = store.bind(
        mission_id="mission-001",
        payload_fingerprint="fingerprint-a",
        security_sequence=7,
    )

    second = store.bind(
        mission_id="mission-001",
        payload_fingerprint="fingerprint-a",
        security_sequence=99,
    )

    assert first == 7
    assert second == 7

    assert store.get(
        "mission-001"
    ) == (
        "fingerprint-a",
        7,
    )


def test_binding_store_rejects_payload_conflict(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "security_sequence_bindings.json"
    )

    store = PersistentSecuritySequenceBindingStore(
        storage_path
    )

    store.bind(
        mission_id="mission-001",
        payload_fingerprint="fingerprint-a",
        security_sequence=3,
    )

    with pytest.raises(
        ValueError,
        match=(
            "mission_id already bound to "
            "different payload"
        ),
    ):
        store.bind(
            mission_id="mission-001",
            payload_fingerprint="fingerprint-b",
            security_sequence=4,
        )

    assert store.get(
        "mission-001"
    ) == (
        "fingerprint-a",
        3,
    )


def test_binding_store_restores_after_restart(
    tmp_path,
):
    storage_path = (
        tmp_path
        / "security_sequence_bindings.json"
    )

    first_store = (
        PersistentSecuritySequenceBindingStore(
            storage_path
        )
    )

    first_store.bind(
        mission_id="mission-001",
        payload_fingerprint="fingerprint-a",
        security_sequence=12,
    )

    restored_store = (
        PersistentSecuritySequenceBindingStore(
            storage_path
        )
    )

    assert restored_store.get(
        "mission-001"
    ) == (
        "fingerprint-a",
        12,
    )

    assert restored_store.bind(
        mission_id="mission-001",
        payload_fingerprint="fingerprint-a",
        security_sequence=13,
    ) == 12


def test_binding_store_persistence_failure_does_not_commit_memory(
    tmp_path,
    monkeypatch,
):
    storage_path = (
        tmp_path
        / "security_sequence_bindings.json"
    )

    store = PersistentSecuritySequenceBindingStore(
        storage_path
    )

    def fail_replace(
        self,
        target,
    ):
        raise OSError(
            "simulated persistence failure"
        )

    monkeypatch.setattr(
        type(storage_path),
        "replace",
        fail_replace,
    )

    with pytest.raises(
        OSError,
        match="simulated persistence failure",
    ):
        store.bind(
            mission_id="mission-001",
            payload_fingerprint="fingerprint-a",
            security_sequence=1,
        )

    assert store.get(
        "mission-001"
    ) is None

    if storage_path.exists():
        payload = json.loads(
            storage_path.read_text(
                encoding="utf-8",
            )
        )

        assert (
            "mission-001"
            not in payload.get(
                "bindings",
                {},
            )
        )