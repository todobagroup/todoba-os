from unittest.mock import Mock

import httpx
import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.remote_control_mission_http_client import (
    RemoteControlMissionHttpClient,
)


def build_client() -> RemoteControlMissionHttpClient:
    return RemoteControlMissionHttpClient(
        cloud_base_url="https://cloud.example.test/",
        executor_id="executor-test",
        executor_secret="secret-test",
    )


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id="control-test-001",
        agent_id="trusted-agent-002",
        account_fingerprint=(
            "XMGlobal-MT5 6:1301858471"
        ),
        action=ControlAction.CLOSE_BUY,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=123456,
        created_at="2026-08-24T05:00:00Z",
        expires_at="2026-08-24T05:02:00Z",
        sequence=501,
    )


def test_constructor_normalizes_configuration():
    client = RemoteControlMissionHttpClient(
        cloud_base_url=(
            "https://cloud.example.test/"
        ),
        executor_id=" executor-test ",
        executor_secret=" secret-test ",
        timeout_seconds=7.5,
    )

    assert (
        client.cloud_base_url
        == "https://cloud.example.test"
    )
    assert client.executor_id == "executor-test"
    assert client.executor_secret == "secret-test"
    assert client.timeout_seconds == 7.5


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "expected_message",
    ),
    [
        (
            "cloud_base_url",
            "",
            "cloud_base_url is required.",
        ),
        (
            "executor_id",
            "",
            "executor_id is required.",
        ),
        (
            "executor_secret",
            "",
            "executor_secret is required.",
        ),
    ],
)
def test_constructor_rejects_missing_configuration(
    field,
    value,
    expected_message,
):
    kwargs = {
        "cloud_base_url": (
            "https://cloud.example.test"
        ),
        "executor_id": "executor-test",
        "executor_secret": "secret-test",
    }

    kwargs[field] = value

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        RemoteControlMissionHttpClient(
            **kwargs
        )


def test_constructor_rejects_invalid_timeout():
    with pytest.raises(
        ValueError,
        match=(
            "timeout_seconds must be greater "
            "than zero."
        ),
    ):
        RemoteControlMissionHttpClient(
            cloud_base_url=(
                "https://cloud.example.test"
            ),
            executor_id="executor-test",
            executor_secret="secret-test",
            timeout_seconds=0,
        )


def test_read_latest_broker_state_uses_authenticated_get(
    monkeypatch,
):
    response = Mock()
    response.json.return_value = {
        "agent_id": "trusted-agent-002",
        "open_position_count": 4,
    }

    get_mock = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        httpx,
        "get",
        get_mock,
    )

    result = (
        build_client()
        .read_latest_broker_state(
            agent_id=" trusted-agent-002 "
        )
    )

    get_mock.assert_called_once_with(
        (
            "https://cloud.example.test"
            "/broker/state/latest"
        ),
        params={
            "agent_id": "trusted-agent-002",
        },
        headers={
            "X-TODOBA-Executor-ID": (
                "executor-test"
            ),
            "Authorization": (
                "Bearer secret-test"
            ),
        },
        timeout=5.0,
    )

    response.raise_for_status.assert_called_once_with()

    assert result == {
        "agent_id": "trusted-agent-002",
        "open_position_count": 4,
    }


def test_read_latest_broker_state_rejects_invalid_agent():
    client = build_client()

    with pytest.raises(
        TypeError,
        match="agent_id must be str.",
    ):
        client.read_latest_broker_state(
            agent_id=None
        )

    with pytest.raises(
        ValueError,
        match="agent_id is required.",
    ):
        client.read_latest_broker_state(
            agent_id="   "
        )


def test_send_posts_exact_control_contract(
    monkeypatch,
):
    response = Mock()
    response.json.return_value = {
        "status": "persisted",
        "mission_id": "control-test-001",
    }

    post_mock = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        httpx,
        "post",
        post_mock,
    )

    mission = build_mission()

    result = build_client().send(
        mission
    )

    post_mock.assert_called_once_with(
        (
            "https://cloud.example.test"
            "/control/missions/inject"
        ),
        headers={
            "X-TODOBA-Executor-ID": (
                "executor-test"
            ),
            "Authorization": (
                "Bearer secret-test"
            ),
        },
        json={
            "mission_id": "control-test-001",
            "agent_id": "trusted-agent-002",
            "account_fingerprint": (
                "XMGlobal-MT5 6:1301858471"
            ),
            "action": "CLOSE_BUY",
            "symbol": "XAUUSD",
            "magic_number": 10001,
            "requested_by_sender_id": 123456,
            "created_at": (
                "2026-08-24T05:00:00Z"
            ),
            "expires_at": (
                "2026-08-24T05:02:00Z"
            ),
            "sequence": 501,
        },
        timeout=5.0,
    )

    response.raise_for_status.assert_called_once_with()

    assert result == {
        "status": "persisted",
        "mission_id": "control-test-001",
    }


def test_send_rejects_wrong_mission_type():
    with pytest.raises(
        TypeError,
        match=(
            "RemoteControlMissionHttpClient "
            "requires ControlMission."
        ),
    ):
        build_client().send(
            object()
        )


def test_http_failure_propagates_fail_closed(
    monkeypatch,
):
    response = Mock()

    response.raise_for_status.side_effect = (
        httpx.HTTPStatusError(
            "500",
            request=Mock(),
            response=Mock(),
        )
    )

    monkeypatch.setattr(
        httpx,
        "post",
        Mock(
            return_value=response
        ),
    )

    with pytest.raises(
        httpx.HTTPStatusError
    ):
        build_client().send(
            build_mission()
        )
