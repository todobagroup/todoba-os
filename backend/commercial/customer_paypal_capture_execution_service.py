"""
Authenticated customer PayPal approved-order capture execution.

Caller authority:
    authenticated customer + payment_intent_id

Server authority:
    authoritative payment intent
    -> authoritative commercial order
    -> authoritative PayPal binding
    -> server-owned PayPal order identity
    -> PayPal capture-order transport

This owner deliberately does not:
- accept customer_id from caller
- accept PayPal order identity from caller
- accept amount/currency/rail from caller
- create payment evidence
- verify webhook truth
- settle payment
- grant entitlement
- activate Setup
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
    CustomerCommercialOrderStatus,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentService,
    CustomerPaymentIntentStatus,
    PaymentRail,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingStatus,
    CustomerPayPalOrderBindingStore,
)
from backend.commercial.customer_paypal_order_http_client import (
    CustomerPayPalOrderHttpClient,
)


@dataclass(frozen=True)
class CustomerPayPalCaptureExecutionResult:
    payment_intent_id: str
    order_id: str
    paypal_order_id: str
    provider_status: str


class CustomerPayPalCaptureExecutionService:
    def __init__(
        self,
        *,
        payment_intent_service: CustomerPaymentIntentService,
        order_service: CustomerCommercialOrderService,
        paypal_binding_store: CustomerPayPalOrderBindingStore,
        paypal_order_client: CustomerPayPalOrderHttpClient,
    ) -> None:
        if not isinstance(
            payment_intent_service,
            CustomerPaymentIntentService,
        ):
            raise TypeError(
                "payment_intent_service must be "
                "CustomerPaymentIntentService."
            )

        if not isinstance(
            order_service,
            CustomerCommercialOrderService,
        ):
            raise TypeError(
                "order_service must be "
                "CustomerCommercialOrderService."
            )

        if not isinstance(
            paypal_binding_store,
            CustomerPayPalOrderBindingStore,
        ):
            raise TypeError(
                "paypal_binding_store must be "
                "CustomerPayPalOrderBindingStore."
            )

        if not isinstance(
            paypal_order_client,
            CustomerPayPalOrderHttpClient,
        ):
            raise TypeError(
                "paypal_order_client must be "
                "CustomerPayPalOrderHttpClient."
            )

        if not paypal_binding_store.is_ready():
            raise RuntimeError(
                "Customer PayPal order binding store "
                "is not initialized."
            )

        self._payment_intent_service = (
            payment_intent_service
        )
        self._order_service = order_service
        self._paypal_binding_store = (
            paypal_binding_store
        )
        self._paypal_order_client = (
            paypal_order_client
        )

    def capture(
        self,
        *,
        payment_intent_id: str,
        authenticated_customer: CustomerIdentity,
    ) -> CustomerPayPalCaptureExecutionResult:
        normalized_intent_id = (
            self._normalize_required_string(
                payment_intent_id,
                name="payment_intent_id",
            )
        )

        if not isinstance(
            authenticated_customer,
            CustomerIdentity,
        ):
            raise TypeError(
                "authenticated_customer must be "
                "CustomerIdentity."
            )

        intent = self._payment_intent_service.get(
            payment_intent_id=normalized_intent_id
        )

        if intent is None:
            raise ValueError(
                "Payment intent is not authoritative."
            )

        if (
            intent.payment_intent_id
            != normalized_intent_id
            or intent.payment_rail
            is not PaymentRail.PAYPAL
            or intent.status
            is not CustomerPaymentIntentStatus.PENDING
        ):
            raise ValueError(
                "Payment intent is not eligible "
                "for PayPal capture."
            )

        order = self._order_service.get(
            order_id=intent.order_id
        )

        if order is None:
            raise ValueError(
                "Commercial order is not authoritative."
            )

        if (
            order.order_id
            != intent.order_id
            or order.customer_id
            != authenticated_customer.customer_id
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "Authenticated customer does not own "
                "the authoritative pending order."
            )

        binding = (
            self._paypal_binding_store
            .get_by_payment_intent_id(
                payment_intent_id=(
                    intent.payment_intent_id
                )
            )
        )

        if binding is None:
            raise ValueError(
                "PayPal order binding is not authoritative."
            )

        if (
            binding.status
            is not CustomerPayPalOrderBindingStatus.BOUND
            or binding.payment_intent_id
            != intent.payment_intent_id
            or binding.order_id
            != order.order_id
            or binding.paypal_request_id
            != intent.payment_intent_id
            or binding.amount_minor
            != order.amount_minor
            or binding.currency
            != order.currency
        ):
            raise ValueError(
                "PayPal order binding does not match "
                "authoritative commercial facts."
            )

        provider_status = (
            self._paypal_order_client.capture_order(
                paypal_order_id=(
                    binding.paypal_order_id
                ),
                paypal_request_id=(
                    "paypal-capture:"
                    f"{intent.payment_intent_id}"
                ),
            )
        )

        if provider_status != "COMPLETED":
            raise RuntimeError(
                "PayPal capture execution did not complete."
            )

        return CustomerPayPalCaptureExecutionResult(
            payment_intent_id=(
                intent.payment_intent_id
            ),
            order_id=order.order_id,
            paypal_order_id=(
                binding.paypal_order_id
            ),
            provider_status=provider_status,
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
                f"{name} is required."
            )

        return normalized