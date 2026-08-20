"""
TODOBA Execution Target Registry

Owns the configured remote execution targets used by
higher-level routing and fan-out capabilities.

This component does not own:
- Trusted Agent credentials
- mission signing keys
- account binding security
- broker state
- execution missions
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionTarget:
    """
    Immutable execution routing target.

    One Trusted Agent owns one bound execution account.
    """

    agent_id: str
    account_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        if not isinstance(
            self.account_fingerprint,
            str,
        ):
            raise TypeError(
                "account_fingerprint must be str."
            )

        normalized_agent_id = (
            self.agent_id.strip()
        )

        normalized_account_fingerprint = (
            self.account_fingerprint.strip()
        )

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        if not normalized_account_fingerprint:
            raise ValueError(
                "account_fingerprint is required."
            )

        object.__setattr__(
            self,
            "agent_id",
            normalized_agent_id,
        )

        object.__setattr__(
            self,
            "account_fingerprint",
            normalized_account_fingerprint,
        )


class ExecutionTargetRegistry:
    """
    Registry of execution routing targets.

    Registration order is preserved so future fan-out
    behavior remains deterministic.
    """

    def __init__(self) -> None:
        self._targets: dict[
            str,
            ExecutionTarget,
        ] = {}

    def register(
        self,
        target: ExecutionTarget,
    ) -> ExecutionTarget:
        if not isinstance(
            target,
            ExecutionTarget,
        ):
            raise TypeError(
                "ExecutionTargetRegistry requires "
                "ExecutionTarget."
            )

        existing = self._targets.get(
            target.agent_id
        )

        if existing is not None:
            if existing != target:
                raise ValueError(
                    "Execution target Agent is already "
                    "registered with a different account."
                )

            return existing

        self._targets[
            target.agent_id
        ] = target

        return target

    def get(
        self,
        *,
        agent_id: str,
    ) -> ExecutionTarget | None:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        normalized_agent_id = (
            agent_id.strip()
        )

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        return self._targets.get(
            normalized_agent_id
        )

    def all(
        self,
    ) -> tuple[
        ExecutionTarget,
        ...,
    ]:
        return tuple(
            self._targets.values()
        )

    def size(
        self,
    ) -> int:
        return len(
            self._targets
        )


def build_execution_target_registry(
    targets: tuple[
        dict[str, str],
        ...,
    ],
) -> ExecutionTargetRegistry:
    """
    Build an ExecutionTargetRegistry from validated
    execution target configuration records.
    """

    if not isinstance(
        targets,
        tuple,
    ):
        raise TypeError(
            "targets must be tuple."
        )

    registry = ExecutionTargetRegistry()

    for target_record in targets:
        if not isinstance(
            target_record,
            dict,
        ):
            raise TypeError(
                "Execution target record must be dict."
            )

        if "agent_id" not in target_record:
            raise ValueError(
                "Execution target record requires agent_id."
            )

        if "account_fingerprint" not in target_record:
            raise ValueError(
                "Execution target record requires "
                "account_fingerprint."
            )

        registry.register(
            ExecutionTarget(
                agent_id=target_record[
                    "agent_id"
                ],
                account_fingerprint=target_record[
                    "account_fingerprint"
                ],
            )
        )

    return registry