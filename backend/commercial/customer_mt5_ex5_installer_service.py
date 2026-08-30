"""
TODOBA Customer MT5 EX5 Installer Service

Installs one already-downloaded, already-authorized TODOBA Trusted
Agent EX5 artifact into the exact MT5 data directory established by
Customer MT5 Setup Preflight.

Installation flow:

    CustomerMT5SetupPreflightResult
    downloaded EX5 bytes
    authoritative SHA-256
    authoritative size
        -> verify artifact before filesystem mutation
        -> resolve exact R4 data_path
        -> fixed MQL5/Experts target
        -> fail closed on conflicting existing artifact
        -> same artifact is idempotent success
        -> write temporary artifact
        -> verify temporary artifact
        -> atomic Windows rename into final target
        -> verify installed artifact

This owner does not:
- discover or select an MT5 terminal
- authenticate or change MT5 accounts
- build or compile MQL5
- enable Auto Trading
- attach an Expert Advisor to a chart
- purchase or migrate MetaTrader VPS
- call TODOBA server APIs
- persist duplicate commercial state
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)


_ARTIFACT_FILENAME = "TODOBA_Trusted_Agent.ex5"


@dataclass(
    frozen=True,
)
class CustomerMT5EX5InstallationResult:
    """
    Customer-side evidence that the requested EX5 bytes are installed.

    This result means INSTALLED only. It does not mean that the Expert
    Advisor is attached, running, online, or trading-ready.
    """

    terminal_path: str
    data_path: str
    account_fingerprint: str
    installed_path: str
    artifact_sha256: str
    artifact_size_bytes: int
    already_present: bool

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "terminal_path",
            "data_path",
            "account_fingerprint",
            "installed_path",
            "artifact_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        digest = self.artifact_sha256.lower()

        if (
            len(digest) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in digest
            )
        ):
            raise ValueError(
                "artifact_sha256 must be a SHA-256 "
                "hexadecimal digest."
            )

        object.__setattr__(
            self,
            "artifact_sha256",
            digest,
        )

        if (
            not isinstance(
                self.artifact_size_bytes,
                int,
            )
            or isinstance(
                self.artifact_size_bytes,
                bool,
            )
            or self.artifact_size_bytes <= 0
        ):
            raise ValueError(
                "artifact_size_bytes must be a positive int."
            )

        if not isinstance(
            self.already_present,
            bool,
        ):
            raise TypeError(
                "already_present must be bool."
            )


class CustomerMT5EX5InstallerService:
    """
    Install one verified deployment-specific EX5 artifact.

    Collision policy:
    - no target -> install
    - same SHA-256 and size -> idempotent success
    - any different existing target -> fail closed
    """

    def install(
        self,
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        artifact_bytes: bytes,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> CustomerMT5EX5InstallationResult:
        if not isinstance(
            preflight_result,
            CustomerMT5SetupPreflightResult,
        ):
            raise TypeError(
                "preflight_result must be "
                "CustomerMT5SetupPreflightResult."
            )

        if not isinstance(
            artifact_bytes,
            bytes,
        ):
            raise TypeError(
                "artifact_bytes must be bytes."
            )

        if len(
            artifact_bytes
        ) == 0:
            raise ValueError(
                "artifact_bytes must not be empty."
            )

        normalized_sha256 = _normalize_sha256(
            expected_sha256
        )

        if (
            not isinstance(
                expected_size_bytes,
                int,
            )
            or isinstance(
                expected_size_bytes,
                bool,
            )
            or expected_size_bytes <= 0
        ):
            raise ValueError(
                "expected_size_bytes must be a positive int."
            )

        if len(
            artifact_bytes
        ) != expected_size_bytes:
            raise ValueError(
                "Downloaded EX5 artifact size mismatch."
            )

        actual_download_sha256 = _sha256_bytes(
            artifact_bytes
        )

        if (
            actual_download_sha256
            != normalized_sha256
        ):
            raise ValueError(
                "Downloaded EX5 artifact SHA-256 mismatch."
            )

        (
            data_path,
            experts_path,
            target_path,
        ) = self._resolve_target(
            preflight_result
        )

        if target_path.is_symlink():
            raise RuntimeError(
                "TODOBA EX5 target must not be a symbolic link."
            )

        if target_path.exists():
            if not target_path.is_file():
                raise RuntimeError(
                    "TODOBA EX5 target exists but is not a file."
                )

            if self._matches_expected_artifact(
                target_path,
                expected_sha256=(
                    normalized_sha256
                ),
                expected_size_bytes=(
                    expected_size_bytes
                ),
            ):
                return self._build_result(
                    preflight_result=(
                        preflight_result
                    ),
                    data_path=data_path,
                    target_path=target_path,
                    artifact_sha256=(
                        normalized_sha256
                    ),
                    artifact_size_bytes=(
                        expected_size_bytes
                    ),
                    already_present=True,
                )

            raise FileExistsError(
                "Existing TODOBA EX5 artifact does not match "
                "the requested deployment package."
            )

        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".TODOBA_Trusted_Agent.",
                suffix=".tmp",
                dir=experts_path,
                delete=False,
            ) as temporary_file:
                temporary_file.write(
                    artifact_bytes
                )
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )

                temporary_path = Path(
                    temporary_file.name
                )

            if not self._matches_expected_artifact(
                temporary_path,
                expected_sha256=(
                    normalized_sha256
                ),
                expected_size_bytes=(
                    expected_size_bytes
                ),
            ):
                raise RuntimeError(
                    "Temporary TODOBA EX5 artifact verification "
                    "failed."
                )

            try:
                os.rename(
                    temporary_path,
                    target_path,
                )
            except OSError:
                if target_path.exists():
                    if (
                        target_path.is_file()
                        and not target_path.is_symlink()
                        and self._matches_expected_artifact(
                            target_path,
                            expected_sha256=(
                                normalized_sha256
                            ),
                            expected_size_bytes=(
                                expected_size_bytes
                            ),
                        )
                    ):
                        return self._build_result(
                            preflight_result=(
                                preflight_result
                            ),
                            data_path=data_path,
                            target_path=target_path,
                            artifact_sha256=(
                                normalized_sha256
                            ),
                            artifact_size_bytes=(
                                expected_size_bytes
                            ),
                            already_present=True,
                        )

                    raise FileExistsError(
                        "Existing TODOBA EX5 artifact does not "
                        "match the requested deployment package."
                    )

                raise

            temporary_path = None

            if not self._matches_expected_artifact(
                target_path,
                expected_sha256=(
                    normalized_sha256
                ),
                expected_size_bytes=(
                    expected_size_bytes
                ),
            ):
                raise RuntimeError(
                    "Installed TODOBA EX5 artifact verification "
                    "failed."
                )

            return self._build_result(
                preflight_result=preflight_result,
                data_path=data_path,
                target_path=target_path,
                artifact_sha256=(
                    normalized_sha256
                ),
                artifact_size_bytes=(
                    expected_size_bytes
                ),
                already_present=False,
            )
        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()

    @staticmethod
    def _resolve_target(
        preflight_result: CustomerMT5SetupPreflightResult,
    ) -> tuple[
        Path,
        Path,
        Path,
    ]:
        raw_data_path = Path(
            preflight_result.data_path
        )

        try:
            data_path = raw_data_path.resolve(
                strict=True
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "Authoritative MT5 data path does not exist."
            ) from exc

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

        if not mql5_path.is_dir():
            raise RuntimeError(
                "Authoritative MT5 data path has no MQL5 directory."
            )

        if not experts_path.is_dir():
            raise RuntimeError(
                "Authoritative MT5 data path has no Experts directory."
            )

        resolved_mql5 = mql5_path.resolve(
            strict=True
        )
        resolved_experts = experts_path.resolve(
            strict=True
        )

        if resolved_mql5.parent != data_path:
            raise RuntimeError(
                "MT5 MQL5 directory escapes authoritative data path."
            )

        if resolved_experts.parent != resolved_mql5:
            raise RuntimeError(
                "MT5 Experts directory escapes authoritative "
                "MQL5 directory."
            )

        target_path = (
            resolved_experts
            / _ARTIFACT_FILENAME
        )

        return (
            data_path,
            resolved_experts,
            target_path,
        )

    @staticmethod
    def _matches_expected_artifact(
        path: Path,
        *,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> bool:
        try:
            size = path.stat().st_size
        except OSError:
            return False

        if size != expected_size_bytes:
            return False

        return (
            _sha256_file(
                path
            )
            == expected_sha256
        )

    @staticmethod
    def _build_result(
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        data_path: Path,
        target_path: Path,
        artifact_sha256: str,
        artifact_size_bytes: int,
        already_present: bool,
    ) -> CustomerMT5EX5InstallationResult:
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
                target_path
            ),
            artifact_sha256=artifact_sha256,
            artifact_size_bytes=(
                artifact_size_bytes
            ),
            already_present=already_present,
        )


def _normalize_required_string(
    value: str,
    *,
    name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be str."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    return normalized


def _normalize_sha256(
    value: str,
) -> str:
    normalized = _normalize_required_string(
        value,
        name="expected_sha256",
    ).lower()

    if (
        len(normalized) != 64
        or any(
            character
            not in "0123456789abcdef"
            for character in normalized
        )
    ):
        raise ValueError(
            "expected_sha256 must be a SHA-256 "
            "hexadecimal digest."
        )

    return normalized


def _sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
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

    return digest.hexdigest()