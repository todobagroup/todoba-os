"""
TODOBA customer-side setup bootstrap acquisition.

This owner exists only inside the customer Setup process.

Flow:
1. Generate one PKCE code_verifier locally with a CSPRNG.
2. Derive the RFC 7636 S256 code_challenge locally.
3. Expose only code_challenge_s256 to the caller.
4. Receive the one-time authorization_code later.
5. Pass authorization_code + the private in-memory verifier
   into CustomerSetupBootstrapCoordinator.

Security boundaries:
- code_verifier is never public
- code_verifier is never persisted
- code_verifier is never logged or represented
- operator/server issuance receives only the challenge
- this owner has no customer/deployment/payment authority
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import re
import secrets

from backend.commercial.customer_setup_bootstrap_coordinator import (
    CustomerSetupBootstrapCoordinator,
)


_PKCE_CODE_VERIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9\-._~]{43,128}$"
)

_PKCE_CODE_CHALLENGE_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{43}$"
)


def _generate_code_verifier() -> str:
    """
    Generate a PKCE verifier using OS-backed cryptographic randomness.

    token_urlsafe(32) yields 32 random bytes encoded as an
    unpadded URL-safe Base64 string, which is 43 characters and
    therefore satisfies RFC 7636's 43-128 character requirement.
    """

    verifier = secrets.token_urlsafe(
        32
    )

    return _normalize_code_verifier(
        verifier
    )


def _derive_pkce_s256_code_challenge(
    code_verifier: str,
) -> str:
    """
    Derive RFC 7636 S256 challenge:
        BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))
    with Base64 padding removed.
    """

    normalized = _normalize_code_verifier(
        code_verifier
    )

    digest = hashlib.sha256(
        normalized.encode(
            "ascii"
        )
    ).digest()

    challenge = (
        base64.urlsafe_b64encode(
            digest
        )
        .decode(
            "ascii"
        )
        .rstrip("=")
    )

    if (
        _PKCE_CODE_CHALLENGE_PATTERN.fullmatch(
            challenge
        )
        is None
    ):
        raise RuntimeError(
            "Derived PKCE S256 challenge is invalid."
        )

    return challenge


class CustomerSetupBootstrapAcquisition:
    """
    Customer-side owner of the ephemeral PKCE verifier.

    The verifier is intentionally private. The only bootstrap
    material exposed before authorization is code_challenge_s256.
    """

    __slots__ = (
        "_setup_base_url",
        "_mt5_module",
        "_roaming_appdata_path",
        "_code_verifier",
        "_code_challenge_s256",
    )

    def __init__(
        self,
        *,
        setup_base_url: str,
        mt5_module,
        roaming_appdata_path: Path,
    ) -> None:
        self._setup_base_url = (
            _normalize_required_string(
                setup_base_url,
                name="setup_base_url",
            )
        )

        if mt5_module is None:
            raise TypeError(
                "mt5_module must not be None."
            )

        self._mt5_module = mt5_module

        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        self._roaming_appdata_path = (
            roaming_appdata_path
        )

        code_verifier = (
            _generate_code_verifier()
        )

        self._code_verifier = (
            code_verifier
        )

        self._code_challenge_s256 = (
            _derive_pkce_s256_code_challenge(
                code_verifier
            )
        )

    @property
    def code_challenge_s256(
        self,
    ) -> str:
        return self._code_challenge_s256

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupBootstrapAcquisition("
            f"setup_base_url={self._setup_base_url!r}, "
            "code_verifier=<redacted>, "
            f"code_challenge_s256="
            f"{self._code_challenge_s256!r})"
        )

    def launch(
        self,
        *,
        authorization_code: str,
    ) -> None:
        normalized_authorization_code = (
            _normalize_required_string(
                authorization_code,
                name="authorization_code",
            )
        )

        coordinator = (
            CustomerSetupBootstrapCoordinator(
                setup_base_url=(
                    self._setup_base_url
                ),
                authorization_code=(
                    normalized_authorization_code
                ),
                code_verifier=(
                    self._code_verifier
                ),
                mt5_module=(
                    self._mt5_module
                ),
                roaming_appdata_path=(
                    self._roaming_appdata_path
                ),
            )
        )

        coordinator.run()


def _normalize_required_string(
    value,
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
            f"{name} must not be empty."
        )

    return normalized


def _normalize_code_verifier(
    value,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "code_verifier must be str."
        )

    if (
        _PKCE_CODE_VERIFIER_PATTERN.fullmatch(
            value
        )
        is None
    ):
        raise ValueError(
            "code_verifier is invalid."
        )

    return value
