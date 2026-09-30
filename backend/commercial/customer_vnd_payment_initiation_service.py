"""
TODOBA Customer VND Payment Initiation Service

Server-authoritative orchestration boundary for beginning one
customer VND bank-transfer payment.

Trust flow:

    authenticated CustomerIdentity
        -> authoritative current billing cycle
        -> deterministic USD price book
        -> immutable VND pricing projection
        -> immutable commercial order
        -> VND-bank payment intent
        -> server-owned bank payment instruction

Security rules:
- caller supplies no customer_id
- caller supplies no balance, USD price, VND amount, or currency
- caller supplies no payment rail
- caller supplies no bank destination
- current commercial-cycle authority must already exist
- pricing must be derived from authoritative cycle balance
- request identity deterministically binds all downstream
  idempotency identities
- settlement, reconciliation, entitlement, and activation are
  deliberately outside this owner
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
from backend.commercial.customer_commercial_vnd_order_pricing_projection import (
    CustomerCommercialVndOrderPricingProjectionRecord,
    CustomerCommercialVndOrderPricingProjectionService,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentResult,
    CustomerPaymentIntentService,
    PaymentRail,
)
from backend.commercial.customer_vnd_bank_payment_instruction_service import (
    CustomerVndBankPaymentInstructionResult,
    CustomerVndBankPaymentInstructionService,
)


@dataclass(frozen=True)
class CustomerVndPaymentInitiationResult:
    pricing: CustomerCommercialVndOrderPricingProjectionRecord
    order: CustomerCommercialOrderResult
    payment_intent: CustomerPaymentIntentResult
    instruction: CustomerVndBankPaymentInstructionResult


class CustomerVndPaymentInitiationService:
    """
    Compose existing authoritative commercial/payment owners.

    This service intentionally owns no durable store itself.
    """

    def __init__(
        self,
        *,
        current_billing_cycle_service: (
            CustomerCommercialCurrentBillingCycleService
        ),
        vnd_pricing_projection_service: (
            CustomerCommercialVndOrderPricingProjectionService
        ),
        order_service: CustomerCommercialOrderService,
        payment_intent_service: CustomerPaymentIntentService,
        payment_instruction_service: (
            CustomerVndBankPaymentInstructionService
        ),
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
            vnd_pricing_projection_service,
            CustomerCommercialVndOrderPricingProjectionService,
        ):
            raise TypeError(
                "vnd_pricing_projection_service must be "
                "CustomerCommercialVndOrderPricingProjectionService."
            )

        if not isinstance(
            order_service,
            CustomerCommercialOrderService,
        ):
            raise TypeError(
                "order_service must be CustomerCommercialOrderService."
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
            payment_instruction_service,
            CustomerVndBankPaymentInstructionService,
        ):
            raise TypeError(
                "payment_instruction_service must be "
                "CustomerVndBankPaymentInstructionService."
            )

        self._current_billing_cycle_service = (
            current_billing_cycle_service
        )
        self._vnd_pricing_projection_service = (
            vnd_pricing_projection_service
        )
        self._order_service = order_service
        self._payment_intent_service = payment_intent_service
        self._payment_instruction_service = (
            payment_instruction_service
        )

    def initiate(
        self,
        *,
        initiation_request_id: str,
        authenticated_customer: CustomerIdentity,
    ) -> CustomerVndPaymentInitiationResult:
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

        pricing = self._vnd_pricing_projection_service.create(
            pricing_request_id=f"{request_id}:pricing",
            customer_id=authenticated_customer.customer_id,
            usd_price=quote.standard_monthly_price_usd,
        )

        order = self._order_service.create(
            order_request_id=f"{request_id}:order",
            authorized_customer=authenticated_customer,
            amount_minor=pricing.amount_minor,
            currency=pricing.currency,
        )

        payment_intent = self._payment_intent_service.create(
            payment_intent_request_id=f"{request_id}:intent",
            authorized_order=order,
            payment_rail=PaymentRail.VND_BANK_TRANSFER,
        )

        instruction = self._payment_instruction_service.build(
            payment_intent_id=payment_intent.payment_intent_id
        )

        if (
            instruction.order_id != order.order_id
            or instruction.amount_minor != order.amount_minor
            or instruction.currency != order.currency
        ):
            raise RuntimeError(
                "Payment instruction does not match "
                "authoritative commercial order."
            )

        return CustomerVndPaymentInitiationResult(
            pricing=pricing,
            order=order,
            payment_intent=payment_intent,
            instruction=instruction,
        )

    @staticmethod
    def _normalize_request_id(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError(
                "initiation_request_id must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "initiation_request_id is required."
            )

        return normalized
