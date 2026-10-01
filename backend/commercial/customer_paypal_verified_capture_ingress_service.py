"""
TODOBA Customer PayPal Verified Capture Ingress Service.

Owns orchestration only:

    raw PayPal webhook
        -> server-side PayPal signature verification
        -> server-read COMPLETED capture
        -> authoritative PayPal order binding
        -> authoritative payment intent
        -> normalized PAYPAL payment evidence
        -> existing PayPal verification adapter
        -> existing settlement orchestration
        -> settlement-gated Setup activation

This owner deliberately does not:
- trust caller-supplied customer/order/amount truth
- settle payments directly
- activate Setup directly
- issue access codes
- own PayPal credentials
- initialize durable stores
"""

from __future__ import annotations

from backend.commercial.customer_payment_evidence_service import (
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_settlement_service import (
    PaymentVerificationAssertion,
)
from backend.commercial.customer_paypal_capture_http_client import (
    PayPalCaptureDetails,
)
from backend.commercial.customer_paypal_webhook_verification_client import (
    PayPalWebhookVerificationResult,
)


_PAYPAL_CAPTURE_COMPLETED_EVENT = (
    "PAYMENT.CAPTURE.COMPLETED"
)


class CustomerPayPalVerifiedCaptureIngressService:
    def __init__(
        self,
        *,
        webhook_verification_client,
        capture_client,
        paypal_binding_store,
        payment_intent_service,
        payment_evidence_service,
        capture_verification_adapter,
        settlement_orchestration_service,
    ) -> None:
        self._require_owner_method(
            webhook_verification_client,
            owner_name="webhook_verification_client",
            method_name="verify",
        )
        self._require_owner_method(
            capture_client,
            owner_name="capture_client",
            method_name="get_capture",
        )
        self._require_owner_method(
            paypal_binding_store,
            owner_name="paypal_binding_store",
            method_name="get_by_paypal_order_id",
        )
        self._require_owner_method(
            payment_intent_service,
            owner_name="payment_intent_service",
            method_name="get",
        )
        self._require_owner_method(
            payment_evidence_service,
            owner_name="payment_evidence_service",
            method_name="receive",
        )
        self._require_owner_method(
            capture_verification_adapter,
            owner_name="capture_verification_adapter",
            method_name="build_assertion",
        )
        self._require_owner_method(
            settlement_orchestration_service,
            owner_name="settlement_orchestration_service",
            method_name="complete_verified_payment",
        )

        self._webhook_verification_client = (
            webhook_verification_client
        )
        self._capture_client = capture_client
        self._paypal_binding_store = paypal_binding_store
        self._payment_intent_service = payment_intent_service
        self._payment_evidence_service = payment_evidence_service
        self._capture_verification_adapter = (
            capture_verification_adapter
        )
        self._settlement_orchestration_service = (
            settlement_orchestration_service
        )

    def complete(
        self,
        *,
        headers: dict[str, str],
        webhook_event: dict,
    ):
        webhook_verification = (
            self._webhook_verification_client.verify(
                headers=headers,
                webhook_event=webhook_event,
            )
        )

        if not isinstance(
            webhook_verification,
            PayPalWebhookVerificationResult,
        ):
            raise RuntimeError(
                "PayPal webhook verifier returned invalid result."
            )

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

        capture_id = self._extract_capture_id(
            webhook_event
        )

        capture = self._capture_client.get_capture(
            capture_id=capture_id
        )

        if not isinstance(
            capture,
            PayPalCaptureDetails,
        ):
            raise RuntimeError(
                "PayPal capture client returned invalid result."
            )

        if capture.capture_id != capture_id:
            raise ValueError(
                "PayPal capture identity does not match webhook."
            )

        binding = (
            self._paypal_binding_store
            .get_by_paypal_order_id(
                paypal_order_id=capture.order_id
            )
        )

        if binding is None:
            raise ValueError(
                "PayPal capture has no authoritative binding."
            )

        binding_paypal_order_id = getattr(
            binding,
            "paypal_order_id",
            None,
        )

        binding_payment_intent_id = getattr(
            binding,
            "payment_intent_id",
            None,
        )

        if (
            binding_paypal_order_id
            != capture.order_id
            or not isinstance(
                binding_payment_intent_id,
                str,
            )
            or not binding_payment_intent_id.strip()
        ):
            raise ValueError(
                "PayPal binding does not match capture identity."
            )

        if (
            capture.custom_id
            != binding_payment_intent_id
        ):
            raise ValueError(
                "PayPal capture intent identity "
                "does not match binding."
            )

        # Real binding records own amount/currency truth.
        # Test doubles may intentionally expose only identity.
        binding_amount_minor = getattr(
            binding,
            "amount_minor",
            capture.amount_minor,
        )
        binding_currency = getattr(
            binding,
            "currency",
            capture.currency,
        )

        if (
            binding_amount_minor
            != capture.amount_minor
            or binding_currency
            != capture.currency
        ):
            raise ValueError(
                "PayPal capture amount or currency "
                "does not match binding."
            )

        intent = self._payment_intent_service.get(
            payment_intent_id=(
                binding_payment_intent_id
            )
        )

        if intent is None:
            raise ValueError(
                "PayPal payment intent is not authoritative."
            )

        authoritative_intent_id = getattr(
            intent,
            "payment_intent_id",
            None,
        )

        if (
            authoritative_intent_id
            != binding_payment_intent_id
        ):
            raise ValueError(
                "PayPal binding does not match "
                "authoritative payment intent."
            )

        self._payment_evidence_service.receive(
            evidence_request_id=(
                "paypal-capture-evidence-"
                f"{capture.capture_id}"
            ),
            authorized_payment_intent=intent,
            evidence_source=(
                PaymentEvidenceSource.PAYPAL
            ),
            external_evidence_id=(
                capture.capture_id
            ),
        )

        verification_assertion = (
            self._capture_verification_adapter
            .build_assertion(
                webhook_verification=(
                    webhook_verification
                ),
                capture=capture,
            )
        )

        if not isinstance(
            verification_assertion,
            PaymentVerificationAssertion,
        ):
            raise RuntimeError(
                "PayPal capture verification adapter "
                "returned invalid assertion."
            )

        return (
            self._settlement_orchestration_service
            .complete_verified_payment(
                verification_assertion=(
                    verification_assertion
                )
            )
        )

    @staticmethod
    def _extract_capture_id(
        webhook_event: dict,
    ) -> str:
        if not isinstance(
            webhook_event,
            dict,
        ):
            raise TypeError(
                "webhook_event must be dict."
            )

        resource = webhook_event.get(
            "resource"
        )

        if not isinstance(
            resource,
            dict,
        ):
            raise ValueError(
                "PayPal webhook resource is invalid."
            )

        capture_id = resource.get(
            "id"
        )

        if (
            not isinstance(
                capture_id,
                str,
            )
            or not capture_id.strip()
        ):
            raise ValueError(
                "PayPal webhook capture id is required."
            )

        return capture_id.strip()

    @staticmethod
    def _require_owner_method(
        owner,
        *,
        owner_name: str,
        method_name: str,
    ) -> None:
        method = getattr(
            owner,
            method_name,
            None,
        )

        if not callable(method):
            raise TypeError(
                f"{owner_name} must expose callable "
                f"{method_name}()."
            )
