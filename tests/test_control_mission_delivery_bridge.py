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
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)


def build_mission(
    *,
    mission_id: str = "control-001",
    agent_id: str = "trusted-agent-001",
) -> ControlMission:
    return ControlMission(
        mission_id=mission_id,
        agent_id=agent_id,
        account_fingerprint="account-test",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def test_bridge_delivers_control_mission_to_agent_queue() -> None:
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    mission = build_mission()

    delivered = bridge.deliver(
        mission
    )

    assert delivered == mission
    assert store.size() == 1
    assert store.pop_for_agent(
        "trusted-agent-001"
    ) == mission


def test_bridge_preserves_agent_routing() -> None:
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    mission = build_mission(
        agent_id="trusted-agent-002"
    )

    bridge.deliver(
        mission
    )

    assert store.pop_for_agent(
        "trusted-agent-001"
    ) is None
    assert store.pop_for_agent(
        "trusted-agent-002"
    ) == mission


def test_bridge_retry_does_not_duplicate_mission() -> None:
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    mission = build_mission()

    first = bridge.deliver(
        mission
    )
    second = bridge.deliver(
        mission
    )

    assert first == mission
    assert second == mission
    assert store.size() == 1


def test_bridge_rejects_invalid_store() -> None:
    with pytest.raises(
        TypeError,
        match="requires ControlMissionStore",
    ):
        ControlMissionDeliveryBridge(
            "not-a-store"
        )


def test_bridge_rejects_invalid_mission() -> None:
    bridge = ControlMissionDeliveryBridge(
        ControlMissionStore()
    )

    with pytest.raises(
        TypeError,
        match="deliver requires ControlMission",
    ):
        bridge.deliver(
            "not-a-mission"
        )


def test_bridge_redelivers_mission_after_delivery_attempt() -> None:
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    mission = build_mission()
    bridge.deliver(
        mission
    )
    assert store.pop_for_agent(
        "trusted-agent-001"
    ) == mission

    redelivered = bridge.redeliver(
        mission
    )

    assert redelivered == mission
    assert store.size() == 1
    assert store.pop_for_agent(
        "trusted-agent-001"
    ) == mission


def test_bridge_redelivery_does_not_duplicate_queue() -> None:
    store = ControlMissionStore()
    bridge = ControlMissionDeliveryBridge(
        store
    )
    mission = build_mission()
    bridge.deliver(
        mission
    )

    bridge.redeliver(
        mission
    )
    bridge.redeliver(
        mission
    )

    assert store.size() == 1


def test_bridge_rejects_invalid_redelivery_mission() -> None:
    bridge = ControlMissionDeliveryBridge(
        ControlMissionStore()
    )

    with pytest.raises(
        TypeError,
        match="redeliver requires ControlMission",
    ):
        bridge.redeliver(
            "not-a-mission"
        )