from dataclasses import replace
from pathlib import Path

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.persistent_security_sequence_allocator import (
    PersistentSecuritySequenceAllocator,
)
from backend.trading.execution.persistent_security_sequence_binding_store import (
    PersistentSecuritySequenceBindingStore,
)
from backend.trading.execution.security_sequence_assignment_service import (
    SecuritySequenceAssignmentService,
)


MISSION_ID = "execution-security-integration-001"
AGENT_ID = "trusted-agent-001"


def build_source_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=MISSION_ID,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Security Integration",
        created_at="2026-08-18T12:00:00Z",
        expires_at="2026-08-18T13:00:00Z",
        sequence=168001,
    )


def build_stack(
    tmp_path: Path,
) -> tuple[
    ExecutionMissionService,
    ExecutionMissionRepository,
    ExecutionMissionRegistry,
    ExecutionMissionStore,
    PersistentSecuritySequenceAllocator,
]:
    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    registry = ExecutionMissionRegistry()

    store = ExecutionMissionStore()

    delivery_bridge = ExecutionMissionDeliveryBridge(
        store
    )

    allocator = PersistentSecuritySequenceAllocator(
        tmp_path
        / "execution_security_sequence.json"
    )

    binding_store = (
        PersistentSecuritySequenceBindingStore(
            tmp_path
            / "execution_security_sequence_bindings.json"
        )
    )

    assignment_service = (
        SecuritySequenceAssignmentService(
            allocator=allocator,
            binding_store=binding_store,
        )
    )

    service = ExecutionMissionService(
        repository,
        persistence,
        delivery_bridge,
        registry,
        security_sequence_assignment_service=(
            assignment_service
        ),
    )

    return (
        service,
        repository,
        registry,
        store,
        allocator,
    )


def test_cloud_assigns_security_sequence_before_persistence(
    tmp_path: Path,
) -> None:
    (
        service,
        repository,
        registry,
        store,
        allocator,
    ) = build_stack(
        tmp_path
    )

    source_mission = build_source_mission()

    assert source_mission.security_sequence == 0

    result = service.create_mission(
        source_mission
    )

    assert source_mission.security_sequence == 0
    assert result.security_sequence == 1
    assert allocator.current_sequence == 1

    stored = repository.get(
        MISSION_ID
    )

    assert stored is not None
    assert stored.security_sequence == 1

    record = registry.get(
        MISSION_ID
    )

    assert record is not None
    assert record.mission.security_sequence == 1

    queued = store.pop_for_agent(
        AGENT_ID
    )

    assert queued is not None
    assert queued.security_sequence == 1


def test_identical_source_retry_reuses_security_sequence(
    tmp_path: Path,
) -> None:
    (
        service,
        repository,
        registry,
        store,
        allocator,
    ) = build_stack(
        tmp_path
    )

    source_mission = build_source_mission()

    first = service.create_mission(
        source_mission
    )

    existing_record = registry.get(
        MISSION_ID
    )

    second = service.create_mission(
        source_mission
    )

    assert first.security_sequence == 1
    assert second.security_sequence == 1

    assert allocator.current_sequence == 1

    assert repository.size() == 1

    assert registry.get(
        MISSION_ID
    ) is existing_record

    assert store.size() == 1


def test_conflicting_source_retry_is_rejected_without_allocating(
    tmp_path: Path,
) -> None:
    (
        service,
        _,
        _,
        _,
        allocator,
    ) = build_stack(
        tmp_path
    )

    source_mission = build_source_mission()

    service.create_mission(
        source_mission
    )

    conflicting = replace(
        source_mission,
        volume=0.02,
    )

    with pytest.raises(
        ValueError,
        match=(
            "mission_id already bound to "
            "different payload"
        ),
    ):
        service.create_mission(
            conflicting
        )

    assert allocator.current_sequence == 1


def test_producer_cannot_supply_security_sequence(
    tmp_path: Path,
) -> None:
    (
        service,
        repository,
        registry,
        store,
        allocator,
    ) = build_stack(
        tmp_path
    )

    forged = replace(
        build_source_mission(),
        security_sequence=999,
    )

    with pytest.raises(
        ValueError,
        match=(
            "source mission security_sequence "
            "must be zero"
        ),
    ):
        service.create_mission(
            forged
        )

    assert allocator.current_sequence == 0
    assert repository.size() == 0
    assert registry.size() == 0
    assert store.size() == 0


def test_distinct_missions_receive_monotonic_security_sequences(
    tmp_path: Path,
) -> None:
    (
        service,
        repository,
        _,
        _,
        allocator,
    ) = build_stack(
        tmp_path
    )

    first_source = build_source_mission()

    second_source = replace(
        first_source,
        mission_id=(
            "execution-security-integration-002"
        ),
        sequence=168002,
    )

    first = service.create_mission(
        first_source
    )

    second = service.create_mission(
        second_source
    )

    assert first.security_sequence == 1
    assert second.security_sequence == 2

    assert allocator.current_sequence == 2

    assert repository.get(
        first.mission_id
    ).security_sequence == 1

    assert repository.get(
        second.mission_id
    ).security_sequence == 2