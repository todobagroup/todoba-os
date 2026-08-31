"""
TODOBA Customer Setup Bootstrap Coordinator

Customer-side composition boundary between the trusted
bootstrap exchange transport and the existing customer
setup launcher.

Flow:

    setup_base_url
    + authorization_code
    + code_verifier
        -> CustomerSetupBootstrapHttpClient.exchange()
        -> setup_launch_credential
        -> CustomerSetupBootstrapInput
        -> CustomerSetupLauncher.run()

Ownership rules:
- bootstrap exchange transport remains owned by the bootstrap
  HTTP client
- launcher composition remains owned by CustomerSetupLauncher
- this coordinator does not generate PKCE material
- this coordinator does not issue bootstrap authorizations
- this coordinator does not grant launch credentials
- this coordinator does not authenticate commercial identity
- this coordinator does not persist secrets
- this coordinator does not read environment or runtime config
- bootstrap exchange must succeed before launcher composition
"""

from __future__ import annotations

from backend.commercial.customer_setup_bootstrap_http_client import (
    CustomerSetupBootstrapHttpClient,
    CustomerSetupBootstrapTransportResult,
)
from backend.commercial.customer_setup_bootstrap_input import (
    CustomerSetupBootstrapInput,
)
from backend.commercial.customer_setup_launcher import (
    CustomerSetupLauncher,
)


class CustomerSetupBootstrapCoordinator:
    """
    Compose trusted bootstrap exchange into the existing
    customer setup launcher.
    """

    __slots__ = (
        "_setup_base_url",
        "_authorization_code",
        "_code_verifier",
        "_mt5_module",
        "_roaming_appdata_path",
    )

    def __init__(
        self,
        *,
        setup_base_url: str,
        authorization_code: str,
        code_verifier: str,
        mt5_module,
        roaming_appdata_path,
    ) -> None:
        self._setup_base_url = (
            setup_base_url
        )
        self._authorization_code = (
            authorization_code
        )
        self._code_verifier = (
            code_verifier
        )
        self._mt5_module = (
            mt5_module
        )
        self._roaming_appdata_path = (
            roaming_appdata_path
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupBootstrapCoordinator("
            f"setup_base_url="
            f"{self._setup_base_url!r}, "
            "authorization_code=<redacted>, "
            "code_verifier=<redacted>, "
            f"roaming_appdata_path="
            f"{self._roaming_appdata_path!r})"
        )

    def run(
        self,
    ) -> None:
        """
        Exchange bootstrap material, then run the existing
        customer setup launcher.
        """

        bootstrap_client = (
            CustomerSetupBootstrapHttpClient(
                setup_base_url=(
                    self._setup_base_url
                ),
                authorization_code=(
                    self._authorization_code
                ),
                code_verifier=(
                    self._code_verifier
                ),
            )
        )

        bootstrap_result = (
            bootstrap_client.exchange()
        )

        if not isinstance(
            bootstrap_result,
            CustomerSetupBootstrapTransportResult,
        ):
            raise RuntimeError(
                "Customer setup bootstrap exchange returned "
                "invalid result."
            )

        bootstrap_input = (
            CustomerSetupBootstrapInput(
                setup_base_url=(
                    self._setup_base_url
                ),
                setup_launch_credential=(
                    bootstrap_result
                    .setup_launch_credential
                ),
            )
        )

        launcher = CustomerSetupLauncher(
            bootstrap_input=bootstrap_input,
            mt5_module=self._mt5_module,
            roaming_appdata_path=(
                self._roaming_appdata_path
            ),
        )

        launcher.run()
