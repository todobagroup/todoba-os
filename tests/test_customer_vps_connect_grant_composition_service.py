from types import SimpleNamespace

import pytest

from backend.commercial.customer_vps_connect_grant_composition_service import (
    CustomerVPSConnectGrantCompositionService,
)


_ACTIVATION_CODE = "customer-activation-code"
_CUSTOMER_ID = "customer-001"
_DEPLOYMENT_ID = "deployment-001"
_AGENT_ID = "trusted-agent-001"
_ACCOUNT_FINGERPRINT = "Broker-Server:12345678"


def _build_service(
    *,
    bound_customer_id=_CUSTOMER_ID,
    bound_deployment_id=_DEPLOYMENT_ID,
    resolved_customer_id=_CUSTOMER_ID,
    resolved_deployment_id=_DEPLOYMENT_ID,
    resolved_agent_id=_AGENT_ID,
    resolution_exists=True,
):
    issue_calls = []

    def authorize_bound_access_code(
        *,
        activation_code,
    ):
        assert activation_code == _ACTIVATION_CODE

        return SimpleNamespace(
            setup_activation_id=(
                "setup-activation-001"
            ),
            customer_id=bound_customer_id,
            deployment_id=(
                bound_deployment_id
            ),
        )

    def resolve_deployment(
        *,
        customer_id,
        account_fingerprint,
    ):
        assert customer_id == bound_customer_id
        assert (
            account_fingerprint
            == _ACCOUNT_FINGERPRINT
        )

        if not resolution_exists:
            return None

        return SimpleNamespace(
            customer_id=resolved_customer_id,
            deployment_id=(
                resolved_deployment_id
            ),
            agent_id=resolved_agent_id,
            account_fingerprint=(
                _ACCOUNT_FINGERPRINT
            ),
        )

    def issue_grant(
        **kwargs,
    ):
        issue_calls.append(kwargs)

        return SimpleNamespace(
            grant_id="grant-001",
            grant_credential="opaque-grant",
            **kwargs,
        )

    service = CustomerVPSConnectGrantCompositionService(
        authorize_bound_access_code=(
            authorize_bound_access_code
        ),
        resolve_deployment=resolve_deployment,
        issue_grant=issue_grant,
    )

    return service, issue_calls


def test_exact_bound_deployment_issues_grant(
) -> None:
    service, issue_calls = _build_service()

    result = service.issue(
        activation_code=_ACTIVATION_CODE,
        account_fingerprint=(
            _ACCOUNT_FINGERPRINT
        ),
    )

    assert result.grant_credential == "opaque-grant"

    assert issue_calls == [
        {
            "customer_id": _CUSTOMER_ID,
            "deployment_id": _DEPLOYMENT_ID,
            "agent_id": _AGENT_ID,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
        }
    ]


def test_missing_deployment_resolution_fails_closed(
) -> None:
    service, issue_calls = _build_service(
        resolution_exists=False,
    )

    with pytest.raises(
        ValueError,
        match="deployment",
    ):
        service.issue(
            activation_code=_ACTIVATION_CODE,
            account_fingerprint=(
                _ACCOUNT_FINGERPRINT
            ),
        )

    assert issue_calls == []


def test_different_deployment_fails_closed(
) -> None:
    service, issue_calls = _build_service(
        resolved_deployment_id=(
            "deployment-other"
        ),
    )

    with pytest.raises(
        ValueError,
        match="deployment",
    ):
        service.issue(
            activation_code=_ACTIVATION_CODE,
            account_fingerprint=(
                _ACCOUNT_FINGERPRINT
            ),
        )

    assert issue_calls == []


def test_different_customer_fails_closed(
) -> None:
    service, issue_calls = _build_service(
        resolved_customer_id=(
            "customer-other"
        ),
    )

    with pytest.raises(
        ValueError,
        match="customer",
    ):
        service.issue(
            activation_code=_ACTIVATION_CODE,
            account_fingerprint=(
                _ACCOUNT_FINGERPRINT
            ),
        )

    assert issue_calls == []


def test_different_account_fingerprint_fails_closed(
) -> None:
    issue_calls = []

    def authorize_bound_access_code(
        *,
        activation_code,
    ):
        assert activation_code == _ACTIVATION_CODE

        return SimpleNamespace(
            setup_activation_id=(
                "setup-activation-001"
            ),
            customer_id=_CUSTOMER_ID,
            deployment_id=_DEPLOYMENT_ID,
        )

    def resolve_deployment(
        *,
        customer_id,
        account_fingerprint,
    ):
        assert customer_id == _CUSTOMER_ID
        assert (
            account_fingerprint
            == _ACCOUNT_FINGERPRINT
        )

        return SimpleNamespace(
            customer_id=_CUSTOMER_ID,
            deployment_id=_DEPLOYMENT_ID,
            agent_id=_AGENT_ID,
            account_fingerprint=(
                "Broker-Server:99999999"
            ),
        )

    def issue_grant(
        **kwargs,
    ):
        issue_calls.append(kwargs)
        return object()

    service = CustomerVPSConnectGrantCompositionService(
        authorize_bound_access_code=(
            authorize_bound_access_code
        ),
        resolve_deployment=resolve_deployment,
        issue_grant=issue_grant,
    )

    with pytest.raises(
        ValueError,
        match="account",
    ):
        service.issue(
            activation_code=_ACTIVATION_CODE,
            account_fingerprint=(
                _ACCOUNT_FINGERPRINT
            ),
        )

    assert issue_calls == []
