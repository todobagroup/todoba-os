from __future__ import annotations

from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementRegistry,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingStore,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)


class CustomerPaymentSettlementEntitlementConvergenceService:
    """
    Converge authoritative settled payment truth into exactly one
    purchased commercial entitlement.

    The caller supplies settlement_id only.

    This service does not:
    - verify or mutate payment settlement
    - activate customer Setup
    - bind deployment / MT5 identity
    - authorize runtime
    - perform network or HTTP work
    """

    def __init__(
        self,
        *,
        settlement_store: CustomerPaymentSettlementStore,
        order_store: CustomerCommercialOrderStore,
        order_terms_store: CustomerCommercialOrderTermsBindingStore,
        entitlement_registry: CustomerCommercialEntitlementRegistry,
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
                "order_store must be "
                "CustomerCommercialOrderStore."
            )

        if not isinstance(
            order_terms_store,
            CustomerCommercialOrderTermsBindingStore,
        ):
            raise TypeError(
                "order_terms_store must be "
                "CustomerCommercialOrderTermsBindingStore."
            )

        if not isinstance(
            entitlement_registry,
            CustomerCommercialEntitlementRegistry,
        ):
            raise TypeError(
                "entitlement_registry must be "
                "CustomerCommercialEntitlementRegistry."
            )

        if not settlement_store.is_ready():
            raise RuntimeError(
                "Payment settlement store is not initialized."
            )

        if not order_store.is_ready():
            raise RuntimeError(
                "Commercial order store is not initialized."
            )

        if not order_terms_store.is_ready():
            raise RuntimeError(
                "Order terms binding store is not initialized."
            )

        if not entitlement_registry.is_ready():
            raise RuntimeError(
                "Commercial entitlement registry "
                "is not initialized."
            )

        self._settlement_store = settlement_store
        self._order_store = order_store
        self._order_terms_store = order_terms_store
        self._entitlement_registry = entitlement_registry

    def converge(
        self,
        *,
        settlement_id: str,
    ) -> CustomerCommercialEntitlement:
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
            order.order_id
            != settlement.order_id
            or order.customer_id
            != settlement.customer_id
            or order.amount_minor
            != settlement.amount_minor
            or order.currency
            != settlement.currency
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "Payment settlement does not match "
                "authoritative commercial order."
            )

        terms = (
            self._order_terms_store
            .get_by_order_id(
                order_id=settlement.order_id
            )
        )

        if terms is None:
            raise ValueError(
                "Purchased commercial order terms "
                "are not authoritative."
            )

        if (
            terms.order_id
            != settlement.order_id
            or terms.customer_id
            != settlement.customer_id
        ):
            raise ValueError(
                "Purchased commercial order terms "
                "do not match settlement truth."
            )

        entitlement = CustomerCommercialEntitlement(
            entitlement_id=(
                "commercial-entitlement-"
                f"{settlement.settlement_id}"
            ),
            order_id=settlement.order_id,
            customer_id=settlement.customer_id,
            licensed_account_cap_usd=(
                terms.licensed_account_cap_usd
            ),
            standard_monthly_price_usd=(
                terms.standard_monthly_price_usd
            ),
            status=(
                CustomerCommercialEntitlementStatus.ACTIVE
            ),
        )

        return self._entitlement_registry.register(
            entitlement
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
