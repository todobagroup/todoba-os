from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.trading.execution.persistent_security_sequence_allocator import (
    PersistentSecuritySequenceAllocator,
)
from backend.trading.execution.persistent_security_sequence_binding_store import (
    PersistentSecuritySequenceBindingStore,
)
from backend.trading.execution.security_sequence_assignment_service import (
    SecuritySequenceAssignmentService,
)
from backend.trading.execution.security_sequence_payload_fingerprint import (
    SecuritySequencePayloadFingerprint,
)


def build_service(
    tmp_path,
):
    allocator = PersistentSecuritySequenceAllocator(
        tmp_path
        / "security_sequence.json"
    )

    binding_store = (
        PersistentSecuritySequenceBindingStore(
            tmp_path
            / "security_sequence_bindings.json"
        )
    )

    service = SecuritySequenceAssignmentService(
        allocator=allocator,
        binding_store=binding_store,
    )

    return (
        service,
        allocator,
        binding_store,
    )


def test_assignment_allocates_for_new_mission(
    tmp_path,
):
    (
        service,
        allocator,
        binding_store,
    ) = build_service(
        tmp_path
    )

    payload = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    assigned = service.assign(
        mission_id="mission-001",
        source_payload=payload,
    )

    assert assigned == 1
    assert allocator.current_sequence == 1

    fingerprint = (
        SecuritySequencePayloadFingerprint.build(
            payload
        )
    )

    assert binding_store.get(
        "mission-001"
    ) == (
        fingerprint,
        1,
    )


def test_assignment_reuses_sequence_for_identical_retry(
    tmp_path,
):
    (
        service,
        allocator,
        _,
    ) = build_service(
        tmp_path
    )

    payload = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    first = service.assign(
        mission_id="mission-001",
        source_payload=payload,
    )

    second = service.assign(
        mission_id="mission-001",
        source_payload=payload,
    )

    assert first == 1
    assert second == 1

    assert allocator.current_sequence == 1


def test_assignment_rejects_conflicting_retry_without_allocating(
    tmp_path,
):
    (
        service,
        allocator,
        _,
    ) = build_service(
        tmp_path
    )

    service.assign(
        mission_id="mission-001",
        source_payload={
            "mission_id": "mission-001",
            "symbol": "XAUUSD",
            "sequence": 168001,
        },
    )

    with pytest.raises(
        ValueError,
        match=(
            "mission_id already bound to "
            "different payload"
        ),
    ):
        service.assign(
            mission_id="mission-001",
            source_payload={
                "mission_id": "mission-001",
                "symbol": "XAUUSD",
                "sequence": 168002,
            },
        )

    assert allocator.current_sequence == 1


def test_assignment_allocates_next_sequence_for_distinct_mission(
    tmp_path,
):
    (
        service,
        allocator,
        _,
    ) = build_service(
        tmp_path
    )

    first = service.assign(
        mission_id="mission-001",
        source_payload={
            "mission_id": "mission-001",
            "sequence": 168001,
        },
    )

    second = service.assign(
        mission_id="mission-002",
        source_payload={
            "mission_id": "mission-002",
            "sequence": 168002,
        },
    )

    assert first == 1
    assert second == 2

    assert allocator.current_sequence == 2


def test_assignment_restores_retry_binding_after_restart(
    tmp_path,
):
    (
        first_service,
        first_allocator,
        _,
    ) = build_service(
        tmp_path
    )

    payload = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    assert first_service.assign(
        mission_id="mission-001",
        source_payload=payload,
    ) == 1

    assert first_allocator.current_sequence == 1

    (
        restored_service,
        restored_allocator,
        _,
    ) = build_service(
        tmp_path
    )

    assert restored_service.assign(
        mission_id="mission-001",
        source_payload=payload,
    ) == 1

    assert restored_allocator.current_sequence == 1

    assert restored_service.assign(
        mission_id="mission-002",
        source_payload={
            "mission_id": "mission-002",
            "sequence": 168002,
        },
    ) == 2


def test_concurrent_identical_retry_allocates_only_once(
    tmp_path,
):
    (
        service,
        allocator,
        _,
    ) = build_service(
        tmp_path
    )

    payload = {
        "mission_id": "mission-001",
        "symbol": "XAUUSD",
        "sequence": 168001,
    }

    def assign():
        return service.assign(
            mission_id="mission-001",
            source_payload=payload,
        )

    with ThreadPoolExecutor(
        max_workers=8,
    ) as executor:
        results = list(
            executor.map(
                lambda _: assign(),
                range(20),
            )
        )

    assert results == [1] * 20
    assert allocator.current_sequence == 1