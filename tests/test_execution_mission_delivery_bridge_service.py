from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)

from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="bridge-service-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Delivery Bridge",
        created_at="2026-07-29T00:00:00Z",
        expires_at="2026-07-30T00:00:00Z",
        sequence=1,
    )


def test_delivery_bridge_pushes_mission_into_store():

    store = ExecutionMissionStore()

    bridge = ExecutionMissionDeliveryBridge(
        store
    )

    mission = build_mission()

    result = bridge.deliver(
        mission
    )

    assert result == mission

    assert store.size() == 1

    delivered = store.pop()

    assert delivered is not None

    assert delivered.mission_id == (
        "bridge-service-001"
    )

    assert delivered.agent_id == (
        "trusted-agent-001"
    )