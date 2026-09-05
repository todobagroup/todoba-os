"""
Customer-side hidden Activation Code bootstrap bridge.

Flow:

    Activation Code
        -> public PKCE code_challenge_s256 from existing acquisition
        -> CustomerSetupAccessCodeHttpClient.exchange()
        -> short-lived internal authorization_code
        -> CustomerSetupBootstrapAcquisition.launch()

Security boundaries:
- the private PKCE verifier remains exclusively inside
  CustomerSetupBootstrapAcquisition
- the internal authorization code is never returned or persisted
- customer, deployment, activation-record, payment, entitlement,
  package, and MT5 authority are not owned here
- this owner only sequences two already-authoritative customer-side
  owners
"""

from __future__ import annotations

from backend.commercial.customer_setup_access_code_http_client import (
    CustomerSetupAccessCodeHttpClient,
)
from backend.commercial.customer_setup_bootstrap_acquisition import (
    CustomerSetupBootstrapAcquisition,
)


def _require_activation_code(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "activation_code must be str."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            "activation_code must not be empty."
        )

    if normalized != value:
        raise ValueError(
            "activation_code must be normalized."
        )

    return normalized


class CustomerSetupAccessCodeBootstrapBridge:
    """
    Hidden customer-side sequencing boundary for commercial Setup start.
    """

    __slots__ = (
        "_access_code_client",
        "_acquisition",
    )

    def __init__(
        self,
        *,
        access_code_client: CustomerSetupAccessCodeHttpClient,
        acquisition: CustomerSetupBootstrapAcquisition,
    ) -> None:
        if not isinstance(
            access_code_client,
            CustomerSetupAccessCodeHttpClient,
        ):
            raise TypeError(
                "access_code_client must be "
                "CustomerSetupAccessCodeHttpClient."
            )

        if not isinstance(
            acquisition,
            CustomerSetupBootstrapAcquisition,
        ):
            raise TypeError(
                "acquisition must be "
                "CustomerSetupBootstrapAcquisition."
            )

        self._access_code_client = (
            access_code_client
        )

        self._acquisition = (
            acquisition
        )

    def launch(
        self,
        *,
        activation_code: str,
    ) -> None:
        normalized_activation_code = (
            _require_activation_code(
                activation_code
            )
        )

        result = (
            self._access_code_client.exchange(
                activation_code=(
                    normalized_activation_code
                ),
                code_challenge_s256=(
                    self._acquisition
                    .code_challenge_s256
                ),
            )
        )

        self._acquisition.launch(
            authorization_code=(
                result.authorization_code
            ),
        )