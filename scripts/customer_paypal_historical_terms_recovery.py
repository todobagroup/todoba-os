"""
One-time operator recovery owner for the PayPal Sandbox
historical-order-terms incident discovered in P8F13C-5C-R2M.

This owner is intentionally incident-specific.

Authority:
    authoritative SETTLED settlement
        -> exact authoritative commercial order
        -> exact current billing-cycle baseline
        -> missing immutable purchased order terms
        -> existing settlement activation bridge

Caller authority:
    none of customer_id, order_id, cycle_id, price, amount,
    currency, payment evidence, provider identity, or settlement
    facts are accepted from the caller.

This owner does NOT:
- capture or recapture PayPal payment
- verify provider payment
- create payment evidence
- create or mutate settlement
- mutate commercial order
- expose HTTP
- accept caller-supplied pricing
"""

from __future__ import annotations

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingRecord,
    CustomerCommercialOrderTermsBindingStore,
)
from backend.commercial.customer_commercial_current_billing_cycle_service import (
    CustomerCommercialCurrentBillingCycleService,
)
from backend.commercial.customer_payment_settlement_activation_bridge import (
    CustomerPaymentSettlementActivationBridge,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)


SETTLEMENT_ID = "payment-settlement-c7212ef5c542420ca10803b7cbcb32da"
ORDER_ID = "commercial-order-f7320b2d0a0c447a882821d7330492ba"
CUSTOMER_ID = "customer-7fbf874d6bf4413596354c3693ae253a"
CYCLE_ID = "paypal-sandbox-golden-20261006"

EXPECTED_AMOUNT_MINOR = 14000
EXPECTED_CURRENCY = "USD"
EXPECTED_CYCLE_BALANCE_USD = "3084.41"
EXPECTED_LICENSED_ACCOUNT_CAP_USD = 4000
EXPECTED_STANDARD_MONTHLY_PRICE_USD = 140


def recover_historical_paypal_order_terms(
    *,
    settlement_store: CustomerPaymentSettlementStore,
    order_store: CustomerCommercialOrderStore,
    current_billing_cycle_service: (
        CustomerCommercialCurrentBillingCycleService
    ),
    order_terms_store: CustomerCommercialOrderTermsBindingStore,
    activation_bridge: CustomerPaymentSettlementActivationBridge,
):
    """
    Recover exactly the missing immutable purchased terms for the
    locked Sandbox incident, then continue through the existing
    settlement -> entitlement -> Setup activation authority chain.

    Retry safety:
    - exact same terms registration is idempotent
    - conflicting existing terms fail closed in the terms store
    - downstream activation uses deterministic settlement lineage
    """

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
        current_billing_cycle_service,
        CustomerCommercialCurrentBillingCycleService,
    ):
        raise TypeError(
            "current_billing_cycle_service must be "
            "CustomerCommercialCurrentBillingCycleService."
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
        activation_bridge,
        CustomerPaymentSettlementActivationBridge,
    ):
        raise TypeError(
            "activation_bridge must be "
            "CustomerPaymentSettlementActivationBridge."
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
            "Commercial order terms store is not initialized."
        )

    settlement = settlement_store.get(
        settlement_id=SETTLEMENT_ID
    )

    if settlement is None:
        raise ValueError(
            "Locked recovery settlement is not authoritative."
        )

    if (
        settlement.settlement_id != SETTLEMENT_ID
        or settlement.order_id != ORDER_ID
        or settlement.customer_id != CUSTOMER_ID
        or settlement.amount_minor != EXPECTED_AMOUNT_MINOR
        or settlement.currency != EXPECTED_CURRENCY
        or settlement.status
        is not CustomerPaymentSettlementStatus.SETTLED
    ):
        raise ValueError(
            "Locked recovery settlement lineage mismatch."
        )

    order = order_store.get(
        order_id=ORDER_ID
    )

    if order is None:
        raise ValueError(
            "Locked recovery commercial order is not authoritative."
        )

    if (
        order.order_id != ORDER_ID
        or order.customer_id != CUSTOMER_ID
        or order.amount_minor != EXPECTED_AMOUNT_MINOR
        or order.currency != EXPECTED_CURRENCY
        or order.status
        is not CustomerCommercialOrderStatus.PENDING
        or order.order_id != settlement.order_id
        or order.customer_id != settlement.customer_id
        or order.amount_minor != settlement.amount_minor
        or order.currency != settlement.currency
    ):
        raise ValueError(
            "Locked recovery commercial order lineage mismatch."
        )

    baseline = (
        current_billing_cycle_service.resolve_current(
            customer_id=CUSTOMER_ID
        )
    )

    if (
        baseline.cycle_id != CYCLE_ID
        or baseline.customer_id != CUSTOMER_ID
        or str(
            baseline.authoritative_cycle_balance_usd
        )
        != EXPECTED_CYCLE_BALANCE_USD
        or baseline.licensed_account_cap_usd
        != EXPECTED_LICENSED_ACCOUNT_CAP_USD
        or baseline.standard_monthly_price_usd
        != EXPECTED_STANDARD_MONTHLY_PRICE_USD
        or (
            baseline.standard_monthly_price_usd * 100
            != order.amount_minor
        )
    ):
        raise ValueError(
            "Locked recovery billing-cycle terms mismatch."
        )

    existing_terms = order_terms_store.get_by_order_id(
        order_id=ORDER_ID
    )

    if existing_terms is not None:
        expected_existing = (
            CustomerCommercialOrderTermsBindingRecord(
                order_id=ORDER_ID,
                customer_id=CUSTOMER_ID,
                licensed_account_cap_usd=4000,
                standard_monthly_price_usd=140,
            )
        )

        if existing_terms != expected_existing:
            raise ValueError(
                "Locked recovery order already has "
                "conflicting commercial terms."
            )

        stored_terms = existing_terms

    else:
        stored_terms = order_terms_store.register(
            CustomerCommercialOrderTermsBindingRecord(
                order_id=ORDER_ID,
                customer_id=CUSTOMER_ID,
                licensed_account_cap_usd=4000,
                standard_monthly_price_usd=140,
            )
        )

    if (
        stored_terms.order_id != ORDER_ID
        or stored_terms.customer_id != CUSTOMER_ID
        or stored_terms.licensed_account_cap_usd
        != EXPECTED_LICENSED_ACCOUNT_CAP_USD
        or stored_terms.standard_monthly_price_usd
        != EXPECTED_STANDARD_MONTHLY_PRICE_USD
    ):
        raise RuntimeError(
            "Recovered commercial order terms did not converge."
        )

    activation = activation_bridge.activate_from_settlement(
        settlement_id=SETTLEMENT_ID
    )

    return stored_terms, activation
