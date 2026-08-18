import importlib
import json
from pathlib import Path


MODULE_NAME = (
    "backend.trading.execution."
    "persistent_security_sequence_allocator"
)

SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "trading"
    / "execution"
    / "persistent_security_sequence_allocator.py"
)


def load_allocator_class():
    module = importlib.import_module(
        MODULE_NAME
    )

    return module.PersistentSecuritySequenceAllocator


def test_allocator_starts_at_zero_and_persists_allocations(
    tmp_path: Path,
) -> None:
    allocator_class = load_allocator_class()

    storage_path = (
        tmp_path
        / "security_sequence.json"
    )

    allocator = allocator_class(
        storage_path
    )

    assert allocator.current_sequence == 0
    assert allocator.allocate() == 1
    assert allocator.allocate() == 2
    assert allocator.current_sequence == 2

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload == {
        "current_sequence": 2,
    }


def test_allocator_restores_sequence_after_restart(
    tmp_path: Path,
) -> None:
    allocator_class = load_allocator_class()

    storage_path = (
        tmp_path
        / "security_sequence.json"
    )

    first_runtime = allocator_class(
        storage_path
    )

    assert first_runtime.allocate() == 1
    assert first_runtime.allocate() == 2

    second_runtime = allocator_class(
        storage_path
    )

    assert second_runtime.current_sequence == 2
    assert second_runtime.allocate() == 3
    assert second_runtime.current_sequence == 3


def test_independent_allocators_do_not_share_sequence_state(
    tmp_path: Path,
) -> None:
    allocator_class = load_allocator_class()

    execution_path = (
        tmp_path
        / "execution_security_sequence.json"
    )

    control_path = (
        tmp_path
        / "control_security_sequence.json"
    )

    execution_allocator = allocator_class(
        execution_path
    )

    control_allocator = allocator_class(
        control_path
    )

    assert execution_allocator.allocate() == 1
    assert execution_allocator.allocate() == 2

    assert control_allocator.allocate() == 1

    assert (
        execution_allocator.current_sequence
        == 2
    )

    assert (
        control_allocator.current_sequence
        == 1
    )


def test_allocator_uses_atomic_temporary_file_replacement() -> None:
    assert SOURCE_PATH.exists(), (
        "Persistent security sequence allocator "
        "source does not exist."
    )

    source = SOURCE_PATH.read_text(
        encoding="utf-8-sig"
    )

    assert '".tmp"' in source
    assert ".replace(" in source