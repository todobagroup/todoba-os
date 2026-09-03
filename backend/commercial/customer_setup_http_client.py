"""
TODOBA Customer Setup HTTP Client

Owns the customer-side HTTP transport for the authenticated
TODOBA Setup provisioning and package-delivery boundaries.

Transport flow:

    setup_base_url
    setup_handoff_credential
        -> POST /customer/setup/provision
        -> 202 build_pending
        -> 200 ready + authoritative artifact metadata

    ready
        -> GET /customer/setup/package
        -> raw TODOBA_Trusted_Agent.ex5 bytes

Safety rules:
- setup handoff credential is never returned or persisted
- credential is redacted from repr()
- only account_fingerprint is sent to provisioning
- provisioning response exposes only safe status/hash/size
- package response must be HTTP 200 and application/octet-stream
- unexpected success statuses fail closed
- this owner does not poll, sleep, discover MT5, or install EX5

This component does not:
- own registration, activation, entitlement, or deployment state
- discover or select MetaTrader
- install files
- build or compile trading source code
- persist commercial state
- expose FastAPI routes
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Literal

import httpx


_PROVISION_PATH = "/customer/setup/provision"
_CONTINUE_PATH = "/customer/setup/continue"
_PACKAGE_PATH = "/customer/setup/package"
_PACKAGE_MEDIA_TYPE = "application/octet-stream"


@dataclass(
    frozen=True,
)
class CustomerSetupProvisioningTransportResult:
    """
    Customer-safe provisioning response.

    build_pending contains no artifact metadata.
    ready contains authoritative SHA-256 and artifact size.
    """

    status: Literal[
        "build_pending",
        "ready",
    ]
    continuation_credential: str | None = field(
        default=None,
        repr=False,
    )
    artifact_sha256: str | None = None
    artifact_size_bytes: int | None = None

    def __post_init__(
        self,
    ) -> None:
        if self.status not in (
            "build_pending",
            "ready",
        ):
            raise ValueError(
                "Unsupported customer setup provisioning status."
            )

        if self.status == "build_pending":
            if (
                self.artifact_sha256 is not None
                or self.artifact_size_bytes is not None
            ):
                raise ValueError(
                    "build_pending must not contain artifact metadata."
                )

            continuation_credential = (
                self.continuation_credential
            )

            if continuation_credential is not None:
                if (
                    not isinstance(
                        continuation_credential,
                        str,
                    )
                    or not continuation_credential
                    or continuation_credential.strip()
                    != continuation_credential
                    or not continuation_credential.startswith(
                        "tdbsc1."
                    )
                ):
                    raise ValueError(
                        "build_pending continuation_credential "
                        "must be a normalized TODOBA build "
                        "continuation credential."
                    )

            return

        if self.continuation_credential is not None:
            raise ValueError(
                "ready must not contain continuation_credential."
            )

        digest = self.artifact_sha256

        if not isinstance(
            digest,
            str,
        ):
            raise ValueError(
                "ready requires artifact_sha256."
            )

        normalized_digest = digest.strip().lower()

        if (
            len(normalized_digest) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in normalized_digest
            )
        ):
            raise ValueError(
                "ready requires valid artifact_sha256."
            )

        object.__setattr__(
            self,
            "artifact_sha256",
            normalized_digest,
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
                "ready requires positive artifact_size_bytes."
            )


class CustomerSetupHttpClient:
    """
    Synchronous authenticated TODOBA Setup transport.
    """

    def __init__(
        self,
        *,
        setup_base_url: str,
        setup_handoff_credential: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        normalized_url = _normalize_required_string(
            setup_base_url,
            name="setup_base_url",
        ).rstrip("/")

        normalized_credential = (
            _normalize_required_string(
                setup_handoff_credential,
                name="setup_handoff_credential",
            )
        )

        if (
            not isinstance(
                timeout_seconds,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                timeout_seconds,
                bool,
            )
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self._setup_base_url = normalized_url
        self._setup_handoff_credential = (
            normalized_credential
        )
        self._timeout_seconds = float(
            timeout_seconds
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupHttpClient("
            f"setup_base_url="
            f"{self._setup_base_url!r}, "
            "setup_handoff_credential=<redacted>, "
            f"timeout_seconds="
            f"{self._timeout_seconds!r})"
        )

    def provision(
        self,
        *,
        account_fingerprint: str,
    ) -> CustomerSetupProvisioningTransportResult:
        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        response = httpx.post(
            (
                f"{self._setup_base_url}"
                f"{_PROVISION_PATH}"
            ),
            headers=self._authentication_headers(),
            json={
                "account_fingerprint": (
                    normalized_account_fingerprint
                ),
            },
            timeout=self._timeout_seconds,
        )

        self._require_expected_status(
            response,
            expected_statuses=(
                200,
                202,
            ),
        )

        payload = self._response_json_object(
            response
        )

        if response.status_code == 202:
            if (
                payload.get("status")
                != "build_pending"
                or set(payload)
                not in (
                    {
                        "status",
                    },
                    {
                        "status",
                        "continuation_credential",
                    },
                    {
                        "status",
                        "continuation_credential",
                        "continuation_expires_at",
                    },
                )
            ):
                raise RuntimeError(
                    "Invalid build_pending customer setup "
                    "provisioning response."
                )

            if (
                "continuation_expires_at"
                in payload
            ):
                continuation_expires_at = (
                    payload[
                        "continuation_expires_at"
                    ]
                )

                if (
                    not isinstance(
                        payload.get(
                            "continuation_credential"
                        ),
                        str,
                    )
                    or not isinstance(
                        continuation_expires_at,
                        str,
                    )
                    or not continuation_expires_at
                    or continuation_expires_at.strip()
                    != continuation_expires_at
                ):
                    raise RuntimeError(
                        "Invalid build_pending customer setup "
                        "continuation expiry."
                    )

            try:
                return (
                    CustomerSetupProvisioningTransportResult(
                        status="build_pending",
                        continuation_credential=(
                            payload.get(
                                "continuation_credential"
                            )
                        ),
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise RuntimeError(
                    "Invalid build_pending customer setup "
                    "continuation credential."
                ) from exc

        if set(
            payload
        ) != {
            "status",
            "artifact_sha256",
            "artifact_size_bytes",
        }:
            raise RuntimeError(
                "Invalid ready customer setup provisioning "
                "response shape."
            )

        if payload.get(
            "status"
        ) != "ready":
            raise RuntimeError(
                "HTTP 200 customer setup provisioning "
                "response must be ready."
            )

        try:
            return (
                CustomerSetupProvisioningTransportResult(
                    status="ready",
                    artifact_sha256=(
                        payload.get(
                            "artifact_sha256"
                        )
                    ),
                    artifact_size_bytes=(
                        payload.get(
                            "artifact_size_bytes"
                        )
                    ),
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Invalid ready customer setup provisioning "
                "metadata."
            ) from exc

    def continue_provisioning(
        self,
        *,
        continuation_credential: str,
    ) -> CustomerSetupProvisioningTransportResult:
        normalized_continuation_credential = (
            _normalize_required_string(
                continuation_credential,
                name="continuation_credential",
            )
        )

        if (
            normalized_continuation_credential
            != continuation_credential
            or not normalized_continuation_credential.startswith(
                "tdbsc1."
            )
        ):
            raise ValueError(
                "continuation_credential must be a normalized "
                "TODOBA build continuation credential."
            )

        response = httpx.post(
            (
                f"{self._setup_base_url}"
                f"{_CONTINUE_PATH}"
            ),
            headers={
                "Authorization": (
                    "Bearer "
                    f"{normalized_continuation_credential}"
                ),
            },
            timeout=self._timeout_seconds,
        )

        self._require_expected_status(
            response,
            expected_statuses=(
                200,
                202,
            ),
        )

        payload = self._response_json_object(
            response
        )

        if response.status_code == 202:
            if (
                payload.get("status")
                != "build_pending"
                or set(payload)
                not in (
                    {
                        "status",
                    },
                    {
                        "status",
                        "continuation_credential",
                    },
                )
            ):
                raise RuntimeError(
                    "Invalid build_pending customer setup "
                    "continuation response."
                )

            returned_credential = payload.get(
                "continuation_credential"
            )

            if (
                returned_credential is not None
                and returned_credential
                != normalized_continuation_credential
            ):
                raise RuntimeError(
                    "Customer setup continuation response "
                    "changed continuation credential."
                )

            try:
                return (
                    CustomerSetupProvisioningTransportResult(
                        status="build_pending",
                        continuation_credential=(
                            returned_credential
                        ),
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise RuntimeError(
                    "Invalid build_pending customer setup "
                    "continuation credential."
                ) from exc

        if set(
            payload
        ) != {
            "status",
            "artifact_sha256",
            "artifact_size_bytes",
        }:
            raise RuntimeError(
                "Invalid ready customer setup continuation "
                "response shape."
            )

        if payload.get(
            "status"
        ) != "ready":
            raise RuntimeError(
                "HTTP 200 customer setup continuation "
                "response must be ready."
            )

        try:
            return (
                CustomerSetupProvisioningTransportResult(
                    status="ready",
                    artifact_sha256=(
                        payload.get(
                            "artifact_sha256"
                        )
                    ),
                    artifact_size_bytes=(
                        payload.get(
                            "artifact_size_bytes"
                        )
                    ),
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Invalid ready customer setup continuation "
                "metadata."
            ) from exc

    def download_package(
        self,
        *,
        continuation_credential: str | None = None,
    ) -> bytes:
        if continuation_credential is None:
            authentication_headers = (
                self._authentication_headers()
            )
        else:
            normalized_continuation_credential = (
                _normalize_required_string(
                    continuation_credential,
                    name="continuation_credential",
                )
            )

            if (
                normalized_continuation_credential
                != continuation_credential
                or not normalized_continuation_credential.startswith(
                    "tdbsc1."
                )
            ):
                raise ValueError(
                    "continuation_credential must be a normalized "
                    "TODOBA build continuation credential."
                )

            authentication_headers = {
                "Authorization": (
                    "Bearer "
                    f"{normalized_continuation_credential}"
                ),
            }
        response = httpx.get(
            (
                f"{self._setup_base_url}"
                f"{_PACKAGE_PATH}"
            ),
            headers=authentication_headers,
            timeout=self._timeout_seconds,
        )

        self._require_expected_status(
            response,
            expected_statuses=(
                200,
            ),
        )

        content_type = (
            response.headers.get(
                "content-type",
                "",
            )
            .split(
                ";",
                1,
            )[0]
            .strip()
            .lower()
        )

        if content_type != _PACKAGE_MEDIA_TYPE:
            raise RuntimeError(
                "Customer setup package response has invalid "
                "content type."
            )

        content = response.content

        if not isinstance(
            content,
            bytes,
        ):
            raise RuntimeError(
                "Customer setup package response is not bytes."
            )

        if len(
            content
        ) == 0:
            raise RuntimeError(
                "Customer setup package response is empty."
            )

        return content

    def _authentication_headers(
        self,
    ) -> dict[str, str]:
        return {
            "Authorization": (
                "Bearer "
                f"{self._setup_handoff_credential}"
            ),
        }

    @staticmethod
    def _require_expected_status(
        response: httpx.Response,
        *,
        expected_statuses: tuple[int, ...],
    ) -> None:
        if response.status_code in expected_statuses:
            return

        response.raise_for_status()

        raise RuntimeError(
            "Unexpected successful customer setup HTTP status."
        )

    @staticmethod
    def _response_json_object(
        response: httpx.Response,
    ) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Customer setup response is not valid JSON."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Customer setup response JSON must be an object."
            )

        return payload


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