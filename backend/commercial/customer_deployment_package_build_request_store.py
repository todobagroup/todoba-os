"""
TODOBA Customer Deployment Package Build Request Store

Owns immutable durable requests for building one customer
Trusted Agent package outside the cloud HTTP process.

Architecture:

Customer Setup / Online Orchestration
    -> prepared customer deployment bootstrap
    -> immutable durable package build request

Windows Package Build Worker
    -> enumerate build requests
    -> recover authoritative prepared bootstrap
    -> acquire a separate build lease
    -> build / verify / publish EX5

CustomerDeploymentPackagePublication remains authoritative
for whether a valid package has actually been published.

Persistence architecture:

- one immutable directory per deployment_id
- one request.json inside each request directory
- final request directory name is deterministic
- new requests are fully written in a unique staging
  directory
- os.rename() publishes the staging directory atomically
- final request directories are never rewritten
- concurrent identical creation converges
- conflicting reuse of deployment_id fails closed
- abandoned staging directories are ignored safely

This avoids a shared mutable jobs.json registry between
the API process and the Windows package-build worker.

This component does not:
- build or compile EX5 artifacts
- access MetaEditor
- access deployment secrets
- persist MT5 account fingerprints
- persist customer identity
- own mutable build status
- own build leases
- mark packages DONE
- activate customer deployments
- provision customer access
- expose an HTTP API
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import uuid


STORE_VERSION = 1

_REQUEST_FILE_NAME = "request.json"

_REQUEST_DIRECTORY_PREFIX = (
    "build-request-"
)

_STAGING_DIRECTORY_PREFIX = (
    ".staging-"
)


@dataclass(
    frozen=True,
)
class CustomerDeploymentPackageBuildRequest:
    """
    Immutable durable identity for one package build.

    deployment_id is the package-build request identity.

    bootstrap_request_id points back to the authoritative
    durable bootstrap record needed by a worker to recover
    the prepared deployment candidate.
    """

    deployment_id: str
    bootstrap_request_id: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "deployment_id",
            "bootstrap_request_id",
        ):
            object.__setattr__(
                self,
                name,
                self._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

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


class CustomerDeploymentPackageBuildRequestStore:
    """
    Durable immutable package-build request owner.

    Cross-process safety does not depend on threading.RLock.

    RLock protects only one Python store instance.
    Publication of a new request relies on an atomic,
    no-overwrite directory rename on the shared filesystem.
    """

    def __init__(
        self,
        storage_root: Path,
    ) -> None:
        if not isinstance(
            storage_root,
            Path,
        ):
            raise TypeError(
                "storage_root must be Path."
            )

        self.storage_root = (
            storage_root
        )

        self._ready = False
        self._lock = threading.RLock()

        if self.storage_root.exists():
            self._validate_storage_root()
            self._ready = True

    def initialize_empty(
        self,
    ) -> None:
        """
        Explicitly initialize durable build-request storage.

        Missing storage is never silently interpreted as an
        empty initialized commercial queue.
        """

        with self._lock:
            if self._ready:
                return

            if self.storage_root.exists():
                self._validate_storage_root()
                self._ready = True
                return

            self.storage_root.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            try:
                self.storage_root.mkdir(
                    exist_ok=False,
                )
            except FileExistsError:
                # Another process may have initialized the
                # same durable root after our existence
                # check. Validate what actually exists.
                pass

            self._validate_storage_root()
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        request: CustomerDeploymentPackageBuildRequest,
    ) -> CustomerDeploymentPackageBuildRequest:
        """
        Durably publish one immutable build request.

        Identical retry is idempotent.

        Reuse of deployment_id with a different bootstrap
        request identity fails closed.

        The final directory is never overwritten.
        """

        if not isinstance(
            request,
            CustomerDeploymentPackageBuildRequest,
        ):
            raise TypeError(
                "CustomerDeploymentPackageBuildRequestStore "
                "requires "
                "CustomerDeploymentPackageBuildRequest."
            )

        with self._lock:
            self._require_ready()
            self._validate_storage_root()

            final_directory = (
                self._request_directory(
                    deployment_id=(
                        request.deployment_id
                    )
                )
            )

            if final_directory.exists():
                return self._require_same_request(
                    request=request,
                    existing=(
                        self._read_request_directory(
                            final_directory
                        )
                    ),
                )

            staging_directory = (
                self.storage_root
                / (
                    _STAGING_DIRECTORY_PREFIX
                    + uuid.uuid4().hex
                )
            )

            staging_directory.mkdir(
                exist_ok=False,
            )

            try:
                request_path = (
                    staging_directory
                    / _REQUEST_FILE_NAME
                )

                payload = {
                    "version": STORE_VERSION,
                    "deployment_id": (
                        request.deployment_id
                    ),
                    "bootstrap_request_id": (
                        request.bootstrap_request_id
                    ),
                }

                with request_path.open(
                    "w",
                    encoding="utf-8",
                    newline="\n",
                ) as target:
                    target.write(
                        json.dumps(
                            payload,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    )

                    target.flush()
                    os.fsync(
                        target.fileno()
                    )

                try:
                    # Important:
                    #
                    # os.rename() is intentionally used
                    # instead of os.replace().
                    #
                    # The destination request directory is
                    # non-empty after successful publication,
                    # so a competing creator cannot replace
                    # the already-published request.
                    os.rename(
                        staging_directory,
                        final_directory,
                    )
                except OSError:
                    if not final_directory.exists():
                        raise

                    existing = (
                        self._read_request_directory(
                            final_directory
                        )
                    )

                    return self._require_same_request(
                        request=request,
                        existing=existing,
                    )

                return (
                    self._read_request_directory(
                        final_directory
                    )
                )

            finally:
                if staging_directory.exists():
                    shutil.rmtree(
                        staging_directory
                    )

    def get(
        self,
        *,
        deployment_id: str,
    ) -> (
        CustomerDeploymentPackageBuildRequest
        | None
    ):
        self._require_ready()

        normalized_deployment_id = (
            CustomerDeploymentPackageBuildRequest
            ._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        with self._lock:
            self._validate_storage_root()

            request_directory = (
                self._request_directory(
                    deployment_id=(
                        normalized_deployment_id
                    )
                )
            )

            if not request_directory.exists():
                return None

            return self._read_request_directory(
                request_directory
            )

    def all(
        self,
    ) -> tuple[
        CustomerDeploymentPackageBuildRequest,
        ...,
    ]:
        self._require_ready()

        with self._lock:
            return self._read_all_requests()

    def size(
        self,
    ) -> int:
        return len(
            self.all()
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer deployment package build "
                "request store is not initialized."
            )

    def _validate_storage_root(
        self,
    ) -> None:
        if self.storage_root.is_symlink():
            raise RuntimeError(
                "Package build request storage root "
                "must not be a symlink."
            )

        if not self.storage_root.is_dir():
            raise RuntimeError(
                "Package build request storage root "
                "must be a directory."
            )

        self._read_all_requests()

    def _read_all_requests(
        self,
    ) -> tuple[
        CustomerDeploymentPackageBuildRequest,
        ...,
    ]:
        requests = []

        for item in sorted(
            self.storage_root.iterdir(),
            key=lambda path: path.name,
        ):
            if item.name.startswith(
                _STAGING_DIRECTORY_PREFIX
            ):
                if (
                    item.is_symlink()
                    or not item.is_dir()
                ):
                    raise RuntimeError(
                        "Package build request staging "
                        "material is malformed."
                    )

                # A crash before atomic publication may
                # leave an unreachable staging directory.
                # It is not authoritative request state.
                continue

            if not self._is_request_directory_name(
                item.name
            ):
                raise RuntimeError(
                    "Package build request storage contains "
                    "unexpected material."
                )

            requests.append(
                self._read_request_directory(
                    item
                )
            )

        return tuple(
            requests
        )

    def _read_request_directory(
        self,
        directory: Path,
    ) -> CustomerDeploymentPackageBuildRequest:
        if directory.is_symlink():
            raise RuntimeError(
                "Package build request directory must not "
                "be a symlink."
            )

        if not directory.is_dir():
            raise RuntimeError(
                "Package build request path must be "
                "a directory."
            )

        items = tuple(
            directory.iterdir()
        )

        if len(items) != 1:
            raise RuntimeError(
                "Package build request directory must "
                "contain exactly one file."
            )

        request_path = items[
            0
        ]

        if (
            request_path.is_symlink()
            or not request_path.is_file()
            or request_path.name
            != _REQUEST_FILE_NAME
        ):
            raise RuntimeError(
                "Package build request directory must "
                "contain only request.json."
            )

        payload = json.loads(
            request_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Package build request payload must "
                "be an object."
            )

        if set(
            payload
        ) != {
            "version",
            "deployment_id",
            "bootstrap_request_id",
        }:
            raise ValueError(
                "Package build request payload has "
                "invalid fields."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported package build request "
                "store version."
            )

        request = (
            CustomerDeploymentPackageBuildRequest(
                deployment_id=(
                    payload[
                        "deployment_id"
                    ]
                ),
                bootstrap_request_id=(
                    payload[
                        "bootstrap_request_id"
                    ]
                ),
            )
        )

        expected_directory = (
            self._request_directory(
                deployment_id=(
                    request.deployment_id
                )
            )
        )

        if (
            directory.name
            != expected_directory.name
        ):
            raise ValueError(
                "Package build request directory identity "
                "does not match deployment identity."
            )

        return request

    @staticmethod
    def _require_same_request(
        *,
        request: CustomerDeploymentPackageBuildRequest,
        existing: CustomerDeploymentPackageBuildRequest,
    ) -> CustomerDeploymentPackageBuildRequest:
        if existing != request:
            raise ValueError(
                "Customer deployment package build request "
                "is already bound to a different bootstrap "
                "request."
            )

        return existing

    def _request_directory(
        self,
        *,
        deployment_id: str,
    ) -> Path:
        return (
            self.storage_root
            / (
                _REQUEST_DIRECTORY_PREFIX
                + hashlib.sha256(
                    deployment_id.encode(
                        "utf-8"
                    )
                ).hexdigest()
            )
        )

    @staticmethod
    def _is_request_directory_name(
        name: str,
    ) -> bool:
        if not name.startswith(
            _REQUEST_DIRECTORY_PREFIX
        ):
            return False

        digest = name[
            len(
                _REQUEST_DIRECTORY_PREFIX
            ):
        ]

        return (
            len(digest) == 64
            and all(
                character
                in "0123456789abcdef"
                for character in digest
            )
        )
