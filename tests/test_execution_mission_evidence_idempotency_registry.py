import pytest

from backend.trading.execution.execution_mission_evidence_idempotency_registry import (
    ExecutionMissionEvidenceIdempotencyRegistry,
)


def test_accepts_new_identity() -> None:
    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    accepted = registry.accept(
        "COMPLETED:mission-001"
    )

    assert accepted is True
    assert registry.size() == 1


def test_rejects_duplicate_identity() -> None:
    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    assert registry.accept(
        "COMPLETED:mission-001"
    ) is True

    assert registry.accept(
        "COMPLETED:mission-001"
    ) is False

    assert registry.size() == 1


def test_contains_accepted_identity() -> None:
    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    registry.accept(
        "FAILED:mission-001"
    )

    assert registry.contains(
        "FAILED:mission-001"
    ) is True

    assert registry.contains(
        "FAILED:mission-999"
    ) is False


def test_accept_rejects_empty_identity() -> None:
    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    with pytest.raises(
        ValueError,
        match="identity must not be empty.",
    ):
        registry.accept(
            ""
        )

    assert registry.size() == 0


def test_accept_rejects_wrong_identity_type() -> None:
    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    with pytest.raises(
        TypeError,
        match="identity must be str.",
    ):
        registry.accept(
            123
        )

    assert registry.size() == 0


def test_contains_rejects_wrong_identity_type() -> None:
    registry = (
        ExecutionMissionEvidenceIdempotencyRegistry()
    )

    with pytest.raises(
        TypeError,
        match="identity must be str.",
    ):
        registry.contains(
            123
        )