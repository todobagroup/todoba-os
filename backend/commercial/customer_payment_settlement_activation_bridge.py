from __future__ import annotations

from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationService,
)


class CustomerPaymentSettlementActivationBridge:
    """
    Narrow bridge from purchased commercial entitlement truth to
    the existing Setup activation owner.

    Input authority:
        settlement_id only

    Authority chain:
        authoritative SETTLED payment
        -> purchased commercial entitlement convergence
        -> ACTIVE commercial entitlement
        -> Setup activation

    This owner does not:
    - receive payment evidence
    - verify provider payment
    - mutate settlement/order truth
    - create commercial terms
    - bind deployment / MT5 identity
    """

    def __init__(
        self,
        *,
        entitlement_convergence_service,
        setup_activation_service: CustomerSetupActivationService,
    ) -> None:
        converge = getattr(
            entitlement_convergence_service,
            "converge",
            None,
        )

        if not callable(
            converge
        ):
            raise TypeError(
                "entitlement_convergence_service must expose converge()."
            )

        activate = getattr(
            setup_activation_service,
            "activate",
            None,
        )

        if not callable(
            activate
        ):
            raise TypeError(
                "setup_activation_service must expose activate()."
            )

        self._entitlement_convergence_service = (
            entitlement_convergence_service
        )
        self._setup_activation_service = (
            setup_activation_service
        )

    def activate_from_settlement(
        self,
        *,
        settlement_id: str,
    ):
        normalized_settlement_id = (
            self._normalize_required_string(
                settlement_id,
                name="settlement_id",
            )
        )

        entitlement = (
            self._entitlement_convergence_service
            .converge(
                settlement_id=normalized_settlement_id
            )
        )

        if not isinstance(
            entitlement,
            CustomerCommercialEntitlement,
        ):
            raise RuntimeError(
                "Commercial entitlement convergence returned "
                "invalid truth."
            )

        expected_entitlement_id = (
            "commercial-entitlement-"
            f"{normalized_settlement_id}"
        )

        if (
            entitlement.entitlement_id
            != expected_entitlement_id
        ):
            raise RuntimeError(
                "Commercial entitlement identity did not converge."
            )

        if (
            entitlement.status
            is not CustomerCommercialEntitlementStatus.ACTIVE
        ):
            raise ValueError(
                "Setup activation requires an ACTIVE "
                "commercial entitlement."
            )

        activation_request_id = (
            "payment-settlement-activation-"
            f"{normalized_settlement_id}"
        )

        return self._setup_activation_service.activate(
            activation_request_id=activation_request_id,
            customer_id=entitlement.customer_id,
        )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} must not be empty."
            )

        return normalized
