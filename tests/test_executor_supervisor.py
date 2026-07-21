import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from backend.runtime.executor_supervisor import (
    ExecutorSupervisor,
)


def test_runner_completes_normally():
    call_count = 0

    def runner():
        nonlocal call_count
        call_count += 1

    supervisor = ExecutorSupervisor(
        runner,
    )

    supervisor.run()

    assert call_count == 1
    assert supervisor.restart_count == 0
    assert supervisor.running is False


def test_runner_recovers_after_failure(
    monkeypatch,
):
    call_count = 0
    sleep_delays = []

    def runner():
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            raise RuntimeError(
                "Simulated executor failure."
            )

    def fake_sleep(seconds):
        sleep_delays.append(seconds)

    monkeypatch.setattr(
        "backend.runtime.executor_supervisor.time.sleep",
        fake_sleep,
    )

    supervisor = ExecutorSupervisor(
        runner,
        restart_delay_seconds=5.0,
    )

    supervisor.run()

    assert call_count == 2
    assert supervisor.restart_count == 1
    assert sleep_delays == [5.0]
    assert supervisor.running is False


def test_keyboard_interrupt_stops_supervisor():
    call_count = 0

    def runner():
        nonlocal call_count
        call_count += 1
        raise KeyboardInterrupt

    supervisor = ExecutorSupervisor(
        runner,
    )

    supervisor.run()

    assert call_count == 1
    assert supervisor.restart_count == 0
    assert supervisor.running is False


def test_invalid_restart_delay():
    with pytest.raises(ValueError):
        ExecutorSupervisor(
            lambda: None,
            restart_delay_seconds=0,
        )


def test_invalid_runner():
    with pytest.raises(TypeError):
        ExecutorSupervisor(
            None,
        )