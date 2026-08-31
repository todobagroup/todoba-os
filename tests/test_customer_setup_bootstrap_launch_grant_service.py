"""
Owner tests for Customer Setup Bootstrap Launch Grant Service.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import inspect

import pytest

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationRedemption,
)
from backend.commercial.customer_setup_bootstrap_launch_grant_service import (
    CustomerSetupBootstrapLaunchGrantResult,
    CustomerSetupBootstrapLaunchGrantService,
    derive_customer_setup_bootstrap_launch_issuance_request_id,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchCredentialIssuanceResult,
)


NOW = datetime(
    2026,
    8,
    31,
    3,
    0,
    tzinfo=timezone.utc,
)

AUTHORIZATION_ID = "a" * 32
CUSTOMER_ID = "customer-001"
AUTHORIZATION_CODE = (
    "bootstrap-authorization-code"
)
CODE_VERIFIER = (
    "A" * 43
)
LAUNCH_ID = "b" * 32
LAUNCH_CREDENTIAL = (
    f"tdbsl.{LAUNCH_ID}."
    + ("C" * 43)
)


def _redemption(
    *,
    authorization_id=AUTHORIZATION_ID,
    customer_id=CUSTOMER_ID,
):
    return (
        CustomerSetupBootstrapAuthorizationRedemption(
            authorization_id=(
                authorization_id
            ),
            customer_id=(
                customer_id
            ),
            consumed_at=(
                NOW.isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            ),
            customer_identity=(
                CustomerIdentity(
                    customer_id=(
                        customer_id
                    )
                )
            ),
        )
    )


def _issuance(
    *,
    issuance_request_id,
    customer_id=CUSTOMER_ID,
    launch_id=LAUNCH_ID,
    launch_credential=LAUNCH_CREDENTIAL,
):
    return (
        CustomerSetupLaunchCredentialIssuanceResult(
            issuance_request_id=(
                issuance_request_id
            ),
            launch_id=(
                launch_id
            ),
            customer_id=(
                customer_id
            ),
            issued_at=(
                NOW.isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            ),
            expires_at=(
                (
                    NOW
                    + timedelta(
                        minutes=10
                    )
                )
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            ),
            launch_credential=(
                launch_credential
            ),
        )
    )


class _AuthorizationOwner:
    def __init__(
        self,
        *,
        redeem_result=None,
        redeem_error=None,
        recovery_result=None,
        recovery_error=None,
    ) -> None:
        self.redeem_result = (
            redeem_result
            if redeem_result is not None
            else _redemption()
        )
        self.redeem_error = redeem_error
        self.recovery_result = (
            recovery_result
            if recovery_result is not None
            else _redemption()
        )
        self.recovery_error = (
            recovery_error
        )
        self.redeem_calls = []
        self.recovery_calls = []

    def redeem(
        self,
        **kwargs,
    ):
        self.redeem_calls.append(
            kwargs
        )

        if self.redeem_error is not None:
            raise self.redeem_error

        return self.redeem_result

    def recover_consumed_redemption(
        self,
        **kwargs,
    ):
        self.recovery_calls.append(
            kwargs
        )

        if self.recovery_error is not None:
            raise self.recovery_error

        return self.recovery_result


class _LaunchOwner:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = []

    def issue(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        if self.error is not None:
            raise self.error

        if self.result is not None:
            return self.result

        return _issuance(
            issuance_request_id=(
                kwargs[
                    "issuance_request_id"
                ]
            ),
            customer_id=(
                kwargs[
                    "customer_id"
                ]
            ),
        )


def _service(
    *,
    authorization_owner=None,
    launch_owner=None,
):
    if authorization_owner is None:
        authorization_owner = (
            _AuthorizationOwner()
        )

    if launch_owner is None:
        launch_owner = _LaunchOwner()

    return (
        authorization_owner,
        launch_owner,
        CustomerSetupBootstrapLaunchGrantService(
            bootstrap_authorization_service=(
                authorization_owner
            ),
            launch_credential_service=(
                launch_owner
            ),
        ),
    )


def test_grant_redeems_bootstrap_and_issues_launch_credential():
    authorization_owner, launch_owner, service = (
        _service()
    )

    result = service.grant(
        authorization_code=(
            AUTHORIZATION_CODE
        ),
        code_verifier=CODE_VERIFIER,
        current_time=NOW,
    )

    expected_request_id = (
        derive_customer_setup_bootstrap_launch_issuance_request_id(
            AUTHORIZATION_ID
        )
    )

    assert isinstance(
        result,
        CustomerSetupBootstrapLaunchGrantResult,
    )
    assert (
        result.authorization_id
        == AUTHORIZATION_ID
    )
    assert (
        result.customer_id
        == CUSTOMER_ID
    )
    assert (
        result.launch_issuance_request_id
        == expected_request_id
    )
    assert result.launch_id == LAUNCH_ID
    assert (
        result.setup_launch_credential
        == LAUNCH_CREDENTIAL
    )

    assert len(
        authorization_owner.redeem_calls
    ) == 1
    assert (
        authorization_owner.recovery_calls
        == []
    )

    assert len(
        launch_owner.calls
    ) == 1
    assert (
        launch_owner.calls[0][
            "issuance_request_id"
        ]
        == expected_request_id
    )
    assert (
        launch_owner.calls[0][
            "customer_id"
        ]
        == CUSTOMER_ID
    )


def test_grant_never_accepts_customer_id_from_caller():
    parameters = (
        inspect.signature(
            CustomerSetupBootstrapLaunchGrantService
            .grant
        )
        .parameters
    )

    assert set(
        parameters
    ) == {
        "self",
        "authorization_code",
        "code_verifier",
        "current_time",
    }

    assert "customer_id" not in parameters


def test_consumed_authorization_retry_uses_dedicated_recovery():
    authorization_owner = (
        _AuthorizationOwner(
            redeem_error=ValueError(
                "Consumed bootstrap authorization "
                "cannot be redeemed."
            )
        )
    )

    (
        authorization_owner,
        launch_owner,
        service,
    ) = _service(
        authorization_owner=(
            authorization_owner
        )
    )

    result = service.grant(
        authorization_code=(
            AUTHORIZATION_CODE
        ),
        code_verifier=CODE_VERIFIER,
        current_time=NOW,
    )

    assert (
        result.customer_id
        == CUSTOMER_ID
    )
    assert len(
        authorization_owner.redeem_calls
    ) == 1
    assert len(
        authorization_owner.recovery_calls
    ) == 1
    assert len(
        launch_owner.calls
    ) == 1


def test_unrecoverable_redemption_preserves_original_failure():
    authorization_owner = (
        _AuthorizationOwner(
            redeem_error=ValueError(
                "Invalid bootstrap authorization."
            ),
            recovery_error=ValueError(
                "Recovery not available."
            ),
        )
    )

    _, launch_owner, service = (
        _service(
            authorization_owner=(
                authorization_owner
            )
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Invalid bootstrap authorization"
        ),
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )

    assert launch_owner.calls == []


def test_non_value_redemption_failure_is_not_recovered():
    authorization_owner = (
        _AuthorizationOwner(
            redeem_error=RuntimeError(
                "authorization store unavailable"
            )
        )
    )

    _, launch_owner, service = (
        _service(
            authorization_owner=(
                authorization_owner
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="store unavailable",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )

    assert (
        authorization_owner.recovery_calls
        == []
    )
    assert launch_owner.calls == []


def test_downstream_failure_can_retry_through_consumed_recovery():
    class CrashRecoveryAuthorizationOwner:
        def __init__(
            self,
        ) -> None:
            self.redeemed = False
            self.recoveries = 0

        def redeem(
            self,
            **kwargs,
        ):
            del kwargs

            if self.redeemed:
                raise ValueError(
                    "Consumed bootstrap authorization "
                    "cannot be redeemed."
                )

            self.redeemed = True
            return _redemption()

        def recover_consumed_redemption(
            self,
            **kwargs,
        ):
            del kwargs
            self.recoveries += 1
            return _redemption()

    class CrashRecoveryLaunchOwner:
        def __init__(
            self,
        ) -> None:
            self.calls = []

        def issue(
            self,
            **kwargs,
        ):
            self.calls.append(
                kwargs
            )

            if len(
                self.calls
            ) == 1:
                raise RuntimeError(
                    "simulated downstream interruption"
                )

            return _issuance(
                issuance_request_id=(
                    kwargs[
                        "issuance_request_id"
                    ]
                ),
                customer_id=(
                    kwargs[
                        "customer_id"
                    ]
                ),
                launch_credential=(
                    f"tdbsl.{LAUNCH_ID}."
                    + ("D" * 43)
                ),
            )

    authorization_owner = (
        CrashRecoveryAuthorizationOwner()
    )
    launch_owner = (
        CrashRecoveryLaunchOwner()
    )

    service = (
        CustomerSetupBootstrapLaunchGrantService(
            bootstrap_authorization_service=(
                authorization_owner
            ),
            launch_credential_service=(
                launch_owner
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="downstream interruption",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )

    recovered = service.grant(
        authorization_code=(
            AUTHORIZATION_CODE
        ),
        code_verifier=CODE_VERIFIER,
        current_time=(
            NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    assert (
        authorization_owner.recoveries
        == 1
    )
    assert len(
        launch_owner.calls
    ) == 2
    assert (
        launch_owner.calls[0][
            "issuance_request_id"
        ]
        == launch_owner.calls[1][
            "issuance_request_id"
        ]
    )
    assert (
        recovered.launch_issuance_request_id
        == launch_owner.calls[1][
            "issuance_request_id"
        ]
    )


def test_issuance_request_identity_is_deterministic_and_namespaced():
    first = (
        derive_customer_setup_bootstrap_launch_issuance_request_id(
            AUTHORIZATION_ID
        )
    )
    second = (
        derive_customer_setup_bootstrap_launch_issuance_request_id(
            AUTHORIZATION_ID
        )
    )
    other = (
        derive_customer_setup_bootstrap_launch_issuance_request_id(
            "c" * 32
        )
    )

    assert first == second
    assert first != other
    assert first.startswith(
        "bootstrap-launch-"
    )
    assert (
        AUTHORIZATION_ID
        not in first
    )


def test_invalid_current_time_is_rejected_before_redemption():
    authorization_owner, launch_owner, service = (
        _service()
    )

    with pytest.raises(
        TypeError,
        match="current_time must be datetime",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time="not-a-datetime",
        )

    assert (
        authorization_owner.redeem_calls
        == []
    )
    assert launch_owner.calls == []


def test_naive_current_time_is_rejected_before_redemption():
    authorization_owner, launch_owner, service = (
        _service()
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=(
                datetime(
                    2026,
                    8,
                    31,
                    3,
                    0,
                )
            ),
        )

    assert (
        authorization_owner.redeem_calls
        == []
    )
    assert launch_owner.calls == []


def test_invalid_redemption_result_fails_closed():
    authorization_owner = (
        _AuthorizationOwner(
            redeem_result=object()
        )
    )

    _, launch_owner, service = (
        _service(
            authorization_owner=(
                authorization_owner
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid redemption",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )

    assert launch_owner.calls == []


def test_invalid_recovered_redemption_result_fails_closed():
    authorization_owner = (
        _AuthorizationOwner(
            redeem_error=ValueError(
                "Consumed bootstrap authorization"
            ),
            recovery_result=object(),
        )
    )

    _, launch_owner, service = (
        _service(
            authorization_owner=(
                authorization_owner
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="invalid redemption",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )

    assert launch_owner.calls == []


def test_invalid_launch_issuance_result_fails_closed():
    launch_owner = (
        _LaunchOwner(
            result=object()
        )
    )

    _, _, service = _service(
        launch_owner=launch_owner
    )

    with pytest.raises(
        RuntimeError,
        match="invalid issuance result",
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )


def test_launch_issuance_request_identity_must_converge():
    wrong = _issuance(
        issuance_request_id=(
            "wrong-request-id"
        )
    )

    _, _, service = _service(
        launch_owner=(
            _LaunchOwner(
                result=wrong
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "issuance request identity "
            "did not converge"
        ),
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )


def test_launch_customer_identity_must_converge():
    expected_request_id = (
        derive_customer_setup_bootstrap_launch_issuance_request_id(
            AUTHORIZATION_ID
        )
    )

    wrong = _issuance(
        issuance_request_id=(
            expected_request_id
        ),
        customer_id="customer-002",
    )

    _, _, service = _service(
        launch_owner=(
            _LaunchOwner(
                result=wrong
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "customer identity did not converge"
        ),
    ):
        service.grant(
            authorization_code=(
                AUTHORIZATION_CODE
            ),
            code_verifier=CODE_VERIFIER,
            current_time=NOW,
        )


def test_grant_result_repr_redacts_launch_credential():
    _, _, service = _service()

    result = service.grant(
        authorization_code=(
            AUTHORIZATION_CODE
        ),
        code_verifier=CODE_VERIFIER,
        current_time=NOW,
    )

    rendered = repr(
        result
    )

    assert (
        LAUNCH_CREDENTIAL
        not in rendered
    )
    assert (
        "setup_launch_credential=<redacted>"
        in rendered
    )


@pytest.mark.parametrize(
    (
        "authorization_owner",
        "launch_owner",
        "expected",
    ),
    [
        (
            object(),
            _LaunchOwner(),
            "redeem",
        ),
        (
            type(
                "RedeemOnly",
                (),
                {
                    "redeem": (
                        lambda self, **kwargs: None
                    )
                },
            )(),
            _LaunchOwner(),
            "recover_consumed_redemption",
        ),
        (
            _AuthorizationOwner(),
            object(),
            "issue",
        ),
    ],
)
def test_constructor_requires_authoritative_owner_methods(
    authorization_owner,
    launch_owner,
    expected,
):
    with pytest.raises(
        TypeError,
        match=expected,
    ):
        CustomerSetupBootstrapLaunchGrantService(
            bootstrap_authorization_service=(
                authorization_owner
            ),
            launch_credential_service=(
                launch_owner
            ),
        )