"""
TODOBA Customer Deployment Package Build Lock

Provides one Windows OS-native exclusive build lock for a
customer deployment package.

Purpose:

Multiple TODOBA processes may observe the same immutable
package-build request. Only one worker may build/publish the
package for one deployment at a time.

Architecture:

deployment_id
    -> deterministic non-secret zero-byte lock file
    -> Windows byte-range exclusive lock
    -> one active package builder

Windows permits msvcrt byte-range locking beyond the current
end of a file. The persistent lock file therefore remains
empty for its entire lifetime.

This removes any initialization-write state transition and
avoids a first-creation race between package workers.

Properties:

- acquisition is non-blocking
- same deployment cannot be built concurrently
- different deployments may be built concurrently
- release makes the deployment immediately available
- process termination/crash releases the OS lock
- lock ownership is held by the operating-system file handle
- persistent lock files remain zero-byte
- lock filenames expose only SHA-256 deployment identity

This component does not:
- persist commercial job status
- use time-based leases
- use worker heartbeats
- write mutable lock metadata
- build or publish EX5 artifacts
- access MetaEditor
- access deployment secrets
- access MT5 account fingerprints
- activate deployments
- provision customer access
- authenticate HTTP requests

Windows is authoritative for this capability.
"""

from __future__ import annotations

import errno
import hashlib
import msvcrt
from pathlib import Path
from typing import BinaryIO


_LOCK_FILE_PREFIX = "build-lock-"
_LOCK_FILE_SUFFIX = ".lock"

_LOCK_BYTE_COUNT = 1


class CustomerDeploymentPackageBuildLock:
    """
    One acquired Windows package-build lock.

    The open file handle owns the operating-system lock.

    release() is idempotent.

    The object is also a context manager so callers can
    guarantee normal-path release with a with-block.
    """

    def __init__(
        self,
        *,
        deployment_id: str,
        lock_path: Path,
        handle: BinaryIO,
    ) -> None:
        self.deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        if not isinstance(
            lock_path,
            Path,
        ):
            raise TypeError(
                "lock_path must be Path."
            )

        if not hasattr(
            handle,
            "fileno",
        ):
            raise TypeError(
                "handle must expose fileno()."
            )

        self.lock_path = lock_path
        self._handle = handle
        self._released = False

    @property
    def released(
        self,
    ) -> bool:
        return self._released

    def release(
        self,
    ) -> None:
        """
        Release the Windows byte-range lock and close its
        owning file handle.

        Repeated release is safe.
        """

        if self._released:
            return

        error: BaseException | None = None

        try:
            self._handle.seek(
                0
            )

            msvcrt.locking(
                self._handle.fileno(),
                msvcrt.LK_UNLCK,
                _LOCK_BYTE_COUNT,
            )
        except BaseException as exc:
            error = exc
        finally:
            try:
                self._handle.close()
            finally:
                self._released = True

        if error is not None:
            raise error

    def __enter__(
        self,
    ) -> "CustomerDeploymentPackageBuildLock":
        if self._released:
            raise RuntimeError(
                "Customer deployment package build lock "
                "has already been released."
            )

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:
        self.release()

        return False

    @staticmethod
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


class CustomerDeploymentPackageBuildLockManager:
    """
    Acquire deployment-scoped Windows package-build locks.

    This manager owns no durable commercial state.

    threading locks are intentionally insufficient here:
    package builders may run in separate Python processes.

    Cross-process exclusion is therefore provided directly
    by Windows through msvcrt.locking().
    """

    def __init__(
        self,
        lock_root: Path,
    ) -> None:
        if not isinstance(
            lock_root,
            Path,
        ):
            raise TypeError(
                "lock_root must be Path."
            )

        self.lock_root = lock_root

    def acquire(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentPackageBuildLock | None:
        """
        Attempt one non-blocking deployment build lock.

        Returns:
            CustomerDeploymentPackageBuildLock
                lock acquired by this process

            None
                another process currently owns the same
                deployment build lock
        """

        normalized_deployment_id = (
            CustomerDeploymentPackageBuildLock
            ._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        self._prepare_lock_root()

        lock_path = self._lock_path(
            deployment_id=(
                normalized_deployment_id
            )
        )

        # A dangling symlink reports exists() == False,
        # therefore test symlink identity independently.
        if lock_path.is_symlink():
            raise RuntimeError(
                "Customer package build lock file must "
                "not be a symlink."
            )

        if lock_path.exists():
            self._validate_lock_file(
                lock_path
            )

        # a+b atomically opens-or-creates the persistent
        # lock file without truncating existing material.
        #
        # No initialization byte is written. Windows has
        # been production-probed to lock one byte beyond
        # EOF on this zero-byte file.
        handle = lock_path.open(
            "a+b",
            buffering=0,
        )

        try:
            self._validate_lock_file(
                lock_path
            )

            handle.seek(
                0
            )

            msvcrt.locking(
                handle.fileno(),
                msvcrt.LK_NBLCK,
                _LOCK_BYTE_COUNT,
            )

        except OSError as exc:
            handle.close()

            if exc.errno in {
                errno.EACCES,
                errno.EAGAIN,
                errno.EDEADLK,
            }:
                return None

            raise

        except BaseException:
            handle.close()
            raise

        return CustomerDeploymentPackageBuildLock(
            deployment_id=(
                normalized_deployment_id
            ),
            lock_path=lock_path,
            handle=handle,
        )

    def lock_path(
        self,
        *,
        deployment_id: str,
    ) -> Path:
        """
        Return the deterministic non-secret lock path.

        This method does not create filesystem state.
        """

        normalized_deployment_id = (
            CustomerDeploymentPackageBuildLock
            ._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        return self._lock_path(
            deployment_id=(
                normalized_deployment_id
            )
        )

    def _prepare_lock_root(
        self,
    ) -> None:
        if self.lock_root.exists():
            if self.lock_root.is_symlink():
                raise RuntimeError(
                    "Customer package build lock root "
                    "must not be a symlink."
                )

            if not self.lock_root.is_dir():
                raise RuntimeError(
                    "Customer package build lock root "
                    "must be a directory."
                )

            return

        self.lock_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
            self.lock_root.is_symlink()
            or not self.lock_root.is_dir()
        ):
            raise RuntimeError(
                "Customer package build lock root "
                "could not be prepared safely."
            )

    @staticmethod
    def _validate_lock_file(
        lock_path: Path,
    ) -> None:
        if lock_path.is_symlink():
            raise RuntimeError(
                "Customer package build lock file must "
                "not be a symlink."
            )

        if not lock_path.is_file():
            raise RuntimeError(
                "Customer package build lock path must "
                "be a file."
            )

        if lock_path.stat().st_size != 0:
            raise RuntimeError(
                "Customer package build lock file must "
                "remain empty."
            )

    def _lock_path(
        self,
        *,
        deployment_id: str,
    ) -> Path:
        digest = hashlib.sha256(
            deployment_id.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            self.lock_root
            / (
                _LOCK_FILE_PREFIX
                + digest
                + _LOCK_FILE_SUFFIX
            )
        )
