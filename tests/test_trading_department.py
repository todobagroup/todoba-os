import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pytest

from backend.brain.memory import MemoryEngine
from backend.trading.department.trading_department import (
    TradingDepartment,
)
from backend.trading.pending.pending_activation_bridge import (
    PendingActivationBridge,
)
from backend.trading.pending.pending_activation_runtime import (
    PendingActivationRuntime,
)
from backend.trading.pending.pending_broker_evidence_reader import (
    PendingBrokerEvidenceReader,
)


class DummyExecutionPipeline:
    pass


class DummyMT5:
    pass


def create_memory() -> MemoryEngine:
    return MemoryEngine.__new__(
        MemoryEngine
    )


def test_trading_department_requires_pipeline():

    with pytest.raises(
        ValueError,
        match="requires an execution pipeline",
    ):
        TradingDepartment(
            execution_pipeline=None,
            open_trades_storage_path=Path(
                "open_trades.json"
            ),
            memory=create_memory(),
        )


def test_trading_department_requires_storage_path():

    with pytest.raises(
        TypeError,
        match="open_trades_storage_path must be Path",
    ):
        TradingDepartment(
            execution_pipeline=(
                DummyExecutionPipeline()
            ),
            open_trades_storage_path=(
                "open_trades.json"
            ),
            memory=create_memory(),
        )


def test_department_owns_pending_activation_capability(
    tmp_path,
):

    department = TradingDepartment(
        execution_pipeline=(
            DummyExecutionPipeline()
        ),
        open_trades_storage_path=(
            tmp_path / "open_trades.json"
        ),
        memory=create_memory(),
        mt5_module=DummyMT5(),
    )

    assert isinstance(
        department.pending_evidence_reader,
        PendingBrokerEvidenceReader,
    )

    assert isinstance(
        department.pending_activation_bridge,
        PendingActivationBridge,
    )

    assert isinstance(
        department.pending_activation_runtime,
        PendingActivationRuntime,
    )

    assert (
        department.pending_activation_runtime.repository
        is department.pending_repository
    )

    assert (
        department.pending_activation_runtime.evidence_reader
        is department.pending_evidence_reader
    )

    assert (
        department.pending_activation_runtime.activation_bridge
        is department.pending_activation_bridge
    )

    assert (
        department.pending_activation_runtime.trading_runtime
        is department.runtime
    )