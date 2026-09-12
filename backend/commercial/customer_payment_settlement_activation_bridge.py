from __future__ import annotations

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementRecord,
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
    CustomerSetupActivationService,
)


class CustomerPaymentSettlementActivationBridge:
    """
    Narrow bridge from authoritative SETTLED payment truth to
    the existing setup activation owner.

    Input authority:
        settlement_id only

    This owner does not:
    - receive payment evidence
    - verify provider payment
    - settle payment
    - create duplicate activation persistence
    - accept caller-supplied customer_id
    """

    def __init__(
        self,
        *,
        settlement_store: CustomerPaymentSettlementStore,
        order_store: CustomerCommercialOrderStore,
        setup_activation_service: CustomerSetupActivationService,
    ) -> None:
        if not isinstance(
            settlement_store,
            CustomerPaymentSettlementStore,
        ):
            raise TypeError(
                "settlement_store must be "
                "CustomerPaymentSettlementStore."
            )

        if not isinstance(
            order_store,
            CustomerCommercialOrderStore,
        ):
            raise TypeError(
                "order_store must be CustomerCommercialOrderStore."
            )

        if not isinstance(
            setup_activation_service,
            CustomerSetupActivationService,
        ):
            raise TypeError(
                "setup_activation_service must be "
                "CustomerSetupActivationService."
            )

        if not settlement_store.is_ready():
            raise RuntimeError(
                "Customer payment settlement store "
                "is not initialized."
            )

        if not order_store.is_ready():
            raise RuntimeError(
                "Commercial order store is not initialized."
            )

        self._settlement_store = settlement_store
        self._order_store = order_store
        self._setup_activation_service = setup_activation_service

    def activate_from_settlement(
        self,
        *,
        settlement_id: str,
    ) -> CustomerSetupActivationResult:
        normalized_settlement_id = (
            self._normalize_required_string(
                settlement_id,
                name="settlement_id",
            )
        )

        settlement = self._settlement_store.get(
            settlement_id=normalized_settlement_id
        )

        if settlement is None:
            raise ValueError(
                "Payment settlement is not authoritative."
            )

        if (
            settlement.settlement_id
            != normalized_settlement_id
            or settlement.status
            is not CustomerPaymentSettlementStatus.SETTLED
        ):
            raise ValueError(
                "Payment settlement is not settled "
                "authoritative truth."
            )

        order = self._order_store.get(
            order_id=settlement.order_id
        )

        if order is None:
            raise ValueError(
                "Commercial order is not authoritative."
            )

        if (
            order.order_id != settlement.order_id
            or order.customer_id != settlement.customer_id
            or order.amount_minor != settlement.amount_minor
            or order.currency != settlement.currency
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "Payment settlement does not match "
                "authoritative commercial order."
            )

        activation_request_id = (
            "payment-settlement-activation-"
            f"{settlement.settlement_id}"
        )

        return self._setup_activation_service.activate(
            activation_request_id=activation_request_id,
            customer_id=settlement.customer_id,
        )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} must not be empty."
            )

        return normalized
