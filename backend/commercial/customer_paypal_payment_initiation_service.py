"""
Authenticated customer PayPal payment initiation orchestration.

Authority chain:

authenticated CustomerIdentity
    -> authoritative current commercial cycle
    -> deterministic USD price book
    -> server-owned USD minor-unit conversion
    -> authoritative commercial order
    -> PAYPAL payment intent
    -> PayPal create-order provider call
    -> authoritative durable PayPal order binding

Security rules:
- caller supplies no customer_id
- caller supplies no balance, USD price, amount, or currency
- caller supplies no payment rail
- caller supplies no PayPal order identity
- pricing is derived only from authoritative commercial state
- payment intent ID is the PayPal custom_id and provider request identity
- settlement, evidence, entitlement, and activation are outside this owner
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
)
from backend.commercial.customer_commercial_current_billing_cycle_service import (
    CustomerCommercialCurrentBillingCycleService,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderResult,
    CustomerCommercialOrderService,
)
from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingRecord,
    CustomerCommercialOrderTermsBindingStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentResult,
    CustomerPaymentIntentService,
    PaymentRail,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingRecord,
    CustomerPayPalOrderBindingService,
    PayPalOrderCreationResult,
)
from backend.commercial.customer_paypal_order_http_client import (
    CustomerPayPalOrderHttpClient,
)


_USD_MINOR_UNIT_FACTOR = 100
_PAYPAL_CURRENCY = "USD"


@dataclass(frozen=True)
class CustomerPayPalPaymentInitiationResult:
    order: CustomerCommercialOrderResult
    payment_intent: CustomerPaymentIntentResult
    paypal_order: PayPalOrderCreationResult
    binding: CustomerPayPalOrderBindingRecord


class CustomerPayPalPaymentInitiationService:
    """
    Compose existing authoritative commercial and PayPal owners.

    This service owns no durable store and no settlement authority.
    """

    def __init__(
        self,
        *,
        current_billing_cycle_service: (
            CustomerCommercialCurrentBillingCycleService
        ),
        order_service: CustomerCommercialOrderService,
        order_terms_store: CustomerCommercialOrderTermsBindingStore,
        payment_intent_service: CustomerPaymentIntentService,
        paypal_order_client: CustomerPayPalOrderHttpClient,
        paypal_binding_service: CustomerPayPalOrderBindingService,
    ) -> None:
        if not isinstance(
            current_billing_cycle_service,
            CustomerCommercialCurrentBillingCycleService,
        ):
            raise TypeError(
                "current_billing_cycle_service must be "
                "CustomerCommercialCurrentBillingCycleService."
            )

        if not isinstance(
            order_service,
            CustomerCommercialOrderService,
        ):
            raise TypeError(
                "order_service must be CustomerCommercialOrderService."
            )

        if not isinstance(
            order_terms_store,
            CustomerCommercialOrderTermsBindingStore,
        ):
            raise TypeError(
                "order_terms_store must be "
                "CustomerCommercialOrderTermsBindingStore."
            )

        if not order_terms_store.is_ready():
            raise RuntimeError(
                "order_terms_store must be initialized."
            )

        if not isinstance(
            payment_intent_service,
            CustomerPaymentIntentService,
        ):
            raise TypeError(
                "payment_intent_service must be "
                "CustomerPaymentIntentService."
            )

        if not isinstance(
            paypal_order_client,
            CustomerPayPalOrderHttpClient,
        ):
            raise TypeError(
                "paypal_order_client must be "
                "CustomerPayPalOrderHttpClient."
            )

        if not isinstance(
            paypal_binding_service,
            CustomerPayPalOrderBindingService,
        ):
            raise TypeError(
                "paypal_binding_service must be "
                "CustomerPayPalOrderBindingService."
            )

        self._current_billing_cycle_service = (
            current_billing_cycle_service
        )
        self._order_service = order_service
        self._order_terms_store = order_terms_store
        self._payment_intent_service = payment_intent_service
        self._paypal_order_client = paypal_order_client
        self._paypal_binding_service = paypal_binding_service

    def initiate(
        self,
        *,
        initiation_request_id: str,
        authenticated_customer: CustomerIdentity,
    ) -> CustomerPayPalPaymentInitiationResult:
        request_id = self._normalize_request_id(
            initiation_request_id
        )

        if not isinstance(
            authenticated_customer,
            CustomerIdentity,
        ):
            raise TypeError(
                "authenticated_customer must be CustomerIdentity."
            )

        baseline = (
            self._current_billing_cycle_service.resolve_current(
                customer_id=authenticated_customer.customer_id
            )
        )

        quote = CustomerCommercialAccountPriceBook.quote(
            authoritative_cycle_balance_usd=(
                baseline.authoritative_cycle_balance_usd
            )
        )

        if (
            quote.licensed_account_cap_usd
            != baseline.licensed_account_cap_usd
            or quote.standard_monthly_price_usd
            != baseline.standard_monthly_price_usd
        ):
            raise RuntimeError(
                "Authoritative billing-cycle pricing facts "
                "do not match the current price book."
            )

        amount_minor = (
            quote.standard_monthly_price_usd
            * _USD_MINOR_UNIT_FACTOR
        )

        if amount_minor <= 0:
            raise RuntimeError(
                "Authoritative PayPal amount is invalid."
            )

        order = self._order_service.create(
            order_request_id=f"{request_id}:order",
            authorized_customer=authenticated_customer,
            amount_minor=amount_minor,
            currency=_PAYPAL_CURRENCY,
        )

        self._order_terms_store.register(
            CustomerCommercialOrderTermsBindingRecord(
                order_id=order.order_id,
                customer_id=order.customer_id,
                licensed_account_cap_usd=(
                    quote.licensed_account_cap_usd
                ),
                standard_monthly_price_usd=(
                    quote.standard_monthly_price_usd
                ),
            )
        )

        payment_intent = self._payment_intent_service.create(
            payment_intent_request_id=f"{request_id}:intent",
            authorized_order=order,
            payment_rail=PaymentRail.PAYPAL,
        )

        paypal_order = self._paypal_order_client.create_order(
            payment_intent_id=(
                payment_intent.payment_intent_id
            ),
            amount_minor=order.amount_minor,
            currency=order.currency,
        )

        if (
            paypal_order.custom_id
            != payment_intent.payment_intent_id
            or paypal_order.paypal_request_id
            != payment_intent.payment_intent_id
            or paypal_order.amount_minor
            != order.amount_minor
            or paypal_order.currency
            != order.currency
            or not isinstance(
                paypal_order.approval_url,
                str,
            )
            or not paypal_order.approval_url.strip()
        ):
            raise RuntimeError(
                "PayPal order does not match "
                "authoritative payment intent."
            )

        binding = self._paypal_binding_service.bind(
            authorized_payment_intent=payment_intent,
            paypal_order=paypal_order,
        )

        if (
            binding.payment_intent_id
            != payment_intent.payment_intent_id
            or binding.order_id
            != order.order_id
            or binding.paypal_order_id
            != paypal_order.paypal_order_id
            or binding.amount_minor
            != order.amount_minor
            or binding.currency
            != order.currency
        ):
            raise RuntimeError(
                "PayPal binding does not match "
                "authoritative commercial payment."
            )

        return CustomerPayPalPaymentInitiationResult(
            order=order,
            payment_intent=payment_intent,
            paypal_order=paypal_order,
            binding=binding,
        )

    @staticmethod
    def _normalize_request_id(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "initiation_request_id must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "initiation_request_id is required."
            )

        return normalized
