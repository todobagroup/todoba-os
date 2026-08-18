"""
TODOBA Trusted Agent Protocol Dependency

Owns authenticated mission protocol negotiation for
Trusted Agents.

Responsibilities:
- authenticate Trusted Agent credentials
- read the optional mission protocol header
- default legacy Agents to V1
- accept supported mission protocol generations
- reject unsupported protocol generations fail-closed

This component does not:
- sign missions
- serialize missions
- execute broker actions
- own Agent software versioning
"""

from dataclasses import dataclass

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


@dataclass(frozen=True)
class TrustedAgentProtocolContext:
    """
    Authenticated Trusted Agent mission protocol context.
    """

    agent_id: str
    mission_protocol: str


def create_trusted_agent_protocol_dependency(
    authenticator: TrustedAgentAuthenticator,
):
    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_trusted_agent_protocol_dependency "
            "requires TrustedAgentAuthenticator."
        )

    def require_trusted_agent_protocol(
        agent_id: str | None = Header(
            default=None,
            alias="X-TODOBA-Agent-ID",
        ),
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
        mission_protocol: str | None = Header(
            default=None,
            alias="X-TODOBA-Mission-Protocol",
        ),
    ) -> TrustedAgentProtocolContext:
        if not authenticator.authenticate(
            agent_id=agent_id,
            authorization=authorization,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Trusted Agent authentication failed."
                ),
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        normalized_protocol = (
            "V1"
            if mission_protocol is None
            else mission_protocol.strip().upper()
        )

        if normalized_protocol not in {
            "V1",
            "V2",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Unsupported TODOBA mission protocol."
                ),
            )

        return TrustedAgentProtocolContext(
            agent_id=agent_id.strip(),
            mission_protocol=normalized_protocol,
        )

    return require_trusted_agent_protocol