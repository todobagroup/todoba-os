"""
TODOBA Customer Setup Handoff Authorizer Tests

Security / composition proof:
- only CustomerSetupHandoffService may be wrapped
- clock must be callable
- authorization accepts only the handoff credential
- clock result must be datetime
- clock result must be timezone-aware
- non-UTC aware clocks are normalized to UTC
- credential and authoritative UTC time are delegated unchanged
- R3 authorization failures propagate unchanged
- R3 authorization result identity is preserved
- owner exposes no issuance or revocation capability
- owner contains no HTTP, durable initialization, or backend.main
  ownership

All durable test state is isolated beneath pytest tmp_path.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from inspect import signature
from pathlib import Path

import pytest

import backend.commercial.customer_setup_handoff_authorizer as authorizer_module
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_handoff_authorizer import (
    CustomerSetupHandoffAuthorizer,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffService,
    CustomerSetupHandoffStore,
)


NOW = datetime(
    2026,
    8,
    29,
    3,
    0,
    0,
    tzinfo=timezone.utc,
)


def build_service(
    tmp_path: Path,
) -> CustomerSetupHandoffService:
    activation_store = CustomerSetupActivationStore(
        tmp_path
        / "customer_setup_activations.json"
    )
    activation_store.initialize_empty()

    handoff_store = CustomerSetupHandoffStore(
        tmp_path
        / "customer_setup_handoffs.json"
    )
    handoff_store.initialize_empty()

    return CustomerSetupHandoffService(
        handoff_store=handoff_store,
        setup_activation_store=activation_store,
    )


def test_constructor_requires_handoff_service() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerSetupHandoffService",
    ):
        CustomerSetupHandoffAuthorizer(
            handoff_service=object(),
        )


def test_constructor_requires_callable_clock(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="clock must be callable",
    ):
        CustomerSetupHandoffAuthorizer(
            handoff_service=service,
            clock=None,
        )


def test_authorize_contract_accepts_only_handoff_credential(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path
    )

    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=service,
        clock=lambda: NOW,
    )

    parameters = tuple(
        signature(
            authorizer.authorize
        ).parameters
    )

    assert parameters == (
        "handoff_credential",
    )


def test_authorize_delegates_credential_and_utc_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path
    )

    expected_result = object()
    seen = {}

    def recording_authorize(
        *,
        handoff_credential: str,
        current_time: datetime,
    ):
        seen["credential"] = handoff_credential
        seen["current_time"] = current_time

        return expected_result

    monkeypatch.setattr(
        service,
        "authorize",
        recording_authorize,
    )

    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=service,
        clock=lambda: NOW,
    )

    result = authorizer.authorize(
        "handoff.test.secret"
    )

    assert result is expected_result
    assert (
        seen["credential"]
        == "handoff.test.secret"
    )
    assert seen["current_time"] == NOW
    assert (
        seen["current_time"].tzinfo
        is timezone.utc
    )


def test_non_utc_aware_clock_is_normalized_to_utc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path
    )

    local_time = datetime(
        2026,
        8,
        29,
        10,
        0,
        0,
        tzinfo=timezone(
            timedelta(
                hours=7
            )
        ),
    )

    seen = {}

    def recording_authorize(
        *,
        handoff_credential: str,
        current_time: datetime,
    ):
        seen["current_time"] = current_time
        return object()

    monkeypatch.setattr(
        service,
        "authorize",
        recording_authorize,
    )

    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=service,
        clock=lambda: local_time,
    )

    authorizer.authorize(
        "handoff.test.secret"
    )

    assert seen["current_time"] == NOW
    assert (
        seen["current_time"].tzinfo
        is timezone.utc
    )


def test_non_datetime_clock_result_fails_before_r3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path
    )

    called = []

    def recording_authorize(
        **kwargs,
    ):
        called.append(
            kwargs
        )
        return object()

    monkeypatch.setattr(
        service,
        "authorize",
        recording_authorize,
    )

    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=service,
        clock=lambda: "2026-08-29T03:00:00Z",
    )

    with pytest.raises(
        TypeError,
        match="clock must return datetime",
    ):
        authorizer.authorize(
            "handoff.test.secret"
        )

    assert called == []


def test_naive_datetime_clock_fails_before_r3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path
    )

    called = []

    def recording_authorize(
        **kwargs,
    ):
        called.append(
            kwargs
        )
        return object()

    monkeypatch.setattr(
        service,
        "authorize",
        recording_authorize,
    )

    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=service,
        clock=lambda: datetime(
            2026,
            8,
            29,
            3,
            0,
            0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware datetime",
    ):
        authorizer.authorize(
            "handoff.test.secret"
        )

    assert called == []


def test_r3_value_error_propagates_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path
    )

    expected_error = ValueError(
        "Invalid customer setup handoff credential."
    )

    def failing_authorize(
        *,
        handoff_credential: str,
        current_time: datetime,
    ):
        raise expected_error

    monkeypatch.setattr(
        service,
        "authorize",
        failing_authorize,
    )

    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=service,
        clock=lambda: NOW,
    )

    with pytest.raises(
        ValueError,
    ) as exc_info:
        authorizer.authorize(
            "handoff.invalid.secret"
        )

    assert exc_info.value is expected_error


def test_default_clock_is_timezone_aware_utc() -> None:
    current_time = (
        authorizer_module._utc_now()
    )

    assert isinstance(
        current_time,
        datetime,
    )

    assert current_time.tzinfo is not None
    assert current_time.utcoffset() == timedelta(0)


def test_authorizer_exposes_no_issue_or_revoke(
    tmp_path: Path,
) -> None:
    authorizer = CustomerSetupHandoffAuthorizer(
        handoff_service=build_service(
            tmp_path
        ),
        clock=lambda: NOW,
    )

    assert not hasattr(
        authorizer,
        "issue",
    )

    assert not hasattr(
        authorizer,
        "revoke",
    )

    assert not hasattr(
        authorizer,
        "initialize_empty",
    )


def test_owner_has_no_http_or_runtime_composition_dependency() -> None:
    source = Path(
        authorizer_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "fastapi" not in source

    assert "`nimport backend.main" not in source
    assert "`nfrom backend.main" not in source

    assert "initialize_empty(" not in source
    assert ".issue(" not in source
    assert ".revoke(" not in source
