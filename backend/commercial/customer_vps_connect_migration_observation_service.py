from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


class CustomerVPSConnectMigrationProofProbe(
    Protocol
):
    def check_live_proof(
        self,
    ):
        ...


@dataclass(
    frozen=True,
)
class CustomerVPSConnectMigrationObservationResult:
    status: Literal[
        "observation_pending",
        "observation_exhausted",
        "vps_online",
    ]
    attempts: int
    retry_after_ms: int | None

    def __post_init__(
        self,
    ) -> None:
        if self.status not in {
            "observation_pending",
            "observation_exhausted",
            "vps_online",
        }:
            raise ValueError(
                "Unsupported migration observation status."
            )

        if (
            not isinstance(self.attempts, int)
            or isinstance(self.attempts, bool)
            or self.attempts < 1
        ):
            raise ValueError(
                "attempts must be a positive int."
            )

        if self.status == "observation_pending":
            if (
                not isinstance(self.retry_after_ms, int)
                or isinstance(self.retry_after_ms, bool)
                or self.retry_after_ms < 1
            ):
                raise ValueError(
                    "pending observation requires "
                    "positive retry_after_ms."
                )
        elif self.retry_after_ms is not None:
            raise ValueError(
                "terminal observation result must not retry."
            )


class CustomerVPSConnectMigrationObservationService:
    def __init__(
        self,
        *,
        proof_probe: CustomerVPSConnectMigrationProofProbe,
        max_attempts: int,
        retry_after_ms: int,
    ) -> None:
        if (
            not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or max_attempts < 1
        ):
            raise ValueError(
                "max_attempts must be a positive int."
            )

        if (
            not isinstance(retry_after_ms, int)
            or isinstance(retry_after_ms, bool)
            or retry_after_ms < 1
        ):
            raise ValueError(
                "retry_after_ms must be a positive int."
            )

        if not callable(
            getattr(
                proof_probe,
                "check_live_proof",
                None,
            )
        ):
            raise TypeError(
                "proof_probe must provide "
                "check_live_proof()."
            )

        self._proof_probe = proof_probe
        self._max_attempts = max_attempts
        self._retry_after_ms = retry_after_ms
        self._attempts = 0
        self._active = False

    def begin(
        self,
    ) -> None:
        self._attempts = 0
        self._active = True

    def observe(
        self,
    ) -> CustomerVPSConnectMigrationObservationResult:
        if not self._active:
            raise RuntimeError(
                "Migration observation is not active."
            )

        if self._attempts >= self._max_attempts:
            self._active = False
            raise RuntimeError(
                "Migration observation attempt limit exceeded."
            )

        proof = self._proof_probe.check_live_proof()

        self._attempts += 1

        status = getattr(
            proof,
            "status",
            None,
        )

        if status == "vps_online":
            self._active = False

            return CustomerVPSConnectMigrationObservationResult(
                status="vps_online",
                attempts=self._attempts,
                retry_after_ms=None,
            )

        if status not in {
            "runtime_ready",
            "vps_pending",
        }:
            self._active = False

            raise RuntimeError(
                "Invalid VPS migration proof status."
            )

        if self._attempts >= self._max_attempts:
            self._active = False

            return CustomerVPSConnectMigrationObservationResult(
                status="observation_exhausted",
                attempts=self._attempts,
                retry_after_ms=None,
            )

        return CustomerVPSConnectMigrationObservationResult(
            status="observation_pending",
            attempts=self._attempts,
            retry_after_ms=self._retry_after_ms,
        )
