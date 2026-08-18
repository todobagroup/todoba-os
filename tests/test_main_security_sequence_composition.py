from pathlib import Path

from backend.main import (
    CONTROL_SECURITY_SEQUENCE_BINDING_STORAGE_PATH,
    CONTROL_SECURITY_SEQUENCE_STORAGE_PATH,
    EXECUTION_SECURITY_SEQUENCE_BINDING_STORAGE_PATH,
    EXECUTION_SECURITY_SEQUENCE_STORAGE_PATH,
    control_mission_service,
    control_security_sequence_allocator,
    control_security_sequence_assignment_service,
    control_security_sequence_binding_store,
    execution_mission_service,
    execution_security_sequence_allocator,
    execution_security_sequence_assignment_service,
    execution_security_sequence_binding_store,
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


def test_main_composes_independent_security_sequence_domains() -> None:
    assert isinstance(
        execution_security_sequence_allocator,
        PersistentSecuritySequenceAllocator,
    )

    assert isinstance(
        control_security_sequence_allocator,
        PersistentSecuritySequenceAllocator,
    )

    assert (
        execution_security_sequence_allocator
        is not control_security_sequence_allocator
    )

    assert isinstance(
        execution_security_sequence_binding_store,
        PersistentSecuritySequenceBindingStore,
    )

    assert isinstance(
        control_security_sequence_binding_store,
        PersistentSecuritySequenceBindingStore,
    )

    assert (
        execution_security_sequence_binding_store
        is not control_security_sequence_binding_store
    )

    assert isinstance(
        execution_security_sequence_assignment_service,
        SecuritySequenceAssignmentService,
    )

    assert isinstance(
        control_security_sequence_assignment_service,
        SecuritySequenceAssignmentService,
    )

    assert (
        execution_security_sequence_assignment_service
        is not control_security_sequence_assignment_service
    )

    assert (
        execution_security_sequence_assignment_service.allocator
        is execution_security_sequence_allocator
    )

    assert (
        execution_security_sequence_assignment_service.binding_store
        is execution_security_sequence_binding_store
    )

    assert (
        control_security_sequence_assignment_service.allocator
        is control_security_sequence_allocator
    )

    assert (
        control_security_sequence_assignment_service.binding_store
        is control_security_sequence_binding_store
    )

    assert (
        execution_mission_service.security_sequence_assignment_service
        is execution_security_sequence_assignment_service
    )

    assert (
        control_mission_service.security_sequence_assignment_service
        is control_security_sequence_assignment_service
    )


def test_main_uses_separate_persistent_security_storage_paths() -> None:
    assert EXECUTION_SECURITY_SEQUENCE_STORAGE_PATH == (
        Path("data")
        / "trading"
        / "execution_security_sequence.json"
    )

    assert EXECUTION_SECURITY_SEQUENCE_BINDING_STORAGE_PATH == (
        Path("data")
        / "trading"
        / "execution_security_sequence_bindings.json"
    )

    assert CONTROL_SECURITY_SEQUENCE_STORAGE_PATH == (
        Path("data")
        / "trading"
        / "control_security_sequence.json"
    )

    assert CONTROL_SECURITY_SEQUENCE_BINDING_STORAGE_PATH == (
        Path("data")
        / "trading"
        / "control_security_sequence_bindings.json"
    )

    assert (
        EXECUTION_SECURITY_SEQUENCE_STORAGE_PATH
        != CONTROL_SECURITY_SEQUENCE_STORAGE_PATH
    )

    assert (
        EXECUTION_SECURITY_SEQUENCE_BINDING_STORAGE_PATH
        != CONTROL_SECURITY_SEQUENCE_BINDING_STORAGE_PATH
    )