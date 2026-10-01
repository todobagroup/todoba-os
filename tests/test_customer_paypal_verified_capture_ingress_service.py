from types import SimpleNamespace

import pytest

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

from backend.commercial.customer_paypal_verified_capture_ingress_service import (
    CustomerPayPalVerifiedCaptureIngressService,
)


CAPTURE_ID = "CAPTURE-001"
PAYPAL_ORDER_ID = "PAYPAL-ORDER-001"
PAYMENT_INTENT_ID = "payment-intent-001"


class RecordingWebhookVerifier:
    def __init__(self):
        self.calls = []

    def verify(
        self,
        *,
        headers,
        webhook_event,
    ):
        self.calls.append(
            (
                headers,
                webhook_event,
            )
        )

        return PayPalWebhookVerificationResult(
            webhook_event_id="WH-EVENT-001",
            event_type="PAYMENT.CAPTURE.COMPLETED",
            verification_status="SUCCESS",
        )


class RecordingCaptureClient:
    def __init__(self):
        self.calls = []

    def get_capture(
        self,
        *,
        capture_id,
    ):
        self.calls.append(capture_id)

        return PayPalCaptureDetails(
            capture_id=CAPTURE_ID,
            order_id=PAYPAL_ORDER_ID,
            custom_id=PAYMENT_INTENT_ID,
            amount_minor=1999,
            currency="USD",
            status="COMPLETED",
        )


class RecordingBindingStore:
    def __init__(self):
        self.calls = []

    def get_by_paypal_order_id(
        self,
        *,
        paypal_order_id,
    ):
        self.calls.append(paypal_order_id)

        return SimpleNamespace(
            paypal_order_id=PAYPAL_ORDER_ID,
            payment_intent_id=PAYMENT_INTENT_ID,
        )


class RecordingPaymentIntentService:
    def __init__(self):
        self.calls = []

    def get(
        self,
        *,
        payment_intent_id,
    ):
        self.calls.append(payment_intent_id)

        return SimpleNamespace(
            payment_intent_id=PAYMENT_INTENT_ID,
        )


class RecordingEvidenceService:
    def __init__(self):
        self.calls = []

    def receive(
        self,
        *,
        evidence_request_id,
        authorized_payment_intent,
        evidence_source,
        external_evidence_id,
    ):
        self.calls.append(
            {
                "evidence_request_id": evidence_request_id,
                "authorized_payment_intent": authorized_payment_intent,
                "evidence_source": evidence_source,
                "external_evidence_id": external_evidence_id,
            }
        )

        return SimpleNamespace(
            payment_evidence_id="payment-evidence-001",
            payment_intent_id=PAYMENT_INTENT_ID,
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id=CAPTURE_ID,
        )


class RecordingVerificationAdapter:
    def __init__(self):
        self.calls = []

    def build_assertion(
        self,
        *,
        webhook_verification,
        capture,
    ):
        self.calls.append(
            (
                webhook_verification,
                capture,
            )
        )

        return PaymentVerificationAssertion(
            verification_assertion_id=(
                "paypal-verification-CAPTURE-001"
            ),
            payment_evidence_id="payment-evidence-001",
            payment_intent_id=PAYMENT_INTENT_ID,
            order_id="order-001",
            customer_id="customer-001",
            amount_minor=1999,
            currency="USD",
            evidence_source=PaymentEvidenceSource.PAYPAL,
            external_evidence_id=CAPTURE_ID,
        )


class RecordingSettlementOrchestration:
    def __init__(self):
        self.calls = []

    def complete_verified_payment(
        self,
        *,
        verification_assertion,
    ):
        self.calls.append(
            verification_assertion
        )

        return SimpleNamespace(
            setup_activation_id="setup-activation-paypal-001",
            customer_id="customer-001",
        )


def _build():
    verifier = RecordingWebhookVerifier()
    capture_client = RecordingCaptureClient()
    binding_store = RecordingBindingStore()
    intent_service = RecordingPaymentIntentService()
    evidence_service = RecordingEvidenceService()
    adapter = RecordingVerificationAdapter()
    settlement = RecordingSettlementOrchestration()

    service = CustomerPayPalVerifiedCaptureIngressService(
        webhook_verification_client=verifier,
        capture_client=capture_client,
        paypal_binding_store=binding_store,
        payment_intent_service=intent_service,
        payment_evidence_service=evidence_service,
        capture_verification_adapter=adapter,
        settlement_orchestration_service=settlement,
    )

    return (
        service,
        verifier,
        capture_client,
        binding_store,
        intent_service,
        evidence_service,
        adapter,
        settlement,
    )


def _event():
    return {
        "id": "WH-EVENT-001",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": CAPTURE_ID,
        },
    }


def _headers():
    return {
        "PAYPAL-TRANSMISSION-ID": "transmission-001",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-01T00:00:00Z",
        "PAYPAL-CERT-URL": "https://api.paypal.com/cert.pem",
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-TRANSMISSION-SIG": "signature",
    }


def test_verified_capture_converges_into_existing_settlement():
    (
        service,
        verifier,
        capture_client,
        binding_store,
        intent_service,
        evidence_service,
        adapter,
        settlement,
    ) = _build()

    result = service.complete(
        headers=_headers(),
        webhook_event=_event(),
    )

    assert len(verifier.calls) == 1
    assert capture_client.calls == [CAPTURE_ID]
    assert binding_store.calls == [PAYPAL_ORDER_ID]
    assert intent_service.calls == [PAYMENT_INTENT_ID]

    assert len(evidence_service.calls) == 1

    evidence_call = evidence_service.calls[0]

    assert evidence_call["evidence_request_id"] == (
        "paypal-capture-evidence-CAPTURE-001"
    )

    assert (
        evidence_call["evidence_source"]
        is PaymentEvidenceSource.PAYPAL
    )

    assert evidence_call["external_evidence_id"] == CAPTURE_ID

    assert len(adapter.calls) == 1
    assert len(settlement.calls) == 1

    assert result.setup_activation_id == (
        "setup-activation-paypal-001"
    )


def test_webhook_body_cannot_supply_customer_order_or_amount_truth():
    (
        service,
        _,
        _,
        _,
        _,
        evidence_service,
        _,
        _,
    ) = _build()

    event = _event()

    event["customer_id"] = "customer-forged"
    event["order_id"] = "order-forged"
    event["amount_minor"] = 1
    event["currency"] = "XXX"
    event["payment_intent_id"] = "payment-intent-forged"

    service.complete(
        headers=_headers(),
        webhook_event=event,
    )

    evidence_call = evidence_service.calls[0]

    assert (
        evidence_call[
            "authorized_payment_intent"
        ].payment_intent_id
        == PAYMENT_INTENT_ID
    )


def test_capture_id_must_come_from_webhook_resource():
    service, *_ = _build()

    event = _event()
    del event["resource"]["id"]

    with pytest.raises(
        ValueError,
        match="capture",
    ):
        service.complete(
            headers=_headers(),
            webhook_event=event,
        )


def test_invalid_resource_shape_fails_before_capture_fetch():
    (
        service,
        _,
        capture_client,
        *_,
    ) = _build()

    event = _event()
    event["resource"] = []

    with pytest.raises(
        ValueError,
        match="resource",
    ):
        service.complete(
            headers=_headers(),
            webhook_event=event,
        )

    assert capture_client.calls == []


def test_unbound_paypal_order_fails_before_evidence():
    (
        service,
        _,
        _,
        binding_store,
        _,
        evidence_service,
        _,
        settlement,
    ) = _build()

    binding_store.get_by_paypal_order_id = (
        lambda **_: None
    )

    with pytest.raises(
        ValueError,
        match="binding",
    ):
        service.complete(
            headers=_headers(),
            webhook_event=_event(),
        )

    assert evidence_service.calls == []
    assert settlement.calls == []


def test_capture_custom_id_must_match_bound_intent():
    (
        service,
        _,
        capture_client,
        _,
        _,
        evidence_service,
        _,
        settlement,
    ) = _build()

    capture_client.get_capture = (
        lambda **_: PayPalCaptureDetails(
            capture_id=CAPTURE_ID,
            order_id=PAYPAL_ORDER_ID,
            custom_id="payment-intent-forged",
            amount_minor=1999,
            currency="USD",
            status="COMPLETED",
        )
    )

    with pytest.raises(
        ValueError,
        match="intent",
    ):
        service.complete(
            headers=_headers(),
            webhook_event=_event(),
        )

    assert evidence_service.calls == []
    assert settlement.calls == []


def test_service_has_no_direct_settlement_or_activation_authority():
    service, *_ = _build()

    for name in (
        "settle",
        "activate",
        "activate_from_settlement",
        "issue",
        "issue_once",
        "mark_paid",
    ):
        assert not hasattr(service, name)
