from decimal import Decimal
from inspect import signature

import pytest

from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecision,
    CustomerCommercialCapacityDecisionStatus,
)
from backend.commercial.customer_commercial_new_exposure_authorization_service import (
    CustomerCommercialNewExposureAuthorizationService,
)


def _decision(
    status: CustomerCommercialCapacityDecisionStatus,
) -> CustomerCommercialCapacityDecision:
    return CustomerCommercialCapacityDecision(
        commercial_entitlement_id="commercial-entitlement-001",
        deployment_id="deployment-001",
        cycle_id="cycle-001",
        licensed_account_cap_usd=Decimal("1000"),
        operational_grace_limit_usd=Decimal("1050.00"),
        commercial_capacity_high_water_usd=(
            Decimal("1000")
            if (
                status
                is CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            )
            else Decimal("1050.01")
        ),
        status=status,
    )


def test_authorize_accepts_only_capacity_decision() -> None:
    parameters = list(
        signature(
            CustomerCommercialNewExposureAuthorizationService
            .authorize
        ).parameters
    )

    assert parameters == [
        "self",
        "capacity_decision",
    ]


def test_allow_new_exposure_is_authorized() -> None:
    result = (
        CustomerCommercialNewExposureAuthorizationService()
        .authorize(
            capacity_decision=_decision(
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            )
        )
    )

    assert result is None


def test_upgrade_required_fails_closed() -> None:
    with pytest.raises(
        RuntimeError,
        match="upgrade required",
    ):
        (
            CustomerCommercialNewExposureAuthorizationService()
            .authorize(
                capacity_decision=_decision(
                    CustomerCommercialCapacityDecisionStatus
                    .UPGRADE_REQUIRED
                )
            )
        )


def test_wrong_decision_type_fails_closed() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerCommercialCapacityDecision",
    ):
        (
            CustomerCommercialNewExposureAuthorizationService()
            .authorize(
                capacity_decision=object()
            )
        )


def test_owner_has_no_store_payment_setup_or_mt5_authority() -> None:
    import inspect

    source = inspect.getsource(
        CustomerCommercialNewExposureAuthorizationService
    )

    for forbidden in (
        "Store",
        "store=",
        "_store",
        "payment",
        "settlement",
        "setup_activation",
        "MT5",
        "mt5",
        "order_send",
        "open_position",
        "close_position",
        "current_balance_usd",
        "equity_usd",
    ):
        assert forbidden not in source
