from dataclasses import replace
from pathlib import Path

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
)
from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_service import (
    ControlMissionService,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
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


MISSION_ID = "control-security-integration-001"


def build_source_mission() -> ControlMission:
    return ControlMission(
        mission_id=MISSION_ID,
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-18T12:00:00Z",
        expires_at="2026-08-18T13:00:00Z",
        sequence=168001,
    )


def build_stack(
    tmp_path: Path,
) -> tuple[
    ControlMissionService,
    ControlMissionRepository,
    ControlMissionRegistry,
    ControlMissionStore,
    PersistentSecuritySequenceAllocator,
]:
    repository = ControlMissionRepository()

    persistence = ControlMissionPersistence(
        tmp_path / "control_missions.json"
    )

    registry = ControlMissionRegistry()

    record_persistence = (
        ControlMissionRecordPersistence(
            tmp_path
            / "control_mission_records.json"
        )
    )

    store = ControlMissionStore()

    delivery_bridge = ControlMissionDeliveryBridge(
        store
    )

    lifecycle_service = ControlMissionLifecycleService(
        registry,
        record_persistence,
        repository=repository,
        mission_persistence=persistence,
    )

    allocator = PersistentSecuritySequenceAllocator(
        tmp_path
        / "control_security_sequence.json"
    )

    binding_store = (
        PersistentSecuritySequenceBindingStore(
            tmp_path
            / "control_security_sequence_bindings.json"
        )
    )

    assignment_service = (
        SecuritySequenceAssignmentService(
            allocator=allocator,
            binding_store=binding_store,
        )
    )

    service = ControlMissionService(
        repository,
        persistence,
        delivery_bridge,
        registry,
        lifecycle_service,
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


def test_cloud_assigns_control_security_sequence_before_persistence(
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
        "trusted-agent-001"
    )

    assert queued is not None
    assert queued.security_sequence == 1


def test_identical_control_retry_reuses_security_sequence(
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


def test_conflicting_control_retry_is_rejected_without_allocating(
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
        action=ControlAction.CLOSE_RED,
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


def test_control_producer_cannot_supply_security_sequence(
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


def test_distinct_control_missions_receive_monotonic_security_sequences(
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
            "control-security-integration-002"
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