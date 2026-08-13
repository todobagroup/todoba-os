"""
TODOBA Executor Authenticator

Owns authentication of trusted TODOBA Executors
across the Cloud mission injection boundary.

Trusted Agent authentication belongs to a separate
capability.
"""

from hmac import compare_digest


class ExecutorAuthenticator:
    """
    Authenticate one TODOBA Executor identity using
    a shared secret supplied through HTTP headers.
    """

    def __init__(
        self,
        executor_id: str,
        executor_secret: str,
    ) -> None:
        normalized_executor_id = executor_id.strip()
        normalized_executor_secret = (
            executor_secret.strip()
        )

        if not normalized_executor_id:
            raise ValueError(
                "executor_id is required."
            )

        if not normalized_executor_secret:
            raise ValueError(
                "executor_secret is required."
            )

        self._executor_id = normalized_executor_id
        self._executor_secret = (
            normalized_executor_secret
        )

    def authenticate(
        self,
        executor_id: str | None,
        authorization: str | None,
    ) -> bool:
        if executor_id is None:
            return False

        if authorization is None:
            return False

        supplied_executor_id = executor_id.strip()
        supplied_authorization = (
            authorization.strip()
        )

        bearer_prefix = "Bearer "

        if not supplied_authorization.startswith(
            bearer_prefix
        ):
            return False

        supplied_secret = supplied_authorization[
            len(bearer_prefix):
        ].strip()

        if not supplied_secret:
            return False

        executor_matches = compare_digest(
            supplied_executor_id,
            self._executor_id,
        )

        secret_matches = compare_digest(
            supplied_secret,
            self._executor_secret,
        )

        return executor_matches and secret_matches