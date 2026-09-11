"""
TODOBA Customer VPS Connect MT5 Installed Agent Verifier.

Verifies that the already-installed TODOBA Trusted Agent exists
inside the exact authoritative MT5 data tree established by
Customer MT5 Setup Preflight.

This owner is read-only. It returns the standard Setup installation
evidence type so runtime preparation receives authoritative,
type-convergent EX5 evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
)

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)


_ARTIFACT_FILENAME = "TODOBA_Trusted_Agent.ex5"


class CustomerVPSConnectMT5InstalledAgentVerifier:
    """
    Verify one already-installed TODOBA Agent inside one exact MT5.
    """

    def verify(
        self,
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
    ) -> CustomerMT5EX5InstallationResult:
        if not isinstance(
            preflight_result,
            CustomerMT5SetupPreflightResult,
        ):
            raise TypeError(
                "preflight_result must be "
                "CustomerMT5SetupPreflightResult."
            )

        raw_data_path = Path(
            preflight_result.data_path
        )

        try:
            data_path = raw_data_path.resolve(
                strict=True
            )
        except FileNotFoundError as error:
            raise FileNotFoundError(
                "Authoritative MT5 data path does not exist."
            ) from error

        if not data_path.is_dir():
            raise RuntimeError(
                "Authoritative MT5 data path is not a directory."
            )

        mql5_path = (
            data_path
            / "MQL5"
        )

        experts_path = (
            mql5_path
            / "Experts"
        )

        target_path = (
            experts_path
            / _ARTIFACT_FILENAME
        )

        if target_path.is_symlink():
            raise RuntimeError(
                "TODOBA Agent target must not be a symbolic link."
            )

        if not target_path.exists():
            raise FileNotFoundError(
                "TODOBA Trusted Agent is not installed."
            )

        if not target_path.is_file():
            raise RuntimeError(
                "TODOBA Trusted Agent target is not a file."
            )

        try:
            resolved_mql5 = mql5_path.resolve(
                strict=True
            )

            resolved_experts = experts_path.resolve(
                strict=True
            )

            resolved_target = target_path.resolve(
                strict=True
            )
        except OSError as error:
            raise RuntimeError(
                "Unable to resolve installed TODOBA Agent path."
            ) from error

        if (
            resolved_mql5.parent
            != data_path
        ):
            raise RuntimeError(
                "MT5 MQL5 directory escapes authoritative data path."
            )

        if (
            resolved_experts.parent
            != resolved_mql5
        ):
            raise RuntimeError(
                "MT5 Experts directory escapes authoritative "
                "MQL5 directory."
            )

        if (
            resolved_target.parent
            != resolved_experts
        ):
            raise RuntimeError(
                "TODOBA Agent escapes authoritative Experts directory."
            )

        if (
            resolved_target.name.casefold()
            != _ARTIFACT_FILENAME.casefold()
        ):
            raise RuntimeError(
                "TODOBA Agent filename does not match "
                "the authoritative artifact name."
            )

        artifact_size_bytes = (
            resolved_target.stat().st_size
        )

        if artifact_size_bytes <= 0:
            raise RuntimeError(
                "TODOBA Trusted Agent artifact is empty."
            )

        digest = hashlib.sha256()

        with resolved_target.open(
            "rb"
        ) as artifact:
            for chunk in iter(
                lambda: artifact.read(
                    1024 * 1024
                ),
                b"",
            ):
                digest.update(
                    chunk
                )

        artifact_sha256 = (
            digest.hexdigest()
        )

        return CustomerMT5EX5InstallationResult(
            terminal_path=(
                preflight_result.terminal_path
            ),
            data_path=str(
                data_path
            ),
            account_fingerprint=(
                preflight_result.account_fingerprint
            ),
            installed_path=str(
                resolved_target
            ),
            artifact_sha256=artifact_sha256,
            artifact_size_bytes=(
                artifact_size_bytes
            ),
            already_present=True,
        )
