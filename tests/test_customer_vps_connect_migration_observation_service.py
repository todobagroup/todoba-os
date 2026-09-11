from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.commercial.customer_vps_connect_migration_observation_service import (
    CustomerVPSConnectMigrationObservationService,
)


@dataclass(frozen=True)
class _Proof:
    status: str


class _ProofProbe:
    def __init__(self, statuses):
        self._statuses = list(statuses)
        self.calls = 0

    def check_live_proof(self):
        self.calls += 1

        if not self._statuses:
            raise AssertionError(
                "Unexpected extra proof check."
            )

        return _Proof(
            status=self._statuses.pop(0)
        )


def _service(
    statuses,
    *,
    max_attempts=3,
    retry_after_ms=5000,
):
    probe = _ProofProbe(statuses)

    service = (
        CustomerVPSConnectMigrationObservationService(
            proof_probe=probe,
            max_attempts=max_attempts,
            retry_after_ms=retry_after_ms,
        )
    )

    return service, probe


def test_observation_requires_explicit_begin():
    service, probe = _service(
        ["runtime_ready"]
    )

    with pytest.raises(RuntimeError):
        service.observe()

    assert probe.calls == 0


def test_each_observation_performs_exactly_one_proof_check():
    service, probe = _service(
        [
            "runtime_ready",
            "runtime_ready",
            "vps_online",
        ]
    )

    service.begin()

    first = service.observe()

    assert first.status == "observation_pending"
    assert first.attempts == 1
    assert first.retry_after_ms == 5000
    assert probe.calls == 1

    second = service.observe()

    assert second.status == "observation_pending"
    assert second.attempts == 2
    assert probe.calls == 2

    third = service.observe()

    assert third.status == "vps_online"
    assert third.attempts == 3
    assert third.retry_after_ms is None
    assert probe.calls == 3


def test_runtime_ready_never_becomes_online_without_vps_origin():
    service, probe = _service(
        [
            "runtime_ready",
            "runtime_ready",
        ],
        max_attempts=2,
    )

    service.begin()

    assert (
        service.observe().status
        == "observation_pending"
    )

    result = service.observe()

    assert result.status == "observation_exhausted"
    assert result.attempts == 2
    assert result.retry_after_ms is None
    assert probe.calls == 2


def test_vps_pending_is_fail_closed_and_bounded():
    service, probe = _service(
        [
            "vps_pending",
            "vps_pending",
        ],
        max_attempts=2,
    )

    service.begin()

    assert (
        service.observe().status
        == "observation_pending"
    )

    assert (
        service.observe().status
        == "observation_exhausted"
    )

    assert probe.calls == 2


def test_vps_online_finishes_observation_immediately():
    service, probe = _service(
        [
            "vps_online",
            "vps_pending",
        ],
        max_attempts=5,
    )

    service.begin()

    result = service.observe()

    assert result.status == "vps_online"
    assert result.attempts == 1
    assert result.retry_after_ms is None
    assert probe.calls == 1

    with pytest.raises(RuntimeError):
        service.observe()

    assert probe.calls == 1


def test_begin_resets_bounded_observation():
    service, probe = _service(
        [
            "runtime_ready",
            "runtime_ready",
        ],
        max_attempts=1,
    )

    service.begin()

    assert (
        service.observe().status
        == "observation_exhausted"
    )

    service.begin()

    assert (
        service.observe().status
        == "observation_exhausted"
    )

    assert probe.calls == 2


def test_invalid_proof_status_fails_closed():
    service, _ = _service(
        ["unknown"]
    )

    service.begin()

    with pytest.raises(RuntimeError):
        service.observe()


@pytest.mark.parametrize(
    ("max_attempts", "retry_after_ms"),
    [
        (0, 5000),
        (True, 5000),
        (3, 0),
        (3, True),
    ],
)
def test_invalid_policy_is_rejected(
    max_attempts,
    retry_after_ms,
):
    probe = _ProofProbe(
        ["runtime_ready"]
    )

    with pytest.raises(ValueError):
        CustomerVPSConnectMigrationObservationService(
            proof_probe=probe,
            max_attempts=max_attempts,
            retry_after_ms=retry_after_ms,
        )


def test_observation_owner_has_policy_but_no_timing_or_gui_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_migration_observation_service.py"
    ).read_text(
        encoding="utf-8-sig",
    )

    assert "max_attempts" in source
    assert "retry_after_ms" in source

    for forbidden in (
        "time.sleep",
        "asyncio.sleep",
        "tkinter",
        ".after(",
        "threading",
        "while True",
        "subprocess",
        "common.ini",
        "pywinauto",
        "uiautomation",
    ):
        assert forbidden not in source
