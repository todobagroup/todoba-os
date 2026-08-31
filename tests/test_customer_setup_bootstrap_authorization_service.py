"""
Owner tests for Customer Setup Bootstrap Authorization Core.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationService,
    CustomerSetupBootstrapAuthorizationStatus,
    CustomerSetupBootstrapAuthorizationStore,
    derive_customer_setup_bootstrap_authorization_verifier,
    derive_pkce_s256_code_challenge,
)


_NOW = datetime(
    2026,
    8,
    31,
    2,
    45,
    tzinfo=timezone.utc,
)

_CUSTOMER_ID = "customer-001"

_CODE_VERIFIER = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-._~"
)


def _build_identity_registry(
    tmp_path: Path,
) -> CustomerIdentityRegistry:
    registry = CustomerIdentityRegistry(
        tmp_path
        / "customer_identities.json"
    )

    registry.initialize_empty()

    registry.register(
        CustomerIdentity(
            customer_id=_CUSTOMER_ID
        )
    )

    return registry


def _build_service(
    tmp_path: Path,
) -> tuple[
    CustomerIdentityRegistry,
    CustomerSetupBootstrapAuthorizationStore,
    CustomerSetupBootstrapAuthorizationService,
]:
    identity_registry = (
        _build_identity_registry(
            tmp_path
        )
    )

    store = (
        CustomerSetupBootstrapAuthorizationStore(
            tmp_path
            / "bootstrap_authorizations.json",
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    store.initialize_empty()

    service = (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=store,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    return (
        identity_registry,
        store,
        service,
    )


def _issue(
    service: CustomerSetupBootstrapAuthorizationService,
):
    return service.issue(
        authorization_request_id="request-001",
        customer_id=_CUSTOMER_ID,
        code_challenge_s256=(
            derive_pkce_s256_code_challenge(
                _CODE_VERIFIER
            )
        ),
        current_time=_NOW,
    )


def test_pkce_s256_derivation_is_stable(
) -> None:
    challenge = (
        derive_pkce_s256_code_challenge(
            _CODE_VERIFIER
        )
    )

    assert len(
        challenge
    ) == 43

    assert "=" not in challenge

    assert (
        challenge
        == derive_pkce_s256_code_challenge(
            _CODE_VERIFIER
        )
    )


def test_issue_creates_active_authorization(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    record = store.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    assert record is not None

    assert (
        record.status
        is CustomerSetupBootstrapAuthorizationStatus.ACTIVE
    )

    assert (
        record.customer_id
        == _CUSTOMER_ID
    )

    assert (
        record.code_challenge_s256
        == derive_pkce_s256_code_challenge(
            _CODE_VERIFIER
        )
    )


def test_plaintext_authorization_code_is_not_persisted(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    persisted = (
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        issued.authorization_code
        not in persisted
    )

    assert (
        derive_customer_setup_bootstrap_authorization_verifier(
            issued.authorization_code
        )
        in persisted
    )


def test_code_verifier_is_not_persisted(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    _issue(
        service
    )

    persisted = (
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        _CODE_VERIFIER
        not in persisted
    )


def test_issuance_repr_redacts_authorization_code(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    rendered = repr(
        issued
    )

    assert (
        issued.authorization_code
        not in rendered
    )

    assert (
        "authorization_code=<redacted>"
        in rendered
    )


def test_issue_rejects_unknown_customer(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="Unknown customer identity",
    ):
        service.issue(
            authorization_request_id=(
                "request-unknown"
            ),
            customer_id="unknown-customer",
            code_challenge_s256=(
                derive_pkce_s256_code_challenge(
                    _CODE_VERIFIER
                )
            ),
            current_time=_NOW,
        )


def test_issue_retry_preserves_authorization_identity_and_lifetime(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    first = _issue(
        service
    )

    second = _issue(
        service
    )

    assert (
        second.authorization_id
        == first.authorization_id
    )

    assert (
        second.issued_at
        == first.issued_at
    )

    assert (
        second.expires_at
        == first.expires_at
    )

    assert (
        second.authorization_code
        != first.authorization_code
    )


def test_retry_rotates_authorization_verifier(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    first = _issue(
        service
    )

    first_verifier = (
        derive_customer_setup_bootstrap_authorization_verifier(
            first.authorization_code
        )
    )

    second = _issue(
        service
    )

    second_verifier = (
        derive_customer_setup_bootstrap_authorization_verifier(
            second.authorization_code
        )
    )

    assert (
        first_verifier
        != second_verifier
    )

    assert (
        store.get_by_verifier(
            authorization_verifier_sha256=(
                first_verifier
            )
        )
        is None
    )

    assert (
        store.get_by_verifier(
            authorization_verifier_sha256=(
                second_verifier
            )
        )
        is not None
    )


def test_retry_rejects_other_customer(
    tmp_path,
) -> None:
    (
        identity_registry,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    identity_registry.register(
        CustomerIdentity(
            customer_id="customer-002"
        )
    )

    _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="belongs to another customer",
    ):
        service.issue(
            authorization_request_id=(
                "request-001"
            ),
            customer_id="customer-002",
            code_challenge_s256=(
                derive_pkce_s256_code_challenge(
                    _CODE_VERIFIER
                )
            ),
            current_time=_NOW,
        )


def test_retry_rejects_other_pkce_challenge(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    _issue(
        service
    )

    other_verifier = (
        "A"
        * 43
    )

    with pytest.raises(
        ValueError,
        match="another PKCE challenge",
    ):
        service.issue(
            authorization_request_id=(
                "request-001"
            ),
            customer_id=_CUSTOMER_ID,
            code_challenge_s256=(
                derive_pkce_s256_code_challenge(
                    other_verifier
                )
            ),
            current_time=_NOW,
        )


def test_redeem_returns_authoritative_customer(
    tmp_path,
) -> None:
    (
        identity_registry,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    redeemed = service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    assert (
        redeemed.customer_id
        == _CUSTOMER_ID
    )

    assert (
        redeemed.customer_identity
        is identity_registry.get(
            customer_id=_CUSTOMER_ID
        )
    )


def test_successful_redeem_consumes_authorization(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    record = store.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    assert (
        record.status
        is CustomerSetupBootstrapAuthorizationStatus.CONSUMED
    )

    assert (
        record.consumed_at
        is not None
    )


def test_authorization_cannot_be_redeemed_twice(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="already consumed",
    ):
        service.redeem(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=(
                _NOW
                + timedelta(
                    seconds=2
                )
            ),
        )


def test_consumed_authorization_cannot_be_reissued(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="cannot be reissued",
    ):
        _issue(
            service
        )


def test_wrong_pkce_verifier_does_not_consume(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    wrong_verifier = (
        "Z"
        * 43
    )

    with pytest.raises(
        ValueError,
        match="Invalid PKCE verifier",
    ):
        service.redeem(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=(
                wrong_verifier
            ),
            current_time=(
                _NOW
                + timedelta(
                    seconds=1
                )
            ),
        )

    record = store.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    assert (
        record.status
        is CustomerSetupBootstrapAuthorizationStatus.ACTIVE
    )


def test_old_rotated_authorization_code_is_invalid(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    first = _issue(
        service
    )

    second = _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="Invalid bootstrap authorization",
    ):
        service.redeem(
            authorization_code=(
                first.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=(
                _NOW
                + timedelta(
                    seconds=1
                )
            ),
        )

    record = store.get(
        authorization_id=(
            second.authorization_id
        )
    )

    assert (
        record.status
        is CustomerSetupBootstrapAuthorizationStatus.ACTIVE
    )


def test_expired_authorization_cannot_be_redeemed(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    record = store.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    expires_at = datetime.fromisoformat(
        record.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    with pytest.raises(
        ValueError,
        match="is expired",
    ):
        service.redeem(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=expires_at,
        )


def test_expired_authorization_cannot_be_reissued(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    record = store.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    expires_at = datetime.fromisoformat(
        record.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    with pytest.raises(
        ValueError,
        match="cannot be reissued",
    ):
        service.issue(
            authorization_request_id=(
                "request-001"
            ),
            customer_id=_CUSTOMER_ID,
            code_challenge_s256=(
                derive_pkce_s256_code_challenge(
                    _CODE_VERIFIER
                )
            ),
            current_time=expires_at,
        )


def test_restart_restores_active_authorization(
    tmp_path,
) -> None:
    (
        identity_registry,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    reopened = (
        CustomerSetupBootstrapAuthorizationStore(
            store.storage_path,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    reopened.open_existing()

    reopened_service = (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=reopened,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    redeemed = (
        reopened_service.redeem(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=(
                _NOW
                + timedelta(
                    seconds=1
                )
            ),
        )
    )

    assert (
        redeemed.customer_id
        == _CUSTOMER_ID
    )


def test_consumed_state_survives_restart(
    tmp_path,
) -> None:
    (
        identity_registry,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    reopened = (
        CustomerSetupBootstrapAuthorizationStore(
            store.storage_path,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    reopened.open_existing()

    record = reopened.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    assert (
        record.status
        is CustomerSetupBootstrapAuthorizationStatus.CONSUMED
    )


def test_store_persists_exact_schema(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    _issue(
        service
    )

    payload = json.loads(
        store.storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert set(
        payload
    ) == {
        "version",
        "items",
    }

    assert (
        payload[
            "version"
        ]
        == 1
    )

    assert len(
        payload[
            "items"
        ]
    ) == 1

    assert set(
        payload[
            "items"
        ][
            0
        ]
    ) == {
        "authorization_request_id",
        "authorization_id",
        "customer_id",
        "authorization_verifier_sha256",
        "code_challenge_s256",
        "issued_at",
        "expires_at",
        "status",
        "consumed_at",
    }


@pytest.mark.parametrize(
    "value",
    (
        "short",
        "contains space"
        + ("A" * 40),
        "A" * 42,
        "A" * 129,
    ),
)
def test_invalid_pkce_code_verifier_is_rejected(
    value,
) -> None:
    with pytest.raises(
        ValueError,
        match="code_verifier is invalid",
    ):
        derive_pkce_s256_code_challenge(
            value
        )


@pytest.mark.parametrize(
    "challenge",
    (
        "",
        "A" * 42,
        "A" * 44,
        ("A" * 42) + "=",
    ),
)
def test_invalid_pkce_challenge_is_rejected(
    tmp_path,
    challenge,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="code_challenge_s256 is invalid",
    ):
        service.issue(
            authorization_request_id=(
                "request-invalid"
            ),
            customer_id=_CUSTOMER_ID,
            code_challenge_s256=challenge,
            current_time=_NOW,
        )


def test_store_requires_ready_customer_identity_registry(
    tmp_path,
) -> None:
    identity_registry = (
        CustomerIdentityRegistry(
            tmp_path
            / "customer_identities.json"
        )
    )

    store = (
        CustomerSetupBootstrapAuthorizationStore(
            tmp_path
            / "bootstrap_authorizations.json",
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="identity registry is not ready",
    ):
        store.initialize_empty()


def test_service_requires_ready_authorization_store(
    tmp_path,
) -> None:
    identity_registry = (
        _build_identity_registry(
            tmp_path
        )
    )

    store = (
        CustomerSetupBootstrapAuthorizationStore(
            tmp_path
            / "bootstrap_authorizations.json",
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    service = (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=store,
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="authorization store is not ready",
    ):
        service.issue(
            authorization_request_id=(
                "request-001"
            ),
            customer_id=_CUSTOMER_ID,
            code_challenge_s256=(
                derive_pkce_s256_code_challenge(
                    _CODE_VERIFIER
                )
            ),
            current_time=_NOW,
        )


def test_consumed_redemption_can_be_recovered(
    tmp_path,
) -> None:
    (
        identity_registry,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    first = service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    recovered = (
        service.recover_consumed_redemption(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=(
                _NOW
                + timedelta(
                    seconds=2
                )
            ),
        )
    )

    assert (
        recovered.authorization_id
        == first.authorization_id
    )

    assert (
        recovered.customer_id
        == first.customer_id
    )

    assert (
        recovered.consumed_at
        == first.consumed_at
    )

    assert (
        recovered.customer_identity
        is identity_registry.get(
            customer_id=_CUSTOMER_ID
        )
    )


def test_consumed_redemption_recovery_does_not_mutate_store(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    before = store.storage_path.read_bytes()

    service.recover_consumed_redemption(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=2
            )
        ),
    )

    after = store.storage_path.read_bytes()

    assert after == before


def test_active_authorization_cannot_use_recovery_path(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    with pytest.raises(
        ValueError,
        match="is not consumed",
    ):
        service.recover_consumed_redemption(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=(
                _NOW
                + timedelta(
                    seconds=1
                )
            ),
        )


def test_consumed_recovery_rejects_wrong_authorization_code(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    replacement = (
        "A"
        if not issued.authorization_code.endswith(
            "A"
        )
        else "B"
    )

    wrong_code = (
        issued.authorization_code[
            :-1
        ]
        + replacement
    )

    with pytest.raises(
        ValueError,
        match="Invalid bootstrap authorization",
    ):
        service.recover_consumed_redemption(
            authorization_code=wrong_code,
            code_verifier=_CODE_VERIFIER,
            current_time=(
                _NOW
                + timedelta(
                    seconds=2
                )
            ),
        )


def test_consumed_recovery_rejects_wrong_pkce_verifier(
    tmp_path,
) -> None:
    (
        _,
        _,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="Invalid PKCE verifier",
    ):
        service.recover_consumed_redemption(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=(
                "Z"
                * 43
            ),
            current_time=(
                _NOW
                + timedelta(
                    seconds=2
                )
            ),
        )


def test_consumed_recovery_rejects_expired_authorization(
    tmp_path,
) -> None:
    (
        _,
        store,
        service,
    ) = _build_service(
        tmp_path
    )

    issued = _issue(
        service
    )

    service.redeem(
        authorization_code=(
            issued.authorization_code
        ),
        code_verifier=_CODE_VERIFIER,
        current_time=(
            _NOW
            + timedelta(
                seconds=1
            )
        ),
    )

    record = store.get(
        authorization_id=(
            issued.authorization_id
        )
    )

    expires_at = datetime.fromisoformat(
        record.expires_at.replace(
            "Z",
            "+00:00",
        )
    )

    with pytest.raises(
        ValueError,
        match="is expired",
    ):
        service.recover_consumed_redemption(
            authorization_code=(
                issued.authorization_code
            ),
            code_verifier=_CODE_VERIFIER,
            current_time=expires_at,
        )


def test_owner_has_no_http_browser_or_main_dependency(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_authorization_service.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden_imports = (
        "fastapi",
        "httpx",
        "requests",
        "webbrowser",
        "backend.main",
        "MetaTrader5",
    )

    for token in forbidden_imports:
        assert (
            f"import {token}"
            not in source
        )

        assert (
            f"from {token}"
            not in source
        )