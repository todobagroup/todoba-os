from datetime import datetime, timedelta, timezone

import pytest

from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantService,
    CustomerVPSConnectGrantStore,
)


_CUSTOMER_ID = "customer-001"
_DEPLOYMENT_ID = "deployment-001"
_AGENT_ID = "trusted-agent-001"
_ACCOUNT_FINGERPRINT = "Broker-Server:12345678"

_NOW = datetime(
    2026,
    9,
    7,
    8,
    0,
    tzinfo=timezone.utc,
)


def _build_service(
    tmp_path,
    *,
    now=_NOW,
):
    store = CustomerVPSConnectGrantStore(
        tmp_path
        / "customer_vps_connect_grants.json"
    )
    store.initialize_empty()

    service = CustomerVPSConnectGrantService(
        grant_store=store,
        clock=lambda: now,
    )

    return store, service


def test_issue_and_authorize_returns_bound_identity(
    tmp_path,
) -> None:
    _, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    authorized = service.authorize(
        grant_credential=(
            issued.grant_credential
        )
    )

    assert authorized.customer_id == _CUSTOMER_ID
    assert (
        authorized.deployment_id
        == _DEPLOYMENT_ID
    )
    assert authorized.agent_id == _AGENT_ID
    assert (
        authorized.account_fingerprint
        == _ACCOUNT_FINGERPRINT
    )


def test_plaintext_grant_is_not_persisted(
    tmp_path,
) -> None:
    store, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    persisted = (
        tmp_path
        / "customer_vps_connect_grants.json"
    ).read_text(
        encoding="utf-8"
    )

    assert issued.grant_credential not in persisted

    record = store.get(
        grant_id=issued.grant_id
    )

    assert record is not None
    assert (
        getattr(
            record,
            "grant_credential",
            None,
        )
        is None
    )


def test_wrong_grant_secret_fails_closed(
    tmp_path,
) -> None:
    _, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    wrong = (
        issued.grant_credential[:-1]
        + (
            "A"
            if issued.grant_credential[-1] != "A"
            else "B"
        )
    )

    with pytest.raises(
        ValueError,
        match="grant is invalid",
    ):
        service.authorize(
            grant_credential=wrong
        )


def test_expired_grant_fails_closed(
    tmp_path,
) -> None:
    _, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    expired_service = CustomerVPSConnectGrantService(
        grant_store=service._grant_store,
        clock=lambda: (
            issued.expires_at
            + timedelta(
                seconds=1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="grant is invalid",
    ):
        expired_service.authorize(
            grant_credential=(
                issued.grant_credential
            )
        )


def test_revoke_invalidates_grant(
    tmp_path,
) -> None:
    _, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    service.revoke(
        grant_id=issued.grant_id
    )

    with pytest.raises(
        ValueError,
        match="grant is invalid",
    ):
        service.authorize(
            grant_credential=(
                issued.grant_credential
            )
        )


def test_grant_survives_store_reopen(
    tmp_path,
) -> None:
    _, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    reopened_store = CustomerVPSConnectGrantStore(
        tmp_path
        / "customer_vps_connect_grants.json"
    )
    reopened_store.open_existing()

    reopened_service = CustomerVPSConnectGrantService(
        grant_store=reopened_store,
        clock=lambda: _NOW,
    )

    authorized = reopened_service.authorize(
        grant_credential=(
            issued.grant_credential
        )
    )

    assert authorized.customer_id == _CUSTOMER_ID
    assert (
        authorized.deployment_id
        == _DEPLOYMENT_ID
    )
    assert authorized.agent_id == _AGENT_ID
    assert (
        authorized.account_fingerprint
        == _ACCOUNT_FINGERPRINT
    )


def test_grant_fails_closed_at_exact_expiry(
    tmp_path,
) -> None:
    _, service = _build_service(tmp_path)

    issued = service.issue(
        customer_id=_CUSTOMER_ID,
        deployment_id=_DEPLOYMENT_ID,
        agent_id=_AGENT_ID,
        account_fingerprint=_ACCOUNT_FINGERPRINT,
    )

    expired_service = CustomerVPSConnectGrantService(
        grant_store=service._grant_store,
        clock=lambda: issued.expires_at,
    )

    with pytest.raises(
        ValueError,
        match="grant is invalid",
    ):
        expired_service.authorize(
            grant_credential=(
                issued.grant_credential
            )
        )
