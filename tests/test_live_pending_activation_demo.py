from types import SimpleNamespace
from unittest.mock import Mock

from backend.trading.pending.pending_activation_runtime import (
    PendingActivationRuntime,
)
from backend.trading.pending.pending_activation_scheduler import (
    PendingActivationScheduler,
)
from backend.trading.pending.pending_order_status import (
    PendingOrderStatus,
)


def build_runtime():
    record = SimpleNamespace(
        pending_order_id="pending-001",
        status=PendingOrderStatus.PLACED,
    )

    trade_record = SimpleNamespace(
        trade_id="pending-001",
    )

    observation = SimpleNamespace(
        status="FILLED",
    )

    activation_result = SimpleNamespace(
        activated=True,
        trade_record=trade_record,
    )

    repository = Mock()
    repository.all.return_value = [record]

    evidence_reader = Mock()
    evidence_reader.observe.return_value = observation

    activation_bridge = Mock()
    activation_bridge.activate.return_value = (
        activation_result
    )

    trading_runtime = Mock()

    runtime = PendingActivationRuntime(
        repository=repository,
        evidence_reader=evidence_reader,
        activation_bridge=activation_bridge,
        trading_runtime=trading_runtime,
    )

    return (
        runtime,
        record,
        trade_record,
        repository,
        evidence_reader,
        activation_bridge,
        trading_runtime,
    )


def test_pending_activation_runtime_registers_trade_and_removes_pending():
    (
        runtime,
        record,
        trade_record,
        repository,
        evidence_reader,
        activation_bridge,
        trading_runtime,
    ) = build_runtime()

    activated_count = runtime.process()

    assert activated_count == 1
    assert record.status == PendingOrderStatus.TRIGGERED

    evidence_reader.observe.assert_called_once_with(
        record
    )

    activation_bridge.activate.assert_called_once_with(
        record=record,
        observation=evidence_reader.observe.return_value,
    )

    trading_runtime.register_open_trade.assert_called_once_with(
        trade_record
    )

    repository.remove.assert_called_once_with(
        "pending-001"
    )


def test_pending_activation_scheduler_runs_runtime_cycle():
    (
        runtime,
        _record,
        _trade_record,
        _repository,
        _evidence_reader,
        _activation_bridge,
        _trading_runtime,
    ) = build_runtime()

    scheduler = PendingActivationScheduler(
        runtime=runtime,
        interval_seconds=1.0,
    )

    cycle = scheduler.run_cycle()

    assert cycle.cycle_number == 1
    assert cycle.activated_count == 1
    assert scheduler.cycle_count == 1
    assert scheduler.last_cycle == cycle
    assert scheduler.last_error is None