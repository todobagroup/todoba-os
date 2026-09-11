"""
TODOBA Customer PayPal Capture Verification Adapter

Owns provider-specific PayPal verification convergence:

    verified PayPal webhook authenticity
        + server-read COMPLETED PayPal capture
        + authoritative PayPal order binding
        + authoritative payment evidence
        + authoritative payment intent
        + authoritative commercial order
        -> PaymentVerificationAssertion

This adapter deliberately does not:
- perform HTTP/network access
- verify webhook cryptography itself
- fetch PayPal capture details itself
- create or persist payment evidence
- persist verification assertions
- settle payments
- grant activation or entitlement
"""

from __future__ import annotations

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceStatus,
    CustomerPaymentEvidenceStore,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)
from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)
from backend.commercial.customer_paypal_capture_http_client import (
    PayPalCaptureDetails,
)
from backend.commercial.customer_paypal_order_binding_service import (
    CustomerPayPalOrderBindingStatus,
    CustomerPayPalOrderBindingStore,
)
from backend.commercial.customer_paypal_webhook_verification_client import (
    PayPalWebhookVerificationResult,
)


_PAYPAL_CAPTURE_COMPLETED_EVENT = (
    "PAYMENT.CAPTURE.COMPLETED"
)


class CustomerPayPalCaptureVerificationAdapter:
    """
    Build one normalized settlement assertion only from an exact
    authoritative PayPal commercial chain.
    """

    def __init__(
        self,
        *,
        paypal_binding_store: CustomerPayPalOrderBindingStore,
        payment_evidence_store: CustomerPaymentEvidenceStore,
        payment_intent_store: CustomerPaymentIntentStore,
        order_store: CustomerCommercialOrderStore,
    ) -> None:
        if not isinstance(
            paypal_binding_store,
            CustomerPayPalOrderBindingStore,
        ):
            raise TypeError(
                "paypal_binding_store must be "
                "CustomerPayPalOrderBindingStore."
            )

        if not isinstance(
            payment_evidence_store,
            CustomerPaymentEvidenceStore,
        ):
            raise TypeError(
                "payment_evidence_store must be "
                "CustomerPaymentEvidenceStore."
            )

        if not isinstance(
            payment_intent_store,
            CustomerPaymentIntentStore,
        ):
            raise TypeError(
                "payment_intent_store must be "
                "CustomerPaymentIntentStore."
            )

        if not isinstance(
            order_store,
            CustomerCommercialOrderStore,
        ):
            raise TypeError(
                "order_store must be "
                "CustomerCommercialOrderStore."
            )

        self._paypal_binding_store = (
            paypal_binding_store
        )
        self._payment_evidence_store = (
            payment_evidence_store
        )
        self._payment_intent_store = (
            payment_intent_store
        )
        self._order_store = order_store

    def build_assertion(
        self,
        *,
        webhook_verification: PayPalWebhookVerificationResult,
        capture: PayPalCaptureDetails,
    ) -> PaymentVerificationAssertion:
        if not isinstance(
            webhook_verification,
            PayPalWebhookVerificationResult,
        ):
            raise TypeError(
                "webhook_verification must be "
                "PayPalWebhookVerificationResult."
            )

        if not isinstance(
            capture,
            PayPalCaptureDetails,
        ):
            raise TypeError(
                "capture must be PayPalCaptureDetails."
            )

        self._verify_webhook_gate(
            webhook_verification
        )

        binding = (
            self._paypal_binding_store
            .get_by_paypal_order_id(
                paypal_order_id=capture.order_id
            )
        )

        if binding is None:
            raise ValueError(
                "PayPal capture has no authoritative "
                "PayPal order binding."
            )

        if (
            binding.status
            is not CustomerPayPalOrderBindingStatus.BOUND
            or binding.paypal_order_id
            != capture.order_id
            or binding.paypal_request_id
            != binding.payment_intent_id
        ):
            raise ValueError(
                "PayPal binding does not match "
                "authoritative provider truth."
            )

        if (
            capture.custom_id
            != binding.payment_intent_id
        ):
            raise ValueError(
                "PayPal capture intent identity "
                "does not match binding."
            )

        if (
            capture.amount_minor
            != binding.amount_minor
            or capture.currency
            != binding.currency
        ):
            raise ValueError(
                "PayPal capture amount or currency "
                "does not match binding."
            )

        intent = self._payment_intent_store.get(
            payment_intent_id=(
                binding.payment_intent_id
            )
        )

        if intent is None:
            raise ValueError(
                "PayPal payment intent is not authoritative."
            )

        if (
            intent.payment_intent_id
            != binding.payment_intent_id
            or intent.order_id
            != binding.order_id
        ):
            raise ValueError(
                "PayPal binding does not match "
                "authoritative payment intent."
            )

        if (
            intent.payment_rail
            is not PaymentRail.PAYPAL
        ):
            raise ValueError(
                "PayPal verification requires "
                "a PayPal payment intent."
            )

        if (
            intent.status
            is not CustomerPaymentIntentStatus.PENDING
        ):
            raise ValueError(
                "PayPal payment intent is not "
                "in authoritative pending state."
            )

        evidence = (
            self._payment_evidence_store
            .get_by_replay_identity(
                evidence_source=(
                    PaymentEvidenceSource.PAYPAL
                ),
                external_evidence_id=(
                    capture.capture_id
                ),
            )
        )

        if evidence is None:
            raise ValueError(
                "PayPal capture evidence is not authoritative."
            )

        if (
            evidence.payment_intent_id
            != intent.payment_intent_id
            or evidence.evidence_source
            is not PaymentEvidenceSource.PAYPAL
            or evidence.external_evidence_id
            != capture.capture_id
            or evidence.status
            is not CustomerPaymentEvidenceStatus.RECEIVED
        ):
            raise ValueError(
                "PayPal evidence does not match "
                "authoritative capture truth."
            )

        order = self._order_store.get(
            order_id=binding.order_id
        )

        if order is None:
            raise ValueError(
                "PayPal commercial order is not authoritative."
            )

        if (
            order.order_id
            != intent.order_id
            or order.order_id
            != binding.order_id
        ):
            raise ValueError(
                "PayPal binding does not match "
                "authoritative commercial order."
            )

        if (
            order.amount_minor
            != binding.amount_minor
            or order.currency
            != binding.currency
        ):
            raise ValueError(
                "PayPal binding does not match "
                "authoritative commercial order facts."
            )

        if (
            capture.amount_minor
            != order.amount_minor
            or capture.currency
            != order.currency
        ):
            raise ValueError(
                "PayPal capture does not match "
                "authoritative commercial order facts."
            )

        if (
            order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "PayPal commercial order is not "
                "in authoritative pending state."
            )

        return PaymentVerificationAssertion(
            verification_assertion_id=(
                "paypal-verification-"
                f"{capture.capture_id}"
            ),
            payment_evidence_id=(
                evidence.payment_evidence_id
            ),
            payment_intent_id=(
                intent.payment_intent_id
            ),
            order_id=order.order_id,
            customer_id=order.customer_id,
            amount_minor=order.amount_minor,
            currency=order.currency,
            evidence_source=(
                PaymentEvidenceSource.PAYPAL
            ),
            external_evidence_id=(
                capture.capture_id
            ),
        )

    @staticmethod
    def _verify_webhook_gate(
        webhook_verification: PayPalWebhookVerificationResult,
    ) -> None:
        if (
            webhook_verification.verification_status
            != "SUCCESS"
        ):
            raise ValueError(
                "PayPal webhook verification did not succeed."
            )

        if (
            webhook_verification.event_type
            != _PAYPAL_CAPTURE_COMPLETED_EVENT
        ):
            raise ValueError(
                "PayPal webhook event is not "
                "PAYMENT.CAPTURE.COMPLETED."
            )
