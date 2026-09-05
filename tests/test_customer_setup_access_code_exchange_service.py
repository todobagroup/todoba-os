import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.commercial.customer_setup_access_code_exchange_service import (
    CustomerSetupAccessCodeExchangeResult,
    CustomerSetupAccessCodeExchangeService,
)
from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeAuthorization,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationIssuance,
)


_ACTIVATION_CODE = (
    "tdbsa."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

_CODE_CHALLENGE = "B" * 43
_CUSTOMER_ID = "customer-001"
_SETUP_ACTIVATION_ID = "setup-activation-001"

_NOW = datetime(
    2026,
    9,
    4,
    12,
    0,
    tzinfo=timezone.utc,
)

_EXPIRES_AT = (
    _NOW
    + timedelta(
        minutes=10
    )
)

_INTERNAL_AUTHORIZATION_CODE = (
    "tdbba."
    + ("2" * 32)
    + "."
    + ("C" * 43)
)


def _build_service(
    *,
    access_calls=None,
    issue_calls=None,
    clock=None,
):
    if access_calls is None:
        access_calls = []

    if issue_calls is None:
        issue_calls = []

    def authorize_access_code(
        **kwargs,
    ):
        access_calls.append(
            kwargs
        )

        return CustomerSetupAccessCodeAuthorization(
            setup_activation_id=(
                _SETUP_ACTIVATION_ID
            ),
            customer_id=_CUSTOMER_ID,
        )

    def issue_bootstrap_authorization(
        **kwargs,
    ):
        issue_calls.append(
            kwargs
        )

        return CustomerSetupBootstrapAuthorizationIssuance(
            authorization_request_id=(
                kwargs[
                    "authorization_request_id"
                ]
            ),
            authorization_id=(
                "bootstrap-authorization-001"
            ),
            customer_id=(
                kwargs[
                    "customer_id"
                ]
            ),
            issued_at=(
                kwargs[
                    "current_time"
                ]
            ),
            expires_at=_EXPIRES_AT,
            authorization_code=(
                _INTERNAL_AUTHORIZATION_CODE
            ),
        )

    return (
        CustomerSetupAccessCodeExchangeService(
            authorize_access_code=(
                authorize_access_code
            ),
            issue_bootstrap_authorization=(
                issue_bootstrap_authorization
            ),
            clock=(
                clock
                if clock is not None
                else lambda: _NOW
            ),
        ),
        access_calls,
        issue_calls,
    )


def test_exchange_uses_activation_code_as_only_bearer_authority(
) -> None:
    service, access_calls, issue_calls = (
        _build_service()
    )

    result = service.exchange(
        activation_code=(
            _ACTIVATION_CODE
        ),
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    assert access_calls == [
        {
            "activation_code": (
                _ACTIVATION_CODE
            )
        }
    ]

    assert len(
        issue_calls
    ) == 1

    call = issue_calls[0]

    assert call[
        "customer_id"
    ] == _CUSTOMER_ID

    assert call[
        "code_challenge_s256"
    ] == _CODE_CHALLENGE

    assert call[
        "current_time"
    ] == _NOW

    assert (
        result.authorization_code
        == _INTERNAL_AUTHORIZATION_CODE
    )

    assert result.expires_at == _EXPIRES_AT


def test_exchange_public_surface_has_no_customer_or_activation_identity(
) -> None:
    parameters = inspect.signature(
        CustomerSetupAccessCodeExchangeService.exchange
    ).parameters

    assert set(
        parameters
    ) == {
        "self",
        "activation_code",
        "code_challenge_s256",
    }

    assert "customer_id" not in parameters
    assert "setup_activation_id" not in parameters


def test_same_activation_code_and_challenge_derive_same_request_identity(
) -> None:
    service, _, issue_calls = (
        _build_service()
    )

    service.exchange(
        activation_code=_ACTIVATION_CODE,
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    service.exchange(
        activation_code=_ACTIVATION_CODE,
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    assert (
        issue_calls[0][
            "authorization_request_id"
        ]
        == issue_calls[1][
            "authorization_request_id"
        ]
    )

    request_id = issue_calls[0][
        "authorization_request_id"
    ]

    assert request_id.startswith(
        "setup-access-exchange-"
    )

    assert _ACTIVATION_CODE not in request_id


def test_different_pkce_challenge_derives_different_request_identity(
) -> None:
    service, _, issue_calls = (
        _build_service()
    )

    service.exchange(
        activation_code=_ACTIVATION_CODE,
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    service.exchange(
        activation_code=_ACTIVATION_CODE,
        code_challenge_s256=(
            "D" * 43
        ),
    )

    assert (
        issue_calls[0][
            "authorization_request_id"
        ]
        != issue_calls[1][
            "authorization_request_id"
        ]
    )


def test_customer_identity_is_derived_from_access_authorization(
) -> None:
    observed = []

    def authorize_access_code(
        **kwargs,
    ):
        return CustomerSetupAccessCodeAuthorization(
            setup_activation_id=(
                "setup-activation-authoritative"
            ),
            customer_id=(
                "customer-authoritative"
            ),
        )

    def issue_bootstrap_authorization(
        **kwargs,
    ):
        observed.append(
            kwargs
        )

        return CustomerSetupBootstrapAuthorizationIssuance(
            authorization_request_id=(
                kwargs[
                    "authorization_request_id"
                ]
            ),
            authorization_id="authorization-001",
            customer_id=(
                "customer-authoritative"
            ),
            issued_at=_NOW,
            expires_at=_EXPIRES_AT,
            authorization_code=(
                _INTERNAL_AUTHORIZATION_CODE
            ),
        )

    service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            authorize_access_code
        ),
        issue_bootstrap_authorization=(
            issue_bootstrap_authorization
        ),
        clock=lambda: _NOW,
    )

    service.exchange(
        activation_code=_ACTIVATION_CODE,
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    assert observed[0][
        "customer_id"
    ] == "customer-authoritative"


def test_mismatched_bootstrap_customer_fails_closed(
) -> None:
    def authorize_access_code(
        **kwargs,
    ):
        return CustomerSetupAccessCodeAuthorization(
            setup_activation_id=(
                _SETUP_ACTIVATION_ID
            ),
            customer_id=_CUSTOMER_ID,
        )

    def issue_bootstrap_authorization(
        **kwargs,
    ):
        return CustomerSetupBootstrapAuthorizationIssuance(
            authorization_request_id=(
                kwargs[
                    "authorization_request_id"
                ]
            ),
            authorization_id="authorization-001",
            customer_id="customer-attacker",
            issued_at=_NOW,
            expires_at=_EXPIRES_AT,
            authorization_code=(
                _INTERNAL_AUTHORIZATION_CODE
            ),
        )

    service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            authorize_access_code
        ),
        issue_bootstrap_authorization=(
            issue_bootstrap_authorization
        ),
        clock=lambda: _NOW,
    )

    with pytest.raises(
        RuntimeError,
        match="customer identity",
    ):
        service.exchange(
            activation_code=_ACTIVATION_CODE,
            code_challenge_s256=(
                _CODE_CHALLENGE
            ),
        )


def test_mismatched_request_identity_fails_closed(
) -> None:
    def authorize_access_code(
        **kwargs,
    ):
        return CustomerSetupAccessCodeAuthorization(
            setup_activation_id=(
                _SETUP_ACTIVATION_ID
            ),
            customer_id=_CUSTOMER_ID,
        )

    def issue_bootstrap_authorization(
        **kwargs,
    ):
        return CustomerSetupBootstrapAuthorizationIssuance(
            authorization_request_id=(
                "wrong-request"
            ),
            authorization_id="authorization-001",
            customer_id=_CUSTOMER_ID,
            issued_at=_NOW,
            expires_at=_EXPIRES_AT,
            authorization_code=(
                _INTERNAL_AUTHORIZATION_CODE
            ),
        )

    service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            authorize_access_code
        ),
        issue_bootstrap_authorization=(
            issue_bootstrap_authorization
        ),
        clock=lambda: _NOW,
    )

    with pytest.raises(
        RuntimeError,
        match="request identity",
    ):
        service.exchange(
            activation_code=_ACTIVATION_CODE,
            code_challenge_s256=(
                _CODE_CHALLENGE
            ),
        )


def test_invalid_access_authorization_result_fails_closed(
) -> None:
    issue_calls = []

    service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            lambda **kwargs: object()
        ),
        issue_bootstrap_authorization=(
            lambda **kwargs: (
                issue_calls.append(
                    kwargs
                )
            )
        ),
        clock=lambda: _NOW,
    )

    with pytest.raises(
        RuntimeError,
        match="invalid result",
    ):
        service.exchange(
            activation_code=_ACTIVATION_CODE,
            code_challenge_s256=(
                _CODE_CHALLENGE
            ),
        )

    assert issue_calls == []


def test_invalid_bootstrap_issuance_result_fails_closed(
) -> None:
    service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            lambda **kwargs: (
                CustomerSetupAccessCodeAuthorization(
                    setup_activation_id=(
                        _SETUP_ACTIVATION_ID
                    ),
                    customer_id=_CUSTOMER_ID,
                )
            )
        ),
        issue_bootstrap_authorization=(
            lambda **kwargs: object()
        ),
        clock=lambda: _NOW,
    )

    with pytest.raises(
        RuntimeError,
        match="invalid result",
    ):
        service.exchange(
            activation_code=_ACTIVATION_CODE,
            code_challenge_s256=(
                _CODE_CHALLENGE
            ),
        )


def test_naive_clock_fails_closed_before_bootstrap_issue(
) -> None:
    issue_calls = []

    service, _, _ = _build_service(
        clock=(
            lambda: datetime(
                2026,
                9,
                4,
                12,
                0,
            )
        )
    )

    service._issue_bootstrap_authorization = (
        lambda **kwargs: (
            issue_calls.append(
                kwargs
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        service.exchange(
            activation_code=_ACTIVATION_CODE,
            code_challenge_s256=(
                _CODE_CHALLENGE
            ),
        )

    assert issue_calls == []


def test_clock_is_normalized_to_utc(
) -> None:
    supplied = datetime(
        2026,
        9,
        4,
        19,
        0,
        tzinfo=timezone(
            timedelta(
                hours=7
            )
        ),
    )

    service, _, issue_calls = (
        _build_service(
            clock=lambda: supplied
        )
    )

    service.exchange(
        activation_code=_ACTIVATION_CODE,
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    assert (
        issue_calls[0][
            "current_time"
        ]
        == _NOW
    )


def test_result_repr_redacts_internal_authorization_code(
) -> None:
    result = CustomerSetupAccessCodeExchangeResult(
        authorization_code=(
            _INTERNAL_AUTHORIZATION_CODE
        ),
        expires_at=_EXPIRES_AT,
    )

    rendered = repr(
        result
    )

    assert (
        _INTERNAL_AUTHORIZATION_CODE
        not in rendered
    )

    assert (
        "authorization_code=<redacted>"
        in rendered
    )


def test_result_contains_no_customer_or_setup_activation_identity(
) -> None:
    parameters = inspect.signature(
        CustomerSetupAccessCodeExchangeResult
    ).parameters

    assert set(
        parameters
    ) == {
        "authorization_code",
        "expires_at",
    }


def test_constructor_requires_only_narrow_dependencies(
) -> None:
    parameters = inspect.signature(
        CustomerSetupAccessCodeExchangeService.__init__
    ).parameters

    assert set(
        parameters
    ) == {
        "self",
        "authorize_access_code",
        "issue_bootstrap_authorization",
        "clock",
    }


def test_owner_has_no_payment_http_main_or_persistence_authority(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_access_code_exchange_service.py"
    )

    source = source_path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "fastapi",
        "httpx",
        "requests",
        "paypal",
        "vietqr",
        "payment_id",
        "subscription_id",
        "backend.main",
        "tempfile",
        "os.replace",
        "initialize_empty(",
        "open_existing(",
    )

    for token in forbidden:
        assert token not in source


def test_exchange_converges_authoritative_serialized_bootstrap_expiry(
) -> None:
    """
    Production bootstrap issuance exposes serialized timestamps.

    Access-code exchange must converge that authoritative
    transport-neutral timestamp into its own result contract
    instead of failing after durable authorization issuance.
    """

    serialized_now = (
        _NOW
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )

    serialized_expiry = (
        _EXPIRES_AT
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )

    def authorize_access_code(
        **kwargs,
    ):
        return CustomerSetupAccessCodeAuthorization(
            setup_activation_id=(
                _SETUP_ACTIVATION_ID
            ),
            customer_id=(
                _CUSTOMER_ID
            ),
        )

    def issue_bootstrap_authorization(
        **kwargs,
    ):
        return CustomerSetupBootstrapAuthorizationIssuance(
            authorization_request_id=(
                kwargs[
                    "authorization_request_id"
                ]
            ),
            authorization_id=(
                "bootstrap-authorization-production-shaped"
            ),
            customer_id=(
                kwargs[
                    "customer_id"
                ]
            ),
            issued_at=(
                serialized_now
            ),
            expires_at=(
                serialized_expiry
            ),
            authorization_code=(
                _INTERNAL_AUTHORIZATION_CODE
            ),
        )

    service = CustomerSetupAccessCodeExchangeService(
        authorize_access_code=(
            authorize_access_code
        ),
        issue_bootstrap_authorization=(
            issue_bootstrap_authorization
        ),
        clock=(
            lambda: _NOW
        ),
    )

    result = service.exchange(
        activation_code=(
            _ACTIVATION_CODE
        ),
        code_challenge_s256=(
            _CODE_CHALLENGE
        ),
    )

    assert (
        result.authorization_code
        == _INTERNAL_AUTHORIZATION_CODE
    )

    assert (
        result.expires_at
        == _EXPIRES_AT
    )
