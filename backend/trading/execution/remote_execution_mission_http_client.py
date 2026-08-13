"""
TODOBA Remote Execution Mission HTTP Client

Provides the authenticated HTTP connection used by
the Telegram remote executor to:

- read the latest Trusted Agent broker state
- submit ExecutionMission objects to TODOBA Cloud

This component does not:

- create trading decisions
- execute broker orders
- own mission persistence
- own mission queues
"""

from __future__ import annotations

import httpx

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class RemoteExecutionMissionHttpClient:
    """
    Connect the remote Telegram executor to TODOBA Cloud.
    """

    def __init__(
        self,
        *,
        cloud_base_url: str,
        executor_id: str,
        executor_secret: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        normalized_url = cloud_base_url.rstrip("/")
        normalized_executor_id = executor_id.strip()
        normalized_executor_secret = (
            executor_secret.strip()
        )

        if not normalized_url:
            raise ValueError(
                "cloud_base_url is required."
            )

        if not normalized_executor_id:
            raise ValueError(
                "executor_id is required."
            )

        if not normalized_executor_secret:
            raise ValueError(
                "executor_secret is required."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self.cloud_base_url = normalized_url
        self.executor_id = normalized_executor_id
        self.executor_secret = (
            normalized_executor_secret
        )
        self.timeout_seconds = timeout_seconds

    def _authentication_headers(
        self,
    ) -> dict[str, str]:
        return {
            "X-TODOBA-Executor-ID": (
                self.executor_id
            ),
            "Authorization": (
                f"Bearer {self.executor_secret}"
            ),
        }

    def read_latest_broker_state(
        self,
        *,
        agent_id: str,
    ) -> dict:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        normalized_agent_id = agent_id.strip()

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        response = httpx.get(
            (
                f"{self.cloud_base_url}"
                "/broker/state/latest"
            ),
            params={
                "agent_id": normalized_agent_id,
            },
            headers=self._authentication_headers(),
            timeout=self.timeout_seconds,
        )

        response.raise_for_status()

        return response.json()

    def send(
        self,
        mission: ExecutionMission,
    ) -> dict:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "RemoteExecutionMissionHttpClient "
                "requires ExecutionMission."
            )

        response = httpx.post(
            f"{self.cloud_base_url}/missions/inject",
            headers=self._authentication_headers(),
            json={
                "mission_id": mission.mission_id,
                "agent_id": mission.agent_id,
                "account_fingerprint": (
                    mission.account_fingerprint
                ),
                "symbol": mission.symbol,
                "order_type": mission.order_type,
                "volume": mission.volume,
                "entry": mission.entry,
                "sl": mission.sl,
                "tp": mission.tp,
                "magic_number": mission.magic_number,
                "comment": mission.comment,
                "created_at": mission.created_at,
                "expires_at": mission.expires_at,
                "sequence": mission.sequence,
            },
            timeout=self.timeout_seconds,
        )

        response.raise_for_status()

        return response.json()